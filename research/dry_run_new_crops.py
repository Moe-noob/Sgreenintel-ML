"""
Dry run: how would the candidate crops behave in the advisor, BEFORE anything
is added to crop_database.py?

Entries are built in memory only. CROP_DB is one plain dict shared by
crop_database.py and season_simulator.py, so updating it here changes nothing
on disk and affects only this process. The real scan_planting_dates() and
simulate_annual_season() are used unchanged.

Sources for every number (nothing else is used):
  Tbase / Tupper         Paredes et al. 2025 (AWM 319:109758), Tables 1-2
  Stage GDD              same paper, Table 5. Short/long (or industry/market)
                         variants are BOTH run so we can choose, as we did for
                         potato, by matching FAO-56 arid-region durations.
  Kc, height, Tmax/Tmin  Elnesr & Alazba (2016) workbook, Crops sheet
                         (Kc and height cross-checked against the database for
                         tomato, pepper and potato: exact match)
  Melon: Table 5 has one Cucumis melo row; Table 1 lists cantaloupe and melon
  with identical thresholds, so cantaloupe uses the melon GDD row. Sweet melons
  differ from cantaloupe only in Kc (mid 1.05 vs 0.85) and height (0.4 vs 0.3).

Written BEFORE running, so the test stays honest:
  onion, carrot, garlic, pea (cool-season): picks expected in autumn-winter,
  roughly Oct-Jan. Melon (warm-season, cold floor 15 C): Dec-May would be
  plausible; autumn (Sep-Nov) picks in interior cities would be a warning sign.

Usage:
    python research/dry_run_new_crops.py
"""

import datetime as dt
import sys
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "heatmap"))

from crop_database import CROP_DB
from nasa_power import fetch_daily_climatology_full
from season_simulator import scan_planting_dates, simulate_annual_season

KNOWN_LOCATIONS = {
    "riyadh": (24.71, 46.68), "jeddah": (21.54, 39.17), "dammam": (26.43, 50.10),
    "najran": (17.49, 44.13), "jazan": (16.89, 42.55), "abha": (18.22, 42.51),
    "tabuk": (28.38, 36.57), "qassim": (26.33, 43.98), "madinah": (24.47, 39.61),
    "makkah": (21.39, 39.86), "hail": (27.52, 41.69),
}


def entry(kc, height, tolerance, thresholds, gdd):
    return {
        "kind": "annual",
        "kc_ini": kc[0], "kc_mid": kc[1], "kc_end": kc[2], "height_m": height,
        "t_max_tolerable": tolerance[0], "t_min_tolerable": tolerance[1],
        "t_base": thresholds[0], "t_upper": thresholds[1],
        "gdd_stages": {"ini": gdd[0], "dev": gdd[1], "mid": gdd[2], "late": gdd[3]},
        "plants_per_m2": 1.0,  # placeholder: the simulator never reads it
    }


VARIANTS = {
    "Cantaloupe (melon short)": entry((0.5, 0.85, 0.6), 0.3, (38, 15), (10, 38), (185, 520, 315, 155)),
    "Cantaloupe (melon long)": entry((0.5, 0.85, 0.6), 0.3, (38, 15), (10, 38), (140, 545, 460, 455)),
    "Onion (dry, common)": entry((0.7, 1.05, 0.75), 0.4, (35, 2), (4.5, 35), (460, 470, 880, 480)),
    "Carrot (common)": entry((0.7, 1.05, 0.95), 0.3, (28, 6), (6, 30), (320, 465, 500, 290)),
    "Garlic (short)": entry((0.7, 1.0, 0.7), 0.3, (30, 8), (4, 30), (150, 340, 335, 315)),
    "Garlic (long)": entry((0.7, 1.0, 0.7), 0.3, (30, 8), (4, 30), (580, 615, 315, 240)),
    "Pea (fresh, industry)": entry((0.5, 1.15, 1.1), 0.5, (29, 4), (5, 27), (90, 300, 510, 25)),
    "Pea (fresh, market)": entry((0.5, 1.15, 1.1), 0.5, (29, 4), (5, 27), (155, 350, 575, 320)),
}

# first word of the variant name -> [(label, month, day, reference total days)]
REFERENCES = {
    "Cantaloupe": [
        ("Dec 31 (FAO-56 arid, sweet melons)", 12, 31, 160),
        ("Jan 15 (FAO-56 California, cantaloupe)", 1, 15, 120),
        ("Aug 15 (FAO-56 California, cantaloupe)", 8, 15, 120),
    ],
    "Onion": [
        ("Oct 15 (FAO-56 arid)", 10, 15, 210),
        ("Jan 15 (FAO-56 arid)", 1, 15, 210),
    ],
    "Carrot": [
        ("Oct 15 (FAO-56 arid)", 10, 15, 110),
        ("Jan 15 (FAO-56 arid)", 1, 15, 110),
    ],
    "Garlic": [
        ("Nov 15 (workbook: region undefined)", 11, 15, 100),
    ],
    "Pea": [
        ("Nov 15 (no arid reference; ~Europe/Med)", 11, 15, 100),
        ("Mar 15 (FAO-56 Mediterranean)", 3, 15, 100),
    ],
}


def doy_of(month, day):
    return dt.date(2023, month, day).timetuple().tm_yday


def main():
    CROP_DB.update(VARIANTS)  # in memory only; nothing is written to disk
    print("Loading climatologies (cached)...")
    climates = {city: fetch_daily_climatology_full(lat, lon)
                for city, (lat, lon) in KNOWN_LOCATIONS.items()}

    print("\n" + "=" * 110)
    print("MODEL PICKS: lowest-mean-daily-water feasible date, per city (real production scan)")
    print("=" * 110)
    for name in VARIANTS:
        print(f"\n{name}")
        for city, (lat, _lon) in KNOWN_LOCATIONS.items():
            clim, elev, _raw = climates[city]
            scan = scan_planting_dates(name, clim, elev, lat, step_days=10)
            best = scan["best"]
            if best is None:
                print(f"  {city:<9} no viable date (heat units not reached within a year)")
                continue
            print(f"  {city:<9} {best['start_date']} -> {best['end_date']} ({best['total_days']:>3} d)  "
                  f"water {best['seasonal_etc_mm']:>5.0f} mm  "
                  f"shocks H/C {best['heat_shock_days']}/{best['cold_shock_days']}  "
                  f"shock-free {scan['n_shock_free']}, viable {scan['n_viable']} of {scan['n_candidates']}")

    print("\n" + "=" * 110)
    print("SEASON LENGTH AT REFERENCE DATES vs the FAO-56 duration (median across cities, min-max)")
    print("=" * 110)
    for name in VARIANTS:
        family = name.split(" ")[0]
        for label, month, day, fao_days in REFERENCES.get(family, []):
            lengths = []
            for city, (lat, _lon) in KNOWN_LOCATIONS.items():
                clim, elev, _raw = climates[city]
                run = simulate_annual_season(name, clim, elev, lat, doy_of(month, day))
                if run["viable"]:
                    lengths.append(run["total_days"])
            if not lengths:
                print(f"  {name:<26}{label:<44} not viable in any city")
                continue
            print(f"  {name:<26}{label:<44}{len(lengths):>2}/{len(KNOWN_LOCATIONS)} viable  "
                  f"median {median(lengths):>4.0f} d ({min(lengths)}-{max(lengths)})   reference {fao_days} d")

    print("\nNothing was written to crop_database.py.")


if __name__ == "__main__":
    main()
