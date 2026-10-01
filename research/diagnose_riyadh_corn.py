import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "heatmap"))

from nasa_power import fetch_daily_climatology_full
from season_simulator import scan_planting_dates

LAT, LON = 24.71, 46.68  # Riyadh

clim, elevation_m, raw_years = fetch_daily_climatology_full(LAT, LON)

scan = scan_planting_dates("Corn_(maize)", clim, elevation_m, LAT, step_days=10, raw_years=raw_years)

print(f"Riyadh Corn -- ALL {scan['n_candidates']} candidates, sorted by TOTAL shock days:\n")
print(f"{'Start date':<12}{'End date':<12}{'Days':>6}{'HeatShk':>9}{'ColdShk':>9}{'Total':>7}{'MeanETc':>10}{'ShockFree':>11}")

runs = [r for r in scan["runs"] if r["viable"]]
runs_sorted = sorted(runs, key=lambda r: (r["heat_shock_days"] + r["cold_shock_days"],
                                          r["seasonal_etc_mm"] / r["total_days"]))

for r in runs_sorted:
    total_shock = r["heat_shock_days"] + r["cold_shock_days"]
    mean_daily = r["seasonal_etc_mm"] / r["total_days"]
    marker = " <-- WINNER" if r is scan["best"] else ""
    print(f"{r['start_date']:<12}{r['end_date']:<12}{r['total_days']:>6}"
          f"{r['heat_shock_days']:>9}{r['cold_shock_days']:>9}{total_shock:>7}"
          f"{mean_daily:>10.2f}{str(r['shock_free']):>11}{marker}")