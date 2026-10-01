"""
Predictor logic with a stub model whose logits are fixed per photo colour,
so each rule (unsupported / OOD rejection, crop selector, multi-photo and
per-leaf aggregation, low-confidence rejection, look-alikes) is checked
exactly. Also the leaf-detector box helpers and PlantDoc -> YOLO conversion.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from PIL import Image

from feature1_v2 import models
from feature1_v2.detector import prepare_plantdoc
from feature1_v2.detector.leaf_detector import select_boxes
from feature1_v2.predictor import Predictor

CLASSES = ["_unsupported", "cucumber__healthy", "cucumber__powdery_mildew", "tomato__healthy", "tomato__late_blight"]
# photo colour (red channel value) -> logits
TABLE = {
    0:   [0, 6, 0, 0, 0],      # confident cucumber healthy
    40:  [0, 0, 0, 0, 6],      # confident tomato late blight
    80:  [6, 0, 0, 0, 0],      # unsupported (e.g. a rice leaf or a cat)
    120: [0, 3, 0, 3.2, 0],    # tomato vs cucumber healthy: crop unclear
    160: [0, 0, 0, 1, 0.9],    # tomato healthy vs late blight: close -> look-alike / low confidence
    200: [0, 0, 0, 4, 0],      # tomato healthy, confident
}


class StubModel(nn.Module):
    def __init__(self, mean, std):
        super().__init__()
        self.w = nn.Parameter(torch.zeros(1))          # so .parameters() has a device
        self.mean, self.std = mean[0], std[0]

    def forward(self, x):
        red = (x[:, 0].mean(dim=(1, 2)) * self.std + self.mean) * 255
        keys = np.array(sorted(TABLE))
        rows = [TABLE[int(keys[np.abs(keys - r.item()).argmin()])] for r in red]
        return torch.tensor(rows, dtype=torch.float32)


def photo(red, size=96):
    return Image.new("RGB", (size, size), (red, 120, 60))


class FakeDetector:
    """Returns one 'leaf' box in the right half; the photo's right half has a different colour."""
    def leaves(self, img):
        w, h = img.size
        return [(w // 2, 0, w, h)]


def two_tone(left, right, size=96):
    im = photo(left, size)
    im.paste(photo(right, size).crop((size // 2, 0, size, size)), (size // 2, 0))
    return im


class TestPredictor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        m, meta = models.create("test", len(CLASSES), img_size=64, pretrained=False)
        cls.ckpt = cls.tmp / "best.pt"
        models.save_checkpoint(cls.ckpt, m, meta, CLASSES)
        (cls.tmp / "calibration.json").write_text(json.dumps(
            {"temperature": 1.0, "threshold_auto": 0.6, "threshold_crop": 0.6, "energy_threshold": 1e9}))
        cls.meta = meta

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def make(self, **kw):
        p = Predictor(self.ckpt, tta=False, **kw)
        p.model = StubModel(self.meta["mean"], self.meta["std"])
        return p

    def test_confident_prediction(self):
        r = self.make().predict(photo(40))
        self.assertTrue(r["accepted"])
        self.assertEqual(r["prediction"], "tomato__late_blight")
        self.assertEqual((r["crop"], r["condition"]), ("tomato", "late_blight"))
        self.assertIn("ar", r["display"])
        self.assertGreater(r["confidence"], 0.9)

    def test_unsupported_rejected(self):
        r = self.make().predict(photo(80))
        self.assertFalse(r["accepted"])
        self.assertEqual(r["rejection_code"], "not_supported")

    def test_energy_rejection(self):
        p = self.make()
        p.cal["energy_threshold"] = -100.0              # everything looks out-of-distribution
        self.assertEqual(p.predict(photo(40))["rejection_code"], "not_supported")
        # with the crop given by the user, the OOD gate is skipped
        self.assertTrue(p.predict(photo(40), crop="tomato")["accepted"])

    def test_crop_selector_resolves_cross_crop_confusion(self):
        p = self.make()
        auto = p.predict(photo(120))
        self.assertFalse(auto["accepted"])               # 0.5 / 0.5 between crops -> low confidence
        self.assertEqual(auto["rejection_code"], "low_confidence")
        given = p.predict(photo(120), crop="cucumber")
        self.assertTrue(given["accepted"])
        self.assertEqual(given["prediction"], "cucumber__healthy")
        self.assertTrue(given["crop_given_by_user"])
        with self.assertRaises(ValueError):
            p.predict(photo(120), crop="date_palm")

    def test_lookalike_hint(self):
        p = self.make()
        p.cal["threshold_crop"] = 0.3
        r = p.predict(photo(160), crop="tomato")
        self.assertTrue(r["accepted"])
        self.assertEqual(set(r["lookalike"]), {"tomato__healthy", "tomato__late_blight"})

    def test_multi_photo_mean(self):
        r = self.make().predict([photo(200), photo(160)], crop="tomato")
        self.assertEqual(r["photos"], 2)
        self.assertEqual(r["prediction"], "tomato__healthy")

    def test_worst_case_leaf_wins(self):
        # whole photo looks healthy tomato; the detected leaf shows late blight
        p = self.make(detector=FakeDetector())
        r = p.predict(two_tone(200, 40), crop="tomato")
        self.assertEqual(r["leaves_detected"], 1)
        self.assertEqual(r["prediction"], "tomato__late_blight")
        # explicit mean aggregation does not let one leaf override everything
        self.assertEqual(p.predict(two_tone(200, 40), crop="tomato", aggregate="mean")["photos"], 1)

    def test_default_calibration_when_missing(self):
        d = self.tmp / "nocal"
        d.mkdir(exist_ok=True)
        shutil.copy(self.ckpt, d / "best.pt")
        p = Predictor(d / "best.pt", tta=False)
        self.assertEqual(p.cal["temperature"], 1.0)
        self.assertEqual(p.crops, ["cucumber", "tomato"])


class TestDetectorHelpers(unittest.TestCase):
    def test_select_boxes(self):
        boxes = [(0, 0, 10, 10), (10, 10, 110, 110), (0, 0, 300, 200), (50, 50, 150, 250)]
        out = select_boxes(boxes, (320, 240), max_leaves=2, min_side=48, pad=0.1)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0], (0, 0, 320, 220))          # largest first, padded and clipped
        for x0, y0, x1, y1 in out:
            self.assertTrue(0 <= x0 < x1 <= 320 and 0 <= y0 < y1 <= 240)

    def test_yolo_conversion_and_benchmark_exclusion(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            for split in ("TRAIN", "TEST"):
                (tmp / "src" / split).mkdir(parents=True)
                rows = ["filename,width,height,class,xmin,ymin,xmax,ymax"]
                for n in ("a.jpg", "bench.jpg"):
                    Image.new("RGB", (200, 100)).save(tmp / "src" / split / n)
                    rows.append(f"{n},200,100,Tomato leaf,20,10,120,90")
                rows.append("a.jpg,200,100,Tomato leaf,50,50,40,60")        # invalid box, dropped
                (tmp / "src" / f"{split.lower()}_labels.csv").write_text("\n".join(rows))
            stats = prepare_plantdoc.build(tmp / "src", tmp / "out", exclude_names=["bench.jpg"])
            self.assertEqual(stats["train"], {"images": 1, "skipped": 1})
            self.assertEqual(stats["val"]["images"], 2)               # exclusion only applies to train
            line = (tmp / "out" / "labels" / "train" / "a.txt").read_text().split()
            self.assertEqual(line, ["0", "0.350000", "0.500000", "0.500000", "0.800000"])
            self.assertIn("leaf", (tmp / "out" / "leaf.yaml").read_text())
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
