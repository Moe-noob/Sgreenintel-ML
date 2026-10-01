"""
Two-season preview: what would Feature 2 show if it reported the best date in
EACH of two start windows instead of one overall pick?

Windows (by planting start date):
  autumn : Jul 15 - Dec 31   (covers the Saudi autumn potato sources, late Jul to Oct)
  spring : Jan 1  - May 31   (Saudipedia's Mar-May, the Jan-Feb potato crop, FAO arid Jan)
Starts from Jun 1 to Jul 14 fall in neither window: no source we found describes
them as a normal season, and they are the hottest part of the year.

The selection rule inside each window is the EXACT production rule from
season_simulator.scan_planting_dates(): prefer shock-free dates, otherwise take
all viable dates, then choose the lowest mean daily water. This script only
partitions the 37 candidates the real scan already computes; nothing in
production changes.

Usage:
    python research/two_season_preview.py          # summary + Riyadh detail
    python research/two_season_preview.py --all    # also every other city
"""

import datetime as dt
import sys
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "heatmap"))

from crop_database import SCAN_CROPS
from nasa_power import fetch_daily_climatology_full
from season_simulator import scan_planting_dates

KNOWN_LOCATIONS = {
    "riyadh": (24.71, 46.68), "jeddah": (21.54, 39.17), "dammam": (26.43, 50.10),
    "najran": (17.49, 44.13), "jazan": (16.89, 42.55), "abha": (18.22, 42.51),
    "tabuk": (28.38, 36.57), "qassim": (26.33, 43.98), "madinah": (24.47, 39.61),
    "makkah": (21.39, 39.86), "hail": (27.52, 41.69),
}


def doy_of(month, day):
    return dt.date(2023, month, day).timetuple().tm_yday  # non-leap reference year


AUTUMN = (doy_of(7, 15), 365)
SPRING = (1, doy_of(5, 31))


def in_window(doy, window):
    return window[0] <= doy <= window[1]


def pick(runs):
    """Production rule: shock-free if any exist, else all viable; lowest mean daily water."""
    viable = [r for r in runs if r["viable"]]
    shock_free = [r for r in viable if r["shock_free"]]
    pool = shock_free if shock_free else viable
    if not pool:
        return None, 0, 0
    best = min(pool, key=lambda r: r["seasonal_etc_mm"] / r["total_days"])
    return best, len(shock_free), len(viable)


def evaluate():
    picks = {}
    for city, (lat, lon) in KNOWN_LOCATIONS.items():
        clim, elevation_m, _raw = fetch_daily_climatology_full(lat, lon)
        for crop in SCAN_CROPS:
            scan = scan_planting_dates(crop, clim, elevation_m, lat, step_days=10)
            if scan["best"] is None:
                continue
            runs = scan["runs"]
            picks[(city, crop)] = {
                "overall": scan["best"],
                "autumn": pick([r for r in runs if in_window(r["start_doy"], AUTUMN)]),
                "spring": pick([r for r in runs if in_window(r["start_doy"], SPRING)]),
            }
    return picks


def avg(values):
    return sum(values) / len(values)


def summary(picks):
    where = {"autumn": 0, "spring": 0, "neither": 0}
    for entry in picks.values():
        doy = entry["overall"]["start_doy"]
        if in_window(doy, AUTUMN):
            where["autumn"] += 1
        elif in_window(doy, SPRING):
            where["spring"] += 1
        else:
            where["neither"] += 1
    print(f"\nWhere does the CURRENT single pick start? ({len(picks)} crop x city combinations)")
    print(f"  autumn window (Jul 15 - Dec 31): {where['autumn']}")
    print(f"  spring window (Jan 1 - May 31) : {where['spring']}")
    print(f"  neither (Jun 1 - Jul 14)       : {where['neither']}")

    print(f"\n{'Crop':<14}{'Window':<8}{'cities':>7}{'w/ shock-free':>15}{'median water mm':>17}"
          f"{'median mm/day':>15}{'avg shocks H/C':>16}")
    print("-" * 92)
    for crop in SCAN_CROPS:
        keys = sorted(k for k in picks if k[1] == crop)
        for window in ("autumn", "spring"):
            found = [picks[k][window][0] for k in keys if picks[k][window][0]]
            free = sum(1 for k in keys if picks[k][window][1] > 0)
            if not found:
                print(f"{crop if window == 'autumn' else '':<14}{window:<8}{0:>7}")
                continue
            print(f"{crop if window == 'autumn' else '':<14}{window:<8}{len(found):>7}{free:>15}"
                  f"{median([f['seasonal_etc_mm'] for f in found]):>17.0f}"
                  f"{median([f['seasonal_etc_mm'] / f['total_days'] for f in found]):>15.2f}"
                  f"{avg([f['heat_shock_days'] for f in found]):>10.0f}/{avg([f['cold_shock_days'] for f in found]):<4.0f}")
        both = [(picks[k]["autumn"][0], picks[k]["spring"][0]) for k in keys
                if picks[k]["autumn"][0] and picks[k]["spring"][0]]
        if both:
            water = [s["seasonal_etc_mm"] / a["seasonal_etc_mm"] for a, s in both]
            daily = [(s["seasonal_etc_mm"] / s["total_days"]) / (a["seasonal_etc_mm"] / a["total_days"])
                     for a, s in both]
            print(f"{'':<14}{'spring vs autumn:':<22} seasonal water x{median(water):.2f} "
                  f"({min(water):.2f}-{max(water):.2f}), per day x{median(daily):.2f}")
        print()


def detail(picks, city):
    print(f"\n{'Crop':<14}{'Window':<8}{'start -> end':<16}{'days':>5}{'water mm':>10}{'mm/day':>8}"
          f"{'shocks H/C':>12}{'shock-free/viable':>19}")
    for crop in SCAN_CROPS:
        entry = picks.get((city, crop))
        if entry is None:
            continue
        for window in ("autumn", "spring"):
            best, n_free, n_viable = entry[window]
            label = crop if window == "autumn" else ""
            if best is None:
                print(f"{label:<14}{window:<8}no viable date in this window")
                continue
            print(f"{label:<14}{window:<8}{best['start_date'] + ' -> ' + best['end_date']:<16}"
                  f"{best['total_days']:>5}{best['seasonal_etc_mm']:>10.0f}"
                  f"{best['seasonal_etc_mm'] / best['total_days']:>8.2f}"
                  f"{best['heat_shock_days']:>8}/{best['cold_shock_days']:<3}{n_free:>10}/{n_viable:<8}")
        print()


def main():
    print("Evaluating 11 cities x 4 crops (real production scan, about a minute)...")
    picks = evaluate()
    summary(picks)
    print("=" * 92)
    print("DETAIL: riyadh")
    detail(picks, "riyadh")
    if "--all" in sys.argv:
        for city in KNOWN_LOCATIONS:
            if city != "riyadh":
                print("=" * 92)
                print(f"DETAIL: {city}")
                detail(picks, city)


if __name__ == "__main__":
    main()