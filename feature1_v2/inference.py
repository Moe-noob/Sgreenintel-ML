"""
Shared inference helpers: batched logits with optional test-time
augmentation, temperature-scaled probabilities, crop restriction and
multi-photo aggregation (plan, Steps 2 and 3.4-3.5).
"""

import numpy as np
import torch
from PIL import Image

from torchvision import transforms as T

from feature1_v2 import taxonomy
from feature1_v2.data.dataset import eval_transform


def transform_for(meta):
    """v2 models: resize + centre crop. v1 (legacy) models: square resize, as v1 did."""
    if meta.get("square_resize"):
        s = meta["img_size"]
        return T.Compose([T.Resize((s, s)), T.ToTensor(), T.Normalize(meta["mean"], meta["std"])])
    return eval_transform(meta["img_size"], meta["mean"], meta["std"])


def device():
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


@torch.no_grad()
def logits_for_images(model, images, meta, tta=False, batch_size=32):
    """images: list of PIL images. Returns float32 numpy (n, classes)."""
    dev = next(model.parameters()).device
    t = transform_for(meta)
    out = []
    for i in range(0, len(images), batch_size):
        x = torch.stack([t(im.convert("RGB")) for im in images[i:i + batch_size]]).to(dev)
        if tta:
            views = [x, torch.flip(x, dims=[3]), torch.flip(x, dims=[2])]
            # average log-probabilities over views (more robust than averaging raw logits)
            lp = torch.stack([torch.log_softmax(model(v).float(), 1) for v in views]).mean(0)
            out.append(lp.cpu().numpy())
        else:
            out.append(model(x).float().cpu().numpy())
    return np.concatenate(out) if out else np.zeros((0, 0), np.float32)


@torch.no_grad()
def logits_for_paths(model, paths, meta, tta=False, batch_size=32):
    images = []
    for p in paths:
        try:
            images.append(Image.open(p).convert("RGB"))
        except Exception:                                    # noqa: BLE001
            images.append(Image.new("RGB", (256, 256)))
    return logits_for_images(model, images, meta, tta, batch_size)


def softmax(z, temperature=1.0, axis=-1):
    z = np.asarray(z, dtype=np.float64) / temperature
    z = z - z.max(axis=axis, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=axis, keepdims=True)


def energy(z, temperature=1.0):
    """Energy score (Liu et al. 2020): lower = more in-distribution. -T * logsumexp(z / T)."""
    z = np.asarray(z, dtype=np.float64) / temperature
    m = z.max(axis=-1)
    return -temperature * (m + np.log(np.exp(z - m[..., None]).sum(axis=-1)))


def crop_mask(classes, crop):
    """Boolean mask of the classes that belong to `crop` (unsupported is never in a crop)."""
    return np.array([taxonomy.crop_of(c) == crop for c in classes])


def restrict_to_crop(logits, classes, crop):
    """Set logits of other crops' classes to -inf, so prediction is among this crop's conditions."""
    if crop is None:
        return np.asarray(logits, dtype=np.float64)
    m = crop_mask(classes, crop)
    if not m.any():
        raise ValueError(f"crop '{crop}' has no classes in this model")
    z = np.array(logits, dtype=np.float64, copy=True)
    z[..., ~m] = -np.inf
    return z


def aggregate_photos(logits, temperature=1.0):
    """
    Several photos of the same plant -> one prediction: average log-probabilities
    (product of per-photo probabilities, renormalised). Returns probabilities.
    """
    lp = np.log(np.clip(softmax(logits, temperature), 1e-12, 1.0)).mean(axis=0)
    return softmax(lp)
