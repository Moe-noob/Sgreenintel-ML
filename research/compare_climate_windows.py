"""
Climate-window sensitivity analysis.

Tests whether the REAL production Advisor recommendation (planting date,
viable window, seasonal water need) actually changes depending on which
NASA POWER year range the climatology is built from:

  2020-2025  (6 years -- short, recency-focused)
  2016-2025  (10 years -- current production baseline)
  1996-2025  (30 years -- matches WMO's own climate-normal standard length)

This does NOT modify any production file. It calls the REAL
scan_planting_dates() / simulate_perennial_cycle() from
heatmap/season_simulator.py with three custom climatologies built the
same way nasa_power.py builds its production one (same smoothing
function, same constant), so the comparison is a genuine test of the
production logic under different inputs -- not a simplified
reimplementation of it.

Important epistemic limit, stated plainly: this tests whether the
recommendation is ROBUST to the choice of window. It does NOT and
cannot determine which window is "more accurate" for real planting
outcomes -- that would require actual KSA crop yield/trial data, which
this project does not have. See research/README.md.

Also computes a simple year-by-year linear trend (1996-2025) for
headline variables, to check whether the climate this project models
is stationary or shifting -- a legitimate, cheap complement to the
window comparison, distinct from claiming which window is "correct."

Usage:
    python research/compare_climate_windows.py
"""

import sys
import time
import json
from pathlib import Path
from collections import defaultdict

import numpy as np
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "heatmap"))

from nasa_power import (
    fetch_daily_climatology_full, DAILY_URL, DAILY_PARAMETERS,
    SMOOTHING_HALF_WINDOW, _smooth_circular, _doy_365,
)
from season_simulator import scan_planting_dates, simulate_perennial_cycle
from crop_database import CROP_DB, SCAN_CROPS, PERENNIAL_CROPS

from compare_climatology_methods import build_field_date_value, FIELDS

CACHE_DIR = Path(__file__).resolve().parent / "cache"
WINDOWS = [("2020-2025", 2020, 2025), ("2016-2025", 2016, 2025), ("1996-2025", 1996, 2025)]


def fetch_raw_range_cached(lat, lon, start, end, retries=3, delay=3):
    """Fetches (and locally caches) a custom date-range payload -- separate
    cache from both nasa_power.py's production cache and the other research
    script's cache, filename includes the exact range so nothing collides
    or goes stale silently."""
    CACHE_DIR.mkdir(exist_ok=True)
    path = CACHE_DIR / f"raw_range_{lat:.2f}_{lon:.2f}_{start}_{end}.json"
    if path.exists():
        with open(path) as fh:
            return json.load(fh)

    params = {
        "parameters": DAILY_PARAMETERS, "community": "AG",
        "longitude": lon, "latitude": lat, "start": start, "end": end, "format": "JSON",
    }
    for attempt in range(retries):
        try:
            r = requests.get(DAILY_URL, params=params, timeout=180)
            r.raise_for_status()
            payload = r.json()
            with open(path, "w") as fh:
                json.dump(payload, fh)
            return payload
        except (requests.exceptions.RequestException, ValueError) as e:
            print(f"    fetch attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                raise


def build_climatology_for_year_range(by_field_date_value, start_year, end_year):
    """
    Builds a 365-day climatology from only the years in [start_year, end_year],
    using the EXACT same per-day-mean + circular-smoothing approach as
    nasa_power.py's production build_daily_climatology() -- same smoothing
    constant, same function -- so the only thing that varies between windows
    is which years' data goes in, not the method itself.
    """
    sums = {f: defaultdict(float) for f in FIELDS}
    counts = {f: defaultdict(int) for f in FIELDS}
    for field in FIELDS:
        for date_key, value in by_field_date_value[field].items():
            year = int(date_key[:4])
            if not (start_year <= year <= end_year):
                continue
            doy = _doy_365(date_key)
            sums[field][doy] += value
            counts[field][doy] += 1

    clim = []
    for doy in range(1, 366):
        entry = {"doy": doy}
        for f in FIELDS:
            entry[f] = sums[f][doy] / counts[f][doy]
        clim.append(entry)

    for f in FIELDS:
        smoothed = _smooth_circular([c[f] for c in clim], SMOOTHING_HALF_WINDOW)
        for c, v in zip(clim, smoothed):
            c[f] = v

    return clim


def compute_trend(by_field_date_value, fields=("temp_c", "temp_max_c", "wind_speed_ms")):
    """Simple year-by-year linear trend (1996-2025) -- is the climate
    stationary or shifting? A legitimate, cheap complement to the window
    comparison; does not claim to say which window is 'more correct.'"""
    print(f"\n  Year-by-year trend (linear slope, 1996-2025):")
    for field in fields:
        by_year = defaultdict(list)
        for date_key, value in by_field_date_value[field].items():
            by_year[int(date_key[:4])].append(value)
        years = sorted(by_year)
        yearly_means = [sum(by_year[y]) / len(by_year[y]) for y in years]
        slope, intercept = np.polyfit(years, yearly_means, 1)
        total_change = slope * (years[-1] - years[0])
        print(f"    {field:<18} slope={slope:+.4f}/yr   "
              f"total change over {years[-1]-years[0]} yrs: {total_change:+.2f}")


def compare_city(name, lat, lon):
    print(f"\n{'='*95}")
    print(f"  {name.upper()}  ({lat}, {lon})")
    print(f"{'='*95}")

    _, elevation_m, _ = fetch_daily_climatology_full(lat, lon)  # reuse production's elevation

    print(f"  Fetching 1996-2025 raw data (covers all 3 windows)...")
    payload = fetch_raw_range_cached(lat, lon, "19960101", "20251231")
    by_field_date_value = build_field_date_value(payload)

    clims = {win: build_climatology_for_year_range(by_field_date_value, sy, ey)
             for win, sy, ey in WINDOWS}

    print(f"\n  Annual crops -- does the REAL recommended planting date change?")
    for crop in SCAN_CROPS:
        print(f"\n  {crop}:")
        for win, _, _ in WINDOWS:
            scan = scan_planting_dates(crop, clims[win], elevation_m, lat, step_days=10)
            best = scan["best"]
            if best:
                print(f"    {win:12s}  best={best['start_date']} -> {best['end_date']}  "
                      f"({best['total_days']}d)  shock_free={scan['n_shock_free']}/{scan['n_candidates']}  "
                      f"seasonal_etc={best['seasonal_etc_mm']:.0f}mm")
            else:
                print(f"    {win:12s}  NOT VIABLE")

    print(f"\n  Perennial crops:")
    for crop in PERENNIAL_CROPS:
        print(f"\n  {crop}:")
        for win, _, _ in WINDOWS:
            result = simulate_perennial_cycle(crop, clims[win], elevation_m, lat)
            print(f"    {win:12s}  {result['start_date']} -> {result['end_date']}  "
                  f"seasonal_etc={result['seasonal_etc_mm']:.0f}mm")

    compute_trend(by_field_date_value)


if __name__ == "__main__":
    KNOWN_LOCATIONS = {
        "riyadh": (24.71, 46.68), "jeddah": (21.54, 39.17), "dammam": (26.43, 50.10),
        "najran": (17.49, 44.13), "jazan": (16.89, 42.55), "abha": (18.22, 42.51),
        "tabuk": (28.38, 36.57), "qassim": (26.33, 43.98), "madinah": (24.47, 39.61),
        "makkah": (21.39, 39.86), "hail": (27.52, 41.69),
    }
    for name, (lat, lon) in KNOWN_LOCATIONS.items():
        compare_city(name, lat, lon)