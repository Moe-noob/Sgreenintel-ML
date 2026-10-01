"""
Convert PlantDoc's object-detection annotations to a one-class ("leaf")
YOLO dataset for the leaf detector.

PlantDoc (github.com/pratikkayal/PlantDoc-Object-Detection-Dataset) ships
images with Pascal-VOC XML files and/or CSVs train_labels.csv /
test_labels.csv with columns filename,width,height,class,xmin,ymin,xmax,ymax.
Both are supported. All disease classes become class 0 "leaf": the
detector only finds leaves; the classifier decides the condition.

Images that are in the classifier's frozen benchmark are excluded from the
detector's TRAINING set, so the benchmark stays unseen end to end.

Usage
  python -m feature1_v2.detector.prepare_plantdoc --src $F1V2_DATA_ROOT/PlantDoc-Object-Detection-Dataset --out work/detector/yolo
"""

import argparse
import csv
import shutil
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

from feature1_v2 import config


def boxes_from_csv(csv_path):
    out = defaultdict(list)
    with open(csv_path, newline="") as fh:
        for r in csv.DictReader(fh):
            out[r["filename"]].append((int(float(r["width"])), int(float(r["height"])),
                                       float(r["xmin"]), float(r["ymin"]), float(r["xmax"]), float(r["ymax"])))
    return out


def boxes_from_voc(folder):
    out = defaultdict(list)
    for xml in Path(folder).glob("*.xml"):
        root = ET.parse(xml).getroot()
        fn = root.findtext("filename") or xml.with_suffix(".jpg").name
        w = int(float(root.findtext("size/width") or 0))
        h = int(float(root.findtext("size/height") or 0))
        for o in root.findall("object"):
            b = o.find("bndbox")
            out[fn].append((w, h, *(float(b.findtext(k)) for k in ("xmin", "ymin", "xmax", "ymax"))))
    return out


def to_yolo_lines(boxes):
    lines = []
    for w, h, x0, y0, x1, y1 in boxes:
        if w <= 0 or h <= 0 or x1 <= x0 or y1 <= y0:
            continue
        cx, cy = (x0 + x1) / 2 / w, (y0 + y1) / 2 / h
        bw, bh = (x1 - x0) / w, (y1 - y0) / h
        lines.append(f"0 {min(max(cx, 0), 1):.6f} {min(max(cy, 0), 1):.6f} {min(bw, 1):.6f} {min(bh, 1):.6f}")
    return lines


def build(src, out, exclude_names=()):
    src, out = Path(src), Path(out)
    exclude = set(exclude_names)
    stats = {}
    for split, folder in (("train", "TRAIN"), ("val", "TEST")):
        img_dir = next((p for p in (src / folder, src / folder.lower(), src / split) if p.is_dir()), None)
        if img_dir is None:
            continue
        csv_path = next((p for p in (src / f"{folder.lower()}_labels.csv", src / f"{split}_labels.csv") if p.exists()), None)
        boxes = boxes_from_csv(csv_path) if csv_path else boxes_from_voc(img_dir)
        (out / "images" / split).mkdir(parents=True, exist_ok=True)
        (out / "labels" / split).mkdir(parents=True, exist_ok=True)
        n = skipped = 0
        for fn, bx in boxes.items():
            img = img_dir / fn
            if not img.exists() or (split == "train" and fn in exclude):
                skipped += 1
                continue
            lines = to_yolo_lines(bx)
            if not lines:
                continue
            shutil.copy2(img, out / "images" / split / fn)
            (out / "labels" / split / (Path(fn).stem + ".txt")).write_text("\n".join(lines))
            n += 1
        stats[split] = {"images": n, "skipped": skipped}
    (out / "leaf.yaml").write_text(f"path: {out.resolve()}\ntrain: images/train\nval: images/val\nnames:\n  0: leaf\n")
    return stats


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", default=str(config.WORK_DIR / "detector" / "yolo"))
    a = ap.parse_args(argv)
    bench = config.BENCHMARK_DIR / "benchmark.csv"
    exclude = []
    if bench.exists():
        with open(bench, newline="") as fh:
            exclude = [Path(r["path"]).name for r in csv.DictReader(fh)]
    print(build(a.src, a.out, exclude))
    print("Train with:  yolo detect train data=" + str(Path(a.out) / "leaf.yaml") +
          " model=yolov8n.pt imgsz=640 epochs=80 project=work/detector/runs name=leaf")


if __name__ == "__main__":
    main()
