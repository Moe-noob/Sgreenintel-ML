"""
Phase 2 fine-tuning: loads the v4 checkpoint and continues training
at a lower learning rate (1e-5 vs 1e-4 in phase 1).

This is a standard technique to squeeze out the last few percentage
points when the model has already found a good region but needs finer
adjustment. Phase 1 (1e-4) does the heavy lifting; phase 2 (1e-5)
refines without overshooting.

Stops early if val_loss increases for 2 consecutive epochs (simple
early stopping to prevent overnight overfitting).

Saves as v4p2 checkpoint -- v4 stays intact for comparison.
"""

import time
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, WeightedRandomSampler, ConcatDataset, Dataset
from torchvision import models, transforms, datasets
from PIL import Image

try:
    from . import config
except ImportError:
    import config

# Reuse the same data sources as finetune_combined.py
from finetune_combined import (
    PLANTDOC_TRAIN_DIR, PLANTWILD_DIR, PLANTWILD_IMAGES_DIR, PLANTWILD_SPLIT_FILE,
    PLANTDOC_TO_OURS, PLANTWILD_TO_OURS,
    RealWorldDataset,
    build_plantdoc_samples, build_plantwild_samples,
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


def main():
    print("=== SGreen Intel v4 Phase 2: Lower LR continuation ===\n")
    print(f"Loading v4 checkpoint: {config.V4_MODEL_PATH}")

    checkpoint = torch.load(config.V4_MODEL_PATH, map_location=config.DEVICE)
    class_names = checkpoint["class_names"]
    class_to_idx = {name: i for i, name in enumerate(class_names)}

    print(f"Starting from epoch {checkpoint['epoch']}, "
          f"val_acc={checkpoint['val_acc']:.2f}%, "
          f"val_loss={checkpoint['val_loss']:.4f}\n")

    # Build model and load v4 weights
    model = models.mobilenet_v2(weights=None)
    num_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(num_features, len(class_names))
    model = model.to(config.DEVICE)
    model.load_state_dict(checkpoint["model_state_dict"])

    # Keep same layers unfrozen as phase 1
    for param in model.parameters():
        param.requires_grad = False
    for i in [15, 16, 17]:
        for param in model.features[i].parameters():
            param.requires_grad = True
    for param in model.classifier.parameters():
        param.requires_grad = True

    # Build datasets -- same as phase 1
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

    from dataset import get_class_weights
    weights_loss = get_class_weights(pv_dataset).to(config.DEVICE)
    criterion = nn.CrossEntropyLoss(weight=weights_loss)

    # Phase 2: 10x lower learning rate
    optimizer = torch.optim.Adam(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=1e-5
    )

    v4p2_path = config.MODEL_SAVE_DIR / "mobilenetv2_sgreenintel_v4p2.pth"

    NUM_EPOCHS = 5
    PATIENCE = 2  # stop if val_loss increases for 2 consecutive epochs
    best_val_loss = checkpoint["val_loss"]  # start from v4's best
    best_val_acc = checkpoint["val_acc"]
    patience_counter = 0

    print(f"Phase 2: {NUM_EPOCHS} epochs at lr=1e-5 "
          f"(early stop if val_loss increases {PATIENCE} times in a row)\n")

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
            patience_counter = 0
            torch.save({
                "epoch": f"v4p2-{epoch+1}",
                "model_state_dict": model.state_dict(),
                "val_acc": val_acc,
                "val_loss": avg_val_loss,
                "class_names": class_names,
            }, v4p2_path)
            print(f"  --> Saved v4p2 checkpoint (val_acc={val_acc:.2f}%)")
        else:
            patience_counter += 1
            print(f"  (no improvement, patience {patience_counter}/{PATIENCE})")
            if patience_counter >= PATIENCE:
                print(f"\nEarly stopping — val_loss hasn't improved for {PATIENCE} epochs.")
                break

    print(f"\nBest val_acc: {best_val_acc:.2f}%  (v4 was {checkpoint['val_acc']:.2f}%)")
    if v4p2_path.exists():
        improvement = best_val_acc - checkpoint['val_acc']
        print(f"Improvement over v4: {improvement:+.2f}pp")
        print(f"v4p2 checkpoint: {v4p2_path}")
        print(f"\nNext: run evalute.py and evaluate_plantdoc.py with V4P2_MODEL_PATH")
    else:
        print("No improvement over v4 -- use v4 as the final model.")


if __name__ == "__main__":
    main()
