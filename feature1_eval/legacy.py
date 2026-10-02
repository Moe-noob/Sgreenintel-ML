"""
Adapter that runs the v1 production model (v6p2, MobileNetV2, 35 classes,
384 px) through the same evaluation pipeline, so the baseline
is measured on the same frozen benchmark.

v1 checkpoints store 'model_state_dict', 'class_names' and optionally
'architecture' (training/model_loader.py). v1 resizes to a square 384 x 384
with ImageNet normalisation (training/predict_api.py); the same is done here.
"""

import torch
import torch.nn as nn
from torchvision import models as tvm

from feature1_eval import taxonomy

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def load(path, map_location="cpu"):
    ck = torch.load(path, map_location=map_location, weights_only=False)
    arch = ck.get("architecture", "mobilenet_v2")
    names = ck["class_names"]
    if arch == "efficientnet_b0":
        m = tvm.efficientnet_b0(weights=None)
    else:
        m = tvm.mobilenet_v2(weights=None)
    m.classifier[1] = nn.Linear(m.classifier[1].in_features, len(names))
    m.load_state_dict(ck["model_state_dict"])
    m.eval()
    unified = [taxonomy.LEGACY_35[n] for n in names]
    meta = {"backbone": f"v1_{arch}", "img_size": 384, "mean": IMAGENET_MEAN, "std": IMAGENET_STD,
            "square_resize": True}
    return m, {"classes": unified, "meta": meta, "legacy_names": names}
