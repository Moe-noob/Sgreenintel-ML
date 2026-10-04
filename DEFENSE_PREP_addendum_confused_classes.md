# Addendum: Investigating the confused disease pairs (corn, tomato blight cluster)

Standalone draft, not yet merged into DEFENSE_PREP.md. Covers one investigation end to end: why certain disease
pairs score far below the model's average, what was tried to fix it, and what a direct look at the photos found.

## 1. The starting observation

Feature 1's v6p2 checkpoint performs well overall (67.0% auto-mode accuracy on the frozen benchmark) but unevenly
across classes. A small number of visually similar disease pairs account for most of the weakest results:

| Class | Recall | Paired with |
|---|---|---|
| corn gray leaf spot | 0.36 | northern leaf blight (0.79) |
| tomato early blight | 0.63 | late blight (0.61), septoria leaf spot (0.57) |
| potato early blight | 0.57 | late blight (0.74) |
| tomato leaf curl virus | 0.62 | mosaic virus (0.33) |
| apple cedar apple rust | 0.79 | scab (0.69) |

## 2. Three fixes attempted, three pre-registered failures

Each attempt was scored against targets fixed before training, on the project's frozen 1,267-photo benchmark, never
on the data used to pick a checkpoint.

**Corn (gray leaf spot / northern leaf blight), three different mechanisms:**

| Attempt | Mechanism | gray leaf spot recall | northern leaf blight recall | Result |
|---|---|---|---|---|
| v6p2 baseline | — | 0.36 | 0.79 | — |
| 1 | Full 35-class retrain, 4x sample weight on the pair | 0.44 (target 0.50) | 0.77 | Fail — also dropped 7 other classes by more than 5 points |
| 2 | Full 35-class retrain, weighting removed, larger anchor set | 0.36 | 0.70 | Fail — no movement on the target class |
| 3 | Dedicated specialist classifier (see §3) | 0.38 | 0.81 | Fail on the target class; zero effect on any other class |

**Tomato blight cluster (early blight / late blight / septoria leaf spot), three variants of the specialist approach:**

| Attempt | Change from the previous one | early blight | late blight | septoria |
|---|---|---|---|---|
| v6p2 baseline | — | 0.63 | 0.61 | 0.57 |
| 1 | Specialist, plain data pooling (target ≥0.73 / ≥0.71 / ≥0.67) | 0.66 | 0.59 | 0.57 |
| 2 | + real-world photos weighted to 65% of every training batch | 0.63 | 0.57 | 0.60 |
| 3 | + 570 training images with a verified conflicting label removed (§4) | 0.62 | 0.57 | 0.57 |

None of the six runs met its pre-registered targets. Each candidate checkpoint was deleted after scoring, per the
project's standing rule that a failed experiment is not written up as a result and does not alter production.

## 3. The specialist mechanism itself: proven safe, not proven useful

Attempts 3 (corn) and all three tomato attempts used a dedicated second classifier: v6p2's own feature extractor,
a new head covering only the 2-3 classes in question, trained independently, and activated only when v6p2's own
prediction already lands in that group — the main model is never retrained or otherwise touched. This was built
specifically because attempt 1's full retrain damaged unrelated classes.

This part worked exactly as designed. In automated tests (feature1_eval/tests/test_cascade.py) and in every one of
four live benchmark runs, every class outside the target group was numerically identical, to two decimal places,
with and without the specialist active. The mechanism adds a capability with no measurable downside; it simply
never produced a large enough improvement on the classes it targeted to be worth adopting.

## 4. A direct look at the photos

Three failed attempts at the same two problems raised an obvious question neither the numbers nor the code could
answer: is this a modelling limitation, or a data one? A sample of the photos was reviewed by eye (37 of the
model's errors inside confused pairs, 24 pairs of photos that had been dropped from the benchmark for carrying
conflicting labels, and 11 correct predictions for comparison).

**What the review found, by eye (student review, not an expert pathologist — see §6):**
- Of the 37 error photos: roughly 11 (30%) were not valid test photos at all — a video frame with a watermark and
  the on-screen caption "Developing lesions", a magazine graphic of rotting tomato *fruit* under a "how to identify
  late blight" headline, several stock photos with large visible watermarks, a roughly 80-pixel thumbnail, a
  near-black frame, whole-plant shots with no visible symptoms, and one photo of a child holding a largely healthy
  leaf. Roughly 5 more had labels that looked doubtful on inspection. The remainder (~17) were ordinary, valid, and
  simply hard.
