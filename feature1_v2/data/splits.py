"""
Builds train / field-val / frozen benchmark splits (plan, Step 1) and decides
which classes enter the model (plan, Step 2).

Rules, in order
  1. Benchmark (test) = FIELD images only:
       - official test splits (PlantWild v1 'domain 0', PlantDoc test/), and
       - for field sources without an official split, a stable hash-based
         FIELD_TEST_FRACTION of each class (by duplicate group).
     Lab (PlantVillage-style) images and v1's processed_v2 data never enter
     it (v1 chose models on those splits).
  2. Field validation = official val splits + a stable FIELD_VAL_FRACTION of
     the remaining field training pool. Used for model selection,
     calibration and thresholds. Never the benchmark.
  3. Train = everything else (lab + field).
  4. Leakage: a near-duplicate group (data/dedupe.py) that spans the
     benchmark and anything else keeps only its benchmark members; one that
     spans val and train keeps only its val members. A group whose members
     carry DIFFERENT labels is dropped entirely and reported.
  5. Class inclusion: a label enters only with >= MIN_FIELD_TRAIN field
     training images and >= MIN_FIELD_TEST benchmark images; "_unsupported"
     is kept whenever present. Excluded labels are reported with counts.
  6. Freeze: benchmark/benchmark.csv (path, label) + benchmark/FROZEN.json
     (SHA-256 of the sorted list, counts, date). load_split("test") refuses
     to run unless final=True, and every final use is appended to
     benchmark/usage_log.txt, so any reuse of the benchmark is visible.

Usage
  python -m feature1_v2.data.splits            # needs work/manifest.csv and work/hashes.csv
"""

import argparse
import csv
import datetime as dt
import getpass
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from feature1_v2 import config, taxonomy
from feature1_v2.data import manifest as mf


def _stable_fraction(key):
    """Deterministic number in [0, 1) from a string (same on every machine)."""
    h = hashlib.sha256(f"{config.SPLIT_SALT}:{key}".encode()).hexdigest()
    return int(h[:12], 16) / float(16 ** 12)


def assign(rows, groups, min_train=None, min_test=None):
    """
    rows: manifest rows; groups: duplicate-group id per row (same order).
    Returns (rows with 'split' in {"train","val","test","drop"}, report dict, included labels).
    """
    min_train = config.MIN_FIELD_TRAIN if min_train is None else min_train
    min_test = config.MIN_FIELD_TEST if min_test is None else min_test
    rows = [dict(r, group=str(g)) for r, g in zip(rows, groups)]
    report = {"label_conflict_groups": 0, "dropped_label_conflict": 0,
              "dropped_leak_test": 0, "dropped_leak_val": 0, "excluded_unlabelled": 0}

    # 0. unlabelled / excluded rows
    for r in rows:
        if not r["label"]:
            r["split"] = "drop"
            report["excluded_unlabelled"] += 1

    # 1-3. initial split per row
    for r in rows:
        if r.get("split") == "drop":
            continue
        field = r["domain"] == "field"
        off = r["official_split"]
        if not field:
            r["split"] = "train"
        elif off == "test":
            r["split"] = "test"
        elif off == "val":
            r["split"] = "val"
        elif off == "train":
            r["split"] = "val" if _stable_fraction("val:" + r["group"]) < config.FIELD_VAL_FRACTION else "train"
        else:  # field source without official split -> hash by duplicate group
            f = _stable_fraction("test:" + r["group"])
            r["split"] = ("test" if f < config.FIELD_TEST_FRACTION else
                          "val" if f < config.FIELD_TEST_FRACTION + config.FIELD_VAL_FRACTION else "train")

    # 4. leakage and label conflicts, per duplicate group
    by_group = defaultdict(list)
    for r in rows:
        if r["split"] != "drop":
            by_group[r["group"]].append(r)
    for members in by_group.values():
        if len(members) < 2:
            continue
        if len({m["label"] for m in members}) > 1:
            report["label_conflict_groups"] += 1
            for m in members:
                m["split"] = "drop"
                report["dropped_label_conflict"] += 1
            continue
        splits = {m["split"] for m in members}
        if "test" in splits and len(splits) > 1:
            for m in members:
                if m["split"] != "test":
                    m["split"] = "drop"
                    report["dropped_leak_test"] += 1
        elif "val" in splits and "train" in splits:
            for m in members:
                if m["split"] == "train":
                    m["split"] = "drop"
                    report["dropped_leak_val"] += 1

    # 5. class inclusion
    field_train = Counter(r["label"] for r in rows if r["split"] == "train" and r["domain"] == "field")
    test = Counter(r["label"] for r in rows if r["split"] == "test")
    all_labels = sorted({r["label"] for r in rows if r["split"] != "drop"})
    included, excluded = [], {}
    for lab in all_labels:
        if lab == taxonomy.UNSUPPORTED or (field_train[lab] >= min_train and test[lab] >= min_test):
            included.append(lab)
        else:
            excluded[lab] = {"field_train": field_train[lab], "test": test[lab]}
    inc = set(included)
    for r in rows:
        if r["split"] != "drop" and r["label"] not in inc:
            r["split"] = "drop"
    report["excluded_classes"] = excluded
    report["counts"] = {s: Counter(r["label"] for r in rows if r["split"] == s) for s in ("train", "val", "test")}
    return rows, report, included


