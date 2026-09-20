"""
Architecture-aware model loader.
Reads the 'architecture' key saved in every checkpoint and builds
the correct model before loading weights. This means evaluation and
inference scripts never need to know which architecture a checkpoint
uses -- they just call load_model_from_checkpoint().

Supported architectures:
  'mobilenet_v2'   -- default for all pre-v8 checkpoints
  'efficientnet_b0' -- v8 and later
"""

import torch
import torch.nn as nn
from torchvision import models

try:
    from . import config
except ImportError:
    import config


def build_model(architecture, num_classes):
    """Builds the right model structure for the given architecture string."""
    if architecture == "efficientnet_b0":
        model = models.efficientnet_b0(weights=None)
        in_features = model.classifier[1].in_features
        model.classifier[1] = nn.Linear(in_features, num_classes)
    else:
        # Default: mobilenet_v2 (covers all pre-v8 checkpoints which have
        # no 'architecture' key, so checkpoint.get() returns 'mobilenet_v2')
        model = models.mobilenet_v2(weights=None)
        num_features = model.classifier[1].in_features
        model.classifier[1] = nn.Linear(num_features, num_classes)
    return model.to(config.DEVICE)


def load_model_from_checkpoint(checkpoint_path):
    """
    Loads a checkpoint and returns (model, class_names).
    Automatically detects architecture from the checkpoint dict.
    Works for all model versions (v2 through v8+).
    """
    checkpoint = torch.load(checkpoint_path, map_location=config.DEVICE)
    arch = checkpoint.get("architecture", "mobilenet_v2")
    model = build_model(arch, config.NUM_CLASSES)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model, checkpoint["class_names"]


def get_best_checkpoint_path():
    """
    Returns the path to the best available checkpoint,
    checking from newest to oldest.
    """
    candidates = [
        config.V8P2_MODEL_PATH,
        config.V8_MODEL_PATH,
        config.V7P2_MODEL_PATH,
        config.V7_MODEL_PATH,
        config.V6P2_MODEL_PATH,
        config.V6_MODEL_PATH,
        config.V5P2_MODEL_PATH,
        config.V4P2_MODEL_PATH,
        config.V4_MODEL_PATH,
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError("No model checkpoint found in models/cnn/")


def load_best_model():
    """
    Loads the best available checkpoint automatically.
    Returns (model, class_names, checkpoint_path).
    """
    path = get_best_checkpoint_path()
    print(f"Using model: {path.name}")
    model, class_names = load_model_from_checkpoint(path)
    return model, class_names, path