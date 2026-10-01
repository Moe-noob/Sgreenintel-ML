"""
NASA POWER API client -- DAILY climatology version.

Why this changed
----------------
The previous version mixed two reference periods (the POWER climatology
endpoint for T2M/dew/wind/radiation, and 2016-2025 daily data for
Tmax/Tmin) and never filtered POWER's -999 fill value. The planting-date
simulator also needs DAILY resolution: FAO-56 growth stages are 20-40
days long, so monthly means cannot place them.

What this does
--------------
1. Pulls one 10-year block (2016-2025) of DAILY data for every variable
   the pipeline needs, from a single endpoint / single period.
2. Drops POWER fill values (-999) before averaging.
3. Averages by day-of-year (1..365; 29 Feb is folded into day 59) to
   give a 365-day climatology, then applies a centred +/-7-day running
   mean to remove single-day noise (a standard smoothing step; the
   window is a stated choice, not a sourced constant).
4. Caches the result to disk (heatmap/cache/) so repeated runs and the
   7-city test loop do not hit the API every time.
5. Still exposes fetch_climate_data(lat, lon) returning MONTHLY means
   for any old code that expects it -- but now derived from the same
   daily record, so everything is internally consistent.

POWER parameter notes
---------------------
T2M_MAX / T2M_MIN on the DAILY endpoint are the true daily max/min
(the earlier docstring's warning applied to the CLIMATOLOGY endpoint,
where those names return extremes). WS2M is already at 2 m (no FAO-56
Eq. 47 conversion needed). ALLSKY_SFC_SW_DWN units are read from the
response metadata and converted to MJ m-2 day-1 if needed.
"""

import json
import time
import warnings
from collections import defaultdict
from pathlib import Path

import requests

DAILY_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
DAILY_PARAMETERS = "T2M,T2M_MAX,T2M_MIN,T2MDEW,WS2M,ALLSKY_SFC_SW_DWN,PRECTOTCORR"
DAILY_START = "20160101"
DAILY_END = "20251231"          # 10-year window for stable averages, refreshed Sep 2026
                                  # (previously 2014-2023; shifted forward as more
                                  # current NASA POWER data became available)
FILL_VALUE_THRESHOLD = -900     # POWER uses -999 for missing data
SMOOTHING_HALF_WINDOW = 7       # +/- days for the running mean

CACHE_DIR = Path(__file__).resolve().parent / "cache"

MONTH_KEYS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
              "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
# Day-of-year ranges for each month in a 365-day year (1-based, inclusive)
MONTH_DOY_RANGES = {
    "JAN": (1, 31), "FEB": (32, 59), "MAR": (60, 90), "APR": (91, 120),
    "MAY": (121, 151), "JUN": (152, 181), "JUL": (182, 212), "AUG": (213, 243),
    "SEP": (244, 273), "OCT": (274, 304), "NOV": (305, 334), "DEC": (335, 365),
}
MID_MONTH_DAY = {
    "JAN": 15, "FEB": 46, "MAR": 74, "APR": 105, "MAY": 135, "JUN": 166,
    "JUL": 196, "AUG": 227, "SEP": 258, "OCT": 288, "NOV": 319, "DEC": 349,
}

KWH_TO_MJ = 3.6

# Field names used throughout the pipeline
FIELDS = ["temp_c", "temp_max_c", "temp_min_c", "dewpoint_c",
          "wind_speed_ms", "solar_radiation_mj", "precip_mm_day"]
_POWER_TO_FIELD = {
    "T2M": "temp_c", "T2M_MAX": "temp_max_c", "T2M_MIN": "temp_min_c",
    "T2MDEW": "dewpoint_c", "WS2M": "wind_speed_ms",
    "ALLSKY_SFC_SW_DWN": "solar_radiation_mj", "PRECTOTCORR": "precip_mm_day",
}


def _radiation_to_mj(value, unit_string):
    u = (unit_string or "").lower()
    if "mj" in u:
        return value
    if "kw" in u:
        return value * KWH_TO_MJ
    raise ValueError(f"Unrecognised radiation unit '{unit_string}' -- check API response")


def _elevation_from_payload(payload):
    try:
        coords = payload["geometry"]["coordinates"]
        if len(coords) >= 3 and coords[2] is not None:
            return float(coords[2])
    except (KeyError, TypeError, IndexError):
        pass
    return 0.0


def _doy_365(date_key):
    """'YYYYMMDD' -> day of year in a 365-day calendar (29 Feb folded to day 59)."""
    import datetime as _dt
    d = _dt.date(int(date_key[:4]), int(date_key[4:6]), int(date_key[6:8]))
    doy = d.timetuple().tm_yday
    leap = d.year % 4 == 0 and (d.year % 100 != 0 or d.year % 400 == 0)
    if leap and doy >= 60:       # after 29 Feb in a leap year
        doy -= 1
    return doy


