import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from feature1_eval import calibrate as cal


class TestJointSearch(unittest.TestCase):
    def setUp(self):
        # Built by hand: confidence and entropy both track correctness, but NOT perfectly together, so the joint
        # search must do better than either threshold alone. 20 photos.
        #                     conf:   0.95 0.92 0.90 0.88 0.85 0.83 0.80 0.78 0.75 0.72 0.70 0.68 0.65 0.60 0.55 0.50 0.45 0.40 0.35 0.30
        self.conf =    np.array([0.95,0.92,0.90,0.88,0.85,0.83,0.80,0.78,0.75,0.72,0.70,0.68,0.65,0.60,0.55,0.50,0.45,0.40,0.35,0.30])
        #                     entropy:0.05 0.08 0.35 0.12 0.15 0.40 0.20 0.45 0.25 0.50 0.30 0.55 0.60 0.35 0.65 0.70 0.75 0.80 0.85 0.90
        self.entropy = np.array([0.05,0.08,0.35,0.12,0.15,0.40,0.20,0.45,0.25,0.50,0.30,0.55,0.60,0.35,0.65,0.70,0.75,0.80,0.85,0.90])
        # correct: true for the 10 highest-confidence AND lowest-entropy photos (indices 0,1,3,4,6,8,10,12,2,5 by combined rank);
        # wrong for two photos that are confident but high-entropy (idx 2, 5) -- a joint rule should exclude them, a
        # confidence-only rule could not.
        self.correct = np.array([1,1,0,1,1,0,1,1,1,1,1,0,1,0,0,0,0,0,0,0], dtype=bool)

    def test_perfect_target_excludes_the_confident_but_high_entropy_wrong_photos(self):
        r = cal.joint_search(self.conf, self.entropy, self.correct, target=1.0)
        self.assertIsNotNone(r)
        m = (self.conf >= r["confidence_threshold"]) & (self.entropy <= r["entropy_threshold"])
        self.assertTrue(self.correct[m].all())                     # genuinely 100% on what it accepts
        self.assertGreaterEqual(int(m.sum()), 7)                   # and accepts a reasonable chunk, not just 1 photo
        # a confidence-only rule reaching 100% would have to stop before the two wrong-but-confident photos (idx 2 at
        # conf 0.90, idx 5 at conf 0.83), i.e. accept at most 2 photos (idx 0, 1) -- the joint rule must beat that
        conf_only_thr, conf_only_cov, _ = __import__("feature1_eval.metrics", fromlist=["x"]).threshold_for_accuracy(
            self.conf, self.correct, 1.0)
        self.assertGreater(r["coverage"], conf_only_cov)

    def test_higher_target_never_exceeds_lower_targets_coverage(self):
        covs = [cal.joint_search(self.conf, self.entropy, self.correct, t)["coverage"] for t in (0.6, 0.8, 1.0)]
        self.assertEqual(covs, sorted(covs, reverse=True))

    def test_unreachable_target_returns_none(self):
        self.assertIsNone(cal.joint_search(self.conf, self.entropy, self.correct, target=1.01))
        all_wrong = np.zeros(20, dtype=bool)
        self.assertIsNone(cal.joint_search(self.conf, self.entropy, all_wrong, target=0.5))

    def test_matches_a_hand_worked_small_case(self):
        # 4 photos, entropy already sorted with confidence so the joint search degenerates to the confidence-only case
        c = np.array([0.9, 0.8, 0.7, 0.6])
        e = np.array([0.1, 0.2, 0.3, 0.4])
        k = np.array([True, True, False, True])
        # target 100%: must stop before the wrong photo (idx 2) -> accept idx 0,1 only -> coverage 0.5, conf_thr 0.8
        r = cal.joint_search(c, e, k, target=1.0)
        self.assertEqual((r["confidence_threshold"], r["coverage"], r["n_accepted"]), (0.8, 0.5, 2))
        # target 75%: accepting all 4 gives 75% (3/4) -- the lowest confidence threshold reaching 75% is the minimum, 0.6
        r2 = cal.joint_search(c, e, k, target=0.75)
        self.assertEqual((round(r2["confidence_threshold"], 2), r2["coverage"], r2["n_accepted"]), (0.6, 1.0, 4))


class TestAtFixedThresholds(unittest.TestCase):
    def test_matches_a_hand_count(self):
        conf = np.array([0.9, 0.5, 0.8, 0.3])
        ent = np.array([0.1, 0.1, 0.5, 0.1])
        correct = np.array([True, True, False, False])
        r = cal.at_fixed_thresholds(conf, ent, correct, conf_thr=0.7, entropy_thr=0.4)
        self.assertEqual((r["n_accepted"], r["coverage"], r["accuracy"]), (1, 0.25, 1.0))   # only photo 0 passes both


class TestAnalyseAndMarkdown(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        rows = []
        for i in range(60):
            correct = i < 45                                           # 75% overall, skewed toward high confidence
            conf = 0.5 + 0.49 * (1 - i / 60) if correct else 0.3 + 0.3 * (i / 60)
            ent = 0.05 + 0.3 * (i / 60) if correct else 0.5 + 0.4 * (i / 60)
            rows.append({"label": "tomato__healthy", "pred_auto": "tomato__healthy" if correct else "tomato__late_blight",
                         "conf_auto": f"{conf:.4f}", "entropy_auto": f"{ent:.4f}",
                         "pred_crop_given": "tomato__healthy" if correct else "tomato__late_blight",
                         "conf_crop_given": f"{min(conf * 1.1, 0.99):.4f}", "entropy_crop_given": f"{ent * 0.8:.4f}"})
        self.rows = rows

    def test_both_modes_present_and_coverage_decreases_with_target(self):
        res = cal.analyse(self.rows, targets=(0.8, 0.9))
        self.assertEqual(set(res), {"auto", "crop_given"})
        for mode in res:
            self.assertEqual(res[mode]["n_photos"], 60)
            r80, r90 = res[mode]["recommendations"]["80%"], res[mode]["recommendations"]["90%"]
            if r80 and r90:
                self.assertGreaterEqual(r80["coverage"], r90["coverage"])
        # crop_given has higher confidence / lower entropy by construction -> should do at least as well at 90%
        a90, c90 = res["auto"]["recommendations"]["90%"], res["crop_given"]["recommendations"]["90%"]
        if a90 and c90:
            self.assertGreaterEqual(c90["coverage"], a90["coverage"] - 1e-9)

    def test_markdown_mentions_both_modes_and_current_thresholds(self):
        res = cal.analyse(self.rows)
        md = cal.to_markdown(res, "x/predictions.csv")
        self.assertIn("## auto", md)
        self.assertIn("## crop_given", md)
        self.assertIn(f"confidence >= {cal.CURRENT_CONF}", md)

    def test_main_refuses_a_test_split_report(self):
        (self.tmp / "report.json").write_text(json.dumps({"split": "test"}))
        import csv
        with open(self.tmp / "predictions.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(self.rows[0]))
            w.writeheader()
            w.writerows(self.rows)
        with self.assertRaises(SystemExit):
            cal.main(["--predictions", str(self.tmp / "predictions.csv")])

    def test_main_runs_on_a_val_split_report(self):
        (self.tmp / "report.json").write_text(json.dumps({"split": "val"}))
        import csv
        with open(self.tmp / "predictions.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(self.rows[0]))
            w.writeheader()
            w.writerows(self.rows)
        cal.main(["--predictions", str(self.tmp / "predictions.csv")])
        self.assertTrue((self.tmp / "calibration.json").exists())
        self.assertTrue((self.tmp / "calibration.md").exists())


if __name__ == "__main__":
    unittest.main()
