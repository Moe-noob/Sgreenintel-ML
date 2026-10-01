"""
Optional FastAPI router for Feature 1 v2. Not wired into api/main.py, so
deleting feature1_v2/ leaves the existing API untouched (same approach as
feature2_v2/api_router.py). To try it, add to api/main.py:

    sys.path.insert(0, str(PROJECT_ROOT))
    from feature1_v2.api_router import router as f1v2_router; app.include_router(f1v2_router)

and set F1V2_CKPT (and optionally F1V2_DETECTOR) to the trained files.

Endpoints
  GET  /v2/disease/crops                 crops the loaded model supports (for the crop selector)
  POST /v2/disease/predict               1-3 photos of the same plant (+ optional crop, lang, city or lat/lon)
  GET  /v2/disease/advice/{label}        advice entry for a label (lang=en|ar)
"""

import os
import tempfile
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from PIL import Image, UnidentifiedImageError

from feature1_v2 import config, taxonomy
from feature1_v2.advice import kb

router = APIRouter(prefix="/v2/disease", tags=["Feature 1 v2 -- plant disease detection"])
MAX_PHOTOS = 3
_service = None


def get_service():
    global _service
    if _service is None:
        ckpt = os.environ.get("F1V2_CKPT", str(config.WORK_DIR / "runs" / "best" / "best.pt"))
        if not Path(ckpt).exists():
            raise HTTPException(503, f"Feature 1 v2 model not found at {ckpt}; set F1V2_CKPT (see feature1_v2/RUNBOOK.md)")
        from feature1_v2.service import Service
        _service = Service(ckpt, detector=os.environ.get("F1V2_DETECTOR") or None)
    return _service


@router.get("/crops")
def crops(lang: str = Query("en", pattern="^(en|ar)$")):
    svc = get_service()
    i = 0 if lang == "en" else 1
    return {"crops": [{"key": c, "name": taxonomy.CROPS[c][i]} for c in svc.crops]}


@router.post("/predict")
async def predict(files: List[UploadFile] = File(...), crop: Optional[str] = Form(None),
                  lang: str = Form("en"), city: Optional[str] = Form(None),
                  lat: Optional[float] = Form(None), lon: Optional[float] = Form(None),
                  weather: bool = Form(True)):
    if lang not in ("en", "ar"):
        raise HTTPException(400, "lang must be en or ar")
    if not 1 <= len(files) <= MAX_PHOTOS:
        raise HTTPException(400, f"send 1 to {MAX_PHOTOS} photos of the same plant")
    images = []
    for f in files:
        if not (f.content_type or "").startswith("image/"):
            raise HTTPException(400, f"{f.filename}: not an image")
        with tempfile.SpooledTemporaryFile() as tmp:
            tmp.write(await f.read())
            tmp.seek(0)
            try:
                images.append(Image.open(tmp).convert("RGB"))
            except UnidentifiedImageError:
                raise HTTPException(400, f"{f.filename}: unreadable image")
    svc = get_service()
    if crop is not None and crop not in svc.crops:
        raise HTTPException(400, f"unsupported crop '{crop}'; supported: {svc.crops}")
    location = (lat, lon) if lat is not None and lon is not None else city
    return svc.diagnose(images, crop=crop, lang=lang, location=location, weather=weather)


@router.get("/advice/{label}")
def advice(label: str, lang: str = Query("en", pattern="^(en|ar)$")):
    try:
        return kb.advice_for(label, lang)
    except KeyError:
        raise HTTPException(404, f"no advice entry for '{label}'")
