"""
Generates a grid of lat/lon points covering Saudi Arabia, used as the
basis for the suitability heatmap.

Starting at a coarse 2° x 2° resolution (~220km x ~220km cells) to get
the full pipeline working end-to-end quickly. Can be refined to a finer
resolution (e.g. 1°, matching NASA POWER's native 0.5° resolution) later
once the pipeline is validated — no need to build fine-grained here.

Saudi Arabia's approximate bounding box:
  Latitude:  16.0°N to 32.5°N
  Longitude: 34.5°E to 55.7°E

Note: this uses a simple rectangular bounding box, not the country's
actual border polygon. This means some generated grid cells will fall
outside Saudi Arabia (e.g. over the Red Sea, the Gulf, or neighboring
countries). This is a known, deliberate simplification to get the
pipeline working — precise border clipping (e.g. via a Saudi Arabia
boundary shapefile + point-in-polygon check) is a reasonable future
refinement, not needed for the current scope.
"""

import json
from pathlib import Path

# ---- Config ----
LAT_MIN, LAT_MAX = 16.0, 32.5
LON_MIN, LON_MAX = 34.5, 55.7
CELL_SIZE_DEGREES = 0.5

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "saudi_grid.json"


def generate_grid():
    """
    Generates grid cell centers. Each cell is identified by its center
    lat/lon, which is what we'll query NASA POWER with.
    """
    cells = []
    cell_id = 0

    lat = LAT_MIN
    while lat < LAT_MAX:
        lon = LON_MIN
        while lon < LON_MAX:
            center_lat = round(lat + CELL_SIZE_DEGREES / 2, 4)
            center_lon = round(lon + CELL_SIZE_DEGREES / 2, 4)

            cells.append({
                "cell_id": cell_id,
                "center_lat": center_lat,
                "center_lon": center_lon,
                "bounds": {
                    "lat_min": round(lat, 4),
                    "lat_max": round(lat + CELL_SIZE_DEGREES, 4),
                    "lon_min": round(lon, 4),
                    "lon_max": round(lon + CELL_SIZE_DEGREES, 4),
                },
            })

            cell_id += 1
            lon += CELL_SIZE_DEGREES
        lat += CELL_SIZE_DEGREES

    return cells


def main():
    cells = generate_grid()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(cells, f, indent=2)

    print(f"Generated {len(cells)} grid cells")
    print(f"Cell size: {CELL_SIZE_DEGREES}° x {CELL_SIZE_DEGREES}° (~{CELL_SIZE_DEGREES * 111:.0f}km x ~{CELL_SIZE_DEGREES * 111:.0f}km)")
    print(f"Saved to: {OUTPUT_PATH}")
    print(f"\nFirst cell: {cells[0]}")
    print(f"Last cell: {cells[-1]}")


if __name__ == "__main__":
    main()