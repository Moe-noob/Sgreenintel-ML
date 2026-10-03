"""
Tests for taxonomy, manifest, de-duplication, splitting/freezing and metrics,
on small synthetic datasets written to a temp folder in the real layouts.

Run:  python -m unittest discover -s feature1_eval/tests -t . -v
"""

import json
import shutil
import tempfile
import importlib.util
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from feature1_eval import config, metrics, taxonomy
from feature1_eval.data import dedupe, manifest, splits

RNG = np.random.default_rng(0)


def _img(seed, size=96):
    r = np.random.default_rng(seed)
    base = (r.random((12, 12, 3)) * 255).astype("uint8")
    return Image.fromarray(base).resize((size, size), Image.BILINEAR)


class FakeData:
    """PlantWild-style, PlantDoc-style and processed_v2-style folders with planted duplicates."""

    def __init__(self, root):
        self.root = Path(root)
        seed = 1000
        # PlantWild: images/<class>/, trainval.txt "<path>=<idx>=<domain>" (0 test, 1 train, 2 val)
        pw = self.root / "plantwild" / "plantwild"
        classes = ["cucumber leaf", "cucumber powdery mildew", "rice leaf"]
        lines = []
        for ci, c in enumerate(classes):
            (pw / "images" / c).mkdir(parents=True)
            for k in range(30):
                seed += 1
                p = pw / "images" / c / f"{k}.jpg"
                _img(seed).save(p)
                dom = 0 if k < 6 else 2 if k < 9 else 1
                lines.append(f"{p}={ci}={dom}")
        (pw / "trainval.txt").write_text("\n".join(lines))
        self.pw = pw
        # PlantDoc: train/ and test/ class folders
        pd = self.root / "PlantDoc-Dataset"
        for split, n in (("train", 20), ("test", 6)):
            for c in ("Tomato leaf", "Tomato leaf late blight"):
                (pd / split / c).mkdir(parents=True)
                for k in range(n):
                    seed += 1
                    _img(seed).save(pd / split / c / f"{k}.jpg")
        # planted LEAK: a PlantDoc test image re-used (blurred, same label) in PlantDoc training
        leak_src = pd / "test" / "Tomato leaf" / "0.jpg"
        Image.open(leak_src).filter(ImageFilter.GaussianBlur(0.8)).save(pd / "train" / "Tomato leaf" / "leak.jpg")
        # planted LABEL CONFLICT: same photo labelled late blight in PlantDoc train and healthy cucumber in PlantWild train
        conf_src = pd / "train" / "Tomato leaf late blight" / "0.jpg"
        Image.open(conf_src).resize((80, 80)).save(pw / "images" / "cucumber leaf" / "28.jpg")
        # processed_v2: lab (PlantVillage '___' names) and field (fgvc8-style) files
        pv = self.root / "processed_v2"
        for split in ("train", "test"):
            (pv / split / "Tomato___healthy").mkdir(parents=True)
            for k in range(5):
                seed += 1
                _img(seed).save(pv / split / "Tomato___healthy" / f"uuid{k}___RS_HL {k}.JPG")
            seed += 1
            _img(seed).save(pv / split / "Tomato___healthy" / f"abc{split}.jpg")
        self.sources = [
            {"name": "plantwild_v1", "enabled": True, "layout": "plantwild_trainval",
             "path": "plantwild/plantwild", "domain": "field", "map": "plantwild"},
            {"name": "plantdoc", "enabled": True, "layout": "split_folders",
             "path": "PlantDoc-Dataset", "domain": "field", "map": "plantdoc"},
            {"name": "legacy", "enabled": True, "layout": "split_folders", "path": "processed_v2",
             "domain": "auto_plantvillage_filename", "map": "legacy35", "split_policy": "train_only"},
        ]


