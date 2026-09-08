"""
NASA POWER API client.

Climatology endpoint: T2M (mean temp), T2MDEW (dew point -- used to
derive real RHmin per FAO-56, replacing the earlier mean-humidity
approximation), RH2M (mean humidity, kept for reference), WS2M (wind,
already at 2m -- no conversion needed), ALLSKY_SFC_SW_DWN (solar
radiation), PRECTOTCORR (precipitation).

Tmax/Tmin: NASA POWER's climatology-endpoint T2M_MAX/T2M_MIN and
T2M_MAX_AVG/T2M_MIN_AVG were BOTH independently verified as incorrect
for this purpose -- neither represents a typical daily high/low.
T2M_MAX/T2M_MIN returns record extremes; T2M_MAX_AVG/T2M_MIN_AVG returns
the average of each year's single most extreme day, not the average
daily max/min. Verified against Riyadh January: extreme=32.19/-2.78,
_AVG=28.68/1.33, actual daily-averaged=22.01/7.88 (confirmed against
independent real-world climate normals). The only correct method is
pulling raw daily data and averaging it ourselves, which is what
fetch_daily_minmax_averages() does.
"""

import time
import requests
from collections import defaultdict

CLIMATOLOGY_URL = "https://power.larc.nasa.gov/api/temporal/climatology/point"
DAILY_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

CLIMATOLOGY_PARAMETERS = "T2M,T2MDEW,RH2M,WS2M,ALLSKY_SFC_SW_DWN,PRECTOTCORR"
DAILY_MINMAX_PARAMETERS = "T2M_MAX,T2M_MIN"
DAILY_START = "20140101"
DAILY_END = "20231231"  # 10-year window for stable averages

MONTH_KEYS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
              "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

KWH_TO_MJ = 3.6  # in case radiation comes back in kW-hr/m2/day instead of MJ/m2/day


def _radiation_unit(payload):
    meta = payload.get("parameters", {})
    entry = meta.get("ALLSKY_SFC_SW_DWN", {})
    return (entry.get("units") or "").lower()


def _radiation_to_mj(value, unit_string):
    if "mj" in unit_string:
        return value
    if "kw" in unit_string:
        return value * KWH_TO_MJ
    # Unknown unit -- don't silently guess wrong, surface it
    raise ValueError(f"Unrecognised radiation unit '{unit_string}' -- check API response before assuming a conversion")


def _elevation_from_payload(payload):
    try:
        coords = payload["geometry"]["coordinates"]
        if len(coords) >= 3 and coords[2] is not None:
            return float(coords[2])
    except (KeyError, TypeError, IndexError):
        pass
    return 0.0


def fetch_climatology(lat, lon, retries=3, delay=1):
    params = {
        "parameters": CLIMATOLOGY_PARAMETERS,
        "community": "AG",
        "longitude": lon,
        "latitude": lat,
        "format": "JSON",
    }
    for attempt in range(retries):
        try:
            response = requests.get(CLIMATOLOGY_URL, params=params, timeout=30)
            response.raise_for_status()
            payload = response.json()
            raw = payload["properties"]["parameter"]
            rad_unit = _radiation_unit(payload)
            elevation = _elevation_from_payload(payload)

            monthly = {}
            for month in MONTH_KEYS:
                monthly[month] = {
                    "temp_c": raw["T2M"][month],
                    "dewpoint_c": raw["T2MDEW"][month],
                    "humidity_pct": raw["RH2M"][month],
                    "wind_speed_ms": raw["WS2M"][month],
                    "solar_radiation_mj": _radiation_to_mj(raw["ALLSKY_SFC_SW_DWN"][month], rad_unit),
                    "precip_mm_day": raw["PRECTOTCORR"][month],
                }
            return monthly, elevation

        except (requests.exceptions.RequestException, KeyError) as e:
            print(f"  Climatology attempt {attempt+1} failed for ({lat}, {lon}): {e}")
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                raise


def fetch_daily_minmax_averages(lat, lon, retries=3, delay=1):
    params = {
        "parameters": DAILY_MINMAX_PARAMETERS,
        "community": "AG",
        "longitude": lon,
        "latitude": lat,
        "start": DAILY_START,
        "end": DAILY_END,
        "format": "JSON",
    }
    for attempt in range(retries):
        try:
            response = requests.get(DAILY_URL, params=params, timeout=60)
            response.raise_for_status()
            raw = response.json()["properties"]["parameter"]

            monthly_max = defaultdict(list)
            monthly_min = defaultdict(list)
            for date_key, value in raw["T2M_MAX"].items():
                monthly_max[date_key[4:6]].append(value)
            for date_key, value in raw["T2M_MIN"].items():
                monthly_min[date_key[4:6]].append(value)

            result = {}
            for i, month in enumerate(MONTH_KEYS):
                month_num = f"{i+1:02d}"
                result[month] = {
                    "temp_max_c": sum(monthly_max[month_num]) / len(monthly_max[month_num]),
                    "temp_min_c": sum(monthly_min[month_num]) / len(monthly_min[month_num]),
                }
            return result

        except (requests.exceptions.RequestException, KeyError, ZeroDivisionError) as e:
            print(f"  Daily attempt {attempt+1} failed for ({lat}, {lon}): {e}")
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                raise


def fetch_climate_data(lat, lon):
    """Combines climatology + daily-derived min/max, plus elevation."""
    climatology, elevation = fetch_climatology(lat, lon)
    daily_minmax = fetch_daily_minmax_averages(lat, lon)

    monthly = {}
    for month in MONTH_KEYS:
        monthly[month] = {**climatology[month], **daily_minmax[month]}

    return monthly, elevation


if __name__ == "__main__":
    print("Testing with Riyadh (24.71, 46.68)...")
    result, elevation = fetch_climate_data(24.71, 46.68)
    print(f"Elevation: {elevation}m\n")
    for month, v in result.items():
        print(f"  {month}: temp={v['temp_c']:.2f}, max={v['temp_max_c']:.2f}, min={v['temp_min_c']:.2f}, "
              f"dewpoint={v['dewpoint_c']:.2f}, humidity={v['humidity_pct']:.1f}%, "
              f"wind={v['wind_speed_ms']:.2f}m/s, radiation={v['solar_radiation_mj']:.2f}MJ, "
              f"precip={v['precip_mm_day']:.3f}")