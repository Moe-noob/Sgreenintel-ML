"""
End-to-end smoke test on CPU: synthetic dataset -> manifest -> dedupe ->
splits/freeze -> train (tiny timm model, no pretrained weights) -> calibrate
-> evaluate (val and guarded test) -> v1 legacy adapter -> paired compare.

It checks the pipeline runs and learns an easy synthetic task; it says
nothing about real accuracy (that needs the real data, see RUNBOOK.md).
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
from torchvision import models as tvm

from feature1_v2 import calibrate, compare, config, distill, evaluate, models, taxonomy, train
from feature1_v2.data import dedupe, manifest, splits

CLASSES = {  # PlantWild raw name -> colour that makes the class learnable
    "cucumber leaf": (40, 160, 40), "cucumber powdery mildew": (200, 200, 200),
    "tomato leaf": (20, 120, 20), "tomato late blight": (90, 60, 20), "rice leaf": (180, 180, 40),
}


def make_data(root, n=40):
    pw = Path(root) / "plantwild" / "plantwild"
    names = sorted(CLASSES)
    lines, rng = [], np.random.default_rng(0)
    for ci, c in enumerate(names):
        d = pw / "images" / c
        d.mkdir(parents=True)
        for k in range(n):
            base = np.array(CLASSES[c], float)
            img = np.clip(base + rng.normal(0, 25, (64, 64, 3)), 0, 255).astype("uint8")
            p = d / f"{k}.jpg"
            Image.fromarray(img).save(p)
            dom = 0 if k < 10 else 2 if k < 16 else 1
            lines.append(f"{p}={ci}={dom}")
    (pw / "trainval.txt").write_text("\n".join(lines))
    return [{"name": "plantwild_v1", "enabled": True, "layout": "plantwild_trainval",
             "path": "plantwild/plantwild", "domain": "field", "map": "plantwild"}]


class TestEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.old_bench = config.BENCHMARK_DIR
        config.BENCHMARK_DIR = cls.tmp / "bench"
        torch.manual_seed(0)
        srcs = make_data(cls.tmp / "data")
        rows, unknown, _ = manifest.build(cls.tmp / "data", srcs)
        assert not unknown
        hashes = [dedupe._hash_file(str(cls.tmp / "data" / r["path"])) for r in rows]
        rows, report, included = splits.assign(rows, dedupe.group_duplicates(hashes), min_train=10, min_test=5)
        cls.work = cls.tmp / "work"
        cls.work.mkdir()
        splits.write_splits(rows, cls.work / "splits.csv")
        (cls.work / "classes.json").write_text(json.dumps(included))
        splits.freeze(rows, included)
        cls.included = included
        cls.run_dir = cls.tmp / "run"
        cls.ckpt = train.main(["--backbone", "test", "--mode", "finetune", "--epochs", "6", "--batch", "16",
                               "--lr", "3e-3", "--img-size", "64", "--no-pretrained", "--workers", "0",
                               "--ema", "0", "--cutmix", "0.3", "--splits", str(cls.work / "splits.csv"),
                               "--data-root", str(cls.tmp / "data"), "--out", str(cls.run_dir)])

    @classmethod
    def tearDownClass(cls):
        config.BENCHMARK_DIR = cls.old_bench
        shutil.rmtree(cls.tmp)

    def test_1_classes_and_training_learned(self):
        self.assertIn(taxonomy.UNSUPPORTED, self.included)
        self.assertEqual(len(self.included), 5)
        hist = json.loads((self.run_dir / "history.json").read_text())
        self.assertGreater(max(h["val_accuracy"] for h in hist), 0.6)
        _, ck = models.load_checkpoint(self.ckpt)
        self.assertEqual(ck["classes"], self.included)

    def test_2_calibrate_and_evaluate(self):
        calibrate.main(["--ckpt", str(self.ckpt), "--target", "0.8", "--splits", str(self.work / "splits.csv"),
                        "--data-root", str(self.tmp / "data")])
        cal = json.loads((self.run_dir / "calibration.json").read_text())
        self.assertGreater(cal["temperature"], 0)
        for k in ("threshold_auto", "threshold_crop", "energy_threshold"):
            self.assertIn(k, cal)
        evaluate.main(["--ckpt", str(self.ckpt), "--split", "val", "--splits", str(self.work / "splits.csv"),
                       "--data-root", str(self.tmp / "data"), "--out", str(self.run_dir / "ev_val")])
        rep = json.loads((self.run_dir / "ev_val" / "report.json").read_text())
        self.assertIn("crop_given", rep)
        self.assertGreaterEqual(rep["crop_given"]["accuracy"], rep["auto"]["accuracy"] - 1e-9)
        # the frozen benchmark is refused without --final ...
        with self.assertRaises(PermissionError):
            evaluate.main(["--ckpt", str(self.ckpt), "--split", "test", "--splits", str(self.work / "splits.csv"),
                           "--data-root", str(self.tmp / "data"), "--out", str(self.run_dir / "ev_test")])
        # ... and logged when used
        evaluate.main(["--ckpt", str(self.ckpt), "--split", "test", "--final", "--purpose", "unit test",
                       "--splits", str(self.work / "splits.csv"), "--data-root", str(self.tmp / "data"),
                       "--out", str(self.run_dir / "ev_test")])
        self.assertIn("unit test", (config.BENCHMARK_DIR / "usage_log.txt").read_text())

    def test_3_legacy_adapter_and_compare(self):
        # a fake v1 checkpoint in v1's format (random weights, 35 legacy class names)
        m = tvm.mobilenet_v2(weights=None)
        m.classifier[1] = nn.Linear(m.classifier[1].in_features, 35)
        path = self.tmp / "fake_v6p2.pth"
        torch.save({"model_state_dict": m.state_dict(), "class_names": list(taxonomy.LEGACY_35)}, path)
        evaluate.main(["--legacy", str(path), "--split", "val", "--splits", str(self.work / "splits.csv"),
                       "--data-root", str(self.tmp / "data"), "--out", str(self.tmp / "v1_val")])
        rep = json.loads((self.tmp / "v1_val" / "report.json").read_text())
        self.assertGreater(rep["share_unknown_to_model"], 0)          # cucumber is unknown to v1
        if not (self.run_dir / "ev_val" / "predictions.csv").exists():
            evaluate.main(["--ckpt", str(self.ckpt), "--split", "val", "--splits", str(self.work / "splits.csv"),
                           "--data-root", str(self.tmp / "data"), "--out", str(self.run_dir / "ev_val")])
        r = compare.compare(compare.read(self.tmp / "v1_val" / "predictions.csv"),
                            compare.read(self.run_dir / "ev_val" / "predictions.csv"))
        self.assertGreater(r["n"], 0)

    def test_4_distillation(self):
        student = distill.main(["--teacher", str(self.ckpt), "--student", "test", "--epochs", "3", "--batch", "16",
                                "--img-size", "48", "--no-pretrained", "--workers", "0", "--lr", "3e-3",
                                "--splits", str(self.work / "splits.csv"), "--data-root", str(self.tmp / "data"),
                                "--out", str(self.tmp / "student")])
        _, ck = models.load_checkpoint(student)
        self.assertEqual(ck["classes"], self.included)
        self.assertEqual(ck["meta"]["img_size"], 48)
        hist = json.loads((self.tmp / "student" / "history.json").read_text())
        self.assertGreater(max(h["val_accuracy"] for h in hist), 0.4)


if __name__ == "__main__":
    unittest.main()
