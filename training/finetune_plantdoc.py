"""
Fine-tunes the SGreen Intel 35-class CNN (v2, PlantVillage-trained) on
PlantDoc real-world field images to reduce the domain gap.

Strategy:
- Freeze all backbone layers except the last 3 feature blocks + classifier
- Mix PlantDoc training images with our existing processed_v2 data using
  WeightedRandomSampler to oversample PlantDoc (otherwise the model just
  sees mostly PlantVillage images and barely learns from PlantDoc)
- Low learning rate (1e-4) to avoid overwriting PlantVillage knowledge
- Save as v3 checkpoint -- v2 stays intact for comparison

Expected outcome: PlantDoc accuracy improves from ~13% to ~30-50%.
PlantVillage test accuracy may drop slightly (2-5pp) -- acceptable tradeoff.
Both are re-evaluated after fine-tuning.

PlantDoc citation: Singh et al. (2020). CODS-COMAD 2020.
"""

import sys
import time
from pathlib import Path
from collections import defaultdict

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, WeightedRandomSampler, ConcatDataset
from torchvision import models, transforms, datasets

try:
    from . import config
except ImportError:
    import config

PLANTDOC_TRAIN_DIR = Path("data/raw/PlantDoc-Dataset/train")

# Same mapping as evaluate_plantdoc.py
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

# More aggressive augmentation for fine-tuning on real-world images
# Note: color jitter is mild -- disease symptoms are color-based
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


def build_plantdoc_dataset(class_names):
    """
    Builds a dataset from PlantDoc training images, mapping PlantDoc
    folder names to our class indices.
    """
    class_to_idx = {name: i for i, name in enumerate(class_names)}
    samples = []

    for plantdoc_folder, our_class in PLANTDOC_TO_OURS.items():
        folder_path = PLANTDOC_TRAIN_DIR / plantdoc_folder
        if not folder_path.exists() or our_class not in class_to_idx:
            continue
        idx = class_to_idx[our_class]
        images = list(folder_path.glob("*.jpg")) + \
                 list(folder_path.glob("*.JPG")) + \
                 list(folder_path.glob("*.png")) + \
                 list(folder_path.glob("*.jpeg"))
        for img in images:
            samples.append((str(img), idx))

    print(f"PlantDoc training samples: {len(samples)} across {len(PLANTDOC_TO_OURS)} classes")
    return samples


class MixedDataset(torch.utils.data.Dataset):
    """Combines PlantDoc samples + PlantVillage processed_v2 samples."""

    def __init__(self, plantdoc_samples, plantvillage_dataset, transform):
        self.transform = transform
        # PlantDoc samples: list of (path_str, class_idx)
        self.plantdoc = plantdoc_samples
        # PlantVillage dataset (torchvision ImageFolder)
        self.plantvillage = plantvillage_dataset
        self.plantdoc_len = len(plantdoc_samples)
        self.pv_len = len(plantvillage_dataset)

    def __len__(self):
        return self.plantdoc_len + self.pv_len

    def __getitem__(self, idx):
        from PIL import Image
        if idx < self.plantdoc_len:
            path, label = self.plantdoc[idx]
            image = Image.open(path).convert("RGB")
            return self.transform(image), label
        else:
            image, label = self.plantvillage[idx - self.plantdoc_len]
            return image, label


def build_model_for_finetuning(class_names, device):
    """
    Loads v2 checkpoint and freezes everything except the last 3
    feature blocks + classifier.
    """
    model = models.mobilenet_v2(weights=None)
    num_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(num_features, len(class_names))
    model = model.to(device)

    checkpoint = torch.load(config.BEST_MODEL_PATH, map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])

    # Freeze everything first
    for param in model.parameters():
        param.requires_grad = False

    # Unfreeze last 3 feature blocks (indices 15, 16, 17) + classifier
    # MobileNetV2 has 19 feature blocks (0-18)
    for i in [15, 16, 17]:
        for param in model.features[i].parameters():
            param.requires_grad = True
    for param in model.classifier.parameters():
        param.requires_grad = True

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"Trainable params: {trainable:,} / {total:,} ({trainable/total*100:.1f}%)")

    return model


def build_weighted_sampler(mixed_dataset, plantdoc_len, pv_len):
    """
    Oversamples PlantDoc images so they appear ~50% of each batch,
    despite being a small fraction of the combined dataset.
    """
    # PlantDoc images get weight = pv_len/plantdoc_len (upsampled)
    # PlantVillage images get weight = 1.0 (baseline)
    pd_weight = pv_len / plantdoc_len
    weights = [pd_weight] * plantdoc_len + [1.0] * pv_len
    return WeightedRandomSampler(weights, num_samples=len(mixed_dataset), replacement=True)


def main():
    print("=== SGreen Intel v3: Fine-tuning on PlantDoc ===\n")

    # Load class names from v2 checkpoint
    checkpoint = torch.load(config.BEST_MODEL_PATH, map_location=config.DEVICE)
    class_names = checkpoint["class_names"]

    # Build PlantDoc training samples
    plantdoc_samples = build_plantdoc_dataset(class_names)

    # Build PlantVillage training dataset (reuse processed_v2)
    pv_train_dir = Path(config.DATA_DIR) / "train"
    pv_dataset = datasets.ImageFolder(
        str(pv_train_dir),
        transform=finetune_transform
    )
    # Remap PlantVillage class indices to match our checkpoint's class order
    pv_class_to_idx = {name: i for i, name in enumerate(class_names)}
    pv_dataset.class_to_idx = pv_class_to_idx
    pv_dataset.samples = [(path, pv_class_to_idx.get(
        Path(path).parent.name, 0)) for path, _ in pv_dataset.samples]

    print(f"PlantVillage training samples: {len(pv_dataset)}")

    # Build mixed dataset and weighted sampler
    mixed = MixedDataset(plantdoc_samples, pv_dataset, finetune_transform)
    sampler = build_weighted_sampler(mixed, len(plantdoc_samples), len(pv_dataset))
    train_loader = DataLoader(mixed, batch_size=config.BATCH_SIZE,
                              sampler=sampler, num_workers=4, pin_memory=True)

    # Validation: PlantVillage val set only (quick check per epoch)
    pv_val_dir = Path(config.DATA_DIR) / "val"
    val_dataset = datasets.ImageFolder(str(pv_val_dir), transform=val_transform)
    val_loader = DataLoader(val_dataset, batch_size=config.BATCH_SIZE,
                            shuffle=False, num_workers=4, pin_memory=True)

    # Build model
    model = build_model_for_finetuning(class_names, config.DEVICE)

    # Loss: class-weighted same as original training
    from dataset import get_class_weights
    weights = get_class_weights(pv_dataset).to(config.DEVICE)
    criterion = nn.CrossEntropyLoss(weight=weights)

    # Low learning rate -- critical for fine-tuning
    optimizer = torch.optim.Adam(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=1e-4
    )

    NUM_EPOCHS = 7
    best_val_acc = 0.0
    best_val_loss = float("inf")

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

        # Validation
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
            }, config.FINETUNE_MODEL_PATH)
            print(f"  --> Saved v3 checkpoint (val_acc={val_acc:.2f}%)")

    print(f"\nBest val_acc: {best_val_acc:.2f}%")
    print(f"Checkpoint saved: {config.FINETUNE_MODEL_PATH}")
    print(f"\nNext step: run evaluate_plantdoc.py with BEST_MODEL_PATH = FINETUNE_MODEL_PATH")
    print(f"to compare v3 PlantDoc accuracy against v2's 12.97%")


if __name__ == "__main__":
    main()