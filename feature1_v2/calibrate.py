"""
Calibration and rejection thresholds, fitted on the FIELD VALIDATION split
(plan, Step 3.5). Writes calibration.json next to the checkpoint.

  temperature      T minimising validation NLL (Guo et al. 2017): probabilities
                   softmax(z / T) then mean what they say (checked with ECE)
  threshold_auto   lowest confidence at which accepted validation photos reach
                   the target accuracy, when the model chooses among all classes
  threshold_crop   the same when the user has selected the crop (crop selector)
  energy_threshold energy score (Liu et al. 2020) above which a photo is treated as
                   "not a supported leaf"; set so 95 % of supported validation
                   photos pass. Reported with the share of unsupported photos it rejects.

Usage
  python -m feature1_v2.calibrate --ckpt work/runs/dinov2_s_ft/best.pt --target 0.90
"""

import argparse
import json
from pathlib import Path

import numpy as np
import torch

from feature1_v2 import config, inference, metrics, models, taxonomy
from feature1_v2.data import splits as sp


def fit_temperature(logits, y, max_iter=200):
    z = torch.tensor(np.asarray(logits), dtype=torch.float64)
    t = torch.tensor(np.asarray(y), dtype=torch.long)
    log_t = torch.zeros(1, dtype=torch.float64, requires_grad=True)
    opt = torch.optim.LBFGS([log_t], lr=0.1, max_iter=max_iter)

    def closure():
        opt.zero_grad()
        loss = torch.nn.functional.cross_entropy(z / log_t.exp(), t)
        loss.backward()
        return loss

    opt.step(closure)
    return float(log_t.exp().item())


def fit(logits, y, classes, target=0.90):
    """All numbers needed at inference time, from validation logits and labels."""
    logits, y = np.asarray(logits), np.asarray(y)
    unsup = classes.index(taxonomy.UNSUPPORTED) if taxonomy.UNSUPPORTED in classes else None
    T = fit_temperature(logits, y)
    p_raw, p_cal = inference.softmax(logits), inference.softmax(logits, T)
    pred = p_cal.argmax(1)
    conf = p_cal.max(1)
    correct = pred == y

    supported = np.ones(len(y), bool) if unsup is None else (y != unsup)
    thr_auto, cov_auto, acc_auto = metrics.threshold_for_accuracy(conf[supported], correct[supported], target)

    # crop selector: restrict each supported photo to its true crop's classes
    crop_conf, crop_correct = [], []
    for z, yy in zip(logits[supported], y[supported]):
        crop = taxonomy.crop_of(classes[yy])
        pc = inference.softmax(inference.restrict_to_crop(z, classes, crop), T)
        crop_conf.append(pc.max())
        crop_correct.append(pc.argmax() == yy)
    thr_crop, cov_crop, acc_crop = metrics.threshold_for_accuracy(crop_conf, crop_correct, target)

    e = inference.energy(logits, T)
    e_thr = float(np.percentile(e[supported], 95))
    unsup_reject = float((e[~supported] > e_thr).mean()) if (~supported).any() else None
    return {
        "temperature": T, "target_accuracy": target,
        "threshold_auto": thr_auto, "val_coverage_auto": cov_auto, "val_accuracy_accepted_auto": acc_auto,
        "threshold_crop": thr_crop, "val_coverage_crop": cov_crop, "val_accuracy_accepted_crop": acc_crop,
        "energy_threshold": e_thr, "val_unsupported_rejected_by_energy": unsup_reject,
        "ece_before": metrics.ece(p_raw.max(1), p_raw.argmax(1) == y),
        "ece_after": metrics.ece(conf, correct),
        "n_val": int(len(y)),
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--target", type=float, default=0.90)
    ap.add_argument("--splits", default=str(config.WORK_DIR / "splits.csv"))
    ap.add_argument("--data-root", default=str(config.DATA_ROOT))
    ap.add_argument("--tta", action="store_true")
    a = ap.parse_args(argv)
    model, ck = models.load_checkpoint(a.ckpt)
    model.to(inference.device())
    classes = ck["classes"]
    rows = [r for r in sp.load_split("val", a.splits) if r["label"] in classes]
    logits = inference.logits_for_paths(model, [str(Path(a.data_root) / r["path"]) for r in rows], ck["meta"], a.tta)
    y = np.array([classes.index(r["label"]) for r in rows])
    cal = fit(logits, y, classes, a.target)
    cal["tta"] = a.tta
    out = Path(a.ckpt).with_name("calibration.json")
    out.write_text(json.dumps(cal, indent=1))
    print(json.dumps(cal, indent=1))


if __name__ == "__main__":
    main()