- 22 of the 24 reviewed "conflict" pairs were confirmed, by feature matching (not just by eye), to be the exact
  same photograph filed under two different disease labels — in some cases two different crops entirely (an
  apple/pear photo filed as both apple black rot and grape black rot).

**This prompted a full, programmatic audit of the whole dataset**, not just the 24-photo sample, using a new tool
(feature1_eval/verify_duplicates.py) that re-checks every near-duplicate candidate the existing hash-based grouping
found, this time with geometric feature matching (ORB + RANSAC), calibrated on the 24 manually reviewed pairs
(confirmed duplicates matched on 30-1,500 points; the two false positives matched on 0).

**Results across the full dataset (61,975 images):**

| | Count |
|---|---|
| Near-duplicate groups carrying more than one label | 485 |
| …confirmed as the same photo under conflicting labels | 244 (50%) |
| …found to be false matches (chains of visually similar but distinct photos) | 241 (50%) |
| Confirmed conflicts spanning different crops | 70 of 244 (29%) |
| Benchmark photos originally dropped for a conflicting label | 98 |
| …confirmed as real conflicts | 96 (98%) |
| …found to be false positives | 2 (2%) |
| Training images subsequently excluded (conflicting label or duplicates a benchmark photo) | 570 |

The most frequent conflicting label pairs line up closely with the weakest-performing classes in the model:
corn gray leaf spot vs. northern leaf blight (30 instances), tomato bacterial spot vs. septoria leaf spot (26),
potato early vs. late blight (24), potato early blight vs. tomato early blight (24, cross-crop), tomato leaf curl
virus vs. mosaic virus (16).

One reassurance from this audit: the benchmark's own existing duplicate-drop logic held up well (98% of its drops
were confirmed real), which supports every accuracy figure reported earlier in this project. The much higher
false-match rate (50%) is almost entirely in the wider training data, not the curated benchmark.

## 5. What this does and does not establish

Three independent explanations for the two classes' poor performance were tested and each failed to produce a
fix: competition for model capacity with 33 other classes (attempt 1), under-exposure to real-world (vs. lab)
photos (attempt 2 of the tomato cluster), and training on images with contradictory labels (attempt 3 of the
tomato cluster). Ruling out three specific, testable causes is not the same as proving a fourth, untestable one.
What can honestly be said: the photo review and the dataset-wide audit both point toward the same two classes'
underlying data being genuinely ambiguous — in part because a measurable fraction of it is mislabeled or invalid,
and in part, plausibly, because the diseases are visually similar enough in these photos that even a correctly
labelled photo may not carry the information needed to tell them apart. The cleanest further test — asking a
plant pathologist to independently relabel a sample of the confused photos — was considered and set aside as out
of scope for this project.

## 6. Limitations of this investigation itself

- The manual photo review was conducted by the student, not a plant pathologist. Calls like "this label looks
  wrong" are informed opinions, not verified ground truth; the duplicate-matching numbers, by contrast, come from
  pixel-level feature comparison and are not opinions.
- The 37-photo error sample was drawn specifically from the model's *mistakes*, which is expected to over-represent
  low-quality photos relative to the dataset as a whole. The "~30% invalid" figure should not be read as an
  estimate of overall dataset quality.
- The feature-matching threshold was calibrated on only 24 hand-reviewed pairs; applied dataset-wide, it is a
  well-evidenced heuristic, not a guarantee, which is why the frozen benchmark's existing (hash-based) duplicate
  removal was deliberately left unchanged rather than rebuilt from this improved check.

## 7. What changed as a result

- `feature1_eval/verify_duplicates.py` and its test suite are a new, permanent, reusable diagnostic, committed to
  the repository, producing a reproducible audit report and a training-data exclusion list.
- The specialist-cascade mechanism (safe, tested, not adopted) was removed from the repository rather than left
  as unused infrastructure for a line of experimentation that did not pan out.
- Production — v6p2, its thresholds, and the live application — is unchanged by this entire investigation.
