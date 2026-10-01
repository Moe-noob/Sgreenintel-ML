"""
Reference-date comparison: what does the SAME engine say at customary
planting dates, versus the date the advisor selects?

The advisor selects the date with the lowest mean daily water use (an
adaptation of Elnesr & Alazba 2016, see season_simulator.py). Farmers pick
dates for other reasons, so the two can differ. This script measures the
difference in water, season length and shock days instead of arguing about it.

Reference dates are the MIDPOINT of ranges cited in DEFENSE_PREP.md section 6
(KAU 1992, FAO-56 Table 11 arid-region rows, Saudi potato sources, Saudipedia).
They are our own choice of midpoint, NOT an official calendar; replace them
with a real local calendar if one is obtained.

Nothing here modifies production code: it calls the real
scan_planting_dates() and simulate_annual_season().

Usage:
    python research/compare_reference_dates.py          # summary + Riyadh detail
    python research/compare_reference_dates.py --all    # also every other city
"""

import datetime as dt
import sys
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "heatmap"))

from nasa_power import fetch_daily_climatology_full
from season_simulator import scan_planting_dates, simulate_annual_season

KNOWN_LOCATIONS = {
    "riyadh": (24.71, 46.68), "jeddah": (21.54, 39.17), "dammam": (26.43, 50.10),
    "najran": (17.49, 44.13), "jazan": (16.89, 42.55), "abha": (18.22, 42.51),
    "tabuk": (28.38, 36.57), "qassim": (26.33, 43.98), "madinah": (24.47, 39.61),
    "makkah": (21.39, 39.86), "hail": (27.52, 41.69),
}

# (label, month, day) -- midpoint of the cited range, chosen by us.
REFERENCES = {
    "Tomato": [
        ("KAU 1992: Sep", 9, 15),
        ("FAO-56 arid: Oct/Nov", 10, 31),
        ("FAO-56 arid: Jan", 1, 15),
        ("Saudipedia: Mar-May", 4, 15),
    ],
    "Potato": [
        ("Saudi sources: Aug", 8, 15),
        ("Saudi/ARC: Sep/Oct", 9, 30),
        ("FAO-56 arid: Nov", 11, 15),
        ("Spring: Jan-Feb", 1, 31),
    ],
    "Corn_(maize)": [
        ("Jazan tradition: mid-Oct", 10, 15),
        ("FAO-56 arid: Dec/Jan", 12, 31),
    ],
    "Pepper,_bell": [
        ("FAO-56 arid: Oct", 10, 15),
    ],
}


def doy_of(month, day):
    return dt.date(2023, month, day).timetuple().tm_yday  # non-leap reference year


def metrics(run):
    days = run["total_days"]
    water = run["seasonal_etc_mm"]
    return {
        "start": run["start_date"], "end": run["end_date"], "days": days,
        "water": water, "mean": water / days,
        "heat": run["heat_shock_days"], "cold": run["cold_shock_days"],
    }


def avg(values):
    return sum(values) / len(values)


def evaluate():
    rows = {}
    for city, (lat, lon) in KNOWN_LOCATIONS.items():
        clim, elevation_m, _raw_years = fetch_daily_climatology_full(lat, lon)
        for crop, refs in REFERENCES.items():
            scan = scan_planting_dates(crop, clim, elevation_m, lat, step_days=10)
            best = scan["best"]
            if best is None:
                continue
            entry = {"model": metrics(best), "refs": {}}
            for label, month, day in refs:
                run = simulate_annual_season(crop, clim, elevation_m, lat, doy_of(month, day))
                entry["refs"][label] = metrics(run) if run["viable"] else None
            rows[(city, crop)] = entry
    return rows


def fmt_ratio(values):
    if not values:
        return "n/a"
    return f"x{median(values):.2f} ({min(values):.2f}-{max(values):.2f})"


def summary(rows):
    n_cities = len(KNOWN_LOCATIONS)
    print(f"\n{'Crop':<14}{'Planting date used':<42}{'viable':>8}  "
          f"{'seasonal water vs model':<26}{'mean/day vs model':<20}{'days':>5}{'shocks H/C':>12}")
    print("-" * 130)
    for crop, refs in REFERENCES.items():
        cities = sorted(c for (c, cr) in rows if cr == crop)
        if not cities:
            continue
        mods = [rows[(c, crop)]["model"] for c in cities]
        print(f"{crop:<14}{'MODEL PICK (lowest mean daily water)':<42}{len(cities):>5}/{n_cities:<2}"
              f"{'x1.00':<26}{'x1.00':<20}{avg([m['days'] for m in mods]):>5.0f}"
              f"{avg([m['heat'] for m in mods]):>8.0f}/{avg([m['cold'] for m in mods]):<3.0f}")
        for label, month, day in refs:
            pairs = [(rows[(c, crop)]["model"], rows[(c, crop)]["refs"][label])
                     for c in cities if rows[(c, crop)]["refs"][label]]
            name = f"{label} ({dt.date(2023, month, day):%b %d})"
            if not pairs:
                print(f"{'':<14}{name:<42}{0:>5}/{n_cities:<2}  not viable anywhere")
                continue
            water = [r["water"] / m["water"] for m, r in pairs]
            mean = [r["mean"] / m["mean"] for m, r in pairs]
            refs_only = [r for _, r in pairs]
            print(f"{'':<14}{name:<42}{len(pairs):>5}/{n_cities:<2}"
                  f"{fmt_ratio(water):<26}{fmt_ratio(mean):<20}"
                  f"{avg([r['days'] for r in refs_only]):>5.0f}"
                  f"{avg([r['heat'] for r in refs_only]):>8.0f}/{avg([r['cold'] for r in refs_only]):<3.0f}")
        print()
    print("Ratios are reference-date value / model-pick value, per city (median, then min-max).")
    print("'water' = whole-season mm; 'mean/day' = season mm divided by season days.")


def detail(rows, city):
    print(f"\n{'Crop':<14}{'Planting date used':<42}{'start -> end':<16}{'days':>5}"
          f"{'water mm':>10}{'mm/day':>8}{'shocks H/C':>12}")
    for crop, refs in REFERENCES.items():
        entry = rows.get((city, crop))
        if entry is None:
            continue
        m = entry["model"]
        print(f"{crop:<14}{'MODEL PICK':<42}{m['start'] + ' -> ' + m['end']:<16}{m['days']:>5}"
              f"{m['water']:>10.0f}{m['mean']:>8.2f}{m['heat']:>8}/{m['cold']:<3}")
        for label, month, day in refs:
            r = entry["refs"][label]
            name = f"{label} ({dt.date(2023, month, day):%b %d})"
            if r is None:
                print(f"{'':<14}{name:<42}not viable (GDD not reached within a year)")
                continue
            print(f"{'':<14}{name:<42}{r['start'] + ' -> ' + r['end']:<16}{r['days']:>5}"
                  f"{r['water']:>10.0f}{r['mean']:>8.2f}{r['heat']:>8}/{r['cold']:<3}")
        print()


def main():
    show_all = "--all" in sys.argv
    print("Evaluating 11 cities x 4 crops (about 2000 simulations, roughly a minute)...")
    rows = evaluate()
    summary(rows)
    print("=" * 130)
    print("DETAIL: riyadh")
    detail(rows, "riyadh")
    if show_all:
        for city in KNOWN_LOCATIONS:
            if city != "riyadh":
                print("=" * 130)
                print(f"DETAIL: {city}")
                detail(rows, city)


if __name__ == "__main__":
    main()
