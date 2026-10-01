"""
Step 4, stage 2: five warm-season crops (spring / summer / autumn types), labelled LOWER CONFIDENCE.

  Added   : Cucumber (fresh market), Eggplant, Squash (zucchini), Pumpkin, Green bean.
  Deferred: Cabbage, Cauliflower, Spinach, Lentil. Simulated seasons run 0.40-0.72x FAO-56's arid durations for every heat-unit
            variant, cabbage and cauliflower spend half the season in the initial stage (790 / 700 of ~1,700 heat units), and
            lentil's cold floor in the workbook (15 C) is implausible for a winter legume.
  Not possible: watermelon, radish, okra, molokhia (no heat-unit data in Rev.1 for any of them).

Evidence, and its limits
  * Kc and height : FAO-56 Rev.1 Table 6.1, read back from the PDF row by row. Tbase/Tupper (Table 6.10) and the stage heat-unit rows
                    (Table 6.12) were machine-checked against the PDF.
  * Table 6.12 gives each of these crops as a MIN-length row and a MAX-length row derived from FAO-56's 1998 DURATIONS (not field
    observations), and the two rows are far apart (cucumber 970-1,520 heat units, green bean 450-1,170). The variant for each crop
    (min, max or mean) was chosen BEFORE looking at the Saudi calendars, by closeness of the simulated season length to FAO-56's
    arid-region duration over the 11 cities: cucumber mean 0.97x, eggplant max 0.95x, squash max 0.91x, pumpkin max 1.05x, green bean
    mean 0.80x.
  * AquaCrop has no file for any of them, so none is checked against it (cards say so).
  * Saudi calendars (Alsadon 2002, Table 5; 5 cases): the SPRING pick lands inside the directorate window in 4 of 5 cases; random dates
    give about 3.2 of 5, because the windows are broad. So the calendars are consistent with the picks but do not prove them.

Headline rule for these five crops (needs heatmap/season_picks.py from the same download)
  The least-water-per-day headline rule is validated against AquaCrop for tomato, potato and corn only. For these five cold-sensitive
  crops it picks winter sowings in about half the cities (median 56-77 cold days for cucumber, eggplant, pumpkin). Their card headline is
  therefore the autumn or spring pick with the FEWEST exceedance days (ties: lower water per day), and their SPRING pick is itself the
  spring date with the fewest exceedance days, so the headline is never worse than the default rule's choice. The default rule's choice
  is kept in the data (scan["best_default_rule"]). With this rule the headline lands inside the Saudi directorate window in 5 of 5
  cases (default rule: 1 of 5; a random date: 2.0 expected, p = 0.08 for 4 or more). The rule was adjusted after seeing those cases for
  an internal reason (a headline worse than the default in 3 of 55 city x crop cases), so treat 5 of 5 with caution.

Also in this patch (index.html)
  * Track dropdown: the five crops.
  * Card badge: "Shock-free window found" now reflects the headline date's own exceedance days (identical result for every existing
    crop); when no shock-free date exists these five say "Fewest exceedance days" instead of "Least-water viable" (which would be
    untrue for them); and a "Lower confidence" badge on these five, with the reason as its tooltip.
  * Chart note: for these crops it says the outlined bar is chosen by fewest exceedance days, and the "only N dates are exceedance-free"
    sentence (which assumes the headline is picked among them) is skipped.

Same safety rules as the other patch scripts: every anchor must match exactly once or that file is left untouched, a .bak5 copy is saved,
running twice is harmless, --dry-run reports without writing.

Run from the project root, AFTER copying the new season_picks.py over heatmap/season_picks.py:
    python apply_step5_patch.py --dry-run
    python apply_step5_patch.py
"""

import sys
from pathlib import Path

DRY = "--dry-run" in sys.argv

NO_SPACING = '"plants_per_m2": None, "spacing_source": "none: litres per plant need a user-supplied density",'
CONF = ('"confidence": "lower", "headline_rule": "fewest_exceedance_days",\n'
        '        "confidence_note": "Heat units are a min/max range derived from the 1998 FAO-56 durations (Rev.1 Table 6.12), not field '
        'observed, and AquaCrop cannot check this crop",')

