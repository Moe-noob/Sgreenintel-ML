"""
Location-based crop advisor: given a location, ranks our 6 crops by how
well the local climate matches each crop's known ideal temperature
range, identifies the best planting months, and reports real FAO-56
water requirements (per hectare, per square meter, and a stated-
assumption per-plant estimate for home growers).

Deliberate design choice: crops are ranked by CLIMATE FIT (how many
months fall inside the crop's ideal range), not by total water use or
growing-season length. Ranking by water/season length was checked and
rejected -- it rewards short-season crops regardless of whether they
actually suit the climate (e.g. a crop could "win" by having a short
season in mediocre conditions, rather than genuinely thriving there).
Key (use lowercase)	City
riyadh	Riyadh
jeddah	Jeddah
dammam	Dammam
najran	Najran
jazan	Jazan
abha	Abha
tabuk	Tabuk
qassim	Qassim
madinah	Madinah
makkah	Makkah
hail	Hail
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "care"))

from nasa_power import fetch_climate_data, MONTH_KEYS
from evapotranspiration import penman_monteith_et0, real_rhmin
from crop_coefficients import CROP_COEFFICIENTS, calculate_etc
from care_profiles import SPECIES_PROFILES

# A few major Saudi cities for convenience -- users can also pass raw lat/lon.
KNOWN_LOCATIONS = {
    "riyadh": (24.71, 46.68),
    "jeddah": (21.54, 39.17),
    "dammam": (26.43, 50.10),
    "najran": (17.49, 44.13),
    "jazan": (16.89, 42.55),
    "abha": (18.22, 42.51),
    "tabuk": (28.38, 36.57),
    "qassim": (26.33, 43.98),
    "madinah": (24.47, 39.61),
    "makkah": (21.39, 39.86),
    "hail": (27.52, 41.69),
}

# Planting density assumptions, cross-checked against real horticultural
# extension spacing guidance (not arbitrary picks):
#   Tomato: 24-36in spacing (UC ANR, Gardening Know How) -> ~1.8-3.6/m^2
#   Pepper: 18-24in spacing (Utah State Extension)        -> ~4.8-5/m^2
#   Potato: 10-12in x 30-36in rows (USU, UMN Extension)   -> ~4.25-5.2/m^2
#   Corn:   9-12in x 24-36in rows (U Maryland Extension)  -> ~4.9/m^2
#   Grape:  9x6ft real vineyard spacing (eVineyard)        -> ~0.2/m^2
#   Apple:  modern dwarf-rootstock spacing (current commercial standard)
ASSUMED_PLANTS_PER_M2 = {
    "Tomato": 2.5,
    "Potato": 5,
    "Pepper,_bell": 5,
    "Grape": 1 / 4,
    "Apple": 1 / 5,
    "Corn_(maize)": 5,
}


def resolve_location(location):
    """Accepts either a known city name (case-insensitive) or a (lat, lon) tuple."""
    if isinstance(location, str):
        key = location.strip().lower()
        if key not in KNOWN_LOCATIONS:
            raise ValueError(f"Unknown location '{location}'. Known: {list(KNOWN_LOCATIONS)} "
                              f"or pass (lat, lon) directly.")
        return KNOWN_LOCATIONS[key]
    return location


def evaluate_month_fit(temp_max_c, ideal_range):
    """True if this month's typical daytime high falls inside the crop's
    ideal range."""
    low, high = ideal_range
    return low <= temp_max_c <= high


def analyze_crop(crop_name, monthly_climate, elevation, latitude):
    """
    Returns per-crop analysis: suitable months, and water requirement
    (ETc-based) averaged across those suitable months.
    """
    ideal_range = SPECIES_PROFILES[crop_name]["ideal_temp_range_c"]

    suitable_months = []
    etc_values = []
    clamped_any = False

    for month in MONTH_KEYS:
        v = monthly_climate[month]
        is_suitable = evaluate_month_fit(v["temp_c"], ideal_range)

        if is_suitable:
            et0 = penman_monteith_et0(
                temp_mean_c=v["temp_c"], temp_max_c=v["temp_max_c"], temp_min_c=v["temp_min_c"],
                dewpoint_c=v["dewpoint_c"], wind_speed_ms=v["wind_speed_ms"],
                solar_radiation_mj=v["solar_radiation_mj"], elevation_m=elevation,
                latitude_deg=latitude, month=month,
            )
            rhmin = real_rhmin(v["temp_max_c"], v["dewpoint_c"])
            etc, kc_adj, clamped = calculate_etc(et0, crop_name, v["wind_speed_ms"], rhmin)

            suitable_months.append(month)
            etc_values.append(etc)
            clamped_any = clamped_any or clamped

    avg_etc = sum(etc_values) / len(etc_values) if etc_values else None

    return {
        "crop": crop_name,
        "suitable_months": suitable_months,
        "num_suitable_months": len(suitable_months),
        "avg_etc_mm_day": avg_etc,
        "any_clamped": clamped_any,
    }


def water_breakdown(etc_mm_day, crop_name):
    """Converts ETc (mm/day) into two simple, audience-specific numbers:
    liters per plant per day (home growers) and cubic meters per
    hectare per day (farmers) -- deliberately kept to two numbers, not
    four, to avoid the extra unit-conversion step (mm -> L/m2 -> m3/ha
    -> per-month) making the result harder to read than it needs to be."""
    plants_per_m2 = ASSUMED_PLANTS_PER_M2[crop_name]
    liters_per_plant_day = etc_mm_day / plants_per_m2
    m3_per_hectare_day = etc_mm_day * 10  # 1mm over 1 hectare = 10 m^3

    return {
        "liters_per_plant_per_day": round(liters_per_plant_day, 2),
        "m3_per_hectare_per_day": round(m3_per_hectare_day, 1),
        "assumed_plants_per_m2": plants_per_m2,
    }


def get_recommendations(location):
    """
    Main entry point. location: a known city name (str) or (lat, lon) tuple.
    Returns crops ranked by climate fit, with water requirements for each.
    """
    lat, lon = resolve_location(location)
    monthly_climate, elevation = fetch_climate_data(lat, lon)

    results = []
    for crop_name in CROP_COEFFICIENTS:
        analysis = analyze_crop(crop_name, monthly_climate, elevation, lat)
        if analysis["avg_etc_mm_day"] is not None:
            analysis["water"] = water_breakdown(analysis["avg_etc_mm_day"], crop_name)
        results.append(analysis)

    # Ranked by climate fit (number of suitable months) -- NOT by water use.
    results.sort(key=lambda r: r["num_suitable_months"], reverse=True)

    return {
        "location": location,
        "coordinates": (lat, lon),
        "elevation_m": elevation,
        "recommendations": results,
    }


def print_recommendations(result):
    print(f"\n=== Crop Suitability for {result['location']} "
          f"({result['coordinates'][0]}, {result['coordinates'][1]}, "
          f"elevation {result['elevation_m']:.0f}m) ===\n")

    for r in result["recommendations"]:
        print(f"{r['crop']:15s}  Climate-suitable months (modeled, open-field): "
              f"{r['num_suitable_months']}/12 "
              f"({', '.join(r['suitable_months']) if r['suitable_months'] else 'none'})")

        if r["avg_etc_mm_day"] is not None:
            w = r["water"]
            clamp_note = "  [estimate may be conservative in extreme dryness]" if r["any_clamped"] else ""
            print(f"                 Estimated water use during those months: "
                  f"{r['avg_etc_mm_day']:.2f} mm/day{clamp_note}")
            print(f"                   Home garden: ~{w['liters_per_plant_per_day']} L per single plant, per day "
                  f"(based on an assumed spacing of {w['assumed_plants_per_m2']} plants per m²)")
            print(f"                   Farm scale: ~{w['m3_per_hectare_per_day']} m³/ha/day")
        print()


if __name__ == "__main__":
    test_cities = ["riyadh", "jeddah", "dammam", "najran", "jazan", "abha", "tabuk"]
    for city in test_cities:
        result = get_recommendations(city)
        print_recommendations(result)
        print("=" * 70)
        
        
#get_recommendations((26.30, 43.98))  # e.g. Buraidah, or anywhere else