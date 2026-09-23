"""
API-facing prediction function -- same model loading and OOD rejection
logic as predict.py's CLI version, but returns a JSON-serializable dict
instead of printing to the terminal.

Keeping this separate from predict.py means the CLI tool (predict.py)
stays untouched and still works exactly as before for local testing.
"""

import math
import torch
from PIL import Image
from torchvision import transforms

try:
    from . import config
except ImportError:
    import config

from model_loader import load_best_model

import sys
sys.path.insert(0, str(config.PROJECT_ROOT / "care"))
from care_profiles import get_care_info

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

MAX_ENTROPY = math.log(config.NUM_CLASSES)
CONFIDENCE_THRESHOLD = 0.70
ENTROPY_NORM_THRESHOLD = 0.40   

predict_transform = transforms.Compose([
    transforms.Resize((config.IMAGE_SIZE, config.IMAGE_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
])

# Cache the model across requests -- loading it fresh on every API call
# would be slow and pointless since the weights never change between calls.
_cached_model = None
_cached_class_names = None


def _get_model():
    global _cached_model, _cached_class_names
    if _cached_model is None:
        _cached_model, _cached_class_names, _ = load_best_model()
    return _cached_model, _cached_class_names


def predict_structured(image_path, top_k=3):
    """
    Runs inference and returns a JSON-ready dict:

    {
        "accepted": bool,
        "prediction": str | None,           # e.g. "Tomato___Late_blight"
        "crop": str | None,                 # e.g. "Tomato"
        "condition": str | None,            # e.g. "Late blight"
        "confidence": float,                # 0-100
        "uncertainty": float,                # 0-1, normalized entropy
        "rejection_reason": str | None,
        "top_k": [{"class": str, "confidence": float}, ...]
    }
    """
    model, class_names = _get_model()

    image = Image.open(image_path).convert("RGB")
    input_tensor = predict_transform(image).unsqueeze(0).to(config.DEVICE)

    with torch.no_grad():
        outputs = model(input_tensor)
        probs = torch.softmax(outputs, dim=1)[0]

    max_conf = probs.max().item()
    entropy = -(probs * torch.log(probs + 1e-9)).sum().item()
    entropy_norm = entropy / MAX_ENTROPY

    top_probs, top_indices = torch.topk(probs, top_k)
    top_k_list = [
        {"class": class_names[idx.item()], "confidence": round(prob.item() * 100, 2)}
        for prob, idx in zip(top_probs, top_indices)
    ]

    # OOD rejection check -- same thresholds as predict.py CLI
    rejected = False
    rejection_reason = None

    if max_conf < CONFIDENCE_THRESHOLD:
        rejected = True
        rejection_reason = (
            f"Low confidence ({max_conf*100:.1f}%). The model cannot confidently "
            f"diagnose this image. Please retake the photo: single leaf filling "
            f"the frame, plain background, natural lighting, no filters."
        )
    elif entropy_norm > ENTROPY_NORM_THRESHOLD:
        rejected = True
        rejection_reason = (
            f"High uncertainty (predictions too spread across classes). "
            f"Please retake the photo: single leaf filling the frame, "
            f"plain background, natural lighting, no filters."
        )

    if rejected:
        return {
            "accepted": False,
            "prediction": None,
            "crop": None,
            "condition": None,
            "confidence": round(max_conf * 100, 2),
            "uncertainty": round(entropy_norm, 3),
            "rejection_reason": rejection_reason,
            "top_k": top_k_list,
        }

    predicted_class = class_names[top_indices[0].item()]
    # Split "Tomato___Late_blight" into crop + condition for cleaner display
    parts = predicted_class.split("___")
    crop = parts[0].replace("_", " ") if len(parts) == 2 else predicted_class
    condition = parts[1].replace("_", " ") if len(parts) == 2 else ""

    try:
        care = get_care_info(predicted_class)
    except ValueError:
        care = None

    return {
        "accepted": True,
        "prediction": predicted_class,
        "crop": crop,
        "condition": condition,
        "category_label": care["category_label"] if care else None,
        "management": care["management"] if care else None,
        "specific_note": care["specific_note"] if care else None,
        "baseline_care": care["baseline_care"] if care else None,
        "confidence": round(max_conf * 100, 2),
        "uncertainty": round(entropy_norm, 3),
        "rejection_reason": None,
        "top_k": top_k_list,
    }