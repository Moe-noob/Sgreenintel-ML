# Feature 1 evaluation kit

A small, tested toolkit for measuring the CNN honestly. It trains nothing and changes no model. It answers three questions the old
evaluation scripts could not:

1. How accurate is v6p2 on real field photos **after removing near-duplicates and label conflicts**, with confidence intervals?
2. How many benchmark photos have a near-identical twin in v1's **own training data** (so the score was inflated), and what is v1's
   accuracy on the photos that do not?
3. What does the live app do today: how many photos does it accept at the 0.70 / 0.40 rules, and how accurate are those?

## Provenance (what this is, and where it came from)

Cherry-picked from the `feature1_v2` package on the branch `claude/compassionate-hopper-lh08ol`, which another AI agent (Claude Code)
wrote as a proposed plan for a better Feature 1. Only the evaluation machinery was taken; read every file you intend to defend.

| Taken (unchanged except the package rename `feature1_v2` -> `feature1_eval`, env prefix `F1V2_` -> `F1E_`) | |
|---|---|
| `data/manifest.py` | scans PlantWild, PlantDoc and v1's processed set into one CSV; never guesses unknown labels |
| `data/dedupe.py` | perceptual-hash near-duplicate groups across all datasets (pHash, <= 6 differing bits of 64) |
| `data/splits.py` | field validation split + frozen benchmark; removes leaks; logs every use of the benchmark |
| `metrics.py`, `taxonomy.py`, `config.py`, `sources.json` | bootstrap intervals, calibration error, the class map for the 35 v1 classes |
| `tests/test_data_pipeline.py` | 11 tests of the above |

| Changed | |
|---|---|
| `evaluate.py` | legacy-only (no v2 backbones, no `timm`); results go to `work/eval_<checkpoint name>/<split>/` so one model can never overwrite another; the report records the checkpoint's name, size, SHA-256 and date; applies v1's exact acceptance rules (confidence >= 0.70, normalised entropy <= 0.40) |
| `inference.py` | defines its own plain `eval_transform` instead of importing the v2 training module |

