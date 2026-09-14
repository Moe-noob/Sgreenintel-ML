"""
Feature 3: Personalized Plant Care Tracker.

Given a saved plant (crop, city, planting date), this module:
1. Determines the current growth stage using GDD-based simulation
   from the same climatological baseline as Feature 2 (ensuring
   consistency between the planning and tracking tools).
2. Reports the current stage's water requirement and care needs.
3. Fetches a 5-day weather forecast (OpenWeatherMap) and checks it
   against Elnesr & Alazba 2016 temperature-tolerance thresholds.
4. Raises specific, sourced alerts when forecast conditions exceed
   modeled tolerance thresholds -- consolidated by type, not one per day.

What this does NOT do:
- Convert ETc to irrigation requirement (no soil/efficiency modelling)
- Predict disease risk from weather (no sourced disease-weather
  relationships exist in this codebase -- deferred)
- Control irrigation hardware (no IoT scope)
- Apply rainfall offset (OpenWeatherMap precipitation data is not
  reliable at the accuracy needed for irrigation planning)

OpenWeatherMap free tier: current weather + 5-day/3-hour forecast.
API key required -- set OWM_API_KEY in a .env file or environment variable.
"""

import datetime
import os
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "heatmap"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv optional; key can be set directly in environment

from nasa_power import fetch_daily_climatology_full
from season_simulator import simulate_annual_season, doy_to_date, STAGES
from crop_database import CROP_DB, SCAN_CROPS
from care_profiles import CLASS_INFO, SPECIES_PROFILES

OWM_BASE = "https://api.openweathermap.org/data/2.5"
OWM_API_KEY = os.environ.get("OWM_API_KEY", "")


# ---------------------------------------------------------------------------
# Date utilities
# ---------------------------------------------------------------------------

def date_to_doy(d):
    """datetime.date -> day-of-year in our 365-day calendar (29 Feb folds to 59)."""
    doy = d.timetuple().tm_yday
    leap = d.year % 4 == 0 and (d.year % 100 != 0 or d.year % 400 == 0)
    if leap and doy >= 60:
        doy -= 1
    return doy


def parse_planting_date(date_str):
    """
    Accepts 'YYYY-MM-DD' or 'DD/MM/YYYY'.
    Returns datetime.date.
    """
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse planting date '{date_str}' -- use YYYY-MM-DD or DD/MM/YYYY")


# ---------------------------------------------------------------------------
# GDD-based stage tracker
# ---------------------------------------------------------------------------

def get_current_stage(crop_name, planting_date, clim, elevation_m, latitude_deg):
    """
    Determines which growth stage the plant is in today, using GDD
    accumulation on the same climatological baseline as Feature 2.

    Stage position is determined by calendar days elapsed against
    climatological GDD-derived stage lengths -- a typical-year
    approximation. Real GDD accumulation this season may differ if
    the current year is significantly warmer or cooler than the
    2014-2023 average used to build the climatology.

    Returns a dict with stage info, water need, and season summary.
    """
    today = datetime.date.today()

    # Guard: future planting date
    if planting_date > today:
        return {
            "viable": False,
            "reason": (
                f"Planting date {planting_date.strftime('%b %d, %Y')} is in the future. "
                f"Use the advisor (Feature 2) to plan ahead; the tracker works once "
                f"the plant is in the ground."
            ),
            "days_since_planting": None,
        }

    planting_doy = date_to_doy(planting_date)
    days_since_planting = (today - planting_date).days

    # Run the full GDD simulation from the planting date
    run = simulate_annual_season(crop_name, clim, elevation_m, latitude_deg, planting_doy)

    if not run["viable"]:
        return {
            "viable": False,
            "reason": run.get("reason", "GDD requirement not met at this location"),
            "days_since_planting": days_since_planting,
        }

    stage_lengths = run["stage_lengths"]
    total_days = run["total_days"]

    # If the plant has already completed its cycle
    if days_since_planting >= total_days:
        return {
            "viable": True,
            "season_complete": True,
            "days_since_planting": days_since_planting,
            "total_season_days": total_days,
            "harvest_date": (planting_date + datetime.timedelta(days=total_days)).strftime("%b %d, %Y"),
            "all_stages": run["stages"],
            "seasonal_etc_mm": run["seasonal_etc_mm"],
            "seasonal_m3_per_ha": run["seasonal_m3_per_ha"],
            "kc_mid_adjusted": run["kc_mid_adjusted"],
            "kc_end_adjusted": run["kc_end_adjusted"],
        }

    # Find the current stage
    cumulative = 0
    for i, (stage_name, stage_days) in enumerate(zip(STAGES, stage_lengths)):
        if days_since_planting < cumulative + stage_days:
            days_into = days_since_planting - cumulative
            days_remaining = stage_days - days_into
            stage_start = planting_date + datetime.timedelta(days=cumulative)
            stage_end = planting_date + datetime.timedelta(days=cumulative + stage_days - 1)
            next_stage = STAGES[i + 1] if i + 1 < len(STAGES) else "harvest"

            current_stage_data = run["stages"][i]

            return {
                "viable": True,
                "season_complete": False,
                "stage_name": stage_name,
                "stage_index": i,
                "days_into_stage": days_into,
                "days_remaining_in_stage": days_remaining,
                "stage_start_date": stage_start.strftime("%b %d"),
                "stage_end_date": stage_end.strftime("%b %d"),
                "next_stage": next_stage,
                "days_since_planting": days_since_planting,
                "total_season_days": total_days,
                "harvest_date": (planting_date + datetime.timedelta(days=total_days)).strftime("%b %d, %Y"),
                "current_stage_etc_mm_per_day": current_stage_data["etc_mm_per_day"],
                "current_stage_liters_per_plant": (
                    current_stage_data["etc_mm_per_day"] / CROP_DB[crop_name]["plants_per_m2"]
                ),
                "all_stages": run["stages"],
                "seasonal_etc_mm": run["seasonal_etc_mm"],
                "seasonal_m3_per_ha": run["seasonal_m3_per_ha"],
                "kc_mid_adjusted": run["kc_mid_adjusted"],
                "kc_end_adjusted": run["kc_end_adjusted"],
            }
        cumulative += stage_days

    return {"viable": True, "season_complete": True, "days_since_planting": days_since_planting}


