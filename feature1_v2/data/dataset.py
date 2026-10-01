"""
Torch dataset, augmentation and sampling for Feature 1 v2 (plan, Step 3.2).

The augmentations target the difference between training photos and what
users actually send:
  - random framing      RandomResizedCrop with a wide scale range (leaf small or large in frame)
  - phone camera        white-balance shift, exposure (gamma), blur, JPEG re-compression
  - RandAugment         generic photometric/geometric variety
  - background swap     lab (PlantVillage) leaves pasted onto crops of real field photos,
                        so the model cannot learn "plain background = this class"
CutMix / label smoothing are applied per batch in train.py (timm Mixup).

Sampling: each training image is weighted so every class is drawn about
equally often and field photos FIELD_WEIGHT times more often than lab
photos, so the 50k lab images do not dominate the few thousand field ones.
"""

import io
import random
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageFilter
from torch.utils.data import Dataset, WeightedRandomSampler
from torchvision import transforms as T


class PhoneCamera:
    """White balance, exposure, blur and JPEG artefacts of everyday phone photos."""

    def __init__(self, p=0.8):
        self.p = p

    def __call__(self, img):
        if random.random() > self.p:
            return img
        a = np.asarray(img).astype(np.float32) / 255.0
        a *= np.array([random.uniform(0.85, 1.15) for _ in range(3)], dtype=np.float32)   # white balance
        a = np.clip(a, 0, 1) ** random.uniform(0.7, 1.4)                                    # exposure
        img = Image.fromarray((a * 255).astype(np.uint8))
        if random.random() < 0.3:
            img = img.filter(ImageFilter.GaussianBlur(random.uniform(0.3, 1.6)))
        if random.random() < 0.5:
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=random.randint(30, 90))
            img = Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
        return img


class BackgroundSwap:
    """
    For lab images only: estimate the plain background from the border colour,
    and replace it with a random crop of a real field photo.
    """

    def __init__(self, background_paths, p=0.5, tol=0.12):
        self.paths = list(background_paths)
        self.p, self.tol = p, tol

    def __call__(self, img):
        if not self.paths or random.random() > self.p:
            return img
        a = np.asarray(img).astype(np.float32) / 255.0
        border = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
        bg = np.median(border, axis=0)
        mask = (np.abs(a - bg).max(axis=2) < self.tol)          # True = background
        if mask.mean() < 0.1 or mask.mean() > 0.9:
            return img                                            # no clear plain background
        try:
            with Image.open(random.choice(self.paths)) as b:
                b = b.convert("RGB")
                w, h = img.size
                s = min(b.size)
                x, y = random.randint(0, b.size[0] - s), random.randint(0, b.size[1] - s)
                b = b.crop((x, y, x + s, y + s)).resize((w, h))
        except Exception:                                         # noqa: BLE001
            return img
        out = np.where(mask[..., None], np.asarray(b), np.asarray(img))
        return Image.fromarray(out.astype(np.uint8))


def train_transform(size, mean, std):
    return T.Compose([
        T.RandomResizedCrop(size, scale=(0.35, 1.0), ratio=(0.75, 1.33)),
        T.RandomHorizontalFlip(),
        T.RandomVerticalFlip(p=0.2),
        PhoneCamera(),
        T.RandAugment(num_ops=2, magnitude=7),
        T.ToTensor(),
        T.Normalize(mean, std),
    ])


def eval_transform(size, mean, std):
    return T.Compose([
        T.Resize(int(round(size * 1.14))),
        T.CenterCrop(size),
        T.ToTensor(),
        T.Normalize(mean, std),
    ])


class RowsDataset(Dataset):
    """rows: split rows (path, label, domain, ...); paths relative to data_root."""

    def __init__(self, rows, data_root, class_to_idx, transform, background_swap=None):
        self.rows = [r for r in rows if r["label"] in class_to_idx]
        self.root = Path(data_root)
        self.c2i = class_to_idx
        self.t = transform
        self.bg = background_swap

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        r = self.rows[i]
        try:
            img = Image.open(self.root / r["path"]).convert("RGB")
        except Exception:                                         # noqa: BLE001 -- corrupt file
            img = Image.new("RGB", (256, 256))
        if self.bg is not None and r.get("domain") == "lab":
            img = self.bg(img)
        return self.t(img), self.c2i[r["label"]]


def sample_weights(rows, field_weight=3.0):
    """Class-balanced weights, with field photos field_weight x more likely than lab photos."""
    per_class = Counter(r["label"] for r in rows)
    per_class_domain = Counter((r["label"], r.get("domain", "field")) for r in rows)
    w = []
    for r in rows:
        dom = r.get("domain", "field")
        dom_w = field_weight if dom == "field" else 1.0
        # share of the class's draws given to this domain, then spread over its images
        f_n, l_n = per_class_domain[(r["label"], "field")], per_class_domain[(r["label"], "lab")]
        denom = (field_weight * (f_n > 0) + 1.0 * (l_n > 0)) or 1.0
        w.append((dom_w / denom) / per_class_domain[(r["label"], dom)] / len(per_class))
    return torch.tensor(w, dtype=torch.double)


def balanced_sampler(rows, field_weight=3.0, epoch_size=None):
    w = sample_weights(rows, field_weight)
    return WeightedRandomSampler(w, num_samples=epoch_size or len(rows), replacement=True)
