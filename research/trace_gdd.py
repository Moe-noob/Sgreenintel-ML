"""
Trace the heat-unit (GDD) accumulation for one crop, city and start date, day
by day, exactly as season_simulator._stage_lengths_from_gdd does it, then
compare the result with the real production simulation.

GDD as implemented (crop_database.growing_degree_day, Paredes et al. 2025 Eq. 1):
    Tavg = (Tmax + Tmin) / 2
    GDD  = 0                    if Tavg <  Tbase
         = Tupper - Tbase       if Tavg >  Tupper     (the per-day cap)
         = Tavg - Tbase         otherwise
The DAILY MEAN is clamped; Tmax and Tmin are NOT capped individually.
Stage boundaries fall on the first day the cumulative GDD reaches each target.

Usage (aliases avoid PowerShell trouble with parentheses and commas):
    python research/trace_gdd.py                        # abha, corn, Jul 10
    python research/trace_gdd.py riyadh corn 8 29       # city crop month day
    crops: corn, tomato, pepper, potato
"""

import datetime as dt
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "heatmap"))

from crop_database import CROP_DB, growing_degree_day
from nasa_power import fetch_daily_climatology_full
from season_simulator import simulate_annual_season, doy_to_date, STAGES

KNOWN_LOCATIONS = {
    "riyadh": (24.71, 46.68), "jeddah": (21.54, 39.17), "dammam": (26.43, 50.10),
    "najran": (17.49, 44.13), "jazan": (16.89, 42.55), "abha": (18.22, 42.51),
    "tabuk": (28.38, 36.57), "qassim": (26.33, 43.98), "madinah": (24.47, 39.61),
    "makkah": (21.39, 39.86), "hail": (27.52, 41.69),
}
ALIASES = {"corn": "Corn_(maize)", "tomato": "Tomato", "pepper": "Pepper,_bell", "potato": "Potato"}

# Where the paper's own printed total differs from the sum of its stage values.
PAPER_PRINTED_TOTAL = {"Corn_(maize)": 1540}  # Paredes 2025 Table 5, maize grain, short season


def doy_of(month, day):
    return dt.date(2023, month, day).timetuple().tm_yday  # non-leap reference year


def main():
    args = sys.argv[1:]
    city = args[0].lower() if len(args) > 0 else "abha"
    crop = ALIASES.get(args[1].lower(), args[1]) if len(args) > 1 else "Corn_(maize)"
    month = int(args[2]) if len(args) > 2 else 7
    day = int(args[3]) if len(args) > 3 else 10

    lat, lon = KNOWN_LOCATIONS[city]
    clim, elevation_m, _raw = fetch_daily_climatology_full(lat, lon)
    c = CROP_DB[crop]
    g = c["gdd_stages"]
    stage_gdd = [g["ini"], g["dev"], g["mid"], g["late"]]
    targets = [sum(stage_gdd[: i + 1]) for i in range(4)]
    cap = c["t_upper"] - c["t_base"]
    start_doy = doy_of(month, day)

    print(f"{crop} at {city}, start {doy_to_date(start_doy)} (day-of-year {start_doy})")
    print(f"Tbase {c['t_base']}  Tupper {c['t_upper']}  -> at most {cap:g} GDD per day")
    print(f"Stage GDD (initial/dev/mid/late): {stage_gdd}   cumulative targets: {targets}")
    print(f"Total heat-unit requirement USED BY THE ENGINE: {targets[-1]}")
    if crop in PAPER_PRINTED_TOTAL and PAPER_PRINTED_TOTAL[crop] != targets[-1]:
        print(f"  (Paredes Table 5 prints {PAPER_PRINTED_TOTAL[crop]} for this row, but its four stage "
              f"values add to {targets[-1]}; the engine uses the stage values.)")
    print(f"Shortest season the cap allows: {math.ceil(targets[-1] / cap)} days\n")

    print(f"{'day':>4} {'date':<7}{'Tmax':>6}{'Tmin':>6}{'Tavg':>6}{'GDD':>7}{'cumul':>8}  {'stage':<13}note")
    cum, boundaries, days_at_cap, days_at_zero, rows = 0.0, [], 0, 0, 0
    for n in range(365):
        d = clim[(start_doy + n - 1) % 365]
        tavg = (d["temp_max_c"] + d["temp_min_c"]) / 2
        gdd = growing_degree_day(d["temp_max_c"], d["temp_min_c"], c["t_base"], c["t_upper"])
        cum += gdd
        note = ""
        if tavg > c["t_upper"]:
            note, days_at_cap = "at cap", days_at_cap + 1
        elif tavg < c["t_base"]:
            note, days_at_zero = "below base", days_at_zero + 1
        stage = STAGES[len(boundaries)]
        print(f"{n + 1:>4} {doy_to_date(start_doy + n):<7}{d['temp_max_c']:>6.1f}{d['temp_min_c']:>6.1f}"
              f"{tavg:>6.1f}{gdd:>7.2f}{cum:>8.1f}  {stage:<13}{note}")
        rows = n + 1
        while len(boundaries) < 4 and cum >= targets[len(boundaries)]:
            boundaries.append(n + 1)
            print(f"     --- {stage} stage complete after day {n + 1} (cumulative {cum:.1f} >= {targets[len(boundaries) - 1]}) ---")
        if len(boundaries) == 4:
            break

    print()
    if len(boundaries) < 4:
        print("Heat-unit requirement NOT reached within a year: not viable at this start date.")
        return
    lengths = (boundaries[0], boundaries[1] - boundaries[0], boundaries[2] - boundaries[1], boundaries[3] - boundaries[2])
    print(f"Trace result : {rows} days, stage lengths {lengths}")
    print(f"Final day    : cumulative GDD {cum:.1f} (requirement {targets[-1]})")
    print(f"Average      : {cum / rows:.2f} GDD/day; days at the {cap:g}/day cap: {days_at_cap}; days at zero: {days_at_zero}")

    run = simulate_annual_season(crop, clim, elevation_m, lat, start_doy)
    if not run["viable"]:
        print("Production says NOT viable -> MISMATCH")
    else:
        same = run["total_days"] == rows and tuple(run["stage_lengths"]) == lengths
        print(f"Production   : {run['total_days']} days, stage lengths {tuple(run['stage_lengths'])} -> "
              f"{'MATCHES the trace' if same else 'MISMATCH'}")


if __name__ == "__main__":
    main()
