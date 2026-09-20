"""
Controlled architecture experiment: EfficientNet-B0 vs MobileNetV2 baseline.

Exactly the same as finetune_combined.py (PlantDoc + PlantWild, same splits,
same augmentation, same sampler, same optimizer, same epochs, same resolution)
with ONLY the architecture changed from MobileNetV2 to EfficientNet-B0.

This answers the specific question: "Does a stronger architecture improve
real-world generalization on plant disease photos, or is the domain gap
a data problem that architecture can't fix?"

Key differences from MobileNetV2 training:
- No pretrained checkpoint to load (different architecture) -- starts from
  ImageNet pretrained EfficientNet-B0 weights (standard transfer learning)
- Unfreezes only the last 3 feature blocks + classifier (same proportion as MobileNetV2)
- EfficientNet-B0 classifier: Sequential(Dropout(0.2), Linear(1280, num_classes))
- Total params: ~5.3M vs MobileNetV2's 3.4M

Saves as V8_MODEL_PATH. Run finetune_phase2_effb0.py after for phase 2.

Baseline to beat (v6p2, MobileNetV2):
  PlantVillage: 95.44%  PlantDoc: 70.81%  PlantWild: 63.79%
"""

import time
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, WeightedRandomSampler, ConcatDataset
from torchvision import models, transforms, datasets

try:
    from . import config
except ImportError:
    import config

from finetune_combined import (
    build_plantdoc_samples, build_plantwild_samples,
    RealWorldDataset,
)

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD  = [0.229, 0.224, 0.225]

finetune_transform = transforms.Compose([
    transforms.RandomResizedCrop(config.IMAGE_SIZE, scale=(0.7, 1.0)),
    transforms.RandomHorizontalFlip(),
    transforms.RandomVerticalFlip(),
    transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.1, hue=0.05),
    transforms.ToTensor(),
    transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
])

val_transform = transforms.Compose([
    transforms.Resize((config.IMAGE_SIZE, config.IMAGE_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
])


def build_efficientnet_b0(num_classes, device):
    """
    EfficientNet-B0 with ImageNet pretrained weights.
    Freezes everything except the last 3 feature blocks + classifier,
    same as MobileNetV2 training for a fair comparison.

    EfficientNet-B0 has 9 feature blocks (indices 0-8).
    We unfreeze blocks 6, 7, 8 + classifier.
    """
    model = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.DEFAULT)

    # Replace classifier head for our 35 classes
    in_features = model.classifier[1].in_features  # 1280
    model.classifier[1] = nn.Linear(in_features, num_classes)
    model = model.to(device)

    # Freeze everything first
    for param in model.parameters():
        param.requires_grad = False

    # Unfreeze last 3 feature blocks (6, 7, 8) + classifier
    for i in [6, 7, 8]:
        for param in model.features[i].parameters():
            param.requires_grad = True
    for param in model.classifier.parameters():
        param.requires_grad = True

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"EfficientNet-B0. Trainable: {trainable:,} / {total:,} ({trainable/total*100:.1f}%)")
    return model


