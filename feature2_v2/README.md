# Feature 2 v2: KSA crop water planner

A stronger, better-evidenced version of Feature 2 (the location-based crop advisor). For any Saudi location it answers, per crop:

- **When can I sow here, and which day is best?** Every one of the 365 days is tested. You get a best date and a lowest-risk alternative.
- **How long is the season here?** Total and per FAO-56 growth stage, from the field-observed growing-degree-days of the 2025 FAO-56 revision, so it is shorter in hot places (Jazan, Makkah) and longer in cool ones (Abha, winter Tabuk).
- **How much water per stage, per month and per season?** Net crop water use (ETc) and the gross amount to pump after system efficiency and salt leaching. Given in mm, m³/ha and litres per plant.
- **How often to irrigate?** Root-zone water balance per stage, for your soil.

Everything is self-contained in this folder and runs **offline** (no API keys, no internet). The v1 code in `heatmap/` is untouched. **To remove v2, delete the `feature2_v2/` folder.** Nothing else in the repo imports it.

```bash
pip install openpyxl                 # only needed to re-extract data from the workbook
python feature2_v2/advisor.py riyadh                       # all crops for Riyadh
python feature2_v2/advisor.py jazan --crop tomato --ecw 2.0 --spacing 1.2 0.4
python feature2_v2/advisor.py 26.0 44.0 --soil sandy_loam --method sprinkler
python feature2_v2/report.py         # rebuild outputs/report.html + summary CSV (~30 s)
python -m unittest discover feature2_v2/tests -v           # evidence suite (28 tests)
python feature2_v2/validation/alsadon2002.py               # benchmark vs Saudi directorate calendars
python feature2_v2/validation/fao56rev1_gdd.py --old       # why season lengths moved to FAO-56 Rev.1
```

**Full audit trail** — every change from v1, every issue found, every source and every validation — is in [`DOCUMENTATION.md`](DOCUMENTATION.md).

Open `outputs/report.html` in any browser for the interactive report: city picker, sowing calendar, stage table, daily and monthly water charts, in light or dark mode. `outputs/summary_11_cities.csv` has one row per city × crop.

---

## What is better than v1

| | v1 (`heatmap/`) | v2 (this folder) |
|---|---|---|
| Climate data | NASA POWER reanalysis (0.5° grid), needs internet | **FAOCLIM-2 ground stations** (FAO), as fitted and published by Elnesr & Alazba (2016). 24 stations inside KSA, offline |
| ET0 | computed from reanalysis radiation/wind | **FAO's own station Penman-Monteith ET0** |
| Crops | 5 annuals + 2 perennials (strawberry unresolved) | **24 crop seasons, 22 crops** grown in KSA, incl. autumn and spring tomato, okra, molokhia, onion, garlic, melons |
| Paper method | "adapted from" Elnesr & Alazba | **exact reproduction**, checked against the KSU spreadsheet's own computed values (all 365 rows × 21 columns, zero difference) |
| Season length | GDD tables from Paredes 2025 | **FAO-56 Rev.1 (2025)** Tables 6.10–6.12 field-observed GDD per stage (18 crops); paper Eq. 7 heat units for the other 4 |
| Crop coefficients & soil constants | FAO-56 (1998) | **FAO-56 Rev.1 (2025)** Tables 6.1/6.2 (Kc, root depth), 8.1/8.2 (depletion p), 8.8/8.9 (salt tolerance), 7.5 (soils) |
| Stress check | day counts | **degree-days** beyond crop tolerance over the whole season, so a 44 °C day weighs more than a 36 °C one |
| Water output | ETc only | ETc, dry-air upper bound, **gross irrigation** (drip/sprinkler/surface efficiency), **salinity leaching and expected yield loss**, **irrigation interval**, **monthly volumes**, litres per plant |
| Location | 11 cities | 11 cities or any lat/lon (nearest station, with distance and elevation warnings) |

## Evidence

Run `python -m unittest discover feature2_v2/tests -v`. All 28 tests pass.

