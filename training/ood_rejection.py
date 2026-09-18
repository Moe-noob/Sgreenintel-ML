"""
Out-of-distribution (OOD) rejection for SGreen Intel's plant disease CNN.

Uses two complementary signals from the existing model's output — no new
training, no new model required:

1. Max confidence (softmax probability of the top predicted class):
   Very low max confidence = model is uncertain = likely OOD.

2. Prediction entropy (Shannon entropy of the full softmax distribution):
   High entropy = flat distribution = model can't distinguish between classes.
   For a 35-class model, max possible entropy = ln(35) ≈ 3.56 bits.
   Low entropy = peaked distribution = model is confident (right or wrong).

The combination catches two distinct failure modes:
- Genuinely uncertain images (low confidence + high entropy): random objects,
  heavily occluded leaves, extreme blur.
- Confidently wrong images (high confidence + low entropy): this is the harder
  domain-gap case -- the model is sure but wrong. These are harder to reject
  with entropy alone; confidence alone doesn't help either. We document this
  honestly rather than pretending the threshold catches everything.

Threshold calibration: thresholds are calibrated empirically on known good
(PlantVillage test set) and known bad (real-world OOD) examples, not assumed.
"""

import sys
import math
import torch
import torch.nn as nn
from pathlib import Path
from torchvision import models, transforms
from PIL import Image

try:
    from . import config
except ImportError:
    import config

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD  = [0.229, 0.224, 0.225]

predict_transform = transforms.Compose([
    transforms.Resize((config.IMAGE_SIZE, config.IMAGE_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
])

MAX_ENTROPY_35_CLASS = math.log(35)  # 3.555 -- theoretical maximum for 35 classes


def build_and_load_model():
    model = models.mobilenet_v2(weights=None)
    num_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(num_features, config.NUM_CLASSES)
    model = model.to(config.DEVICE)
    checkpoint = torch.load(config.BEST_MODEL_PATH, map_location=config.DEVICE)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model, checkpoint["class_names"]


def compute_ood_signals(probs):
    """
    Given a softmax probability tensor [35], compute:
    - max_confidence: probability of the top class
    - entropy: Shannon entropy of the distribution (nats)
    - entropy_normalized: entropy as fraction of theoretical maximum [0, 1]
    """
    max_conf = probs.max().item()
    entropy = -(probs * torch.log(probs + 1e-9)).sum().item()
    entropy_norm = entropy / MAX_ENTROPY_35_CLASS
    return max_conf, entropy, entropy_norm


def predict_with_ood(image_path,
                     confidence_threshold=0.55,
                     entropy_norm_threshold=0.40,
                     top_k=3):
    """
    Runs the model and applies OOD rejection before returning a prediction.

    Rejection criteria (either triggers a rejection):
    - max_confidence < confidence_threshold: model too uncertain
    - entropy_normalized > entropy_norm_threshold: distribution too flat

    Returns a dict with:
      prediction, confidence, entropy, entropy_normalized,
      rejected (bool), rejection_reason, top_k_predictions
    """
    model, class_names = build_and_load_model()

    image = Image.open(image_path).convert("RGB")
    input_tensor = predict_transform(image).unsqueeze(0).to(config.DEVICE)

    with torch.no_grad():
        outputs = model(input_tensor)
        probs = torch.softmax(outputs, dim=1)[0]

    max_conf, entropy, entropy_norm = compute_ood_signals(probs)
    top_probs, top_indices = torch.topk(probs, top_k)

    predicted_idx = probs.argmax().item()
    predicted_class = class_names[predicted_idx]

    # OOD rejection check
    rejected = False
    rejection_reason = None

    if max_conf < confidence_threshold:
        rejected = True
        rejection_reason = (
            f"Low confidence ({max_conf*100:.1f}% < {confidence_threshold*100:.0f}% threshold). "
            f"The model cannot confidently identify the plant disease. "
            f"Please retake the photo: single leaf filling the frame, "
            f"plain background, natural lighting, no filters."
        )
    elif entropy_norm > entropy_norm_threshold:
        rejected = True
        rejection_reason = (
            f"High prediction uncertainty (entropy {entropy_norm:.2f} > {entropy_norm_threshold} threshold). "
            f"The model's probability is spread too evenly across classes. "
            f"Please retake the photo: single leaf filling the frame, "
            f"plain background, natural lighting, no filters."
        )

    return {
        "image": str(image_path),
        "predicted_class": predicted_class,
        "confidence": max_conf,
        "entropy": entropy,
        "entropy_normalized": entropy_norm,
        "rejected": rejected,
        "rejection_reason": rejection_reason,
        "top_k": [
            {"class": class_names[idx.item()], "confidence": prob.item()}
            for prob, idx in zip(top_probs, top_indices)
        ],
    }


def print_result(result):
    print(f"\nImage: {Path(result['image']).name}")
    print(f"  Max confidence:      {result['confidence']*100:.1f}%")
    print(f"  Entropy (raw):       {result['entropy']:.3f} / {MAX_ENTROPY_35_CLASS:.3f} max")
    print(f"  Entropy (normalized):{result['entropy_normalized']:.3f}  (0=certain, 1=max uncertain)")

    if result["rejected"]:
        print(f"\n  ❌ REJECTED -- {result['rejection_reason']}")
    else:
        print(f"\n  ✓ ACCEPTED: {result['predicted_class']}  ({result['confidence']*100:.1f}%)")
        print(f"  Top predictions:")
        for p in result["top_k"]:
            print(f"    {p['class']:55s}  {p['confidence']*100:.2f}%")


if __name__ == "__main__":
    """
    Calibration run: test on known good and known bad images to
    check whether the default thresholds work, before committing to them.
    """
    print("=== OOD Rejection Calibration ===")
    print(f"Max possible entropy for 35 classes: {MAX_ENTROPY_35_CLASS:.3f}\n")

    # Known good -- should be ACCEPTED
    good_images = [
        "data/processed_v2/test/Tomato___Late_blight/0ab1cab4-a0c9-4323-9a64-cdafa4342a9b___GHLB2 Leaf 8918.JPG",
        "test_images/corn_gray_1.jpg",
        "test_images/corn_gray_2.png",
        "test_images/corn_gray_3.png",
    ]

    # Known bad -- should be REJECTED
    bad_images = [
        "test_images/potato_early_blight_1.jfif",
        "test_images/potato_late_blight_1.jfif",
        "test_images/tomato_bacterial_spot_1.jfif",
        "test_images/grape_black_rot_1.jfif",
    ]

    print("--- KNOWN GOOD (expect: ACCEPTED) ---")
    for img in good_images:
        if Path(img).exists():
            result = predict_with_ood(img)
            print_result(result)

    print("\n--- KNOWN BAD (expect: REJECTED) ---")
    for img in bad_images:
        if Path(img).exists():
            result = predict_with_ood(img)
            print_result(result)