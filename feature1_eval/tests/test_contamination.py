import csv
import tempfile
import unittest
from pathlib import Path

from feature1_eval import contamination as ct
from feature1_eval.data import manifest as mf


def _write(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


class TestWilson(unittest.TestCase):
    def test_bounds_and_edge_cases(self):
        self.assertIsNone(ct.wilson(0, 0))
        p, lo, hi = ct.wilson(70, 100)
        self.assertAlmostEqual(p, 0.7)
        self.assertTrue(0 <= lo < p < hi <= 1)
        self.assertAlmostEqual(lo, 0.6041, places=3)      # worked out by hand: centre 0.6926, half-width 0.0885
        self.assertAlmostEqual(hi, 0.7811, places=3)
        p0, lo0, hi0 = ct.wilson(0, 20)
        self.assertEqual((p0, lo0), (0.0, 0.0))
        self.assertGreater(hi0, 0)
        p1, lo1, hi1 = ct.wilson(20, 20)
        self.assertEqual((p1, hi1), (1.0, 1.0))
        self.assertLess(lo1, 1.0)


class TestContamination(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        man = [  # path, source, domain, raw_label, label, official_split
            ("v1/a.jpg", "legacy_processed_v2", "lab", "x", "tomato__late_blight", "train"),
            ("v1/val.jpg", "legacy_processed_v2", "lab", "x", "tomato__late_blight", "val"),       # not trained on
            ("pd/train1.jpg", "plantdoc", "field", "x", "tomato__late_blight", "train"),
            ("pw/train1.jpg", "plantwild_v1", "field", "x", "potato__late_blight", "train"),
            ("pd/t_dirty.jpg", "plantdoc", "field", "x", "tomato__late_blight", "test"),            # twin in plantdoc train
            ("pw/t_dirty2.jpg", "plantwild_v1", "field", "x", "potato__late_blight", "test"),       # twin in v1 base set
            ("pw/t_twin_a.jpg", "plantwild_v1", "field", "x", "potato__late_blight", "test"),       # twin only of another TEST photo
            ("pd/t_twin_b.jpg", "plantdoc", "field", "x", "potato__late_blight", "test"),
            ("pd/t_val_twin.jpg", "plantdoc", "field", "x", "tomato__late_blight", "test"),         # twin only of a v1 VAL photo
            ("pw/t_clean1.jpg", "plantwild_v1", "field", "x", "potato__late_blight", "test"),
            ("pw/t_clean2.jpg", "plantwild_v1", "field", "x", "tomato__late_blight", "test"),
            ("pw/t_unknown.jpg", "plantwild_v1", "field", "x", "apple__scab", "test"),              # class unknown to the model
        ]
        groups = {"v1/a.jpg": 1, "v1/val.jpg": 2, "pd/train1.jpg": 3, "pw/train1.jpg": 4, "pd/t_dirty.jpg": 3, "pw/t_dirty2.jpg": 1,
                  "pw/t_twin_a.jpg": 5, "pd/t_twin_b.jpg": 5, "pd/t_val_twin.jpg": 2, "pw/t_clean1.jpg": 6, "pw/t_clean2.jpg": 7,
                  "pw/t_unknown.jpg": 8}
        _write(self.tmp / "manifest.csv", mf.FIELDS, man)
        _write(self.tmp / "hashes.csv", ["path", "phash", "group"], [(p, "", g) for p, g in groups.items()])
        # predictions: contaminated photos always right, clean photos right half the time
        pred = [  # path, label, known, pred_auto, conf, pred_crop_given
            ("pd/t_dirty.jpg", "tomato__late_blight", 1, "tomato__late_blight", 0.9, "tomato__late_blight"),
            ("pw/t_dirty2.jpg", "potato__late_blight", 1, "potato__late_blight", 0.9, "potato__late_blight"),
            ("pw/t_twin_a.jpg", "potato__late_blight", 1, "potato__late_blight", 0.9, "potato__late_blight"),
            ("pd/t_twin_b.jpg", "potato__late_blight", 1, "tomato__late_blight", 0.6, "potato__late_blight"),
            ("pd/t_val_twin.jpg", "tomato__late_blight", 1, "potato__late_blight", 0.6, "tomato__late_blight"),
            ("pw/t_clean1.jpg", "potato__late_blight", 1, "tomato__late_blight", 0.5, "potato__late_blight"),
            ("pw/t_clean2.jpg", "tomato__late_blight", 1, "tomato__late_blight", 0.8, "tomato__late_blight"),
            ("pw/t_unknown.jpg", "apple__scab", 0, "tomato__late_blight", 0.5, ""),
        ]
        _write(self.tmp / "predictions.csv", ["path", "label", "label_known_to_model", "pred_auto", "conf_auto", "pred_crop_given"], pred)

    def run_analysis(self):
        rows = mf.read(str(self.tmp / "manifest.csv"))
        pg = {r["path"]: r["group"] for r in mf.read(str(self.tmp / "hashes.csv"))}
        ps = {r["path"]: r["source"] for r in rows}
        with open(self.tmp / "predictions.csv", newline="") as fh:
            preds = list(csv.DictReader(fh))
        return ct.analyse(preds, pg, ps, ct.v1_training_groups(rows, pg))

    def test_groups_that_v1_trained_on(self):
        rows = mf.read(str(self.tmp / "manifest.csv"))
        pg = {r["path"]: r["group"] for r in mf.read(str(self.tmp / "hashes.csv"))}
        self.assertEqual(ct.v1_training_groups(rows, pg), {"1", "3", "4"})      # v1 validation group (2) is NOT counted

    def test_counts_and_accuracy_partition(self):
        res = self.run_analysis()
        self.assertEqual(res["n_benchmark_photos"], 8)
        self.assertEqual(res["n_contaminated"], 2)                              # only the two photos with a twin v1 trained on
        self.assertEqual(res["by_source"]["plantdoc"], {"n": 3, "contaminated": 1})
        self.assertEqual(res["by_source"]["plantwild_v1"], {"n": 5, "contaminated": 1})
        auto = res["accuracy"]["auto"]
        self.assertEqual((auto["all"]["n"], auto["clean"]["n"], auto["contaminated"]["n"]), (7, 5, 2))   # unknown-class photo excluded
        self.assertAlmostEqual(auto["contaminated"]["accuracy"], 1.0)
        self.assertAlmostEqual(auto["clean"]["accuracy"], 2 / 5)               # twin_a and clean2 right; twin_b, val_twin, clean1 wrong
        self.assertAlmostEqual(auto["all"]["accuracy"], 4 / 7)
        crop = res["accuracy"]["crop_given"]
        self.assertAlmostEqual(crop["clean"]["accuracy"], 1.0)                 # the crop selector fixes every clean error here
        for block in list(auto.values()) + list(crop.values()):
            lo, hi = block["ci95"]
            self.assertTrue(0 <= lo <= block["accuracy"] <= hi <= 1)

    def test_markdown_and_main(self):
        out = ct.to_markdown(self.run_analysis(), "x/predictions.csv")
        self.assertIn("Benchmark photos: **8**", out)
        self.assertIn("| auto | clean | 5 |", out)
        ct.main(["--predictions", str(self.tmp / "predictions.csv"), "--manifest", str(self.tmp / "manifest.csv"),
                 "--hashes", str(self.tmp / "hashes.csv")])
        self.assertTrue((self.tmp / "contamination.json").exists() and (self.tmp / "contamination.md").exists())


if __name__ == "__main__":
    unittest.main()
