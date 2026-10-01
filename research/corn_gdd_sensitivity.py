"""
Corn heat-unit sensitivity.

Paredes et al. 2025 Table 5, maize grain, short season, prints stage values
200 / 380 / 500 / 340 (sum 1,420) but a total of 1,540. The engine uses the stage
values. If one of them is actually 120 higher (so the printed total is right),
how much do the corn recommendations move?

Variants run through the REAL production scan (crop data changed in memory
only, restored at the end; nothing on disk changes):
  as configured : 200 / 380 / 500 / 340   (1,420, what production uses)
  +120 initial  : 320 / 380 / 500 / 340   (1,540)
  +120 dev      : 200 / 500 / 500 / 340   (1,540)
  +120 mid      : 200 / 380 / 620 / 340   (1,540)
  +120 late     : 200 / 380 / 500 / 460   (1,540)

Usage:
    python research/corn_gdd_sensitivity.py
"""

import sys
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "heatmap"))

from crop_database import CROP_DB
from nasa_power import fetch_daily_climatology_full
from season_simulator import scan_planting_dates

CROP = "Corn_(maize)"
KNOWN_LOCATIONS = {
    "riyadh": (24.71, 46.68), "jeddah": (21.54, 39.17), "dammam": (26.43, 50.10),
    "najran": (17.49, 44.13), "jazan": (16.89, 42.55), "abha": (18.22, 42.51),
    "tabuk": (28.38, 36.57), "qassim": (26.33, 43.98), "madinah": (24.47, 39.61),
    "makkah": (21.39, 39.86), "hail": (27.52, 41.69),
}
DETAIL_CITIES = ("abha", "riyadh")

BASE = dict(CROP_DB[CROP]["gdd_stages"])
VARIANTS = {
    "as configured (1420)": dict(BASE),
    "+120 initial (1540)": {**BASE, "ini": BASE["ini"] + 120},
    "+120 development (1540)": {**BASE, "dev": BASE["dev"] + 120},
    "+120 mid-season (1540)": {**BASE, "mid": BASE["mid"] + 120},
    "+120 late (1540)": {**BASE, "late": BASE["late"] + 120},
}


def shift_days(a, b):
    d = abs(a - b)
    return min(d, 365 - d)


def main():
    climates = {city: fetch_daily_climatology_full(lat, lon) for city, (lat, lon) in KNOWN_LOCATIONS.items()}
    picks = {}
    original = CROP_DB[CROP]["gdd_stages"]
    try:
        for name, stages in VARIANTS.items():
            CROP_DB[CROP]["gdd_stages"] = stages
            for city, (lat, _lon) in KNOWN_LOCATIONS.items():
                clim, elevation_m, _raw = climates[city]
                scan = scan_planting_dates(CROP, clim, elevation_m, lat, step_days=10)
                picks[(name, city)] = scan["best"]
    finally:
        CROP_DB[CROP]["gdd_stages"] = original  # always restore

    base_name = next(iter(VARIANTS))
    print(f"\n{'Variant':<26}{'picks moved':>12}{'median shift':>14}{'median days':>13}{'water vs base':>26}")
    print("-" * 91)
    for name in VARIANTS:
        cur = [picks[(name, c)] for c in KNOWN_LOCATIONS]
        base = [picks[(base_name, c)] for c in KNOWN_LOCATIONS]
        moved = sum(1 for p, b in zip(cur, base) if p["start_doy"] != b["start_doy"])
        shifts = [shift_days(p["start_doy"], b["start_doy"]) for p, b in zip(cur, base)]
        water = [p["seasonal_etc_mm"] / b["seasonal_etc_mm"] for p, b in zip(cur, base)]
        print(f"{name:<26}{moved:>9}/{len(cur):<2}{median(shifts):>11.0f} d{median([p['total_days'] for p in cur]):>13.0f}"
              f"   x{median(water):.2f} ({min(water):.2f}-{max(water):.2f})")

    for city in DETAIL_CITIES:
        print(f"\nDETAIL: {city}")
        print(f"{'Variant':<26}{'start -> end':<16}{'days':>5}{'water mm':>10}{'shocks H/C':>12}")
        for name in VARIANTS:
            p = picks[(name, city)]
            print(f"{name:<26}{p['start_date'] + ' -> ' + p['end_date']:<16}{p['total_days']:>5}"
                  f"{p['seasonal_etc_mm']:>10.0f}{p['heat_shock_days']:>8}/{p['cold_shock_days']:<3}")


if __name__ == "__main__":
    main()
