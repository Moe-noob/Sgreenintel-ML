"""
Decision gate for the leaf detector (plan, Step 3.3): does detect-then-classify
beat whole-photo classification on the FIELD VALIDATION split?

Both runs use the same checkpoint, calibration and TTA, with the crop given
(the app's main mode). Reported: accuracy with and without the detector and
the paired-bootstrap difference. Keep the detector only if the interval is
above zero.

  python -m feature1_v2.detector.evaluate_gain --ckpt work/runs/X/best.pt --detector work/detector/runs/leaf/weights/best.pt
"""

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from feature1_v2 import config, metrics, taxonomy
from feature1_v2.data import splits as sp
from feature1_v2.predictor import Predictor


def run(predictor, rows, data_root):
    pred = []
    for r in rows:
        res = predictor.predict(Image.open(Path(data_root) / r["path"]), crop=taxonomy.crop_of(r["label"]))
        p = res["prediction"] or (res["alternatives"][0]["label"] if res["alternatives"] else "")
        pred.append(p)
    return np.array(pred)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--detector", required=True)
    ap.add_argument("--splits", default=str(config.WORK_DIR / "splits.csv"))
    ap.add_argument("--data-root", default=str(config.DATA_ROOT))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-tta", action="store_true")
    a = ap.parse_args(argv)

    base = Predictor(a.ckpt, tta=not a.no_tta)
    det = Predictor(a.ckpt, detector=a.detector, tta=not a.no_tta)
    rows = [r for r in sp.load_split("val", a.splits) if r["label"] in base.classes and r["label"] != taxonomy.UNSUPPORTED]
    if a.limit:
        rows = rows[:a.limit]
    y = np.array([r["label"] for r in rows])
    pa, pb = run(base, rows, a.data_root), run(det, rows, a.data_root)
    d, lo, hi = metrics.paired_bootstrap_diff(metrics.accuracy, y, pa, pb)
    res = {"n": len(rows), "accuracy_without_detector": metrics.accuracy(y, pa),
           "accuracy_with_detector": metrics.accuracy(y, pb), "difference": d, "ci95": [lo, hi],
           "decision": "keep detector" if lo > 0 else "do not use detector (no clear gain)"}
    out = Path(a.ckpt).parent / "detector_gain.json"
    out.write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
