"""
Lists the crops in the Elnesr & Alazba (2016) supplementary workbook's
"Crops" sheet with their sourced heat/cold tolerance thresholds, so we know
which candidate crops (watermelon, cucumber, eggplant, melon, ...) already
have sourced tolerances before anything is added to crop_database.py.

Layout (seen in the first run): columns include Family, Crop, Plant Date,
Region, KCini/KCmid/KCend, DUR* (stage lengths, days), crTmax, crTmin,
crTbase, crTopt and heat-unit columns. The workbook has several rows per
crop (different planting dates / regions), so rows are grouped by the Crop
column.

Usage:
    python research/list_elnesr_crops.py
"""

import re
from pathlib import Path

import pandas as pd

WORKBOOK = (Path(__file__).resolve().parent.parent / "data" / "sources"
            / "1-s2.0-S0168169916300989-mmc1.xlsx")

df = pd.read_excel(WORKBOOK, sheet_name="Crops")
needed = ["Crop", "Family", "Plant Date", "Region", "DURtotal", "crTmax", "crTmin", "crTbase", "crTopt"]
missing = [c for c in needed if c not in df.columns]
if missing:
    raise SystemExit(f"Missing columns {missing}; the sheet's columns are: {list(df.columns)}")

df["Crop"] = df["Crop"].astype(str).str.strip()


def values(series):
    return sorted(set(float(v) for v in series.dropna()))


print(f"{df['Crop'].nunique()} distinct crops in {len(df)} rows\n")
print(f"{'Crop':<32}{'rows':>5}  {'crTmax':<10}{'crTmin':<10}Family")
for crop, g in df.groupby("Crop"):
    family = re.sub(r"\s*\(.*$", "", str(g["Family"].iloc[0])).strip()
    print(f"{crop:<32}{len(g):>5}  {str(values(g['crTmax'])):<10}{str(values(g['crTmin'])):<10}{family}")

pattern = r"water|melon|cantal|cucum|egg|onion|garlic|carrot|\bpeas?\b|cauli"
cand = df[df["Crop"].str.contains(pattern, case=False, regex=True, na=False)]
print(f"\nCandidate crops from the Saudipedia lists -- every matching row ({len(cand)}):")
if cand.empty:
    print("  none matched")
else:
    cols = ["Crop", "Plant Date", "Region", "DURtotal", "crTmax", "crTmin", "crTbase", "crTopt"]
    print(cand[cols].to_string(index=False))