# Addendum: Checking the climate data and the exceedance counts against real weather stations

Standalone draft, not yet merged into DEFENSE_PREP.md. Covers one check end to end: whether NASA POWER, after the
site-elevation correction, matches what real weather stations recorded, and whether the app's heat and cold
exceedance ("shock") counts match the stations for the same planting seasons. Related sections of DEFENSE_PREP.md:
5 (shock-day selection), 7 (why cold-shock counts look high), A (the water number), B (the 50 km grid cell) and
C (what the AquaCrop validation proves).

## 1. The questions

1. Does the elevation correction (Section B) bring NASA POWER close to real station temperatures, especially at
   Abha, where the NASA cell is at 1,188 m and the city is at about 2,100-2,200 m?
2. Do the app's heat and cold exceedance counts match the number of days a station actually recorded beyond a
   crop's limits, for the same season windows?
3. Secondary: how do NASA's dewpoint and 2 m wind compare with station readings, given that both feed ET0?

## 2. Data and method

**Station data.** An hourly weather file found online (`saudi-hourly-weather-data_Historical`, about 5.4 GB, roughly 80
station names, records ending 24 May 2019). The column layout and quality flags look like NOAA's Integrated
Surface Database, but the source and licence still need to be confirmed from the dataset page and cited. The file
is not in the repository (`data/external/`, git-ignored).

**Stations used** (the long-record entries for each city):

| City | Station name in the file | Station height | Rows |
|---|---|---|---|
| Abha | ABHA | 2,090 m | 310,776 |
| Najran | NEJRAN | 1,214 m | 300,355 |
| Jazan | KING ABDULLAH BIN ABDULAZIZ (the Jazan airport; coordinates 16.90 N, 42.59 E) | 6 m | 316,138 |

**Period.** Start years 2016-2018, the full years covered by both NASA POWER (window 2016-2025) and the stations
(which stop in May 2019).

**Processing.** Daily Tmax and Tmin from the readings, days with at least 6 readings only. The day boundary is
local time (UTC+3), assuming the file's times are UTC. Missing-value codes removed. Station wind (reported at
10 m) converted to 2 m with FAO-56 Eq. 47. On the NASA side the app's own pipeline was used
(`fetch_daily_climatology_full`, including the elevation and humidity corrections), compared date by date. 29
February was excluded because the NASA cache folds it into 28 February.

**Scripts** (both in `research/`): `compare_station_nasa.py` (temperature, dewpoint, wind) and
`compare_shock_days_station.py` (exceedance counts per crop and planting date).

## 3. Result 1: temperature and the elevation correction

| | Abha | Najran | Jazan |
|---|---|---|---|
| NASA cell height / station height | 1,188 / 2,090 m | 1,379 / 1,214 m | 31 / 6 m |
| Map (DEM) height at the station | 2,086 m | 1,208 m | 5 m |
| Tmax bias, raw NASA to corrected (degC) | **+5.3 to -0.5** | -0.4 to +0.7 | -0.7 to -0.5 |
| Tmin bias, raw to corrected (degC) | +5.3 to -0.5 | -1.1 to 0.0 | +0.2 to +0.4 |
| Tmax mean absolute error, raw to corrected | **5.3 to 1.3** | 1.25 to 1.17 | 1.08 to 1.01 |
| Tmin mean absolute error, raw to corrected | 5.3 to 1.2 | 1.65 to 1.40 | 1.35 to 1.38 |

- At Abha the correction removes about 90% of the error. The lapse rate that would fit the data exactly is
  5.9 degC/km against the 6.5 used (9% lower). Corrected Tmax is too cool by about 1.3 degC in June-August and by
  about 0.3 degC in the other nine months. (An early reading from a single month suggested 4.5 degC/km; the
  full-year fit does not support that.)
- At Najran and Jazan the cell and station heights are close, so the correction changes little. Raw NASA is already
  within about 1.0-1.7 degC mean absolute error. The "fitting lapse rate" the script prints for Najran is not
  meaningful with a 165 m height gap.
- The elevation source the app uses (Copernicus 90 m map through Open-Meteo) is within 4, 6 and 1 m of the three
  stations' recorded heights.

## 4. Result 2: days above a temperature limit

Days per year with Tmax above a limit, station | raw NASA | corrected NASA (the corrected series is what the app
uses):

