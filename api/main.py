"""
SGreen Intel API — FastAPI backend wrapping the three ML features:
  1. CNN disease detection (training/predict.py)
  2. Crop advisor (heatmap/advisor.py)
  3. Plant care tracker (care/tracker.py)

Run locally:
    uvicorn api.main:app --reload --port 8000

Then visit http://localhost:8000/docs for interactive API testing.

CORS is open to all origins for local development. Restrict this before
any real deployment.
"""

import sys
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

# Make training/, heatmap/, care/ importable from the project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "training"))
sys.path.insert(0, str(PROJECT_ROOT / "heatmap"))
sys.path.insert(0, str(PROJECT_ROOT / "care"))

from predict_api import predict_structured  # new function, see predict_api.py
from advisor import get_recommendations, KNOWN_LOCATIONS
from tracker import get_plant_status

app = FastAPI(
    title="SGreen Intel API",
    description="CNN disease detection, crop advisor, and plant care tracker for Saudi agriculture.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten before real deployment
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
        "endpoints": ["/predict", "/advisor/{city}", "/tracker", "/locations"],
    }


# ---------------------------------------------------------------------------
# Feature 1 — CNN disease detection
# ---------------------------------------------------------------------------

@app.post("/predict")
async def predict_endpoint(file: UploadFile = File(...)):
    """
    Upload a leaf image, get back a disease diagnosis or a rejection
    message if the model is too uncertain (OOD rejection).

    Accepts: JPG, PNG, JFIF, WEBP.
    Returns: structured JSON -- see predict_structured() in predict_api.py
    for the exact response shape.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image.")

    # Save the upload to a temp file -- predict_structured() expects a path
    suffix = Path(file.filename).suffix or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        result = predict_structured(tmp_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {e}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return result


# ---------------------------------------------------------------------------
# Feature 2 — Crop advisor
# ---------------------------------------------------------------------------

@app.get("/locations")
def list_locations():
    """Returns the list of known Saudi cities the advisor supports."""
    return {"cities": sorted(KNOWN_LOCATIONS.keys())}


@app.get("/advisor/{city}")
def advisor_endpoint(city: str):
    """
    Returns planting-date recommendations, growth-stage water requirements,
    and temperature-tolerance warnings for every supported crop at the
    given Saudi city.

    city: one of the values from GET /locations (e.g. "riyadh", "jeddah")
    """
    city_key = city.strip().lower()
    if city_key not in KNOWN_LOCATIONS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown city '{city}'. See /locations for supported cities.",
        )

    try:
        result = get_recommendations(city_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Advisor failed: {e}")

    return _make_json_safe(result)


# ---------------------------------------------------------------------------
# Feature 3 — Plant care tracker
# ---------------------------------------------------------------------------

class TrackerRequest(BaseModel):
    crop_name: str
    location: str
    planting_date: str  # "YYYY-MM-DD"
    include_forecast: Optional[bool] = True


@app.post("/tracker")
def tracker_endpoint(req: TrackerRequest):
    """
    Returns the current growth stage, water needs, and any weather
    alerts for a saved plant.

    crop_name: e.g. "Tomato", "Potato" (must match a class in the CNN's
               35 supported classes -- see care_profiles.py)
    location: a known city name (see GET /locations) or omit forecast
    planting_date: "YYYY-MM-DD"
    """
    try:
        result = get_plant_status(
            crop_name=req.crop_name,
            location_name=req.location,
            planting_date_str=req.planting_date,
            include_forecast=req.include_forecast,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tracker failed: {e}")

    return _make_json_safe(result)


# ---------------------------------------------------------------------------
# Helper: make dict outputs JSON-safe (tuples -> lists, etc.)
# ---------------------------------------------------------------------------

def _make_json_safe(obj):
    """Recursively converts tuples to lists so FastAPI's JSON encoder
    doesn't choke on them (coordinates are stored as tuples in our
    advisor/tracker code)."""
    if isinstance(obj, tuple):
        return [_make_json_safe(x) for x in obj]
    if isinstance(obj, list):
        return [_make_json_safe(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _make_json_safe(v) for k, v in obj.items()}
    return obj