"""
Scan every enabled dataset in sources.json into one manifest CSV:

    path, source, domain, raw_label, label, official_split

  path            relative to F1V2_DATA_ROOT
  domain          "field" (real photo) or "lab" (plain-background, PlantVillage-style)
  label           unified label (taxonomy.py), "_unsupported", or "" if excluded/unknown
  official_split  "train" / "val" / "test" when the dataset defines one, else ""

Unknown source labels are never guessed: they are counted and reported, so
the mapping can be completed by hand (taxonomy.py or the source's label_map).

Usage
  python -m feature1_v2.data.manifest                      # build work/manifest.csv
  python -m feature1_v2.data.manifest --list-labels plantdoc
"""

import argparse
import csv
import json
import os
import sys
from collections import Counter
from pathlib import Path

from feature1_v2 import config, taxonomy

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
FIELDS = ["path", "source", "domain", "raw_label", "label", "official_split"]


def load_sources(path=None):
    doc = json.loads(Path(path or config.SOURCES_FILE).read_text(encoding="utf-8"))
    return doc["sources"]


def _images(folder):
    return sorted(p for p in Path(folder).rglob("*") if p.suffix.lower() in IMG_EXT and p.is_file())


def _domain(src, file_path):
    d = src.get("domain", "field")
    if d == "auto_plantvillage_filename":
        # PlantVillage file names look like "<uuid>___<code> <n>.JPG"; fgvc8/cds/sms do not.
        return "lab" if "___" in Path(file_path).name else "field"
    return d


def _map_label(src, raw):
    if "fixed_label" in src:
        return src["fixed_label"], True
    if src.get("label_map"):
        return taxonomy.unify(src["label_map"], raw)
    return taxonomy.unify(src["map"], raw)


def scan_split_folders(root, src):
    """root/<split>/<class>/*.jpg with split in train/val/test (PlantDoc, processed_v2)."""
    for split in ("train", "val", "test"):
        d = root / split
        if not d.is_dir():
            continue
        for cls in sorted(p for p in d.iterdir() if p.is_dir()):
            for img in _images(cls):
                yield img, cls.name, split


def scan_class_folders(root, src):
    """root/<class>/*.jpg (no official split)."""
    for cls in sorted(p for p in root.iterdir() if p.is_dir()):
        for img in _images(cls):
            yield img, cls.name, ""


def scan_plantwild_trainval(root, src):
    """
    PlantWild v1: root/images/<class>/*.jpg and root/trainval.txt with lines
    '<path>=<label index>=<domain>' where domain 0 = test, 1 = train, 2 = val
    and label index refers to the sorted class-folder list
    (github.com/tqwei05/MVPDR, datasets/plantwild.py).
    """
    images = root / "images"
    classes = sorted(p.name for p in images.iterdir() if p.is_dir())
    split_file = root / "trainval.txt"
    names = {0: "test", 1: "train", 2: "val"}
    if split_file.exists():
        for line in split_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            name, lab, dom = line.rsplit("=", 2)
            cls = classes[int(lab)]
            p = images / cls / Path(name).name
            if p.exists():
                yield p, cls, names[int(dom)]
    else:
        for cls in classes:
            for img in _images(images / cls):
                yield img, cls, ""


SCANNERS = {"split_folders": scan_split_folders, "class_folders": scan_class_folders,
            "plantwild_trainval": scan_plantwild_trainval}


def build(data_root=None, sources=None, only=None):
    data_root = Path(data_root or config.DATA_ROOT)
    rows, unknown, missing = [], Counter(), []
    for src in sources or load_sources():
        if not src.get("enabled", True) or (only and src["name"] != only):
            continue
        root = (data_root / src["path"]).resolve()
        if not root.exists():
            missing.append(f"{src['name']}: {root}")
            continue
        for img, raw, split in SCANNERS[src["layout"]](root, src):
            lbl, known = _map_label(src, raw)
            if not known:
                unknown[(src["name"], raw)] += 1
            if src.get("split_policy") == "train_only":
                split = "train"
            rows.append({"path": os.path.relpath(img, data_root),
                         "source": src["name"], "domain": _domain(src, img), "raw_label": raw,
                         "label": lbl or "", "official_split": split})
    return rows, unknown, missing


def write(rows, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def read(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def summary(rows):
    by = Counter((r["label"] or "(excluded)", r["domain"]) for r in rows)
    labels = sorted({k[0] for k in by})
    lines = [f"{'label':42}{'field':>8}{'lab':>8}"]
    for lab in labels:
        lines.append(f"{lab:42}{by[(lab, 'field')]:>8}{by[(lab, 'lab')]:>8}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", default=None)
    ap.add_argument("--out", default=str(config.WORK_DIR / "manifest.csv"))
    ap.add_argument("--list-labels", metavar="SOURCE", help="print the raw class names of one source and exit")
    a = ap.parse_args(argv)

    if a.list_labels:
        src = next((s for s in load_sources() if s["name"] == a.list_labels), None)
        if not src:
            sys.exit(f"no source named {a.list_labels}")
        src = dict(src, enabled=True)
        rows, unknown, missing = build(a.data_root, [src])
        for raw, n in sorted(Counter(r["raw_label"] for r in rows).items()):
            lbl = next(r["label"] for r in rows if r["raw_label"] == raw)
            print(f"{n:6}  {raw!r:45} -> {lbl or '(unmapped)'}")
        for m in missing:
            print("missing:", m)
        return

    rows, unknown, missing = build(a.data_root)
    write(rows, a.out)
    print(summary(rows))
    print(f"\n{len(rows)} images written to {a.out}")
    for m in missing:
        print("MISSING SOURCE (skipped):", m)
    for (src, raw), n in sorted(unknown.items()):
        print(f"UNMAPPED LABEL (excluded): {src}: {raw!r} ({n} images) -- add it to taxonomy.py or the source's label_map")


if __name__ == "__main__":
    main()
