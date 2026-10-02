"""
SGreen Intel API -- FastAPI backend wrapping the three ML features:
  1. CNN disease detection (training/predict.py)
  2. Crop advisor (heatmap/advisor.py)
  3. Plant care tracker (care/tracker.py)

Location handling: the 11 known cities (GET /locations) are the
validated, fast-path option -- their planting-date rule was checked against an
independent crop model (FAO AquaCrop; see research/), not against field trials. Any
other Saudi location can be used via geocoding (GET /geocode) plus
the coordinate-based endpoints (/advisor/at, /tracker with lat/lon).
Geocoding is restricted to Saudi Arabia: the FAO-56 tolerance
thresholds and arid-climate calibrations this project uses (Elnesr &
Alazba 2016) are specific to Saudi conditions, not validated elsewhere.

Run locally:
    uvicorn api.main:app --reload --port 8000

Then visit http://localhost:8000/docs for interactive API testing.
"""

import sys
import shutil
import tempfile
from pathlib import Path

import requests
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "training"))
sys.path.insert(0, str(PROJECT_ROOT / "heatmap"))
sys.path.insert(0, str(PROJECT_ROOT / "care"))

from predict_api import predict_structured, available_crops
from advisor import get_recommendations, KNOWN_LOCATIONS
from tracker import get_plant_status

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"

