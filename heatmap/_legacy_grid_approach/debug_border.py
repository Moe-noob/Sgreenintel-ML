import json
from pathlib import Path
from shapely.geometry import shape, Point
from shapely.ops import unary_union

BORDER_PATH = Path(__file__).resolve().parent.parent / "data" / "geo" / "national_border" / "SAU-geo.json"

with open(BORDER_PATH) as f:
    border_geojson = json.load(f)

print("Top-level type:", border_geojson.get("type"))
print("Number of features:", len(border_geojson.get("features", [border_geojson])))

all_geoms = []
for i, feature in enumerate(border_geojson.get("features", [border_geojson])):
    geom = shape(feature["geometry"] if "geometry" in feature else feature)
    all_geoms.append(geom)
    print(f"  Feature {i}: type={geom.geom_type}, bounds={geom.bounds}")

# Merge everything into one shape
merged = unary_union(all_geoms)
print(f"\nMerged shape type: {merged.geom_type}")
print(f"Merged bounds: {merged.bounds}")

test_points = {
    "Riyadh": (24.71, 46.68),
    "Jeddah": (21.54, 39.17),
    "Najran": (17.49, 44.13),
}
for city, (lat, lon) in test_points.items():
    point = Point(lon, lat)
    print(f"{city} inside merged polygon: {merged.contains(point)}")