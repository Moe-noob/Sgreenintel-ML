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

# The 7 production crops, as they appear before "___" in class_names (training/config.py: NUM_CLASSES = 35, 7 crops).
# Built once a model is loaded, not hard-coded, so it can never drift from the checkpoint's own class list.
CROP_CLASS_INDICES = None   # dict[str, list[int]], lower-case crop name -> indices into class_names; set by _get_model()


def _build_crop_index(class_names):
    groups = {}
    for i, name in enumerate(class_names):
        crop = name.split("___")[0].lower()
        groups.setdefault(crop, []).append(i)
    return groups


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
    global CROP_CLASS_INDICES
    if _cached_model is None:
        _cached_model, _cached_class_names, _ = load_best_model()
        CROP_CLASS_INDICES = _build_crop_index(_cached_class_names)
    return _cached_model, _cached_class_names


def available_crops():
    """The crop names predict_structured(..., crop=...) accepts, in a stable (class-list) order."""
    _get_model()
    return list(CROP_CLASS_INDICES)


def predict_structured(image_path, top_k=3, crop=None):
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

    crop: optional crop name (case-insensitive, e.g. "Tomato"). When given, only that crop's classes compete: a photo's
    probabilities are computed among its own disease/healthy classes only, instead of against all 35 classes, and the
    acceptance rule is judged against that narrower class count. Raises ValueError for a name the model does not know.
    """
    model, class_names = _get_model()
    crop_key = None
    if crop is not None:
        crop_key = crop.strip().lower()
        if crop_key not in CROP_CLASS_INDICES:
            raise ValueError(f"Unknown crop {crop!r}. Known crops: {', '.join(sorted(CROP_CLASS_INDICES))}")

    image = Image.open(image_path).convert("RGB")
    input_tensor = predict_transform(image).unsqueeze(0).to(config.DEVICE)

    with torch.no_grad():
        outputs = model(input_tensor)
        if crop_key is not None:
            mask = torch.full_like(outputs, float("-inf"))
            idx = torch.tensor(CROP_CLASS_INDICES[crop_key], device=outputs.device)
            mask[:, idx] = outputs[:, idx]
            outputs = mask
        probs = torch.softmax(outputs, dim=1)[0]

    n_classes_considered = len(CROP_CLASS_INDICES[crop_key]) if crop_key is not None else config.NUM_CLASSES
    max_entropy = math.log(n_classes_considered) if n_classes_considered > 1 else 1.0   # a single-class crop has no entropy to speak of
    max_conf = probs.max().item()
    entropy = -(probs * torch.log(probs + 1e-9)).sum().item()
    entropy_norm = entropy / max_entropy

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
            "crop_given": crop_key,
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
        "crop_given": crop_key,
    }