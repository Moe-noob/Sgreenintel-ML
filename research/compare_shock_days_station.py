"""
Do the app's heat/cold exceedance ("shock") counts match what a real weather station recorded?

For every crop and every planting date the app evaluates (viable ones only), this takes the app's season window
(start day + cycle length) and counts, for the SAME dates in 2016-2018:
    station      days the real station recorded Tmax > the crop's max-tolerable or Tmin < its min-tolerable
    NASA daily   the same count on NASA's unsmoothed daily values (elevation-corrected exactly as the app does)
    app headline heat_shock_days / cold_shock_days as the app reports them (smoothed typical year)
    app raw      the app's own raw_exceedances mean (unsmoothed NASA years 2016-2025)

Run from the repo root:   python research/compare_shock_days_station.py [path/to/station.csv]
Needs the hourly station CSV (default data/external/saudi-hourly-weather-data_Historical.csv) and internet on the
first run per location (NASA POWER + Open-Meteo elevation), like the app. The station data ends in May 2019.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "heatmap"))
import nasa_power as npw
import season_simulator as ss
from crop_database import CROP_DB, SCAN_CROPS

CSV = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "data" / "external" / "saudi-hourly-weather-data_Historical.csv")
CASES = [("Abha", "ABHA"), ("Najran", "NEJRAN"), ("Jazan", "KING ABDULLAH BIN ABDULAZIZ")]   # (label, station name in the file)
YEARS = (2016, 2017, 2018)      # start years to compare (windows may run into 2019; the station has data to May 2019)
MIN_OBS = 6                     # readings a day needs before its max/min are trusted
MIN_COVERAGE = 0.9              # a season window needs this share of its days with data, or that year is skipped
CORRECT_ELEVATION = True        # True = exactly what the app does (needs internet for the site height)

cols = ["STATION_NAME", "OBSERVATION_DATE", "LATITUDE", "LONGITUDE", "ELEVATION", "AIR_TEMPERATURE"]
want = {st for _, st in CASES}
parts = []
for chunk in pd.read_csv(CSV, usecols=cols, chunksize=500_000):
    chunk = chunk[chunk.STATION_NAME.str.strip().isin(want)]
    if chunk.empty:
        continue
    chunk = chunk.assign(STATION_NAME=chunk.STATION_NAME.str.strip(), t_utc=pd.to_datetime(chunk.OBSERVATION_DATE, format="ISO8601"))
    parts.append(chunk[chunk.t_utc.dt.year.between(min(YEARS) - 1, max(YEARS) + 1)])
df = pd.concat(parts)

def window_counts(get, start_year, start_doy, total_days, txc, tnc):
    """(heat days, cold days) for the season starting on that day-of-year, scaled to the full cycle; None if too many gaps."""
    start = date(start_year, 1, 1) + timedelta(days=start_doy - 1)
    heat = cold = used = 0
    for k in range(total_days):
        dt = start + timedelta(days=k)
        if dt.month == 2 and dt.day == 29:
            continue                                            # the NASA cache folds 29 Feb into 28 Feb
        v = get(dt)
        if v is None:
            continue
        used += 1
        heat += v[0] > txc
        cold += v[1] < tnc
    if used < MIN_COVERAGE * total_days:
        return None
    scale = total_days / used
    return heat * scale, cold * scale

for label, station in CASES:
    s = df[df.STATION_NAME == station].copy()
    if s.empty:
        print(f"\n##### {label}: station '{station}' not found"); continue
    s.loc[s.AIR_TEMPERATURE >= 99, "AIR_TEMPERATURE"] = np.nan
    s["day"] = (s.t_utc + pd.Timedelta(hours=3)).dt.floor("D")
    d = s.groupby("day").agg(n=("AIR_TEMPERATURE", "count"), tmax=("AIR_TEMPERATURE", "max"), tmin=("AIR_TEMPERATURE", "min"))
    d = d[d.n >= MIN_OBS]
    stn = {ts.date(): (r.tmax, r.tmin) for ts, r in d.iterrows()}
    lat, lon = round(float(s.LATITUDE.iloc[0]), 2), round(float(s.LONGITUDE.iloc[0]), 2)
    print(f"\n{'#' * 100}\n##### {label}: station '{station}' ({lat}, {lon}, {s.ELEVATION.iloc[0]:.0f} m), {len(stn)} usable days")

    clim, elev, raw_years = npw.fetch_daily_climatology_full(lat, lon, correct_elevation=CORRECT_ELEVATION)

    def nasa_get(dt):
        ry = raw_years.get(str(dt.year))
        if not ry:
            return None
        i = npw._doy_365(dt.strftime("%Y%m%d")) - 1
        a, b = ry["temp_max_c"][i], ry["temp_min_c"][i]
        return None if a is None or b is None else (a, b)

    rows = []
    for crop in SCAN_CROPS:
        txc, tnc = CROP_DB[crop].get("t_max_tolerable"), CROP_DB[crop].get("t_min_tolerable")
        if txc is None or tnc is None:
            continue
        scan = ss.scan_planting_dates(crop, clim, elev, lat, 10, raw_years)
        best_doy = scan["best"]["start_doy"] if scan["best"] else None
        for run in scan["runs"]:
            if not run["viable"]:
                continue
            pairs = []
            for y in YEARS:
                a = window_counts(stn.get, y, run["start_doy"], run["total_days"], txc, tnc)
                b = window_counts(nasa_get, y, run["start_doy"], run["total_days"], txc, tnc)
                if a is not None and b is not None:
                    pairs.append((a, b))
            if not pairs:
                continue
            rx = run.get("raw_exceedances") or {}
            rows.append(dict(crop=crop, start=run["start_date"], days=run["total_days"], best=run["start_doy"] == best_doy, txc=txc, tnc=tnc,
                             heat_stn=np.mean([p[0][0] for p in pairs]), heat_nasa=np.mean([p[1][0] for p in pairs]), heat_app=run["heat_shock_days"], heat_raw=rx.get("heat_mean", np.nan),
                             cold_stn=np.mean([p[0][1] for p in pairs]), cold_nasa=np.mean([p[1][1] for p in pairs]), cold_app=run["cold_shock_days"], cold_raw=rx.get("cold_mean", np.nan)))
    R = pd.DataFrame(rows)
    if R.empty:
        print("no comparable windows"); continue

    best = R[R.best].round(0).astype({c: int for c in ("days", "heat_stn", "heat_nasa", "heat_app", "cold_stn", "cold_nasa", "cold_app")}, errors="ignore")
    print("\nAPP'S RECOMMENDED START PER CROP: days over the crop's limits during its cycle (station | NASA daily | app headline | app raw-years mean)")
    print(best[["crop", "start", "days", "txc", "heat_stn", "heat_nasa", "heat_app", "heat_raw", "tnc", "cold_stn", "cold_nasa", "cold_app", "cold_raw"]].to_string(index=False))

    print(f"\nALL {len(R)} CROP x START-DATE WINDOWS: error against the station (days per cycle; + means the source counts MORE days than the station)")
    for kind in ("heat", "cold"):
        for name, col in (("NASA daily", f"{kind}_nasa"), ("app headline", f"{kind}_app"), ("app raw mean", f"{kind}_raw")):
            e = (R[col] - R[f"{kind}_stn"]).dropna()
            print(f"  {kind:<4} {name:<13} bias {e.mean():+6.1f} | mean abs error {e.abs().mean():5.1f}")
        free = R[R[f"{kind}_app"] == 0]
        if len(free):
            print(f"  {kind:<4} app says 0 days in {len(free)} windows; the station recorded >=1 day in {(free[f'{kind}_stn'] >= 1).sum()} of them, >=10 days in {(free[f'{kind}_stn'] >= 10).sum()}")