**A. The published KSU model is reproduced exactly.**
The workbook that ships with the paper (`data/sources/…mmc1.xlsx`) contains Excel's cached results on its `Model` sheet. `elnesr_model.py` recomputes all 365 sowing days from the same inputs. For every column (Tmax, Tmin, ET0, GDD, seasonal HU and ET by summation and by integral, the three suitability flags, the ET/HU/combined indices), the difference is **0 to 9 decimal places**. The heat-unit windows (DOY 90–123 and 199–232), the heat-unit + temperature windows (102–123, 199–232), the day counts (68, 56) and the best day (DOY 199) are also identical.

Reproducing the workbook surfaced these details of how it actually computes, which the Python engine follows exactly:
- The season length is the `DurTherm` column, not `DUR_total`.
- The HU test is `HU_min < HU ≤ HU_max`.
- The temperature test only checks the sowing day.
- `Model!L27` contains a broken `#REF!`, so Excel falls back to `Ta = (Tx+Tn)/2`.
- Paper Eq. 12 prints `(a_E − Tb)` where the sheet correctly uses `a_E`.
- Paper Eq. 28 calls the overall efficiency a *product*, but every value in its Tables 1–2 is the *mean* of the three partial efficiencies.

**B. The paper's model-efficiency metric is reproduced.** Given the relative set sizes in the paper's Table 1 (Central Maryland), `overlap_efficiency()` returns the published overall efficiencies to within 1 %. So once published MEWA or extension sowing calendars are available, you can score this model against them the same way the paper did.

**C. FAO worked examples and the 2025 FAO-56 revision.** FAO-56 Example 28 (Kc curve, Eq. 66), Example 27 (Kc_mid climate adjustment, Eq. 62: 1.30 and 1.07), FAO-29 Eq. 7 (leaching), Maas–Hoffman yield response, the p-adjustment (Rev.1 Eq. 8.5), and spot checks of the transcribed Rev.1 tables.

All crop and soil constants in `agronomy.py` now come from **FAO-56 Rev.1** (Pereira, Allen, Paredes et al., December 2025; `cd6621en.pdf` at the repo root), checked against the text extracted from that PDF, with book page numbers cited. Compared with the 1998 values v2 used before, several Kc values changed (tomato fresh market mid/end 1.15/0.80 → 1.10/1.00; okra 1.15/1.00 → 0.95/0.80; potato end 0.75 → 0.40), and several depletion fractions changed (potato and pepper 0.40, cabbage 0.35, squash 0.45). Garlic, pumpkin, okra and molokhia gained values. The paper-method engine keeps the workbook's 1998 Kc so the spreadsheet reproduction stays exact.

**Season length was switched to FAO-56 Rev.1 after a check against it.** `validation/fao56rev1_gdd.py --old` compares v2's original season length (paper Eq. 7 heat units, capped at the optimum temperature) with the length Rev.1's field-observed growing-degree-days give at the same sowing date and station. Only 8 of 210 city × crop cases fell inside the Rev.1 range, and **188 were longer** (cucumber, Makkah: 136 vs 54–90 days; spinach: 100 vs ~30). Capping development at the optimum made the 1998 durations a minimum that hot Saudi sites could never beat, which also overstated seasonal water. Seasons now use Rev.1 Tables 6.10–6.12 for the 18 crops listed there; watermelon, radish, okra and molokhia keep the Eq. 7 method.

**D. Data integrity.**
- The workbook labels 33 stations "Saudi Arabia", but 9 are actually in Kuwait, Bahrain or Jordan (e.g. "Kuwait International Airport", "Azraq", "Wadi Rum"). They are removed with a point-in-polygon test against `data/geo/national_border/SAU-geo.json`.
- The workbook's trailing column-index row, which would otherwise overwrite crop #1 (Broccoli), is skipped.
- Every station's climate is checked to be physical.

**E. Benchmark against Saudi directorate calendars (Alsadon 2002).**
Alsadon (2002, *J. King Saud Univ.*; copy in `data/sources/alsadon_2002_planting_dates_KSA.doc`) Table 5 lists the sowing dates recommended by the regional Directorates of Agriculture & Water for 16 crop × region cases (Tabuk, Al-Ahsa, Qassim, Jazan). It also lists Alsadon's own heat-unit program dates. `validation/alsadon2002.py` transcribes the table (original Arabic kept) and scores every method against the directorate dates:

