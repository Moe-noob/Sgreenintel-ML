"""
Extends our original 6-crop PlantVillage-only dataset with 3 additional
sources: fgvc8 (Apple, real orchard photos), cds (Corn, real field
photos), sms (Strawberry, adds a new crop). Filtering follows PLDC-80's
own published methodology for fgvc8 and sms (see their README's
documented class deletions), not an arbitrary choice.

Does NOT modify data/processed/{train,val,test} from prepare_data.py --
writes to data/processed_v2/ instead, so the original validated 93.57%
CNN result and its data remain untouched and reproducible.
"""

import shutil
import random
from pathlib import Path
import pandas as pd

random.seed(42)

RAW_DIR = Path("data/raw")
OUTPUT_DIR = Path("data/processed_v2")
SPLIT_RATIOS = {"train": 0.70, "val": 0.15, "test": 0.15}

PLANTVILLAGE_COLOR = RAW_DIR / "PlantVillage-Dataset" / "raw" / "color"


def split_and_copy(images, dest_class_name):
    """Splits a list of image paths 70/15/15 and copies into the v2 structure."""
    images = list(images)
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
        dest_dir = OUTPUT_DIR / split_name / dest_class_name
        dest_dir.mkdir(parents=True, exist_ok=True)
        for img in split_images:
            shutil.copy2(img, dest_dir / img.name)

    return {k: len(v) for k, v in splits.items()}


def get_plantvillage_images(folder_name):
    folder = PLANTVILLAGE_COLOR / folder_name
    return list(folder.glob("*.*")) if folder.exists() else []


def process_class(dest_class_name, source_image_lists):
    """source_image_lists: list of lists of image paths from different sources."""
    all_images = [img for source_list in source_image_lists for img in source_list]
    counts = split_and_copy(all_images, dest_class_name)
    total = sum(counts.values())
    print(f"{dest_class_name:50s} total={total:5d}  (train={counts['train']}, val={counts['val']}, test={counts['test']})")
    return total


