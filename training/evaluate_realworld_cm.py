"""
Generates confusion matrices for PlantDoc and PlantWild test sets using
the current best model (v4p2). Unlike evalute.py which only evaluates on
PlantVillage, this shows which classes the model confuses with which in
real-world conditions -- the key diagnostic for deciding what to fix next.

Outputs:
  models/cnn/plantdoc_confusion_matrix.png
  models/cnn/plantwild_confusion_matrix.png
"""

from pathlib import Path
from collections import defaultdict

import torch
import torch.nn as nn
import numpy as np
import matplotlib.pyplot as plt
from torchvision import models, transforms
from PIL import Image

try:
    from . import config
except ImportError:
    import config

# ---- PlantDoc mapping ----
PLANTDOC_TEST_DIR = Path("data/raw/PlantDoc-Dataset/test")
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

# ---- PlantWild mapping ----
PLANTWILD_IMAGES_DIR = Path("data/raw/plantwild/plantwild/images")
PLANTWILD_SPLIT_FILE = Path("data/raw/plantwild/plantwild/trainval.txt")
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


def build_and_load_model():
    model = models.mobilenet_v2(weights=None)
    num_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(num_features, config.NUM_CLASSES)
    model = model.to(config.DEVICE)
    model_path = (config.V7P2_MODEL_PATH if config.V7P2_MODEL_PATH.exists()
              else config.V7_MODEL_PATH if config.V7_MODEL_PATH.exists()
              else config.V6P2_MODEL_PATH if config.V6P2_MODEL_PATH.exists()
              else config.V6_MODEL_PATH if config.V6_MODEL_PATH.exists()
              else config.V5P2_MODEL_PATH if config.V5P2_MODEL_PATH.exists()
              else config.V4P2_MODEL_PATH if config.V4P2_MODEL_PATH.exists()
              else config.V4_MODEL_PATH)
    print(f"Using model: {model_path.name}")
    checkpoint = torch.load(model_path, map_location=config.DEVICE)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model, checkpoint["class_names"]


def run_inference(model, class_to_idx, samples):
    true_indices = []
    pred_indices = []
    for img_path, true_class in samples:
        try:
            image = Image.open(img_path).convert("RGB")
            tensor = eval_transform(image).unsqueeze(0).to(config.DEVICE)
            with torch.no_grad():
                outputs = model(tensor)
                predicted_idx = outputs.argmax(dim=1).item()
            true_indices.append(class_to_idx[true_class])
            pred_indices.append(predicted_idx)
        except Exception:
            pass
    return true_indices, pred_indices


def build_plantdoc_samples(class_to_idx):
    samples = []
    classes_used = set()
    for folder, our_class in PLANTDOC_TO_OURS.items():
        folder_path = PLANTDOC_TEST_DIR / folder
        if not folder_path.exists() or our_class not in class_to_idx:
            continue
        for ext in ['*.jpg', '*.JPG', '*.png', '*.jpeg']:
            for img in folder_path.glob(ext):
                samples.append((img, our_class))
                classes_used.add(our_class)
    return samples, sorted(classes_used)


def build_plantwild_samples(class_to_idx):
    lines = PLANTWILD_SPLIT_FILE.read_text().splitlines()
    samples = []
    classes_used = set()
    for line in lines:
        parts = line.strip().split('=')
        if len(parts) != 3:
            continue
        img_rel, _, split_idx_str = parts
        if int(split_idx_str) != 0:
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
        samples.append((img_path, our_class))
        classes_used.add(our_class)
    return samples, sorted(classes_used)


