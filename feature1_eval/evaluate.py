"""
Evaluate a v1 checkpoint (MobileNetV2 / EfficientNet-B0, 35 classes) on the field
validation split or -- deliberately, with --final -- the frozen benchmark.

Reports (JSON + Markdown + per-image predictions CSV)
  - accuracy and macro-F1 with 95 % bootstrap intervals
  - two modes: "auto" (model picks among all classes) and "crop_given"
    (the crop selector: restricted to the photo's true crop)
  - per crop and per class precision / recall / F1
  - calibration: ECE before / after temperature scaling
  - accuracy on accepted photos vs share accepted, at the calibrated threshold
  - "unsupported" photos: share correctly rejected
  - for the v1 model: results on the classes it knows ("common classes"),
    plus the share of benchmark photos whose class it cannot predict at all

Usage
  python -m feature1_eval.evaluate --legacy models/cnn/mobilenetv2_sgreenintel_v6p2.pth --split val
  python -m feature1_eval.evaluate --legacy models/cnn/mobilenetv2_sgreenintel_v6p2.pth --split test --final --purpose "baseline v6p2"

Results go to work/eval_<checkpoint name>/<split>/ so evaluating one model can never overwrite
another's results, and report.json records the checkpoint's name, size, SHA-256 and date.
"""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from feature1_eval import config, inference, legacy, metrics, taxonomy
from feature1_eval.data import splits as sp


# Acceptance rulesets, by name, selected with --rules. Each has its own confidence AND entropy cutoff, separately for
# auto mode (all 35 classes compete) and crop-given mode (only the named crop's classes compete) -- the two modes see
# very different confidence/entropy ranges, so one shared pair is not necessarily right for both (confirmed by
# feature1_eval.calibrate on the validation split, 2 Oct 2026).
#   "current"    -- training/predict_api.py's shared values before calibration (0.70 confidence, 0.40 entropy, both modes)
#   "calibrated" -- feature1_eval.calibrate's 90%-target recommendation (see calibration.md); NOT yet in production --
#                   this ruleset exists so it can be CONFIRMED on the frozen benchmark before predict_api.py is changed
RULESETS = {
    "current": {"temperature": 1.0, "energy_threshold": float("inf"),
                "confidence_auto": 0.70, "entropy_auto": 0.40, "confidence_crop": 0.70, "entropy_crop": 0.40},
    "calibrated": {"temperature": 1.0, "energy_threshold": float("inf"),
                  "confidence_auto": 0.6819, "entropy_auto": 0.2496, "confidence_crop": 0.5927, "entropy_crop": 0.9997},
}


