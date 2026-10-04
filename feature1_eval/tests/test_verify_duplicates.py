import csv
import importlib.util
import random
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from feature1_eval import verify_duplicates as vd

_HAS_CV2 = importlib.util.find_spec("cv2") is not None


def row(path, label, group, split="train", official="train", domain="field", source="plantwild_v1"):
    return {"path": path, "source": source, "domain": domain, "raw_label": "x", "label": label,
            "official_split": official, "group": str(group), "split": split}


class TestAcceptanceRule(unittest.TestCase):
    """Numbers below are the real ones measured on the 24 reviewed pairs (and the synthetic noise level)."""

    def ok(self, inliers, n_kp, dist=6):
        return vd.is_verified({"inliers": inliers, "n_kp": n_kp}, dist)[0]

    def test_real_duplicates_pass(self):
        self.assertTrue(self.ok(1500, 1500))       # identical image
        self.assertTrue(self.ok(81, 1030))         # a zoomed crop of a larger photo: only 8% of the big image's features can match
        self.assertTrue(self.ok(30, 73))           # a tiny thumbnail

    def test_false_matches_fail(self):
        self.assertFalse(self.ok(0, 197))          # strawberry leaf vs plain apple leaf
        self.assertFalse(self.ok(0, 920))
        self.assertFalse(self.ok(10, 1500))        # two unrelated feature-rich images: noise level, below max(15, 2% of 1500 = 30)
        self.assertFalse(self.ok(14, 40))          # just under the absolute floor

    def test_the_fraction_requirement_scales_with_image_richness(self):
        self.assertFalse(self.ok(29, 1500))        # needs 30 here ...
        self.assertTrue(self.ok(30, 1500))
        self.assertTrue(self.ok(15, 100))          # ... but only the floor of 15 on a small image

    def test_identical_hash_on_a_textureless_image_is_accepted_but_labelled_hash_only(self):
        self.assertEqual(vd.is_verified({"inliers": 3, "n_kp": 10}, 0), (True, "hash"))
        self.assertFalse(vd.is_verified({"inliers": 3, "n_kp": 10}, 2)[0])        # not identical -> no
        self.assertFalse(vd.is_verified({"inliers": 2, "n_kp": 500}, 0)[0])       # rich image with no geometric support -> no

    def test_unreadable_images_are_never_verified(self):
        self.assertFalse(vd.is_verified({"inliers": None, "n_kp": 0}, 0)[0])


