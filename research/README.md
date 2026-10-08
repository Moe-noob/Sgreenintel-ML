# Research / Methodology Validation Scripts

Standalone scripts that tested a specific methodological question and
produced a documented finding, referenced in the project report. None of
these are called by the production API, frontend, or training pipeline --
they're one-off validation work, kept visible rather than deleted since
they're evidence for specific claims made in the report.

Most scripts import the production modules from `heatmap/` and `care/`
read-only (crop data is changed in memory only and restored). Results that
need NASA POWER use the local cache in `heatmap/cache/`; AquaCrop results are
cached in `research/cache/` (both git-ignored). "DEFENSE" below means
`DEFENSE_PREP.md`.

## compare_climatology_methods.py

Tests whether an alternative smoothing method (harmonic/Fourier regression,
Gaussian-weighted smoothing, LOESS) would improve on the moving-average
climatology used in `heatmap/nasa_power.py`, via leave-one-year-out
cross-validation across all 11 known cities.

**Finding:** none of the three alternatives offer a practically meaningful
improvement (best case ~0.003-0.007 degC MAE difference). The existing
moving-average method is kept as production. Full detail in the commit
history (search for "climatology methodology validation").

Does not modify `nasa_power.py` -- only imports its read-only functions.
Run: `python research/compare_climatology_methods.py`

## sanity_check.py

Quick verification that `training/dataset.py`'s data loading, class list,
and class-weight computation produce the expected shapes and values
(37,526 train / 8,029 val / 8,074 test images, 35 classes). Used during
initial CNN dataset setup and re-run occasionally to confirm the pipeline
still loads correctly after dataset changes.