def _smooth_circular(values, half_window):
    """Centred running mean on a circular (day-of-year) series."""
    n = len(values)
    out = []
    w = 2 * half_window + 1
    for i in range(n):
        s = 0.0
        for k in range(-half_window, half_window + 1):
            s += values[(i + k) % n]
        out.append(s / w)
    return out


def _cache_path(lat, lon):
    CACHE_DIR.mkdir(exist_ok=True)
    return CACHE_DIR / f"power_daily_v2_{lat:.2f}_{lon:.2f}_{DAILY_START}_{DAILY_END}.json"


def fetch_daily_raw(lat, lon, retries=3, delay=2):
    """One API call: 10 years of daily data for all parameters."""
    params = {
        "parameters": DAILY_PARAMETERS,
        "community": "AG",
        "longitude": lon,
        "latitude": lat,
        "start": DAILY_START,
        "end": DAILY_END,
        "format": "JSON",
    }
    for attempt in range(retries):
        try:
            r = requests.get(DAILY_URL, params=params, timeout=120)
            r.raise_for_status()
            return r.json()
        except (requests.exceptions.RequestException, ValueError) as e:
            print(f"  POWER daily attempt {attempt + 1} failed for ({lat}, {lon}): {e}")
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                raise


def build_daily_climatology(payload):
    """
    Turns a POWER daily payload into a 365-entry list of dicts (index 0 =
    1 Jan) plus elevation. Fill values are dropped; a day with no valid
    data for a variable raises, rather than silently producing garbage.
    """
    raw = payload["properties"]["parameter"]
    rad_unit = (payload.get("parameters", {}).get("ALLSKY_SFC_SW_DWN", {}) or {}).get("units", "")
    elevation = _elevation_from_payload(payload)

    sums = {f: defaultdict(float) for f in FIELDS}
    counts = {f: defaultdict(int) for f in FIELDS}
    dropped = defaultdict(int)

    for power_name, field in _POWER_TO_FIELD.items():
        series = raw[power_name]
        for date_key, value in series.items():
            if value is None or value <= FILL_VALUE_THRESHOLD:
                dropped[field] += 1
                continue
            if field == "solar_radiation_mj":
                value = _radiation_to_mj(value, rad_unit)
            doy = _doy_365(date_key)
            sums[field][doy] += value
            counts[field][doy] += 1

    # Raw per-year daily Tmax/Tmin (unsmoothed) for temperature-tolerance
    # exceedance statistics. Index 0 = 1 Jan; None where POWER had no value.
    raw_years = {}
    for power_name, field in (("T2M_MAX", "temp_max_c"), ("T2M_MIN", "temp_min_c")):
        for date_key, value in raw[power_name].items():
            if value is None or value <= FILL_VALUE_THRESHOLD:
                continue
            year = date_key[:4]
            raw_years.setdefault(year, {"temp_max_c": [None] * 365, "temp_min_c": [None] * 365})
            raw_years[year][field][_doy_365(date_key) - 1] = value

    clim = []
    for doy in range(1, 366):
        entry = {"doy": doy}
        for f in FIELDS:
            if counts[f][doy] == 0:
                raise ValueError(f"No valid POWER data for {f} on day-of-year {doy}")
            entry[f] = sums[f][doy] / counts[f][doy]
        clim.append(entry)

    # Smooth each field on the circular year
    for f in FIELDS:
        smoothed = _smooth_circular([c[f] for c in clim], SMOOTHING_HALF_WINDOW)
        for c, v in zip(clim, smoothed):
            c[f] = v

    meta = {"elevation_m": elevation, "dropped_fill_values": dict(dropped),
            "period": f"{DAILY_START}-{DAILY_END}", "smoothing_half_window_days": SMOOTHING_HALF_WINDOW,
            "raw_years": raw_years}
    return clim, meta


def _fetch_uncorrected(lat, lon, use_cache=True):
    """
    NASA grid-cell climatology exactly as POWER reports it (temperatures at the CELL elevation).
    Returns (climatology, elevation_m, raw_years).
    climatology: list of 365 dicts (smoothed typical year) with keys doy,
      temp_c, temp_max_c, temp_min_c, dewpoint_c, wind_speed_ms,
      solar_radiation_mj, precip_mm_day.
    raw_years: {year: {"temp_max_c": [365], "temp_min_c": [365]}} unsmoothed,
      used only for temperature-tolerance exceedance statistics.
    """
    path = _cache_path(lat, lon)
    if use_cache and path.exists():
        with open(path) as fh:
            cached = json.load(fh)
        return cached["climatology"], cached["meta"]["elevation_m"], cached["meta"].get("raw_years", {})

    payload = fetch_daily_raw(lat, lon)
    clim, meta = build_daily_climatology(payload)
    with open(path, "w") as fh:
        json.dump({"climatology": clim, "meta": meta}, fh)
    return clim, meta["elevation_m"], meta["raw_years"]


