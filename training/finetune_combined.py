"""
Fine-tunes the SGreen Intel 35-class CNN (v2 base) on a combined
real-world dataset: PlantDoc + PlantWild v1.

This supersedes the PlantDoc-only fine-tune (v3). Starting from v2
rather than v3 avoids stacking two sequential domain-shift fine-tunes.

Real-world training data:
  - PlantDoc train: ~1,400 images, 21 classes
  - PlantWild v1 train: 4,073 images, 25 classes (official split)
  - Combined: ~5,473 real-world images

Strategy: same as finetune_plantdoc.py --
  Unfreeze last 3 MobileNetV2 feature blocks + classifier
  Mix real-world images with PlantVillage using WeightedRandomSampler
  lr=1e-4, 7 epochs, save as v4 checkpoint

Citations:
  PlantDoc: Singh et al. (2020). CODS-COMAD 2020.
  PlantWild: Wei et al. (2024). arxiv 2408.03120.
"""

import time
from pathlib import Path
from collections import defaultdict

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, WeightedRandomSampler, Dataset
from torchvision import models, transforms, datasets
from PIL import Image

try:
    from . import config
except ImportError:
    import config

PLANTDOC_TRAIN_DIR = Path("data/raw/PlantDoc-Dataset/train")
PLANTWILD_DIR = Path("data/raw/plantwild/plantwild")
PLANTWILD_IMAGES_DIR = PLANTWILD_DIR / "images"
PLANTWILD_SPLIT_FILE = PLANTWILD_DIR / "trainval.txt"

# PlantDoc mapping (same as before)
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

# PlantWild mapping
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


class RealWorldDataset(Dataset):
    """Unified dataset for PlantDoc + PlantWild training images."""

    def __init__(self, samples, transform):
        self.samples = samples  # list of (image_path, class_idx)
        self.transform = transform

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        image = Image.open(path).convert("RGB")
        return self.transform(image), label


def build_plantdoc_samples(class_to_idx):
    samples = []
    for folder, our_class in PLANTDOC_TO_OURS.items():
        folder_path = PLANTDOC_TRAIN_DIR / folder
        if not folder_path.exists() or our_class not in class_to_idx:
            continue
        idx = class_to_idx[our_class]
        for ext in ['*.jpg', '*.JPG', '*.png', '*.jpeg']:
            for img in folder_path.glob(ext):
                samples.append((str(img), idx))
    print(f"PlantDoc train samples: {len(samples)}")
    return samples


def build_plantwild_samples(class_to_idx):
    """Uses the official PlantWild train split (split_idx=1 in trainval.txt)."""
    lines = PLANTWILD_SPLIT_FILE.read_text().splitlines()
    samples = []
    skipped = 0
    for line in lines:
        parts = line.strip().split('=')
        if len(parts) != 3:
            continue
        img_rel, class_idx_str, split_idx_str = parts
        if int(split_idx_str) != 1:  # 1 = train only
            continue
        class_name = img_rel.split('/')[0]
        if class_name not in PLANTWILD_TO_OURS:
            continue
        our_class = PLANTWILD_TO_OURS[class_name]
        if our_class not in class_to_idx:
            continue
        img_path = PLANTWILD_IMAGES_DIR / img_rel
        if not img_path.exists():
            skipped += 1
            continue
        samples.append((str(img_path), class_to_idx[our_class]))
    print(f"PlantWild train samples: {len(samples)} ({skipped} skipped - not extracted)")
    return samples


def build_model_for_finetuning(class_names):
    """Loads v2 checkpoint (not v3) and unfreezes last 3 blocks + classifier."""
    model = models.mobilenet_v2(weights=None)
    num_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(num_features, len(class_names))
    model = model.to(config.DEVICE)

    # Load v2, not v3 -- starting fresh from the PlantVillage-only base
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
    print(f"Base: v2 checkpoint. Trainable params: {trainable:,} / {total:,} ({trainable/total*100:.1f}%)")
    return model


def main():
    print("=== SGreen Intel v4: Fine-tuning on PlantDoc + PlantWild combined ===\n")

    checkpoint = torch.load(config.BEST_MODEL_PATH, map_location=config.DEVICE)
    class_names = checkpoint["class_names"]
    class_to_idx = {name: i for i, name in enumerate(class_names)}

    # Build real-world training samples
    plantdoc_samples = build_plantdoc_samples(class_to_idx)
    plantwild_samples = build_plantwild_samples(class_to_idx)
    all_real_world = plantdoc_samples + plantwild_samples
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

    # Combined dataset with weighted sampler
    # Real-world images get upsampled to appear ~40% of each batch
    rw_weight = len(pv_dataset) / len(real_world_dataset) * 0.67
    weights = [rw_weight] * len(real_world_dataset) + [1.0] * len(pv_dataset)

    from torch.utils.data import ConcatDataset
    combined = ConcatDataset([real_world_dataset, pv_dataset])
    sampler = WeightedRandomSampler(weights, num_samples=len(combined), replacement=True)
    train_loader = DataLoader(
        combined, batch_size=config.BATCH_SIZE,
        sampler=sampler, num_workers=4, pin_memory=True
    )

    # Validation: PlantVillage val set
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

    # v4 checkpoint path
    v4_path = config.V6_MODEL_PATH

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
            }, config.V6_MODEL_PATH)
            print(f"  --> Saved v6 checkpoint (val_acc={val_acc:.2f}%)")

    print(f"\nBest val_acc: {best_val_acc:.2f}%")
    print(f"v6 checkpoint: {config.V6_MODEL_PATH}")
    print(f"\nNext: run evalute.py, evaluate_plantdoc.py, evaluate_plantwild.py")
    print(f"with V6P2_MODEL_PATH after running finetune_phase2.py")


if __name__ == "__main__":
    main()