| Limit | Abha | Najran | Jazan |
|---|---|---|---|
| above 35 degC (tomato's limit) | 0.3 / 117 / **0.3** | 158 / 145 / 164 | 189 / 174 / 180 |
| above 38 degC (squash, pumpkin) | 0 / 20 / **0** | 85 / 64 / 103 | 41 / 21 / 27 |
| above 40 degC (corn) | 0 / 0.3 / 0 | 17 / 6 / 34 | 2.3 / 0.3 / 0.3 |

Without the elevation correction, Abha would show about 117 spurious days a year above tomato's 35 degC limit.
Near a limit, counts swing hard on about 1 degC: at Najran the corrected series overshoots (the correction warms
by 1.07 degC), at Jazan NASA runs about 1 degC cool in the warm months and under-counts the hottest days.

## 5. Result 3: dewpoint and wind

Annual means of the monthly means:

| | Abha | Najran | Jazan |
|---|---|---|---|
| Aridity class and aT used | semi-arid, 1.5 degC | hyper-arid, 4.0 degC | arid, 2.5 degC |
| Dewpoint: station / NASA after elevation shift / after humidity fix (degC) | 8.1 / 9.1 / 12.6 | 3.2 / 3.3 / **15.1** | 23.8 / 21.6 / 26.0 |
| Wind at 2 m: station / NASA (m/s) | 2.31 / 2.42 | 1.69 / **2.75** | 2.48 / 2.77 |

- NASA's dewpoint, after the elevation shift, agrees with the stations within about 1 degC at Abha and Najran
  and is about 2 degC too dry at Jazan.
- The humidity fix (Section A, FAO-56 Rev.1 Eq. 2.6) raises the dewpoint a lot where the station sits in very dry
  air: about 12 degC above the station at Najran. This is its intended effect (the station is a dry,
  non-reference surface), so this comparison cannot validate the aT values, only show their size.
- NASA's wind at Najran is about 63% above the airport's; at Abha and Jazan it is within 5% and 11%.
- Illustration only, not a result: a single Najran July day with an assumed radiation of 27 MJ/m2 (the stations
  have no radiation) gave ET0 of 8.95 mm/day as the app computes it; swapping in the station wind alone gave 7.92,
  the station dewpoint alone 10.54, both 8.64. Each assumption alone moves ET0 by roughly 11-18%, and at Najran
  they partly cancel.

## 6. Result 4: the app's exceedance counts against the stations

For every crop and planting date, the app's season window (start day and cycle length) was applied to the station
and NASA daily records for 2016-2018. Counts are days over the crop's limits per cycle. Four sources: station,
NASA daily values, the app's headline counts (smoothed typical year), and the app's raw-year counts (unsmoothed
NASA years 2016-2025, `raw_exceedances`). About 1,570 usable station days per city; 518 crop-by-date windows per
city.

Mean absolute error against the station (days per cycle):

| | Abha | Najran | Jazan |
|---|---|---|---|
| Heat: NASA daily / app headline / app raw | 1.2 / 1.8 / 1.7 | 4.1 / **6.2** / 4.6 | 1.5 / 1.6 / 2.2 |
| Cold: NASA daily / app headline / app raw | 5.1 / **6.2** / 4.3 | 1.8 / **3.0** / 2.8 | 0.0 / 0.0 / 0.0 |

Windows where the app reports zero days but the station recorded some:

| | Abha | Najran | Jazan |
|---|---|---|---|
| Heat: station at least 1 day | 18 of 409 (4%) | 72 of 170 (**42%**) | 73 of 207 (**35%**) |
| Heat: station at least 10 days | 3 | 22 | 23 |
| Cold: station at least 1 day | 86 of 264 (33%) | 121 of 384 (32%) | 0 of 518 |
| Cold: station at least 10 days | 20 | 34 | 0 |

At each crop's recommended start (station | NASA daily | app headline | app raw):

- Where a crop is far over or under its limit the sources agree: Jazan potato 87 / 87 / 87 / 87 heat days, carrot
  73 / 73 / 73 / 72, lettuce 55 / 55 / 55 / 55; Abha pepper 180 / 201 / 199 / 195 cold days; Najran tomato 83 / 75 /
  79 / 69 cold days.
- Near a limit the headline counts miss days: Najran corn 26 / 21 / **0** / 16 cold days, sweet corn 20 / 16 / **0** /
  13, green bean 12 / 17 / **0** / 19 heat days, garlic 14 / 28 / **0** / 27.
- They can also overshoot: Najran potato 63 / 87 / **118** / 90 heat days, lettuce 34 / 54 / **78** / 55.

Why: the headline counts use the smoothed, averaged typical year (`_run_cycle`), where hot and cold spells are
averaged away, so a crop whose limit sits near the average gets "none" or "too many" on a small shift. The
raw-year counts use unsmoothed days and are closer to the station in 4 of the 5 non-trivial comparisons.

## 7. What this does and does not establish

**Establishes:**
- The elevation correction works where it matters: it removes about 90% of Abha's temperature bias and about 117
  spurious hot days a year, and the app's elevation source matches the stations to within 6 m.
- NASA POWER is within about 1.0-1.7 degC mean absolute error of the stations at Najran and Jazan.
- The exceedance counts are reliable when a crop is clearly over or under its limit, and the high cold counts in
  Section 7 of DEFENSE_PREP.md are real nights below the stated limit, not an artifact of the NASA data.
- Near a crop's limit the headline counts are not reliable: in Najran and Jazan, 35-42% of the windows the app
  calls free of heat days had at least one real hot day.

**Does not establish:**
- That the water numbers are right. The stations have no radiation or rainfall, so ET0 could not be recomputed.
- That the humidity correction is right (the station is not a reference surface), or that NASA wind is wrong
  (one airport per city, and the 10 m to 2 m conversion is itself an assumption).
- That the crop temperature limits are right. They come from one source (Elnesr and Alazba 2016).
- Anything about 2020-2025, which the station records do not cover.

## 8. Limitations of this check itself

- Three years only (2016-2018), and the stations are airport points compared with a 50-60 km grid cell.
- The 518 windows per city overlap heavily (14 crops, up to 37 start dates each), so the percentages above are
  shares of windows, not independent trials.
- The file's times are assumed to be UTC (not confirmed). Daily maxima from readings can miss the true peak
  slightly. Season windows need at least 90% of their days with data. In 2016 (a leap year) day-of-year windows can
  be off by one day after February.
- The source and licence of the station file are not yet confirmed.
- The exceedance summary is not split by crop, so it cannot yet name squash or pumpkin in Jazan on its own.

## 9. What changed as a result

- No change to the selection rule, the picks or the AquaCrop validation (Section C).
- The frontend (`index_2.html`) now describes stress days as counted "in a typical year", states that they can
  be missed near a crop's limit, and moves the technical wording into a collapsed "How this is calculated" note.
- The raw-year counts (`raw_exceedances`) are already in the API output and could be shown as a range later.
- Not yet changed: the "Shock-free window found" badge on the Plan cards still uses the older wording.

Possible follow-ups: a per-crop breakdown of the zero-day windows (especially Jazan squash and pumpkin); a second
mountain station (Taif, 1,478 m) to test 5.9 against 6.5 degC/km; a wind sensitivity across all stations; newer
station data for 2020-2025; confirming the file's time zone, source and licence.

## 10. Questions a reviewer might ask

**"Did you validate the elevation correction?"** Yes, against hourly records at Abha for 2016-2018: bias from
+5.3 to -0.5 degC, mean absolute error from 5.3 to about 1.3 degC, and about 117 spurious hot days a year removed.
Najran and Jazan have cell heights close to the station, so the correction changes little there.

**"Why 6.5 degC per km?"** It is the standard-atmosphere lapse rate. At Abha the best fit is 5.9, about 9% lower,
and the correction runs about 1.3 degC cool in summer. Taif would be a useful second mountain test.

**"Are the heat and cold counts accurate?"** Far from a limit, yes, within a few days. Near a limit they are
typical-year counts and can miss days, which the app says in its notes.

**"Does this change your recommendations?"** The selection rule was not changed, so the picks and the AquaCrop
validation are as before. What changed is how the counts are described.

**"Why only three years?"** The station file ends in May 2019 and NASA's window starts in 2016, so full years in
common are 2016-2018.

## Numbers to know cold

| Item | Value |
|---|---|
| Abha Tmax bias, raw to corrected | +5.3 to -0.5 degC |
| Abha spurious days above 35 degC | 117 per year (station 0.3) |
| Best-fit lapse rate at Abha | 5.9 degC/km (code uses 6.5) |
| Map height vs station height | within 4, 6, 1 m (Abha, Najran, Jazan) |
| Najran wind, NASA vs station | 2.75 vs 1.69 m/s (+63%) |
| App says zero heat days, station recorded some | 4% / 42% / 35% (Abha / Najran / Jazan) |
