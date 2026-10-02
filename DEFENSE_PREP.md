# SGreen Intel — Defense Preparation Notes

Running collection of hard questions worked through during development,
with real, sourced, or tested answers. Organized by topic. Add to this
as more questions come up.

---

## 1. "Feature 2 gives one planting date — isn't that a one-time lookup? Can't you just Google it?"

**Short answer:** the stability is intentional (that's what a climatology
is for), but what we produce isn't Google-able — it's a location-specific
water and risk budget computed from real physics, not a general blog
recommendation.

**Full answer:**
A climatological recommendation is *supposed* to be stable — it's built
from 10 years of averaged data specifically so it represents a "typical
year," not noisy one-off weather. If it changed wildly year to year, that
would be a red flag, not a feature.

The real distinction: a blog might say "plant tomatoes in Saudi Arabia in
autumn." Our system instead computes, for one specific city:
- The real viable planting window from actual NASA POWER climate data
- A stage-by-stage water budget (mm/day, L/plant, m³/ha) unique to that
  crop and location
- Whether a chosen date carries real temperature-tolerance exceedance
  risk, using a sourced Saudi-specific methodology (Elnesr & Alazba 2016,
  King Saud University)

That's not "when to plant" — it's a full water/risk budget, computed from
FAO-56 physics, not looked up.

> **UPDATE 1 Oct 2026 — two details changed**
>
> Litres per plant are no longer shown by default. They appear only when the user types a planting density, because the
> spacings the old figure assumed had no source; otherwise the app shows mm/day (1 mm = 1 L per m2).
>
> Each crop card now gives two planting seasons (an autumn pick and a spring pick), not a single date. See Part II, Sections D and G.

---

## 2. "Feature 2 and Feature 3 seem redundant — isn't Feature 3 just Feature 2 without the ranking?"

**Short answer:** they deliberately share the same underlying engine for
consistency, but answer genuinely different questions — planning
(before anything exists) vs. tracking (a specific plant you've already
committed to).

**Full answer:**
- **Feature 2** answers: "Which of several crops should I consider here,
  and when should I start?" — a decision made *before* planting,
  comparing multiple options. That's why it ranks.
- **Feature 3** answers: "I already planted X on real date Y — where is
  it right now, and does *this week's actual weather* change anything?"
  There's nothing to rank — you already chose. Feature 2 has no live
  weather at all; Feature 3 has no multi-crop comparison at all.

**Concrete evidence, not hypothetical:** tested directly this session — a
Riyadh tomato's live water need came out **23% below** the climatological
baseline on a real day, despite it being hotter than typical, because
the *actual* wind that day was unusually calm (see: live-vs-baseline ETc
comparison, Feature 3). Feature 2 has no concept of "today" and could
never surface this. Feature 3 caught a real, physically-explained
deviation a static plan would miss.

**Honest limit to state, not overclaim:** Feature 3's "more info" is
more granular *awareness*, not a different kind of prescription. Neither
feature converts ETc into an irrigation instruction (no soil model, no
efficiency losses in either). Feature 3 is more current, not more
prescriptive.

> **UPDATE 1 Oct 2026 — the live-vs-baseline comparison is now like-for-like**
>
> Feature 3 still works as described, and the 23% example was measured before the corrections in Part II. Live and baseline now use the
> same site-elevation correction and the same FAO-56 Rev.1 humidity correction, so the comparison isolates the weather and not a
> data-source mismatch. Tested: with a forecast equal to the climate normal, live and baseline ET agree to 1.000 on every day; leaving the
> live side uncorrected would have put it 15% high (Part II, Section A).

---

## 3. "Why 2016-2025 for the climatology? Why not shorter (more current) or the WMO 30-year standard?"

**Short answer:** tested directly — a short window (4-6 years) is
demonstrably too noisy; the current 10-year window and a full 30-year
window mostly agree closely with each other.

**Full answer, with real evidence (leave-one-year-out testing +
multi-window sensitivity analysis, 11 cities):**

- A short 2020-2025 (6-year) window produced a genuinely worse
  recommendation in real, concrete cases. Example: **Najran corn** —
  under 6 years, the model recommends Dec 17 with only 27/37 candidate
  dates shock-free; under both 10 years and 30 years, it recommends
  Oct 08 with **all 37/37 candidates shock-free** — a clean result. The
  two longer windows agree with each other; the short one is the outlier.
