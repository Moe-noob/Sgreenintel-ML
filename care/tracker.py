"""
Feature 3: Personalized Plant Care Tracker.

Given a saved plant (crop, city, planting date), this module:
1. Determines the current growth stage using GDD-based simulation
   from the same climatological baseline as Feature 2 (ensuring
   consistency between the planning and tracking tools).
2. Reports the current stage's water requirement and care needs.
3. Fetches a 5-day weather forecast (Open-Meteo) and checks it against
   Elnesr & Alazba 2016 temperature-tolerance thresholds.
4. Computes a LIVE daily ETc for each forecast day using full FAO-56
   Penman-Monteith (same equation, same Kc curve, same elevation and
   latitude as the climatological baseline) and compares it against
   that baseline for the same calendar days -- isolating the weather
   difference between "typical year" and "what's actually forecast."
5. Raises specific, sourced alerts when forecast conditions exceed
   modeled tolerance thresholds -- consolidated by type, not one per day.

Why Open-Meteo, not OpenWeatherMap: Open-Meteo's forecast includes
shortwave solar radiation (shortwave_radiation_sum), which OWM's free
tier does not. Without real solar radiation, a live Penman-Monteith
ETc isn't possible -- only the cruder, temperature-only Hargreaves-
Samani method, which FAO-56 itself documents can diverge from
Penman-Monteith by up to ~30% in extreme arid conditions (confirmed
directly for Riyadh: -22% to -34% across all 12 months when checked
against this codebase's own Penman-Monteith implementation). Open-Meteo
gives us the same equation, same accuracy class, for both the live and
baseline figures. It also requires no API key, unlike OpenWeatherMap.
(hargreaves_et0_doy() remains in evapotranspiration.py as a fallback
if Open-Meteo is ever unreachable -- not used in the primary path.)

What this does NOT do:
- Convert ETc to irrigation requirement (no soil/efficiency modelling)
- Predict disease risk from weather (no sourced disease-weather
  relationships exist in this codebase -- deferred)
- Control irrigation hardware (no IoT scope)
- Apply rainfall offset (forecast precipitation data is not reliable
  at the accuracy needed for irrigation planning)
- Re-adjust the FAO-56 Eq.62/65 Kc wind/humidity correction per forecast
  day -- that correction represents typical stage-level conditions by
  design (a single representative value), not day-to-day noise; the
  live comparison reuses the same adjusted Kc as the climatological run
"""

import datetime
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "heatmap"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from nasa_power import fetch_daily_climatology_full
from season_simulator import simulate_annual_season, doy_to_date, STAGES
from crop_database import CROP_DB, SCAN_CROPS, CROP_COEFFICIENTS
from crop_coefficients import kc_on_day
from evapotranspiration import penman_monteith_et0_doy, wind_speed_2m
from aridity import conditioned_dewpoint
from care_profiles import CLASS_INFO, SPECIES_PROFILES

OPEN_METEO_BASE = "https://api.open-meteo.com/v1/forecast"