def _fetch_elevation_corrected(lat, lon, use_cache=True, correct_elevation=True):
    """
    Returns (climatology, elevation_m, raw_years), as _fetch_uncorrected, but by default with temperatures
    and dewpoint adjusted from the NASA grid-cell elevation to the true site elevation (Copernicus 90 m DEM
    via Open-Meteo) using a standard lapse rate -- see site_elevation.py. The returned elevation_m is then
    the SITE elevation. If the site elevation cannot be fetched, the uncorrected cell climate is returned
    with a warning. Pass correct_elevation=False for the raw NASA cell values.
    """
    clim, elevation_m, raw_years = _fetch_uncorrected(lat, lon, use_cache)
    if not correct_elevation:
        return clim, elevation_m, raw_years
    try:
        import site_elevation as _site
    except ImportError:
        return clim, elevation_m, raw_years
    site_m = _site.fetch_site_elevation_m(lat, lon)
    if site_m is None:
        warnings.warn(f"Site elevation unavailable for ({lat}, {lon}); using uncorrected NASA cell climate "
                      f"({elevation_m:.0f} m)", RuntimeWarning, stacklevel=2)
        return clim, elevation_m, raw_years
    new_clim, new_raw, info = _site.correct_climatology(clim, raw_years, elevation_m, site_m)
    if info is None:                      # difference too small to matter
        return clim, elevation_m, raw_years
    return new_clim, site_m, new_raw


def fetch_daily_climatology_full(lat, lon, use_cache=True, correct_elevation=True, correct_aridity=True):
    """
    Returns (climatology, elevation_m, raw_years). By default the NASA grid-cell climate is
      (1) adjusted to the site elevation (site_elevation.py), and
      (2) conditioned for dry-site humidity: the dewpoint becomes max(NASA dewpoint, Tmin - aT) following
          FAO-56 Rev.1 Sec. 2.5.2, Eq. 2.6, with aT set by the location's UNEP aridity index (aridity.py).
          Reanalysis humidity over dry land is not "reference" humidity and inflates ET0 by roughly 6-13 %.
    The source dewpoint is kept as dewpoint_raw_c and the aT used as aridity_aT on every day.
    Pass correct_aridity=False for the unconditioned dewpoint, correct_elevation=False for raw cell temperatures.
    The cache always holds the raw NASA values; both corrections are applied after loading.
    """
    clim, elevation_m, raw_years = _fetch_elevation_corrected(lat, lon, use_cache, correct_elevation)
    if not correct_aridity:
        return clim, elevation_m, raw_years
    try:
        import aridity as _arid
    except ImportError:                      # aridity.py not installed: behave as before
        return clim, elevation_m, raw_years
    new_clim, _info = _arid.condition_climatology(clim)
    return new_clim, elevation_m, raw_years


def fetch_daily_climatology(lat, lon, use_cache=True):
    """Backward-compatible: (climatology, elevation_m)."""
    clim, elev, _ = fetch_daily_climatology_full(lat, lon, use_cache)
    return clim, elev


def monthly_from_daily(clim):
    """Monthly means computed from the daily climatology (for legacy callers)."""
    monthly = {}
    for m, (a, b) in MONTH_DOY_RANGES.items():
        days = clim[a - 1:b]
        monthly[m] = {f: sum(d[f] for d in days) / len(days) for f in FIELDS}
        monthly[m]["humidity_pct"] = None  # RH2M no longer fetched; RHmin is derived from dew point
    return monthly


def fetch_climate_data(lat, lon):
    """Backward-compatible: (monthly dict, elevation). Same data source as the daily climatology."""
    clim, elevation = fetch_daily_climatology(lat, lon)
    return monthly_from_daily(clim), elevation


if __name__ == "__main__":
    print("Testing with Riyadh (24.71, 46.68)...")
    clim, elevation = fetch_daily_climatology(24.71, 46.68)
    print(f"Elevation: {elevation} m, {len(clim)} days")
    for d in (15, 105, 196, 288):
        c = clim[d - 1]
        print(f"  DOY {d:3d}: Tmean={c['temp_c']:.1f} Tmax={c['temp_max_c']:.1f} Tmin={c['temp_min_c']:.1f} "
              f"Tdew={c['dewpoint_c']:.1f} u2={c['wind_speed_ms']:.2f} Rs={c['solar_radiation_mj']:.1f}")
    m = monthly_from_daily(clim)
    print("  JAN monthly Tmax/Tmin:", round(m['JAN']['temp_max_c'], 2), round(m['JAN']['temp_min_c'], 2))