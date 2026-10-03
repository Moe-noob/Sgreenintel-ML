"""
Calibrate the two rejection thresholds (confidence, normalised entropy) that training/predict_api.py currently sets
to fixed, uncalibrated values (0.70 and 0.40) -- one shared pair used for both "auto" and "crop-given" mode.

Method
  For a target accuracy T and a mode (auto / crop_given): search entropy thresholds e (a grid over the observed
  range), and for each e restrict to photos with entropy <= e; within that subset, metrics.threshold_for_accuracy
  (already tested in test_data_pipeline.py) finds the lowest confidence threshold whose ACCEPTED photos reach T. The
  (e, that confidence threshold) pair accepting photos satisfying BOTH conf >= c AND entropy <= e is exactly what
  predict_api.py's rejection rule computes, so this is a direct joint search over the rule's own two knobs, not an
  approximation. The entropy grid point maximising overall coverage, among those whose chosen confidence threshold
  reaches T, is kept. Run separately for auto and crop_given, because crop-given mode's confidence/entropy sit in a
  different range (fewer competing classes), so one shared pair may not be the right trade-off for both.

  Only ever fit this on the VALIDATION split (data.splits.load_split refuses the frozen benchmark without
  final=True+a purpose). Confirm a chosen threshold on the frozen benchmark EXACTLY ONCE, by re-running
  feature1_eval.evaluate with --final on the TEST split and reading its accepted_share / accepted_accuracy at
  whatever threshold V1_RULES holds at the time -- this script does not touch the frozen benchmark itself.

Usage
  python -m feature1_eval.evaluate --legacy models/cnn/mobilenetv2_sgreenintel_v6p2.pth --split val
  python -m feature1_eval.calibrate --predictions feature1_eval/work/eval_mobilenetv2_sgreenintel_v6p2/val/predictions.csv
"""

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from feature1_eval import metrics

TARGETS = (0.75, 0.80, 0.85, 0.90, 0.95)
CURRENT_CONF, CURRENT_ENTROPY = 0.70, 0.40          # training/predict_api.py's current fixed values, for comparison


def _wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return (p, max(0.0, centre - half), min(1.0, centre + half))


def joint_search(conf, entropy, correct, target, grid=200):
    """
    Best (conf_threshold, entropy_threshold, coverage, accuracy) for one target accuracy: the entropy cut-off, among
    `grid` candidates spanning the observed range, whose paired (lowest-possible) confidence cut-off reaches `target`
    accuracy on the jointly accepted photos, maximising coverage. Returns None if no entropy cut-off can reach the
    target at all (not even accepting the single most-confident, lowest-entropy photo).
    """
    conf, entropy, correct = (np.asarray(a) for a in (conf, entropy, correct))
    correct = correct.astype(bool)
    best = None
    for e in np.linspace(entropy.min(), entropy.max(), grid):
        m = entropy <= e
        if not m.any():
            continue
        c_thr, _, _ = metrics.threshold_for_accuracy(conf[m], correct[m], target)
        accepted = m & (conf >= c_thr)
        n = int(accepted.sum())
        if n == 0:
            continue
        acc = float(correct[accepted].mean())
        if acc + 1e-9 < target:            # threshold_for_accuracy can return (1.0, 0, nan) when target is unreachable in this subset
            continue
        cov = n / len(conf)
        if best is None or cov > best["coverage"]:
            best = {"confidence_threshold": round(float(c_thr), 4), "entropy_threshold": round(float(e), 4),
                    "coverage": round(cov, 4), "n_accepted": n, "accuracy": round(acc, 4)}
    return best


def at_fixed_thresholds(conf, entropy, correct, conf_thr, entropy_thr):
    conf, entropy, correct = (np.asarray(a) for a in (conf, entropy, correct))
    m = (conf >= conf_thr) & (entropy <= entropy_thr)
    n = int(m.sum())
    acc = float(correct[m].mean()) if n else None
    return {"confidence_threshold": conf_thr, "entropy_threshold": entropy_thr, "coverage": round(n / len(conf), 4),
            "n_accepted": n, "accuracy": round(acc, 4) if acc is not None else None}


