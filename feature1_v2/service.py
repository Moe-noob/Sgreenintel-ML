"""
Full Feature 1 v2 response = prediction + advice + weather risk + season note.
Kept separate from the FastAPI router so it can be used and tested without
a web server.

    svc = Service("work/runs/best/best.pt", detector="work/detector/best.pt")
    svc.diagnose([img1, img2], crop="tomato", lang="ar", location="riyadh")
"""

import datetime as dt

from feature1_v2.advice import kb, season_check, weather_risk
from feature1_v2.predictor import Predictor


def enrich(pred, lang="en", location=None, date=None, weather=True, hourly=None):
    """
    pred: Predictor.predict() output. location: Feature 2 city name or (lat, lon).
    hourly: optional pre-fetched Open-Meteo hourly data (tests / caching).
    Every add-on fails soft: an error there never hides the diagnosis.
    """
    out = {"prediction": pred, "advice": None, "lookalike_help": None, "weather_risk": None, "season_note": None}
    if not pred["accepted"]:
        return out
    label = pred["prediction"]
    out["advice"] = kb.advice_for(label, lang)
    if pred.get("lookalike"):
        out["lookalike_help"] = kb.lookalike_hint(pred["lookalike"], lang)
    if location is not None:
        try:
            out["season_note"] = season_check.check(pred["crop"], location, date, lang)
        except Exception as e:                                              # noqa: BLE001
            out["season_note"] = {"status": "error", "error": str(e)[:300], "message": {
                "en": "The crop-calendar check could not be run for this location.",
                "ar": "تعذّر إجراء فحص التقويم الزراعي لهذا الموقع."}[lang]}
        rule = out["advice"]["weather_rule"]
        if weather and rule:
            try:
                if hourly is None:
                    lat, lon = _latlon(location)
                    hourly = weather_risk.fetch(lat, lon)
                out["weather_risk"] = weather_risk.assess(rule, hourly, lang)
            except Exception as e:                                          # noqa: BLE001
                out["weather_risk"] = {"rule": rule, "risk": "unavailable", "error": str(e)[:300], "message": {
                    "en": "The weather forecast could not be fetched, so the weather risk is not shown.",
                    "ar": "تعذّر جلب توقعات الطقس، لذلك لا يُعرض خطر الطقس."}[lang]}
        elif weather:
            out["weather_risk"] = weather_risk.assess(None, None, lang)
    return out


def _latlon(location):
    if isinstance(location, (tuple, list)):
        return location[0], location[1]
    from feature1_v2.advice.season_check import _f2
    mods = _f2()
    if mods is None:
        raise ValueError("city names need feature2_v2; pass (lat, lon)")
    loc = mods[1].resolve(location)
    return loc["lat"], loc["lon"]


class Service:
    def __init__(self, ckpt, detector=None, tta=True):
        self.predictor = Predictor(ckpt, detector=detector, tta=tta)

    @property
    def crops(self):
        return self.predictor.crops

    def diagnose(self, images, crop=None, lang="en", location=None, date=None, weather=True, aggregate=None):
        pred = self.predictor.predict(images, crop=crop, aggregate=aggregate)
        return enrich(pred, lang, location, date or dt.date.today(), weather)
