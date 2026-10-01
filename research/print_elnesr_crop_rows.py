"""
Prints the Kc, height, stage-duration and tolerance columns of the Elnesr &
Alazba (2016) workbook for the candidate crops we could add (melon, onion,
carrot, garlic, fresh pea), next to what crop_database.py already holds for
crops we have validated (tomato, bell pepper, potato).

Purpose: crop_database.py's rule is that Kc values come from FAO-56 Table 12.
The workbook reproduces FAO-56 tables, but before trusting it for NEW crops we
check that it reproduces the values we already have for OLD ones. Any mismatch
is printed, not hidden.

Not covered here (still open for every crop, old and new): plants per m2,
which crop_database.py marks "TODO verify".

Usage:
    python research/print_elnesr_crop_rows.py
"""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "heatmap"))

from crop_database import CROP_DB  # noqa: E402

WORKBOOK = ROOT / "data" / "sources" / "1-s2.0-S0168169916300989-mmc1.xlsx"

df = pd.read_excel(WORKBOOK, sheet_name="Crops")
df["Crop"] = df["Crop"].astype(str).str.strip()

ROW_COLS = ["Plant Date", "Region", "KCini", "KCmid", "KCend", "Heightx(m)",
            "DURini", "DURdev", "DURmid", "DURlate", "DURtotal", "crTmax", "crTmin"]

# workbook crop name -> crop_database.py key (validated crops used for the cross-check)
CROSS_CHECK = {
    "Tomato": "Tomato",
    "Sweet peppers {bell}": "Pepper,_bell",
    "Potato": "Potato",
}

CANDIDATES = ["Sweet Melons", "Muskmelon", "Cantaloupe", "Onions {dry}",
              "Carrots", "Garlic", "Peas {Fresh}"]


def unique_numbers(series):
    values = pd.to_numeric(series, errors="coerce").dropna()
    return sorted(set(round(float(v), 3) for v in values))


print("=" * 100)
print("CROSS-CHECK: does the workbook reproduce what crop_database.py already holds?")
print("=" * 100)
for wb_name, db_name in CROSS_CHECK.items():
    g = df[df["Crop"] == wb_name]
    db = CROP_DB[db_name]
    print(f"\n{db_name}  (workbook name: {wb_name}, {len(g)} rows)")
    print(f"  database : kc_ini={db['kc_ini']}  kc_mid={db['kc_mid']}  kc_end={db['kc_end']}  height_m={db['height_m']}")
    print(f"  workbook : KCini={unique_numbers(g['KCini'])}  KCmid={unique_numbers(g['KCmid'])}  "
          f"KCend={unique_numbers(g['KCend'])}  height={unique_numbers(g['Heightx(m)'])}")
print("\n(Corn is skipped on purpose: the database uses FIELD maize, the workbook only has sweet corn.)")

print("\n" + "=" * 100)
print("CANDIDATES: every workbook row")
print("=" * 100)
for name in CANDIDATES:
    g = df[df["Crop"] == name]
    print(f"\n{name}  ({len(g)} rows)")
    if g.empty:
        print("  not found -- check the crop name against list_elnesr_crops.py output")
        continue
    print(g[ROW_COLS].to_string(index=False))
