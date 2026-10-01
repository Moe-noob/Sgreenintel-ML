"""
Crop database -- the SINGLE source of truth for every per-crop number
used by the advisor. Every value carries its source. If a number is not
here with a source, it is not in the pipeline.

Sources
-------
[FAO56]   Allen, Pereira, Raes, Smith (1998). FAO Irrigation & Drainage
          Paper 56. Table 12 (Kc ini/mid/end, max height h) and Table 11
          (indicative stage lengths, days). Kc mid/end are for a sub-humid
          standard climate (RHmin 45 %, u2 2 m/s) and are climate-adjusted
          at run time with Eq. 62 / Eq. 65.
[FAO56R1] Pereira, Allen, Paredes, Lopez-Urrea, Raes, Smith, Kilic, Salman (2025).
          Crop evapotranspiration -- Guidelines for computing crop water requirements,
          FAO Irrigation & Drainage Paper 56 Rev.1, doi:10.4060/cd6621en. Tables 6.1 / 6.2
          (Kc ini/mid/end, max height h): used for the Kc values below, replacing the 1998
          values. Kc mid/end are for the same standard climate (RHmin 45 %, u2 2 m/s) and
          are climate-adjusted at run time with Eq. 62 / Eq. 65 as before.
[PAR25]   Paredes, Lopez-Urrea, Martinez-Romero, Petry, Cameira, Montoya,
          Salman, Pereira (2025). "Estimating the lengths of crop growth
          stages to define the crop coefficient curves using growing degree
          days (GDD): Application of the revised FAO56 guidelines."
          Agricultural Water Management 319:109758. Tables 1-3 (Tbase,
          Tupper) and Tables 5-6 (cumulative GDD per FAO stage).
          GDD = clamp(Tavg - Tbase, 0, Tupper - Tbase), Tavg = (Tmax+Tmin)/2.
[ELN16]   Elnesr & Alazba (2016). "A spreadsheet model to select vegetables
          planting dates for maximum yield and water use efficiency."
          Computers and Electronics in Agriculture 124:55-64 (King Saud
          University). Provides the selection framework used by the
          simulator: heat units satisfied -> heat/cold-shock check ->
          choose the planting date with minimum seasonal ETc.
[ELN16-S] Elnesr & Alazba (2016) Appendix A supplementary workbook
          (mmc1.xlsx, sheet "Crops"): crop maximum / minimum tolerable
          temperatures (crTmax, crTmin) used for the heat/cold-shock test
          (Tx <= Txc and Tn >= Tnc). Values verified directly against the
          downloaded workbook (columns crTmax, crTmin); identical across all
          regional rows of each crop. Grape, apple and field maize are not in
          the sheet. The sheet also lists Strawberries (Oct, Calif., USA) with
          stage lengths 60/160/60/30 d = 310 d -- a California annual-hill
          system, not used here because it does not match KSA practice.
[MEWA]    Saudi Ministry of Environment, Water & Agriculture (via SPA /
          Arab News, Mar 2025; Saudipedia): grapes grown in KSA are table
          grapes (Tabuk, Qassim, Hail, Asir; harvest Jun-Sep).

Perennials (Grape, Apple)
-------------------------
No planting-date scan is meaningful for a vine/tree that is planted once
and cropped for decades. For these we model ONE annual cycle of an
ESTABLISHED plant, using FAO-56 Table 11 stage lengths anchored at the
listed start month, and report annual water use per stage. The multi-
year establishment period before first harvest is NOT modelled and is
stated as such in the output.
"""

