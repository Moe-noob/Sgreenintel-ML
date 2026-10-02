import json
import tempfile
import unittest
from pathlib import Path

from feature1_eval import drops_report as dr
from feature1_eval.data import splits


def _row(path, label, off, domain="field", source="plantdoc"):
    return {"path": path, "source": source, "domain": domain, "raw_label": "x", "label": label, "official_split": off}


class TestDropsReport(unittest.TestCase):
    def setUp(self):
        rows, groups = [], []
        for lab in ("tomato__healthy", "tomato__late_blight", "tomato__early_blight"):       # plenty of field training photos
            for i in range(30):
                rows.append(_row(f"train/{lab}/{i}.jpg", lab, "train"))
                groups.append(f"{lab}-{i}")
        test = [("A", "tomato__healthy", "A"),
                ("B", "tomato__late_blight", "BC"), ("C", "tomato__early_blight", "BC"),      # same photo, two labels -> conflict
                ("D", "potato__healthy", "D"),                                                 # no field training photos -> class excluded
                ("E", "tomato__healthy", "EF"), ("F", "tomato__healthy", "EF")]                # two near-copies, both kept
        for name, lab, g in test:
            rows.append(_row(f"test/{name}.jpg", lab, "test", source="plantwild_v1" if name in "EF" else "plantdoc"))
            groups.append(g)
        self.rows, self.report, self.included = splits.assign(rows, groups, min_train=2, min_test=1)

    def test_every_official_test_photo_is_accounted_for(self):
        res = dr.analyse(self.rows, self.included)
        self.assertEqual(res["official_test_photos"], 6)
        self.assertEqual(res["kept"], 3)                                                   # A, E, F
        self.assertEqual(res["by_status"], {"kept": 3, "dropped: label conflict": 2, "dropped: class excluded": 1})
        self.assertEqual(res["by_source"]["plantdoc"], {"kept": 1, "dropped: label conflict": 2, "dropped: class excluded": 1})
        self.assertEqual(res["by_source"]["plantwild_v1"], {"kept": 2})
        self.assertEqual(res["by_class"]["potato__healthy"], {"dropped: class excluded": 1})
        self.assertEqual(res["top_conflicting_label_pairs"], [("tomato__early_blight vs tomato__late_blight", 2)])

    def test_effective_size_counts_near_copies_once(self):
        res = dr.analyse(self.rows, self.included)
        self.assertEqual(res["benchmark_effective_size"], 2)                                # groups A and EF
        self.assertEqual(res["benchmark_photos_sharing_a_duplicate_group"], 2)              # E and F

    def test_relaxed_inclusion_keeps_the_class(self):
        # with --min-train 0 the class with no field training photos stays in the benchmark
        rows, groups = [], []
        for r in self.rows:
            rows.append({k: v for k, v in r.items() if k not in ("split", "group")})
            groups.append(r["group"])
        rows2, _, included2 = splits.assign(rows, groups, min_train=0, min_test=1)
        res = dr.analyse(rows2, included2)
        self.assertEqual(res["kept"], 4)
        self.assertEqual(res["by_class"]["potato__healthy"], {"kept": 1})

    def test_markdown_and_main(self):
        tmp = Path(tempfile.mkdtemp())
        splits.write_splits(self.rows, tmp / "splits.csv")
        (tmp / "classes.json").write_text(json.dumps(self.included))
        dr.main(["--work", str(tmp)])
        md = (tmp / "drops_report.md").read_text(encoding="utf-8")
        self.assertIn("Kept in the frozen benchmark: **3**", md)
        self.assertIn("dropped: label conflict: **2**", md)
        self.assertIn("Effective benchmark size, counting near-copies once: **2** of 3", md)
        self.assertTrue((tmp / "drops_report.json").exists())


if __name__ == "__main__":
    unittest.main()