def benchmark_hash(test_rows):
    items = sorted(f"{r['path']}\t{r['label']}" for r in test_rows)
    return hashlib.sha256("\n".join(items).encode("utf-8")).hexdigest()


def freeze(rows, included, out_dir=None, force=False):
    out = Path(out_dir or config.BENCHMARK_DIR)
    out.mkdir(parents=True, exist_ok=True)
    test = sorted((r for r in rows if r["split"] == "test"), key=lambda r: r["path"])
    h = benchmark_hash(test)
    frozen = out / "FROZEN.json"
    if frozen.exists() and not force:
        old = json.loads(frozen.read_text())
        if old["sha256"] != h:
            raise SystemExit(
                "Benchmark already frozen with a DIFFERENT image list.\n"
                f"  frozen: {old['sha256']}\n  now:    {h}\n"
                "Re-freezing would make old and new results incomparable. "
                "Use --force only if the change is intended, and document it.")
    with open(out / "benchmark.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["path", "label", "source"])
        for r in test:
            w.writerow([r["path"], r["label"], r["source"]])
    frozen.write_text(json.dumps({
        "sha256": h, "n_images": len(test), "classes": included,
        "per_class": dict(sorted(Counter(r["label"] for r in test).items())),
        "frozen_on": dt.date.today().isoformat()}, indent=1, ensure_ascii=False))
    return h


def write_splits(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=mf.FIELDS + ["group", "split"])
        w.writeheader()
        w.writerows(rows)


def load_split(name, splits_csv=None, final=False, purpose=""):
    """
    Rows of one split. The benchmark ('test') is only returned with final=True,
    and each such use is logged with a purpose.
    """
    if name == "test":
        if not final:
            raise PermissionError("The frozen benchmark is for the final evaluation only. "
                                  "Use the 'val' split for development, or pass final=True with a purpose.")
        log = config.BENCHMARK_DIR / "usage_log.txt"
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "a", encoding="utf-8") as fh:
            fh.write(f"{dt.datetime.now().isoformat(timespec='seconds')}\t{getpass.getuser()}\t{purpose or '(no purpose given)'}\n")
    path = splits_csv or (config.WORK_DIR / "splits.csv")
    return [r for r in mf.read(path) if r["split"] == name]


def classes(splits_csv=None):
    path = Path(splits_csv or config.WORK_DIR / "splits.csv")
    return json.loads((path.parent / "classes.json").read_text(encoding="utf-8"))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default=str(config.WORK_DIR))
    ap.add_argument("--force-refreeze", action="store_true")
    a = ap.parse_args(argv)
    work = Path(a.work)
    rows = mf.read(work / "manifest.csv")
    hashes = {r["path"]: r["group"] for r in mf.read(work / "hashes.csv")}
    groups = [hashes.get(r["path"], f"solo:{r['path']}") for r in rows]
    rows, report, included = assign(rows, groups)
    write_splits(rows, work / "splits.csv")
    (work / "classes.json").write_text(json.dumps(included, indent=1))
    h = freeze(rows, included, force=a.force_refreeze)
    counts = report.pop("counts")
    (work / "split_report.json").write_text(json.dumps(
        {**report, "counts": {k: dict(v) for k, v in counts.items()}}, indent=1, ensure_ascii=False))
    print(f"classes included: {len(included)}  |  train {sum(counts['train'].values())}, "
          f"val {sum(counts['val'].values())}, benchmark {sum(counts['test'].values())} (sha256 {h[:12]})")
    print(f"dropped: label conflicts {report['dropped_label_conflict']}, test leakage {report['dropped_leak_test']}, "
          f"val leakage {report['dropped_leak_val']}")
    for lab, c in report["excluded_classes"].items():
        print(f"excluded (too few real photos): {lab:40} field train {c['field_train']}, test {c['test']}")


if __name__ == "__main__":
    main()