NEW_CROPS = '''    "Cucumber": {
        "t_max_tolerable": 35.0, "t_min_tolerable": 16.0,
        "tolerance_source": "Elnesr & Alazba 2016 workbook, Crops sheet, Cucumber {Fresh Market} (crTmax 35, crTmin 16)",
        "kind": "annual",
        # [FAO56R1] Table 6.1: Cucumber, fresh market: Kc ini 0.60, mid 1.00, end 0.75, h 0.40 m
        "kc_ini": 0.60, "kc_mid": 1.00, "kc_end": 0.75, "height_m": 0.40,
        "kc_source": "FAO-56 Rev.1 (2025) Table 6.1, Cucumber fresh market",
        "t_base": 10.0, "t_upper": 32.0,
        # Rev.1 Table 6.12: min row 80/170/450/270, max row 370/510/520/120 (derived from 1998 durations). Mean used: 0.97x FAO-56's
        # duration over the 11 cities (min row 0.81x, max row 1.13x).
        "gdd_stages": {"ini": 225, "dev": 340, "mid": 485, "late": 195},
        "gdd_source": "FAO-56 Rev.1 (2025) Table 6.12, Cucumber fresh market: mean of the min and max length rows",
        "fao56_table11_days": {"Arid Region, June/Aug": (20, 30, 40, 15), "Arid Region, Nov; Feb": (25, 35, 50, 20)},
        __CONF__
        __NO_SPACING__
    },
    "Eggplant": {
        "t_max_tolerable": 35.0, "t_min_tolerable": 15.0,
        "tolerance_source": "Elnesr & Alazba 2016 workbook, Crops sheet, EggPlant (crTmax 35, crTmin 15)",
        "kind": "annual",
        # [FAO56R1] Table 6.1: Eggplant: Kc ini 0.60, mid 1.05, end 0.95, h 0.80 m
        "kc_ini": 0.60, "kc_mid": 1.05, "kc_end": 0.95, "height_m": 0.80,
        "kc_source": "FAO-56 Rev.1 (2025) Table 6.1, Eggplant",
        "t_base": 10.0, "t_upper": 35.0,
        # Rev.1 Table 6.12: min row 280/440/380/80, max row 230/540/480/180. Max row used: 0.95x FAO-56's duration (min row 0.83x,
        # mean 0.94x).
        "gdd_stages": {"ini": 230, "dev": 540, "mid": 480, "late": 180},
        "gdd_source": "FAO-56 Rev.1 (2025) Table 6.12, Eggplant, max length row",
        "fao56_table11_days": {"Arid Region, Oct": (30, 40, 40, 20)},
        __CONF__
        __NO_SPACING__
    },
    "Squash": {
        "t_max_tolerable": 38.0, "t_min_tolerable": 15.0,
        "tolerance_source": "Elnesr & Alazba 2016 workbook, Crops sheet, Squash (crTmax 38, crTmin 15)",
        "kind": "annual",
        # [FAO56R1] Table 6.1: Zucchini, Squash (Cucurbita pepo): Kc ini 0.50, mid 1.00, end 0.70, h 0.50 m
        "kc_ini": 0.50, "kc_mid": 1.00, "kc_end": 0.70, "height_m": 0.50,
        "kc_source": "FAO-56 Rev.1 (2025) Table 6.1, Zucchini / Squash",
        "t_base": 10.0, "t_upper": 32.0,
        # Rev.1 Table 6.12: min row 90/200/210/130, max row 160/370/360/260. Max row used: 0.91x FAO-56's duration (min row 0.42x,
        # mean 0.72x).
        "gdd_stages": {"ini": 160, "dev": 370, "mid": 360, "late": 260},
        "gdd_source": "FAO-56 Rev.1 (2025) Table 6.12, Squash / Zucchini, max length row",
        "fao56_table11_days": {"Medit.; Arid Reg., Apr; Dec.": (25, 35, 25, 15)},
        __CONF__
        __NO_SPACING__
    },
    "Pumpkin": {
        "t_max_tolerable": 38.0, "t_min_tolerable": 15.0,
        "tolerance_source": "Elnesr & Alazba 2016 workbook, Crops sheet, Pumpkin (crTmax 38, crTmin 15)",
        "kind": "annual",
        # [FAO56R1] Table 6.1: Pumpkin, winter squash (Cucurbita pepo): Kc ini 0.50, mid 0.95, end 0.70, h 0.40 m
        "kc_ini": 0.50, "kc_mid": 0.95, "kc_end": 0.70, "height_m": 0.40,
        "kc_source": "FAO-56 Rev.1 (2025) Table 6.1, Pumpkin / winter squash",
        "t_base": 10.0, "t_upper": 32.0,
        # Rev.1 Table 6.12: min row 170/380/370/150, max row 230/440/430/200. Max row used: 1.05x FAO-56's duration (min row 0.85x,
        # mean 0.92x).
        "gdd_stages": {"ini": 230, "dev": 440, "mid": 430, "late": 200},
        "gdd_source": "FAO-56 Rev.1 (2025) Table 6.12, Pumpkin, max length row",
        "fao56_table11_days": {"Mediterranean, Mar, Aug": (20, 30, 30, 20)},
        __CONF__
        __NO_SPACING__
    },
    "Green_bean": {
        "t_max_tolerable": 35.0, "t_min_tolerable": 15.0,
        "tolerance_source": "Elnesr & Alazba 2016 workbook, Crops sheet, Beans, green (crTmax 35, crTmin 15)",
        "kind": "annual",
        # [FAO56R1] Table 6.1: Common bean, green: Kc ini 0.50, mid 1.05, end 0.95, h 0.50-0.70 m -> midpoint 0.60 m
        "kc_ini": 0.50, "kc_mid": 1.05, "kc_end": 0.95, "height_m": 0.60,
        "kc_source": "FAO-56 Rev.1 (2025) Table 6.1, Common bean green (h = midpoint of 0.5-0.7 m)",
        "t_base": 10.0, "t_upper": 32.0,
        # Rev.1 Table 6.12: min row 20/110/220/100, max row 230/390/400/150. Mean used: 0.80x FAO-56's duration (min row 0.47x,
        # max row 1.29x).
        "gdd_stages": {"ini": 125, "dev": 250, "mid": 310, "late": 125},
        "gdd_source": "FAO-56 Rev.1 (2025) Table 6.12, Beans green: mean of the min and max length rows",
        "fao56_table11_days": {"Calif., Mediterranean, Feb/Mar": (20, 30, 30, 10), "Calif., Egypt, Lebanon, Aug/Sep": (15, 25, 25, 10)},
        __CONF__
        __NO_SPACING__
    },
'''.replace("__CONF__", CONF).replace("__NO_SPACING__", NO_SPACING)

