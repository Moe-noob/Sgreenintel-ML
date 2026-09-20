"""
Fine-tunes SGreen Intel v7: same as v6 (PlantDoc + PlantWild) but adds
a filtered subset of genuinely non-PlantVillage tomato images from the
Tomato Disease Multiple Sources dataset (Kaggle).

Filtering applied to tomato_multi:
  - Skip UUID-named files (PlantVillage-derived, ~71% of dataset)
  - Skip files with augmentation keywords in the name (_change, _mirror,
    _flip, _rot, _hight, _high, _low, _bright, _dark, _zoom, _noise, _blur)
  - Keep everything else as "genuine" non-PV images

This adds ~3,739 filtered tomato images across 9 classes to the training
mix alongside PlantDoc (3,542) and PlantWild (4,073).

Starting from v2 (not v6p2) to keep the experiment clean -- we're testing
whether targeted tomato data improves real-world performance, not stacking
on top of resolution changes.

Resolution: IMAGE_SIZE from config (currently 384px for v6/v7 experiments).
If you want a 320px v7, change IMAGE_SIZE to 320 in config.py first.

Saves as V7_MODEL_PATH. Run finetune_phase2.py after this to get v7p2.
"""

import re
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

from finetune_combined import (
    PLANTDOC_TRAIN_DIR, PLANTWILD_DIR, PLANTWILD_IMAGES_DIR, PLANTWILD_SPLIT_FILE,
    PLANTDOC_TO_OURS, PLANTWILD_TO_OURS,
    RealWorldDataset,
    build_plantdoc_samples, build_plantwild_samples,
)

TOMATO_MULTI_TRAIN = Path("data/raw/tomato_multi/train")

UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
)
AUG_KEYWORDS = [
    '_change', '_mirror', '_flip', '_rot', '_hight', '_high',
    '_low', '_bright', '_dark', '_zoom', '_noise', '_blur'
]

TOMATO_MULTI_TO_OURS = {
    "Bacterial_spot":                           "Tomato___Bacterial_spot",
    "Early_blight":                             "Tomato___Early_blight",
    "Late_blight":                              "Tomato___Late_blight",
    "Leaf_Mold":                                "Tomato___Leaf_Mold",
    "Septoria_leaf_spot":                       "Tomato___Septoria_leaf_spot",
    "Tomato_Yellow_Leaf_Curl_Virus":            "Tomato___Tomato_Yellow_Leaf_Curl_Virus",
    "Tomato_mosaic_virus":                      "Tomato___Tomato_mosaic_virus",
    "healthy":                                  "Tomato___healthy",
    # Spider_mites: only 6 genuine, skip
    # Target_Spot: 0 genuine, skip
}

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


def is_genuine(filename):
    """True if not UUID-named and not obviously augmented."""
    if UUID_PATTERN.match(filename):
        return False
    name_lower = Path(filename).stem.lower()
    if any(kw in name_lower for kw in AUG_KEYWORDS):
        return False
    return True


def build_tomato_multi_samples(class_to_idx):
    """Loads only genuine (non-UUID, non-augmented) images from tomato_multi."""
    samples = []
    skipped_aug = 0
    skipped_uuid = 0

    for folder, our_class in TOMATO_MULTI_TO_OURS.items():
        folder_path = TOMATO_MULTI_TRAIN / folder
        if not folder_path.exists() or our_class not in class_to_idx:
            continue
        idx = class_to_idx[our_class]
        for img in folder_path.glob("*.*"):
            if UUID_PATTERN.match(img.name):
                skipped_uuid += 1
            elif any(kw in img.stem.lower() for kw in AUG_KEYWORDS):
                skipped_aug += 1
            else:
                samples.append((str(img), idx))

    print(f"Tomato_multi genuine samples: {len(samples)} "
          f"(skipped {skipped_uuid} UUID, {skipped_aug} augmented)")
    return samples


def build_model_for_finetuning(class_names):
    """Loads v2 checkpoint, unfreezes last 3 feature blocks + classifier."""
    model = models.mobilenet_v2(weights=None)
    num_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(num_features, len(class_names))
    model = model.to(config.DEVICE)

    checkpoint = torch.load(config.BEST_MODEL_PATH, map_location=config.DEVICE)
    model.load_state_dict(checkpoint["model_state_dict"])

    for param in model.parameters():
        param.requires_grad = False
    for i in [15, 16, 17]:
        for param in model.features[i].parameters():
            param.requires_grad = True
    for param in model.classifier.parameters():
        param.requires_grad = True

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"Base: v2 checkpoint. Trainable: {trainable:,} / {total:,} "
          f"({trainable/total*100:.1f}%)")
    return model


def main():
    print("=== SGreen Intel v7: PlantDoc + PlantWild + filtered tomato_multi ===\n")

    checkpoint = torch.load(config.BEST_MODEL_PATH, map_location=config.DEVICE)
    class_names = checkpoint["class_names"]
    class_to_idx = {name: i for i, name in enumerate(class_names)}

    # Build all three real-world sources
    plantdoc_samples = build_plantdoc_samples(class_to_idx)
    plantwild_samples = build_plantwild_samples(class_to_idx)
    tomato_samples = build_tomato_multi_samples(class_to_idx)

    all_real_world = plantdoc_samples + plantwild_samples + tomato_samples
    print(f"Total real-world train samples: {len(all_real_world)}\n")

    real_world_dataset = RealWorldDataset(all_real_world, finetune_transform)

    # PlantVillage training set
    pv_train_dir = Path(config.DATA_DIR) / "train"
    pv_dataset = datasets.ImageFolder(str(pv_train_dir), transform=finetune_transform)
    pv_class_to_idx = {name: i for i, name in enumerate(class_names)}
    pv_dataset.class_to_idx = pv_class_to_idx
    pv_dataset.samples = [
        (path, pv_class_to_idx.get(Path(path).parent.name, 0))
        for path, _ in pv_dataset.samples
    ]
    print(f"PlantVillage train samples: {len(pv_dataset)}")

    # Weighted sampler: real-world images appear ~40% of each batch
    rw_weight = len(pv_dataset) / len(real_world_dataset) * 0.67
    weights = [rw_weight] * len(real_world_dataset) + [1.0] * len(pv_dataset)
    combined = ConcatDataset([real_world_dataset, pv_dataset])
    sampler = WeightedRandomSampler(weights, num_samples=len(combined),
                                    replacement=True)
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

    model = build_model_for_finetuning(class_names)

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

    print(f"\nFine-tuning for {NUM_EPOCHS} epochs...\n")

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
            }, config.V7_MODEL_PATH)
            print(f"  --> Saved v7 checkpoint (val_acc={val_acc:.2f}%)")

    print(f"\nBest val_acc: {best_val_acc:.2f}%")
    print(f"v7 checkpoint: {config.V7_MODEL_PATH}")
    print(f"\nNext: run finetune_phase2.py (update to load V7_MODEL_PATH, save V7P2)")
    print(f"Then evaluate all three datasets and compare against v6p2 baseline:")
    print(f"  v6p2: PV 95.44% / PlantDoc 70.81% / PlantWild 63.79%")


if __name__ == "__main__":
    main()
