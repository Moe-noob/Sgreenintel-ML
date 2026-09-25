"""
Copies a random sample of NON-UUID-named images from tomato_multi into a
temp inspection folder, so we can visually judge whether they're genuinely
different from PlantVillage (real field photos, other sources) or just more
PlantVillage-style lab images / augmentations.

UUID-named files follow PlantVillage's convention and are skipped -- we only
want to see the "other source" images that might add real-world diversity.

Output: data/raw/tomato_multi_inspect/<class>/ with ~20 sampled images each.
Open these in Windows photo viewer to assess.
"""

import re
import random
import shutil
from pathlib import Path

random.seed(42)

SRC = Path("data/raw/tomato_multi/train")
DST = Path("data/raw/tomato_multi_inspect")
SAMPLES_PER_CLASS = 20

uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')

# Focus on the classes that are struggling on real-world data
PRIORITY_CLASSES = [
    "Bacterial_spot",
    "Septoria_leaf_spot",
    "Late_blight",
    "Early_blight",
    "Leaf_Mold",
    "Tomato_mosaic_virus",
    "Tomato_Yellow_Leaf_Curl_Virus",
    "powdery_mildew",
    "healthy",
]

if DST.exists():
    shutil.rmtree(DST)
DST.mkdir(parents=True)

print("Sampling non-UUID (non-PlantVillage) images for visual inspection...\n")

for cls in PRIORITY_CLASSES:
    src_dir = SRC / cls
    if not src_dir.exists():
        print(f"  {cls}: folder not found, skipping")
        continue

    # Collect only non-UUID-named images
    non_uuid = [img for img in src_dir.glob("*.*")
                if not uuid_pattern.match(img.name)]

    if not non_uuid:
        print(f"  {cls}: no non-UUID images")
        continue

    sample = random.sample(non_uuid, min(SAMPLES_PER_CLASS, len(non_uuid)))
    dst_dir = DST / cls
    dst_dir.mkdir(parents=True)
    for img in sample:
        # Prefix with a counter so they sort nicely in the viewer
        shutil.copy2(img, dst_dir / img.name)

    print(f"  {cls}: copied {len(sample)} of {len(non_uuid)} non-UUID images")

print(f"\nDone. Open the folders in:")
print(f"  {DST.resolve()}")
print(f"\nWhat to look for in each class:")
print(f"  - Plain background + single leaf + even lighting = PlantVillage-style (not useful)")
print(f"  - Field background, hands, multiple leaves, varied lighting = real-world (useful!)")
print(f"  - Obvious flips/rotations/color shifts of the same leaf = augmentation (not useful)")