# ---------------------------------------------------------------------------
# OpenWeatherMap integration
# ---------------------------------------------------------------------------

def fetch_owm_forecast(lat, lon):
    """
    Fetches 5-day / 3-hour forecast from OpenWeatherMap.
    Returns a list of daily summaries (Tmax, Tmin, humidity, description).
    Raises RuntimeError if the API key is missing or the call fails.
    """
    if not OWM_API_KEY:
        raise RuntimeError(
            "OWM_API_KEY environment variable not set. "
            "Get a free key at openweathermap.org and set it in your .env file."
        )

    url = f"{OWM_BASE}/forecast"
    params = {
        "lat": lat, "lon": lon,
        "appid": OWM_API_KEY,
        "units": "metric",
        "cnt": 40,  # 5 days x 8 readings/day
    }
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()

    # Aggregate 3-hour slots into daily summaries
    daily = {}
    for slot in data["list"]:
        date_str = slot["dt_txt"][:10]
        tmax = slot["main"]["temp_max"]
        tmin = slot["main"]["temp_min"]
        humidity = slot["main"]["humidity"]
        desc = slot["weather"][0]["description"] if slot.get("weather") else ""
        if date_str not in daily:
            daily[date_str] = {"tmax": tmax, "tmin": tmin,
                               "humidity_max": humidity, "descriptions": [desc]}
        else:
            daily[date_str]["tmax"] = max(daily[date_str]["tmax"], tmax)
            daily[date_str]["tmin"] = min(daily[date_str]["tmin"], tmin)
            daily[date_str]["humidity_max"] = max(daily[date_str]["humidity_max"], humidity)
            daily[date_str]["descriptions"].append(desc)

    return [
        {"date": d, "tmax": v["tmax"], "tmin": v["tmin"],
         "humidity_max": v["humidity_max"],
         "summary": v["descriptions"][len(v["descriptions"]) // 2]}
        for d, v in sorted(daily.items())
    ]


# ---------------------------------------------------------------------------
# Alert generation -- consolidated by type, not one per day
# ---------------------------------------------------------------------------

def generate_alerts(crop_name, stage_name, forecast_days):
    """
    Checks the 5-day forecast against Elnesr & Alazba 2016 temperature-
    tolerance thresholds (same source as Feature 2).

    Alerts are CONSOLIDATED by type: instead of one alert per day, a
    single alert summarises all affected days within the 5-day window.
    This avoids alert fatigue from repeated identical warnings.

    Returns a list of alert dicts with: level, type, affected_dates,
    n_days, tmax_range or tmin_range, message.
    """
    crop = CROP_DB.get(crop_name, {})
    txc = crop.get("t_max_tolerable")
    tnc = crop.get("t_min_tolerable")

    heat_days = []
    cold_days = []

    for day in forecast_days:
        if txc is not None and day["tmax"] > txc:
            heat_days.append(day)
        if tnc is not None and day["tmin"] < tnc:
            cold_days.append(day)

    alerts = []

    if heat_days:
        tmax_values = [d["tmax"] for d in heat_days]
        date_range = (
            heat_days[0]["date"] if len(heat_days) == 1
            else f"{heat_days[0]['date']} to {heat_days[-1]['date']}"
        )
        stage_advice = (
            "Early-stage seedlings are especially vulnerable -- ensure adequate moisture and consider temporary shading."
            if stage_name == "initial"
            else "Monitor for heat stress symptoms. Increase watering frequency during affected days."
        )
        alerts.append({
            "level": "warning",
            "type": "heat_stress",
            "affected_dates": [d["date"] for d in heat_days],
            "n_days": len(heat_days),
            "tmax_range": (min(tmax_values), max(tmax_values)),
            "message": (
                f"Heat stress forecast: {len(heat_days)}/{len(forecast_days)} days ({date_range}) have Tmax above "
                f"the modeled maximum tolerable temperature for {crop_name} "
                f"({txc}°C, Elnesr & Alazba 2016). "
                f"Forecast Tmax range: {min(tmax_values):.1f}-{max(tmax_values):.1f}°C. "
                f"{stage_advice}"
            ),
        })

    if cold_days:
        tmin_values = [d["tmin"] for d in cold_days]
        date_range = (
            cold_days[0]["date"] if len(cold_days) == 1
            else f"{cold_days[0]['date']} to {cold_days[-1]['date']}"
        )
        alerts.append({
            "level": "warning",
            "type": "cold_stress",
            "affected_dates": [d["date"] for d in cold_days],
            "n_days": len(cold_days),
            "tmin_range": (min(tmin_values), max(tmin_values)),
            "message": (
                f"Cold stress forecast: {len(cold_days)}/{len(forecast_days)} days ({date_range}) have Tmin below "
                f"the modeled minimum tolerable temperature for {crop_name} "
                f"({tnc}°C, Elnesr & Alazba 2016). "
                f"Forecast Tmin range: {min(tmin_values):.1f}-{max(tmin_values):.1f}°C. "
                f"Consider row cover or bringing container plants indoors overnight."
            ),
        })

    return alerts


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def get_plant_status(crop_name, location_name, planting_date_str,
                     known_locations=None, include_forecast=True):
    """
    Main Feature 3 entry point.

    Parameters:
      crop_name: one of SCAN_CROPS (e.g. 'Tomato', 'Potato')
      location_name: a known city name or (lat, lon) tuple
      planting_date_str: 'YYYY-MM-DD' or 'DD/MM/YYYY'
      include_forecast: set False to skip OpenWeatherMap (useful for testing)

    Returns a dict with:
      plant, location, planting_date, stage_info, care, alerts, limitations
    """
    if known_locations is None:
        from advisor import KNOWN_LOCATIONS
        known_locations = KNOWN_LOCATIONS

    if isinstance(location_name, str):
        key = location_name.strip().lower()
        if key not in known_locations:
            raise ValueError(f"Unknown location '{location_name}'")
        lat, lon = known_locations[key]
    else:
        lat, lon = location_name

    planting_date = parse_planting_date(planting_date_str)
    clim, elevation_m, _ = fetch_daily_climatology_full(lat, lon)

    # 1. Growth stage
    stage_info = get_current_stage(crop_name, planting_date, clim, elevation_m, lat)

    # 2. Care profile
    species = SPECIES_PROFILES.get(crop_name, {})
    care = {
        "watering_guidance": species.get("watering", "See care profile"),
        "sun": species.get("sun", "Full sun"),
        "ideal_temp_range_c": species.get("ideal_temp_range_c"),
    }
    if stage_info.get("viable") and not stage_info.get("season_complete"):
        care["current_stage_water_mm_per_day"] = stage_info["current_stage_etc_mm_per_day"]
        care["current_stage_liters_per_plant"] = stage_info["current_stage_liters_per_plant"]
        care["plants_per_m2_assumption"] = CROP_DB[crop_name]["plants_per_m2"]

    # 3. Forecast and alerts
    forecast = []
    alerts = []
    forecast_error = None
    if include_forecast:
        try:
            forecast = fetch_owm_forecast(lat, lon)
            stage_name = stage_info.get("stage_name", "unknown")
            alerts = generate_alerts(crop_name, stage_name, forecast)
        except RuntimeError as e:
            forecast_error = str(e)
        except requests.exceptions.RequestException as e:
            forecast_error = f"Weather forecast unavailable: {e}"

    return {
        "plant": crop_name,
        "location": location_name,
        "coordinates": (lat, lon),
        "planting_date": planting_date_str,
        "stage_info": stage_info,
        "care": care,
        "forecast": forecast,
        "alerts": alerts,
        "forecast_error": forecast_error,
        "limitations": [
            "ETc figures are crop water use, not irrigation requirement (no soil or efficiency losses applied)",
            "Stage position uses calendar days elapsed against climatological GDD-derived stage lengths -- "
            "a typical-year approximation; real GDD accumulation this season may differ if current year "
            "is significantly warmer or cooler than the 2014-2023 climatological baseline",
            "Temperature alerts use Elnesr & Alazba 2016 thresholds -- sourced, but conservative "
            "for some crops (e.g. potato, Txc=27°C); brief exceedances may not cause real damage",
            "Disease risk alerts not implemented: no sourced crop-disease-weather relationships "
            "in this codebase -- deferred pending real epidemiological sources",
            "Rainfall not subtracted from water need: OpenWeatherMap precipitation data is not "
            "reliable at the accuracy needed for irrigation planning",
        ],
    }


def print_plant_status(result):
    """Human-readable output for terminal testing."""
    print(f"\n=== Plant Status: {result['plant']} at {result['location']} ===")
    print(f"    Planted: {result['planting_date']}")

    si = result["stage_info"]
    if not si.get("viable"):
        print(f"    {si.get('reason', 'Not viable at this location.')}")
        return

    if si.get("season_complete"):
        print(f"\n  Season complete.")
        print(f"  Harvest date:      {si.get('harvest_date', '?')}")
        print(f"  Days in ground:    {si['days_since_planting']} "
              f"(season length: {si['total_season_days']} days)")
        print(f"\n  Completed season water use (ETc):")
        print(f"    Total: {si['seasonal_etc_mm']:.0f} mm  "
              f"= {si['seasonal_m3_per_ha']:.0f} m³/ha")
        print(f"\n  Stage breakdown:")
        for s in si["all_stages"]:
            ppm2 = result["care"].get("plants_per_m2_assumption") or CROP_DB[result["plant"]]["plants_per_m2"]
            print(f"    {s['stage']:<13} {s['start']} -- {s['end']}  "
                  f"{s['etc_mm_per_day']:.2f} mm/day  "
                  f"({s['etc_mm_per_day']/ppm2:.2f} L/plant/day)")
    else:
        print(f"\n  Growth stage:  {si['stage_name'].upper()}")
        print(f"  Stage dates:   {si['stage_start_date']} -- {si['stage_end_date']}")
        print(f"  Progress:      Day {si['days_into_stage']} of "
              f"{si['days_into_stage'] + si['days_remaining_in_stage']} "
              f"({si['days_remaining_in_stage']} days remaining in this stage)")
        print(f"  Next stage:    {si['next_stage']} "
              f"(around {si['stage_end_date']})")
        print(f"  Season:        Day {si['days_since_planting']} of "
              f"{si['total_season_days']} total "
              f"(harvest around {si['harvest_date']})")

        care = result["care"]
        print(f"\n  Water need (this stage):")
        if "current_stage_water_mm_per_day" in care:
            print(f"    {care['current_stage_water_mm_per_day']:.2f} mm/day  "
                  f"({care['current_stage_liters_per_plant']:.2f} L per plant, "
                  f"assuming {care['plants_per_m2_assumption']} plants/m²)")
        print(f"  General watering: {care['watering_guidance']}")

    if result["forecast_error"]:
        print(f"\n  Forecast: {result['forecast_error']}")
    elif result["forecast"]:
        print(f"\n  5-day forecast:")
        for day in result["forecast"]:
            print(f"    {day['date']}: {day['tmax']:.1f}°C / {day['tmin']:.1f}°C  "
                  f"humidity {day['humidity_max']}%  {day['summary']}")

    if result["alerts"]:
        print(f"\n  ⚠️  ALERTS ({len(result['alerts'])}):")
        for a in result["alerts"]:
            print(f"    [{a['level'].upper()}] {a['type'].replace('_', ' ').title()}: "
                  f"{a['message']}")
    elif result["forecast"] and not result["forecast_error"]:
        print(f"\n  ✓ No temperature alerts for the next 5 days.")

    print(f"\n  Limitations:")
    for lim in result["limitations"]:
        print(f"    - {lim}")


if __name__ == "__main__":
    # Test 1: active season (should show current stage)
    print("Test 1: Active season...")
    result = get_plant_status(
        crop_name="Tomato",
        location_name="riyadh",
        planting_date_str="2026-09-01",
        include_forecast=True,
    )
    print_plant_status(result)

    print("\n" + "=" * 70)

    # Test 2: completed season (should show season summary, not blank water)
    print("Test 2: Completed season...")
    result2 = get_plant_status(
        crop_name="Tomato",
        location_name="riyadh",
        planting_date_str="2025-09-28",
        include_forecast=False,
    )
    print_plant_status(result2)

    print("\n" + "=" * 70)

    # Test 3: future planting date (should show clear error, not negative days)
    print("Test 3: Future planting date guard...")
    result3 = get_plant_status(
        crop_name="Potato",
        location_name="najran",
        planting_date_str="2026-12-01",
        include_forecast=False,
    )
    print_plant_status(result3)