def fingerprint(path):
    """Name, size, SHA-256 (first 16 hex) and modification date of a checkpoint file."""
    import datetime as _dt
    import hashlib
    p = Path(path)
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return {"file": p.name, "bytes": p.stat().st_size, "sha256_16": h.hexdigest()[:16],
            "modified": _dt.datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds")}


def load_any(legacy_path, ruleset="current"):
    m, info = legacy.load(legacy_path)
    return m, info["classes"], info["meta"], dict(RULESETS[ruleset]), f"v1 ({Path(legacy_path).name}, {ruleset} rules)"


def score(y_true, logits, classes, cal=None):
    """All metrics for one set of (true labels as strings, logits)."""
    T = cal["temperature"] if cal else 1.0
    idx = {c: i for i, c in enumerate(classes)}
    known = np.array([t in idx for t in y_true])
    y = np.array([idx.get(t, -1) for t in y_true])
    p_cal = inference.softmax(logits, T)
    pred = p_cal.argmax(1)
    conf = p_cal.max(1)
    unsup = idx.get(taxonomy.UNSUPPORTED)
    supported = known & (y != unsup) if unsup is not None else known
    res = {"n": int(len(y_true)), "n_supported_known": int(supported.sum()),
           "share_unknown_to_model": float((~known & np.array([t != taxonomy.UNSUPPORTED for t in y_true])).mean())}

    def block(yv, pv, cv):
        acc = metrics.bootstrap_ci(metrics.accuracy, yv, pv, n=1000)
        f1 = metrics.bootstrap_ci(lambda a, b: metrics.macro_f1(a, b), yv, pv, n=500)
        return {"accuracy": acc[0], "accuracy_ci": acc[1:], "macro_f1": f1[0], "macro_f1_ci": f1[1:],
                "ece": metrics.ece(cv, yv == pv)}

    ys, ps, cs = y[supported], pred[supported], conf[supported]
    res["auto"] = block(ys, ps, cs)
    raw = inference.softmax(logits[supported])
    res["auto"]["ece_uncalibrated"] = metrics.ece(raw.max(1), raw.argmax(1) == ys)
    # per-photo normalised entropy, auto mode -- same formula as training/predict_api.py (H / log(n_classes_considered)),
    # kept per-photo (not just aggregated) so a calibration script can search confidence x entropy jointly on the val split
    p_sup = p_cal[supported]
    H_auto = -(p_sup * np.log(p_sup + 1e-9)).sum(1) / np.log(p_sup.shape[1])

    # crop selector mode
    pc_pred, pc_conf, pc_entropy = [], [], []
    for z, yy in zip(logits[supported], ys):
        crop = taxonomy.crop_of(classes[yy])
        p = inference.softmax(inference.restrict_to_crop(z, classes, crop), T)
        n_considered = int(np.isfinite(inference.restrict_to_crop(z, classes, crop)).sum())
        pc_pred.append(p.argmax())
        pc_conf.append(p.max())
        pc_entropy.append(-(p * np.log(p + 1e-9)).sum() / (np.log(n_considered) if n_considered > 1 else 1.0))
    pc_pred, pc_conf, pc_entropy = np.array(pc_pred), np.array(pc_conf), np.array(pc_entropy)
    res["crop_given"] = block(ys, pc_pred, pc_conf)

    # accepted photos at the ruleset's thresholds -- confidence AND entropy, for BOTH modes (previously a bug here
    # applied the entropy check to auto mode only, silently skipping it for crop_given and over-stating its accepted
    # share/accuracy; caught by cross-checking this report against feature1_eval.calibrate on the same predictions)
    if cal:
        for mode, pv, cv, ev, conf_thr, ent_thr in (("auto", ps, cs, H_auto, cal["confidence_auto"], cal["entropy_auto"]),
                                                     ("crop_given", pc_pred, pc_conf, pc_entropy, cal["confidence_crop"], cal["entropy_crop"])):
            m = (cv >= conf_thr) & (ev <= ent_thr) & (pv != (unsup if unsup is not None else -2))
            res[mode]["accepted_share"] = float(m.mean())
            res[mode]["accepted_accuracy"] = float((pv[m] == ys[m]).mean()) if m.any() else None
    res["auto"]["coverage_curve"] = metrics.coverage_curve(cs, ps == ys, points=11)

    # unsupported photos
    if unsup is not None and (y == unsup).any():
        u = y == unsup
        rej_class = pred[u] == unsup
        e = inference.energy(logits[u], T)
        rej_energy = e > cal["energy_threshold"] if cal else np.zeros(u.sum(), bool)
        res["unsupported_rejected"] = float((rej_class | rej_energy).mean())

    # per crop / per class
    per_crop = defaultdict(lambda: [0, 0])
    for yy, pp in zip(ys, ps):
        k = taxonomy.crop_of(classes[yy])
        per_crop[k][0] += int(yy == pp)
        per_crop[k][1] += 1
    res["per_crop_accuracy_auto"] = {k: {"accuracy": a / n, "n": n} for k, (a, n) in sorted(per_crop.items())}
    pcl = metrics.per_class(ys, ps, labels=sorted(set(ys.tolist())))
    res["per_class_auto"] = {classes[k]: v for k, v in pcl.items()}
    return res, pred, conf, pc_pred, H_auto, pc_conf, pc_entropy, supported


def to_markdown(name, split, res):
    a, c = res["auto"], res["crop_given"]
    f = lambda v, ci: f"{v:.1%} ({ci[0]:.1%}–{ci[1]:.1%})"
    lines = [f"# {name} — {split} split", "",
             f"Photos: {res['n']} (supported classes this model knows: {res['n_supported_known']}; "
             f"photos of classes unknown to this model: {res['share_unknown_to_model']:.1%})", "",
             "| Mode | Accuracy (95 % CI) | Macro-F1 (95 % CI) | ECE | Accepted share | Accuracy on accepted |",
             "|---|---|---|---|---|---|"]
    for label, b in (("Model picks crop and disease", a), ("Crop selected by user", c)):
        lines.append(f"| {label} | {f(b['accuracy'], b['accuracy_ci'])} | {f(b['macro_f1'], b['macro_f1_ci'])} | "
                     f"{b['ece']:.3f} | {b.get('accepted_share', float('nan')):.1%} | "
                     f"{(b.get('accepted_accuracy') or float('nan')):.1%} |")
    if "unsupported_rejected" in res:
        lines += ["", f"Unsupported-plant photos correctly rejected: {res['unsupported_rejected']:.1%}"]
    lines += ["", "| Crop | Accuracy | Photos |", "|---|---|---|"]
    for k, v in res["per_crop_accuracy_auto"].items():
        lines.append(f"| {k} | {v['accuracy']:.1%} | {v['n']} |")
    lines += ["", "| Class | Precision | Recall | F1 | Photos |", "|---|---|---|---|---|"]
    for k, v in sorted(res["per_class_auto"].items()):
        lines.append(f"| {k} | {v['precision']:.2f} | {v['recall']:.2f} | {v['f1']:.2f} | {v['support']} |")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--legacy", required=True, help="path to a v1 checkpoint (.pth)")
    ap.add_argument("--rules", default="current", choices=list(RULESETS), help="acceptance ruleset to report accepted_share/accepted_accuracy for")
    ap.add_argument("--split", default="val", choices=["val", "test"])
    ap.add_argument("--final", action="store_true", help="required for --split test")
    ap.add_argument("--purpose", default="")
    ap.add_argument("--tta", action="store_true")
    ap.add_argument("--splits", default=str(config.WORK_DIR / "splits.csv"))
    ap.add_argument("--data-root", default=str(config.DATA_ROOT))
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)

    model, classes, meta, cal, name = load_any(a.legacy, a.rules)
    model.to(inference.device())
    rows = sp.load_split(a.split, a.splits, final=a.final, purpose=a.purpose or name)
    logits = inference.logits_for_paths(model, [str(Path(a.data_root) / r["path"]) for r in rows], meta, a.tta)
    y_true = [r["label"] for r in rows]
    res, pred, conf, pc_pred, H_auto, pc_conf, pc_entropy, supported = score(y_true, logits, classes, cal)
    res.update({"model": name, "split": a.split, "tta": a.tta, "calibrated": False,
                "acceptance_rules": f"ruleset={a.rules}: auto accepts confidence >= {cal['confidence_auto']} and entropy <= "
                                    f"{cal['entropy_auto']}; crop_given accepts confidence >= {cal['confidence_crop']} and entropy <= "
                                    f"{cal['entropy_crop']}",
                "checkpoint": fingerprint(a.legacy)})

    out = Path(a.out or config.WORK_DIR / f"eval_{Path(a.legacy).stem}" / a.split)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(res, indent=1, default=float))
    (out / "report.md").write_text(to_markdown(name, a.split, res))
    with open(out / "predictions.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["path", "label", "label_known_to_model", "pred_auto", "conf_auto", "entropy_auto",
                    "pred_crop_given", "conf_crop_given", "entropy_crop_given"])
        sup = np.flatnonzero(supported).tolist()
        pc_pred_map = dict(zip(sup, pc_pred.tolist())) if len(pc_pred) == len(sup) else {}
        pc_conf_map = dict(zip(sup, pc_conf.tolist())) if len(pc_conf) == len(sup) else {}
        pc_entropy_map = dict(zip(sup, pc_entropy.tolist())) if len(pc_entropy) == len(sup) else {}
        H_map = dict(zip(sup, H_auto.tolist())) if len(H_auto) == len(sup) else {}
        for i, r in enumerate(rows):
            w.writerow([r["path"], r["label"], int(r["label"] in classes), classes[pred[i]], f"{conf[i]:.4f}",
                        f"{H_map[i]:.4f}" if i in H_map else "",
                        classes[pc_pred_map[i]] if i in pc_pred_map else "",
                        f"{pc_conf_map[i]:.4f}" if i in pc_conf_map else "",
                        f"{pc_entropy_map[i]:.4f}" if i in pc_entropy_map else ""])
    print(to_markdown(name, a.split, res))
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
