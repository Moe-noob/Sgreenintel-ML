"""
Step 4, stage 1: five more annual crops in the advisor, tracker and Plan page.

  Added   : Onion (dry), Carrot, Garlic, Lettuce, Sweet corn.
  Deferred: Broccoli (season length fails against FAO's own durations for every heat-unit variant, and its only FAO duration
            row is a non-Saudi one) and Melon (warm-season crop whose headline picks land in autumn -- a warning sign, the same
            result as in the first dry run).

Every number comes from a source that was checked:
  Kc, height   FAO-56 Rev.1 (2025) Table 6.1 / 6.2 -- read back from the PDF row by row for these five crops
  stage GDD    FAO-56 Rev.1 Table 6.11 (field-observed heat units; identical to Paredes et al. 2025 Table 5) -- all 32 stage rows
               in that table were machine-checked against the PDF
  Tbase/Tupper FAO-56 Rev.1 Table 6.10
  tolerances   Elnesr & Alazba (2016) workbook, Crops sheet (crTmax / crTmin)
Heat-unit variant per crop (short / long / mean of both) was chosen BEFORE adding, by how close the simulated season length
came to FAO-56's arid-region duration over the 11 cities: onion and carrot have one row; garlic uses the mean of the short and
long rows (0.94x FAO); lettuce the long row (0.87x); sweet corn the short row (0.85x).

Known limits (also shown in the app): none of these crops can be checked against AquaCrop (it has no crop file for them), so the
cards say "Not checked against AquaCrop"; onion seasons run about a third shorter than FAO's arid-region duration (0.67x); on the
warm coast (Jeddah, Jazan, Makkah) simulated seasons are shorter than FAO's durations for all of these crops, the same heat-
acceleration effect seen in tomato and pepper.

Also in this patch
  * season_simulator.py: at most ONE stage boundary per day. Lettuce's late stage needs only 20 heat units, which one hot day can
    exceed, so the old loop produced a zero-day stage and a division by zero. The four existing crops never had a zero-day stage,
    so their results are unchanged (checked: 44 of 44 headline picks identical).
  * care/tracker.py: for a crop with no species care profile (all five new ones) the "General watering" card now says
    "No crop-specific care notes yet; follow the water amount shown." instead of the dangling "See care profile", and no
    invented "Full sun" default is returned. The four existing crops have profiles and are unchanged.
  * index.html: the new crops in the Track dropdown, and a small "Not checked against AquaCrop" badge on every card whose crop is
    not one of the three AquaCrop-checked crops (tomato, potato, corn) -- this includes bell pepper, which was never checked.

Same safety rules as the other patch scripts: every anchor must match exactly once or that file is left untouched, a .bak4 copy is
saved, running twice is harmless, --dry-run reports without writing.

Run from the project root:
    python apply_step4_patch.py --dry-run
    python apply_step4_patch.py
"""

import sys
from pathlib import Path

DRY = "--dry-run" in sys.argv

NO_SPACING = '"plants_per_m2": None, "spacing_source": "none: litres per plant need a user-supplied density",'