class TestTaxonomy(unittest.TestCase):
    def test_maps_are_consistent(self):
        for name, table in taxonomy.SOURCE_MAPS.items():
            for raw, lab in table.items():
                if lab in (None, taxonomy.UNSUPPORTED):
                    continue
                c, d = lab.split("__")
                self.assertIn(c, taxonomy.CROPS, f"{name}: {raw}")
                self.assertIn(d, taxonomy.CONDITIONS, f"{name}: {raw}")

    def test_all_legacy_classes_and_plantwild_89_mapped(self):
        self.assertEqual(len(taxonomy.LEGACY_35), 35)
        self.assertGreaterEqual(len(taxonomy.PLANTWILD), 89)

    def test_unify_tolerant_and_strict(self):
        self.assertEqual(taxonomy.unify("plantwild", "Tomato_Late_Blight"), ("tomato__late_blight", True))
        self.assertEqual(taxonomy.unify("plantwild", "mystery leaf"), (None, False))

    def test_feature2_link_and_arabic(self):
        self.assertEqual(taxonomy.crop_from_feature2("Cucumber {Fresh Market}"), "cucumber")
        self.assertIn("خيار", taxonomy.display("cucumber__powdery_mildew", "ar"))


class TestPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.fake = FakeData(cls.tmp)
        cls.rows, cls.unknown, cls.missing = manifest.build(cls.tmp, cls.fake.sources)
        paths = [str(Path(cls.tmp) / r["path"]) for r in cls.rows]
        cls.hashes = [dedupe._hash_file(p) for p in paths]
        cls.groups = dedupe.group_duplicates(cls.hashes)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_manifest(self):
        self.assertFalse(self.missing)
        self.assertFalse(self.unknown)
        by = {(r["source"], r["raw_label"]) for r in self.rows}
        self.assertIn(("plantwild_v1", "rice leaf"), by)
        rice = [r for r in self.rows if r["raw_label"] == "rice leaf"]
        self.assertTrue(all(r["label"] == taxonomy.UNSUPPORTED for r in rice))
        legacy = [r for r in self.rows if r["source"] == "legacy"]
        self.assertEqual({r["domain"] for r in legacy if "___" in Path(r["path"]).name}, {"lab"})
        self.assertEqual({r["domain"] for r in legacy if "abc" in Path(r["path"]).name}, {"field"})
        self.assertEqual({r["official_split"] for r in legacy}, {"train"})       # train_only policy
        pw = [r for r in self.rows if r["source"] == "plantwild_v1"]
        self.assertEqual({r["official_split"] for r in pw}, {"train", "val", "test"})

    def test_duplicates_found(self):
        idx = {r["path"]: i for i, r in enumerate(self.rows)}
        leak = [p for p in idx if p.endswith("train/Tomato leaf/leak.jpg")][0]
        src = [p for p in idx if p.endswith("test/Tomato leaf/0.jpg")][0]
        self.assertEqual(self.groups[idx[leak]], self.groups[idx[src]])

    def test_splits_leakage_conflicts_inclusion_freeze(self):
        rows, report, included = splits.assign(self.rows, self.groups, min_train=5, min_test=3)
        by_path = {r["path"]: r for r in rows}
        leak = next(p for p in by_path if p.endswith("train/Tomato leaf/leak.jpg"))
        self.assertEqual(by_path[leak]["split"], "drop")                         # train copy of a test image removed
        src = next(p for p in by_path if p.endswith("test/Tomato leaf/0.jpg"))
        self.assertEqual(by_path[src]["split"], "test")                          # test copy kept
        self.assertEqual(report["label_conflict_groups"], 1)
        for r in rows:
            if r["domain"] == "lab":
                self.assertNotEqual(r["split"], "test")                          # lab never in the benchmark
            if r["source"] == "legacy":
                self.assertNotEqual(r["split"], "test")
        self.assertIn(taxonomy.UNSUPPORTED, included)
        # a class with too few real photos is excluded and reported
        rows2, report2, inc2 = splits.assign(self.rows, self.groups, min_train=1000, min_test=3)
        self.assertEqual(inc2, [taxonomy.UNSUPPORTED])
        self.assertIn("tomato__late_blight", report2["excluded_classes"])

        out = Path(self.tmp) / "bench"
        h1 = splits.freeze(rows, included, out_dir=out)
        self.assertEqual(h1, splits.freeze(rows, included, out_dir=out))           # idempotent
        rows_changed = [dict(r) for r in rows]
        next(r for r in rows_changed if r["split"] == "test")["split"] = "train"
        with self.assertRaises(SystemExit):
            splits.freeze(rows_changed, included, out_dir=out)                    # silent re-freeze refused
        self.assertEqual(json.loads((out / "FROZEN.json").read_text())["sha256"], h1)

    def test_benchmark_guard(self):
        with self.assertRaises(PermissionError):
            splits.load_split("test")

    def test_stable_split_is_deterministic(self):
        self.assertEqual(splits._stable_fraction("x"), splits._stable_fraction("x"))
        f = [splits._stable_fraction(str(i)) for i in range(5000)]
        self.assertAlmostEqual(float(np.mean(np.array(f) < 0.2)), 0.2, delta=0.02)


