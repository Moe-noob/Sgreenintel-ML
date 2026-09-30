"""
Optional FastAPI router for Feature 2 v2. Not wired into api/main.py, so
deleting feature2_v2/ leaves the existing API untouched. To try it, add two
lines to api/main.py:

    sys.path.insert(0, str(PROJECT_ROOT / "feature2_v2"))
    from api_router import router as f2v2_router; app.include_router(f2v2_router)

Endpoints
  GET /v2/advisor/{city}                    all crops for a known city
  GET /v2/advisor/at?lat=..&lon=..          nearest FAOCLIM-2 station
  Common query options: crop, soil, method, ecw, row_m, plant_m, full (include per-sowing-day arrays)
"""

import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agronomy                 # noqa: E402
import climate                  # noqa: E402
from advisor import advise      # noqa: E402

router = APIRouter(prefix="/v2", tags=["Feature 2 v2 -- crop water planner"])


def _run(location, crop, soil, method, ecw, row_m, plant_m, full):
    if soil not in agronomy.SOILS:
        raise HTTPException(400, f"soil must be one of {sorted(agronomy.SOILS)}")
    if method not in agronomy.IRRIGATION_EFFICIENCY:
        raise HTTPException(400, f"method must be one of {sorted(agronomy.IRRIGATION_EFFICIENCY)}")
    spacing = (row_m, plant_m) if row_m and plant_m else None
    res = advise(location, soil, method, ecw, spacing, crop)
    if not full:
        for c in res["crops"]:
            c.pop("by_sowing_day", None)
            c.pop("daily", None)
    return res


@router.get("/advisor/at")
def advisor_at(lat: float = Query(..., ge=15.0, le=33.0), lon: float = Query(..., ge=34.0, le=56.0),
               elevation_m: Optional[float] = None, crop: Optional[str] = None, soil: str = "loamy_sand",
               method: str = "drip", ecw: Optional[float] = Query(None, ge=0, le=20),
               row_m: Optional[float] = None, plant_m: Optional[float] = None, full: bool = False):
    loc = (lat, lon, elevation_m) if elevation_m is not None else (lat, lon)
    return _run(loc, crop, soil, method, ecw, row_m, plant_m, full)


@router.get("/advisor/{city}")
def advisor_city(city: str, crop: Optional[str] = None, soil: str = "loamy_sand", method: str = "drip",
                 ecw: Optional[float] = Query(None, ge=0, le=20), row_m: Optional[float] = None,
                 plant_m: Optional[float] = None, full: bool = False):
    if city.lower() not in climate.KNOWN_CITIES:
        raise HTTPException(404, f"Unknown city. Known: {sorted(climate.KNOWN_CITIES)}")
    return _run(city.lower(), crop, soil, method, ecw, row_m, plant_m, full)
