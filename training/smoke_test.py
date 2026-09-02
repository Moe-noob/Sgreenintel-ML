"""
Quick sanity check before real training: confirms the model builds correctly,
data flows through it with the right shapes, and one forward+backward pass
runs without errors. Not part of the real pipeline — just a fast fail-early check.
"""

import torch
import torch.nn as nn
from torchvision import models

try:
    from . import config
    from .dataset import get_dataloaders, get_class_weights, get_datasets
except ImportError:
    import config
    from dataset import get_dataloaders, get_class_weights, get_datasets


def build_model(num_classes):
    model = models.mobilenet_v2(weights="IMAGENET1K_V1")

    # Freeze the backbone for now — matches the "train only classifier head"
    # strategy from the KAUST notebook. Fastest option, safest for our
    # smaller classes (e.g. Potato_healthy).
    for param in model.parameters():
        param.requires_grad = False

    # Replace the final classification layer for our 27 classes
    num_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(num_features, num_classes)

    return model.to(config.DEVICE)


def main():
    print(f"Device: {config.DEVICE}")

    # --- Load one real batch ---
    train_loader, val_loader, test_loader = get_dataloaders()
    images, labels = next(iter(train_loader))
    images, labels = images.to(config.DEVICE), labels.to(config.DEVICE)
    print(f"Batch shape: {images.shape}")  # expect [16, 3, 224, 224]
    print(f"Labels shape: {labels.shape}, sample labels: {labels[:5]}")

    # --- Build model ---
    model = build_model(config.NUM_CLASSES)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"Trainable params: {trainable:,} / {total:,} ({100*trainable/total:.2f}%)")

    # --- Class weights + loss ---
    train_ds, _, _ = get_datasets()
    weights = get_class_weights(train_ds)
    criterion = nn.CrossEntropyLoss(weight=weights)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.LEARNING_RATE)

    # --- One forward + backward pass ---
    model.train()
    outputs = model(images)
    print(f"Output shape: {outputs.shape}")  # expect [16, 27]

    loss = criterion(outputs, labels)
    print(f"Loss (should be a normal-looking number, not NaN): {loss.item():.4f}")

    optimizer.zero_grad()
    loss.backward()
    optimizer.step()

    print("\n✅ Smoke test passed — one full forward+backward pass completed with no errors.")


if __name__ == "__main__":
    main()