app = FastAPI(
    title="SGreen Intel API",
    description="CNN disease detection, crop advisor, and plant care tracker for Saudi agriculture.",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {
        "service": "SGreen Intel API",
        "status": "running",
        "endpoints": ["/predict", "/advisor/{city}", "/advisor/at", "/tracker", "/locations", "/geocode"],
    }


# ---------------------------------------------------------------------------
# Feature 1 -- CNN disease detection
# ---------------------------------------------------------------------------

@app.post("/predict")
async def predict_endpoint(file: UploadFile = File(...), crop: str = Form(None)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image.")

    suffix = Path(file.filename).suffix or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        result = predict_structured(tmp_path, crop=crop or None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {e}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return result


@app.get("/predict/crops")
async def predict_crops_endpoint():
    """The crops /predict accepts in its 'crop' field. Each entry's "key" is the exact value to send back (it is what
    predict_structured(crop=...) looks up, unchanged by this endpoint); "label" is only for display."""
    return {"crops": [{"key": c, "label": c.replace("_", " ").title()} for c in available_crops()]}


# ---------------------------------------------------------------------------
# Geocoding -- Saudi Arabia only
# ---------------------------------------------------------------------------

@app.get("/geocode")
def geocode_endpoint(query: str = Query(..., min_length=2)):
    """
    Searches for a location by name, restricted to Saudi Arabia.

    Only Saudi results are returned: the FAO-56 tolerance thresholds
    and arid-climate calibrations this project uses (Elnesr & Alazba
    2016) are specific to Saudi conditions, not validated for other
    locations. This is a methodology boundary, not a coverage gap.

    Returns up to 5 matches with name, region, coordinates, and
    Open-Meteo's own elevation estimate (for reference only -- the
    advisor/tracker use NASA POWER's elevation for actual calculations).
    """
    try:
        r = requests.get(GEOCODE_URL, params={
            "name": query, "count": 10, "language": "en", "format": "json",
        }, timeout=10)
        r.raise_for_status()
        data = r.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Geocoding service unavailable: {e}")

    results = data.get("results", [])
    saudi_results = [r for r in results if r.get("country_code") == "SA"][:5]

    return {
        "query": query,
        "matches": [
            {
                "name": r["name"],
                "region": r.get("admin1", ""),
                "lat": r["latitude"],
                "lon": r["longitude"],
                "elevation_m": r.get("elevation"),
            }
            for r in saudi_results
        ],
        "note": (
            "Only Saudi Arabia locations are supported -- this project's "
            "temperature thresholds and climate calibrations are specific "
            "to Saudi conditions."
        ) if not saudi_results else None,
    }

@app.get("/reverse-geocode")
def reverse_geocode_endpoint(lat: float, lon: float):
    """
    Converts raw coordinates (e.g. from the browser's Geolocation API)
    into a readable place name, restricted to Saudi Arabia for the same
    reason as /geocode.

    Uses OpenStreetMap's Nominatim (not Open-Meteo, which has no
    reverse-geocoding endpoint -- confirmed via Open-Meteo's own GitHub
    issue tracker before writing this). Nominatim's usage policy requires
    a descriptive User-Agent and a max of 1 request/second, which is
    well within this app's real usage pattern.
    """
    try:
        r = requests.get("https://nominatim.openstreetmap.org/reverse", params={
            "lat": lat, "lon": lon, "format": "json", "addressdetails": 1,
            "accept-language": "en",
        }, headers={"User-Agent": "SGreenIntel/1.0 (capstone project)"}, timeout=10)
        r.raise_for_status()
        data = r.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Reverse geocoding unavailable: {e}")

    address = data.get("address", {})
    country_code = address.get("country_code", "").upper()

    if country_code != "SA":
        return {
            "lat": lat, "lon": lon, "name": None,
            "note": "This location doesn't appear to be within Saudi Arabia -- "
                    "this project's methodology is calibrated for Saudi conditions only.",
        }

    name = (address.get("city") or address.get("town") or
            address.get("village") or address.get("municipality") or
            address.get("state") or "your location")
    region = address.get("state", "")

    return {"lat": lat, "lon": lon, "name": name, "region": region, "note": None}

# ---------------------------------------------------------------------------
# Feature 2 -- Crop advisor
# ---------------------------------------------------------------------------

@app.get("/locations")
def list_locations():
    """The 11 known, individually validated cities (fast path)."""
    return {"cities": sorted(KNOWN_LOCATIONS.keys())}


@app.get("/advisor/at")
def advisor_at_endpoint(
    lat: float = Query(..., ge=15.0, le=33.0, description="Latitude (Saudi Arabia range)"),
    lon: float = Query(..., ge=34.0, le=56.0, description="Longitude (Saudi Arabia range)"),
    label: Optional[str] = Query(None, description="Display name for this location, e.g. from /geocode"),
):
    """
    Planting-date recommendations for any Saudi coordinate pair, typically
    obtained via GET /geocode. Lat/lon are range-checked against Saudi
    Arabia's approximate bounding box; this is a coarse sanity check, not
    a precise border check.

    Note: this location has not been individually checked against the
    AquaCrop reference run the way the 11 known cities were. Elevation
    accuracy also depends entirely on NASA POWER's grid cell for this exact
    point (see the Abha discrepancy documented in the project's known
    limitations) -- a real source of uncertainty for arbitrary coordinates.
    """
    try:
        result = get_recommendations((lat, lon))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Advisor failed: {e}")

    result = _make_json_safe(result)
    result["location"] = label or f"{lat}, {lon}"
    result["_uncertainty_note"] = (
        "This location was not individually validated against known agricultural "
        "practice, unlike the 11 known cities. Elevation accuracy depends on NASA "
        "POWER's grid cell for this exact point."
    )
    return result


@app.get("/advisor/{city}")
def advisor_endpoint(city: str):
    """Planting-date recommendations for one of the 11 known cities."""
    city_key = city.strip().lower()
    if city_key not in KNOWN_LOCATIONS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown city '{city}'. See /locations, or use /advisor/at for other Saudi locations.",
        )
    try:
        result = get_recommendations(city_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Advisor failed: {e}")
    return _make_json_safe(result)


# ---------------------------------------------------------------------------
# Feature 3 -- Plant care tracker
# ---------------------------------------------------------------------------

class TrackerRequest(BaseModel):
    crop_name: str
    planting_date: str  # "YYYY-MM-DD"
    location: Optional[str] = None       # known city name
    lat: Optional[float] = None          # OR raw coordinates (from /geocode)
    lon: Optional[float] = None
    location_label: Optional[str] = None  # display name when using lat/lon
    include_forecast: Optional[bool] = True
    plants_per_m2: Optional[float] = None  # optional planting density; litres per plant are shown only if given


@app.post("/tracker")
def tracker_endpoint(req: TrackerRequest):
    """
    Returns the current growth stage, water needs, and any weather
    alerts for a saved plant.

    Provide EITHER `location` (a known city name, see GET /locations)
    OR `lat`+`lon` (typically from GET /geocode) -- not both.
    """
    if req.lat is not None and req.lon is not None:
        location_arg = (req.lat, req.lon)
        display_location = req.location_label or f"{req.lat}, {req.lon}"
    elif req.location:
        location_arg = req.location
        display_location = req.location
    else:
        raise HTTPException(status_code=400, detail="Provide either 'location' or 'lat'+'lon'.")

    if req.plants_per_m2 is not None and not (0.05 <= req.plants_per_m2 <= 50):
        raise HTTPException(status_code=400, detail="plants_per_m2 must be between 0.05 and 50.")

    try:
        result = get_plant_status(
            crop_name=req.crop_name,
            location_name=location_arg,
            planting_date_str=req.planting_date,
            include_forecast=req.include_forecast,
            plants_per_m2=req.plants_per_m2,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tracker failed: {e}")

    result = _make_json_safe(result)
    result["location"] = display_location
    if req.lat is not None and req.lon is not None:
        result["_uncertainty_note"] = (
            "This location was not individually validated against known agricultural "
            "practice, unlike the 11 known cities. Elevation accuracy depends on NASA "
            "POWER's grid cell for this exact point."
        )
    return result


# ---------------------------------------------------------------------------
# Helper: make dict outputs JSON-safe (tuples -> lists, etc.)
# ---------------------------------------------------------------------------

def _make_json_safe(obj):
    if isinstance(obj, tuple):
        return [_make_json_safe(x) for x in obj]
    if isinstance(obj, list):
        return [_make_json_safe(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _make_json_safe(v) for k, v in obj.items()}
    return obj