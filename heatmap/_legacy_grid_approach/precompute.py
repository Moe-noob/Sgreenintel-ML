"""
Batch job: for every grid cell, fetches NASA POWER climate data, computes
ET0 (Hargreaves-Samani) and ETc (FAO-56 crop water requirement) for all
6 crops, for all 12 months. Results are cached to disk incrementally —
safe to interrupt and rerun without losing progress or re-hitting the
API for cells already completed.
"""

import json
import time
from pathlib import Path

from nasa_power import fetch_climate_data
from evapotranspiration import hargreaves_et0
from crop_coefficients import CROP_COEFFICIENTS, calculate_etc

GRID_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "saudi_grid.json"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "heatmap_results.json"

REQUEST_DELAY_SECONDS = 1.0  # be polite to NASA POWER's free API
SAVE_EVERY_N_CELLS = 5       # incremental checkpoint, in case of interruption


def load_grid():
    with open(GRID_PATH) as f:
        return json.load(f)


def load_existing_results():
    """Resume support: load whatever's already been computed."""
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH) as f:
            return json.load(f)
    return {}


def save_results(results):
    with open(OUTPUT_PATH, "w") as f:
        json.dump(results, f, indent=2)


def process_cell(cell):
    """
    Fetches climate + computes ET0/ETc for one grid cell, all 12 months,
    all 6 crops.
    """
    lat, lon = cell["center_lat"], cell["center_lon"]
    climate = fetch_climate_data(lat, lon)

    monthly_results = {}
    for month, values in climate.items():
        et0 = hargreaves_et0(
            temp_mean_c=values["temp_c"],
            temp_max_c=values["temp_max_c"],
            temp_min_c=values["temp_min_c"],
            latitude_deg=lat,
            month=month,
        )

        crop_results = {}
        for crop in CROP_COEFFICIENTS:
            etc, kc_adj = calculate_etc(
                et0, crop, values["wind_speed_ms"], values["humidity_pct"]
            )
            crop_results[crop] = {
                "kc_adjusted": round(kc_adj, 3),
                "etc_mm_day": round(etc, 2),
            }

        monthly_results[month] = {
            "et0_mm_day": round(et0, 2),
            "climate": {
                "temp_c": values["temp_c"],
                "temp_max_c": values["temp_max_c"],
                "temp_min_c": values["temp_min_c"],
                "humidity_pct": values["humidity_pct"],
                "wind_speed_ms": values["wind_speed_ms"],
                "precip_mm_day": values["precip_mm_day"],
            },
            "crops": crop_results,
        }

    return {
        "cell_id": cell["cell_id"],
        "center_lat": lat,
        "center_lon": lon,
        "bounds": cell["bounds"],
        "monthly": monthly_results,
    }


def main():
    grid = load_grid()
    results = load_existing_results()

    already_done = set(int(k) for k in results.keys())
    remaining = [c for c in grid if c["cell_id"] not in already_done]

    print(f"Total cells: {len(grid)}")
    print(f"Already completed: {len(already_done)}")
    print(f"Remaining: {len(remaining)}\n")

    if not remaining:
        print("Nothing to do — all cells already processed.")
        return

    processed_this_run = 0
    failed_cells = []

    for i, cell in enumerate(remaining):
        cell_id = cell["cell_id"]
        try:
            print(f"[{i+1}/{len(remaining)}] Processing cell {cell_id} "
                  f"({cell['center_lat']}, {cell['center_lon']})...")
            result = process_cell(cell)
            results[str(cell_id)] = result
            processed_this_run += 1

            if processed_this_run % SAVE_EVERY_N_CELLS == 0:
                save_results(results)
                print(f"  (checkpoint saved — {len(results)}/{len(grid)} total)")

            time.sleep(REQUEST_DELAY_SECONDS)

        except Exception as e:
            print(f"  FAILED cell {cell_id}: {e}")
            failed_cells.append(cell_id)
            continue

    save_results(results)

    print(f"\nDone. {len(results)}/{len(grid)} cells completed.")
    if failed_cells:
        print(f"Failed cells (rerun script to retry): {failed_cells}")


if __name__ == "__main__":
    main()