CROP_DB = ("heatmap/crop_database.py", '"Cucumber": {', [
    ("new crops", '''    "Strawberry": {''', NEW_CROPS + '''    "Strawberry": {''', False),
])

HTML = ("index.html", 'value="Green_bean"', [
    ("Track dropdown",
     '''            <option value="Sweet_corn">Sweet corn</option>''',
     '''            <option value="Sweet_corn">Sweet corn</option>
            <option value="Cucumber">Cucumber</option>
            <option value="Eggplant">Eggplant</option>
            <option value="Squash">Squash</option>
            <option value="Pumpkin">Pumpkin</option>
            <option value="Green_bean">Green bean</option>''', False),
    ("badge reflects the headline date",
     '''const shockFree = scan.n_shock_free > 0;''',
     '''const shockFree = (b.heat_shock_days + b.cold_shock_days) === 0;''', False),
    ("badge wording for override crops",
     ''''Shock-free window found' : 'Least-water viable'}''',
     ''''Shock-free window found' : (scan.headline_rule ? 'Fewest exceedance days' : 'Least-water viable')}''', False),
    ("lower-confidence badge",
     '''<span class="badge info">Not checked against AquaCrop</span>'}''',
     '''<span class="badge info">Not checked against AquaCrop</span>'}
              ${scan.confidence ? '<span class="badge info" title="' + (scan.confidence_note || '') + '">Lower confidence</span>' : ''}''', False),
    ("chart: skip the exceedance-free sentence for override crops",
     '''if (scan.best && freeRuns.length > 0 && freeRuns.length < viableRuns.length) {''',
     '''if (!scan.headline_rule && scan.best && freeRuns.length > 0 && freeRuns.length < viableRuns.length) {''', False),
    ("chart: headline note",
     '''const totalSvg = profileSvg(''',
     '''const headlineNote = scan.headline_rule ? 'For this crop the outlined bar is not the lowest-water date: it is the autumn or spring pick with the fewest exceedance days (ties: lowest water per day). The sentence below about the lowest water per day describes the rule used for the other crops. ' : '';
  const totalSvg = profileSvg(''', False),
    ("chart: print the note",
     '''${eligibleNote}Each bar is one candidate start date''',
     '''${headlineNote}${eligibleNote}Each bar is one candidate start date''', False),
])

PLAN = [CROP_DB, HTML]


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
        path.with_name(path.name + ".bak5").write_bytes(raw.encode("utf-8"))
        path.write_bytes(text.encode("utf-8"))
    return f"{path_str}: " + ("would be changed" if DRY else f"done (backup {path.name}.bak5)")


def main():
    sp = Path("heatmap/season_picks.py")
    if not sp.exists() or "fewest_exceedance_days" not in sp.read_text(encoding="utf-8"):
        print("heatmap/season_picks.py is missing or is the OLD version. Copy the new season_picks.py over it first "
              "(Move-Item -Force), then run this again.")
        return 1
    print("DRY RUN: nothing will be written.\n" if DRY else "")
    for entry in PLAN:
        print(process(*entry))
    print("\nNext: restart the API server and hard-refresh the page (Ctrl+Shift+R).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