Run: `python research/sanity_check.py` (requires `data/processed_v2/` to
exist locally -- see the main README's setup section).

---

# Feature 2 validation (added 1 Oct 2026)

## aquacrop_reference_check.py  *(main validation)*

Uses FAO's AquaCrop (`pip install aquacrop`, v3.1.0) as an independent judge of the planting-date
rule: 11 cities x 3 crops (corn, tomato, potato). The same daily climate and ET0 drive both models.
Regret = shortfall in AquaCrop water productivity at our pick against its best date. Modes: a city and
crop for the per-date detail, `--summary` (33 combinations), `--guards`, `--quantity`. Results are cached
in `research/cache/aquacrop_cache.json`; the first full run takes about 10 minutes.

**Finding (after the Kc, elevation and humidity corrections):** the per-day rule is within 5% of AquaCrop's best water productivity in 33/33 combinations within its own candidate pool (median regret 0.1%, worst 4.3%) and in 31/33 against all viable dates (the misses are Abha tomato and Abha corn); start date within 20 days in 33/33.
Total-water ranking (median regret 13.8%, worst 41.8%) and a water-productivity-index ranking (worst
35.1%) are rejected; stage-aware exceedance guards raised the worst case or the number of yield-losing
picks and are rejected. Our water totals sit within +-15% of AquaCrop's ET in 24/33 combinations
(tomato 1.03, potato 1.14, corn 0.98 median ratio). Caveats: AquaCrop uses our ET0, and our tomato
temperature thresholds are AquaCrop's own. DEFENSE Part II, Sections C and F.

## selection_rules_vs_aquacrop.py

Scores three date-selection rules (current least-water, stress-first, stress-aware) against AquaCrop (33
combinations, reusing the cache) and against the five Saudi directorate sowing-calendar cases our crops
cover (Alsadon 2002, Table 5).

**Finding:** current rule 31/33 within 5% of AquaCrop's best water productivity (all viable dates) but 1/5 on the calendars; stress-first rules 21-22/33
but 3/5 and 2/5 (chance 1.2). The two references disagree, which is why the advisor reports two seasons.
`python research/selection_rules_vs_aquacrop.py` (`--saudi-only` skips AquaCrop). DEFENSE Part II, Section D.

## check_site_elevation.py

Checks the site-elevation correction (`heatmap/site_elevation.py`) against WMO 1991-2020 normals at five
stations (Abha, Khamis Mushait, Sharorah, Wejh, Arar), with pass criteria fixed before running.

**Finding:** DEM elevation matches the official station heights within 5 m; Abha's combined temperature
error falls from 6.3 C to 0.8 C, Khamis Mushait 1.8 -> 0.5, no station worse by more than 0.5 C. Coastal
Wejh keeps a sea-land bias (Tmax -2.1 C, Tmin +4.7 C) that elevation cannot fix. DEFENSE Part II, Section B.

## check_aridity_correction.py

Regression check for the FAO-56 Rev.1 humidity conditioning (`heatmap/aridity.py`): prints each city's
aridity index, aT, and annual ET0 before and after, and compares with the values verified at the time (PASS/CHECK).
`python research/check_aridity_correction.py`. DEFENSE Part II, Section A.

## export_climate_for_sharing.py

Exports the 365-day climate normals (with humidity columns and ET0) and, optionally, the unsmoothed daily
record as CSV plus a README, for tools that cannot reach NASA POWER. `--no-daily` works offline from the cache.

## two_season_preview.py

Compared the best spring-window and autumn-window start dates for every city and crop. **Finding:** all 44 current
picks were in autumn; the best spring start cost a median +4-19% seasonal water and +19-29% per day. Led to the
two-season output (`heatmap/season_picks.py`).

---

# Earlier methodology tests (referenced in DEFENSE Part I)

| Script | What it tests |
|---|---|
| `compare_climate_windows.py` | Whether the recommendation changes with the NASA year range (2020-2025, 2016-2025, 1996-2025). Section 3. |
| `compare_reference_dates.py` | The same engine at customary planting dates versus the advisor's pick (water, season length, shock days). Section 8. |
| `objective_sensitivity.py` | Least water per day versus total seasonal water versus a hybrid. Section 10. |
| `corn_gdd_sensitivity.py` | The 1,420 versus 1,540 corn heat-unit question (Paredes Table 5; Rev.1 prints 1,420). Section 9. |
| `trace_gdd.py` | Day-by-day heat-unit accumulation for a city, crop and start date; matches the production simulation. Section 10. |
| `audit_shock_days_all_cities.py` | Shock-day audit across all cities and crops. Section 7 (re-run after the elevation correction before quoting). |
| `diagnose_riyadh_corn.py`, `diagnose_tabuk_corn.py`, `..._corn2.py`, `..._corn3.py` | The Tabuk/Riyadh corn shock-day story. Section 5. |

# Crop-extension helpers

| Script | Purpose |
|---|---|
| `list_elnesr_crops.py` | Lists the crops in the Elnesr & Alazba workbook with their sourced tolerance thresholds. |
| `print_elnesr_crop_rows.py` | Prints Kc, height, durations and tolerances for candidate crops next to what `crop_database.py` holds. |
| `dry_run_new_crops.py` | Runs candidate crops through the real scanner in memory only, without touching `crop_database.py`. |

# Older diagnostics (not documented elsewhere)

`diagnose_etc.py`, `diagnose_etc2.py` (one-off ETc diagnostics; no docstring), `inspect_tomato.py` (copies a random sample of
non-PlantVillage-named tomato images for visual inspection), `check_plantwild.py` (inspects the PlantWild split file).

# patches/

The scripted edits applied during the 1 Oct 2026 overhaul, kept as an audit trail. Each script's docstring says what it changed and why;
each requires its anchor text to match exactly once, saves a backup, is safe to re-run, and has a `--dry-run` mode.

| Script | Change |
|---|---|
| `apply_text_edits.py` | Tracker limitation wording, chart note wording, and the "only N dates are exceedance-free" sentence |
| `apply_step12_patch.py` | FAO-56 Rev.1 Kc; optional litres per plant; label fixes; humidity conditioning (baseline and live) |
| `apply_step12b_patch.py` | AquaCrop percentages in the chart note; styling of the density box |
| `apply_step3_patch.py` | Autumn and spring picks per crop (Plan card block, chart outlines) |
| `apply_step4_patch.py` | Onion, carrot, garlic, lettuce, sweet corn; zero-day-stage fix; "Not checked against AquaCrop" badge |
| `apply_step5_patch.py` | Cucumber, eggplant, squash, pumpkin, green bean as lower-confidence crops; fewest-exceedance-days headline |



## test_et0_fao_examples.py

Reproduces the worked examples in FAO-56 Chapter 4 (Example 17 Bangkok, monthly; Example 18 Uccle, daily; Example 20 near Lyon, missing data) from the printed inputs.

**Finding:** the ET0 code gives 5.716, 3.880 and 4.562 mm/day against FAO's 5.72, 3.88 and 4.56, and the intermediate values (Ra, delta, gamma, es, ea, Rn) match too.

Run: `python research/test_et0_fao_examples.py` (exits non-zero if any check fails)

## compare_station_nasa.py

Compares daily Tmax/Tmin, dewpoint and 2 m wind from hourly station records (Abha, Najran, Jazan; 2016-2018) with NASA POWER, using the app's own elevation correction. Station CSV is not in the repo (`data/external/`, git-ignored; records end May 2019).

**Finding:** at Abha the correction cuts the Tmax/Tmin bias from +5.3 to -0.5 degC (mean abs error 5.3 to about 1.2-1.3) and removes about 117 spurious days/yr above 35 degC. At Najran and Jazan cell and station heights are close, so it barely matters (mean abs error about 1-1.7 degC). The app's map elevation is within 6 m of each station. NASA wind at Najran is about 63% above the station's, and the humidity fix raises dewpoint there by about 12 degC on average.

Run: `python research/compare_station_nasa.py`

## compare_shock_days_station.py

For each crop and planting date, compares the app's heat/cold exceedance counts with counts from station records for the same dates (2016-2018).

**Finding:** counts agree within a few days where a crop is clearly over or under its limit, but are unreliable near a limit. Headline (typical-year) mean abs error is 1.6-6.2 days for heat and 0-6.2 for cold depending on the city. Where the app reports 0 heat days, the station recorded at least one in 4% (Abha), 42% (Najran) and 35% (Jazan) of windows. The raw-year counts are closer in 4 of 5 comparisons. No production change; the picks are unaffected.

Run: `python research/compare_shock_days_station.py`