class TestAnalyse(unittest.TestCase):
    """A scripted comparison function stands in for the images, so every outcome is known in advance."""

    def setUp(self):
        self.rows = [
            # group 1: ONE pHash group chaining a real conflict (P1~P2) with an unrelated image (P3) -- P3 must be rescued
            row("pw/P1.jpg", "tomato__early_blight", 1), row("pw/P2.jpg", "tomato__late_blight", 1),
            row("pv/P3.jpg", "tomato__healthy", 1, source="legacy_processed_v2", domain="lab"),
            # group 2: a frozen-benchmark photo and a training photo that is the same picture, same label -> leakage
            row("pd/T1.jpg", "corn__gray_leaf_spot", 2, split="test", official="test", source="plantdoc"),
            row("pw/W1.jpg", "corn__gray_leaf_spot", 2),
            # group 3: two labels, but nothing verifies -> a false-positive group, nothing excluded
            row("pw/K1.jpg", "potato__healthy", 3), row("pv/K2.jpg", "tomato__healthy", 3, source="legacy_processed_v2", domain="lab"),
            # group 4: a CROSS-CROP conflict, one of them an official-test photo that the split step dropped
            row("pw/C1.jpg", "apple__black_rot", 4, split="drop", official="test"), row("pw/C2.jpg", "grape__black_rot", 4),
            # group 5: a benchmark candidate dropped for a "conflict" that verification dissolves (false positive)
            row("pw/F1.jpg", "strawberry__leaf_scorch", 5, split="drop", official="test"), row("pv/F2.jpg", "apple__healthy", 5, domain="lab"),
            # group 6: single image -> never examined
            row("pw/S1.jpg", "tomato__healthy", 6),
        ]
        self.true_pairs = {frozenset(p) for p in [("pw/P1.jpg", "pw/P2.jpg"), ("pd/T1.jpg", "pw/W1.jpg"), ("pw/C1.jpg", "pw/C2.jpg")]}
        self.calls = []

        def edge(a, b):
            self.calls.append(frozenset((a, b)))
            return {"inliers": 900, "n_kp": 1000} if frozenset((a, b)) in self.true_pairs else {"inliers": 1, "n_kp": 1000}

        self.res = vd.analyse(self.rows, {}, edge)

    def test_singletons_and_unremarkable_groups_are_not_compared(self):
        self.assertNotIn("pw/S1.jpg", {p for c in self.calls for p in c})

    def test_the_chain_is_dissolved_and_the_unrelated_image_is_rescued(self):
        ex = {e["path"] for e in self.res["exclusions"]}
        self.assertIn("pw/P1.jpg", ex)
        self.assertIn("pw/P2.jpg", ex)
        self.assertNotIn("pv/P3.jpg", ex)                           # a different photo, wrongly chained: stays in training

    def test_leakage_excludes_the_training_copy_never_the_benchmark_photo(self):
        by = {e["path"]: e for e in self.res["exclusions"]}
        self.assertEqual(by["pw/W1.jpg"]["reason"], "benchmark_duplicate")
        self.assertNotIn("pd/T1.jpg", by)

    def test_false_positive_groups_exclude_nothing(self):
        ex = {e["path"] for e in self.res["exclusions"]}
        self.assertFalse({"pw/K1.jpg", "pv/K2.jpg", "pw/F1.jpg", "pv/F2.jpg"} & ex)

    def test_conflict_exclusions_are_labelled(self):
        by = {e["path"]: e for e in self.res["exclusions"]}
        self.assertEqual(by["pw/P1.jpg"]["reason"], "conflict")
        self.assertEqual(by["pw/C2.jpg"]["reason"], "conflict")

    def test_statistics_match_the_hand_count(self):
        s = self.res["stats"]
        self.assertEqual(s["phash_conflict_groups"], 4)                 # groups 1, 3, 4, 5 carry more than one label
        self.assertEqual(s["groups_with_a_verified_conflict"], 2)       # groups 1 and 4
        self.assertEqual(s["groups_dissolved_by_verification"], 2)      # groups 3 and 5
        self.assertEqual(s["verified_conflict_components"], 2)
        self.assertEqual(s["cross_crop_conflict_components"], 1)        # apple vs grape
        self.assertEqual(s["benchmark_candidates_dropped_for_conflict"], 2)   # C1 and F1
        self.assertEqual(s["of_which_verified_true_conflict"], 1)       # C1 only
        self.assertEqual(s["of_which_not_verified_false_positive"], 1)  # F1
        self.assertEqual(s["of_which_cross_crop"], 1)
        self.assertEqual(s["exclusions_by_reason"], {"conflict": 3, "benchmark_duplicate": 1})

    def test_large_groups_are_sampled_deterministically(self):
        rows = [row(f"pw/B{i}.jpg", "tomato__early_blight" if i % 2 else "tomato__late_blight", 9) for i in range(40)]   # 780 pairs
        seen1, seen2 = [], []
        vd.analyse(rows, {}, lambda a, b: (seen1.append((a, b)), {"inliers": 0, "n_kp": 100})[1], max_pairs=50)
        vd.analyse(rows, {}, lambda a, b: (seen2.append((a, b)), {"inliers": 0, "n_kp": 100})[1], max_pairs=50)
        self.assertEqual(len(seen1), 50)
        self.assertEqual(seen1, seen2)


def scene(seed, size=(520, 400)):
    rng = random.Random(seed)
    im = Image.new("RGB", size, tuple(rng.randint(40, 200) for _ in range(3)))
    d = ImageDraw.Draw(im)
    for _ in range(90):
        x0, y0 = rng.randint(0, size[0]), rng.randint(0, size[1])
        x1, y1 = x0 + rng.randint(8, 90), y0 + rng.randint(8, 90)
        col = tuple(rng.randint(0, 255) for _ in range(3))
        k = rng.random()
        if k < 0.4:
            d.rectangle([x0, y0, x1, y1], fill=col)
        elif k < 0.8:
            d.ellipse([x0, y0, x1, y1], fill=col, outline=(0, 0, 0))
        else:
            d.line([x0, y0, x1, y1], fill=col, width=rng.randint(1, 5))
    return im.filter(ImageFilter.GaussianBlur(0.6))