- The current 10-year (2016-2025) window and a 30-year (1996-2025)
  window mostly agree closely across all 11 cities and 6 crops (typically
  a few days' drift, 1-4% water difference).
- Verified directly: NASA POWER genuinely has real, non-fill data back
  to at least 1996 (confirmed via API query, not assumed).
- A real, self-derived warming trend was found in **every one of the 11
  cities** — temp_max_c trending +0.29°C (Abha) to +1.23°C (Tabuk) over
  29 years. Real, own-computed evidence of warming in Saudi Arabia
  specifically, not just citing external literature.

**Why not switch to 30 years as primary:** would require re-validating
every already-published Feature 2/3 result. The 10-year window isn't
contradicted by the 30-year one in the vast majority of cases, so the
switching cost isn't justified by the (mostly small) difference.

**Method comparison, also tested:** harmonic regression, Gaussian-weighted
smoothing, and LOESS were all tested against the current moving-average
method via proper leave-one-year-out cross-validation, across all 11
cities. None offered a practically meaningful improvement (best case
~0.003°C MAE difference). Current method kept as production
(see research/compare_climatology_methods.py and its README).

> **UPDATE 1 Oct 2026 — nothing changed, one labelling error fixed**
>
> Code comments and API text said "2014-2023" although the data window is 2016-2025; they were corrected. The site-elevation correction
> (Part II, Section B) adjusts the climatology from the NASA grid cell to the site; the choice of window is unaffected.

---

## 4. "Is -999 really NASA's documented missing-data code, or did you assume it?"

**Verified, not assumed.** Confirmed via independent third-party source
(a code review on an unrelated project using the same NASA POWER API)
explicitly stating "-999 is genuinely POWER's documented sentinel," with
a corresponding `NasaPowerNoDataError` for it. NASA's own API
documentation describes it as "the value for missing source data that
cannot be computed or is outside of the source's availability range."

---

## 5. The Tabuk corn / shock-day selection story — a real methodology
    finding, worth bringing up proactively

**What happened:** discovered that under the 2016-2025 climatology,
*every single one* of 37 candidate planting dates for Tabuk corn had at
least one temperature-tolerance exceedance — meaning the "prefer
shock-free dates" rule (Elnesr & Alazba 2016) had nothing to select from,
and the fallback picked purely by lowest water use, regardless of how
severely a candidate failed the exceedance test.

**Attempted fix:** rank the fallback by total exceedance-day count first,
water use second — a candidate excluded by one borderline day shouldn't
lose to one with dozens of exceedances just because the latter uses less
water.

**Rigorously re-tested against the model's most independently-validated
result (Riyadh corn, confirmed multiple times against real KSA autumn
field-crop practice) — and the fix broke it.** Riyadh corn flipped from
Sep 28 (real, validated) to Feb 20 (unvalidated, wrong season).

**Root cause, confirmed with real agronomic literature:** the fix
summed heat-shock and cold-shock days as if equivalent. They are not.
Corn is documented as most heat-tolerant at the seedling stage (up to
36°C) and most heat-*vulnerable* during tasseling/pollination
specifically, with yield losses of 3-8% per day of heat exposure during
that narrow window (SDSU Extension). Riyadh's "Sep 28" candidate had 60
total shock days — but all cold, none during a critical reproductive
window. The rejected "Feb 20" candidate had only 7 shock days — but they
were heat days, of unknown severity relative to corn's actual critical
period. Summing these as directly comparable numbers is not
agronomically defensible.

**Decision: reverted the fix.** Kept the original fallback (ignore shock
severity once non-shock-free, minimize water) since it happens to
preserve results that match real practice — not because it's agronomically
correct either, but because the alternative is demonstrably worse without
solving the underlying problem.

**Why this is worth bringing up in defense, not hiding:** it demonstrates
real methodological discipline — identified a genuine edge case, proposed
a principled fix, rigorously tested it against a known-good result rather
than assuming it was correct, caught a regression with real numbers,
traced the root cause to real literature, and made an evidence-based
decision to revert rather than ship an unverified "improvement." **This
is a stated, open limitation** of the current model: neither the old nor
new logic accounts for stress type or growth-stage timing, because no
sourced dose-response data exists for that level of granularity.

> **UPDATE 1 Oct 2026 — what still stands, and one tension to state**
>
> The reversal above still stands for tomato, potato, corn and bell pepper, which keep the original rule. For tomato, potato and corn that rule
> was later validated against AquaCrop (within 5% of AquaCrop's best date in 33/33 combinations; Part II, Section C).
>
> One tension must be stated openly: for the five lower-confidence warm-season crops added later (cucumber, eggplant, squash, pumpkin,
> green bean) the card headline is the autumn or spring pick with the FEWEST exceedance days, which sums heat and cold days, the very step
> this section rejected for corn. It is applied only to crops that no crop model can check, they carry a "Lower confidence" label, and it
> still ignores stress type and growth-stage timing, so the open limitation stated above is unchanged (Part II, Section E).

---

## 6. Real-world validation: does the advisor's output match known Saudi
    agricultural practice?

**Short answer:** at the level of *season*, yes. At the level of *exact
dates*, not exactly: differences run from a few weeks up to about two
months, in both directions. (An earlier version of this section said
"confirmed for 3 of 4 crops", "in every city" and "almost exactly". That
overstated it and was corrected after re-checking each comparison.)

Model dates are the production (2016-2025) recommendations across the 11
cities. References are what we actually found, not an exhaustive survey.

| Crop | Model (range across cities) | What the references say | Difference |
|---|---|---|---|
| Tomato | Sep 8 (Tabuk, Hail) to Nov 17 (Jeddah, Jazan); Riyadh Sep 28 | Byari & Omar (1992, King Abdulaziz Univ.): September best for fall-season tomato, window early Aug to mid Sep. FAO-56 Table 11, arid region: Oct/Nov and Jan. Saudipedia (general classification): summer crop, planted Mar-May | Consistent with the autumn references (interior cities 3-7 weeks earlier than FAO's Oct/Nov; Jeddah about 2 months later than the study's September). A different season from Saudipedia's spring listing |
| Potato | Oct 8 (Tabuk, Hail) to Nov 27 (Jazan); Riyadh Oct 18 | Two documented Saudi seasons: spring (Jan-Feb) and autumn (late Jul to Oct; sources vary: late Jul-mid Aug, Aug, Sep/Oct). FAO-56 arid: Jan/Nov | In the autumn season, but often 4-8 weeks later than the northern producers' dates. Never shows the spring season |
| Corn | Sep 8 (Tabuk) to Nov 27 (Jazan); Riyadh Sep 28 | Saudipedia: Jazan's traditional corn season starts mid-October. FAO-56 arid: Dec/Jan. One low-quality source says May to mid-June (not relied on) | Jazan: about 6 weeks later than the one documented Saudi date. Elsewhere no Saudi date found; roughly 1-3 months earlier than FAO's Dec/Jan |
| Pepper | Aug 29 (Tabuk) to Oct 28 (Jazan); Riyadh Sep 18 | No Saudi source found. FAO-56 arid: October | Within about a month of FAO's October (earlier in the north) |

**Known gaps, stated up front:**
- The advisor shows ONE date per crop, while real practice includes a
  second (spring) season: potato has a documented Jan-Feb crop, and
  Saudipedia lists tomato as a Mar-May crop. A two-window output (best
  autumn date and best spring date) is a planned improvement.
- The only Saudi tomato study found is from a Jeddah university (the
  trial site is not stated in the abstract we saw); our Jeddah date is
  about two months after its September.
- FAO-56 Table 11 is a generic arid-region calendar, not Saudi-specific.
  Saudipedia is an encyclopedia classification, not agronomic research.
- Pepper has no Saudi-specific reference at all.

**How much does "a few weeks" matter?** Little, for two reasons. First,
our own tests moved recommended dates by 10-20 days just from changing
which years were averaged (Madinah pepper: Sep 8, Sep 18, Sep 28 across
the 6-, 10- and 30-year windows), and by two months in one case (Najran
corn under the 6-year window); candidates are also sampled every 10 days.
Second, Alsadon (2002) is a published Saudi study of the "compatibility
between dates planned based on heat units and dates suggested from
regional offices of the ministry of agriculture", so disagreement between
heat-unit-based dates and traditionally known dates is already documented
in KSA agricultural science. A missing *season* (spring), unlike a few
weeks of drift, is a real gap worth addressing.

**Overall verdict:** season-level agreement, not date-level agreement.
For each of the four crops we found at least one independent reference
placing planting in autumn or early winter, and the model's dates differ
from those references by a few weeks up to about two months. It is not
evidence that the model's exact dates are right, and it says nothing
about the spring season the model never shows.

> **UPDATE 1 Oct 2026 — the known gap is closed, and the evidence changed**
>
> 1. The missing second season is built: each crop card now shows an autumn pick and a spring pick, with AquaCrop's estimate of what the
> spring choice costs (Part II, Section D).
>
> 2. The date table above comes from the production run BEFORE the Kc, elevation and humidity corrections. After them, 7 of 44 headline picks
> moved by one 10-day step, so regenerate before quoting a specific date.
>
> 3. Alsadon (2002) is no longer only a citation: its Table 5 (16 crop x region cases of directorate sowing dates, transcription re-checked
> 16/16 against the Arabic original) is now a benchmark. On the five cases our four original crops cover, the headline rule landed inside the
> directorate window in 1 to 2 of 5 cases (depending on the Al-Ahsa stand-in) against about 1.2 expected by chance, which is why the
> two-season output exists.
>
> 4. "Season-level agreement, not date-level agreement" remains the honest verdict.

---

## 7. Why do cold-shock counts look so high, even in mild Saudi winters?

**Verified directly against the actual crop_database.py values and the
selection code, not assumed.**

The threshold values themselves check out: all four `t_min_tolerable`
values (Tomato 14°C, Pepper 15°C, Potato 7°C, Corn 10°C) are taken
directly from the Elnesr & Alazba (2016) supplementary workbook, verified
against the real downloaded file. Corn's cold threshold (10°C, from
Elnesr) independently matches its GDD `t_base` (also 10°C, from Paredes
et al. 2025) -- two unrelated published sources landing on the same
number, a real cross-check, not a coincidence we engineered.

**The real explanation is in *what* gets tested, not the threshold
values.** The shock test compares the single coldest instant of each
night (Tmin) against the threshold -- not the day's average temperature.
A separate, unrelated metric (`cold_days`, using Tavg) correctly reflects
slowed growth; that metric does NOT drive the shock count or the
selection at all.

Saudi Arabia's desert climate has large diurnal swings -- warm, even hot
days with meaningfully cooler nights, in seasons that are overall mild.
A single-instant Tmin test is exactly the kind of check that fires
repeatedly in that climate pattern, even when the crop is objectively
fine during the day. This is a faithful, correct implementation of
Elnesr & Alazba's own defined test (Sec. 2.4.1: "a day is a cold shock if
Tmin < Tnc") -- not a bug we introduced. Whether their original paper's
regional context made this less of an issue than it becomes applied
broadly across 11 diverse Saudi climate zones is not something we can
confirm without the full paper text.

**Confirmed empirically, not just theoretically:** a systematic audit
(research/audit_shock_days_all_cities.py) across all 11 cities x 4
annual crops found 23/44 combinations where the currently-selected
(lowest-water) date has a large gap in total shock days versus the best
achievable option -- and in nearly every flagged case, the selected date
is dominated by cold-shock days while the rejected best-available
alternative is dominated by heat-shock days instead (e.g. Riyadh Corn:
selected 0 heat/60 cold vs best-available 7 heat/0 cold). This matches
independent real-world evidence: every Saudi source found tonight
(Byari & Omar 1992, TADCO, informal gardener accounts) frames *summer
heat* as the dominant real planning risk, never winter cold.

**Consequence for any future fix:** heat-shock counts (Tmax-based) likely
represent real risk more faithfully than cold-shock counts (Tmin-based,
inflated by diurnal-swing sensitivity). A future tiebreak improvement
would need to account for this asymmetry, not just sum or equally weight
heat and cold days -- exactly the kind of "sounds reasonable but isn't
validated" change that broke Riyadh corn earlier tonight (see Section 5).
No fix attempted tonight; documented as an understood, sourced
limitation instead.

> **UPDATE 1 Oct 2026 — numbers predate the elevation correction**
>
> The explanation (single-instant Tmin test, large diurnal swings) is unchanged. The audit numbers (23/44) predate the site-elevation
> correction, which moved temperatures at Abha by -6.7 C and at several lowland cities by +0.4 to +1.8 C, so re-run
> research/audit_shock_days_all_cities.py before quoting them.
>
> The "future fix" this section asks for has since been explored: a stress-first rule was tested against AquaCrop and against the Saudi
> calendars and rejected as a replacement for the default rule (Part II, Section D). It survives only as the spring pick and as the headline
> rule for the five lower-confidence crops.

---

## 8. "Your dates don't match the planting calendar. Is the model wrong? Why not fix the known dates and just calculate water?"

**What the model actually answers.** It selects the date with the lowest
*mean daily* crop water use among dates where the crop completes its
cycle (an adaptation of Elnesr & Alazba 2016, which minimizes *total*
seasonal water over a fixed season length; the adaptation is documented in
season_simulator.py). Farmers choose dates for yield, price windows, frost
risk and labor, none of which the model includes. It is a different
question, so exact dates differ (see Section 6).

**Tested, not argued.** research/compare_reference_dates.py runs the same
engine at the customary dates we found, in all 11 cities. Reference dates
are the midpoint of each cited range (our choice, not an official
calendar), and each is applied to every city, so this is a sensitivity
test, not a validation.

Whole-season crop water use at the reference date divided by the model's
pick: median across cities (min-max), with average shock days (heat/cold).
The model's own picks average 12/66 (tomato), 60/18 (potato), 0/38 (corn)
and 31/87 (pepper).

| Crop | Reference date | Seasonal water | Water per day | Avg shocks H/C |
|---|---|---|---|---|
| Tomato | KAU 1992, Sep 15 | x0.99 (0.92-1.21) | x1.07 | 34/56 |
| Tomato | FAO-56 arid, Oct 31 | x1.05 (0.93-1.15) | x1.03 | 4/73 |
| Tomato | FAO-56 arid, Jan 15 | x1.15 (1.01-1.28) | x1.32 | 28/40 |
| Tomato | Saudipedia, Apr 15 | x1.27 (0.97-1.70) | x1.89 | 86/1 |
| Potato | Saudi sources, Aug 15 | x1.05 (0.90-1.39) | x1.62 | 85/0 |
| Potato | Saudi/ARC, Sep 30 | x0.98 (0.92-1.13) | x1.10 | 66/18 |
| Potato | FAO-56 arid, Nov 15 | x1.07 (0.99-1.18) | x1.05 | 61/18 |
| Potato | Spring, Jan 31 | x1.21 (1.09-1.42) | x1.51 | 83/7 |
| Corn | Jazan tradition, Oct 15 | x1.01 (0.93-1.40) | x1.08 | 0/41 |
| Corn | FAO-56 arid, Dec 31 | x1.09 (0.97-1.31) | x1.19 | 0/30 |
| Pepper | FAO-56 arid, Oct 15 | x1.05 (0.99-1.11) | x1.02 | 23/87 |

**What it shows:**
- Autumn and early-winter reference dates use about the same total water
  as the model's picks: -2% to +9% (median per reference), though single
  cities range from about -10% to +40%.
- January and spring dates cost more: +15% to +27% seasonal water and
  +32% to +89% per day, and they swap cold shocks for heavy heat exposure
  (tomato Apr 15: 86 heat / 1 cold, against the model's 12/66).
- Some reference dates use LESS total water than the model's pick
  (Riyadh tomato Sep 15: 777 vs 823 mm; potato Sep 30: 553 vs 592 mm)
  because the model minimizes water per day, not season total. State this
  before being asked.
- Shock profiles of the autumn references resemble the model's picks, so
  shock days are not what separates our dates from the customary ones.

**"Why not fix the known dates and calculate water?"** We do. Feature 3
calculates water from a planting date the user supplies, and each of the
37 candidates in Feature 2 is exactly that calculation. The scan is kept
because: (1) no sourced calendar exists for every crop x city and the
references we found disagree by 1-3 months; (2) the app accepts any Saudi
location (search, geolocation), where a fixed calendar would not exist;
(3) it shows what shifting the date costs; (4) our own data shows Tmax
warming of +0.3 to +1.2 C over 29 years, which a fixed calendar ignores.
The fixed-date run is also the baseline that lets us state a water
difference at all.

**What we claim and do not claim.** Claim: the lowest-water feasible
window under a published selection method, with heat/cold exposure shown.
Do not claim: best planting date, best yield, or irrigation volume.
"Viable" only means the crop reached its heat-unit total within a year;
potato on Aug 15 is "viable" in 86 days with about 85 heat-shock days.

> **UPDATE 1 Oct 2026 — method unchanged, numbers predate the corrections**
>
> The ratios in the table were computed before the Rev.1 Kc, site-elevation and humidity corrections and may shift; re-run
> research/compare_reference_dates.py before quoting them. The spring dates this section prices (for example tomato Apr 15) are now offered
> explicitly as the spring option, with AquaCrop's estimate of what choosing them costs: about 32% lower water productivity for tomato
> (median over the 11 cities; Part II, Section D).

---

## 9. "Did you transcribe the crop parameters correctly? Why only these crops?"

**Re-checked against the published tables** (Paredes et al. 2025,
Agricultural Water Management 319:109758; Tables 1-3 for Tbase/Tupper,
Table 5 for cumulative GDD per growth stage). Every value in
crop_database.py matched:

| Crop | Tbase / Tupper | Stage GDD (ini/dev/mid/late) | Table 5 row used |
|---|---|---|---|
| Tomato | 7 / 28 | 325 / 660 / 880 / 200 | Market |
| Bell pepper | 10 / 35 | 445 / 1180 / 745 / 45 | Common |
| Potato | 2 / 30 | 405 / 530 / 490 / 835 | Long season |
| Maize (grain) | 10 / 32 | 200 / 380 / 500 / 340 | Short season |
| Strawberry | 3 / 30 | none | Not in Table 5 (matches its exclusion) |

Grape (10 / 35) and apple (4 / 35), from Table 3, also match. The
season-type choices (potato long, maize short) are modelling choices
documented in the database, not evidence about Saudi cultivars.

**Why not watermelon, cucumber, eggplant or squash?** Table 1 gives
Tbase/Tupper for them (watermelon 10/35, cucumber 10/32, eggplant 10/35,
squash and zucchini 10/32), but Table 5 has no cumulative-GDD stage rows
for them, and the rule in crop_database.py is that a value without a
source is not in the pipeline. Same status as strawberry. Table 5 does
have rows for melon (Cucumis melo), onion, carrot, garlic and fresh pea,
so those are the extension candidates (identified, not yet implemented).

> **UPDATE 1 Oct 2026 — three things changed**
>
> 1. The 1,420 versus 1,540 question (a paragraph missing from this copy). In Table 5 of Paredes et al. 2025, 7 of the 53 rows have stage
> values that do not add up to the printed total (soybean short +10, barley long +5, maize grain short +120, maize silage short +25, spring
> wheat short +20, rice short +10, rice long -75). Of the four original crops only maize is affected: its stages 200/380/500/340 sum to 1,420
> while the table prints 1,540. RESOLVED: FAO-56 Rev.1 (2025) Table 6.11 prints 1,420 for maize grain short season, equal to the stage sum, so
> the engine's value was right. For the record, research/corn_gdd_sensitivity.py showed that even if one stage were 120 higher the recommended
> start date would be unchanged in 6-9 of 11 cities (median shift 0 days) and seasonal water would be 4-12% higher.
>
> 2. Crop coefficients were updated to FAO-56 Rev.1 Tables 6.1/6.2. The heat-unit and threshold values in the table above were re-verified
> against the Rev.1 PDF (all 32 stage rows in Tables 6.11/6.12 and all 19 Tbase/Tupper values in Table 6.10 match, as do 23 Kc triples).
>
> 3. "Why not watermelon, cucumber, eggplant or squash?" is now outdated. Rev.1 Table 6.12 supplies heat-unit ranges for cucumber, eggplant,
> squash, pumpkin and green bean, and Table 6.11 supplies field-observed rows for onion, carrot, garlic, lettuce and sweet corn. All ten were
> added (Part II, Section E), the five from Table 6.12 labelled lower confidence. Still excluded: watermelon, radish, okra and molokhia (no
> heat-unit data in Rev.1) and broccoli, melon, cabbage, cauliflower, spinach and lentil (failed our checks). The rule stands: a value without
> a source is not in the pipeline.

---

## 10. "Isn't a shorter season better? Corn doesn't really grow in 74 days, does it?"

**What prompted it.** In the planting-date chart for Abha corn, July starts
show the lowest whole-season water (about 436 mm, 74 days, 5.9 mm/day),
while the model's pick (Oct 28) shows 505 mm over 121 days (4.2 mm/day).
Both have zero exceedance days.

**Why the season is 74 days.** The corn variant needs 1,420 heat units (the
four stage values 200 + 380 + 500 + 340 from Paredes et al. 2025, Table 5,
grain maize short season; the table's printed total says 1,540, see Section
9). The model caps heat-unit gain at 22 per day (Tupper 32 minus Tbase 10;
the daily MEAN is clamped, Tmax and Tmin are not capped individually), so the
shortest season it can produce is about 65 days (1,420 / 22). The trace for Abha starting
Jul 10 (research/trace_gdd.py, which matches the production simulation) shows daily
mean temperatures of 28-30 C giving 18.3-20.5 heat units a day (average 19.3), with
1,426 accumulated by day 74 against 1,420 required. The 22/day cap never applies
(0 days at the cap), so the length is plain heat-unit arithmetic in hot weather,
not a cap effect. FAO-56's arid-region reference for corn in
crop_database.py is 140 days, so 74 days is about half of it: an arithmetic
outcome of adding up heat units, not a field observation.

**Why the model does not pick the lowest total.** season_simulator.py
minimises water PER DAY, because total water rewards short, hot seasons.
Total-water comparisons are only fair when season length is fixed, as in
Elnesr & Alazba (2016); ours varies with heat.

**Tested** (research/objective_sensitivity.py; the script's copy of the
production rule reproduced the production pick in 44/44 combinations):

| Crop | FAO-56 arid reference | Current pick, median days | Total-water rule, median days | Total rule water vs current | Avg shocks H/C, current -> total |
|---|---|---|---|---|---|
| Tomato | 135-180 d | 147 | 120 | x0.93 (0.80-1.00) | 12/66 -> 33/16 |
| Pepper | 210 d | 191 | 121 | x0.85 (0.67-1.00) | 31/87 -> 77/1 |
| Potato | 130 d | 126 | 105 | x0.95 (0.89-1.00) | 60/18 -> 74/1 |
| Corn | 140 d | 135 | 74 | x0.84 (0.64-1.00) | 0/38 -> 14/0 |

- Picking by total water would save 5-16% of seasonal water (median) and
  would move the pick in 39 of 44 combinations (tomato 8/11, pepper 10/11,
  potato 10/11, corn 11/11).
- Season lengths under the current rule land within about 10% of FAO's arid
  references (tomato inside its range); under the total rule they are
  11-47% shorter. That is independent support for the per-day choice, from a
  source we already used.
- The total rule also lowers total exceedance days in every crop (tomato
  78 -> 49, pepper 118 -> 78, potato 78 -> 75, corn 38 -> 14) but swaps cold
  for heat, and heat is the more damaging kind during reproduction
  (Section 5).
- A hybrid (total water when shock-free dates exist, otherwise per-day)
  changes only 7 of 44 picks (tomato 1, corn 6). Where it changes corn it
  chooses short seasons (median 90 days; Abha 74), the case above.

**Is fewer days better?** Not automatically. Hotter weather speeds crop
development and generally shortens the period a cereal can intercept light
and fill grain, which tends to lower yield potential. We do not model yield,
so we cannot show a 74-day crop yields the same. A shorter cycle can help a
farmer (less exposure, more cycles per year), which is a different question
from the one the advisor answers.

**Caveats.** Abha's climate comes from a NASA POWER cell at 1,188 m while
the city is around 2,200 m (open item), so real Abha is probably cooler and
its seasons longer (the trace shows July Tmax about 36 C and Tmin 23-24 C there,
which looks like a lowland climate). Rainfall is not subtracted, so seasons that coincide
with rain (possibly Abha's summer, not checked) may need less irrigation
than the bars suggest. Yield is not modelled.

**Position:** keep the per-day rule; show season total alongside it (the
chart toggle); state that the total rule saves 5-16% of seasonal water only
by choosing seasons much shorter and hotter than FAO's references.

> **UPDATE 1 Oct 2026 — arithmetic unchanged, the Abha example no longer appears**
>
> The arithmetic below (1,420 heat units, at most 22 per day, so about 65 days at the very least) is unchanged and is still the right answer to
> "does corn really grow in 74 days?". The Abha example, however, came from a NASA cell at 1,188 m. After the site-elevation correction a Jul 10
> corn start in Abha takes 125 days, so the 74-day case no longer appears there; hot lowland sowings still produce short seasons (for example the
> total-water rule's Najran corn pick in July, about 69 days). The caveat about Abha's elevation is resolved (Part II, Section B).
>
> The "Tested" table is from before the corrections; the conclusion was re-confirmed by the AquaCrop re-run (total-water rule: median regret
> 13.8%, worst 41.8%, within 5% of AquaCrop's best in 11 of 33). An alternative that lengthens hot seasons by capping heat accumulation at the
> crop's optimum temperature was tested and rejected (Part II, Section F).

# PART II — Work of 1 October 2026

Sections A-I below were added after the nine original sections above (and the corn-season section 10). Every number comes from a
script run during that work; where a number rests on a small sample or a judgement, the text says so. Sections 1-9 are the original
text, kept unchanged, with "UPDATE" blocks where later work changed or extended a claim. An earlier draft of a Section 11 ("crop
extension and chart work: findings so far") is superseded by Sections D-G below and is not included.

---

## A. "Is your water number right? Where does ET0 come from, and could it be biased?"

**What prompted it.** Comparing the two versions of Feature 2 showed our NASA-based reference evapotranspiration (ET0)
was 7-67% above FAO's station values for the same cities. Hargreaves, which needs only temperature, agreed with the
stations, not with us.

**First, was it a bug?** No. An independent re-implementation of FAO-56 Penman-Monteith reproduced our engine's ET0
within 0.2-1.5% a year (worst single day 0.21 mm) on identical inputs. The engine's arithmetic is right; the inputs are
the issue.

**Why the inputs overstate ET0.** FAO-56 Rev.1 (2025), Sec. 2.5, explains that the Penman-Monteith equation assumes
weather over a well-watered reference grass. Weather from dry surroundings, and gridded reanalysis over dry land (NASA
POWER is one), carries air that is drier than a reference surface would have. In our data Riyadh's July minimum
temperature is about 26.6 C above its dewpoint; FAO's own example of a badly non-reference site shows about 10 C.

**The fix (Rev.1 Eq. 2.6).** Keep the temperatures, replace the humidity: Tdew = Tmin - aT, with aT set by the UNEP
aridity index (Rev.1 Box 2.4; our implementation reproduces FAO's Lerida worked example: I = 68.91, CEI = 724.7 mm,
AI = 0.52). Eight cities are hyper-arid (aT 4 C), Hail and Jazan arid (2.5 C), Abha semi-arid (1.5 C). We never make the
air drier than the source says (max of the two); that choice differs from the pure formula by at most 0.3% a year.

| | Result |
|---|---|
| Annual ET0 change | -6.0% (Abha) to -13.8% (Makkah), about -12% typical |
| Same-sowing-date seasonal water, after Kc + ET0 fixes | tomato -12.8%, pepper -8.9%, potato -22.0%, corn -12.5% (median, 11 cities) |
| Best planting date | moved in 7 of 44 picks, each by one 10-day step |
| Live vs typical in the tracker | agree to 1.000 per day once both use the correction (leaving live uncorrected would put it 15% high) |

**Honest limits.**
- After the correction, Riyadh is still about 20% and Madinah about 27% above the station ET0. Wind explains part of it:
  NASA 2 m winds are 2.4-3.6 m/s, FAO's default is 2 m/s, and using 2 m/s would cut another 8-10%. We have no measured
  Saudi winds, so we did not change it.
- Radiation is not the problem (within 3-12% of a temperature-based estimate in 9 of 11 cities).
- The station values are not truth either (FAO says dry-station data overstate ET0; Qatif is an oasis station; the old
  normals cover 1961-1990).
- Published Saudi ET0 ranges from about 2,000 to over 4,000 mm/year depending on the method. We therefore state our
  absolute litres and m3/ha as uncertain by roughly 15% (our estimate), and the app says so.

**If pushed: "so your water numbers are wrong?"** They were biased high by about 12% and are now corrected by FAO's own
documented procedure; the remaining uncertainty is stated. The ranking of planting dates barely moved (summer-to-winter
ET0 ratio changed about 4%), which is what the AquaCrop validation (Section C) tests.

---

## B. "Your climate data is a 50-km grid cell. How can it be right in the mountains?"

**What prompted it.** For Abha the NASA cell is at about 1,188 m, the city at about 2,200 m, the WMO station at 2,093 m.
The cell's July maximum was about 36 C against the WMO normal of 31.0 C.

**What we did.** A lapse-rate correction from the cell elevation to the site elevation (Copernicus 90 m DEM): 6.5 C/km
for temperature, 2.0 C/km for dewpoint; wind, radiation and rain are not adjusted.

**How we checked it** (criteria fixed before running; WMO 1991-2020 normals, 5 stations):
- The DEM matches the official station heights within 5 m at all five (2091/2093, 2051/2056, 724/725, 551/549,
  22/24 m).
- Abha's combined temperature error fell from 6.3 C to 0.8 C; Khamis Mushait 1.8 -> 0.5; flat Sharorah 0.9 -> 0.8 and
  Arar 0.6 -> 0.7 (no harm where no correction is needed).
- Shifts applied: Abha -6.7 C, Makkah +1.8, Madinah +1.2, Jeddah and Tabuk +0.7, Najran +0.5, Qassim +0.4, others
  within 0.2.

**Honest limits.**
- The coast has a different problem the fix does not touch. At Wejh the cell's maxima were 2.1 C too low and minima
  4.7 C too high (sea-land blending). Only one coastal station was tested, so we cannot say how far this extends to
  Jeddah, Dammam and Jazan.
- The warm-side shifts (Makkah, Madinah) were not directly tested against a station; the physics is the same as the
  validated mountain case and the small cases did not get worse.

---

## C. "What exactly does the AquaCrop validation prove?"

**Setup.** FAO's AquaCrop (v3.1.0) is the independent judge. Same daily weather and ET0 drive both models. Regret is the
shortfall in AquaCrop's water productivity (yield per m3) at our pick against its best date. 11 cities x 3 crops
(corn, tomato, potato) = 33 combinations. Re-run after the Kc, elevation and humidity corrections.

| Rule | Median regret | Worst | Within 5% of AquaCrop's best |
|---|---|---|---|
| **Water per day (ours)** | **0.1%** | **4.3%** | **33/33** |
| Water-productivity index | 0.0% | 35.1% | 32/33 |
| Total water | 13.8% | 41.8% | 11/33 |

Our picks are within 10 days of AquaCrop's best date in 32/33 and within 20 days in 33/33. Total water is rejected
("fewer days is not better"). The productivity-index rule is rejected on worst case (it was 80.4% before the corrections;
still 35.1% now, against 4.3% for ours).

**Water quantity against AquaCrop's ET at our pick** (median ratio, ours/AquaCrop): tomato 1.03 (11/11 within +-15%),
potato 1.14 (7/11), corn 0.98 (6/11); the largest gap is cold-season corn in Hail/Tabuk (up to 1.48), where AquaCrop cuts
transpiration under cold stress and we do not.

**What it does NOT prove.**
- AquaCrop uses our ET0, so it validates the Kc and season logic and the ranking, not the ET0 level (Section A).
- Tomato is partly circular: our tomato base/upper temperatures (7/28 C) are AquaCrop's own (Raes et al. 2023), and the
  heat-unit totals are close (2,065 vs 1,933). Corn and potato are the more independent checks.
- It says nothing about whether farmers actually plant on those dates (Section D).

---

## D. "Does the model match what Saudi farmers actually plant? Why two planting seasons?"

**What prompted it.** The model's picks were almost all autumn-winter. Saudi regional agriculture directorates publish
sowing calendars that very often list SPRING dates for the same crops. The calendar source we could read in full is
Alsadon (2002), Table 5: 16 crop x region cases (transcription re-checked 16/16 against the Arabic original).

**Finding 1: the two references disagree.** On identical climate and crop data (16 cases, Saudi FAOCLIM stations):
paper-style index rule 11/16 in the directorate window; "least stress first" 10/16; our least-water rule 8/16; lowest
water only 6/16; a random date 5.5-6.5. The probability of 11+ by chance is 0.3-0.9%; of 8+ it is 13-27%, so our rule's
8/16 is statistically indistinguishable from chance. On our own pipeline with NASA climate (5 comparable cases): ours
1/5, stress-first 3/5 and 2/5, chance 1.2.

**Finding 2: but stress-first loses to AquaCrop.** Within 5% of AquaCrop's best date: ours 31/33, stress-first rules 21-22/33;
tomato median regret 31%; for example Hail tomato falls to 49% of AquaCrop's best yield at its Mar 22 pick.

**Decision: report two seasons side by side** instead of forcing one winner:
- Autumn pick (sowing Jul 15-Dec 31): least water per day, as validated. Against AquaCrop's best date within the
  season: median regret 0.7%, worst 7.9%, 31/33 within 5%.
- Spring pick (Jan 1-Jul 14): least temperature stress among spring dates. Against AquaCrop's best spring date:
  median 0.0%, worst 13.4%.
- The app states what spring costs according to AquaCrop (water productivity vs the year's best date): tomato about 32%
  lower (range 13-55% across cities), corn 31% (10-47), potato 24% (7-44). Per city it is large inland (Hail 55%, Tabuk 53%,
  Qassim 52%, Riyadh 48% for tomato) and small on the coast (Jazan 13%, Jeddah 22%, Makkah 24%).

**Honest limits.**
- Five calendar cases cannot separate rules statistically, and the directorate windows are broad.
- The calendars are recommended dates, not outcomes: Alsadon himself reports low agreement between a heat-unit program
  and the directorates on recommended dates (about 1-18%, in his Arabic text) and attributes it to climatic, economic and
  marketing factors; Tabuk and Qassim are among the regions where he found the disagreement. They also reflect frost and
  tradition, which AquaCrop does not model.
- The two-season pick scored 2 of 5 on the calendars where chance under the same two attempts is 2.4: it is not evidence
  of matching local practice, which the app does not claim.

---

## E. "Why these crops? How did you add them, and what did you leave out?"

**Evidence base (all checked against the FAO-56 Rev.1 PDF, not typed from memory).** 23 Kc triples, all 32 stage
heat-unit rows (Tables 6.11/6.12), 19 temperature thresholds (Table 6.10) and the vegetable salt-tolerance rows match;
Rev.1 prints the maize short-season total as 1,420, equal to the stage sum, so the 1,540 printed in the Paredes 2025
paper was a typo and our engine's value was right.

**Rules written before each test.** Cool-season crops should pick Oct-Jan; warm-season crops Feb-May or Aug-Oct (a
winter pick for a cold-sensitive crop is a warning sign); simulated season length within about 25% of FAO-56's
arid-region duration. The heat-unit variant (short/long/mean) was chosen by that length rule BEFORE looking at the
Saudi calendars.

| Stage | Added | Season length vs FAO | Left out, and why |
|---|---|---|---|
| 1 (field-observed heat units) | onion 0.67x, carrot 1.06x, garlic 0.94x, lettuce 0.87x, sweet corn 0.85x | passes (onion short by a third, flagged) | broccoli (0.39-0.62x in every variant; its only FAO row is non-Saudi), melon (warm-season crop whose picks land in autumn) |
| 2 (min/max ranges derived from 1998 durations) | cucumber 0.97x, eggplant 0.95x, squash 0.91x, pumpkin 1.05x, green bean 0.80x | passes | cabbage 0.65x and cauliflower 0.72x (half the season in the initial stage), spinach 0.40x, lentil 0.60x |
| No data in Rev.1 | - | - | watermelon, radish, okra, molokhia |

**Labelled lower confidence (stage 2).** Heat units are a wide min/max range (cucumber 970-1,520; green bean 450-1,170),
and AquaCrop has no file for any of the 10 new crops, so each card says "Not checked against AquaCrop".

**The headline rule for the five stage-2 crops.** The least-water rule keeps choosing winter sowings for these
cold-sensitive crops (median 56-77 cold days for cucumber, eggplant, pumpkin). Their headline is the autumn or spring
pick with the fewest days outside the crop's temperature limits. Result on the five Saudi cases: headline inside the
directorate window 1/5 -> 5/5 (a random date: 2.0 expected, p = 0.08 for 4 or more). CAUTION: the spring-pick rule was
adjusted after seeing those cases (a degree-day version gave a headline worse than the default in 3 of 55 city x crop
cases), so treat 5/5 as encouraging, not proof.

**Tension with Section 5.** Section 5 above rejects summing heat and cold days (it broke Riyadh corn). This headline rule does sum them. It is
applied only to the five crops that no crop model can check, they carry a "Lower confidence" label, and it still ignores stress type and
growth-stage timing, which Section 5 names as the open limitation. Tomato, potato, corn and pepper keep the rule Section 5 defended.

**Season-length caveat.** At FAO's own reference sowing months (autumn) our seasons match its durations within +-10% for
10 of 14 crops. At spring sowings the five warm-season crops run 0.59-0.74x of FAO's duration; AquaCrop agrees with our
hot-start lengths for tomato (1.04x) but not for corn (0.79x), and has no reference for the new crops. Treat spring
water totals for them as uncertain.

---

## F. "Did you try alternatives? Why not cap heat accumulation at the optimum temperature?"

**The alternative.** Cap heat accumulation at each crop's optimum temperature (Topt, from the Elnesr & Alazba workbook)
instead of its upper limit; the other version of Feature 2 did this. Criteria fixed in advance: spring seasons closer to
FAO while autumn stays within +-10%; for tomato, corn and potato, closer to AquaCrop's days with the date rule still at
31/33.

| | Current cap | Topt cap |
|---|---|---|
| Date rule within 5% of AquaCrop's best | **31/33** | 18/33 |
| Potato season vs AquaCrop days, hot starts | 1.19x | 2.38x |
| Tomato season vs AquaCrop days, hot starts | 1.04x | 1.27x |
| Corn season vs AquaCrop days, hot starts | 0.79x | 1.07x (the one gain) |
| Potato water vs AquaCrop ET | 1.14 | 1.51 |
| Spring season length vs FAO, e.g. pepper | 0.63x | 0.84x |

**Verdict: rejected.** It repairs spring lengths for many crops but breaks the date rule's agreement with AquaCrop,
overshoots low-Topt crops (potato 1.25x of FAO), and Topt is a tuned parameter (Elnesr & Alazba report changing it for 24
of their 34 crops), not a physical constant. Other tested and rejected options, already documented above: ranking by
total water, ranking by a water-productivity index, stage-aware exceedance guards (mid-season exceedance filters raised
the worst case or the number of yield-losing picks), and a recommended "near-optimal" water window.

---

## G. "What did you find wrong in your own work?"

Worth saying plainly in the defense; each item was found by checking, fixed, and re-validated.

| Found | Fix |
|---|---|
| Crop coefficients were the 1998 values while the heat-unit tables belong to FAO-56 Rev.1 | Replaced with Rev.1 values (potato end-season Kc 0.75 -> 0.40, tomato 0.80 -> 1.00, pepper 0.90 -> 1.00, maize end 0.35 -> 0.30) |
| NASA grid cell at 1,188 m for a city at about 2,200 m (Abha) | Site-elevation correction (Section B) |
| ET0 biased high by dry-site humidity | FAO Eq. 2.6 correction (Section A) |
| Litres per plant used unsourced planting densities | Shown only when the user types a density |
| Code and API labels said 2014-2023 (data are 2016-2025); API text claimed "manually cross-checked" with no record | Corrected to what was actually done (AquaCrop reference run) |
| Division by zero on a hot sowing of lettuce (a stage needing 20 heat units could be closed twice in one day) | At most one stage boundary per day; 44/44 existing picks unchanged |
| "See care profile" shown for crops with no care text | Honest message |
| Water-productivity-index rule looked fine until the worst case (80%) was inspected | Rejected on worst case |
| I (Claude) overstated that spring seasons were "too short" and water understated by a third | Corrected after the cap experiment: FAO durations describe autumn sowings; AquaCrop agrees with our tomato hot-start lengths |

---

## H. "Another AI reviewed the outputs and called them robust. Does that count?"

It is a sanity read, not validation. A language model shown only the ranked dates agreed that the patterns are
climatologically sensible (Abha leaning to summer sowings: 9 of 14 crops start Jun-Aug or earlier; Jeddah and Jazan all
14 crops starting Oct-Dec; Tabuk and Riyadh each showing a spring and an autumn cluster). That would catch gross errors.
It could not have caught the ET0 bias, the season-length questions or the AquaCrop/calendar disagreement, and such
reviewers tend to agree. Evidence that counts: AquaCrop (Section C), the verified FAO tables (Section E), the Saudi
calendars (Section D), the WMO check (Section B).

---

## I. Numbers to know cold

| Fact | Number |
|---|---|
| Annual crops in the advisor | 14 (4 original, 5 stage-1, 5 stage-2); 2 perennials |
| AquaCrop check (3 crops x 11 cities) | 33/33 within 5% of best; 33/33 within 20 days; median regret 0.1%, worst 4.3% |
| ET0 correction | -6% to -14% (about -12%); remaining uncertainty about +-15% (our estimate) |
| NASA vs station ET0, before the fix | +7% to +67% |
| Abha temperature error, raw cell -> corrected | 6.3 C -> 0.8 C |
| DEM vs official station heights | within 5 m at 5 stations |
| Rev.1 constants checked against the PDF | 23 Kc, 32 GDD rows, 19 thresholds |
| Saudi calendar benchmark (Alsadon 2002) | 16 cases, 16/16 transcribed correctly; chance 5.5-6.5 of 16 |
| Spring planting cost per AquaCrop | tomato 32%, corn 31%, potato 24% lower water productivity (city range 7-55%) |
| Topt-cap alternative | rejected: date rule 31/33 -> 18/33 |
| Existing-crop regression after each change | 44/44, then 99/99 identical picks |

**What we do not claim.** That the app's dates match Saudi practice (only that its picks are explained against two
references that disagree); that absolute water is exact (about +-15%); that the 10 new crops are validated against a
crop model (they are not, and the cards say so); that wind speed or the coast's day-night range is solved.

---

# PART III — Feature 1 audit and crop selector (work of 2 October 2026)

Prompted by a Feature-1-v2 plan another AI agent (Claude Code) drafted on a separate branch. The plan itself trains nothing
and has no accuracy numbers; what came out of reading it was an audit of v1's own evaluation, a frozen benchmark, and an
optional crop selector added to the live app with no retraining.

## J. "Are your evaluation numbers reproducible? What do they actually measure?"

**What prompted it.** The other agent's plan said the committed `plantdoc_evaluation.json` / `plantwild_evaluation.json`
looked like "a stale, older model". Checking this directly: both scripts always evaluated whichever checkpoint
`load_best_model()` found first, discarded its name, and both hard-coded `plantvillage_test_accuracy = 90.29` (v2's figure)
regardless of which checkpoint was scored, so every JSON reported v2's PlantVillage baseline and no JSON said which model
produced its real-world numbers.

**What it actually was.** Not an old model: re-running both scripts with an explicit `--checkpoint` reproduced the
committed numbers (248/370, 720/1149) exactly from **v8p2**, not v6p2. The production model, v6p2, scores 262/370
(70.81%) and 733/1149 (63.79%) — matching the README, which was correct for v6p2 all along; only the two JSON files on
disk described the wrong model.

**Fix applied** (`training/evaluate_plantdoc.py`, `evaluate_plantwild.py`, `model_loader.py`): `--checkpoint PATH` to
evaluate a specific file, `--pv-acc X` to supply that checkpoint's own PlantVillage accuracy (the hard-coded 90.29 is
gone), and every result JSON now records the checkpoint's file name, size, SHA-256 and modification date, plus a
per-checkpoint copy so two models' results can never again overwrite each other.

**One more correction this produced:** with each model's own PlantVillage accuracy, v6p2's domain gap is 24.6 points
(PlantDoc) and 31.7 points (PlantWild) — not the 19.5/26.5 the stale 90.29 constant implied, and nowhere near the
README's old, since-removed "77pp -> 23pp" framing (see Part I, Section 9, UPDATE block, for why that framing no longer
applies at all).

**v6p2 vs v8p2, is the "worse real-world" framing solid?** A two-proportion check (unpaired) on the raw test sets: v6p2
minus v8p2 is +3.8 points on PlantDoc (95% CI −2.9 to +10.4) and +1.1 on PlantWild (95% CI −2.8 to +5.1). Neither
excludes zero. v6p2 is kept for scoring at least as well on both sets and being the lighter model, not because v8p2 is
shown to be worse.

## K. "What does the frozen benchmark actually show, and is it fair?"

**Built from `feature1_eval/`** (cherry-picked from the other agent's branch: manifest + perceptual-hash de-duplication +
leakage removal + inclusion rule + freeze-and-log, modified to be legacy-only; full provenance and what was deliberately
left out — training code, augmentation, advice base, weather rules — is in `feature1_eval/README.md`). Pooled PlantDoc
and PlantWild test photos, removed near-duplicates and photos whose near-duplicate carries a conflicting label, applied
`--min-train 0` (the default also demands 150 FIELD TRAINING photos per class, which is a question about training a new
model, not about evaluating v1; at the default setting it silently removed four classes v1 predicts and finds hard —
apple black rot, bell pepper bacterial spot, corn healthy, tomato mosaic virus — making the benchmark easier than it
should be).

**Result: 1,267 photos, 24 of v1's 35 classes.**

| | Model guesses the crop | User names the crop |
|---|---|---|
| All benchmark photos | 67.0% (95% CI 64.6-69.7%) | 76.5% (95% CI 74.3-78.9%) |
| Photos with no near-duplicate in v1's own training data | 65.3% (62.5-68.0%) | 75.2% (72.6-77.6%) |
| Live app's acceptance rule (confidence >= 0.70, normalised entropy <= 0.40) | accepts 73.9% of photos, 76.9% of those correct | accepts 81.3%, 83.5% correct |

**The clean-photo row (65.3% / 75.2%) is the number to quote**, not the "all photos" row: a contamination check (also
new; `feature1_eval/contamination.py`) found that 83 of the 1,267 benchmark photos (6.6%) have a near-duplicate among
the images v1 trained on (PlantDoc's and PlantWild's own training splits, plus v1's base training set), and those photos
score far higher (91.5% / 94.7%) than the rest, inflating the pooled score by about 1.7-1.3 points.

**Two things make this benchmark mildly OPTIMISTIC, stated for completeness:**
1. `--min-train 0` keeps classes with enough TEST photos even if v1 never saw many of them in training — fair to v1's
   evaluation, but it also means a class with very little training data is still included.
2. 7.1% of official test photos were dropped for a label conflict (the same or a near-duplicate photo carries two
   different labels across datasets) — concentrated in exactly the classes v1 confuses most (potato/tomato early
   blight: 8 photos; corn gray leaf spot vs northern leaf blight: 15 photos). Removing disputed photos removes some of
   the model's hardest cases along with genuinely mislabelled ones.

**Coverage gap, disclose directly if asked "is every class validated?":** 11 of v1's 35 classes have NO real-field test
photos in either PlantDoc or PlantWild, so no real-world figure exists for them at all: apple frog-eye leaf spot, apple
powdery mildew, corn northern leaf spot, grape esca, grape leaf blight (Isariopsis), strawberry angular leaf spot, leaf
spot, powdery mildew and leaf scorch, tomato spider mites and tomato target spot.

**Weakest crop: tomato, 56.1% (408 photos, the largest crop in the benchmark)** — bacterial spot (recall 30%), leaf curl
virus (recall 41%), mosaic virus (F1 0.46) are the worst classes. Strongest: grape, 93.3%.

**A bug the first real run exposed and fixed:** the PlantWild scanner read the numeric label in `trainval.txt` as an
index into whichever class folders happened to be extracted on disk. Correct only if all 89 official folders are
present; with fewer, it crashed (reproduced and fixed: the class is now read from the image's own path, as v1's own
training scripts already did) — a caution about auditing code before trusting its output, including code in this kit.
A second bug (the evaluator decoding every validation-split photo into memory at once) caused a `MemoryError` on the
first real run and was fixed by streaming one batch at a time; both fixes are covered by regression tests that fail on
the unfixed code.

## L. "What is the crop selector, and why no bigger retrain yet?"

**What it is.** `training/predict_api.py` accepts an optional `crop` argument. When given, every logit for a class
outside that crop is set to −inf before softmax, so the model's probabilities are computed only among that crop's own
classes; confidence and the entropy-rejection rule are then judged against that narrower class count (entropy divided
by log of the crop's own class count, not log(35)). No retraining, no new weights — v1's existing 35-way classifier,
asked a narrower question. `/predict` takes an optional `crop` form field; the Scan page gets a dropdown that defaults
to "Let the model guess" (automatic mode is byte-for-byte unchanged when left on that default).

**Why this was the first thing taken from the other agent's plan, not a bigger backbone:** it is the single largest
accuracy gain measured for Feature 1 (about +10 points, confirmed on the frozen benchmark, Section K above), costs no
GPU time, and does not change the model being defended. A bigger backbone (the plan proposed DINOv2) is the least
certain gain and the only one that needs a GPU v1's hardware (GTX 1650, 4 GB) cannot fine-tune directly; it stays an
optional, gated experiment (adopt only if it beats v6p2 on this same frozen benchmark), not a step taken yet.

**What was deliberately NOT taken from that plan, and why:** a 66-class taxonomy expansion (most of the new classes have
no field photos yet to validate against); severity estimation and a YOLO leaf detector (no validated need established);
the plan's colour-jitter / exposure augmentation (conflicts with the project's own no-colour-jitter rule for disease
detection; would need its own ablation first); its season-risk note (imports the FAOCLIM-based Feature 2 this project
did not adopt, Part I Section 6); date palm, sidr and red palm weevil modelling (the course supervisor advised these
established crops do not need modelling; Feature 2 already covers the crops the course targets).

## Numbers to add to the Part I/II cheat sheet

| Fact | Number |
|---|---|
| Frozen Feature 1 benchmark | 1,267 photos, 24/35 classes; v6p2 65.3%/75.2% (clean), 67.0%/76.5% (all) |
| Contamination in the benchmark | 83/1,267 (6.6%) share a near-duplicate with v1's own training data |
| Classes with no real-world test data at all | 11 of 35 |
| Crop selector gain (no retraining) | about +10 points, clean photos: 65.3% -> 75.2% |
| v6p2 vs v8p2 | not statistically distinguishable on either real-world set |
| v6p2 domain gap (own PlantVillage accuracy, corrected) | 24.6 pp (PlantDoc), 31.7 pp (PlantWild) |