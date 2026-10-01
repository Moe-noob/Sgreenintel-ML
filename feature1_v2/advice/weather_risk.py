"""
Weather risk for diseases with a PUBLISHED weather rule (plan, Step 4).
Only two rules are implemented, both with a citation; every other disease
gets "no published rule implemented" rather than an invented one.

1. Hutton criteria (Dancey, Skelsey & Cooke 2017), potato late blight:
   a "Hutton period" is TWO CONSECUTIVE DAYS, each with minimum air
   temperature >= 10 degC AND at least 6 hours with relative humidity >= 90 %.
   It replaced the Smith period in Great Britain's blight warnings. It was
   developed for potato; using it for tomato late blight (same pathogen)
   is an approximation, stated in the output.

2. "Three tens" rule (Baldacci 1947, reviewed by Gessler et al. 2011),
   grapevine downy mildew primary infection: air temperature >= 10 degC,
   >= 10 mm rain within 24 h, and shoots >= 10 cm long. Shoot length is not
   known from weather, so it is stated as an assumption.

Input: hourly forecast from Open-Meteo (the same service Feature 3 uses):
    {"time": [...ISO local time...], "temperature_2m": [...],
     "relative_humidity_2m": [...], "precipitation": [...]}
"""

from collections import OrderedDict

from feature1_v2.advice.sources import cite

OPEN_METEO = "https://api.open-meteo.com/v1/forecast"


def fetch(lat, lon, days=7, timeout=15):
    import requests                      # only needed for live use
    r = requests.get(OPEN_METEO, params={
        "latitude": lat, "longitude": lon, "forecast_days": days, "timezone": "auto",
        "hourly": "temperature_2m,relative_humidity_2m,precipitation"}, timeout=timeout)
    r.raise_for_status()
    return r.json()["hourly"]


def _by_day(hourly):
    days = OrderedDict()
    for t, temp, rh in zip(hourly["time"], hourly["temperature_2m"], hourly["relative_humidity_2m"]):
        if temp is None or rh is None:
            continue
        d = days.setdefault(t[:10], {"tmin": temp, "rh90_hours": 0, "hours": 0})
        d["tmin"] = min(d["tmin"], temp)
        d["rh90_hours"] += rh >= 90
        d["hours"] += 1
    return days


def hutton(hourly):
    """Days meeting the criteria and the Hutton periods (pairs of consecutive qualifying days)."""
    days = _by_day(hourly)
    names = [d for d, v in days.items() if v["hours"] >= 20]       # skip incomplete first/last days
    ok = {d: days[d]["tmin"] >= 10 and days[d]["rh90_hours"] >= 6 for d in names}
    periods = [(a, b) for a, b in zip(names, names[1:]) if ok[a] and ok[b]]
    return {"days": {d: {"tmin": round(days[d]["tmin"], 1), "rh90_hours": days[d]["rh90_hours"], "meets": ok[d]}
                     for d in names},
            "periods": periods}


def three_tens(hourly):
    """Rolling 24 h windows with >= 10 mm rain and no hour below 10 degC."""
    t, temp, rain = hourly["time"], hourly["temperature_2m"], hourly["precipitation"]
    hits = []
    for i in range(0, max(0, len(t) - 23)):
        w_rain = sum(r or 0 for r in rain[i:i + 24])
        w_temp = [x for x in temp[i:i + 24] if x is not None]
        if w_rain >= 10 and w_temp and min(w_temp) >= 10:
            if not hits or hits[-1][1] < t[i]:
                hits.append([t[i], t[i + 23], round(w_rain, 1)])
            else:
                hits[-1][1], hits[-1][2] = t[i + 23], max(hits[-1][2], round(w_rain, 1))
    return {"windows": [{"from": a, "to": b, "rain_mm": r} for a, b, r in hits]}


TEXT = {
    "hutton_late_blight": {
        "high": {"en": "HIGH risk: the forecast has {n} Hutton period(s) ({first}). Late blight can spread quickly; protect healthy plants before this period.",
                 "ar": "خطر مرتفع: يتضمن التوقع {n} فترة/فترات هَتن ({first}). قد تنتشر اللفحة المتأخرة بسرعة؛ احمِ النباتات السليمة قبل هذه الفترة."},
        "low": {"en": "Low risk from weather in the forecast period: no two consecutive days with minimum temperature >= 10 degC and >= 6 h of humidity >= 90 %.",
                "ar": "خطر منخفض من الطقس خلال فترة التوقع: لا يوجد يومان متتاليان بدرجة حرارة صغرى 10 درجات أو أكثر ورطوبة 90٪ أو أكثر لمدة 6 ساعات على الأقل."},
        "caveat": {"en": "Rule developed for potato late blight in Great Britain (outdoor crops); in greenhouses humidity can be higher than the outdoor forecast, and use for tomato is an approximation.",
                   "ar": "القاعدة طُوّرت للّفحة المتأخرة في البطاطس في بريطانيا (زراعات مكشوفة)؛ في البيوت المحمية قد تكون الرطوبة أعلى من التوقع الخارجي، واستخدامها للطماطم تقريبي."},
        "source": "hutton",
    },
    "three_tens_downy_mildew": {
        "high": {"en": "HIGH risk: {n} rain event(s) of >= 10 mm in 24 h at >= 10 degC ({first}). Primary downy mildew infection is possible if shoots are >= 10 cm.",
                 "ar": "خطر مرتفع: {n} حدث/أحداث مطر 10 مم أو أكثر خلال 24 ساعة مع حرارة 10 درجات أو أكثر ({first}). العدوى الأولية بالبياض الزغبي ممكنة إذا كان طول الأفرع 10 سم أو أكثر."},
        "low": {"en": "Low risk from weather in the forecast period: no 24 h period with >= 10 mm rain at >= 10 degC.",
                "ar": "خطر منخفض من الطقس خلال فترة التوقع: لا توجد فترة 24 ساعة بمطر 10 مم أو أكثر مع حرارة 10 درجات أو أكثر."},
        "caveat": {"en": "The rule also requires shoots >= 10 cm long, which the app cannot see; it predicts primary (rain-driven) infection only, not later spread under irrigation or dew.",
                   "ar": "تتطلب القاعدة أيضًا أن يكون طول الأفرع 10 سم أو أكثر، وهذا لا يستطيع التطبيق رؤيته؛ وهي تتنبأ بالعدوى الأولية (بسبب المطر) فقط، لا بالانتشار اللاحق بسبب الري أو الندى."},
        "source": "rule_10_10_24",
    },
}


def assess(rule, hourly, lang="en"):
    """rule: an entry's 'weather' id (or None). Returns a dict for the API."""
    if rule is None:
        return {"rule": None, "risk": "not_available",
                "message": {"en": "No published weather rule is implemented for this condition.",
                            "ar": "لا توجد قاعدة طقس منشورة مطبقة لهذه الحالة."}[lang]}
    tx = TEXT[rule]
    if rule == "hutton_late_blight":
        r = hutton(hourly)
        hits = [f"{a} - {b}" for a, b in r["periods"]]
        detail = r["days"]
    elif rule == "three_tens_downy_mildew":
        r = three_tens(hourly)
        hits = [f"{w['from']} - {w['to']} ({w['rain_mm']} mm)" for w in r["windows"]]
        detail = r["windows"]
    else:
        raise KeyError(rule)
    risk = "high" if hits else "low"
    msg = tx[risk][lang].format(n=len(hits), first=hits[0] if hits else "")
    return {"rule": rule, "risk": risk, "message": msg, "caveat": tx["caveat"][lang],
            "events": hits, "detail": detail, "source": cite(tx["source"])}
