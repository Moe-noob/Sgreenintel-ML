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
    "Okra": "بامية", "Sweet corn": "ذرة حلوة", "Garlic": "ثوم", "Mulukhiyah": "ملوخية",
}


def load_crop_table():
    doc = json.loads((DATA / "crops_eln16.json").read_text(encoding="utf-8"))
    return {c["number"]: c for c in doc["crops"]}


def ksa_crops():
    table = load_crop_table()
    out = []
    for key, number in KSA_CROP_ROWS:
        row = dict(table[number])
        row.update({"key": key, "arabic": ARABIC.get(key, ""),
                    "label": f"{key} -- {row['region']} ({row['plant_date']})"})
        out.append(row)
    return out
