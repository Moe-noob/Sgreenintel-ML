"""
Evaluates the SGreen Intel CNN on PlantWild v1 test split -- a real-world
dataset of crowdsourced internet images, distinct from PlantDoc.

Uses the official PlantWild train/val/test split (trainval.txt, split_idx=0
for test). PlantWild test images were never used during fine-tuning, making
this a genuine held-out evaluation.

PlantWild citation: Wei et al. (2024). Benchmarking In-the-Wild Multimodal
Plant Disease Recognition and A Versatile Baseline. arxiv 2408.03120.
"""

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

PLANTWILD_IMAGES_DIR = Path("data/raw/plantwild/plantwild/images")
PLANTWILD_SPLIT_FILE = Path("data/raw/plantwild/plantwild/trainval.txt")

# Same mapping as finetune_combined.py
PLANTWILD_TO_OURS = {
    "apple black rot":              "Apple___Black_rot",
    "apple leaf":                   "Apple___healthy",
    "apple rust":                   "Apple___Cedar_apple_rust",
    "apple scab":                   "Apple___Apple_scab",
    "bell pepper leaf":             "Pepper,_bell___healthy",
    "bell pepper leaf spot":        "Pepper,_bell___Bacterial_spot",
    "corn gray leaf spot":          "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot",
    "corn leaf":                    "Corn_(maize)___healthy",
    "corn northern leaf blight":    "Corn_(maize)___Northern_Leaf_Blight",
    "corn rust":                    "Corn_(maize)___Common_rust_",
    "grape black rot":              "Grape___Black_rot",
    "grape leaf":                   "Grape___healthy",
    "potato early blight":          "Potato___Early_blight",
    "potato late blight":           "Potato___Late_blight",
    "potato leaf":                  "Potato___healthy",
    "strawberry leaf":              "Strawberry___healthy",
    "strawberry leaf scorch":       "Strawberry___Leaf_scorch",
    "tomato bacterial leaf spot":   "Tomato___Bacterial_spot",
    "tomato early blight":          "Tomato___Early_blight",
    "tomato late blight":           "Tomato___Late_blight",
    "tomato leaf":                  "Tomato___healthy",
    "tomato leaf mold":             "Tomato___Leaf_Mold",
    "tomato mosaic virus":          "Tomato___Tomato_mosaic_virus",
    "tomato septoria leaf spot":    "Tomato___Septoria_leaf_spot",
    "tomato yellow leaf curl virus":"Tomato___Tomato_Yellow_Leaf_Curl_Virus",
}

eval_transform = transforms.Compose([
    transforms.Resize((config.IMAGE_SIZE, config.IMAGE_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])


from model_loader import load_best_model

def build_and_load_model():
    model, class_names, _ = load_best_model()
    return model, class_names


def evaluate():
    model, class_names = build_and_load_model()
    class_to_idx = {name: i for i, name in enumerate(class_names)}

    # Load test split from trainval.txt (split_idx=0 means test)
    lines = PLANTWILD_SPLIT_FILE.read_text().splitlines()
    test_entries = []
    for line in lines:
        parts = line.strip().split('=')
        if len(parts) != 3:
            continue
        img_rel, class_idx_str, split_idx_str = parts
        if int(split_idx_str) != 0:  # 0 = test
            continue
        class_name = img_rel.split('/')[0]
        if class_name not in PLANTWILD_TO_OURS:
            continue
        our_class = PLANTWILD_TO_OURS[class_name]
        if our_class not in class_to_idx:
            continue
        img_path = PLANTWILD_IMAGES_DIR / img_rel
        if not img_path.exists():
            continue
        test_entries.append((img_path, class_to_idx[our_class], our_class, class_name))

    print(f"Evaluating on PlantWild v1 test split: {len(test_entries)} images\n")

    total = 0
    correct = 0
    per_class = defaultdict(lambda: {"correct": 0, "total": 0, "plantwild_name": ""})

    for img_path, true_idx, our_class, plantwild_name in test_entries:
        try:
            image = Image.open(img_path).convert("RGB")
            tensor = eval_transform(image).unsqueeze(0).to(config.DEVICE)
            with torch.no_grad():
                outputs = model(tensor)
                predicted_idx = outputs.argmax(dim=1).item()
            if predicted_idx == true_idx:
                correct += 1
                per_class[our_class]["correct"] += 1
            per_class[our_class]["total"] += 1
            per_class[our_class]["plantwild_name"] = plantwild_name
            total += 1
        except Exception as e:
            print(f"  Skipping {img_path.name}: {e}")

    overall_acc = correct / total * 100 if total > 0 else 0
    pv_baseline = 90.29

    print(f"{'='*80}")
    print(f"PLANTWILD V1 EVALUATION RESULTS")
    print(f"{'='*80}")
    print(f"Classes evaluated:  {len(per_class)} / 25 mapped classes")
    print(f"Total images:       {total}")
    print(f"Correct:            {correct}")
    print(f"Overall accuracy:   {overall_acc:.2f}%")
    print(f"\nFor comparison: PlantVillage held-out test accuracy: {pv_baseline}%")
    print(f"Domain gap (lab vs PlantWild): {pv_baseline - overall_acc:.2f} pp")

    print(f"\nPer-class breakdown (sorted by accuracy):")
    sorted_classes = sorted(
        per_class.items(),
        key=lambda x: x[1]["correct"] / x[1]["total"] if x[1]["total"] > 0 else 0
    )
    for cls, stats in sorted_classes:
        acc = stats["correct"] / stats["total"] * 100 if stats["total"] > 0 else 0
        print(f"  {cls:<55s} {stats['correct']:>3}/{stats['total']:<3} ({acc:.1f}%)")

    # Save results
    results = {
        "overall_accuracy": overall_acc,
        "total_images": total,
        "correct": correct,
        "plantvillage_test_accuracy": pv_baseline,
        "domain_gap": pv_baseline - overall_acc,
        "classes_evaluated": len(per_class),
        "per_class": {
            cls: {
                "accuracy": s["correct"] / s["total"] * 100 if s["total"] > 0 else 0,
                "correct": s["correct"],
                "total": s["total"],
                "plantwild_folder": s["plantwild_name"],
            }
            for cls, s in per_class.items()
        },
    }
    out_path = Path("models/cnn/plantwild_evaluation.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    evaluate()