# WMO weather codes Open-Meteo returns -- common subset, arid-climate relevant
WMO_CODES = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "depositing rime fog",
    51: "light drizzle", 53: "moderate drizzle", 55: "dense drizzle",
    61: "slight rain", 63: "moderate rain", 65: "heavy rain",
    71: "slight snow", 73: "moderate snow", 75: "heavy snow",
    80: "slight rain showers", 81: "moderate rain showers", 82: "violent rain showers",
    95: "thunderstorm", 96: "thunderstorm with slight hail", 99: "thunderstorm with heavy hail",
}


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
    climatological baseline.

    Returns a dict with stage info, water need, and season summary.
    """
    today = datetime.date.today()

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

    run = simulate_annual_season(crop_name, clim, elevation_m, latitude_deg, planting_doy)

    if not run["viable"]:
        return {
            "viable": False,
            "reason": run.get("reason", "GDD requirement not met at this location"),
            "days_since_planting": days_since_planting,
        }

    stage_lengths = run["stage_lengths"]
    total_days = run["total_days"]

    if days_since_planting >= total_days:
        return {
            "viable": True,
            "season_complete": True,
            "days_since_planting": days_since_planting,
            "total_season_days": total_days,
            "harvest_date": (planting_date + datetime.timedelta(days=total_days)).strftime("%b %d, %Y"),
            "all_stages": run["stages"],
            "stage_lengths": stage_lengths,
            "seasonal_etc_mm": run["seasonal_etc_mm"],
            "seasonal_m3_per_ha": run["seasonal_m3_per_ha"],
            "kc_mid_adjusted": run["kc_mid_adjusted"],
            "kc_end_adjusted": run["kc_end_adjusted"],
        }

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
                "current_stage_liters_per_plant": None,   # filled in by get_plant_status only if the user gives a density
                "all_stages": run["stages"],
                "stage_lengths": stage_lengths,
                "seasonal_etc_mm": run["seasonal_etc_mm"],
                "seasonal_m3_per_ha": run["seasonal_m3_per_ha"],
                "kc_mid_adjusted": run["kc_mid_adjusted"],
                "kc_end_adjusted": run["kc_end_adjusted"],
            }
        cumulative += stage_days

    return {"viable": True, "season_complete": True, "days_since_planting": days_since_planting}


# ---------------------------------------------------------------------------
# Open-Meteo forecast
# ---------------------------------------------------------------------------

def fetch_open_meteo_forecast(lat, lon):
    """
    Fetches a 5-day daily forecast from Open-Meteo: temperature, dewpoint,
    wind, solar radiation, and humidity -- everything a full FAO-56
    Penman-Monteith ET0 calculation needs, plus a human-readable summary.

    No API key required. Raises requests.exceptions.RequestException on
    network failure.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": ",".join([
            "temperature_2m_max", "temperature_2m_min", "temperature_2m_mean",
            "relative_humidity_2m_min", "relative_humidity_2m_max",
            "wind_speed_10m_mean", "shortwave_radiation_sum",
            "dewpoint_2m_mean", "weathercode",
        ]),
        "timezone": "auto",
        "forecast_days": 5,
    }
    r = requests.get(OPEN_METEO_BASE, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()

    d = data["daily"]
    days = []
    for i, date_str in enumerate(d["time"]):
        wind_10m_ms = d["wind_speed_10m_mean"][i] / 3.6  # km/h -> m/s
        wind_2m_ms = wind_speed_2m(wind_10m_ms)  # FAO-56 Eq.47: 10m -> 2m height

        days.append({
            "date": date_str,
            "tmax": d["temperature_2m_max"][i],
            "tmin": d["temperature_2m_min"][i],
            "tmean": d["temperature_2m_mean"][i],
            "dewpoint_c": d["dewpoint_2m_mean"][i],
            "wind_speed_ms": wind_2m_ms,
            "solar_radiation_mj": d["shortwave_radiation_sum"][i],
            "humidity_min": d["relative_humidity_2m_min"][i],
            "humidity_max": d["relative_humidity_2m_max"][i],
            "summary": WMO_CODES.get(d["weathercode"][i], f"weather code {d['weathercode'][i]}"),
        })
    return days


# ---------------------------------------------------------------------------
# Live ETc: full Penman-Monteith, same Kc curve, same day, vs. climatology
# ---------------------------------------------------------------------------

def attach_live_etc(forecast_days, stage_info, crop_name, clim, elevation_m, latitude_deg, plants_per_m2=None):
    """
    For each forecast day, computes:
      - live_etc_mm_day: FAO-56 Penman-Monteith ET0 from ACTUAL forecast
        weather (Open-Meteo), x the crop's Kc for that exact day
      - baseline_etc_mm_day: the same Kc, but ET0 from the CLIMATOLOGICAL
        normal for that same calendar day (same equation, same
        elevation, same latitude -- only the weather-data source differs)

    Both figures use the SAME adjusted Kc_mid/Kc_end already computed
    for the climatological season run (FAO-56 Eq.62/65 represents
    typical stage-level conditions, not something to re-derive per day)
    and the SAME stored elevation/latitude for both calculations, so the
    only variable isolated is: actual forecast weather vs. 10-year normal.

    Mutates each day dict in place (adds live_etc_mm_day, baseline_etc_mm_day,
    live_etc_liters_per_plant, baseline_etc_liters_per_plant) and returns
    a week-level summary dict.
    """
    stage_lengths = stage_info["stage_lengths"]
    kc_ini = CROP_COEFFICIENTS[crop_name]["kc_ini"]
    kc_mid_adj = stage_info["kc_mid_adjusted"]
    kc_end_adj = stage_info["kc_end_adjusted"]
    aT = clim[0].get("aridity_aT", 0.0)   # FAO-56 Rev.1 Eq. 2.6 humidity conditioning: same as the baseline climatology
    start_day_index = stage_info["days_since_planting"]  # today's 0-based day-in-season

    live_values, baseline_values = [], []

    for i, day in enumerate(forecast_days):
        day_index = start_day_index + i
        kc = kc_on_day(day_index, stage_lengths, kc_ini, kc_mid_adj, kc_end_adj)

        forecast_date = datetime.datetime.strptime(day["date"], "%Y-%m-%d").date()
        doy = date_to_doy(forecast_date)

        # Live ET0 from actual forecast weather
        et0_live = penman_monteith_et0_doy(
            temp_mean_c=day["tmean"], temp_max_c=day["tmax"], temp_min_c=day["tmin"],
            dewpoint_c=conditioned_dewpoint(day["dewpoint_c"], day["tmin"], aT), wind_speed_ms=day["wind_speed_ms"],
            solar_radiation_mj=day["solar_radiation_mj"],
            elevation_m=elevation_m, latitude_deg=latitude_deg, day_of_year=doy,
        )

        # Baseline ET0 from the climatological normal for the same day-of-year
        clim_day = clim[doy - 1]
        et0_baseline = penman_monteith_et0_doy(
            temp_mean_c=clim_day["temp_c"], temp_max_c=clim_day["temp_max_c"],
            temp_min_c=clim_day["temp_min_c"], dewpoint_c=clim_day["dewpoint_c"],
            wind_speed_ms=clim_day["wind_speed_ms"], solar_radiation_mj=clim_day["solar_radiation_mj"],
            elevation_m=elevation_m, latitude_deg=latitude_deg, day_of_year=doy,
        )

        live_etc = kc * et0_live
        baseline_etc = kc * et0_baseline

        day["live_etc_mm_day"] = round(live_etc, 2)
        day["baseline_etc_mm_day"] = round(baseline_etc, 2)
        day["live_etc_liters_per_plant"] = round(live_etc / plants_per_m2, 2) if plants_per_m2 else None
        day["baseline_etc_liters_per_plant"] = round(baseline_etc / plants_per_m2, 2) if plants_per_m2 else None

        live_values.append(live_etc)
        baseline_values.append(baseline_etc)

    avg_live = sum(live_values) / len(live_values)
    avg_baseline = sum(baseline_values) / len(baseline_values)
    pct_diff = ((avg_live - avg_baseline) / avg_baseline * 100) if avg_baseline > 0 else 0

    direction = "above" if pct_diff >= 0 else "below"
    summary = {
        "avg_live_etc_mm_day": round(avg_live, 2),
        "avg_baseline_etc_mm_day": round(avg_baseline, 2),
        "pct_diff": round(pct_diff, 1),
        "description": (
            f"This week's forecast water use is running approximately "
            f"{abs(round(pct_diff))}% {direction} the typical rate for this growth stage."
        ),
    }
    return summary


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
                     known_locations=None, include_forecast=True, plants_per_m2=None):
    """
    Main Feature 3 entry point.

    Parameters:
      crop_name: one of SCAN_CROPS (e.g. 'Tomato', 'Potato')
      location_name: a known city name or (lat, lon) tuple
      planting_date_str: 'YYYY-MM-DD' or 'DD/MM/YYYY'
      include_forecast: set False to skip the live forecast (useful for testing)

    Returns a dict with:
      plant, location, planting_date, stage_info, care, forecast, alerts,
      live_vs_baseline, forecast_error, limitations
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
        "watering_guidance": species.get("watering", "No crop-specific care notes yet; follow the water amount shown."),
        "sun": species.get("sun"),
        "ideal_temp_range_c": species.get("ideal_temp_range_c"),
    }
    if stage_info.get("viable") and not stage_info.get("season_complete"):
        care["current_stage_water_mm_per_day"] = stage_info["current_stage_etc_mm_per_day"]
        if plants_per_m2:      # litres per plant only for a density the user supplied; no default spacing is assumed
            care["current_stage_liters_per_plant"] = stage_info["current_stage_etc_mm_per_day"] / plants_per_m2
            care["plants_per_m2_user"] = plants_per_m2

    # 3. Forecast, live ETc, and alerts -- only meaningful for an active season.
    #    A completed season has no living plant left to weather-protect.
    forecast = []
    alerts = []
    live_vs_baseline = None
    forecast_error = None
    active_season = stage_info.get("viable") and not stage_info.get("season_complete")

    if include_forecast and active_season:
        try:
            forecast = fetch_open_meteo_forecast(lat, lon)
            live_vs_baseline = attach_live_etc(forecast, stage_info, crop_name, clim, elevation_m, lat, plants_per_m2)
            alerts = generate_alerts(crop_name, stage_info.get("stage_name", "unknown"), forecast)
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
        "live_vs_baseline": live_vs_baseline,
        "alerts": alerts,
        "forecast_error": forecast_error,
        "limitations": [
            "ETc figures are crop water use, not irrigation requirement (no soil or efficiency losses applied)",
            "Stage position uses calendar days elapsed against climatological GDD-derived stage lengths -- "
            "a typical-year approximation; real GDD accumulation this season may differ if current year "
            "is significantly warmer or cooler than the climatological baseline",
            "Live forecast ETc and the climatological baseline both use full FAO-56 Penman-Monteith and the "
            "same crop coefficient for the same calendar day; only the weather-data source differs (actual "
            "Open-Meteo forecast vs. 10-year climatological normal), isolating that one variable",
            "Both live and baseline calculations use the site elevation (Copernicus 90 m DEM, the DEM "
            "Open-Meteo downscales its forecast to); baseline temperatures are adjusted from the NASA "
            "grid-cell elevation to the site with a standard 6.5 C/km lapse rate",
            "Reference ET0 uses FAO-56 Rev.1 humidity conditioning for dry-site weather data (Eq. 2.6) in both the live "
            "and the baseline calculation; wind speed is not independently verified, so absolute litres and mm are "
            "uncertain by roughly 15% (our estimate)",
            "Temperature alerts use Elnesr & Alazba 2016 thresholds -- sourced, but conservative "
            "for some crops (e.g. potato, Txc=27°C); brief exceedances may not cause real damage",
            "Disease risk alerts not implemented: no sourced crop-disease-weather relationships "
            "in this codebase -- deferred pending real epidemiological sources",
            "Rainfall not subtracted from water need: forecast precipitation data is not "
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
            print(f"    {s['stage']:<13} {s['start']} -- {s['end']}  "
                  f"{s['etc_mm_per_day']:.2f} mm/day")
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
        print(f"\n  Water need (climatological baseline, this stage):")
        if "current_stage_water_mm_per_day" in care:
            line = f"    {care['current_stage_water_mm_per_day']:.2f} mm/day"
            if "current_stage_liters_per_plant" in care:
                line += f"  ({care['current_stage_liters_per_plant']:.2f} L per plant at {care['plants_per_m2_user']} plants/m²)"
            print(line)
        print(f"  General watering: {care['watering_guidance']}")

    if result["forecast_error"]:
        print(f"\n  Forecast: {result['forecast_error']}")
    elif result["forecast"]:
        print(f"\n  5-day forecast (live ETc vs. climatological baseline):")
        for day in result["forecast"]:
            print(f"    {day['date']}: {day['tmax']:.1f}°C / {day['tmin']:.1f}°C  "
                  f"{day['summary']:<20s} live={day['live_etc_mm_day']:.2f} mm/day  "
                  f"baseline={day['baseline_etc_mm_day']:.2f} mm/day")
        if result["live_vs_baseline"]:
            print(f"\n  {result['live_vs_baseline']['description']}")

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
    print("Test 1: Active season (live ETc + forecast should show)...")
    result = get_plant_status(
        crop_name="Tomato",
        location_name="riyadh",
        planting_date_str="2026-09-01",
        include_forecast=True,
    )
    print_plant_status(result)

    print("\n" + "=" * 70)

    print("Test 2: Completed season (no forecast/live ETc -- no living plant)...")
    result2 = get_plant_status(
        crop_name="Tomato",
        location_name="riyadh",
        planting_date_str="2025-09-28",
        include_forecast=True,  # should still be skipped, season is complete
    )
    print_plant_status(result2)

    print("\n" + "=" * 70)

    print("Test 3: Future planting date guard...")
    result3 = get_plant_status(
        crop_name="Potato",
        location_name="najran",
        planting_date_str="2026-12-01",
        include_forecast=False,
    )
    print_plant_status(result3)