| New | |
|---|---|
| `contamination.py` + `tests/test_contamination.py` | measures twins between the benchmark and what v1 trained on (PlantDoc train, PlantWild train split, v1's base training set) |
| `drops_report.py` + `tests/test_drops_report.py` | accounts for every official test photo (kept, or dropped for a label conflict / an excluded class) and the effective benchmark size after counting near-copies once |
| `tests/test_inference_streaming.py` | checks that photos are decoded one batch at a time (needs torch) |

| Left out on purpose | Why |
|---|---|
| v2 backbones, training loop, augmentation (including its white-balance / exposure shifts), detector, distillation, advice base, weather rules, Colab notebook | not needed to evaluate v1; the colour shifts conflict with the project's no-colour-jitter rule and would need their own ablation |

## Before you start

- Same folder layout v1 used: `data/raw/PlantDoc-Dataset/{train,test}`, `data/raw/plantwild/plantwild/{images,trainval.txt}`,
  `data/processed_v2/{train,val,test}`.
- Packages: numpy, Pillow, torch, torchvision (already installed for v1). The tests also use scikit-learn.
- Unzip this folder into the project root so that `feature1_eval\` sits next to `training\`.
- Optional environment variables: `F1E_DATA_ROOT` (default `data\raw`), `F1E_WORK_DIR` (default `feature1_eval\work`),
  `F1E_BENCHMARK_DIR` (default `feature1_eval\benchmark`).

## Steps (PowerShell, from the project root)

```
python -m unittest feature1_eval.tests.test_data_pipeline feature1_eval.tests.test_contamination feature1_eval.tests.test_drops_report feature1_eval.tests.test_inference_streaming
python -m feature1_eval.data.manifest
python -m feature1_eval.data.dedupe
python -m feature1_eval.data.splits --min-train 0
python -m feature1_eval.drops_report
python -m feature1_eval.evaluate --legacy models\cnn\mobilenetv2_sgreenintel_v6p2.pth --split val
python -m feature1_eval.evaluate --legacy models\cnn\mobilenetv2_sgreenintel_v6p2.pth --split test --final --purpose "baseline v6p2"
python -m feature1_eval.contamination --predictions feature1_eval\work\eval_mobilenetv2_sgreenintel_v6p2\test\predictions.csv
```

1. **tests**: 23 tests, a few seconds (about 20 on Windows). All must pass before you trust anything else.
2. **manifest**: prints how many images each source has per label and **lists every source folder name it could not map**. Nothing is guessed; if
   something is unmapped, paste me the list.
3. **dedupe**: hashes every image (a few minutes) and writes `work\hashes.csv`; prints how many duplicate groups it found.
4. **splits --min-train 0**: builds the splits, removes leaks and conflicting labels, keeps every class with >= 30 benchmark photos, and
   **freezes the benchmark** into `benchmark\`. Read its report: it lists every excluded class with counts. Use `--min-train 0`: the default rule also
   demands >= 150 field TRAINING photos, which is a question about training a new model, not about evaluating v1. Applied to the benchmark it
   removed four classes v1 predicts and finds hard (apple black rot, bell pepper bacterial spot, corn healthy, tomato mosaic virus), making the
   benchmark optimistic for v1. Expect the classes with no real-field test photos at all to remain excluded.
   If a `benchmark\` folder already exists from an earlier run, rename it (for example to `benchmark_provisional`) first; do not delete it and do
   not use `--force-refreeze`, so the earlier freeze and its usage log stay on record.
5. **drops_report**: accounts for every PlantDoc / PlantWild test photo: kept, dropped because a near-duplicate carries a different label
   ("label conflict"), or dropped because its class was excluded. It also gives the effective benchmark size, counting near-copies once.
6. **evaluate --split val**: a first look on the field validation split (used for model selection, never for the final number).
7. **evaluate --split test --final**: the baseline on the frozen benchmark. Every `--final` use is appended to `benchmark\usage_log.txt`.
8. **contamination**: splits v1's benchmark score into photos with and without a twin in v1's training data.

## How to read the results

- `report.md` / `report.json`: accuracy and macro-F1 with 95% bootstrap intervals, in two modes (model picks crop and disease / crop selected by
  the user), per-crop and per-class tables, calibration error, accepted share and accuracy at v1's rules, and the share of photos whose class v1
  cannot predict at all.
- `contamination.md`: how many benchmark photos have a twin v1 trained on, and accuracy on all / clean / contaminated photos. **The clean row is the
  fairest estimate of v1 on unseen field photos.**
- Expect numbers to differ from the README: the benchmark is de-duplicated, restricted to classes with enough photos, and pools PlantDoc and
  PlantWild. A lower honest number with an interval is a stronger result than a higher one that cannot be reproduced.

## Fixes made after the first run on Windows

The first real run exposed three bugs in the copied code, each now fixed and covered by a regression test that fails on the old code:

- **PlantWild labels**: the scanner used the numeric label in `trainval.txt` as an index into the class folders found on disk. That is only
  correct when all 89 folders are extracted; with fewer it crashed, and with a different set it could have silently mislabelled photos. The
  class is now read from the image path (its parent folder), as v1's own scripts do.
- **Paths**: manifest paths were written with the operating system's separator. They are now always forward slashes (portable between Windows
  and Colab), and the tests no longer depend on the platform.
- **Usage log**: the benchmark usage log was written before the splits file was read, so a failed run left a false "benchmark used" entry. It is
  now written only after a successful read.
- **Memory**: the evaluator decoded every photo at full resolution into one list before scoring anything, which exhausted RAM on the validation
  split (multi-megapixel orchard photos). Photos are now streamed one batch at a time.
- **Benchmark coverage**: see step 4; the first freeze used the default inclusion rule and dropped four hard classes. Re-freeze with `--min-train 0`.

## Rules

- The benchmark is **frozen**. Never tune, select or threshold on it. Use the validation split for decisions.
- Do not commit `work\`. Do commit `benchmark\benchmark.csv`, `benchmark\FROZEN.json`, `benchmark\usage_log.txt`, and any report you quote.
- Do not change `SPLIT_SALT` or `PHASH_MAX_DISTANCE` after freezing; that would change the benchmark.
