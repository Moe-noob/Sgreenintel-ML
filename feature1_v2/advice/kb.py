"""
Advice lookup for Feature 1 v2 (plan, Step 4).

    from feature1_v2.advice import kb
    kb.advice_for("tomato__late_blight", "ar")
    kb.lookalike_hint(["tomato__early_blight", "tomato__late_blight"], "en")

The result combines the category template (categories.py) with the
condition entry (entries.py) and a resolved bibliography (sources.py).
The predictor does NOT depend on this module, and it does not change any
prediction: it only describes what to check and what to do.
"""

from feature1_v2 import taxonomy
from feature1_v2.advice.categories import CATEGORIES, EXTENSION, LABEL_RULE
from feature1_v2.advice.entries import ENTRIES
from feature1_v2.advice.sources import SOURCES, cite

REVIEW_STATUS = "draft - written from the cited references, to be reviewed by a plant pathologist / MEWA extension specialist before release"
DISCLAIMER = {
    "en": "This is decision support from a photo, not a laboratory diagnosis. Confirm the symptoms described below before acting.",
    "ar": "هذه مساعدة في اتخاذ القرار بناءً على صورة، وليست تشخيصًا مخبريًا. تأكّد من الأعراض الموضحة أدناه قبل التصرف.",
}


def _pick(d, lang):
    return None if d is None else d[lang]


def advice_for(label, lang="en"):
    if lang not in ("en", "ar"):
        raise ValueError("lang must be 'en' or 'ar'")
    if label not in ENTRIES:
        raise KeyError(f"no advice entry for {label}")
    e = ENTRIES[label]
    c = CATEGORIES[e["category"]]
    srcs = list(dict.fromkeys(e["sources"] + c["sources"] + (["mewa"] if c["chemical_groups"] else [])))
    out = {
        "label": label,
        "title": taxonomy.display(label, lang),
        "category": e["category"],
        "category_name": c["name"][lang],
        "cause": e["cause"],
        "confirm_symptoms": e["symptoms"][lang],
        "key_sign": e["key_sign"][lang],
        "lookalikes": [{"label": l, "title": taxonomy.display(l, lang), "key_sign": ENTRIES[l]["key_sign"][lang]}
                       for l in e["lookalikes"]],
        "note": _pick(e["note"], lang),
        "immediate_steps": c["immediate"][lang],
        "cultural_control": c["cultural"][lang],
        "chemical_control": None if c["chemical_groups"] is None else {
            "groups": c["chemical_groups"][lang], "label_rule": LABEL_RULE[lang]},
        "prevention": c["prevention"][lang],
        "when_to_contact_extension": EXTENSION[lang] if e["category"] != "healthy" else None,
        "weather_rule": e["weather"],
        "sources": [cite(s) for s in srcs],
        "review_status": REVIEW_STATUS,
        "disclaimer": DISCLAIMER[lang],
    }
    return out


def lookalike_hint(labels, lang="en"):
    """Two (or more) close predictions -> the sign that tells each apart."""
    return [{"label": l, "title": taxonomy.display(l, lang), "check_for": ENTRIES[l]["key_sign"][lang]}
            for l in labels if l in ENTRIES]


def validate():
    """Problems in the knowledge base (empty list = consistent). Used by the tests."""
    problems = []
    for lbl in taxonomy.all_labels():
        if lbl == taxonomy.UNSUPPORTED:
            continue
        if lbl not in ENTRIES:
            problems.append(f"missing entry: {lbl}")
    for lbl, e in ENTRIES.items():
        if lbl not in taxonomy.all_labels():
            problems.append(f"entry for unknown label: {lbl}")
        if e["category"] not in CATEGORIES:
            problems.append(f"{lbl}: unknown category {e['category']}")
        for k in ("symptoms", "key_sign"):
            for lang in ("en", "ar"):
                if not e[k][lang].strip():
                    problems.append(f"{lbl}: empty {k}/{lang}")
        if e["note"] and not (e["note"]["en"].strip() and e["note"]["ar"].strip()):
            problems.append(f"{lbl}: note missing a language")
        for l in e["lookalikes"]:
            if l not in ENTRIES:
                problems.append(f"{lbl}: look-alike {l} has no entry")
            elif taxonomy.crop_of(l) != taxonomy.crop_of(lbl):
                problems.append(f"{lbl}: look-alike {l} is another crop")
        for s in e["sources"] + CATEGORIES[e["category"]]["sources"]:
            if s not in SOURCES:
                problems.append(f"{lbl}: unknown source {s}")
        if not (e["sources"] or CATEGORIES[e["category"]]["sources"]):
            problems.append(f"{lbl}: no sources")
    for k, c in CATEGORIES.items():
        for f in ("name", "immediate", "cultural", "prevention"):
            if set(c[f]) != {"en", "ar"}:
                problems.append(f"category {k}: {f} not in both languages")
        for f in ("immediate", "cultural", "prevention"):
            if len(c[f]["en"]) != len(c[f]["ar"]):
                problems.append(f"category {k}: {f} has different numbers of EN and AR items")
    return problems
