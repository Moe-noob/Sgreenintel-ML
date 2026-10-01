import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "heatmap"))

from nasa_power import fetch_daily_climatology_full
from season_simulator import scan_planting_dates
from crop_database import SCAN_CROPS

KNOWN_LOCATIONS = {
    "riyadh": (24.71, 46.68), "jeddah": (21.54, 39.17), "dammam": (26.43, 50.10),
    "najran": (17.49, 44.13), "jazan": (16.89, 42.55), "abha": (18.22, 42.51),
    "tabuk": (28.38, 36.57), "qassim": (26.33, 43.98), "madinah": (24.47, 39.61),
    "makkah": (21.39, 39.86), "hail": (27.52, 41.69),
}

print("Audit: current selection (lowest water) vs. best-available (fewest shock days),")
print("for every city x annual crop, using CURRENT PRODUCTION climatology (2016-2025).\n")
print(f"{'City':<10}{'Crop':<16}{'Selected shock (H/C/Tot)':<27}{'Best-avail shock (H/C/Tot)':<28}{'Gap':>6}")
print("-" * 90)

flagged = []

for city_name, (lat, lon) in KNOWN_LOCATIONS.items():
    clim, elevation_m, raw_years = fetch_daily_climatology_full(lat, lon)

    for crop in SCAN_CROPS:
        scan = scan_planting_dates(crop, clim, elevation_m, lat, step_days=10, raw_years=raw_years)
        viable = [r for r in scan["runs"] if r["viable"]]
        if not viable or scan["best"] is None:
            print(f"{city_name:<10}{crop:<16}  NOT VIABLE")
            continue

        selected = scan["best"]
        sel_total = selected["heat_shock_days"] + selected["cold_shock_days"]

        best_available = min(viable, key=lambda r: r["heat_shock_days"] + r["cold_shock_days"])
        best_total = best_available["heat_shock_days"] + best_available["cold_shock_days"]

        gap = sel_total - best_total

        sel_str = f"{selected['heat_shock_days']}/{selected['cold_shock_days']}/{sel_total}"
        best_str = f"{best_available['heat_shock_days']}/{best_available['cold_shock_days']}/{best_total}"

        marker = "  <-- LARGE GAP" if gap > 20 else ""
        print(f"{city_name:<10}{crop:<16}{sel_str:<27}{best_str:<28}{gap:>6}{marker}")

        if gap > 20:
            flagged.append((city_name, crop, sel_total, best_total, gap,
                            selected["start_date"], best_available["start_date"]))

print(f"\n{'='*90}")
print(f"FLAGGED (gap > 20 total shock days between selected and best-available):")
print(f"{'='*90}")
if flagged:
    for city_name, crop, sel_total, best_total, gap, sel_date, best_date in flagged:
        print(f"  {city_name:<10}{crop:<16}selected={sel_date} ({sel_total} shock days)  "
              f"best-available={best_date} ({best_total} shock days)  gap={gap}")
else:
    print("  None.")