| Method | Precision | Recall | Overlap efficiency Ω |
|---|---|---|---|
| Alsadon (2002) heat-unit program | 60 % | 40 % | 54 % |
| Elnesr & Alazba spreadsheet, heat-unit window | 68 % | 36 % | 51 % |
| Elnesr & Alazba spreadsheet, heat units + temperature | 53 % | 7 % | 36 % |
| **v2 "finishes in time" window** | 41 % | **89 %** | **77 %** |
| v2 low-stress window | 55 % | 26 % | 46 % |

- Precision is the share of a method's window that the directorate agrees with (Alsadon's own "% agreement" definition).
- Recall is the share of the directorate's window that the method covers.
- Ω is the paper's Eqs. 19–28 overlap efficiency.
- The directorates publish broad "you can plant" calendars. v2's broad window matches them best; its low-stress window is a conservative subset.

**Best single date inside the directorate window:** v2 9/16; the paper's index alone 11/16. History, for transparency:
- v2's first rule (least stress, then least water) scored 9/16.
- Switching to the paper's index, with the lowest-risk date as the alternative, raised it to 10/16. The rule was chosen after seeing this benchmark (no numeric parameter was fitted).
- A variant that tries the paper's heat-units-only index first scored 12/16, but it recommended sowing garlic in Qassim in late July at 43 °C, so it was not used.
- Moving season lengths to FAO-56 Rev.1 changed one case (Qassim tomato: the paper's Aug 1 index date now finishes in time, and it lies outside the directorate's Jan–Mar window), giving 9/16. The same change raised the window overlap from 68 % to 77 %.

With 16 cases, differences of one or two are noise; the window results are the more robust signal.

Where the best date misses: Tabuk potato and watermelon, Al-Ahsa onion and tomato (the nearest station, Qatif, is about 125 km away), Qassim lettuce and tomato, and Jazan cucumber (Dec 31, one day outside the Sep–Nov and Jan windows).

**F. Behaviour and agreement with KSA practice.**
- Stage lengths follow the Rev.1 GDD targets exactly (tomato at a constant 17 °C: 33/66/88/20 days), and the Eq. 7 fallback reproduces the FAO-56 durations at the optimum temperature.
- Cooler weather gives a longer season; nothing finishes below the base temperature.
- Against well-established Saudi practice: Tihama (Jazan) tomato is best sown in the mild winter; Asir (Abha) tomato in spring; potato, lettuce, carrot, onion and garlic in Riyadh, Qassim and Madinah are never sown in May–July; Riyadh potato is recommended.

### Sample results (drip, loamy sand, fresh water)

| City | Crop (FAO-56 row) | Status | Best sowing | Harvest | Days | Gross m³/ha | Lowest-risk date (gross m³/ha) |
|---|---|---|---|---|---|---|---|
| Riyadh | Tomato (arid, Jan) | possible, with temperature risk | Aug 10 | Nov 30 | 113 | 6,135 | Feb 15 (7,414) |
| Riyadh | Potato (semi-arid) | recommended | Feb 08 | May 13 | 95 | 4,270 | Nov 16 (3,914) |
| Riyadh | Lettuce (arid, Oct/Nov) | recommended | Feb 01 | Apr 14 | 73 | 2,921 | Nov 18 (2,612) |
| Riyadh | Watermelon (Near East desert) | recommended | Apr 21 | Jul 12 | 83 | 5,932 | Mar 27 (5,900) |
| Jeddah | Tomato (arid, Jan) | recommended | Oct 03 | Jan 18 | 108 | 5,095 | Oct 02 (5,056) |
| Jazan | Tomato (arid, Jan) | recommended | Oct 16 | Jan 25 | 102 | 4,653 | Dec 28 (3,841) |
| Makkah | Cucumber (fresh, arid Nov) | recommended | Oct 03 | Dec 12 | 71 | 3,191 | Oct 07 (3,176) |
| Tabuk | Watermelon (Near East desert) | recommended | Jun 20 | Sep 10 | 83 | 6,123 | same |