@unittest.skipUnless(_HAS_CV2, "needs opencv-python")
class TestRealFeatureMatching(unittest.TestCase):
    def test_copy_rescale_and_crop_verify_but_unrelated_images_do_not(self):
        tmp = Path(tempfile.mkdtemp())
        base = scene(1)
        base.save(tmp / "base.jpg", quality=92)
        base.save(tmp / "copy.jpg", quality=92)
        base.resize((int(base.width * .6), int(base.height * .6)), Image.LANCZOS).save(tmp / "small.jpg", quality=70)
        base.crop((60, 40, 460, 340)).save(tmp / "cropped.jpg", quality=85)
        scene(2).save(tmp / "other.jpg", quality=92)
        scene(3).save(tmp / "other2.jpg", quality=92)
        f = vd.Features(tmp)
        verdict = {n: vd.is_verified(f.compare("base.jpg", f"{n}.jpg"), 6)[0] for n in ("copy", "small", "cropped", "other", "other2")}
        self.assertEqual(verdict, {"copy": True, "small": True, "cropped": True, "other": False, "other2": False})

    def test_an_unreadable_file_is_handled_not_fatal(self):
        tmp = Path(tempfile.mkdtemp())
        scene(1).save(tmp / "a.jpg")
        (tmp / "broken.jpg").write_bytes(b"not an image")
        f = vd.Features(tmp)
        self.assertIsNone(f.compare("a.jpg", "broken.jpg")["inliers"])
        self.assertIsNone(f.compare("a.jpg", "missing.jpg")["inliers"])


@unittest.skipUnless(_HAS_CV2, "needs opencv-python")
class TestEndToEnd(unittest.TestCase):
    def test_main_on_disk_writes_every_output_with_paths_relative_to_the_data_root(self):
        tmp = Path(tempfile.mkdtemp())
        root = tmp / "raw"
        (root / "pw").mkdir(parents=True)
        (tmp / "processed_v2" / "train").mkdir(parents=True)             # legacy rows live OUTSIDE the data root: "../processed_v2/..."
        s1, s2 = scene(1), scene(2)
        s1.save(root / "pw" / "a.jpg")
        s1.resize((300, 230), Image.LANCZOS).save(root / "pw" / "b.jpg")                       # same photo, other label
        s2.save(tmp / "processed_v2" / "train" / "c.jpg")                                       # a different photo chained in by pHash
        rows = [row("pw/a.jpg", "tomato__early_blight", 1), row("pw/b.jpg", "tomato__late_blight", 1),
                row("../processed_v2/train/c.jpg", "tomato__healthy", 1, source="legacy_processed_v2", domain="lab")]
        fields = ["path", "source", "domain", "raw_label", "label", "official_split", "group", "split"]
        with open(tmp / "splits.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        with open(tmp / "hashes.csv", "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["path", "phash", "group"])
            for r in rows:
                w.writerow([r["path"], "", 1])
        vd.main(["--splits", str(tmp / "splits.csv"), "--hashes", str(tmp / "hashes.csv"), "--data-root", str(root)])
        ex = {r["path"]: r for r in csv.DictReader(open(tmp / "clean_train_exclusions.csv", newline=""))}
        self.assertEqual(set(ex), {"pw/a.jpg", "pw/b.jpg"})                                      # c.jpg is rescued
        self.assertTrue(all(r["reason"] == "conflict" for r in ex.values()))
        for name in ("verified_duplicates.csv", "duplicate_audit.json", "duplicate_audit.md"):
            self.assertTrue((tmp / name).exists(), name)
        self.assertIn("verified conflicts", (tmp / "duplicate_audit.md").read_text(encoding="utf-8").lower())


if __name__ == "__main__":
    unittest.main()
