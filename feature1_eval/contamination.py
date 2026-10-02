"""
How many benchmark photos have a near-identical twin in v1's OWN training data?

PlantDoc and PlantWild were both collected by web image search, so the same photo can sit in a test split of one and in the
training data of the other (or of v1's base set). v1 fine-tuned on PlantDoc-train and PlantWild's official train split
(training/finetune_combined.py, split_idx = 1) on top of the base set assembled by training/prepare_data_v2.py. A benchmark
photo whose twin v1 trained on is not a fair test of v1.

This script uses files the pipeline already wrote:
  work/manifest.csv   path, source, domain, raw_label, label, official_split         (data/manifest.py)
  work/hashes.csv     path, phash, group      (same group = near-duplicates)         (data/dedupe.py)
  <eval dir>/predictions.csv   from  python -m feature1_eval.evaluate --legacy <ckpt> --split test --final ...

A benchmark photo is "contaminated for v1" when its duplicate group contains an image from v1's training data:
  legacy_processed_v2 (official_split == train)  +  plantdoc (train)  +  plantwild_v1 (train)
(v1's validation and test folders were used to CHOOSE models, not to train, so they are not counted here.)

It then reports v1's accuracy on all, clean and contaminated photos (only classes v1 can predict), with 95% Wilson intervals,
for both the automatic mode and the crop-given mode.

Usage
  python -m feature1_eval.contamination --predictions work/eval_mobilenetv2_sgreenintel_v6p2/test/predictions.csv
"""

import argparse
import csv
import json
import math
from pathlib import Path

from feature1_eval import config
from feature1_eval.data import manifest as mf

V1_TRAINED_ON = {("legacy_processed_v2", "train"), ("plantdoc", "train"), ("plantwild_v1", "train")}


def wilson(k, n, z=1.96):
    """95% Wilson score interval for k successes in n trials: (proportion, low, high), or None if n == 0."""
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, centre - half), min(1.0, centre + half))


def v1_training_groups(manifest_rows, path_group):
    """Set of duplicate-group ids that contain at least one image v1 was trained on."""
    groups = set()
    for r in manifest_rows:
        if (r["source"], r["official_split"]) in V1_TRAINED_ON and r["path"] in path_group:
            groups.add(path_group[r["path"]])
    return groups


def _acc(rows, key):
    use = [r for r in rows if r["label_known_to_model"] == "1" and r[key] != ""]
    return wilson(sum(r[key] == r["label"] for r in use), len(use)), len(use)


def analyse(pred_rows, path_group, path_source, v1_groups):
    """pred_rows: dicts from predictions.csv. Returns the result dictionary."""
    for r in pred_rows:
        g = path_group.get(r["path"])
        r["_contaminated"] = g is not None and g in v1_groups
        r["_source"] = path_source.get(r["path"], "?")
    clean = [r for r in pred_rows if not r["_contaminated"]]
    dirty = [r for r in pred_rows if r["_contaminated"]]
    res = {"n_benchmark_photos": len(pred_rows), "n_contaminated": len(dirty),
           "share_contaminated": len(dirty) / len(pred_rows) if pred_rows else None, "by_source": {}, "accuracy": {}}
    for s in sorted({r["_source"] for r in pred_rows}):
        sub = [r for r in pred_rows if r["_source"] == s]
        res["by_source"][s] = {"n": len(sub), "contaminated": sum(r["_contaminated"] for r in sub)}
    for mode, key in (("auto", "pred_auto"), ("crop_given", "pred_crop_given")):
        out = {}
        for name, rows in (("all", pred_rows), ("clean", clean), ("contaminated", dirty)):
            ci, n = _acc(rows, key)
            out[name] = {"n": n, "accuracy": ci[0] if ci else None, "ci95": [ci[1], ci[2]] if ci else None}
        res["accuracy"][mode] = out
    return res


def to_markdown(res, pred_path):
    pct = lambda x: "n/a" if x is None else f"{100 * x:.1f}%"
    lines = [f"# v1 on the frozen benchmark: contamination check", "", f"Predictions: `{pred_path}`", "",
             f"- Benchmark photos: **{res['n_benchmark_photos']}**; with a near-duplicate in v1's training data: "
             f"**{res['n_contaminated']}** ({pct(res['share_contaminated'])})", ""]
    for s, v in res["by_source"].items():
        lines.append(f"  - {s}: {v['contaminated']} of {v['n']}")
    lines += ["", "| Mode | Photos | n | Accuracy | 95% interval |", "|---|---|---|---|---|"]
    for mode, blocks in res["accuracy"].items():
        for name, b in blocks.items():
            ci = b["ci95"]
            lines.append(f"| {mode} | {name} | {b['n']} | {pct(b['accuracy'])} | "
                         f"{'n/a' if ci is None else f'{100 * ci[0]:.1f}-{100 * ci[1]:.1f}%'} |")
    lines += ["", "Only photos of classes v1 can predict are counted. 'Clean' photos have no near-duplicate (pHash distance <= "
              f"{config.PHASH_MAX_DISTANCE} of 64 bits) among the images v1 trained on, so the clean row is the fairest estimate of "
              "v1's accuracy on unseen field photos. A large gap between clean and contaminated rows means the reported score was inflated."]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--predictions", required=True)
    ap.add_argument("--manifest", default=str(config.WORK_DIR / "manifest.csv"))
    ap.add_argument("--hashes", default=str(config.WORK_DIR / "hashes.csv"))
    a = ap.parse_args(argv)

    manifest_rows = mf.read(a.manifest)
    path_group = {r["path"]: r["group"] for r in mf.read(a.hashes)}
    path_source = {r["path"]: r["source"] for r in manifest_rows}
    v1_groups = v1_training_groups(manifest_rows, path_group)
    with open(a.predictions, newline="", encoding="utf-8") as fh:
        pred_rows = list(csv.DictReader(fh))
    res = analyse(pred_rows, path_group, path_source, v1_groups)
    out = Path(a.predictions).parent
    (out / "contamination.json").write_text(json.dumps(res, indent=1))
    md = to_markdown(res, a.predictions)
    (out / "contamination.md").write_text(md, encoding="utf-8")
    print(md)
    print(f"-> {out / 'contamination.md'}")


if __name__ == "__main__":
    main()
