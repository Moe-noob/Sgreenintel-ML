import json
from pathlib import Path

GEO_DIR = Path(__file__).resolve().parent.parent / "data" / "geo"

border_path = GEO_DIR / "national_border"
regions_path = GEO_DIR / "GeoJSON-of-Saudi-Arabia-Regions" / "data" / "SA_regions.json"

print("Checking national border folder contents:")
if border_path.exists():
    for f in border_path.iterdir():
        print(f"  {f.name}")
else:
    print("  NOT FOUND at expected path:", border_path)

print("\nChecking regions file:")
if regions_path.exists():
    with open(regions_path) as f:
        regions = json.load(f)
    print(f"  Loaded OK. Type: {regions.get('type')}")
    print(f"  Number of features: {len(regions['features'])}")
    print(f"  First feature's properties: {regions['features'][0]['properties']}")
else:
    print("  NOT FOUND at expected path:", regions_path)