CROP_DB = {
    # ------------------------------------------------------------------
    "Tomato": {
        "t_max_tolerable": 35.0, "t_min_tolerable": 14.0,
        "tolerance_source": "ELN16-S Crops sheet, Tomato (crTmax 35, crTmin 14) -- verified against mmc1.xlsx Crops sheet",
        "kind": "annual",
        # [FAO56R1] Table 6.1 (book p. 166), Tomato, fresh market: Kc ini 0.60, mid 1.10, end 1.00, h 0.6 m.
        # (FAO-56 1998 Table 12 gave 0.60 / 1.15 / 0.80.)
        "kc_ini": 0.60, "kc_mid": 1.10, "kc_end": 1.00, "height_m": 0.6,
        "kc_source": "FAO-56 Rev.1 (2025) Table 6.1, Tomato fresh market",
        # [PAR25] Table 1 / Table 5 ("Market" tomato)
        "t_base": 7.0, "t_upper": 28.0,
        "gdd_stages": {"ini": 325, "dev": 660, "mid": 880, "late": 200},
        "gdd_source": "Paredes et al. 2025, Table 5, Tomato (market)",
        # [FAO56] Table 11 arid-region calendars, days -- used only as a sanity reference
        "fao56_table11_days": {"Jan, Arid Region": (30, 40, 40, 25), "Oct/Nov, Arid Region": (35, 45, 70, 30)},
        "plants_per_m2": 2.5, "spacing_source": "TODO verify: row x in-row spacing citation needed",
    },
    # ------------------------------------------------------------------
    "Pepper,_bell": {
        "t_max_tolerable": 35.0, "t_min_tolerable": 15.0,
        "tolerance_source": "ELN16-S Crops sheet, Sweet peppers (bell) (crTmax 35, crTmin 15) -- verified against mmc1.xlsx Crops sheet",
        "kind": "annual",
        # [FAO56R1] Table 6.1 (book p. 166), Bell pepper: Kc ini 0.60, mid 1.10, end 1.00, h 0.70 m.
        # (FAO-56 1998 Table 12 gave 0.60 / 1.05 / 0.90.)
        "kc_ini": 0.60, "kc_mid": 1.10, "kc_end": 1.00, "height_m": 0.7,
        "kc_source": "FAO-56 Rev.1 (2025) Table 6.1, Bell pepper",
        # [PAR25] Table 1 (Bell & chili pepper 10/35), Table 5
        "t_base": 10.0, "t_upper": 35.0,
        "gdd_stages": {"ini": 445, "dev": 1180, "mid": 745, "late": 45},
        "gdd_source": "Paredes et al. 2025, Table 5, Bell pepper (common)",
        "fao56_table11_days": {"Oct, Arid Region": (30, 40, 110, 30)},
        "plants_per_m2": 5.0, "spacing_source": "TODO verify: Utah State Extension 18-24 in gives 2.7-4.8/m2",
    },
    # ------------------------------------------------------------------
    "Potato": {
        "t_max_tolerable": 27.0, "t_min_tolerable": 7.0,
        "tolerance_source": "ELN16-S Crops sheet, Potato (crTmax 27, crTmin 7) -- verified against mmc1.xlsx Crops sheet",
        "kind": "annual",
        # [FAO56R1] Table 6.1 (book p. 165), Potato, LONG season (matches the long-season GDD row used below):
        # Kc ini 0.50, mid 1.10, end 0.40, h 0.60 m. (A short-season crop would be end 0.60.)
        # (FAO-56 1998 Table 12 gave 0.50 / 1.15 / 0.75.)
        "kc_ini": 0.50, "kc_mid": 1.10, "kc_end": 0.40, "height_m": 0.6,
        "kc_source": "FAO-56 Rev.1 (2025) Table 6.1, Potato long season",
        # [PAR25] Table 1 (2/30), Table 5 short season
        "t_base": 2.0, "t_upper": 30.0,
        "gdd_stages": {"ini": 405, "dev": 530, "mid": 490, "late": 835},
        "gdd_source": "Paredes et al. 2025, Table 5, Potato (long season) -- reference phenology selected for consistency with FAO-56 Table 11 arid-region potato duration (115-130 d); the short-season row gave 63-81 d. This is a modelling choice, not evidence about Saudi cultivars.",
        "fao56_table11_days": {"Jan/Nov, (Semi) Arid": (25, 30, 45, 30)},
        "plants_per_m2": 5.0, "spacing_source": "TODO verify: 10-12 in x 30-36 in rows gives 3.6-5.2/m2",
    },
    # ------------------------------------------------------------------
    "Corn_(maize)": {
        "t_max_tolerable": 40.0, "t_min_tolerable": 10.0,
        "tolerance_source": "ELN16-S Crops sheet, Sweet corn (crTmax 40, crTmin 10) -- field maize not in sheet; same species (Zea mays) used as proxy -- verified against mmc1.xlsx Crops sheet",
        "disclosure": "Temperature-tolerance thresholds use the sweet-corn row as a proxy; the Elnesr & Alazba dataset has no field-maize entry. Kc and GDD values are for field (grain) maize.",
        "kind": "annual",
        # [FAO56R1] Table 6.2 (book p. 169), Maize, grain, LOW grain moisture at harvest: Kc ini 0.30, mid 1.20,
        # end 0.30; h 2.50-3.50 m -> midpoint 3.0 m. (FAO-56 1998: 0.30 / 1.20 / 0.35, h 2.0.)
        "kc_ini": 0.30, "kc_mid": 1.20, "kc_end": 0.30, "height_m": 3.0,
        "kc_source": "FAO-56 Rev.1 (2025) Table 6.2, Maize grain, low grain moisture (h = midpoint of 2.5-3.5 m)",
        # [PAR25] Table 2 (10/32), Table 5 Maize grain short season
        "t_base": 10.0, "t_upper": 32.0,
        "gdd_stages": {"ini": 200, "dev": 380, "mid": 500, "late": 340},
        "gdd_source": "Paredes et al. 2025, Table 5, Maize grain (short season)",
        "fao56_table11_days": {"Dec/Jan, Arid Climate": (25, 40, 45, 30)},
        "plants_per_m2": 5.0, "spacing_source": "TODO verify: 9-12 in x 24-36 in rows gives 3.6-7.2/m2",
    },
    # ------------------------------------------------------------------
    "Onion": {
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
        "plants_per_m2": None, "spacing_source": "none: litres per plant need a user-supplied density",
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
        "plants_per_m2": None, "spacing_source": "none: litres per plant need a user-supplied density",
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
        "plants_per_m2": None, "spacing_source": "none: litres per plant need a user-supplied density",
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
        "plants_per_m2": None, "spacing_source": "none: litres per plant need a user-supplied density",
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
        "plants_per_m2": None, "spacing_source": "none: litres per plant need a user-supplied density",
    },
    "Cucumber": {
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
        "confidence": "lower", "headline_rule": "fewest_exceedance_days",
        "confidence_note": "Heat units are a min/max range derived from the 1998 FAO-56 durations (Rev.1 Table 6.12), not field observed, and AquaCrop cannot check this crop",
        "plants_per_m2": None, "spacing_source": "none: litres per plant need a user-supplied density",
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
        "confidence": "lower", "headline_rule": "fewest_exceedance_days",
        "confidence_note": "Heat units are a min/max range derived from the 1998 FAO-56 durations (Rev.1 Table 6.12), not field observed, and AquaCrop cannot check this crop",
        "plants_per_m2": None, "spacing_source": "none: litres per plant need a user-supplied density",
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
        "confidence": "lower", "headline_rule": "fewest_exceedance_days",
        "confidence_note": "Heat units are a min/max range derived from the 1998 FAO-56 durations (Rev.1 Table 6.12), not field observed, and AquaCrop cannot check this crop",
        "plants_per_m2": None, "spacing_source": "none: litres per plant need a user-supplied density",
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
        "confidence": "lower", "headline_rule": "fewest_exceedance_days",
        "confidence_note": "Heat units are a min/max range derived from the 1998 FAO-56 durations (Rev.1 Table 6.12), not field observed, and AquaCrop cannot check this crop",
        "plants_per_m2": None, "spacing_source": "none: litres per plant need a user-supplied density",
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
        "confidence": "lower", "headline_rule": "fewest_exceedance_days",
        "confidence_note": "Heat units are a min/max range derived from the 1998 FAO-56 durations (Rev.1 Table 6.12), not field observed, and AquaCrop cannot check this crop",
        "plants_per_m2": None, "spacing_source": "none: litres per plant need a user-supplied density",
    },
    "Strawberry": {
        "t_max_tolerable": 28.0, "t_min_tolerable": 8.0,
        "tolerance_source": "ELN16-S Crops sheet, Strawberries (crTmax 28, crTmin 8) -- verified against mmc1.xlsx Crops sheet",
        "kind": "annual",   # fruits in first season, unlike Grape/Apple
        # [FAO56R1] Table 6.1 (book p. 166), Strawberries: 0.50 / 0.80 / 0.75, h 0.20 m (1998: 0.40 / 0.85 / 0.75).
        # Strawberry is still excluded from the planting-date scan (no sourced stage GDD).
        "kc_ini": 0.50, "kc_mid": 0.80, "kc_end": 0.75, "height_m": 0.2,
        "kc_source": "FAO-56 Rev.1 (2025) Table 6.1, Strawberries",
        # [PAR25] Table 1 gives Tbase 3 / Tupper 30 but NO cumulative GDD row for strawberry,
        # and FAO-56 Table 11 has no strawberry entry either.
        "t_base": 3.0, "t_upper": 30.0,
        "gdd_stages": None,      # <-- unresolved: no tabulated source found yet
        "gdd_source": "NONE -- strawberry is excluded from the planting-date scan until a sourced stage-length value is added",
        "fao56_table11_days": {},
        "plants_per_m2": 2.5, "spacing_source": "TODO verify: matted-row 18-24 in in-row spacing",
    },
    # ------------------------------------------------------------------
    "Grape": {
        "t_max_tolerable": None, "t_min_tolerable": None,
        "tolerance_source": "not in ELN16-S (vegetables only); shock test not applied to perennials",
        "kind": "perennial",
        # [FAO56] Table 12: Grapes, table or raisin: 0.30 / 0.85 / 0.45, h 2.0  ([MEWA]: KSA grows table grapes)
        "kc_ini": 0.30, "kc_mid": 0.85, "kc_end": 0.45, "height_m": 2.0,
        "kc_source": "FAO56 Table 12, Grapes table/raisin",
        "t_base": 10.0, "t_upper": 35.0,       # [PAR25] Table 3, wine & table grapes
        "gdd_stages": None,                     # [PAR25] Table 6 has WINE grapes only; not used
        # [FAO56] Table 11: Grapes, Low Latitudes, plant/greenup April: 20/40/120/60 = 240 d
        "annual_cycle": {"start_month": 4, "stage_days": (20, 40, 120, 60),
                         "source": "FAO56 Table 11, Grapes, Low Latitudes, April"},
        "establishment": {
            "planting_season": "Plant dormant (bare-root) vines during the dormant season, Dec-Mar, before bud break",
            "years_to_first_harvest": "first meaningful crop in the 3rd growing season; full production later",
            "source": "Oregon State Univ. Extension EC1639 (dormant Dec-Mar; transplant early spring; several years to first crop); "
                      "Univ. of Maryland Extension via Ask Extension (first grapes in the third spring)",
        },
        "establishment_note": "Water use in the establishment years (smaller canopy) is not modelled; the annual table applies to a mature vine.",
        "suitability_status": "established-plant estimate",
        "suitability_reason": "No tolerance thresholds for grape in the Elnesr & Alazba dataset; annual ETc for a mature vine only.",
        "plants_per_m2": 0.2, "spacing_source": "TODO verify: 9 ft x 6 ft = 5.0 m2/vine -> 0.2/m2",
    },
    # ------------------------------------------------------------------
    "Apple": {
        "t_max_tolerable": None, "t_min_tolerable": None,
        "tolerance_source": "not in ELN16-S (vegetables only); shock test not applied to perennials",
        "kind": "perennial",
        # [FAO56] Table 12: Apples/cherries/pears, no ground cover, no frosts: 0.60 / 0.95 / 0.75, h 4
        "kc_ini": 0.60, "kc_mid": 0.95, "kc_end": 0.75, "height_m": 4.0,
        "kc_source": "FAO56 Table 12, Apples no ground cover / no frosts",
        "t_base": 4.0, "t_upper": 35.0,        # [PAR25] Table 3, Apple
        "gdd_stages": None,
        # [FAO56] Table 11: Deciduous Orchard, Low Latitudes, March: 20/70/120/60 = 270 d
        "annual_cycle": {"start_month": 3, "stage_days": (20, 70, 120, 60),
                         "source": "FAO56 Table 11, Deciduous Orchard, Low Latitudes, March"},
        "establishment": {
            "planting_season": "Plant dormant (bare-root) trees in late winter, before bud break",
            "years_to_first_harvest": "dwarf rootstock 2-4 years; semi-dwarf 4-5; standard 7-10 (rootstock-dependent)",
            "source": "Univ. of Maine Extension (dwarf 2-3 yr, semi-dwarf 4-5, standard 7-10); Univ. of Minnesota Extension "
                      "(dwarf 3-4 yr, standard 8+); Illinois Extension (plant/prune while dormant; dwarf may bear at 2-3 yr)",
        },
        "establishment_note": "Water use in the establishment years (smaller canopy) is not modelled; the annual table applies to a mature tree.",
        "suitability_status": "incomplete",
        "suitability_reason": "Apple requires winter chilling to flower and fruit; chilling is not modelled, so this output is an ETc estimate for a mature tree, not a statement that apple is suitable at this location.",
        "plants_per_m2": 0.2, "spacing_source": "TODO verify: dwarf-rootstock row x in-row citation needed",
    },
}

