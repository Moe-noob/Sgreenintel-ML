"""
Run the trained model on a single image file — for manual testing on
real-world photos, not just the PlantVillage test set.

OOD (out-of-distribution) rejection is applied by default: if the model
is not confident enough, or its probability distribution is too uncertain,
it returns a "please retake the photo" message rather than a wrong
confident answer.

Thresholds (calibrated empirically on known good/bad examples):
  confidence_threshold = 0.55   -- reject if top class probability < 55%
  entropy_norm_threshold = 0.40 -- reject if normalized entropy > 0.40
                                    (0 = fully certain, 1 = max uncertain)

To get raw predictions without OOD filtering (e.g. for debugging),
pass --no-ood flag.
"""

import sys
import math
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

MAX_ENTROPY = math.log(config.NUM_CLASSES)  # theoretical max for NUM_CLASSES classes

# OOD rejection thresholds -- calibrated empirically, not assumed
CONFIDENCE_THRESHOLD = 0.70
ENTROPY_NORM_THRESHOLD = 0.40

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


def predict(image_path, top_k=3, use_ood=True):
    """
    Runs inference on a single image.

    With use_ood=True (default): applies OOD rejection before returning
    a prediction. If the model is uncertain, prints a retake message
    instead of a potentially wrong confident answer.

    With use_ood=False: raw predictions, no filtering.
    """
    model_path = config.V4P2_MODEL_PATH if config.V4P2_MODEL_PATH.exists() else config.V4_MODEL_PATH
    checkpoint = torch.load(model_path, map_location=config.DEVICE)
    model = build_model(config.NUM_CLASSES)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    class_names = checkpoint["class_names"]

    image = Image.open(image_path).convert("RGB")
    input_tensor = predict_transform(image).unsqueeze(0).to(config.DEVICE)

    with torch.no_grad():
        outputs = model(input_tensor)
        probs = torch.softmax(outputs, dim=1)[0]

    max_conf = probs.max().item()
    entropy = -(probs * torch.log(probs + 1e-9)).sum().item()
    entropy_norm = entropy / MAX_ENTROPY

    top_probs, top_indices = torch.topk(probs, top_k)

    print(f"\nPredictions for: {image_path}")
    print(f"  Confidence: {max_conf*100:.1f}%  |  "
          f"Uncertainty: {entropy_norm:.3f} (0=certain, 1=max uncertain)\n")

    if use_ood:
        # OOD check -- reject before showing prediction
        if max_conf < CONFIDENCE_THRESHOLD:
            print(f"  ❌ LOW CONFIDENCE -- model is not certain enough to diagnose.")
            print(f"     Please retake the photo:")
            print(f"     • Single leaf filling the frame")
            print(f"     • Plain or simple background")
            print(f"     • Natural lighting, no filters")
            print(f"     • No hands or other objects in frame")
            return
        elif entropy_norm > ENTROPY_NORM_THRESHOLD:
            print(f"  ❌ HIGH UNCERTAINTY -- predictions are too spread across classes.")
            print(f"     Please retake the photo:")
            print(f"     • Single leaf filling the frame")
            print(f"     • Plain or simple background")
            print(f"     • Natural lighting, no filters")
            print(f"     • No hands or other objects in frame")
            return

    # Accepted -- show prediction
    predicted_class = class_names[top_indices[0].item()]
    print(f"  ✓ DIAGNOSIS: {predicted_class}  ({max_conf*100:.1f}%)\n")
    print(f"  Top {top_k} predictions:")
    for prob, idx in zip(top_probs, top_indices):
        print(f"    {class_names[idx]:55s}  {prob.item()*100:.2f}%")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("Usage: python training\\predict.py <path_to_image> [--no-ood]")
        sys.exit(1)

    image_path = args[0]
    use_ood = "--no-ood" not in args

    predict(image_path, use_ood=use_ood)