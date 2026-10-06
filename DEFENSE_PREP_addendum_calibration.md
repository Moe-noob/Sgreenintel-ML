---

## M. "Were the rejection thresholds (confidence 0.70, entropy 0.40) ever actually validated?"

**What prompted it.** Those two numbers (`training/predict_api.py`) were fixed constants chosen when the app was first
built, never tuned or tested against real data. Given the frozen benchmark and validation split already built for
Feature 1 (Section K), this was an opportunity to either justify them with evidence or replace them with something
better.

**Method.** A new tool (`feature1_eval/calibrate.py`) does a joint search over confidence AND entropy cutoffs
together (not confidence alone), fit **only on the validation split**, finding the pair that maximises how many
photos get answered while still hitting a target accuracy on the ones it does answer. The discipline carried over
from Section K: never choose a threshold by looking at the frozen benchmark, only confirm a chosen pair on it
afterward, exactly once.

**A bug this work exposed and fixed first.** While building the confirmation step, `feature1_eval/evaluate.py`'s own
reported accuracy-on-accepted-photos figure for crop-given mode (91.7%) disagreed with an independent recomputation
on the same data (92.3%). Cause: the evaluator's internal acceptance check applied the entropy rule to automatic mode
only, a leftover from before the crop selector (Section L) gave crop-given mode its own entropy check too — so
crop-given's reported numbers had been mildly overstated. Fixed and covered by a regression test built to fail on the
old code and pass on the new (both now verified, independently, to match a from-scratch recalculation off the raw
per-photo predictions).

**Target chosen: 90% accuracy on accepted photos**, for both modes. On the validation split, the search found:

| Mode | Confidence >= | Entropy <= | Coverage | Accuracy |
|---|---|---|---|---|
| Auto | 0.68 | 0.25 | 83.0% | 90.0% |
| Crop-given | 0.59 | ~1.0 (not a binding constraint at this target) | 92.2% | 90.0% |

**Confirmation on the frozen benchmark: the calibrated pair did not hold up.**

| | Auto: accepted / accuracy | Crop-given: accepted / accuracy |
|---|---|---|
| Current thresholds (0.70/0.40), confirmed under the fixed evaluator | 73.9% / **76.9%** | 77.5% / **85.2%** |
| Calibrated-for-90% thresholds, same benchmark | 72.7% / **77.5%** | 88.1% / **81.0%** |

The calibrated pair was supposed to deliver 90% accuracy and instead delivered 77.5% / 81.0% — a clear miss, not a
rounding difference. The underlying cause: raw (unfiltered) accuracy itself differs sharply between the two splits —
auto mode is 82.5% on validation but 67.0% on the benchmark, crop-given is 86.6% on validation but 76.5% on the
benchmark. The validation split, built from the general leftover pool of images not used in training, is measurably
easier than the benchmark, which is built only from PlantDoc's and PlantWild's own official test photos — the harder,
more deliberately varied set each dataset's authors held out. A threshold tuned on the easier split does not transfer.

**Decision: keep the original thresholds (confidence 0.70, entropy 0.40) in production**, for both modes. Not because
calibration failed as an exercise — it caught a real bug, and it produced the first-ever confirmed, benchmark-tested
numbers for these thresholds (76.9% / 85.2% accuracy on accepted photos, cited above). It is rejected as a basis for
*changing* the thresholds, because the number it promised (90%) did not hold up under the project's own confirmation
discipline, and re-tuning against the benchmark itself would have meant abandoning that discipline rather than
following where it led.

**Limits, if pressed further.**
- A higher coverage at lower accuracy (e.g. crop-given's calibrated pair: 88.1% of photos answered, at 81.0% accuracy)
  is a defensible product choice on its own terms — trading some trust for more photos actually getting a diagnosis
  instead of a "retake the photo" message. It was not adopted here because it did not meet the stated 90% goal, not
  because the trade-off itself is wrong.
- This result is a caution about using a non-held-out validation split for any future tuning on this project (e.g.
  the confusable-class fine-tuning question, if pursued): a split drawn from the same general pool as training data
  may not represent real-world or benchmark-level difficulty, and any result from it should be treated as provisional
  until confirmed on the frozen benchmark.

---

### Addition to the Part III cheat sheet (paste as new rows if keeping that table)

| Fact | Number |
|---|---|
| Rejection thresholds, confirmed on the frozen benchmark | confidence >= 0.70, entropy <= 0.40 (unchanged); 76.9% / 85.2% accuracy on accepted photos (auto / crop-given) |
| Calibration attempt (90% target, fit on validation) | did not hold up on the benchmark (77.5% / 81.0% instead of 90%) — validation split found to be easier than the benchmark |