NEW_CROPS = '''    "Onion": {
        "t_max_tolerable": 35.0, "t_min_tolerable": 2.0,
        "tolerance_source": "Elnesr & Alazba 2016 workbook, Crops sheet, Onions {dry} (crTmax 35, crTmin 2)",
        "kind": "annual",
        # [FAO56R1] Table 6.1: Onions, dry: Kc ini 0.70, mid 1.05, end 0.70, h 0.45 m
        "kc_ini": 0.70, "kc_mid": 1.05, "kc_end": 0.70, "height_m": 0.45,
        "kc_source": "FAO-56 Rev.1 (2025) Table 6.1, Onions (dry)",
        "t_base": 4.5, "t_upper": 35.0,
        "gdd_stages": {"ini": 460, "dev": 470, "mid": 880, "late": 480},
        "gdd_source": "FAO-56 Rev.1 (2025) Table 6.11, Onions (dry), common (= Paredes et al. 2025 Table 5)",
        "fao56_table11_days": {"Arid Region; Calif., Oct; Jan.": (20, 35, 110, 45)},
        __NO_SPACING__
    },
    "Carrot": {
        "t_max_tolerable": 28.0, "t_min_tolerable": 6.0,
        "tolerance_source": "Elnesr & Alazba 2016 workbook, Crops sheet, Carrots (crTmax 28, crTmin 6)",
        "kind": "annual",
        # [FAO56R1] Table 6.1: Carrots: Kc ini 0.70, mid 1.00, end 0.85, h 0.30 m
        "kc_ini": 0.70, "kc_mid": 1.00, "kc_end": 0.85, "height_m": 0.30,
        "kc_source": "FAO-56 Rev.1 (2025) Table 6.1, Carrots",
        "t_base": 6.0, "t_upper": 30.0,
        "gdd_stages": {"ini": 320, "dev": 465, "mid": 500, "late": 290},
        "gdd_source": "FAO-56 Rev.1 (2025) Table 6.11, Carrots, common (= Paredes et al. 2025 Table 5)",
        "fao56_table11_days": {"Arid climate, Oct/Jan": (20, 30, 40, 20)},
        __NO_SPACING__
    },
    "Garlic": {
        "t_max_tolerable": 30.0, "t_min_tolerable": 8.0,
        "tolerance_source": "Elnesr & Alazba 2016 workbook, Crops sheet, Garlic (crTmax 30, crTmin 8)",
        "kind": "annual",
        # [FAO56R1] Table 6.1: Garlic: Kc ini 0.70, mid 1.05, end 0.70, h 0.50 m
        "kc_ini": 0.70, "kc_mid": 1.05, "kc_end": 0.70, "height_m": 0.50,
        "kc_source": "FAO-56 Rev.1 (2025) Table 6.1, Garlic",
        "t_base": 4.0, "t_upper": 30.0,
        # Rev.1 Table 6.11 has a short row (150/340/335/315) and a long row (580/615/315/240). The mean of the two was
        # used: it gave 0.94x FAO-56's duration over the 11 cities (short 0.77x, long 1.13x).
        "gdd_stages": {"ini": 365, "dev": 478, "mid": 325, "late": 278},
        "gdd_source": "FAO-56 Rev.1 (2025) Table 6.11, Garlic: mean of the short and long season rows",
        "fao56_table11_days": {"Undefined": (20, 30, 30, 20)},
        __NO_SPACING__
    },
    "Lettuce": {
        "t_max_tolerable": 27.0, "t_min_tolerable": 5.0,
        "tolerance_source": "Elnesr & Alazba 2016 workbook, Crops sheet, Lettuce (crTmax 27, crTmin 5)",
        "kind": "annual",
        # [FAO56R1] Table 6.1: Lettuce: Kc ini 0.70, mid 1.05, end 1.05, h 0.35 m
        "kc_ini": 0.70, "kc_mid": 1.05, "kc_end": 1.05, "height_m": 0.35,
        "kc_source": "FAO-56 Rev.1 (2025) Table 6.1, Lettuce",
        "t_base": 4.0, "t_upper": 28.0,
        # Rev.1 Table 6.11 long-season row (360/455/455/20): 0.87x FAO-56's duration (short row 0.65x).
        "gdd_stages": {"ini": 360, "dev": 455, "mid": 455, "late": 20},
        "gdd_source": "FAO-56 Rev.1 (2025) Table 6.11, Lettuce, long season",
        "fao56_table11_days": {"Arid Region, Oct/Nov": (25, 35, 30, 10)},
        __NO_SPACING__
    },
    "Sweet_corn": {
        "t_max_tolerable": 40.0, "t_min_tolerable": 10.0,
        "tolerance_source": "Elnesr & Alazba 2016 workbook, Crops sheet, Sweet corn (crTmax 40, crTmin 10)",
        "kind": "annual",
        # [FAO56R1] Table 6.2: Maize, sweet: Kc ini 0.30, mid 1.15, end 1.05, h 1.5-2.5 m -> midpoint 2.0 m
        "kc_ini": 0.30, "kc_mid": 1.15, "kc_end": 1.05, "height_m": 2.0,
        "kc_source": "FAO-56 Rev.1 (2025) Table 6.2, Maize sweet (h = midpoint of 1.5-2.5 m)",
        "t_base": 10.0, "t_upper": 32.0,
        # Rev.1 Table 6.11 short-season row (200/310/360/115): 0.85x FAO-56's duration (long row 1.70x).
        "gdd_stages": {"ini": 200, "dev": 310, "mid": 360, "late": 115},
        "gdd_source": "FAO-56 Rev.1 (2025) Table 6.11, Maize sweet, short season",
        "fao56_table11_days": {"Undefined": (20, 30, 20, 10)},
        __NO_SPACING__
    },
'''.replace("__NO_SPACING__", NO_SPACING)

