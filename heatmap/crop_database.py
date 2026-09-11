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
        # [FAO56] Table 12: Kc ini 0.6 (Solanaceae group), mid 1.15, end 0.70-0.90 -> midpoint 0.80
        "kc_ini": 0.60, "kc_mid": 1.15, "kc_end": 0.80, "height_m": 0.6,
        "kc_source": "FAO56 Table 12 (kc_end = midpoint of 0.70-0.90)",
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
        # [FAO56] Table 12: Kc ini 0.6 (group), mid 1.05, end 0.90, h 0.7
        "kc_ini": 0.60, "kc_mid": 1.05, "kc_end": 0.90, "height_m": 0.7,
        "kc_source": "FAO56 Table 12",
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
        # [FAO56] Table 12: Kc ini 0.5 (roots & tubers group), mid 1.15, end 0.75 (0.40 with vine kill), h 0.6
        "kc_ini": 0.50, "kc_mid": 1.15, "kc_end": 0.75, "height_m": 0.6,
        "kc_source": "FAO56 Table 12",
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
        # [FAO56] Table 12: Maize, field (grain): Kc ini 0.3 (cereals group), mid 1.20,
        # end 0.60 (harvest at high grain moisture) / 0.35 (field-dried) -> 0.35 kept, h 2.0
        "kc_ini": 0.30, "kc_mid": 1.20, "kc_end": 0.35, "height_m": 2.0,
        "kc_source": "FAO56 Table 12, Maize field (grain), field-dried harvest",
        # [PAR25] Table 2 (10/32), Table 5 Maize grain short season
        "t_base": 10.0, "t_upper": 32.0,
        "gdd_stages": {"ini": 200, "dev": 380, "mid": 500, "late": 340},
        "gdd_source": "Paredes et al. 2025, Table 5, Maize grain (short season)",
        "fao56_table11_days": {"Dec/Jan, Arid Climate": (25, 40, 45, 30)},
        "plants_per_m2": 5.0, "spacing_source": "TODO verify: 9-12 in x 24-36 in rows gives 3.6-7.2/m2",
    },
    # ------------------------------------------------------------------
    "Strawberry": {
        "t_max_tolerable": 28.0, "t_min_tolerable": 8.0,
        "tolerance_source": "ELN16-S Crops sheet, Strawberries (crTmax 28, crTmin 8) -- verified against mmc1.xlsx Crops sheet",
        "kind": "annual",   # fruits in first season, unlike Grape/Apple
        # [FAO56] Table 12: Strawberries 0.40 / 0.85 / 0.75, h 0.2
        "kc_ini": 0.40, "kc_mid": 0.85, "kc_end": 0.75, "height_m": 0.2,
        "kc_source": "FAO56 Table 12",
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