def plot_confusion_matrix(true_indices, pred_indices, class_names,
                          class_labels, title, out_path):
    n = len(class_labels)
    label_to_local = {label: i for i, label in enumerate(class_labels)}

    cm = np.zeros((n, n), dtype=int)
    for t, p in zip(true_indices, pred_indices):
        true_label = class_names[t]
        pred_label = class_names[p]
        if true_label in label_to_local:
            ti = label_to_local[true_label]
            pi = label_to_local.get(pred_label, -1)
            if pi >= 0:
                cm[ti][pi] += 1

    row_sums = cm.sum(axis=1, keepdims=True)
    cm_norm = np.divide(cm.astype(float), row_sums,
                        where=row_sums > 0,
                        out=np.zeros_like(cm, dtype=float))

    short_labels = []
    for label in class_labels:
        parts = label.split('___')
        if len(parts) == 2:
            crop = parts[0].split('_(')[0].split(',')[0]
            disease = parts[1].replace('_', ' ')
            short_labels.append(f"{crop[:6]}\n{disease[:20]}")
        else:
            short_labels.append(label[:20])

    fig_size = max(14, n * 0.75)
    fig, ax = plt.subplots(figsize=(fig_size, fig_size))
    im = ax.imshow(cm_norm, interpolation='nearest', cmap='Blues', vmin=0, vmax=1)
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(short_labels, rotation=45, ha='right', fontsize=7)
    ax.set_yticklabels(short_labels, fontsize=7)

    for i in range(n):
        for j in range(n):
            val = cm_norm[i, j]
            if val >= 0.10:
                color = 'white' if val > 0.5 else 'black'
                ax.text(j, i, f'{val:.2f}', ha='center', va='center',
                        fontsize=6, color=color)

    ax.set_title(title, fontsize=13, fontweight='bold', pad=15)
    ax.set_ylabel('True class', fontsize=10)
    ax.set_xlabel('Predicted class', fontsize=10)
    plt.tight_layout()
    fig.savefig(out_path, dpi=130, bbox_inches='tight')
    plt.close()
    print(f"Saved: {out_path}")


def print_top_confusions(true_indices, pred_indices, class_names,
                         class_labels, dataset_name, top_n=10):
    label_to_local = {label: i for i, label in enumerate(class_labels)}
    confusions = defaultdict(int)
    for t, p in zip(true_indices, pred_indices):
        true_label = class_names[t]
        pred_label = class_names[p]
        if true_label != pred_label and true_label in label_to_local:
            confusions[(true_label, pred_label)] += 1

    sorted_conf = sorted(confusions.items(), key=lambda x: -x[1])
    print(f"\nTop {top_n} confusions on {dataset_name}:")
    for (true_c, pred_c), count in sorted_conf[:top_n]:
        t_short = true_c.split('___')[-1].replace('_', ' ')
        p_short = pred_c.split('___')[-1].replace('_', ' ')
        print(f"  {t_short:<35s} -> {p_short:<35s}  ({count}x)")


def main():
    model, class_names = build_and_load_model()
    class_to_idx = {name: i for i, name in enumerate(class_names)}
    out_dir = Path("models/cnn")

    print("\n--- PlantDoc confusion matrix ---")
    pd_samples, pd_classes = build_plantdoc_samples(class_to_idx)
    pd_true, pd_pred = run_inference(model, class_to_idx, pd_samples)
    print(f"Evaluated {len(pd_true)} images across {len(pd_classes)} classes")
    plot_confusion_matrix(
        pd_true, pd_pred, class_names, pd_classes,
        title=f"PlantDoc Test Set -- Confusion Matrix (v4p2, {len(pd_true)} images)",
        out_path=out_dir / "plantdoc_confusion_matrix.png"
    )
    print_top_confusions(pd_true, pd_pred, class_names, pd_classes, "PlantDoc")

    print("\n--- PlantWild confusion matrix ---")
    pw_samples, pw_classes = build_plantwild_samples(class_to_idx)
    pw_true, pw_pred = run_inference(model, class_to_idx, pw_samples)
    print(f"Evaluated {len(pw_true)} images across {len(pw_classes)} classes")
    plot_confusion_matrix(
        pw_true, pw_pred, class_names, pw_classes,
        title=f"PlantWild v1 Test Set -- Confusion Matrix (v4p2, {len(pw_true)} images)",
        out_path=out_dir / "plantwild_confusion_matrix.png"
    )
    print_top_confusions(pw_true, pw_pred, class_names, pw_classes, "PlantWild")

    print("\nDone. Both confusion matrices saved to models/cnn/")


if __name__ == "__main__":
    main()