class TestRegressions(unittest.TestCase):
    """Failures met on the real data (Windows, partly extracted PlantWild); each one failed before the fix."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_plantwild_class_comes_from_the_path_not_the_label_index(self):
        # only 2 of PlantWild's 89 class folders are on disk, but the label indices come from the full 89-class list
        root = self.tmp / "pw"
        for cls, name in (("tomato late blight", "a.jpg"), ("potato leaf", "b.jpg"), ("potato leaf", "c.jpg")):
            (root / "images" / cls).mkdir(parents=True, exist_ok=True)
            _img(7).save(root / "images" / cls / name)
        (root / "trainval.txt").write_text(
            "tomato late blight/a.jpg=70=0\n"
            "potato leaf/b.jpg=3=1\n"                      # index 3 would be a different class under the old index-based lookup
            "potato leaf\\c.jpg=3=2\n"                     # a Windows-style separator inside the file
            "tomato late blight/not_on_disk.jpg=70=1\n"    # image not extracted: skipped, not an error
            "\n", encoding="utf-8")
        got = [(p.name, cls, split) for p, cls, split in manifest.scan_plantwild_trainval(root, {})]
        self.assertEqual(got, [("a.jpg", "tomato late blight", "test"), ("b.jpg", "potato leaf", "train"),
                               ("c.jpg", "potato leaf", "val")])

    def test_manifest_paths_use_forward_slashes_even_if_relpath_returns_backslashes(self):
        import os
        from unittest import mock
        (self.tmp / "tiny" / "train" / "Tomato leaf").mkdir(parents=True)
        _img(3).save(self.tmp / "tiny" / "train" / "Tomato leaf" / "0.jpg")
        src = [{"name": "t", "enabled": True, "layout": "split_folders", "path": "tiny", "domain": "field", "map": "plantdoc"}]
        real = os.path.relpath
        with mock.patch("os.path.relpath", side_effect=lambda p, s=None: real(p, s).replace("/", "\\")):   # what Windows returns
            rows, _, _ = manifest.build(self.tmp, src)
        self.assertEqual([r["path"] for r in rows], ["tiny/train/Tomato leaf/0.jpg"])

    def test_benchmark_use_is_logged_only_after_a_successful_read(self):
        from unittest import mock
        bench = self.tmp / "bench"
        with mock.patch.object(config, "BENCHMARK_DIR", bench):
            with self.assertRaises(FileNotFoundError):          # the splits file does not exist yet
                splits.load_split("test", str(self.tmp / "missing.csv"), final=True, purpose="should not be logged")
            self.assertFalse((bench / "usage_log.txt").exists())
            row = {"path": "a.jpg", "source": "s", "domain": "field", "raw_label": "x", "label": "tomato__healthy",
                   "official_split": "test", "group": "1", "split": "test"}
            csv_path = self.tmp / "splits.csv"
            splits.write_splits([row], csv_path)
            self.assertEqual(len(splits.load_split("test", str(csv_path), final=True, purpose="unit test")), 1)
            lines = (bench / "usage_log.txt").read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 1)
            self.assertIn("unit test", lines[0])



@unittest.skipUnless(importlib.util.find_spec("torch") is not None, "needs torch")
class TestEvaluateAcceptanceRules(unittest.TestCase):
    """evaluate.score()'s accepted_share/accepted_accuracy must apply BOTH confidence and entropy, for BOTH modes
    (a past bug applied entropy to auto mode only and silently skipped it for crop_given)."""

    def test_both_modes_apply_both_thresholds(self):
        from feature1_eval import evaluate
        classes = ["a__x", "a__y", "b__x", "b__y"]
        # 4 photos, logits chosen so confidence alone would accept all 4 in both modes, but entropy correctly
        # rejects photo 1 (spread out) and photo 3 (spread within its own crop once masked)
        logits = np.array([
            [5.0, 0.0, -5.0, -5.0],    # confident, low entropy -> accepted
            [5.0, 4.9, -5.0, -5.0],    # confident (same top logit) but high entropy -> must be rejected
            [-5.0, -5.0, 5.0, 0.0],    # confident, low entropy -> accepted
            [-5.0, -5.0, 5.0, 4.9],    # confident but high entropy, within its own crop -> must be rejected
        ])
        y_true = ["a__x", "a__x", "b__x", "b__x"]
        cal = evaluate.RULESETS["current"]            # confidence >= 0.70, entropy <= 0.40, both modes
        res, pred, conf, pc_pred, H_auto, pc_conf, pc_entropy, supported = evaluate.score(y_true, logits, classes, cal)
        self.assertAlmostEqual(res["auto"]["accepted_share"], 0.5)          # photos 0, 2 only
        self.assertAlmostEqual(res["auto"]["accepted_accuracy"], 1.0)
        self.assertAlmostEqual(res["crop_given"]["accepted_share"], 0.5)    # same pattern once masked to each photo's own crop
        self.assertAlmostEqual(res["crop_given"]["accepted_accuracy"], 1.0)

    def test_calibrated_ruleset_uses_different_thresholds_per_mode(self):
        from feature1_eval import evaluate
        self.assertNotEqual(evaluate.RULESETS["calibrated"]["confidence_auto"], evaluate.RULESETS["calibrated"]["confidence_crop"])
        self.assertEqual(evaluate.RULESETS["current"]["confidence_auto"], evaluate.RULESETS["current"]["confidence_crop"])

class TestMetrics(unittest.TestCase):
    def test_against_sklearn(self):
        from sklearn.metrics import accuracy_score, f1_score
        y = RNG.integers(0, 5, 500)
        p = np.where(RNG.random(500) < 0.7, y, RNG.integers(0, 5, 500))
        self.assertAlmostEqual(metrics.accuracy(y, p), accuracy_score(y, p))
        self.assertAlmostEqual(metrics.macro_f1(y, p), f1_score(y, p, average="macro"))
        pt, lo, hi = metrics.bootstrap_ci(metrics.accuracy, y, p, n=300)
        self.assertTrue(lo < pt < hi)

    def test_ece_and_threshold(self):
        conf = RNG.random(5000)
        correct = RNG.random(5000) < conf                    # perfectly calibrated
        self.assertLess(metrics.ece(conf, correct), 0.03)
        self.assertGreater(metrics.ece(np.clip(conf + 0.3, 0, 1), correct), 0.15)
        t, cov, acc = metrics.threshold_for_accuracy(conf, correct, 0.9)
        self.assertGreaterEqual(acc, 0.9)
        self.assertTrue(0 < cov < 1 and 0.7 < t < 0.95)


if __name__ == "__main__":
    unittest.main()
