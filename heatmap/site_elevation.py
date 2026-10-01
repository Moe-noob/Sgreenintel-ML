"""
Site-elevation correction for the NASA POWER climatology.

PROBLEM
-------
NASA POWER (MERRA-2) reports temperatures for a grid cell roughly 50-60 km
across, at the cell's MEAN elevation (returned as `elevation` in its payload).
In mountains the real site can sit a kilometre or more above that mean. Abha:
NASA cell 1,188 m, city about 2,093-2,270 m (WMO station 2,093 m; Wikipedia
2,270 m). The cell's July daily maximum is 36 C; Abha's WMO 1991-2020 normal is
31 C. Uncorrected, seasons come out too short and water use too high, and the
live-vs-typical comparison in Feature 3 compares real mountain weather (Open-
Meteo forecast, downscaled to the 90 m DEM) against lowland-cell climate.

METHOD
------
Standard lapse-rate adjustment from the cell elevation to the site elevation:
    temperature shift = -LAPSE_T   x (site - cell) / 1000
    dewpoint shift    = -LAPSE_DEW x (site - cell) / 1000
applied to daily mean, max and min temperature and to dewpoint, and to the
unsmoothed yearly Tmax/Tmin used for exceedance counts. Wind, solar radiation
and precipitation are NOT adjusted (stated simplification). Site pressure in
Penman-Monteith then uses the site elevation.

  LAPSE_T   = 6.5 C/km  ICAO standard-atmosphere environmental lapse rate.
  LAPSE_DEW = 2.0 C/km  approximate dewpoint lapse rate (a stated choice; the
                        usual quoted range is about 1.8-2 C/km).

SITE ELEVATION SOURCE
---------------------
Copernicus GLO-90 digital elevation model via Open-Meteo's free elevation API
(https://api.open-meteo.com/v1/elevation). Open-Meteo downscales its forecasts to
this same DEM, so the live forecast and this baseline refer to one elevation.

Corrections smaller than MIN_DELTA_M are skipped (under about 0.2 C).
"""

import json
import time
from pathlib import Path

import requests

ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"
LAPSE_T = 6.5          # C per km
LAPSE_DEW = 2.0        # C per km
MIN_DELTA_M = 25.0     # ignore elevation differences smaller than this
CACHE_DIR = Path(__file__).resolve().parent / "cache"


def _cache_path(lat, lon):
    return CACHE_DIR / f"site_elevation_{float(lat):.4f}_{float(lon):.4f}.json"


def fetch_site_elevation_m(lat, lon, retries=3, delay=2):
    """DEM elevation (m) at the coordinates, cached on disk. None if unavailable (failures are not cached)."""
    path = _cache_path(lat, lon)
    if path.exists():
        try:
            return float(json.loads(path.read_text(encoding="utf-8"))["elevation_m"])
        except Exception:
            pass
    for attempt in range(retries):
        try:
            response = requests.get(ELEVATION_URL, params={"latitude": lat, "longitude": lon}, timeout=15)
            response.raise_for_status()
            value = response.json()["elevation"][0]
            if value is None:
                return None
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"elevation_m": float(value),
                                        "source": "Copernicus GLO-90 via Open-Meteo elevation API"}),
                            encoding="utf-8")
            return float(value)
        except Exception:
            if attempt < retries - 1:
                time.sleep(delay)
    return None


def lapse_shift_c(cell_elevation_m, site_elevation_m, lapse=LAPSE_T):
    """Temperature change (C) when moving from the cell elevation to the site elevation."""
    return -lapse * (site_elevation_m - cell_elevation_m) / 1000.0


def correct_climatology(clim, raw_years, cell_elevation_m, site_elevation_m):
    """
    Returns (new_clim, new_raw_years, info). Inputs are not modified. `info` is None (and the inputs are
    returned unchanged) when the elevation difference is below MIN_DELTA_M.
    """
    dz = site_elevation_m - cell_elevation_m
    if abs(dz) < MIN_DELTA_M:
        return clim, raw_years, None
    dt_c = lapse_shift_c(cell_elevation_m, site_elevation_m, LAPSE_T)
    dd_c = lapse_shift_c(cell_elevation_m, site_elevation_m, LAPSE_DEW)

    new_clim = []
    for day in clim:
        d = dict(day)
        d["temp_c"] = day["temp_c"] + dt_c
        d["temp_max_c"] = day["temp_max_c"] + dt_c
        d["temp_min_c"] = day["temp_min_c"] + dt_c
        new_dew = day["dewpoint_c"] + dd_c
        if day["dewpoint_c"] <= day["temp_min_c"]:          # keep a physically consistent original consistent
            new_dew = min(new_dew, d["temp_min_c"])
        d["dewpoint_c"] = new_dew
        new_clim.append(d)

    new_raw = {}
    for year, series in (raw_years or {}).items():
        new_raw[year] = {key: [None if v is None else v + dt_c for v in values] for key, values in series.items()}

    info = {"cell_elevation_m": cell_elevation_m, "site_elevation_m": site_elevation_m,
            "delta_elevation_m": dz, "temp_shift_c": dt_c, "dewpoint_shift_c": dd_c}
    return new_clim, new_raw, info