def main():
    grand_total = 0

    print("--- Unchanged crops (PlantVillage only) ---")
    unchanged = {
        "Tomato___Bacterial_spot": ["Tomato___Bacterial_spot"],
        "Tomato___Early_blight": ["Tomato___Early_blight"],
        "Tomato___healthy": ["Tomato___healthy"],
        "Tomato___Late_blight": ["Tomato___Late_blight"],
        "Tomato___Leaf_Mold": ["Tomato___Leaf_Mold"],
        "Tomato___Septoria_leaf_spot": ["Tomato___Septoria_leaf_spot"],
        "Tomato___Spider_mites Two-spotted_spider_mite": ["Tomato___Spider_mites Two-spotted_spider_mite"],
        "Tomato___Target_Spot": ["Tomato___Target_Spot"],
        "Tomato___Tomato_mosaic_virus": ["Tomato___Tomato_mosaic_virus"],
        "Tomato___Tomato_Yellow_Leaf_Curl_Virus": ["Tomato___Tomato_Yellow_Leaf_Curl_Virus"],
        "Potato___Early_blight": ["Potato___Early_blight"],
        "Potato___healthy": ["Potato___healthy"],
        "Potato___Late_blight": ["Potato___Late_blight"],
        "Pepper,_bell___Bacterial_spot": ["Pepper,_bell___Bacterial_spot"],
        "Pepper,_bell___healthy": ["Pepper,_bell___healthy"],
        "Grape___Black_rot": ["Grape___Black_rot"],
        "Grape___Esca_(Black_Measles)": ["Grape___Esca_(Black_Measles)"],
        "Grape___healthy": ["Grape___healthy"],
        "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)": ["Grape___Leaf_blight_(Isariopsis_Leaf_Spot)"],
        "Apple___Black_rot": ["Apple___Black_rot"],  # fgvc8 has no black rot -- PlantVillage only
        "Corn_(maize)___Common_rust_": ["Corn_(maize)___Common_rust_"],
    }
    for dest_name, source_folders in unchanged.items():
        images = [img for folder in source_folders for img in get_plantvillage_images(folder)]
        grand_total += process_class(dest_name, [images])

    print("\n--- Apple (merged with fgvc8) ---")
    fgvc8_df = pd.read_csv(RAW_DIR / "fgvc8" / "train.csv")
    fgvc8_images_dir = RAW_DIR / "fgvc8" / "train_images"

    def fgvc8_images_for_label(label):
        filenames = fgvc8_df[fgvc8_df["labels"] == label]["image"].tolist()
        return [fgvc8_images_dir / f for f in filenames if (fgvc8_images_dir / f).exists()]

    apple_merges = {
        "Apple___healthy": (get_plantvillage_images("Apple___healthy"), fgvc8_images_for_label("healthy")),
        "Apple___Apple_scab": (get_plantvillage_images("Apple___Apple_scab"), fgvc8_images_for_label("scab")),
        "Apple___Cedar_apple_rust": (get_plantvillage_images("Apple___Cedar_apple_rust"), fgvc8_images_for_label("rust")),
    }
    for dest_name, (pv_images, fgvc8_images) in apple_merges.items():
        grand_total += process_class(dest_name, [pv_images, fgvc8_images])

    apple_new = {
        "Apple___Frog_eye_leaf_spot": fgvc8_images_for_label("frog_eye_leaf_spot"),
        "Apple___Powdery_mildew": fgvc8_images_for_label("powdery_mildew"),
    }
    for dest_name, images in apple_new.items():
        grand_total += process_class(dest_name, [images])

    print("\n--- Corn (merged with cds) ---")
    cds_train_dir = RAW_DIR / "cds" / "train"
    cds_test_dir = RAW_DIR / "cds" / "test"

    def cds_images(subfolder):
        images = []
        for base in [cds_train_dir, cds_test_dir]:
            folder = base / subfolder
            if folder.exists():
                images.extend(folder.glob("*.*"))
        return images

    corn_merges = {
        "Corn_(maize)___healthy": (get_plantvillage_images("Corn_(maize)___healthy"), []),
        "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot": (
            get_plantvillage_images("Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot"), cds_images("gls")),
        "Corn_(maize)___Northern_Leaf_Blight": (
            get_plantvillage_images("Corn_(maize)___Northern_Leaf_Blight"), cds_images("nlb")),
    }
    for dest_name, (pv_images, cds_imgs) in corn_merges.items():
        grand_total += process_class(dest_name, [pv_images, cds_imgs])

    grand_total += process_class("Corn_(maize)___Northern_Leaf_Spot", [cds_images("nls")])

    print("\n--- Strawberry (NEW crop: PlantVillage + sms) ---")
    strawberry_unchanged = {
        "Strawberry___healthy": get_plantvillage_images("Strawberry___healthy"),
        "Strawberry___Leaf_scorch": get_plantvillage_images("Strawberry___Leaf_scorch"),
    }
    for dest_name, images in strawberry_unchanged.items():
        grand_total += process_class(dest_name, [images])

    sms_train_dir = RAW_DIR / "sms" / "train"
    SMS_ALLOWED_PREFIXES = {
        "angular_leafspot": "Strawberry___Angular_leafspot",
        "leaf_spot": "Strawberry___Leaf_spot",
        "powdery_mildew_leaf": "Strawberry___Powdery_mildew",
    }
    sms_by_class = {dest: [] for dest in SMS_ALLOWED_PREFIXES.values()}
    for img_path in sms_train_dir.glob("*.jpg"):
        for prefix, dest_name in SMS_ALLOWED_PREFIXES.items():
            # exact prefix match, avoiding e.g. "leaf_spot" matching "powdery_mildew_leaf_spot"-style false positives
            if img_path.stem.startswith(prefix) and not any(
                img_path.stem.startswith(other) for other in SMS_ALLOWED_PREFIXES if other != prefix and other.startswith(prefix)
            ):
                sms_by_class[dest_name].append(img_path)
                break

    for dest_name, images in sms_by_class.items():
        grand_total += process_class(dest_name, [images])

    print(f"\n=== TOTAL: {grand_total} images across all classes ===")


if __name__ == "__main__":
    main()