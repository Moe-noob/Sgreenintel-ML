# Feature 2 v2 — full documentation and audit trail

This document records **everything v2 does differently from v1**, **every issue found** (in v1, in the source data, and in v2's own earlier versions), **every source used and where it came from**, and **every validation run: against what, how, and with what result**. It is written so each claim can be checked against v1 and against the source documents.

- Code: `feature2_v2/` (self-contained; delete the folder to remove v2 — nothing else imports it).
- v1: `heatmap/` (`advisor.py`, `season_simulator.py`, `crop_database.py`, `nasa_power.py`, `evapotranspiration.py`, `crop_coefficients.py`) — **unchanged by this work**.
- Branch: `claude/compassionate-hopper-lh08ol`. Commits: `0fe823c` (v2 created), `c14eee4` (Saudi benchmark), `df0e179` (FAO-56 Rev.1 adopted), `b1ac47b` (this document), and the season-length fix (§7, D11).

Contents

1. [Summary](#1-summary)
2. [Sources: what was used, from where, and how it was checked](#2-sources)
3. [v1 vs v2, feature by feature](#3-v1-vs-v2-feature-by-feature)
4. [Findings about v1](#4-findings-about-v1)
5. [Findings about the source data and papers](#5-findings-about-the-source-data-and-papers)
6. [Validation: against what, how, results](#6-validation)
7. [Development log: v2's own mistakes and how they were corrected](#7-development-log)
8. [How to check v2 against v1 yourself](#8-how-to-check-v2-against-v1-yourself)
9. [Limitations and what still needs checking by hand](#9-limitations-and-open-items)
10. [File map](#10-file-map)

---

## 1. Summary

v2 answers the same question as v1 — *for a Saudi location, when should each crop be sown, how long is its season, and how much water does it need per growth stage?* — with these main changes:

| Area | v1 | v2 |
|---|---|---|
| Climate source | NASA POWER daily reanalysis, 2016–2025, needs internet | FAOCLIM-2 ground-station long-term means (FAO 2001) as fitted in the Elnesr & Alazba (2016) workbook; offline; 24 stations inside KSA |
| Paper method | "adapted from" Elnesr & Alazba (2016) | exact re-implementation, verified against the workbook's own computed cells (zero difference) |
| Crop parameters | FAO-56 (1998) Kc; FAO56rev GDD (Paredes et al. 2025) | FAO-56 **Rev.1 (Dec 2025)** Kc, root depth, depletion fraction, salt tolerance, GDD |
| Crops | 5 annual + 2 perennial | 22 annual crops (24 crop seasons) |
| Outputs | ETc per stage; per-plant litres from unverified spacing | ETc per stage and month, gross irrigation (system efficiency + salinity leaching), yield under saline water, irrigation interval, per-plant only from user-given spacing |
| External validation | none recorded | Saudi directorate sowing calendars (Alsadon 2002), FAO-56 Rev.1 GDD tables, paper's own efficiency tables, FAO worked examples |

**What v1 does better** (kept honestly in view): v1 adjusts Kc with each location's actual humidity and wind (FAO-56 Eq. 62) and reports year-to-year variability from ten observed years. v2's station data have neither, so it can only give a dry-air upper bound and long-term means. v1 also covers grape and apple; v2 does not.

---

## 2. Sources

### 2.1 Documents

| # | Source | Where the file is | Obtained from | Used for |
|---|---|---|---|---|
| S1 | Elnesr, M.N. & Alazba, A.A. (2016). A spreadsheet model to select vegetables planting dates for maximum yield and water use efficiency. *Computers and Electronics in Agriculture* 124:55–64 | `data/sources/02-a_spreadsheet_model_…pdf` | already in repo (v1) | model equations (Eqs. 1–28), selection rules, validation method |
| S2 | Elnesr & Alazba (2016), Appendix A workbook | `data/sources/1-s2.0-S0168169916300989-mmc1.xlsx` | already in repo (v1) | station climate fits (sheet `Stations`), 122 crop rows (sheet `Crops`), cached model results (sheet `Model`) |
| S3 | FAO (2001) FAOCLIM-2 world agroclimatic database | inside S2 (as sinusoid fits) | via S2 | Tmax, Tmin, Tmean, ET0 per station |
| S4 | Alsadon, A.A. (2002). Best planting dates for vegetable crops in Saudi Arabia: compatibility between heat-unit dates and dates suggested by the regional offices of the Ministry of Agriculture and Water. *J. King Saud Univ. (Agric. Sci.)* 14:75–97 (Arabic) | `data/sources/alsadon_2002_planting_dates_KSA.doc` | uploaded by you in this session | Saudi ground truth: Table 5 directorate sowing dates |
| S5 | Pereira, Allen, Paredes, López-Urrea, Raes, Smith, Kilic & Salman (2025). *Crop evapotranspiration*, FAO Irrigation & Drainage Paper 56 **Rev.1**, doi:10.4060/cd6621en | `cd6621en.pdf` (repo root) | added to the repo by you | Kc (Tables 6.1/6.2), GDD (6.10–6.12), soils (7.5), depletion p (8.1/8.2, Eq. 8.5), salt tolerance (8.8/8.9), dry-station ET0 caveat (Sec. 2.5) |
| S6 | Allen, Pereira, Raes & Smith (1998). FAO-56 | not in repo | cited through S2 and S5 | Eqs. 58, 62, 65, 66 (unchanged in S5); worked Examples 27–28 used as tests |
| S7 | Ayers & Westcot (1985). FAO-29 rev.1 | not in repo | formula restated in S5 Sec. 8 | leaching requirement LR = ECw / (5 ECe − ECw) |
| S8 | Brouwer et al. (1989). FAO Irrigation Water Management Training Manual 4 | not in repo | **hand-typed** | field application efficiency: drip 90 %, sprinkler 75 %, surface 60 % |
| S9 | Saudi national border | `data/geo/national_border/SAU-geo.json` | already in repo | removing mislabelled foreign stations |

Web access to fao.org, ars.usda.gov and similar sites was blocked while v2 was built, so nothing was downloaded; everything above came from files in the repo or files you supplied.

### 2.2 How each number got into the code

| Data | File in v2 | How it was produced | How it was checked |
|---|---|---|---|
| Station climate (24 stations) | `data/stations_ksa.json` | extracted from S2 by `build_data.py` (openpyxl) | point-in-polygon against S9; physical-range test (`tests/`) |
| Crop rows (122) | `data/crops_eln16.json` | extracted from S2 by `build_data.py` | row count, `ThermN = (Topt − Tbase) × DUR_total` for every KSA row (`tests/`) |
| Spreadsheet fixture | `data/spreadsheet_fixture.json` | Excel's cached cell values from S2 `Model` sheet, 365 rows × 21 columns + summary | the engine must reproduce it exactly (`tests/`) |
| Kc, heights, root depth, p, salt tolerance, GDD | `agronomy.py` | transcribed from S5 tables | compared line by line with text extracted from the S5 PDF; book page cited per table; spot-check tests |
| Irrigation efficiencies | `agronomy.py` | hand-typed from S8 | **not machine-checked** (see §9) |
| Directorate sowing dates | `validation/alsadon2002.py` | transcribed from S4 Table 5, original Arabic kept beside each entry | can be re-read against S4 directly |

Book page numbers in S5 = PDF page − 32.

---

## 3. v1 vs v2 feature by feature

| Topic | v1 (file) | v2 (file) | Why the change |
|---|---|---|---|
| Climate | NASA POWER daily 2016–2025, ±7-day smoothed (`nasa_power.py`) | FAOCLIM-2 station sinusoids `X(j) = a + ρ sin(ωj + φ)` (S1 Eq. 4) (`climate.py`) | offline; ground stations; the exact data the paper's model was built and validated on |
| ET0 | FAO-PM computed by v1 from reanalysis Tmax/Tmin/Tdew/wind/radiation (`evapotranspiration.py`) | FAO's own station FAO-PM ET0 (from S3) | no reanalysis radiation/wind; but see the dry-station caveat (§9) |
| Location | 11 cities + geocoded lat/lon | 11 cities + any lat/lon → nearest station, warns if > 100 km or > 300 m elevation difference (`climate.py`) | station network |
| Crops | Tomato, bell pepper, potato, maize, strawberry (unresolved), grape, apple (`crop_database.py`) | 22 crops: tomato ×2 seasons, pepper, potato, cucumber ×2, eggplant, onion, lettuce, carrot, spinach, squash, watermelon, melon, cabbage, cauliflower, broccoli, green bean, radish, lentil, okra, sweet corn, garlic, molokhia (`crops.py`) | workbook has arid-region rows for these |
| Paper method | adapted (mean daily ETc, whole-season shock count) (`season_simulator.py`) | exact spreadsheet logic incl. integral forms and indices (`elnesr_model.py`), reported alongside v2's own choice | reproducibility; lets the paper be benchmarked on its own terms |
| Season length | GDD per stage, Paredes 2025 Table 5, cap at Tupper (`crop_database.py`) | FAO-56 Rev.1 Tables 6.10–6.12 GDD per stage (18 crops), development capped at min(Tupper, crop Topt); paper Eq. 7 heat units for watermelon, radish, okra, molokhia (`season.py`) | same GDD data as v1, for more crops; the Topt cap stops unrealistic acceleration in Saudi heat (§7, D11). **Note: v1 caps at Tupper, so v1 may also give short seasons for hot sowings** |
| Kc | FAO-56 1998 Table 12 | FAO-56 Rev.1 Tables 6.1/6.2 (`agronomy.py` `KC_REV1`) | newer standard; several values changed (see §4) |
| Kc climate adjustment | Eq. 62/65 with actual RHmin and wind | central = table Kc; upper bound = Eq. 62/65 at RHmin 20 %, u2 2 m/s | v2 has no humidity/wind data (v1 is better here) |
| Temperature stress | days above/below tolerance, smoothed + observed-year stats | degree-days above crTmax / below crTmin over the whole season, per stage | a 44 °C day and a 36 °C day are not equally harmful |
| Sowing-date choice | shock-free first, then lowest mean daily ETc | best = paper optimisation index when the crop can finish in time and the date is not more stressed than the lowest-risk date; otherwise the lowest-risk date (least stress, then least water) (`advisor.py`) | chosen after the Saudi benchmark (§6.5) and review (§7, D11) |
| Irrigation | ETc only ("not irrigation requirement") | gross = ETc / (Ea × (1 − LR)); LR from FAO-29 with Rev.1 salt tolerance; yield range under saline water; RAW-based irrigation interval; monthly m³/ha (`irrigation.py`) | what a farmer has to pump |
| Per-plant water | ETc ÷ assumed plants/m² (spacing marked "TODO verify") | only when the user gives row × plant spacing | no unsourced numbers in the output |
| Outputs | console, API | console, JSON, interactive HTML report, CSV for 11 cities, optional FastAPI router | |

---

## 4. Findings about v1

Each item was verified in the v1 code; file and line are given so you can check.

### 4.1 Things that are wrong or out of date

| # | Finding | Where | Impact | What v2 does |
|---|---|---|---|---|
| V1-1 | Output text says the climate is **2014–2023**, but the data fetched are **2016–2025** | `heatmap/advisor.py:9, 96, 122`; `season_simulator.py:194`; `nasa_power.py:7, 14` (docstrings) vs `nasa_power.py:45–46` (`DAILY_START = "20160101"`, `DAILY_END = "20251231"`) | labelling only; numbers are from 2016–2025 | n/a (fix is a text edit in v1) |
| V1-2 | Kc values are FAO-56 **1998**; FAO-56 Rev.1 (2025) revised several | `heatmap/crop_database.py` | seasonal ETc differs, especially late season | uses Rev.1 values |
| | Tomato fresh market: v1 0.60 / 1.15 / 0.80 → Rev.1 0.60 / 1.10 / 1.00 | Rev.1 Table 6.1, p. 166 | | |
| | Bell pepper: 0.60 / 1.05 / 0.90 → 0.60 / 1.10 / 1.00 | Table 6.1, p. 166 | | |
| | Potato: 0.50 / 1.15 / 0.75 → 0.50 / 1.10 / 0.40 (long season) or 0.60 (short) | Table 6.1, p. 165 | | |
| | Maize grain: 0.30 / 1.20 / 0.35 → 0.30 / 1.20 / 0.30 (low grain moisture) | Table 6.2, p. 169 | | |
| | Strawberry: 0.40 / 0.85 / 0.75 → 0.50 / 0.80 / 0.75 | Table 6.1, p. 166 | | |
| | Table grape 0.30 / 0.85 / 0.45 and apple 0.60 / 0.95 / 0.75 → Rev.1 Table 6.3 now gives Kc **by ground-cover class** (e.g. medium-cover table grape 0.35 / 0.95 / 0.70; medium apple 0.45 / 0.85 / 0.45) | Table 6.3 | v1's perennial water use should be re-derived by canopy class | not covered by v2 |
| V1-3 | **Per-plant litres are printed from unsourced spacing.** Every `plants_per_m2` is marked `"TODO verify"`, yet `per_plant_liters()` uses them in the output table | `crop_database.py:64, 79, 94, 111, 127, 151, 175`; `advisor.py:50, 77–81` | L/plant/day figures have no source | per-plant only from user-supplied spacing |
| V1-4 | **Validation claim without a record.** The API docstring says the 11 cities' results "have been manually cross-checked against known KSA agricultural practice"; no data, script or test for this exists in the repo | `api/main.py:8–9, 191` | claim cannot be reproduced | reproducible benchmark against Alsadon (2002) Table 5 (§6.5) |
| V1-5 | ET0 from **gridded reanalysis over dry land** tends to be overstated | FAO-56 Rev.1 Sec. 2.5 (p. 36–38) and 2.5.6 (p. 45–46: gridded ERA5 regressions "generally higher than 1.0"); worked example ≈ 17 % higher from arid data (p. 49) | v1 water figures lean high | **also applies to v2** (dry stations); stated as a limitation, not corrected (§9) |

### 4.2 Deviations that v1 documents itself (not errors)

- Selection minimises **mean daily** ETc, not the paper's seasonal total (`season_simulator.py:222–236` explains why).
- The shock test counts days over the whole season on the smoothed climatology; the paper's spreadsheet checks only the **sowing day** (confirmed in S2, cells `Model!U27`/`V27`, see §5).

### 4.3 Things v1 gets right (confirmed independently)

- **Temperature tolerances** (crTmax/crTmin) for tomato 35/14, pepper 35/15, potato 27/7, sweet-corn proxy 40/10, strawberry 28/8 match the workbook rows exactly (checked programmatically against S2).
- **GDD stage values and thresholds** for tomato (market 325/660/880/200, Tbase 7, Tupper 28), bell pepper (445/1180/745/45, 10/35), potato long season (405/530/490/835, 2/30) and maize grain short season (200/380/500/340, 10/32) are **identical to FAO-56 Rev.1 Tables 6.10–6.11**. v2's first version departed from this and was wrong (§7, item D7); v2 now uses the same data, with one addition: development is capped at the crop's optimum temperature rather than Tupper (§7, D11), because capping at Tupper gives unrealistically short seasons for hot sowings. v1 caps at Tupper, so check v1's hot-season sowings for the same problem.
- FAO-56 Eq. 62 Kc adjustment with actual RHmin/u2 and validity clamping, and FAO-56 Examples 27–28 self-tests.
- Year-to-year exceedance statistics from the unsmoothed record.

### 4.4 Minor maintainability notes

- The 11-city coordinate table is duplicated in `heatmap/advisor.py` and `heatmap/prewarm_cache.py`.
- Strawberry is listed but excluded from the scan (no sourced GDD). FAO-56 Rev.1 Table 6.10 now gives strawberry Tbase 3 / Tupper 30 but still no stage GDD in Tables 6.11/6.12, so it remains unresolved.

---

## 5. Findings about the source data and papers

Found while reproducing the workbook (S2) and reading the papers (S1, S4, S5):

| # | Finding | Evidence | Consequence |
|---|---|---|---|
| D-1 | 9 of the 33 stations labelled "Saudi Arabia" are in Kuwait, Bahrain or Jordan (Kuwait City, Kuwait Int. Airport, Shuwaikh, 3× King Fahad Causeway/Bahrain, Azraq, H4 Ruwaished, Wadi Rum) | point-in-polygon against S9; all ≥ 0.2° outside | removed; 24 stations kept |
| D-2 | The generalised border file cuts off coastal Al Wajh | Al Wajh 0.003–0.03° outside the polygon | stations within 0.1° of the border are kept |
| D-3 | The `Crops` sheet ends with a column-index row ("1, 3, 4, 5 …") that parses as crop #1 and overwrites Broccoli | S2 last row | skipped; 122 crop rows (the paper says 123) |
| D-4 | The model's season length is the `DurTherm` column, not `DUR_total` | `Model!G16`, `F13` | reproduced as-is |
| D-5 | The heat-unit test is `HU_min < HU ≤ HU_max` (strict lower bound) | `Model!T27` | reproduced |
| D-6 | The temperature test checks only the **sowing day's** Tmax/Tmin | `Model!U27`, `V27` | reproduced; v2's own rule checks the whole season |
| D-7 | `Model!L27` contains `(1+#REF!)*…`; Excel falls back to Ta = (Tx+Tn)/2 | formula text in S2 | reproduced |
| D-8 | Paper Eq. 12 prints `(a_E − Tb)`; the sheet correctly uses `a_E` | S1 p. 56 vs `Model!R27` | sheet form used |
| D-9 | Paper Eq. 14 divides by "0.25 D_total"; the sheet computes AVERAGE(4 products)/AVERAGE(4 durations), i.e. a duration-weighted mean Kc | `Model!C16` | sheet form used |
| D-10 | Paper Eq. 28 calls overall efficiency a **product** of the partial efficiencies; every value in its Tables 1–2 is their **mean** (e.g. Asparagus (100 + 74 + 100)/3 = 91) | S1 Table 1 | mean used; both returned |
| D-11 | Excel's 1900 leap-year bug makes DOY 90 display as "Mar-30" | S2 dates | comparisons use day numbers |
| D-12 | FAO-56 Rev.1 revised several Kc and p values relative to the 1998 edition that S2 and v1 use | S5 Tables 6.1, 8.1 | Rev.1 used for water; paper engine keeps 1998 values so reproduction stays exact |
| D-13 | FAO-56 Rev.1 warns ET0 from dry, non-reference stations and from gridded data is overstated (≈ 17 % in its example) | S5 Sec. 2.5, p. 36–49 | stated limitation for both v1 and v2 |

---

## 6. Validation

All of it is automated. `python -m unittest discover feature2_v2/tests -v` runs 29 tests (all pass). Validation scripts are in `feature2_v2/validation/`.

### 6.1 Exact reproduction of the published KSU spreadsheet

- **Against:** Excel's own computed values stored in S2 (`Model` sheet), 365 sowing days × 21 columns: Tx, Tn, Ta, ET0, GDD, seasonal ET and HU (summation and integral), harvest day, 4 flags, 6 indices; plus Kc_eq, HU_min, HU_max, both date windows, suitable-day counts, best-day index (`AF18`) and yellow-band best index (`AL18`).
- **Result:** maximum difference **0** at 9 decimal places for every cell; windows DOY 90–123 & 199–232 (HU) and 102–123 & 199–232 (HU + temperature), counts 68 and 56, best day 199, indices 71.45 — all identical.
- **Test:** `A_SpreadsheetReproduction`.

### 6.2 The paper's own model-efficiency tables

- **Against:** S1 Table 1 (Central Maryland), 9 rows including the extreme cases.
- **Result:** `overlap_efficiency()` reproduces the published overall efficiencies within 1 % (using the mean, see D-10).
- **Test:** `A_OverlapEfficiency`.

### 6.3 FAO worked examples and FAO-56 Rev.1 values

- FAO-56 Example 28 (Kc curve, Eq. 66): 0.15 / 0.77 / 1.19 / 0.56 at days 20 / 40 / 70 / 95 ✓.
- FAO-56 Example 27 (Eq. 62): 1.30 and 1.07 ✓.
- FAO-29 Eq. 7 leaching; Maas–Hoffman yield at both ends of the Rev.1 range; Rev.1 Eq. 8.5 p-adjustment limits ✓.
- Spot checks of the transcribed Rev.1 Tables 6.1, 8.1, 8.8, and that the water budget uses Rev.1 Kc while the paper engine keeps 1998 Kc ✓.
- **Tests:** `B_FAOExamples`, `B_Fao56Rev1`.

### 6.4 Data integrity

- 24 stations, none foreign, all within KSA's lat/lon box.
- 122 crop rows, Broccoli intact.
- ThermN and stage-sum consistency for every KSA row.
- Every station: hottest Tmax 25–48 °C, coldest Tmin −2–25 °C, annual ET0 1200–3200 mm, Tmax > Tmin every day.
- **Test:** `C_DataIntegrity`.

### 6.5 Saudi ground truth: directorate sowing calendars (Alsadon 2002)

- **Against:** S4 Table 5 — sowing dates recommended by the regional Directorates of Agriculture & Water for 16 crop × region cases (Tabuk, Al-Ahsa, Qassim, Jazan). The same table gives Alsadon's heat-unit program dates, used as a published baseline.
- **How:** `validation/alsadon2002.py` turns each date range into day-of-year sets and scores each method:
  - precision = share of the method's window the directorate agrees with (Alsadon's own "% agreement" definition);
  - recall = share of the directorate window the method covers;
  - Ω = the paper's overlap efficiency (Eqs. 19–28);
  - best-date hit = the single recommended date falls inside the directorate window.

**Summary (current version):**

| Method | Precision | Recall | Ω |
|---|---|---|---|
| Alsadon (2002) heat-unit program | 60 % | 40 % | 54 % |
| Elnesr & Alazba spreadsheet, heat-unit window | 68 % | 36 % | 51 % |
| Elnesr & Alazba spreadsheet, heat units + temperature | 53 % | 7 % | 36 % |
| v2 "finishes in time" window | 41 % | 89 % | 77 % |
| v2 low-stress window | 58 % | 24 % | 48 % |

Best date inside the directorate window: **v2 11/16**; paper's index alone 11/16.

**How to read this honestly:**
- v2's broad window wins on Ω mainly through **recall**. For cool-season crops it covers most of the year (precision 17–25 %), and Ω rewards coverage. Precision is the fairer measure of how selective a method is, and there the paper's heat-unit window (68 %) and Alsadon's program (60 %) are better.
- v2's **best single date** now equals the paper's own index (11 of 16 each), after the season-length fix in §7 (D11). Before that fix it was 9 of 16.
- The best-date rule was chosen after seeing this benchmark (history in §7). No numeric parameter was fitted, but the result is not an independent test.
- 16 cases are few: differences of one or two cases are noise.
- Al-Ahsa has no FAOCLIM station; Qatif (~125 km) is used.

**Per case (v2 current):**

| Region | Crop | Directorate dates (S4, Arabic) | Alsadon program P/R | Paper HU window P/R | v2 window P/R | v2 best date |
|---|---|---|---|---|---|---|
| Tabuk | Potato | فبراير، أغسطس- سبتمبر | 77%/65% | 75%/81% | 24%/100% | Oct 28 ✗ |
| Tabuk | Squash | مارس، إبريل، يوليو، أغسطس | 55%/62% | 100%/42% | 48%/100% | Apr 29 ✓ |
| Tabuk | Tomato | أبريل- مايو، يوليو- أغسطس | 59%/37% | 78%/47% | 41%/98% | Jun 28 ✗ |
| Tabuk | Watermelon | مارس- إبريل، يوليو | 0%/0% | –/0% | 27%/24% | Jun 20 ✗ |
| Al-Ahsa | Eggplant | 15 فبراير- 15 مارس، 15 يوليو- 30 أغسطس | 50%/39% | 55%/24% | 21%/100% | Feb 19 ✓ |
| Al-Ahsa | Onion | سبتمبر- أكتوبر | 48%/49% | 50%/51% | 17%/100% | Oct 06 ✓ |
| Al-Ahsa | Tomato | أغسطس- 15 أكتوبر | 52%/39% | 50%/38% | 21%/100% | Oct 08 ✓ |
| Al-Ahsa | Watermelon | فبراير- أغسطس | 100%/15% | 100%/25% | 100%/68% | Jul 08 ✓ |
| Qassim | Pumpkin | مارس- أغسطس | 76%/24% | 87%/18% | 75%/100% | Mar 25 ✓ |
| Qassim | Green bean | مارس- سبتمبر | 100%/21% | 100%/29% | 83%/100% | Mar 25 ✓ |
| Qassim | Lettuce | سبتمبر- أكتوبر | 33%/25% | 51%/74% | 17%/100% | Nov 14 ✗ |
| Qassim | Tomato | يناير- مارس | 66%/32% | 49%/31% | 25%/100% | Mar 02 ✓ |
| Jazan | Cucumber | سبتمبر- نوفمبر، يناير | 78%/88% | 61%/40% | 33%/100% | Dec 31 ✗ |
| Jazan | Okra | سبتمبر- 15 يوليو | 66%/29% | 76%/46% | 87%/100% | Dec 26 ✓ |
| Jazan | Bell pepper | أكتوبر- ديسمبر | 72%/85% | –/0% | 25%/100% | Nov 14 ✓ |
| Jazan | Watermelon | يوليو، نوفمبر- ديسمبر | 20%/34% | 21%/25% | 11%/34% | Jul 09 ✓ |

Full numbers: `validation/alsadon2002_results.json`. Tests: `F_Alsadon2002Benchmark`.

### 6.6 Season length against FAO-56 Rev.1 field-observed growing-degree-days

- **Against:** S5 Tables 6.10 (Tbase/Tupper), 6.11 (field-observed stage GDD), 6.12 (ranges derived from the 1998 durations).
- **How:** `validation/fao56rev1_gdd.py --old` computes, for every city × crop at v2's best sowing date, the season length Rev.1's method gives (short–long range) and compares it with v2's length.
- **Result for v2's original method** (paper Eq. 7 heat units capped at Topt): only 8 of 210 cases inside the Rev.1 range and **188 longer** (e.g. cucumber at Makkah 136 vs 54–90 days; spinach 100 vs ~30). This led to the switch in §7, item D7.
- After the switch, the same script reported 220/220 inside, true **by construction**. After the Topt cap added in §7 (D11), it reports 94/220 inside the Rev.1 range and 174/220 (79 %) inside or within 15 % of it; the 46 others are longer than Rev.1, because the cap deliberately stops development from speeding up above the crop's optimum temperature.
- Independent sanity check of the final lengths: across all 11 cities, the median best-date season is 0.96 × the literature season length in the workbook (`DurTherm`; Maynard & Hochmuth and others cited by S1). Before D11 it was 0.74 ×.

### 6.7 Behaviour and agreement with established Saudi practice

- Rev.1 stage lengths are followed exactly (tomato at a constant 17 °C: 33/66/88/20 days); above the optimum the rate stays at its maximum (tomato: 122 days at both 24 °C and 40 °C); the Eq. 7 fallback reproduces FAO-56 durations at the optimum; cooler means longer; nothing finishes below the base temperature.
- No unrealistically short seasons for spinach, broccoli, garlic, squash or green beans in Riyadh, Jazan, Hail or Tabuk (`test_no_unrealistically_short_seasons`).
- Practice checks:
  - Tihama (Jazan) tomato is best sown Sep–Jan.
  - Asir (Abha) tomato is sown Mar–Jun.
  - Potato, lettuce, carrot, onion and garlic in Riyadh, Qassim and Madinah are never best-sown in May–July.
  - Riyadh potato is "recommended".
- **Tests:** `D_ModelBehaviour`, `E_KsaPractice`.

---

## 7. Development log

v2's own mistakes and wrong turns are listed here so the final design can be judged with its history.

| # | What happened | How it was found | Fix |
|---|---|---|---|
| D1 | NASA POWER (v1's source) was unreachable from the build environment | network error | switched to the workbook's FAOCLIM-2 station data (offline) |
| D2 | Coarse border polygon dropped Al Wajh | manual review of dropped stations | 0.1° coastal tolerance (D-2) |
| D3 | Junk column-index row overwrote crop #1 (Broccoli) | a 15-day "broccoli" season | row skipped (D-3) |
| D4 | First season-length calibration (per-stage thermal time at Riyadh in the FAO planting month) gave 8–15-day seasons for warm-season crops whose Tbase (16 °C) is above Riyadh's winter temperature | output review | replaced by paper Eq. 7 (`ThermN`) |
| D5 | Using the paper's heat-unit test as a hard gate rejected all tomato dates in Abha | output review vs known Asir practice | replaced by "finishes within DUR_total × (1 + Htol)" |
| D6 | Counting stress in days made Riyadh tomato choose a March sowing running into July heat | output review | stress measured in degree-days |
| D7 | Eq. 7 with a Topt cap made seasons too long in hot places (188/210 cases longer than FAO-56 Rev.1), inflating seasonal water | §6.6 | FAO-56 Rev.1 GDD for 18 crops; Eq. 7 kept only for 4 crops Rev.1 does not list. Effect: e.g. Riyadh tomato gross water 9,958 → 6,135 m³/ha; Makkah cucumber 136 → 71 days |
| D8 | Best-date rule: first "least stress, then least water" (9/16 on §6.5). Changed to the paper's index with a lowest-risk alternative (10/16). A variant scoring 12/16 was rejected because it sowed garlic in Qassim in late July. After D7, one case changed (Qassim tomato) → 9/16 | §6.5 | documented; not re-tuned further to avoid overfitting 16 cases |
| D9 | Hand-typed FAO constants (from memory, because fao.org was blocked) had errors: zucchini salt slope 9.4 (Rev.1: 10.0–10.5); several p values were 1998 values; and the salt entry was keyed "Zucchini" while the crop is "Squash", so squash never got a salt value | comparison with S5 once you added it | all replaced with S5 values, checked against the PDF text |
| D10 | A small bug in the leaching function after the salt table gained range columns | test failure | fixed before commit |
| D11 | **Seasons too short after D7.** Your review flagged spinach at 37 days and radish at 40. Checking all 261 best-date seasons found 61 of 60 days or less. Radish (40 d) is correct, since it equals FAO's own radish durations (35 and 40 d). But hot sowings gave unrealistic results: spinach 29–30 d on the coast, broccoli 42 d, garlic 56 d sown in June, squash 44–55 d and green beans 45–50 d. There were two causes: (a) Rev.1's Tupper (e.g. 30 °C for broccoli and garlic) lets development keep accelerating in Saudi heat, beyond the climates its GDD totals were observed in; (b) the paper's index weights heat units 0.75, so it picked cool-season crops' hottest acceptable dates | your review; `DurTherm` and FAO-1998 comparison | (a) development capped at min(Tupper, crop Topt), consistent with the paper's Eq. 7 heat-unit definition; (b) the paper's date is used only if its season stress is negligible or no worse than the lowest-risk date's. Result: median season / literature length 0.74 → 0.96; seasons under 60 % of FAO's duration 110 → 39; median best-date stress 64 → 5 °C·days; benchmark best date 9 → 11/16; low-stress window Ω 46 → 48 %. Examples: spinach Riyadh 49 d (sown Nov 29), broccoli Hail 72 d (Mar 7), Jazan tomato 122 d (Oct 16). New test: minimum realistic season lengths |

---

## 8. How to check v2 against v1 yourself

`validation/compare_with_v1.py` runs both versions side by side. It needs NASA POWER for v1, so run it on a machine with internet (or after `python heatmap/prewarm_cache.py`):

```bash
python feature2_v2/validation/compare_with_v1.py
# writes feature2_v2/validation/compare_with_v1_results.md
```

It produces three sections.

1. **ET0, annual and monthly, 11 cities:** v1 (NASA POWER, FAO-PM computed by v1) vs v2 (FAOCLIM-2 station ET0). Expect differences from the data source; both lean high for the reason in §9.
2. **Same crop, same city, same sowing date:** season length (stages) and seasonal ETc for tomato, bell pepper and potato.
   - Tomato and pepper stage lengths should agree closely, since both versions use the same GDD tables; differences come from the climate data only.
   - Potato will differ: v1 uses the long-season row, while v2 uses the mean of short and long.
   - ETc differs through ET0 (data source) and Kc (1998 vs Rev.1).
3. **The Alsadon benchmark** on the 5 cases whose crops v1 covers (Tabuk potato and tomato, Al-Ahsa tomato, Qassim tomato, Jazan pepper): window precision/recall and best-date hits for both.

`--selftest` runs everything on a synthetic climate to prove the script works. Its numbers mean nothing. It was run while building v2 and completed; in it, tomato stage lengths from v1 and v2 were identical, as expected.

Quick manual checks against v1:
- `python -c "import sys; sys.path.insert(0,'heatmap'); from advisor import *; print_recommendations(get_recommendations('riyadh'))"` (v1) vs `python feature2_v2/advisor.py riyadh --crop tomato` (v2).
- Compare v1 `crop_database.py` Kc values with `feature2_v2/agronomy.py` `KC_REV1` and S5 Table 6.1 (p. 165–167).

---

## 9. Limitations and open items

**Needs checking by hand before quoting in the report:**
- Irrigation efficiencies (drip 90 %, sprinkler 75 %, surface 60 %) are the only remaining hand-typed values (S8), and they are not in FAO-56.
- `validation/alsadon2002.py` transcribes S4 Table 5 from the Arabic; re-read the 16 rows against the document.

**Known limitations:**
- A few season lengths lean long: potato ~140 days (FAO 122; the workbook's potato Topt of 16 °C slows it), and okra and molokhia 130–150 days (they use the paper's Eq. 7 method because FAO-56 Rev.1 has no GDD data for them; FAO's own molokhia row is 140 days including repeated cuttings).
- "Season" follows FAO-56: sowing (or transplanting) to the end of harvest. Seed-packet "days to maturity" count to the first harvest, so they are shorter.
- **ET0 probably runs high** (both v1 and v2). FAO-56 Rev.1 Sec. 2.5 shows ET0 from dry, non-irrigated station surroundings, or from gridded data, is overstated (~17 % in its example). FAOCLIM-2 gives ET0 without dew-point data, so Rev.1's correction cannot be applied. Treat water totals as upper-leaning.
- Long-term means hide individual hot or cold days, so stress is a lower bound. v1's observed-year statistics are better here.
- Kc is not adjusted for actual humidity and wind (no data); only a dry-air upper bound is given. v1 is better here.
- Open-field crops only; greenhouse and mulched production are outside the paper's scope.
- Rainfall is ignored (conservative).
- No salt-tolerance numbers in FAO-56 Rev.1 for okra, watermelon, lentil or molokhia, so no leaching is computed for them.
- Perennials (grape, apple, date palm) are not covered; v1 still covers grape and apple.
- Tomato and cucumber each have two workbook rows; with Rev.1 Kc and GDD they now give nearly identical results.
- The Saudi benchmark has 16 cases; a larger calendar (e.g. the ministry's المفكرة الزراعية) would give a much stronger test.

---

## 10. File map

| File | Role |
|---|---|
| `README.md` | quick start and method summary |
| `DOCUMENTATION.md` | this document |
| `build_data.py` | extracts stations, crops and the spreadsheet fixture from S2 |
| `data/stations_ksa.json`, `data/crops_eln16.json`, `data/spreadsheet_fixture.json` | extracted data |
| `climate.py` | station sinusoids, nearest-station lookup, 11 cities |
| `elnesr_model.py` | exact paper/spreadsheet engine; interval-overlap efficiency |
| `crops.py` | KSA crop rows; applies Rev.1 Kc and GDD |
| `agronomy.py` | FAO-56 Rev.1 constants (Kc, GDD, soils, roots, p, salinity) and efficiencies |
| `season.py` | season and stage lengths, daily Kc/ET0/ETc, stress degree-days |
| `irrigation.py` | gross water, leaching, salinity yield, intervals, monthly and per-plant volumes |
| `advisor.py` | sowing-date scan and choice; CLI |
| `report.py`, `report_template.html`, `outputs/` | interactive HTML report and CSV for 11 cities |
| `api_router.py` | optional FastAPI router, not mounted |
| `tests/test_feature2_v2.py` | 29 tests (§6) |
| `validation/alsadon2002.py` (+ `_results.json`) | Saudi directorate benchmark (§6.5) |
| `validation/fao56rev1_gdd.py` (+ `_results*.json`) | season length vs FAO-56 Rev.1 (§6.6) |
| `validation/compare_with_v1.py` | v1 vs v2 side by side (§8) |
