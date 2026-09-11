"""
Location-based crop advisor (planting-date simulation version).

For each location the advisor answers, per crop:
  "If I plant on date X, can the crop complete its growth cycle here,
   and how much water does it need in each growth stage?"

Method chain (every step sourced -- see crop_database.py):
  NASA POWER daily climatology (2014-2023)
    -> FAO-56 Penman-Monteith ET0 (Eq. 6), per day
    -> FAO56rev growing-degree-day stage lengths (Paredes et al. 2025)
    -> FAO-56 Kc curve (Eq. 66) with arid-climate adjustment (Eq. 62/65)
    -> ETc = Kc x ET0 (Eq. 58), summed per stage and per season
    -> planting-date selection per Elnesr & Alazba 2016 (KSU):
       heat units met -> shock check -> minimum seasonal ETc

Known cities (lowercase): riyadh, jeddah, dammam, najran, jazan, abha,
tabuk, qassim, madinah, makkah, hail -- or pass (lat, lon).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "care"))

from nasa_power import fetch_daily_climatology_full
from crop_database import CROP_DB, SCAN_CROPS, PERENNIAL_CROPS, UNRESOLVED_CROPS
from season_simulator import scan_planting_dates, simulate_perennial_cycle, contiguous_windows

KNOWN_LOCATIONS = {
    "riyadh": (24.71, 46.68), "jeddah": (21.54, 39.17), "dammam": (26.43, 50.10),
    "najran": (17.49, 44.13), "jazan": (16.89, 42.55), "abha": (18.22, 42.51),
    "tabuk": (28.38, 36.57), "qassim": (26.33, 43.98), "madinah": (24.47, 39.61),
    "makkah": (21.39, 39.86), "hail": (27.52, 41.69),
}

PLANTING_STEP_DAYS = 10


def resolve_location(location):
    if isinstance(location, str):
        key = location.strip().lower()
        if key not in KNOWN_LOCATIONS:
            raise ValueError(f"Unknown location '{location}'. Known: {list(KNOWN_LOCATIONS)} or pass (lat, lon).")
        return KNOWN_LOCATIONS[key]
    return location


def per_plant_liters(etc_mm_day, crop_name):
    """ETc (mm/day = L/m2/day) / plants per m2 -> L per plant per day.
    This is a field-equivalent figure (closed canopy at the stated spacing)."""
    return etc_mm_day / CROP_DB[crop_name]["plants_per_m2"]


def get_recommendations(location, step_days=PLANTING_STEP_DAYS):
    lat, lon = resolve_location(location)
    clim, elevation, raw_years = fetch_daily_climatology_full(lat, lon)

    annual = {name: scan_planting_dates(name, clim, elevation, lat, step_days, raw_years) for name in SCAN_CROPS}
    perennial = {name: simulate_perennial_cycle(name, clim, elevation, lat) for name in PERENNIAL_CROPS}

    # Ranking (presentation only): widest shock-free planting window first,
    # then lowest seasonal water among best dates.
    ranked = sorted(annual.values(),
                    key=lambda s: (-s["n_shock_free"], -s["n_viable"],
                                   s["best"]["seasonal_etc_mm"] if s["best"] else 1e9))
    return {
        "location": location, "coordinates": (lat, lon), "elevation_m": elevation,
        "annual_crops": ranked, "perennial_crops": list(perennial.values()),
        "unresolved_crops": UNRESOLVED_CROPS,
    }


def _print_stages(run, crop_name, indent="      "):
    ppm2 = CROP_DB[crop_name]["plants_per_m2"]
    print(f"{indent}{'Stage':<13}{'Days':>5}  {'Dates':<17}{'mm/day':>7}{'mm total':>10}{'ETc-eq L/plant/day':>20}")
    for s in run["stages"]:
        print(f"{indent}{s['stage']:<13}{s['days']:>5}  {s['start']}-{s['end']:<8}"
              f"{s['etc_mm_per_day']:>7.2f}{s['etc_mm']:>10.0f}"
              f"{per_plant_liters(s['etc_mm_per_day'], crop_name):>20.2f}")
    print(f"{indent}{'TOTAL':<13}{run['total_days']:>5}  {'':<17}{'':>7}{run['seasonal_etc_mm']:>10.0f}")
    print(f"{indent}Seasonal crop water use (ETc): {run['seasonal_etc_mm']:.0f} mm  =  {run['seasonal_m3_per_ha']:.0f} m3/ha;  "
          f"mean {run['seasonal_etc_mm']/run['total_days']:.2f} mm/day  "
          f"(ET0 {run['seasonal_et0_mm']:.0f} mm; Kc_mid adj {run['kc_mid_adjusted']:.2f}, Kc_end adj {run['kc_end_adjusted']:.2f})")
    print(f"{indent}Peak crop water use: {run['peak_etc_mm_day']:.2f} mm/day around {run['peak_date']}")
    print(f"{indent}Per-plant figures are the field ETc divided by an assumed density of {ppm2} plants/m2 -- an area-equivalent, not measured uptake.")
    if run["kc_clamp_note"]:
        print(f"{indent}Limitation: a Kc-adjustment input (RHmin or wind) was outside FAO-56 Eq.62's validated range and was clamped "
              f"to the limit as FAO-56 prescribes; {run['kc_clamp_note']}. Interpret ETc with added uncertainty.")


def print_recommendations(result):
    lat, lon = result["coordinates"]
    print(f"\n=== Crop advisor for {result['location']} ({lat}, {lon}, elevation {result['elevation_m']:.0f} m) ===")
    print("    Climate: NASA POWER daily climatology 2014-2023 (a typical year, not a forecast). ET0: FAO-56 Penman-Monteith.")
    print("    Annual crops: FAO56rev GDD phenology (Paredes et al. 2025). Perennials: FAO-56 Table 11 reference phenology, mature plant.")
    print("    Planting-date selection adapted from Elnesr & Alazba (2016, KSU). All water figures are crop water use (ETc), not irrigation requirement.\n")

    for scan in result["annual_crops"]:
        name, best = scan["crop"], scan["best"]
        print(f"{name}")
        print(f"   Candidate planting dates tested: {scan['n_candidates']} (every {scan['step_days']} days); "
              f"complete the cycle within a year: {scan['n_viable']}; shock-free: {scan['n_shock_free']}")
        if best is None:
            print("   -> NOT VIABLE: no planting date lets this crop complete its heat-unit (GDD) requirement here.\n")
            continue
        sf_doys = [r["start_doy"] for r in scan["runs"] if r["viable"] and r["shock_free"]]
        windows = contiguous_windows(sf_doys, scan["step_days"])
        if windows:
            print("   Planting window(s) with no tolerance exceedances: " + "; ".join(f"{a} to {b}" for a, b in windows))
            print(f"   RECOMMENDED planting date: {best['start_date']}  ->  harvest ~{best['end_date']}  ({best['total_days']} days)")
        else:
            print("   No planting date is free of temperature-tolerance exceedances at this location.")
            print(f"   LEAST-WATER VIABLE CANDIDATE: {best['start_date']}  ->  harvest ~{best['end_date']}  ({best['total_days']} days)")
        print(f"   Basis: {scan['selection_basis']}")
        print(f"   Stage lengths from GDD (ini/dev/mid/late): {'/'.join(str(x) for x in best['stage_lengths'])} days")
        print(f"   Days above tolerable Tmax: {best['heat_shock_days']};  days below tolerable Tmin: {best['cold_shock_days']}  "
              f"(Elnesr & Alazba 2016 thresholds on the smoothed climatology; warning only, not a rejection)")
        rx = best.get("raw_exceedances")
        if rx:
            print(f"   Observed 2014-2023 ({len(rx['years'])} seasons, unsmoothed daily data): "
                  f"above Tmax {rx['heat_mean']:.0f} days/season (range {rx['heat_min']}-{rx['heat_max']}); "
                  f"below Tmin {rx['cold_mean']:.0f} days/season (range {rx['cold_min']}-{rx['cold_max']})")
        print(f"   Phenology counts: days at GDD ceiling (Tavg > Tupper) {best['heat_ceiling_days']}, days below Tbase {best['cold_days']}")
        if CROP_DB[name].get("disclosure"):
            print(f"   Note: {CROP_DB[name]['disclosure']}")
        _print_stages(best, name)
        print()

    for run in result["perennial_crops"]:
        name = run["crop"]
        print(f"{name}  (perennial -- one annual cycle of an ESTABLISHED plant)")
        print(f"   Cycle: {run['start_date']} to {run['end_date']} ({run['total_days']} days), stage lengths {run['stage_source']}")
        est = CROP_DB[name].get("establishment")
        if est:
            print(f"   Planting: {est['planting_season']}")
            print(f"   First harvest: {est['years_to_first_harvest']}")
        print(f"   {run['establishment_note']}")
        print(f"   Suitability status: {run['suitability_status'].upper()} -- {run['suitability_reason']}")
        print(f"   Phenology counts: days at GDD ceiling {run['heat_ceiling_days']}, days below Tbase {run['cold_days']} "
              f"(no temperature-tolerance test: not in the Elnesr & Alazba dataset)")
        _print_stages(run, name)
        print()

    if result["unresolved_crops"]:
        print(f"Not simulated (no sourced stage-length data yet): {', '.join(result['unresolved_crops'])}\n")


if __name__ == "__main__":
    test_cities = ["riyadh", "jeddah", "dammam", "najran", "jazan", "abha", "tabuk"]
    for city in test_cities:
        print_recommendations(get_recommendations(city))
        print("=" * 90)