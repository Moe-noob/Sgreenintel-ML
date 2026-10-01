"""
Does the lapse-rate elevation correction move NASA POWER temperatures closer to reality?

Reference data: official WMO 1991-2020 climate normals (monthly mean daily maximum and minimum), one CSV per
station, published by NOAA NCEI (WMO Climatological Standard Normals, NCEI accession 0253808). Each file also
gives the station height, so the correction is tested with an ELEVATION THAT COMES FROM THE STATION, not from
our DEM lookup. The DEM variant is shown too.

For every station we compare, month by month, three versions of the model climate against the WMO normals:
  cell        NASA POWER exactly as reported (temperatures at the grid-cell elevation)
  station     corrected from the cell elevation to the station height
  DEM         corrected from the cell elevation to the Copernicus 90 m DEM elevation at the coordinates

Criteria fixed BEFORE running (so the result cannot be read to suit us):
  1. Abha (a mountain city, cell about 900 m below the station): combined Tmax/Tmin mean absolute error must fall
     to half or less of the uncorrected error.
  2. No other station's combined error may rise by more than 0.5 C.

Caveats: NASA data here are 2016-2025, WMO normals 1991-2020, so a small warm offset (recent decade) is expected;
compare the errors, not the exact values. WMO stations (often airports) are not identical to our NASA grid cell
or to a city centre.

Needs network (NASA POWER, NOAA, Open-Meteo). Run from the project root:
    python research/check_site_elevation.py
"""

import sys
import warnings
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "heatmap"))

import nasa_power  # noqa: E402
from site_elevation import correct_climatology, fetch_site_elevation_m, lapse_shift_c  # noqa: E402

BASE = ("https://www.nodc.noaa.gov/archive/arc0216/0253808/2.2/data/0-data/"
        "Region-2-WMO-Normals-9120/SaudiArabia/CSV/")
STATIONS = [
    ("Abha", BASE + "Abha_41112.csv"),
    ("Khamis Mushait", BASE + "Khamis-Mushait_41114.csv"),
    ("Sharorah", BASE + "Sharorah_41136.csv"),
    ("Wejh", BASE + "Wejh_40400.csv"),
    ("Arar", BASE + "Arar_40357.csv"),
]
KNOWN_LOCATIONS = {
    "riyadh": (24.71, 46.68), "jeddah": (21.54, 39.17), "dammam": (26.43, 50.10),
    "najran": (17.49, 44.13), "jazan": (16.89, 42.55), "abha": (18.22, 42.51),
    "tabuk": (28.38, 36.57), "qassim": (26.33, 43.98), "madinah": (24.47, 39.61),
    "makkah": (21.39, 39.86), "hail": (27.52, 41.69),
}
MONTH_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def dms_to_deg(text):
    deg, minute, sec, hemi = text.split("|")
    value = float(deg) + float(minute) / 60 + float(sec) / 3600
    return -value if hemi.strip().upper() in ("S", "W") else value


def parse_wmo_csv(text):
    """Station name, lat, lon, height (m), monthly mean daily max (12), monthly mean daily min (12)."""
    rows = [line.split(",") for line in text.splitlines()]
    name = next(r[1] for r in rows if r and r[0] == "Station_Name")
    header = next(i for i, r in enumerate(rows) if r and r[0] == "WMO_Number" and len(r) > 3 and r[1] == "Latitude")
    wmo, lat, lon, height = rows[header + 1][:4]

    def monthly(param_code):
        for r in rows:
            if len(r) >= 16 and r[0] == wmo and r[1] == str(param_code) and r[2] == "Mean":
                return [float(v) if v.strip() else None for v in r[4:16]]
        raise ValueError(f"parameter {param_code} not found")

    return {"name": name, "wmo": wmo, "lat": dms_to_deg(lat), "lon": dms_to_deg(lon), "height_m": float(height),
            "tmax": monthly(3), "tmin": monthly(4)}


def monthly_means(clim, key):
    out, start = [], 0
    for days in MONTH_DAYS:
        chunk = [clim[i][key] for i in range(start, start + days)]
        out.append(sum(chunk) / len(chunk))
        start += days
    return out


def load_uncorrected(lat, lon):
    try:
        return nasa_power.fetch_daily_climatology_full(lat, lon, correct_elevation=False)
    except TypeError:                       # nasa_power.py not yet patched: it is uncorrected already
        return nasa_power.fetch_daily_climatology_full(lat, lon)


def errors(model, wmo):
    pairs = [(m, w) for m, w in zip(model, wmo) if w is not None]
    diffs = [m - w for m, w in pairs]
    return sum(diffs) / len(diffs), sum(abs(d) for d in diffs) / len(diffs)   # bias, MAE