# Backward-compatible view used by crop_coefficients.py
CROP_COEFFICIENTS = {
    name: {"kc_ini": c["kc_ini"], "kc_mid": c["kc_mid"], "kc_end": c["kc_end"], "height_m": c["height_m"]}
    for name, c in CROP_DB.items()
}
# NOTE: these densities are UNSOURCED (see spacing_source above). The advisor and the tracker no longer use them:
# litres per plant are shown only when the user supplies a planting density.
ASSUMED_PLANTS_PER_M2 = {name: c["plants_per_m2"] for name, c in CROP_DB.items()}

SCAN_CROPS = [n for n, c in CROP_DB.items() if c["kind"] == "annual" and c["gdd_stages"]]
PERENNIAL_CROPS = [n for n, c in CROP_DB.items() if c["kind"] == "perennial"]
UNRESOLVED_CROPS = [n for n, c in CROP_DB.items() if c["kind"] == "annual" and not c["gdd_stages"]]


def growing_degree_day(t_max_c, t_min_c, t_base, t_upper):
    """Paredes et al. 2025 Eq. 1 (FAO56rev simplified method)."""
    t_avg = (t_max_c + t_min_c) / 2.0
    if t_avg < t_base:
        return 0.0
    if t_avg > t_upper:
        return t_upper - t_base
    return t_avg - t_base