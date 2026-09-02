"""
Run the trained model on a single image file — for manual testing on
real-world photos, not just the PlantVillage test set.
"""

import sys
import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image

try:
    from . import config
except ImportError:
    import config

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

predict_transform = transforms.Compose([
    transforms.Resize((config.IMAGE_SIZE, config.IMAGE_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
])


def build_model(num_classes):
    model = models.mobilenet_v2(weights=None)
    num_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(num_features, num_classes)
    return model.to(config.DEVICE)


def predict(image_path, top_k=3):
    checkpoint = torch.load(config.BEST_MODEL_PATH, map_location=config.DEVICE)
    model = build_model(config.NUM_CLASSES)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    class_names = checkpoint["class_names"]

    image = Image.open(image_path).convert("RGB")
    input_tensor = predict_transform(image).unsqueeze(0).to(config.DEVICE)

    with torch.no_grad():
        outputs = model(input_tensor)
        probs = torch.softmax(outputs, dim=1)[0]

    top_probs, top_indices = torch.topk(probs, top_k)

    print(f"\nPredictions for: {image_path}\n")
    for prob, idx in zip(top_probs, top_indices):
        print(f"  {class_names[idx]:55s}  {prob.item()*100:.2f}%")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python training\\predict.py <path_to_image>")
        sys.exit(1)

    predict(sys.argv[1])