def main():
    results = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for label, url in STATIONS:
            print(f"\n{'=' * 100}\n{label}")
            try:
                st = parse_wmo_csv(requests.get(url, timeout=30).text)
            except Exception as exc:
                print(f"  could not read the WMO file: {exc}")
                continue
            try:
                clim, cell_m, raw = load_uncorrected(st["lat"], st["lon"])
            except Exception as exc:
                print(f"  could not get NASA data: {exc}")
                continue
            dem_m = fetch_site_elevation_m(st["lat"], st["lon"])
            variants = {"cell": clim}
            c_station, _r, info_s = correct_climatology(clim, raw, cell_m, st["height_m"])
            variants["station"] = c_station
            if dem_m is not None:
                c_dem, _r2, _info = correct_climatology(clim, raw, cell_m, dem_m)
                variants["DEM"] = c_dem
            shift = lapse_shift_c(cell_m, st["height_m"])
            print(f"  WMO {st['wmo']} ({st['lat']:.3f}, {st['lon']:.3f})  station height {st['height_m']:.0f} m | "
                  f"NASA cell {cell_m:.0f} m | DEM {'n/a' if dem_m is None else f'{dem_m:.0f} m'} | "
                  f"station minus cell {st['height_m'] - cell_m:+.0f} m -> {shift:+.1f} C")

            entry = {"label": label, "stats": {}}
            print(f"  {'':<10}{'Tmax bias':>10}{'Tmax MAE':>10}{'Tmin bias':>10}{'Tmin MAE':>10}{'combined MAE':>14}")
            for vname, vclim in variants.items():
                bx, mx = errors(monthly_means(vclim, "temp_max_c"), st["tmax"])
                bn, mn = errors(monthly_means(vclim, "temp_min_c"), st["tmin"])
                entry["stats"][vname] = (mx + mn) / 2
                print(f"  {vname:<10}{bx:>+10.1f}{mx:>10.1f}{bn:>+10.1f}{mn:>10.1f}{(mx + mn) / 2:>14.1f}")
            results.append(entry)

            if label == "Abha":
                print(f"\n  Abha month by month (C): WMO normal | NASA cell | corrected to station height")
                print(f"  {'':<5}" + "".join(f"{m:>7}" for m in MONTHS))
                for key, wmo_row, title in (("temp_max_c", st["tmax"], "Tmax"), ("temp_min_c", st["tmin"], "Tmin")):
                    print(f"  {title} WMO " + "".join(f"{v:>7.1f}" for v in wmo_row))
                    print(f"  {title} cell" + "".join(f"{v:>7.1f}" for v in monthly_means(clim, key)))
                    print(f"  {title} corr" + "".join(f"{v:>7.1f}" for v in monthly_means(c_station, key)))

    print(f"\n{'=' * 100}\nCRITERIA (fixed before running)\n{'=' * 100}")
    abha = next((r for r in results if r["label"] == "Abha"), None)
    if abha:
        before, after = abha["stats"]["cell"], abha["stats"]["station"]
        print(f"1. Abha combined MAE {before:.1f} C -> {after:.1f} C (needs <= {before / 2:.1f}): "
              f"{'PASS' if after <= before / 2 else 'FAIL'}")
    worst = [(r["label"], r["stats"]["station"] - r["stats"]["cell"]) for r in results if r["label"] != "Abha"]
    for label, delta in worst:
        print(f"   {label:<16} combined MAE change {delta:+.1f} C ({'ok' if delta <= 0.5 else 'WORSE by more than 0.5'})")
    if worst:
        print(f"2. No other station worse by more than 0.5 C: "
              f"{'PASS' if all(d <= 0.5 for _l, d in worst) else 'FAIL'}")

    print(f"\n{'=' * 100}\nWHAT THE CORRECTION WOULD DO TO OUR 11 CITIES (DEM elevation vs NASA cell elevation)\n{'=' * 100}")
    print(f"{'city':<10}{'NASA cell m':>13}{'DEM m':>9}{'difference m':>14}{'temperature shift C':>21}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for city, (lat, lon) in KNOWN_LOCATIONS.items():
            try:
                _c, cell_m, _r = load_uncorrected(lat, lon)
            except Exception as exc:
                print(f"{city:<10}NASA data unavailable: {exc}")
                continue
            dem_m = fetch_site_elevation_m(lat, lon)
            if dem_m is None:
                print(f"{city:<10}{cell_m:>13.0f}{'n/a':>9}")
                continue
            print(f"{city:<10}{cell_m:>13.0f}{dem_m:>9.0f}{dem_m - cell_m:>+14.0f}{lapse_shift_c(cell_m, dem_m):>+21.1f}")


if __name__ == "__main__":
    main()
