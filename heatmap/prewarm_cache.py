"""
Pre-warms the NASA POWER daily climatology cache for all 11 known cities
under the refreshed 2016-2025 window. Run this once after changing
DAILY_START/DAILY_END in nasa_power.py, so the advisor and tracker don't
each trigger a slow first-fetch independently.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from nasa_power import fetch_daily_climatology_full

KNOWN_LOCATIONS = {
    "riyadh": (24.71, 46.68), "jeddah": (21.54, 39.17), "dammam": (26.43, 50.10),
    "najran": (17.49, 44.13), "jazan": (16.89, 42.55), "abha": (18.22, 42.51),
    "tabuk": (28.38, 36.57), "qassim": (26.33, 43.98), "madinah": (24.47, 39.61),
    "makkah": (21.39, 39.86), "hail": (27.52, 41.69),
}

print("Pre-warming NASA POWER cache (2016-2025) for all known cities...\n")

for name, (lat, lon) in KNOWN_LOCATIONS.items():
    print(f"  {name:12s} ({lat}, {lon})...", end=" ", flush=True)
    try:
        clim, elevation_m, raw_years = fetch_daily_climatology_full(lat, lon)
        print(f"OK -- elevation {elevation_m:.0f}m, {len(clim)} days, "
              f"{len(raw_years)} raw years")
    except Exception as e:
        print(f"FAILED: {e}")

print("\nDone. All cities cached under heatmap/cache/ with the new date range.")