def analyse(rows, targets=TARGETS):
    out = {}
    for mode, pred_col, conf_col, ent_col in (("auto", "pred_auto", "conf_auto", "entropy_auto"),
                                               ("crop_given", "pred_crop_given", "conf_crop_given", "entropy_crop_given")):
        usable = [r for r in rows if r.get(conf_col) and r.get(ent_col) and r.get(pred_col) is not None]
        if not usable:
            continue
        conf = np.array([float(r[conf_col]) for r in usable])
        entropy = np.array([float(r[ent_col]) for r in usable])
        correct = np.array([r[pred_col] == r["label"] for r in usable])
        current = at_fixed_thresholds(conf, entropy, correct, CURRENT_CONF, CURRENT_ENTROPY)
        recs = {}
        for t in targets:
            r = joint_search(conf, entropy, correct, t)
            if r is not None:
                ci = _wilson(int(round(r["accuracy"] * r["n_accepted"])), r["n_accepted"])
                r["accuracy_ci95"] = [round(ci[1], 4), round(ci[2], 4)] if ci else None
            recs[f"{int(t * 100)}%"] = r
        out[mode] = {"n_photos": len(usable), "current_fixed_thresholds": current, "recommendations": recs}
    return out


def to_markdown(res, source):
    pct = lambda x: "n/a" if x is None else f"{100 * x:.1f}%"
    lines = ["# Threshold calibration (fit on the validation split only)", "", f"Source: `{source}`", ""]
    for mode, d in res.items():
        lines += [f"## {mode}  ({d['n_photos']} photos)", "",
                  f"Current fixed thresholds (confidence >= {CURRENT_CONF}, entropy <= {CURRENT_ENTROPY}): "
                  f"coverage {pct(d['current_fixed_thresholds']['coverage'])}, "
                  f"accuracy on accepted {pct(d['current_fixed_thresholds']['accuracy'])} "
                  f"({d['current_fixed_thresholds']['n_accepted']} photos)", "",
                  "| Target accuracy | Confidence >= | Entropy <= | Coverage | Actual accuracy (95% CI) | Photos accepted |",
                  "|---|---|---|---|---|---|"]
        for t, r in d["recommendations"].items():
            if r is None:
                lines.append(f"| {t} | - | - | - | not reachable on this split | - |")
                continue
            ci = r.get("accuracy_ci95")
            ci_s = f"{pct(ci[0])}-{pct(ci[1])}" if ci else "n/a"
            lines.append(f"| {t} | {r['confidence_threshold']} | {r['entropy_threshold']} | {pct(r['coverage'])} | "
                         f"{pct(r['accuracy'])} ({ci_s}) | {r['n_accepted']} |")
        lines.append("")
    lines += ["Fit on the VALIDATION split only -- never choose a threshold by looking at the frozen benchmark. "
              "Confirm the chosen pair on the benchmark exactly once, by re-running `feature1_eval.evaluate --split test "
              "--final` with that pair as the production thresholds and reading its accepted_share / accepted_accuracy; "
              "if confirmed accuracy is notably below the validation figure, the split was overfit to and a more "
              "conservative (higher-coverage-cost) pair should be chosen instead.",
              "", "A row with very few accepted photos has a wide confidence interval even if the point estimate looks good "
              "-- prefer a target whose accepted count is at least a few dozen."]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--predictions", required=True, help="predictions.csv from `evaluate --split val` (never --split test)")
    ap.add_argument("--targets", type=float, nargs="+", default=list(TARGETS))
    a = ap.parse_args(argv)
    pred_path = Path(a.predictions)
    report_path = pred_path.parent / "report.json"
    if report_path.exists():
        split = json.loads(report_path.read_text()).get("split")
        if split != "val":
            raise SystemExit(f"{report_path} says split={split!r}, not 'val'. Calibrate on the validation split only; "
                             "the frozen benchmark exists to confirm a choice afterwards, not to make it.")
    with open(pred_path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    res = analyse(rows, a.targets)
    out_dir = pred_path.parent
    (out_dir / "calibration.json").write_text(json.dumps(res, indent=1))
    md = to_markdown(res, a.predictions)
    (out_dir / "calibration.md").write_text(md, encoding="utf-8")
    print(md)
    print(f"-> {out_dir / 'calibration.md'}")


if __name__ == "__main__":
    main()
