"""
Trains MobileNetV2 (transfer learning) on our 6-crop PlantVillage subset.

Strategy: frozen backbone, train only the classifier head. This is the
fastest and safest approach given our smaller classes (e.g. Potato_healthy,
106 train images) and modest hardware (GTX 1650, 4GB VRAM). If accuracy
isn't sufficient after this, the next step is unfreezing the last few
backbone blocks (see notes at the bottom of this file).
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torchvision import models
from tqdm import tqdm
import matplotlib.pyplot as plt

try:
    from . import config
    from .dataset import get_dataloaders, get_datasets, get_class_weights, get_class_names
except ImportError:
    import config
    from dataset import get_dataloaders, get_datasets, get_class_weights, get_class_names


def build_model(num_classes):
    model = models.mobilenet_v2(weights="IMAGENET1K_V1")

    for param in model.parameters():
        param.requires_grad = False

    num_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(num_features, num_classes)

    return model.to(config.DEVICE)


def train_one_epoch(model, dataloader, criterion, optimizer, device):
    model.train()
    total_loss = 0
    correct = 0
    total = 0

    for images, labels in tqdm(dataloader, desc="Training"):
        images, labels = images.to(device), labels.to(device)

        outputs = model(images)
        loss = criterion(outputs, labels)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        total_loss += loss.item()
        predictions = outputs.argmax(dim=1)
        correct += (predictions == labels).sum().item()
        total += labels.size(0)

    avg_loss = total_loss / len(dataloader)
    accuracy = 100 * correct / total
    return avg_loss, accuracy


def validate(model, dataloader, criterion, device):
    model.eval()
    total_loss = 0
    correct = 0
    total = 0

    with torch.no_grad():
        for images, labels in tqdm(dataloader, desc="Validating"):
            images, labels = images.to(device), labels.to(device)

            outputs = model(images)
            loss = criterion(outputs, labels)
            total_loss += loss.item()

            predictions = outputs.argmax(dim=1)
            correct += (predictions == labels).sum().item()
            total += labels.size(0)

    avg_loss = total_loss / len(dataloader)
    accuracy = 100 * correct / total
    return avg_loss, accuracy


def plot_curves(train_losses, val_losses, train_accs, val_accs):
    plt.figure(figsize=(12, 5))

    plt.subplot(1, 2, 1)
    plt.plot(train_losses, label="Train Loss", marker='o')
    plt.plot(val_losses, label="Validation Loss", marker='o')
    plt.xlabel("Epoch")
    plt.ylabel("Loss")
    plt.title("Loss Curve")
    plt.legend()

    plt.subplot(1, 2, 2)
    plt.plot(train_accs, label="Train Accuracy", marker='o')
    plt.plot(val_accs, label="Validation Accuracy", marker='o')
    plt.xlabel("Epoch")
    plt.ylabel("Accuracy (%)")
    plt.title("Accuracy Curve")
    plt.legend()

    plt.tight_layout()
    save_path = config.MODEL_SAVE_DIR / "training_curves.png"
    plt.savefig(save_path)
    print(f"Saved training curves to {save_path}")
    plt.show()


def main():
    print(f"Device: {config.DEVICE}\n")

    train_loader, val_loader, test_loader = get_dataloaders()
    train_ds, val_ds, test_ds = get_datasets()
    class_names = get_class_names(train_ds)

    model = build_model(config.NUM_CLASSES)

    weights = get_class_weights(train_ds) if config.USE_CLASS_WEIGHTS else None
    criterion = nn.CrossEntropyLoss(weight=weights)
    optimizer = optim.Adam(model.parameters(), lr=config.LEARNING_RATE, weight_decay=config.WEIGHT_DECAY)

    train_losses, val_losses = [], []
    train_accs, val_accs = [], []
    best_val_loss = float("inf")

    config.MODEL_SAVE_DIR.mkdir(parents=True, exist_ok=True)

    for epoch in range(config.EPOCHS):
        print(f"\n--- Epoch {epoch+1}/{config.EPOCHS} ---")

        train_loss, train_acc = train_one_epoch(model, train_loader, criterion, optimizer, config.DEVICE)
        val_loss, val_acc = validate(model, val_loader, criterion, config.DEVICE)

        train_losses.append(train_loss)
        val_losses.append(val_loss)
        train_accs.append(train_acc)
        val_accs.append(val_acc)

        print(f"Train Loss={train_loss:.4f}, Train Acc={train_acc:.2f}% | "
              f"Val Loss={val_loss:.4f}, Val Acc={val_acc:.2f}%")

        # Save the best model separately from the final epoch — protects
        # against overfitting in later epochs eating a good earlier result.
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save({
                "model_state_dict": model.state_dict(),
                "class_names": class_names,
                "epoch": epoch + 1,
                "val_loss": val_loss,
                "val_accuracy": val_acc,
            }, config.BEST_MODEL_PATH)
            print(f"New best model saved (val_loss={val_loss:.4f})")

    plot_curves(train_losses, val_losses, train_accs, val_accs)
    print(f"\nTraining complete. Best model saved at: {config.BEST_MODEL_PATH}")


if __name__ == "__main__":
    main()


# --- Notes for next steps if accuracy isn't sufficient with a frozen backbone ---
# Unfreeze the last few MobileNetV2 blocks (similar to the KAUST notebook's
# "fine-tune last layers + classifier" strategy):
#
#   for param in model.features[-3:].parameters():
#       param.requires_grad = True
#
# This trains more parameters -> better potential accuracy, but needs more
# time per epoch and slightly more risk of overfitting smaller classes.
# Try the frozen version first and look at the real numbers before deciding
# whether this is necessary.