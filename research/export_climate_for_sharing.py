"""
Exports our climate data as plain CSV files, so another tool or chat that cannot reach NASA POWER
(chat sandboxes normally block it) can still work with the same numbers, including humidity.

Writes into ./climate_export/ (created next to where you run it):
  sites.csv                       one row per city: coordinates, NASA cell elevation, site elevation, temperature shift
  climatology_<city>.csv          the 365-day daily NORMAL the app uses (2016-2025 average, 15-day smoothed),
                                  with humidity columns and the engine's ET0 added
  all_cities_climatology.csv      the same, all cities stacked in one file
  daily_<city>.csv                EVERY day 2016-2025, UNSMOOTHED, straight from NASA POWER (needs network)
  DATA_README.md                  column definitions, units, provenance and honest caveats
  climate_export.zip              everything above, ready to upload

Options:
  --no-daily    skip the unsmoothed daily download (works offline, from the cache)
  --raw         climatology WITHOUT the elevation correction (NASA cell values exactly as reported)

Run from the project root:
    python research/export_climate_for_sharing.py
"""

import csv
import math
import shutil
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "heatmap"))

import nasa_power  # noqa: E402

try:
    from site_elevation import LAPSE_DEW, LAPSE_T, lapse_shift_c  # noqa: E402
except ImportError:  # elevation patch not applied
    lapse_shift_c, LAPSE_T, LAPSE_DEW = None, 6.5, 2.0
try:
    from season_simulator import _et0_for  # noqa: E402
except Exception:  # keep the export working even if the engine cannot be imported
    _et0_for = None

KNOWN_LOCATIONS = {
    "riyadh": (24.71, 46.68), "jeddah": (21.54, 39.17), "dammam": (26.43, 50.10),
    "najran": (17.49, 44.13), "jazan": (16.89, 42.55), "abha": (18.22, 42.51),
    "tabuk": (28.38, 36.57), "qassim": (26.33, 43.98), "madinah": (24.47, 39.61),
    "makkah": (21.39, 39.86), "hail": (27.52, 41.69),
}
OUT_DIR = Path("climate_export")


def sat_vp(t_c):
    """Saturation vapour pressure (kPa), FAO-56 Eq. 11."""
    return 0.6108 * math.exp(17.27 * t_c / (t_c + 237.3))


def humidity_columns(temp_c, tmax_c, tmin_c, dewpoint_c):
    ea = sat_vp(dewpoint_c)                                    # actual vapour pressure from dewpoint, FAO-56 Eq. 14
    es = (sat_vp(tmax_c) + sat_vp(tmin_c)) / 2                 # mean saturation vapour pressure, FAO-56 Eq. 12
    rh_mean = min(100.0, 100.0 * ea / sat_vp(temp_c))
    rh_afternoon = min(100.0, 100.0 * ea / sat_vp(tmax_c))     # estimate of the afternoon minimum RH
    return {"ea_kpa": ea, "vpd_kpa": max(0.0, es - ea), "rh_mean_pct": rh_mean, "rh_afternoon_est_pct": rh_afternoon}


def load(lat, lon, correct):
    try:
        return nasa_power.fetch_daily_climatology_full(lat, lon, correct_elevation=correct)
    except TypeError:                           # nasa_power.py not yet patched: values are uncorrected
        return nasa_power.fetch_daily_climatology_full(lat, lon)


def write_csv(path, rows, columns):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: ("" if row.get(k) is None else (round(row[k], 4) if isinstance(row.get(k), float) else row.get(k)))
                             for k in columns})


CLIM_COLUMNS = ["city", "doy", "temp_c", "temp_max_c", "temp_min_c", "dewpoint_c", "rh_mean_pct", "rh_afternoon_est_pct",
                "ea_kpa", "vpd_kpa", "wind_speed_ms", "solar_radiation_mj", "precip_mm_day", "et0_mm_day"]
DAILY_COLUMNS = ["date", "temp_c", "temp_max_c", "temp_min_c", "dewpoint_c", "rh_mean_pct", "wind_speed_ms",
                 "solar_radiation_mj", "precip_mm_day"]