def main():
    print("=== SGreen Intel v8: EfficientNet-B0 architecture experiment ===")
    print("=== Controlled comparison against MobileNetV2 (v6p2 baseline) ===\n")

    # Load class names from v2 MobileNetV2 checkpoint (class list is the same)
    checkpoint = torch.load(config.BEST_MODEL_PATH, map_location=config.DEVICE)
    class_names = checkpoint["class_names"]
    class_to_idx = {name: i for i, name in enumerate(class_names)}

    # Build datasets -- identical to finetune_combined.py
    plantdoc_samples = build_plantdoc_samples(class_to_idx)
    plantwild_samples = build_plantwild_samples(class_to_idx)
    all_real_world = plantdoc_samples + plantwild_samples
    print(f"Total real-world train samples: {len(all_real_world)}")

    real_world_dataset = RealWorldDataset(all_real_world, finetune_transform)

    pv_train_dir = Path(config.DATA_DIR) / "train"
    pv_dataset = datasets.ImageFolder(str(pv_train_dir), transform=finetune_transform)
    pv_class_to_idx = {name: i for i, name in enumerate(class_names)}
    pv_dataset.class_to_idx = pv_class_to_idx
    pv_dataset.samples = [
        (path, pv_class_to_idx.get(Path(path).parent.name, 0))
        for path, _ in pv_dataset.samples
    ]
    print(f"PlantVillage train samples: {len(pv_dataset)}\n")

    rw_weight = len(pv_dataset) / len(real_world_dataset) * 0.67
    weights = [rw_weight] * len(real_world_dataset) + [1.0] * len(pv_dataset)
    combined = ConcatDataset([real_world_dataset, pv_dataset])
    sampler = WeightedRandomSampler(weights, num_samples=len(combined), replacement=True)
    train_loader = DataLoader(
        combined, batch_size=config.BATCH_SIZE,
        sampler=sampler, num_workers=4, pin_memory=True
    )

    pv_val_dir = Path(config.DATA_DIR) / "val"
    val_dataset = datasets.ImageFolder(str(pv_val_dir), transform=val_transform)
    val_loader = DataLoader(
        val_dataset, batch_size=config.BATCH_SIZE,
        shuffle=False, num_workers=4, pin_memory=True
    )

    model = build_efficientnet_b0(len(class_names), config.DEVICE)

    from dataset import get_class_weights
    weights_loss = get_class_weights(pv_dataset).to(config.DEVICE)
    criterion = nn.CrossEntropyLoss(weight=weights_loss)
    optimizer = torch.optim.Adam(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=1e-4
    )

    NUM_EPOCHS = 7
    best_val_loss = float("inf")
    best_val_acc = 0.0

    print(f"Fine-tuning for {NUM_EPOCHS} epochs...\n")

    for epoch in range(NUM_EPOCHS):
        model.train()
        train_loss, train_correct, train_total = 0.0, 0, 0
        t0 = time.time()

        for images, labels in train_loader:
            images, labels = images.to(config.DEVICE), labels.to(config.DEVICE)
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * images.size(0)
            train_correct += (outputs.argmax(1) == labels).sum().item()
            train_total += images.size(0)

        model.eval()
        val_loss, val_correct, val_total = 0.0, 0, 0
        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(config.DEVICE), labels.to(config.DEVICE)
                outputs = model(images)
                loss = criterion(outputs, labels)
                val_loss += loss.item() * images.size(0)
                val_correct += (outputs.argmax(1) == labels).sum().item()
                val_total += images.size(0)

        train_acc = train_correct / train_total * 100
        val_acc = val_correct / val_total * 100
        avg_train_loss = train_loss / train_total
        avg_val_loss = val_loss / val_total
        elapsed = time.time() - t0

        print(f"Epoch {epoch+1:02d}/{NUM_EPOCHS}  "
              f"train_loss={avg_train_loss:.4f}  train_acc={train_acc:.2f}%  "
              f"val_loss={avg_val_loss:.4f}  val_acc={val_acc:.2f}%  "
              f"({elapsed:.0f}s)")

        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            best_val_acc = val_acc
            torch.save({
                "epoch": epoch + 1,
                "model_state_dict": model.state_dict(),
                "val_acc": val_acc,
                "val_loss": avg_val_loss,
                "class_names": class_names,
                "architecture": "efficientnet_b0",
            }, config.V8_MODEL_PATH)
            print(f"  --> Saved v8 checkpoint (val_acc={val_acc:.2f}%)")

    print(f"\nBest val_acc: {best_val_acc:.2f}%")
    print(f"v8 checkpoint: {config.V8_MODEL_PATH}")
    print(f"\nBaseline to beat (v6p2 MobileNetV2):")
    print(f"  PlantVillage: 95.44%  PlantDoc: 70.81%  PlantWild: 63.79%")
    print(f"\nNext: run finetune_phase2_effb0.py for phase 2, then evaluate all three datasets")


if __name__ == "__main__":
    main()
