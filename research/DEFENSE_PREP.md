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

---

## 6. Real-world validation: does the advisor's output actually match
    known Saudi agricultural practice?

**Checked directly against real sources, not assumed.**

- **Tomato:** Byari & Omar (1992), King Abdulaziz University — a real
  Saudi field study — found September planting scientifically optimal
  for fall-season tomato ("early planting in September... best planting
  date is mid/early August to mid-September"). Matches our model's Sep
  recommendation across all 11 cities almost exactly.
- **Potato:** Real Saudi sources (a USDA/ARC-style Saudi Arabia
  agriculture report; TADCO, a real major Tabuk potato producer) confirm
  Saudi farmers commercially run two seasons — spring (Jan) and autumn
  (Jul-Oct, sources vary slightly). Our model's October recommendation
  falls squarely inside the documented autumn season, in every city.
- **Corn:** Saudipedia documents Jazan's traditional corn season
  ("Mazarat al-Makhrat") beginning mid-October. Our model's Jazan
  recommendation (Nov 27) is in the same general season, about six weeks
  later — directionally correct, not an exact date match. Stated
  honestly as such, not oversold.
- **Pepper:** no comparably authoritative Saudi-specific source found.
  Follows the same internally consistent logic as the other three crops,
  but not independently externally verified.

**Bonus, real, citable finding:** Alsadon (2002) is a published Saudi
paper specifically studying "compatibility between dates planned based
on heat units and dates suggested from regional offices of the ministry
of agriculture" — i.e., real KSA agricultural science has already
documented that scientific optimization and traditionally-known dates
don't always perfectly coincide. Any modest discrepancy between our
model and an informal source is a known, expected, already-published
phenomenon in the field — not evidence our model is wrong.

**Overall verdict:** the model's unanimous "autumn planting" pattern
across all 11 cities is not a coincidence or an artifact — it's
independently confirmed by real Saudi university research, a real major
commercial producer, and documented traditional practice, for 3 of the
4 annual crops tested.