Across all 11 cities × 24 crop seasons: 140 recommended, 121 possible with temperature risk, 3 not suitable (too cold to finish in time). Riyadh tomato's best date is now the classic autumn sowing (August), and it is still flagged for heat stress in open fields.

---

## Method (in one page)

1. **Climate** (`climate.py`): `X(j) = a + ρ sin(ωj + φ)` for Tmax, Tmin and ET0 (paper Eq. 4), with parameters from the workbook's `Stations` sheet (FAOCLIM-2 long-term means). The nearest station to the location is used, with a warning beyond 100 km or ±300 m elevation.
2. **Season length** (`season.py`):
   - For the 18 crops in FAO-56 Rev.1 Tables 6.11/6.12, the daily rate is `min(max(Ta − Tbase, 0), Tupper − Tbase)` with Tbase/Tupper from Table 6.10, and each stage ends when its field-observed cumulative GDD is reached (mean of the short- and long-season rows where both are given).
   - For watermelon, radish, okra and molokhia the rate is capped at the optimum temperature and the crop needs `(Topt − Tbase) × DUR_total` (paper Eq. 7, the workbook's `ThermN` column), split over the FAO-56 stage shares.
3. **Water** (`season.py`, `irrigation.py`):
   - Crop water use: `ETc = Kc × ET0`, with FAO-56 Rev.1 Table 6.1/6.2 Kc values on the Eq. 66 curve.
   - Dry-air upper bound: FAO-56 Eq. 62/65 at RHmin 20 %.
   - Gross irrigation: `gross = ETc / (Ea × (1 − LR))`. Ea is 90/75/60 % for drip/sprinkler/surface (FAO Training Manual 4). LR is the FAO-29 leaching requirement.
   - Irrigation interval: `RAW / ETc`, where `RAW = p × 1000 (θFC − θWP) Zr` (FAO-56 Rev.1 Tables 7.5, 6.1 and 8.1/8.2, Eq. 8.5). The lower end of the Zr range is used.
   - Salinity: where Rev.1 Table 8.8 gives a range, the leaching requirement uses its most sensitive end and the expected yield is shown as a range.
4. **Sowing-date choice** (`advisor.py`):
   - A date qualifies if the crop finishes within `DUR_total × (1 + Htol/100)` days, i.e. the paper's heat tolerance applied to duration.
   - **Best date:** the paper's optimisation-index day, taken first from its "yellow band" (heat units and sowing-day temperature both OK), else from its heat-units-only band, as long as it qualifies. Otherwise the lowest-risk date is used.
   - **Lowest-risk date:** the fewest stress degree-days over the whole season, and among those the lowest seasonal ETc. It can differ substantially in water (Riyadh potato: Nov 16, 3,914 m³/ha, vs Feb 08, 4,270 m³/ha).
   - "Recommended" means at least one qualifying date has ≤ 5 °C·days of stress for the whole season.

Why the paper's heat-unit test is not used as a hard gate: it requires the mean temperature over `DurTherm` to reach `Topt`, which rejects warm-season crops in the highlands altogether (e.g. every tomato date in Abha). The paper itself reports that `Topt` had to be hand-tuned for 24 of 34 crops in its own validation.

## Sources

- Alsadon, A.A. (2002). The best planting dates for vegetable crops in Saudi Arabia: compatibility between heat-unit dates and dates suggested by the regional offices of the Ministry of Agriculture and Water. *J. King Saud Univ. (Agric. Sci.)* 14:75–97. Used as the KSA validation benchmark.
- Elnesr, M.N. & Alazba, A.A. (2016). A spreadsheet model to select vegetables planting dates for maximum yield and water use efficiency. *Computers and Electronics in Agriculture* 124:55–64 (King Saud University), and its Appendix A workbook. Supplies all crop rows, cardinal temperatures, heat tolerances and station climate fits.
- FAO (2001). FAOCLIM-2 world-wide agroclimatic database.
- **Pereira, Allen, Paredes, López-Urrea, Raes, Smith, Kilic & Salman (2025). Crop evapotranspiration, 2nd edition revised 2025. FAO Irrigation and Drainage Paper 56 Rev.1** (doi:10.4060/cd6621en; `cd6621en.pdf`). Tables 6.1, 6.2, 6.10–6.12, 7.5, 8.1, 8.2, 8.8, 8.9; Eq. 8.5; Sec. 2.5 on dry weather stations.
- Allen, Pereira, Raes & Smith (1998). FAO-56. Equations 58, 62, 65, 66 (unchanged in Rev.1); Tables 11–12 as used in the Elnesr & Alazba workbook.
- Paredes et al. (2025). *Agricultural Water Management* 319:109758. The GDD method adopted in FAO-56 Rev.1.
- Ayers & Westcot (1985). FAO-29 rev.1, water quality for agriculture. Leaching requirement.
- Brouwer et al. (1989). FAO Irrigation Water Management Training Manual 4. Field application efficiencies.

`data/*.json` is machine-extracted from the workbook by `build_data.py`, so it is auditable and regenerable. The constants in `agronomy.py` were transcribed from FAO-56 Rev.1 and checked against the PDF text, with the table and page next to each. The only remaining hand-typed values are the irrigation efficiencies (FAO Training Manual 4), which are not in FAO-56.

## Limitations

- **ET0 probably runs high.** FAO-56 Rev.1 Sec. 2.5 (p. 36–49) explains that ET0 computed from weather stations in dry, non-irrigated surroundings is overstated, because the air is hotter and drier than over a well-watered field. Its worked example shows about 17 % higher ET0 from arid data than from an irrigated reference site. Nearly all Saudi stations are in such settings, and FAOCLIM-2 gives ET0 without the dew-point data needed for Rev.1's correction. So v2's water figures (and v1's) should be read as upper-leaning estimates.
- Long-term means are not weather. Single hot or cold days exceed the curves, so stress is a *lower bound*. For live conditions, Feature 3 (Open-Meteo forecast) is the right tool.
- Open-field crops only. Greenhouse, net-house and mulched production are outside the paper's scope.
- Rainfall is ignored, which is conservative (most of KSA gets under 100 mm a year).
- The dry-air Kc bound fits inland stations. Coastal stations (Jeddah, Jazan, Dammam) sit nearer the central estimate.
- The workbook has no field maize, date palm, grape or apple rows, so v1 still covers the perennials.
- FAO-56 Rev.1 gives no salt-tolerance numbers for okra, watermelon, lentil or molokhia, so leaching is not computed for them; the output says so rather than guessing.

## Files

| File | Role |
|---|---|
| `build_data.py` | extracts stations, crops and the verification fixture from the workbook |
| `data/` | `stations_ksa.json`, `crops_eln16.json`, `spreadsheet_fixture.json` |
| `climate.py` | station sinusoids, nearest-station lookup, 11-city map |
| `elnesr_model.py` | exact paper/spreadsheet engine + interval-overlap efficiency |
| `crops.py` | which workbook rows represent KSA crops (+ Arabic names) |
| `season.py` | season length, stages, daily Kc/ET0/ETc, stress degree-days |
| `agronomy.py` | FAO-56 Rev.1 constants: Kc, GDD, soils, roots, depletion, salinity; efficiencies |
| `irrigation.py` | gross water, leaching, intervals, monthly and per-plant volumes |
| `advisor.py` | sowing-date scan, selection, CLI |
| `report.py`, `report_template.html` | builds `outputs/report.html` and `outputs/summary_11_cities.csv` |
| `api_router.py` | optional FastAPI router (`/v2/advisor/...`), not mounted by default |
| `validation/alsadon2002.py` | benchmark vs directorate sowing dates (writes `alsadon2002_results.json`) |
| `validation/compare_with_v1.py` | v1 vs v2 side by side (needs NASA POWER access) |
| `validation/fao56rev1_gdd.py` | season length vs FAO-56 Rev.1 GDD (`--old` reproduces the check that triggered the switch) |
| `tests/` | the evidence suite |
