"""
Station climate for Feature 2 v2 -- fully offline.

Source: FAOCLIM-2 (FAO 2001) long-term station means, as sinusoidal fits
published with Elnesr & Alazba (2016), Appendix A ("Stations" sheet):

    X(j) = a + rho * sin(omega * j + phi)          (Elnesr & Alazba Eq. 4)

for X in {Tmax, Tmin, Tmean, ET0}, j = day of year (the spreadsheet lets j
run past 365 for seasons that cross 31 Dec, and so do we). ET0 in FAOCLIM-2
is FAO Penman-Monteith computed by FAO from the station's own observed
temperature, humidity, wind and sunshine -- ground-station ET0, which is
why v2 prefers it over reanalysis-driven ET0 when both are available.

What a sinusoid does NOT give you: day-to-day or year-to-year variability.
All temperatures here are long-term MEANS for that date; single hot or cold
days exceed them. Heat/cold exposure counted from these curves is therefore
a lower bound (see README "Limitations").
"""

import json
import math
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"

# The 11 cities the v1 advisor supports, mapped to coordinates (same as
# heatmap/advisor.py). The nearest FAOCLIM-2 station is chosen automatically.
KNOWN_CITIES = {
    "riyadh": (24.71, 46.68), "jeddah": (21.54, 39.17), "dammam": (26.43, 50.10),
    "najran": (17.49, 44.13), "jazan": (16.89, 42.55), "abha": (18.22, 42.51),
    "tabuk": (28.38, 36.57), "qassim": (26.33, 43.98), "madinah": (24.47, 39.61),
    "makkah": (21.39, 39.86), "hail": (27.52, 41.69),
}

# Distances above this are reported as a representativeness warning.
FAR_STATION_KM = 100.0


def _sine(fit, j):
    return fit["a"] + fit["rho"] * math.sin(fit["omega"] * j + fit["phi"])


class Station:
    # Seasons may run past 31 Dec, so days up to this j are precomputed.
    MAX_J = 800

    def __init__(self, rec):
        self.rec = rec
        self.name = rec["name"]
        self.lat, self.lon, self.elevation_m = rec["lat"], rec["lon"], rec["elevation_m"]
        self._tx = [_sine(rec["Tx"], j) for j in range(self.MAX_J + 1)]
        self._tn = [_sine(rec["Tn"], j) for j in range(self.MAX_J + 1)]
        self._et0 = [max(_sine(rec["ET0"], j), 0.0) for j in range(self.MAX_J + 1)]

    def tx(self, j):
        return self._tx[j] if isinstance(j, int) and 0 <= j <= self.MAX_J else _sine(self.rec["Tx"], j)

    def tn(self, j):
        return self._tn[j] if isinstance(j, int) and 0 <= j <= self.MAX_J else _sine(self.rec["Tn"], j)

    def ta_fit(self, j):
        """Mean temperature from its own sinusoid (used by the integral form)."""
        return _sine(self.rec["Ta"], j)

    def ta(self, j):
        """Mean temperature as (Tx + Tn) / 2 -- what the spreadsheet's summation form uses."""
        return (self.tx(j) + self.tn(j)) / 2.0

    def et0(self, j):
        return self._et0[j] if isinstance(j, int) and 0 <= j <= self.MAX_J else max(_sine(self.rec["ET0"], j), 0.0)

    def fit(self, var):
        return self.rec[var]

    def annual_et0_mm(self):
        return sum(self.et0(j) for j in range(1, 366))

    def summary(self):
        return {"name": self.name, "region": self.rec["region"], "lat": self.lat, "lon": self.lon,
                "elevation_m": self.elevation_m,
                "tmax_hottest_c": round(max(self.tx(j) for j in range(1, 366)), 1),
                "tmin_coldest_c": round(min(self.tn(j) for j in range(1, 366)), 1),
                "et0_annual_mm": round(self.annual_et0_mm()),
                "et0_peak_mm_day": round(max(self.et0(j) for j in range(1, 366)), 2)}


def load_stations():
    doc = json.loads((DATA / "stations_ksa.json").read_text(encoding="utf-8"))
    return [Station(r) for r in doc["stations"]]


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest_station(lat, lon, stations=None, elevation_m=None):
    """
    Returns (station, distance_km, warnings). Stations with byte-identical
    temperature fits (the workbook duplicates a few) are equivalent, so the
    nearest one is simply taken.
    """
    stations = stations or load_stations()
    best = min(stations, key=lambda s: haversine_km(lat, lon, s.lat, s.lon))
    d = haversine_km(lat, lon, best.lat, best.lon)
    warnings = []
    if d > FAR_STATION_KM:
        warnings.append(f"Nearest climate station ({best.name}) is {d:.0f} km away; local climate may differ.")
    if elevation_m is not None and abs(elevation_m - best.elevation_m) > 300:
        # ~6.5 degC per km standard lapse rate: flag, do not silently correct.
        dt = 6.5 * (elevation_m - best.elevation_m) / 1000.0
        warnings.append(f"Site is {elevation_m - best.elevation_m:+.0f} m relative to the station; "
                        f"temperatures may be ~{-dt:+.1f} degC different (standard lapse rate).")
    return best, d, warnings


def resolve(location, stations=None):
    """location: city name, (lat, lon), or a station name substring."""
    stations = stations or load_stations()
    if isinstance(location, str):
        key = location.strip().lower()
        if key in KNOWN_CITIES:
            lat, lon = KNOWN_CITIES[key]
            st, d, w = nearest_station(lat, lon, stations)
            return {"label": location, "lat": lat, "lon": lon, "station": st, "distance_km": d, "warnings": w}
        hits = [s for s in stations if key in s.name.lower()]
        if hits:
            st = hits[0]
            return {"label": st.name, "lat": st.lat, "lon": st.lon, "station": st, "distance_km": 0.0, "warnings": []}
        raise ValueError(f"Unknown location '{location}'. Use one of {sorted(KNOWN_CITIES)} or (lat, lon).")
    lat, lon = location[:2]
    elev = location[2] if len(location) > 2 else None
    st, d, w = nearest_station(lat, lon, stations, elev)
    return {"label": f"({lat:.2f}, {lon:.2f})", "lat": lat, "lon": lon, "station": st, "distance_km": d, "warnings": w}
