# Addendum: Checking the "Good time to plant" band against AquaCrop

Standalone draft, not yet merged into DEFENSE_PREP.md. Covers one check: whether the dates the Plan tab calls "Good
time to plant" are actually good dates according to AquaCrop. Related sections of DEFENSE_PREP.md: 5 (shock-day
selection), C (what the AquaCrop validation proves) and D (the two seasons).

## 1. The question

The Plan tab marks a date "Good time to plant" when it is within 10 days of the crop's best start (one step of the
model's 10-day grid). The best start itself was validated against AquaCrop (Section C). The band around it was not.
For the 33 city x crop combinations that have AquaCrop results (tomato, potato and corn in 11 cities), how good is
AquaCrop's water productivity (WP) and yield on every date inside that band?

## 2. Method

`research/check_plant_now_band_aquacrop.py` reuses the cached AquaCrop results from
`research/aquacrop_reference_check.py`. For each combination it takes the app's pick (the lowest water per day,
exactly as in `--summary`) and every viable date within 10 days of it, and computes the shortfall
1 - (AquaCrop value on the date / AquaCrop's best value). Two references are used: the strict one (AquaCrop's best
among all viable dates) and the rule's own candidate pool (shock-free dates when any exist, as in `--summary`).

## 3. Results

| | Strict (all viable dates) | Rule's own pool |
|---|---|---|
| At the pick itself: median / mean / worst | 0.7% / 2.5% / 31.3% | 0.1% / 0.8% / 4.3% |
| At the pick: within 5% | 31/33 | 33/33 |
| Worst date inside the band: median / mean / worst | 3.2% / 8.9% / 80.5% | 2.3% / 7.2% / 80.5% |
| Worst date inside the band: within 5% / 10% / 25% | 18 / **27** / 30 of 33 | 21 / 29 / 31 of 33 |

By crop, the worst date inside the band (strict reference), median and worst: tomato 1.7% and 32.4%, potato 4.1%
and 13.0%, **corn 6.3% and 80.5%**. On the worst band date, AquaCrop's yield is a median 7.5% below its best (worst
81.6%).

Eight worst combinations (strict reference):

| City, crop | App pick | Worst band date | WP shortfall | Yield shortfall |
|---|---|---|---|---|
| Hail, corn | Sep 18 | Sep 28 | 80.5% | 81.6% |
| Tabuk, corn | Sep 18 | Sep 28 | 35.1% | 37.9% |
| Abha, tomato | May 31 | May 21 | 32.4% | 42.7% |
| Abha, corn | Jul 10 | Jun 30 | 21.0% | 15.8% |
| Tabuk, potato | Oct 08 | Sep 28 | 13.0% | 23.0% |
| Hail, potato | Oct 08 | Sep 28 | 11.2% | 22.3% |
| Riyadh, corn | Sep 28 | Sep 18 | 9.2% | 12.4% |
| Qassim, corn | Sep 28 | Sep 18 | 8.2% | 6.8% |

- **Hail corn is a cliff.** At the Sep 18 pick, 26 of 60 mid-season days are below corn's cold limit. Ten days later
  the mid-season stage stretches to 128 days, because heat accumulates more slowly into winter, and 109 of those
  days are below the limit.
- **Abha tomato and corn** are cases where the pick itself is already 31.3% and 20.4% below AquaCrop's best (the
  shock filter against AquaCrop's yield response; see the addendum on the 33/33 and 31/33 figures and Section C).
- The worst date is **later** than the pick in two of the eight (Hail and Tabuk corn) and **earlier** in six, so a
  one-sided band would not help.

## 4. What this does and does not establish

**Establishes:** for most combinations the whole band is good: 27 of 33 have every band date within 10% of
AquaCrop's best productivity, and the median worst date is 3.2% below. Tomato is the most forgiving crop.

**Does not establish:**
- Anything about the "Possible" state (shock-free dates outside the band), which was not tested.
- That AquaCrop is right. It is a model, not field yields, and it cannot be checked against Saudi field data here.
- Anything for the other eleven annual crops, which have no AquaCrop results.

## 5. Limitations of this check itself

- Only tomato, potato and corn, in 11 cities (33 combinations). The combinations are not independent trials.
- The band is judged on its worst date, which is a strict test: a date near the edge can be bad while the rest of
  the band is fine.
- The AquaCrop results are cached from the earlier `--summary` run and depend on its crop files and settings.

## 6. What changed as a result

- The rule is unchanged. A per-city exception for the few cliffs would be tuned on 33 combinations and likely
  overfit.
- The Plan tab's "How this is calculated" note now says that near the edge of a good window results can drop sharply
  for crops whose season runs into winter (for example corn in the cold north), and points to the crop card's cold
  days.
- The Plan card badges now use plain wording: "No stress days in a typical year", "Fewest stress days" and "Lowest
  water use (has stress days)" in place of "Shock-free window found", "Fewest exceedance days" and "Least-water
  viable".

## 7. Questions a reviewer might ask

**"Is a 'Good time to plant' date actually good?"** For most combinations, yes: in 27 of 33 every date in the band is
within 10% of AquaCrop's best productivity, and the median worst date is 3.2% below. Corn is the exception.

**"Where does it fail?"** Corn in the cold north (Hail 80.5%, Tabuk 35.1%): a 10-day shift pushes the mid-season
stage into winter. The app says so in its note and shows the cold days on the crop card.

**"Why not fix it?"** The failures are few and city-specific. Tuning a rule on 33 combinations to remove them would
risk overfitting, so the limit is documented instead.

## Numbers to know cold

| Item | Value |
|---|---|
| Worst band date within 10% of AquaCrop's best | 27 of 33 |
| Median worst band date | 3.2% below the best |
| Weakest crop | corn (median 6.3%) |
| Biggest cliff | Hail corn, Sep 28: 80.5% below |
