import sys
import datetime as _dt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "heatmap"))

from nasa_power import fetch_daily_climatology_full
from season_simulator import simulate_annual_season
from crop_database import CROP_DB
from compare_climatology_methods import build_field_date_value
from compare_climate_windows import fetch_raw_range_cached, build_climatology_for_year_range, WINDOWS

LAT, LON = 28.38, 36.57  # Tabuk

_, elevation_m, _ = fetch_daily_climatology_full(LAT, LON)
payload = fetch_raw_range_cached(LAT, LON, "19960101", "20251231")
by_field_date_value = build_field_date_value(payload)

sep08_doy = _dt.date(2023, 9, 8).timetuple().tm_yday
apr01_doy = _dt.date(2023, 4, 1).timetuple().tm_yday

crop = CROP_DB["Corn_(maize)"]
print(f"Corn tolerance thresholds: Txc={crop.get('t_max_tolerable')}  Tnc={crop.get('t_min_tolerable')}\n")

print(f"{'Window':<12}{'Candidate':<10}{'Days':>6}{'HeatShockDays':>15}{'ColdShockDays':>15}{'ShockFree':>11}")

for win_name, sy, ey in WINDOWS:
    clim = build_climatology_for_year_range(by_field_date_value, sy, ey)
    for label, doy in [("Sep 08", sep08_doy), ("Apr 01", apr01_doy)]:
        result = simulate_annual_season("Corn_(maize)", clim, elevation_m, LAT, doy)
        if result["viable"]:
            print(f"{win_name:<12}{label:<10}{result['total_days']:>6}"
                  f"{result['heat_shock_days']:>15}{result['cold_shock_days']:>15}"
                  f"{str(result['shock_free']):>11}")
        else:
            print(f"{win_name:<12}{label:<10}  NOT VIABLE")
    print()