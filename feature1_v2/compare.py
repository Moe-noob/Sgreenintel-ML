"""
Paired comparison of two evaluated models on the SAME photos (e.g. v1 vs v2):
difference in accuracy and macro-F1 with a 95 % paired-bootstrap interval.
Only photos whose true class both models can predict are compared
(column label_known_to_model written by evaluate.py).

  python -m feature1_v2.compare work/v1_baseline/eval_val/predictions.csv work/runs/X/eval_val/predictions.csv
"""

import argparse
import csv

import numpy as np

from feature1_v2 import metrics


def read(path):
    with open(path, newline="") as fh:
        return {r["path"]: r for r in csv.DictReader(fh)}


def compare(a_rows, b_rows, column="pred_auto"):
    common = [p for p in a_rows if p in b_rows and a_rows[p][column] and b_rows[p][column]
              and a_rows[p]["label_known_to_model"] == "1" and b_rows[p]["label_known_to_model"] == "1"]
    y = np.array([a_rows[p]["label"] for p in common])
    pa = np.array([a_rows[p][column] for p in common])
    pb = np.array([b_rows[p][column] for p in common])
    return {"n": len(common),
            "accuracy_a": metrics.accuracy(y, pa), "accuracy_b": metrics.accuracy(y, pb),
            "accuracy_diff": metrics.paired_bootstrap_diff(metrics.accuracy, y, pa, pb),
            "macro_f1_diff": metrics.paired_bootstrap_diff(metrics.macro_f1, y, pa, pb, n=500)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--json", help="also write the results to this JSON file")
    a = ap.parse_args(argv)
    A, B = read(a.a), read(a.b)
    out = {}
    for col in ("pred_auto", "pred_crop_given"):
        r = compare(A, B, col)
        if not r["n"]:
            continue
        d, lo, hi = r["accuracy_diff"]
        f, flo, fhi = r["macro_f1_diff"]
        verdict = "B better" if lo > 0 else "A better" if hi < 0 else "no clear difference"
        out[col] = {**r, "verdict": verdict}
        print(f"{col}: {r['n']} common photos | accuracy A {r['accuracy_a']:.1%}, B {r['accuracy_b']:.1%}, "
              f"B-A {d:+.1%} ({lo:+.1%} to {hi:+.1%}) | macro-F1 B-A {f:+.3f} ({flo:+.3f} to {fhi:+.3f}) -> {verdict}")
    if a.json:
        import json
        with open(a.json, "w") as fh:
            json.dump(out, fh, indent=1, default=float)
    return out


if __name__ == "__main__":
    main()
