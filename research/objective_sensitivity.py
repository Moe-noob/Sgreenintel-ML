"""
Objective sensitivity: how much does the choice of selection objective change
the advisor's answer?

The production rule picks the lowest MEAN DAILY water among eligible dates
(shock-free dates if any exist, otherwise all viable ones). Whole-season water
is the other natural objective, but with heat-unit-driven season lengths it can
favour short, hot seasons; that is why season_simulator.py uses per-day.

Rules compared (all three use the same eligible pool):
  current : lowest water per day (production rule)
  total   : lowest whole-season water
  hybrid  : lowest whole-season water when shock-free dates exist, otherwise
            the production per-day rule

Nothing in production changes: this partitions the 37 candidates the real scan
already computes, and first checks that its own copy of the production rule
reproduces the production pick.

Usage:
    python research/objective_sensitivity.py
"""

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
DETAIL_CITIES = ("abha", "riyadh")


def per_day(run):
    return run["seasonal_etc_mm"] / run["total_days"]


def pool_of(runs):
    viable = [r for r in runs if r["viable"]]
    shock_free = [r for r in viable if r["shock_free"]]
    return (shock_free if shock_free else viable), bool(shock_free)


def pick_current(runs):
    pool, _ = pool_of(runs)
    return min(pool, key=per_day) if pool else None


def pick_total(runs):
    pool, _ = pool_of(runs)
    return min(pool, key=lambda r: r["seasonal_etc_mm"]) if pool else None


def pick_hybrid(runs):
    pool, has_free = pool_of(runs)
    if not pool:
        return None
    if has_free:
        return min(pool, key=lambda r: r["seasonal_etc_mm"])
    return min(pool, key=per_day)


def shift_days(a, b):
    d = abs(a["start_doy"] - b["start_doy"])
    return min(d, 365 - d)


def avg(values):
    return sum(values) / len(values)


def evaluate():
    results, mismatches = {}, 0
    for city, (lat, lon) in KNOWN_LOCATIONS.items():
        clim, elevation_m, _raw = fetch_daily_climatology_full(lat, lon)
        for crop in SCAN_CROPS:
            scan = scan_planting_dates(crop, clim, elevation_m, lat, step_days=10)
            runs = scan["runs"]
            current = pick_current(runs)
            if current is None or scan["best"] is None:
                continue
            if current["start_doy"] != scan["best"]["start_doy"]:
                mismatches += 1
            _pool, has_free = pool_of(runs)
            results[(city, crop)] = {
                "current": current, "total": pick_total(runs),
                "hybrid": pick_hybrid(runs), "has_free": has_free,
            }
    return results, mismatches


def summary(results, mismatches):
    n = len(results)
    n_free = sum(1 for e in results.values() if e["has_free"])
    print(f"\nReplica check: the per-day rule reproduces the production pick in {n - mismatches}/{n} combinations.")
    print(f"Combinations that have a shock-free pool: {n_free}/{n} "
          f"(elsewhere 'hybrid' behaves exactly like 'current').")
    print(f"\n{'Crop':<14}{'Rule':<9}{'changed':>9}{'median shift':>14}   {'seasonal water vs current':<27}"
          f"{'median days':>12}{'avg shocks H/C':>16}")
    print("-" * 105)
    for crop in SCAN_CROPS:
        keys = sorted(k for k in results if k[1] == crop)
        base = [results[k]["current"] for k in keys]
        for rule in ("current", "total", "hybrid"):
            picks = [results[k][rule] for k in keys]
            changed = sum(1 for p, b in zip(picks, base) if p["start_doy"] != b["start_doy"])
            shifts = [shift_days(p, b) for p, b in zip(picks, base)]
            water = [p["seasonal_etc_mm"] / b["seasonal_etc_mm"] for p, b in zip(picks, base)]
            print(f"{crop if rule == 'current' else '':<14}{rule:<9}{changed:>6}/{len(keys):<2}{median(shifts):>11.0f} d"
                  f"   x{median(water):.2f} ({min(water):.2f}-{max(water):.2f})".ljust(60)
                  + f"{median([p['total_days'] for p in picks]):>11.0f}"
                  f"{avg([p['heat_shock_days'] for p in picks]):>10.0f}/{avg([p['cold_shock_days'] for p in picks]):<4.0f}")
        print()


def detail(results, city):
    print(f"\n{'Crop':<14}{'Rule':<9}{'start -> end':<16}{'days':>5}{'water mm':>10}{'mm/day':>8}{'shocks H/C':>12}")
    for crop in SCAN_CROPS:
        entry = results.get((city, crop))
        if entry is None:
            continue
        for rule in ("current", "total", "hybrid"):
            p = entry[rule]
            print(f"{crop if rule == 'current' else '':<14}{rule:<9}{p['start_date'] + ' -> ' + p['end_date']:<16}"
                  f"{p['total_days']:>5}{p['seasonal_etc_mm']:>10.0f}{per_day(p):>8.2f}"
                  f"{p['heat_shock_days']:>8}/{p['cold_shock_days']:<3}")
        print()


def main():
    print("Evaluating 11 cities x 4 crops under three rules (real production scan, about a minute)...")
    results, mismatches = evaluate()
    summary(results, mismatches)
    for city in DETAIL_CITIES:
        print("=" * 105)
        print(f"DETAIL: {city}")
        detail(results, city)


if __name__ == "__main__":
    main()