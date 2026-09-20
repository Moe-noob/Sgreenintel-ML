"""
Evaluates the SGreen Intel 35-class CNN on PlantDoc -- a real-world
field-condition dataset -- to quantify the domain gap between
PlantVillage (lab) test accuracy and real-world performance.

PlantDoc citation: Singh et al. (2020). PlantDoc: A Dataset for Visual
Plant Disease Detection. CODS-COMAD 2020.
https://doi.org/10.1145/3371158.3371196

Only PlantDoc classes that map to our 35 supported classes are evaluated.
PlantDoc classes for unsupported crops (Blueberry, Cherry, Peach, etc.)
are skipped. Our classes not covered by PlantDoc are noted in the report.

Uses PlantDoc's test split only -- never the train split -- to keep
this a genuine held-out evaluation.
"""

import sys
import json
from pathlib import Path
from collections import defaultdict

import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image

try:
    from . import config
except ImportError:
    import config

PLANTDOC_TEST_DIR = Path("data/raw/PlantDoc-Dataset/test")

# Mapping: PlantDoc folder name -> our class name
PLANTDOC_TO_OURS = {
    "Apple leaf":                   "Apple___healthy",
    "Apple rust leaf":              "Apple___Cedar_apple_rust",
    "Apple Scab Leaf":              "Apple___Apple_scab",
    "Bell_pepper leaf":             "Pepper,_bell___healthy",
    "Bell_pepper leaf spot":        "Pepper,_bell___Bacterial_spot",
    "Corn Gray leaf spot":          "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot",
    "Corn leaf blight":             "Corn_(maize)___Northern_Leaf_Blight",
    "Corn rust leaf":               "Corn_(maize)___Common_rust_",
    "grape leaf":                   "Grape___healthy",
    "grape leaf black rot":         "Grape___Black_rot",
    "Potato leaf early blight":     "Potato___Early_blight",
    "Potato leaf late blight":      "Potato___Late_blight",
    "Strawberry leaf":              "Strawberry___healthy",
    "Tomato Early blight leaf":     "Tomato___Early_blight",
    "Tomato leaf":                  "Tomato___healthy",
    "Tomato leaf bacterial spot":   "Tomato___Bacterial_spot",
    "Tomato leaf late blight":      "Tomato___Late_blight",
    "Tomato leaf mosaic virus":     "Tomato___Tomato_mosaic_virus",
    "Tomato leaf yellow virus":     "Tomato___Tomato_Yellow_Leaf_Curl_Virus",
    "Tomato mold leaf":             "Tomato___Leaf_Mold",
    "Tomato Septoria leaf spot":    "Tomato___Septoria_leaf_spot",
}

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD  = [0.229, 0.224, 0.225]

eval_transform = transforms.Compose([
    transforms.Resize((config.IMAGE_SIZE, config.IMAGE_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
])


from model_loader import load_best_model

def build_and_load_model():
    model, class_names, _ = load_best_model()
    return model, class_names


def evaluate():
    model, class_names = build_and_load_model()
    class_to_idx = {name: i for i, name in enumerate(class_names)}

    total = 0
    correct = 0
    per_class = defaultdict(lambda: {"correct": 0, "total": 0, "plantdoc_name": ""})
    skipped_folders = []

    print(f"Evaluating on PlantDoc test set: {PLANTDOC_TEST_DIR}\n")

    for plantdoc_folder, our_class in PLANTDOC_TO_OURS.items():
        folder_path = PLANTDOC_TEST_DIR / plantdoc_folder
        if not folder_path.exists():
            print(f"  WARNING: folder not found: {folder_path}")
            skipped_folders.append(plantdoc_folder)
            continue

        if our_class not in class_to_idx:
            print(f"  WARNING: our class '{our_class}' not in model checkpoint")
            skipped_folders.append(plantdoc_folder)
            continue

        true_idx = class_to_idx[our_class]
        images = list(folder_path.glob("*.jpg")) + \
                 list(folder_path.glob("*.JPG")) + \
                 list(folder_path.glob("*.png")) + \
                 list(folder_path.glob("*.jpeg"))

        if not images:
            print(f"  WARNING: no images found in {folder_path}")
            skipped_folders.append(plantdoc_folder)
            continue

        class_correct = 0
        for img_path in images:
            try:
                image = Image.open(img_path).convert("RGB")
                tensor = eval_transform(image).unsqueeze(0).to(config.DEVICE)
                with torch.no_grad():
                    outputs = model(tensor)
                    predicted_idx = outputs.argmax(dim=1).item()
                if predicted_idx == true_idx:
                    class_correct += 1
                    correct += 1
                total += 1
            except Exception as e:
                print(f"  Skipping {img_path.name}: {e}")

        per_class[our_class]["correct"] = class_correct
        per_class[our_class]["total"] = len(images)
        per_class[our_class]["plantdoc_name"] = plantdoc_folder
        acc = class_correct / len(images) * 100 if images else 0
        print(f"  {plantdoc_folder:<35s} -> {our_class:<55s} {class_correct}/{len(images)} ({acc:.1f}%)")

    overall_acc = correct / total * 100 if total > 0 else 0

    print(f"\n{'='*80}")
    print(f"PLANTDOC EVALUATION RESULTS")
    print(f"{'='*80}")
    print(f"Classes evaluated:  {len(per_class)} / 27 PlantDoc classes")
    print(f"Classes skipped:    {len(skipped_folders)} (unsupported crops or missing folders)")
    print(f"Total images:       {total}")
    print(f"Correct:            {correct}")
    print(f"Overall accuracy:   {overall_acc:.2f}%")
    print(f"\nFor comparison: PlantVillage held-out test set accuracy: 90.29%")
    print(f"Domain gap (lab vs real-world): {90.29 - overall_acc:.2f} percentage points")

    print(f"\nPer-class breakdown (sorted by accuracy):")
    sorted_classes = sorted(per_class.items(),
                            key=lambda x: x[1]["correct"]/x[1]["total"] if x[1]["total"] > 0 else 0)
    for cls, stats in sorted_classes:
        acc = stats["correct"] / stats["total"] * 100 if stats["total"] > 0 else 0
        print(f"  {cls:<55s} {stats['correct']:>3}/{stats['total']:<3} ({acc:.1f}%)")

    if skipped_folders:
        print(f"\nSkipped PlantDoc classes (no matching crop in our model):")
        for f in skipped_folders:
            print(f"  {f}")

    # Save results
    results = {
        "overall_accuracy": overall_acc,
        "total_images": total,
        "correct": correct,
        "plantvillage_test_accuracy": 90.29,
        "domain_gap": 90.29 - overall_acc,
        "classes_evaluated": len(per_class),
        "per_class": {cls: {
            "accuracy": s["correct"]/s["total"]*100 if s["total"] > 0 else 0,
            "correct": s["correct"],
            "total": s["total"],
            "plantdoc_folder": s["plantdoc_name"]
        } for cls, s in per_class.items()},
    }
    out_path = Path("models/cnn/plantdoc_evaluation.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    evaluate()