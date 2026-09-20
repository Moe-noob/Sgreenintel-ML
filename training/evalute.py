"""
Evaluates the best saved checkpoint on the held-out test set — the real,
unbiased performance number, since the test set was never touched during
training or checkpoint selection (that used val loss instead).

Produces: overall accuracy, per-class precision/recall/F1, and a confusion
matrix — the confusion matrix specifically lets us check whether our
smaller/imbalanced classes (e.g. Potato_healthy, Tomato_mosaic_virus) are
actually performing worse, rather than guessing.
"""

import torch
import torch.nn as nn
from torchvision import models
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib.pyplot as plt
import numpy as np

try:
    from . import config
    from .dataset import get_dataloaders, get_datasets
except ImportError:
    import config
    from dataset import get_dataloaders, get_datasets


def build_model(num_classes):
    """Must match the architecture used in train_cnn.py exactly, or the
    saved weights won't load correctly."""
    model = models.mobilenet_v2(weights=None)  # no need to redownload ImageNet weights
    num_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(num_features, num_classes)
    return model.to(config.DEVICE)


def load_best_model():
    model_path = (config.V7P2_MODEL_PATH if config.V7P2_MODEL_PATH.exists()
              else config.V7_MODEL_PATH if config.V7_MODEL_PATH.exists()
              else config.V6P2_MODEL_PATH if config.V6P2_MODEL_PATH.exists()
              else config.V6_MODEL_PATH if config.V6_MODEL_PATH.exists()
              else config.V5P2_MODEL_PATH if config.V5P2_MODEL_PATH.exists()
              else config.V4P2_MODEL_PATH if config.V4P2_MODEL_PATH.exists()
              else config.V4_MODEL_PATH)
    print(f"Using model: {model_path.name}")
    checkpoint = torch.load(model_path, map_location=config.DEVICE)
    model = build_model(config.NUM_CLASSES)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    print(f"Loaded checkpoint from epoch {checkpoint['epoch']}")
    val_acc_key = 'val_accuracy' if 'val_accuracy' in checkpoint else 'val_acc'
    print(f"  (val_loss={checkpoint['val_loss']:.4f}, val_accuracy={checkpoint[val_acc_key]:.2f}%)\n")

    return model, checkpoint["class_names"]


def run_inference(model, dataloader, device):
    all_preds = []
    all_labels = []

    with torch.no_grad():
        for images, labels in dataloader:
            images = images.to(device)
            outputs = model(images)
            preds = outputs.argmax(dim=1).cpu().numpy()

            all_preds.extend(preds)
            all_labels.extend(labels.numpy())

    return np.array(all_labels), np.array(all_preds)


def plot_confusion_matrix(cm, class_names, save_path):
    # Shorten labels for readability — full crop-disease names are long
    short_names = [name.split("___")[-1][:15] for name in class_names]

    fig, ax = plt.subplots(figsize=(16, 14))
    im = ax.imshow(cm, cmap="Blues")

    ax.set_xticks(range(len(short_names)))
    ax.set_yticks(range(len(short_names)))
    ax.set_xticklabels(short_names, rotation=90, fontsize=7)
    ax.set_yticklabels(short_names, fontsize=7)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    ax.set_title("Confusion Matrix — Test Set")

    plt.colorbar(im)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    print(f"Saved confusion matrix to {save_path}")
    plt.show()


def main():
    print(f"Device: {config.DEVICE}\n")

    model, class_names = load_best_model()
    _, _, test_loader = get_dataloaders()

    print("Running inference on test set...")
    y_true, y_pred = run_inference(model, test_loader, config.DEVICE)

    overall_accuracy = (y_true == y_pred).mean() * 100
    print(f"\n{'='*60}")
    print(f"TEST SET ACCURACY: {overall_accuracy:.2f}%")
    print(f"{'='*60}\n")

    report = classification_report(y_true, y_pred, target_names=class_names, digits=3)
    print(report)

    # Save the full report to a file for the report/defense prep
    report_path = config.MODEL_SAVE_DIR / "evaluation_report.txt"
    with open(report_path, "w") as f:
        f.write(f"Test Set Accuracy: {overall_accuracy:.2f}%\n\n")
        f.write(report)
    print(f"Saved full evaluation report to {report_path}")

    cm = confusion_matrix(y_true, y_pred)
    cm_path = config.MODEL_SAVE_DIR / "confusion_matrix.png"
    plot_confusion_matrix(cm, class_names, cm_path)


if __name__ == "__main__":
    main()