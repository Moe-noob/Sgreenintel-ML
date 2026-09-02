"""
Filters PlantVillage down to our 6 target crops and splits each class
into train/val/test (70/15/15), matching the split ratios defined in
the project report.
"""

import shutil
import random
from pathlib import Path

# ---- Config ----
SOURCE_DIR = Path("data/raw/PlantVillage-Dataset/raw/color")
OUTPUT_DIR = Path("data/processed")

# Match by folder-name prefix, since some names contain special characters
CROP_PREFIXES = [
    "Apple___",
    "Corn_(maize)___",
    "Grape___",
    "Pepper,_bell___",
    "Potato___",
    "Tomato___",
]

SPLIT_RATIOS = {"train": 0.70, "val": 0.15, "test": 0.15}
SEED = 42

# ---- Script ----
random.seed(SEED)

def get_target_classes():
    classes = []
    for folder in sorted(SOURCE_DIR.iterdir()):
        if folder.is_dir() and any(folder.name.startswith(p) for p in CROP_PREFIXES):
            classes.append(folder)
    return classes

def split_and_copy(class_folder):
    images = list(class_folder.glob("*.*"))
    random.shuffle(images)

    n = len(images)
    n_train = int(n * SPLIT_RATIOS["train"])
    n_val = int(n * SPLIT_RATIOS["val"])

    splits = {
        "train": images[:n_train],
        "val": images[n_train:n_train + n_val],
        "test": images[n_train + n_val:],
    }

    for split_name, split_images in splits.items():
        dest_dir = OUTPUT_DIR / split_name / class_folder.name
        dest_dir.mkdir(parents=True, exist_ok=True)
        for img in split_images:
            shutil.copy2(img, dest_dir / img.name)

    return {k: len(v) for k, v in splits.items()}

def main():
    if not SOURCE_DIR.exists():
        raise FileNotFoundError(f"Source not found: {SOURCE_DIR}. Check the clone path.")

    classes = get_target_classes()
    print(f"Found {len(classes)} matching classes.\n")

    summary = []
    for class_folder in classes:
        counts = split_and_copy(class_folder)
        total = sum(counts.values())
        summary.append((class_folder.name, counts["train"], counts["val"], counts["test"], total))
        print(f"{class_folder.name:55s} train={counts['train']:5d}  val={counts['val']:5d}  test={counts['test']:5d}  total={total:5d}")

    grand_total = sum(row[4] for row in summary)
    print(f"\nTotal images across {len(summary)} classes: {grand_total}")

if __name__ == "__main__":
    main()