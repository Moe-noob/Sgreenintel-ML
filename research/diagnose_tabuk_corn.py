import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "heatmap"))

from nasa_power import fetch_daily_climatology_full
from season_simulator import scan_planting_dates
from compare_climatology_methods import build_field_date_value
from compare_climate_windows import fetch_raw_range_cached, build_climatology_for_year_range

LAT, LON = 28.38, 36.57  # Tabuk

_, elevation_m, _ = fetch_daily_climatology_full(LAT, LON)
payload = fetch_raw_range_cached(LAT, LON, "19960101", "20251231")
by_field_date_value = build_field_date_value(payload)

clim_2016_2025 = build_climatology_for_year_range(by_field_date_value, 2016, 2025)

scan = scan_planting_dates("Corn_(maize)", clim_2016_2025, elevation_m, LAT, step_days=10)

print(f"Tabuk Corn, 2016-2025 climatology -- ALL {scan['n_candidates']} candidates, sorted by mean daily ETc:\n")
print(f"{'Start date':<12}{'End date':<12}{'Days':>6}{'Seasonal mm':>13}{'Mean mm/day':>13}{'Shock-free':>12}")

runs = [r for r in scan["runs"] if r["viable"]]
runs_sorted = sorted(runs, key=lambda r: r["seasonal_etc_mm"] / r["total_days"])

for r in runs_sorted:
    mean_daily = r["seasonal_etc_mm"] / r["total_days"]
    marker = " <-- WINNER" if r is scan["best"] else ""
    print(f"{r['start_date']:<12}{r['end_date']:<12}{r['total_days']:>6}"
          f"{r['seasonal_etc_mm']:>13.0f}{mean_daily:>13.3f}{str(r['shock_free']):>12}{marker}")