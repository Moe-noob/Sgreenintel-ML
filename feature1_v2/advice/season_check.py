"""
Season plausibility (plan, Step 4): is this crop likely to be growing in
the open field at this place and date, according to Feature 2 v2's crop
calendar (FAOCLIM-2 station climate + FAO-56 Rev.1 season lengths)?

The output is a NOTE only. It never changes the prediction: greenhouse and
off-season crops exist, and long-term mean climate is not this year's
weather. The check needs feature2_v2/ to be present; if it is missing, or the
crop has no Feature 2 counterpart (apple, grape, strawberry), the check
returns "not_available".

Rule: a date is "in season" when it falls inside the growing period
(sowing day -> sowing day + season length) of at least one LOW-STRESS
sowing day. Low-stress = Feature 2 candidate days (the crop finishes within
its thermal limits) whose season temperature stress (degree-days outside
the crop's tolerable range) is in the lowest third of all candidate days
for that place. "Candidate" alone is too permissive (e.g. lettuce sown in
Riyadh in June is a candidate but has 1400+ stress degree-days); the
lowest-third cut-off is a heuristic, documented as such.
"""

import datetime as dt
import sys
from functools import lru_cache
from pathlib import Path

from feature1_v2 import taxonomy

LOW_STRESS_FRACTION = 3          # lowest third of candidate sowing days by stress degree-days
F2 = Path(__file__).resolve().parents[2] / "feature2_v2"


def _f2():
    if not F2.is_dir():
        return None
    if str(F2) not in sys.path:
        sys.path.insert(0, str(F2))
    import advisor, climate, crops               # noqa: E401  (feature2_v2 modules)
    return advisor, climate, crops


@lru_cache(maxsize=256)
def _covered_days(f2_key, station_name):
    advisor, climate, crops = _f2()
    st = next(s for s in climate.load_stations() if s.name == station_name)
    covered = set()
    for crop in (c for c in crops.ksa_crops() if c["key"] == f2_key):
        rows = [r for r in advisor.analyse_crop(crop, st)["by_sowing_day"] if r["candidate"] and r["season_days"]]
        if not rows:
            continue
        cut = sorted(r["stress_dd"] for r in rows)[(len(rows) - 1) // LOW_STRESS_FRACTION]
        for r in rows:
            if r["stress_dd"] <= cut:
                covered.update(((r["doy"] - 1 + k) % 365) + 1 for k in range(int(r["season_days"])))
    return frozenset(covered)


def check(crop, location, date=None, lang="en"):
    """crop: taxonomy crop key; location: Feature 2 city name or (lat, lon)."""
    mods = _f2()
    f2_keys = taxonomy.CROPS.get(crop, (None, None, []))[2]
    if mods is None or not f2_keys:
        return {"status": "not_available",
                "message": {"en": "No crop-calendar check for this crop.", "ar": "لا يتوفر فحص تقويم زراعي لهذا المحصول."}[lang]}
    _, climate, _ = mods
    loc = climate.resolve(location)
    date = date or dt.date.today()
    doy = min(date.timetuple().tm_yday, 365)
    covered = set()
    for k in f2_keys:
        covered |= _covered_days(k, loc["station"].name)
    in_season = doy in covered
    name = taxonomy.CROPS[crop][0 if lang == "en" else 1]
    if in_season:
        msg = {"en": f"{name} is normally in the field around this date at {loc['label']}.",
               "ar": f"يكون {name} عادةً في الحقل في هذا الوقت في {loc['label']}."}[lang]
    else:
        msg = {"en": f"Open-field {name} is not usually growing around this date at {loc['label']} (Feature 2 crop calendar). "
                     f"If this is a greenhouse or an off-season planting, ignore this note; otherwise double-check which crop this is.",
               "ar": f"لا يُزرع {name} عادةً في الحقل المكشوف في هذا الوقت في {loc['label']} (حسب التقويم الزراعي في الميزة 2). "
                     f"إذا كانت الزراعة في بيت محمي أو في غير موسمها فتجاهل هذه الملاحظة؛ وإلا فتأكد من نوع المحصول."}[lang]
    return {"status": "in_season" if in_season else "unusual_for_season", "message": msg,
            "station": loc["station"].name, "station_distance_km": round(loc["distance_km"], 1),
            "basis": "Feature 2 v2 low-stress sowing days (lowest third by stress degree-days) and FAO-56 Rev.1 season lengths, long-term mean climate"}