def export_city(city, lat, lon, correct, with_daily):
    clim, site_elev, _raw = load(lat, lon, correct)
    _c0, cell_elev, _r0 = load(lat, lon, False)
    shift = lapse_shift_c(cell_elev, site_elev, LAPSE_T) if (lapse_shift_c and correct and abs(site_elev - cell_elev) > 1e-9) else 0.0

    rows = []
    for day in clim:
        row = {"city": city, "doy": day["doy"]}
        row.update({k: day[k] for k in ("temp_c", "temp_max_c", "temp_min_c", "dewpoint_c", "wind_speed_ms",
                                         "solar_radiation_mj", "precip_mm_day")})
        row.update(humidity_columns(day["temp_c"], day["temp_max_c"], day["temp_min_c"], day["dewpoint_c"]))
        row["et0_mm_day"] = _et0_for(day, site_elev, lat) if _et0_for else None
        rows.append(row)
    write_csv(OUT_DIR / f"climatology_{city}.csv", rows, CLIM_COLUMNS)

    n_daily = 0
    if with_daily:
        payload = nasa_power.fetch_daily_raw(lat, lon)
        raw = payload["properties"]["parameter"]
        rad_unit = (payload.get("parameters", {}).get("ALLSKY_SFC_SW_DWN", {}) or {}).get("units", "")
        by_date = {}
        for power_name, field in nasa_power._POWER_TO_FIELD.items():
            for date_key, value in raw[power_name].items():
                if value is None or value <= nasa_power.FILL_VALUE_THRESHOLD:
                    continue
                if field == "solar_radiation_mj":
                    value = nasa_power._radiation_to_mj(value, rad_unit)
                by_date.setdefault(date_key, {})[field] = value
        daily_rows = []
        for date_key in sorted(by_date):
            d = by_date[date_key]
            row = {"date": f"{date_key[:4]}-{date_key[4:6]}-{date_key[6:8]}", **d}
            if all(k in d for k in ("temp_c", "temp_max_c", "temp_min_c", "dewpoint_c")):
                row["rh_mean_pct"] = humidity_columns(d["temp_c"], d["temp_max_c"], d["temp_min_c"], d["dewpoint_c"])["rh_mean_pct"]
            daily_rows.append(row)
        write_csv(OUT_DIR / f"daily_{city}.csv", daily_rows, DAILY_COLUMNS)
        n_daily = len(daily_rows)

    return rows, {"city": city, "lat": lat, "lon": lon, "cell_elevation_m": cell_elev, "site_elevation_m": site_elev,
                  "temp_shift_c_applied_to_climatology": shift, "daily_rows": n_daily}


