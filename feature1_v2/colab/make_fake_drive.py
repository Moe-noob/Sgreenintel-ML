"""
Developer self-check only (you do NOT need this to train).

Builds a fake "Google Drive sgreen folder" with tiny synthetic datasets in
exactly the shape GUIDE.md asks the user to upload (the same zip names and
the same top-level folders a Windows/Mac "compress folder" produces), so
the Colab notebook can be executed end to end on a CPU with DRY_RUN = True:

    python -m feature1_v2.colab.make_fake_drive /tmp/fake_drive
    python -m feature1_v2.colab.dry_run        (builds the fake drive itself and runs the notebook)
"""

import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torchvision import models as tvm

from feature1_v2 import taxonomy

REPO = Path(__file__).resolve().parents[2]
PLANTWILD = {"cucumber leaf": (40, 160, 40), "cucumber powdery mildew": (200, 200, 200),
             "rice leaf": (180, 180, 40), "tomato late blight": (90, 60, 20), "tomato leaf": (20, 120, 20)}
PLANTDOC = {"Tomato leaf": (25, 125, 25), "Tomato leaf late blight": (95, 65, 25)}
LEGACY = {"Tomato___healthy": (15, 115, 15), "Tomato___Late_blight": (85, 55, 15)}


def _img(path, colour, rng):
    path.parent.mkdir(parents=True, exist_ok=True)
    a = np.clip(np.array(colour, float) + rng.normal(0, 25, (64, 64, 3)), 0, 255).astype("uint8")
    Image.fromarray(a).save(path, quality=90)


def _zip(folder, zip_path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(folder.rglob("*")):
            z.write(f, f.relative_to(folder.parent))        # keeps the top folder, like "Send to > Compressed folder"


def build(drive):
    drive = Path(drive)
    drive.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        # PlantWild: images/<class>/*.jpg + trainval.txt "<class>/<file>=<label>=<domain>" (0 test, 1 train, 2 val)
        pw = t / "plantwild" / "plantwild"
        lines = []
        for ci, c in enumerate(sorted(PLANTWILD)):
            for k in range(40):
                _img(pw / "images" / c / f"{k}.jpg", PLANTWILD[c], rng)
                lines.append(f"{c}/{k}.jpg={ci}={0 if k < 10 else 2 if k < 16 else 1}")
        (pw / "trainval.txt").write_text("\n".join(lines))
        _zip(t / "plantwild", drive / "plantwild.zip")
        # PlantDoc: train/<class>, test/<class>
        pd = t / "PlantDoc-Dataset"
        for c, col in PLANTDOC.items():
            for k in range(15):
                _img(pd / "train" / c / f"{k}.jpg", col, rng)
            for k in range(6):
                _img(pd / "test" / c / f"t{k}.jpg", col, rng)
        _zip(pd, drive / "PlantDoc-Dataset.zip")
        # processed_v2: lab PlantVillage-style files ('___' in the name)
        pv = t / "processed_v2"
        for c, col in LEGACY.items():
            for split, n in (("train", 20), ("val", 4), ("test", 4)):
                for k in range(n):
                    _img(pv / split / c / f"{k}___PV.jpg", col, rng)
        _zip(pv, drive / "processed_v2.zip")
    # v1 model file in v1's checkpoint format (random weights)
    m = tvm.mobilenet_v2(weights=None)
    m.classifier[1] = nn.Linear(m.classifier[1].in_features, 35)
    torch.save({"model_state_dict": m.state_dict(), "class_names": list(taxonomy.LEGACY_35)},
               drive / "mobilenetv2_sgreenintel_v6p2.pth")
    # code.zip like GitHub's "Download ZIP" (top folder <repo>-<branch>), from the working tree
    files = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=REPO,
                           capture_output=True, text=True, check=True).stdout.split()
    with zipfile.ZipFile(drive / "code.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            p = REPO / f
            if p.is_file() and p.suffix not in (".pdf", ".doc") and "/work/" not in f:
                z.write(p, f"Sgreenintel-ML-claude-compassionate-hopper-lh08ol/{f}")
    return sorted(p.name for p in drive.iterdir())


if __name__ == "__main__":
    print(build(sys.argv[1]))
