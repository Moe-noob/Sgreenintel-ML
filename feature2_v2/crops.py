"""
Which rows of the Elnesr & Alazba crop table are used for KSA, and why.

The workbook has 122 crop/condition rows from many climates. For each crop
grown in Saudi Arabia we take the row(s) whose FAO-56 growing conditions are
closest to KSA ("Arid Region", "Calif. Desert", "Near East (desert)"). A
crop with two arid rows (e.g. tomato: January and Oct/Nov plantings) keeps
both -- they are the spring and autumn seasons farmers actually use.

The "Plant Date" of a row is the planting month FAO-56 observed that
duration for; it is informational only. v2 does not assume it -- every
day of the year is tested as a sowing date (advisor.py).
"""

import json
from pathlib import Path

from agronomy import KC_REV1, REV1_GDD

DATA = Path(__file__).resolve().parent / "data"

# (crop key, workbook row number)
KSA_CROP_ROWS = [
    ("Tomato", 34),
    ("Tomato", 37),
    ("Sweet peppers {bell}", 33),
    ("Potato", 70),
    ("Cucumber {Fresh Market}", 42),
    ("Cucumber {Fresh Market}", 41),
    ("EggPlant", 30),
    ("Onions {dry}", 20),
    ("Lettuce", 17),
    ("Carrots", 4),
    ("Spinach", 26),
    ("Squash", 47),
    ("Watermelon", 54),
    ("Sweet Melons", 52),
    ("Cabbage", 3),
    ("Cauliflower", 7),
    ("Broccoli", 1),
    ("Beans, green", 86),
    ("Radish", 28),
    ("Lentil", 106),
    ("Okra", 29),
    ("Sweet corn", 64),
    ("Garlic", 11),
    ("Mulukhiyah", 62),
]

# Arabic names for the report (common KSA market names).
ARABIC = {
    "Tomato": "طماطم", "Sweet peppers {bell}": "فلفل رومي", "Potato": "بطاطس",
    "Cucumber {Fresh Market}": "خيار", "EggPlant": "باذنجان", "Onions {dry}": "بصل",
    "Lettuce": "خس", "Carrots": "جزر", "Spinach": "سبانخ", "Squash": "كوسة",
    "Watermelon": "بطيخ", "Sweet Melons": "شمام", "Cabbage": "ملفوف", "Cauliflower": "قرنبيط",
    "Broccoli": "بروكلي", "Beans, green": "فاصوليا خضراء", "Radish": "فجل", "Lentil": "عدس",
    "Okra": "بامية", "Sweet corn": "ذرة حلوة", "Garlic": "ثوم", "Mulukhiyah": "ملوخية", "Pumpkin": "قرع",
}


def load_crop_table():
    doc = json.loads((DATA / "crops_eln16.json").read_text(encoding="utf-8"))
    return {c["number"]: c for c in doc["crops"]}


def prepare(row, key=None):
    """
    One crop row ready for the simulator. The workbook's Kc/height are FAO-56
    (1998) values; they are kept as *_1998 (the paper-method engine uses them,
    so the spreadsheet reproduction stays exact) and replaced for the water
    budget by FAO-56 Rev.1 (2025) Table 6.1/6.2 values where available.
    Stage GDD requirements from FAO-56 Rev.1 Tables 6.10-6.12 are attached
    as gdd_rev1 when the crop is listed there (see season.py).
    """
    row = dict(row)
    key = key or row["crop"]
    for k in ("kc_ini", "kc_mid", "kc_end", "height_m"):
        row[k + "_1998"] = row[k]
    rev1 = KC_REV1.get(key)
    if rev1:
        row["kc_ini"], row["kc_mid"], row["kc_end"], row["height_m"], rev1_row = rev1
        row["kc_source"] = f"FAO-56 Rev.1 (2025) Table 6.1/6.2: {rev1_row}"
    else:
        row["kc_source"] = "FAO-56 (1998) via Elnesr & Alazba workbook"
    gdd = REV1_GDD.get(key)
    if gdd:
        tb, tu, stage_rows, src = gdd
        mean = tuple(sum(r[i] for r in stage_rows) / len(stage_rows) for i in range(4))
        row["gdd_rev1"] = {"t_base": tb, "t_upper": tu, "stages": mean, "source": src}
    row.update({"key": key, "arabic": ARABIC.get(key, ""),
                "label": f"{key} -- {row['region']} ({row['plant_date']})"})
    return row


def ksa_crops():
    table = load_crop_table()
    return [prepare(table[number], key) for key, number in KSA_CROP_ROWS]