README = """# Climate data export (SGreen Intel)

Plain-CSV copy of the climate data our Feature 2 / Feature 3 engine uses, for tools that cannot reach NASA POWER.

## Source
NASA POWER daily point API (https://power.larc.nasa.gov/api/temporal/daily/point), community AG, 2016-01-01 to 2025-12-31.
Variables: T2M, T2M_MAX, T2M_MIN, T2MDEW, WS2M, ALLSKY_SFC_SW_DWN, PRECTOTCORR. These are MERRA-2 REANALYSIS values for a
grid cell roughly 50-60 km wide (not station measurements). Missing values (-999) are dropped. 29 February is folded into
day 59 so every year has 365 days.

## Files
- `sites.csv` - one row per city: coordinates, NASA cell elevation, site elevation (Copernicus 90 m DEM), temperature shift.
- `climatology_<city>.csv` / `all_cities_climatology.csv` - the 365-day daily NORMAL: the 10-year average for each calendar
  day, smoothed with a centred running mean of +/- {half_window} days (a 15-day window). One row per day of year (doy 1 = 1 Jan).
- `daily_<city>.csv` (if present) - every single day, UNSMOOTHED, as NASA reports them. NOT elevation-corrected.

## Columns
| column | unit | meaning |
|---|---|---|
| temp_c, temp_max_c, temp_min_c | C | daily mean / maximum / minimum air temperature at 2 m |
| dewpoint_c | C | daily mean dewpoint at 2 m (T2MDEW). Humidity is carried by this, NASA's RH2M is not used |
| rh_mean_pct | % | relative humidity = 100 * e(dewpoint) / e(temp_c), FAO-56 Eq. 11 |
| rh_afternoon_est_pct | % | estimate of afternoon minimum RH = 100 * e(dewpoint) / e(temp_max_c) |
| ea_kpa | kPa | actual vapour pressure from dewpoint (FAO-56 Eq. 14) |
| vpd_kpa | kPa | vapour-pressure deficit = mean saturation vapour pressure (FAO-56 Eq. 12) - ea |
| wind_speed_ms | m/s | wind speed at 2 m |
| solar_radiation_mj | MJ/m2/day | all-sky shortwave radiation reaching the surface (converted from kWh/m2/day x 3.6) |
| precip_mm_day | mm/day | corrected precipitation |
| et0_mm_day | mm/day | FAO-56 Penman-Monteith reference ET computed by our engine from the columns above (climatology files only) |

## Elevation correction (climatology files, unless exported with --raw)
NASA gives temperatures at the grid cell's MEAN elevation, which can be far from the real site (Abha: cell 1,188 m vs
about 2,200 m). The climatology files are adjusted from the cell to the site elevation with a lapse rate of {lapse_t} C/km
for temperature and {lapse_dew} C/km for dewpoint; wind, radiation and precipitation are not adjusted. `sites.csv` gives the
shift applied. The daily_ files are NOT corrected: to match, add the temperature shift (see sites.csv) to temp_c/temp_max_c/temp_min_c and
{lapse_dew}/{lapse_t} times that shift to dewpoint_c. Check against WMO 1991-2020 normals: at Abha the monthly
temperature error fell from 6.3 C to 0.8 C after correction.

## Caveats you should carry into any analysis
- Reanalysis is not station data. Elevation is corrected; SEA/LAND blending is not. At coastal Wejh the NASA cell had Tmax about
  2.1 C too low and Tmin about 4.7 C too high against the WMO normals, so coastal cities (Jeddah, Dammam, Jazan) may have a
  compressed day-night range and humidity that is too high or low in ways not yet tested.
- The revised FAO-56 guidelines warn that gridded/reanalysis weather can give biased ET0 in arid areas unless conditioned
  against local observations. Our absolute ET0 level has NOT been checked against station ET0. Rankings of planting dates were
  cross-checked with FAO's AquaCrop model; absolute millimetres were not independently verified.
- The normal is a smoothed 10-year average: it under-represents single cold snaps or heat waves. Use the daily_ files for
  variability, at the cost of noise.
"""


def main():
    correct = "--raw" not in sys.argv
    with_daily = "--no-daily" not in sys.argv
    OUT_DIR.mkdir(exist_ok=True)

    all_rows, sites = [], []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for city, (lat, lon) in KNOWN_LOCATIONS.items():
            print(f"{city:<9}", end="", flush=True)
            try:
                rows, site = export_city(city, lat, lon, correct, with_daily)
            except Exception as exc:
                print(f"FAILED: {exc}")
                continue
            all_rows.extend(rows)
            sites.append(site)
            print(f"ok  (cell {site['cell_elevation_m']:.0f} m, site {site['site_elevation_m']:.0f} m"
                  f"{', ' + str(site['daily_rows']) + ' daily rows' if with_daily else ''})")

    write_csv(OUT_DIR / "all_cities_climatology.csv", all_rows, CLIM_COLUMNS)
    write_csv(OUT_DIR / "sites.csv", sites,
              ["city", "lat", "lon", "cell_elevation_m", "site_elevation_m", "temp_shift_c_applied_to_climatology", "daily_rows"])
    (OUT_DIR / "DATA_README.md").write_text(
        README.format(half_window=nasa_power.SMOOTHING_HALF_WINDOW,
                      lapse_t=LAPSE_T, lapse_dew=LAPSE_DEW), encoding="utf-8")
    archive = shutil.make_archive("climate_export", "zip", OUT_DIR)
    print(f"\nWrote {len(sites)} cities to {OUT_DIR.resolve()}\nUpload this one file: {Path(archive).resolve()}")


if __name__ == "__main__":
    main()