CROP_DB = ("heatmap/crop_database.py", '"Onion": {', [
    ("new crops", '''    "Strawberry": {''', NEW_CROPS + '''    "Strawberry": {''', False),
])

SIM = ("heatmap/season_simulator.py", "at most ONE stage boundary per day", [
    ("one boundary per day",
     '''        while len(boundaries) < 4 and cum >= targets[len(boundaries)]:
            boundaries.append(n + 1)      # stage ends after day n+1''',
     '''        if len(boundaries) < 4 and cum >= targets[len(boundaries)]:   # at most ONE stage boundary per day, so every stage lasts >= 1 day
            boundaries.append(n + 1)      # stage ends after day n+1''', False),
])

HTML = ("index.html", 'value="Sweet_corn"', [
    ("Track dropdown",
     '''            <option value="Corn_(maize)">Corn</option>''',
     '''            <option value="Corn_(maize)">Corn</option>
            <option value="Onion">Onion</option>
            <option value="Carrot">Carrot</option>
            <option value="Garlic">Garlic</option>
            <option value="Lettuce">Lettuce</option>
            <option value="Sweet_corn">Sweet corn</option>''', False),
    ("not-checked badge",
     '''${shockFree ? 'Shock-free window found' : 'Least-water viable'}</span>''',
     '''${shockFree ? 'Shock-free window found' : 'Least-water viable'}</span>
              ${['Tomato', 'Potato', 'Corn_(maize)'].includes(scan.crop) ? '' : '<span class="badge info">Not checked against AquaCrop</span>'}''', False),
])

TRACKER = ("care/tracker.py", "No crop-specific care notes yet", [
    ("watering fallback",
     '''"watering_guidance": species.get("watering", "See care profile"),''',
     '''"watering_guidance": species.get("watering", "No crop-specific care notes yet; follow the water amount shown."),''', False),
    ("sun fallback",
     '''"sun": species.get("sun", "Full sun"),''',
     '''"sun": species.get("sun"),''', False),
])

PLAN = [CROP_DB, SIM, TRACKER, HTML]


def process(path_str, marker, edits):
    path = Path(path_str)
    if not path.exists():
        return f"{path_str}: NOT FOUND. Run this from the project root."
    raw = path.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in raw else "\n"
    if marker in raw:
        return f"{path_str}: already applied."
    text, failed = raw, []
    for label, old, new, optional in edits:
        o, n = old.replace("\n", nl), new.replace("\n", nl)
        c = text.count(o)
        if c == 1:
            text = text.replace(o, n)
        elif not optional:
            failed.append(f"'{label}' (anchor found {c} times, expected 1)")
    if failed:
        return f"{path_str}: NOT CHANGED -- " + "; ".join(failed)
    if path_str.endswith(".py"):
        try:
            compile(text, path_str, "exec")
        except SyntaxError as exc:
            return f"{path_str}: NOT CHANGED -- the edit would break the file ({exc})"
    if not DRY:
        path.with_name(path.name + ".bak4").write_bytes(raw.encode("utf-8"))
        path.write_bytes(text.encode("utf-8"))
    return f"{path_str}: " + ("would be changed" if DRY else f"done (backup {path.name}.bak4)")


def main():
    print("DRY RUN: nothing will be written.\n" if DRY else "")
    for entry in PLAN:
        print(process(*entry))
    print("\nNext: restart the API server and hard-refresh the page (Ctrl+Shift+R).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
