# Feature 1 v2: full documentation and audit trail

This document records everything that is new or changed compared with Feature 1 v1 (the CNN in `training/`, `models/cnn/`, `care/`), every problem found in v1, where each piece of knowledge came from, and how each part was validated. It is meant to be checked against v1 line by line.

**Status in one paragraph.** All code for the agreed plan is written and tested (37 automated tests, all passing). The data pipeline, frozen benchmark, training, calibration, evaluation, v1 baseline adapter, predictor, leaf detector tools, advice knowledge base, weather rules, season note, API and demo page all work. **No real model has been trained yet.** The build environment had no GPU and could not download the datasets (Hugging Face, Kaggle, Mendeley and the dataset hosts were blocked). So this document contains **no v2 accuracy numbers**, and none are claimed. They come from running [`RUNBOOK.md`](RUNBOOK.md) on Colab or a borrowed GPU; section 7 has the empty result tables to fill in.

To remove v2, delete `feature1_v2/`. Nothing outside the folder imports it. `api/main.py`, `index.html`, `training/` and `care/` are unchanged.

---

## 1. Summary of what v2 adds

| Area | v1 | v2 |
|---|---|---|
| Test set | PlantDoc test (370 images), also used to choose between v4p2 and v8p2; PlantWild test | Frozen benchmark of field photos only, de-duplicated against training and validation, never used for choices (code-enforced, usage logged) |
| Model selection | on the PlantDoc test set | on a separate field **validation** split (macro-F1) |
| Reported numbers | single accuracy | accuracy and macro-F1 with 95 % bootstrap intervals; per crop and per class; ECE; accuracy on accepted photos vs share accepted; paired-bootstrap v1 vs v2 comparison |
| Classes | 35 (7 crops: apple, corn, grape, pepper, potato, strawberry, tomato) | Taxonomy of 66 conditions over 16 crops (+ "unsupported"); a class ships only if it has ≥150 field training photos and ≥30 held-out photos |
| Feature 2 crops covered | tomato, potato, sweet pepper, (sweet) corn | plus cucumber, squash/zucchini, eggplant, lettuce, cabbage, cauliflower, broccoli, green bean, garlic, and melon/okra/onion when a field dataset is added |
| Backbone | MobileNetV2 (2018), 384 px | choice of DINOv2-S/B, ConvNeXt-V2-T, EfficientNetV2-S, SigLIP-B (MobileNetV3 for distillation), picked by validation |
| Training recipe | PlantVillage + field fine-tune | field-weighted class-balanced sampling, phone-camera augmentation, background swap, CutMix, label smoothing, EMA, layer-wise LR decay |
| Crop knowledge | model must pick among all classes | **crop selector**: the user (or Feature 2) gives the crop, and only that crop's conditions compete |
| Photo input | one photo | 1–3 photos of the same plant, optional leaf detection, test-time augmentation |
| Rejection | fixed thresholds (confidence 0.70, normalised entropy 0.40) | temperature-scaled confidence with thresholds chosen on validation for a target accuracy; energy-score OOD plus an "unsupported" class |
| Advice | 6 category texts (EN only), "consult extension for approved products" | 66 condition entries + 14 category templates in **Arabic and English**: symptoms to confirm, key distinguishing sign, look-alikes, steps, cultural control, chemical **mode-of-action groups** only plus the MEWA label rule, prevention, when to contact extension, sources on every entry |
| Context | none | weather risk from published rules (late blight, grape downy mildew); season-plausibility note from Feature 2's crop calendar |

## 2. Sources

### 2.1 Datasets

All public. Licences must be confirmed on each dataset page before any non-research use.

| Dataset | Use in v2 | Reference / licence |
|---|---|---|
| PlantWild v1 (89 classes, 18,542 images; official split in `trainval.txt`) | train (domain 1), validation (domain 2), benchmark (domain 0) | Wei et al. (2024), ACM MM, arXiv:2408.03120; research use |
| PlantDoc (classification) | train, benchmark (official test) | Singh et al. (2020), CODS-COMAD, doi:10.1145/3371158.3371196; CC BY 4.0 |
| PlantDoc (object detection boxes) | leaf detector only | same authors, github.com/pratikkayal/PlantDoc-Object-Detection-Dataset |
| v1 `data/processed_v2` (PlantVillage, fgvc8 Plant Pathology 2021, cds, sms) | **training only** (v1 used its splits for choices, so none of it may enter the benchmark) | Hughes & Salathé (2015); Thapa et al. (2021); as assembled by `training/prepare_data_v2.py` |
| Cucumber field dataset | optional source (template) | Data in Brief (2023), PMC10338290 |
| Real-field eggplant leaf diseases | optional source (template) | Mendeley Data pwvpb658rm (also jv6tnm4t5c) |
| Non-plant photos (e.g. COCO val2017) | optional, for "not a supported leaf" | Lin et al. (2014); CC BY 4.0 annotations, Flickr image terms |

### 2.2 Methods

| Method | Where | Reference |
|---|---|---|
| Perceptual hash (DCT pHash), Hamming ≤ 6 | `data/dedupe.py` | Zauner (2010), *Implementation and benchmarking of perceptual image hash functions* |
| DINOv2 | `models.py` | Oquab et al. (2023), arXiv:2304.07193 |
| ConvNeXt-V2 | `models.py` | Woo et al. (2023), CVPR |
| EfficientNetV2 | `models.py` | Tan & Le (2021), ICML |
| SigLIP | `models.py` | Zhai et al. (2023), ICCV |
| Layer-wise LR decay | `models.param_groups` | Clark et al. (2020) ELECTRA; Bao et al. (2022) BEiT |
| CutMix | `train.py` | Yun et al. (2019), ICCV |
| Label smoothing | `train.py` | Szegedy et al. (2016), CVPR |
| EMA of weights | `train.py` | Polyak & Juditsky (1992) |
| Temperature scaling, ECE | `calibrate.py`, `metrics.py` | Guo et al. (2017), ICML |
| Energy OOD score | `inference.energy` | Liu et al. (2020), NeurIPS |
| Bootstrap and paired-bootstrap CIs | `metrics.py` | Efron & Tibshirani (1993) |
| Knowledge distillation | `distill.py` | Hinton, Vinyals & Dean (2015), arXiv:1503.02531 |
| YOLOv8 detector | `detector/` | Jocher et al., Ultralytics (2023) |

### 2.3 Advice and weather knowledge

All bibliography entries are in `advice/sources.py`. Each advice entry lists the keys it relies on.
- **Symptoms and look-alikes:** APS disease compendia (tomato, cucurbits, potato, grape, corn, apple and pear, strawberry, lettuce, brassica, bean, onion and garlic, pepper).
- **Management:** UC IPM Pest Management Guidelines per crop, and FAO Plant Production and Protection Paper 217 (greenhouse GAP, Mediterranean climate).
- **Chemical groups:** FRAC Code List (fungicides) and IRAC MoA Classification (insecticides and acaricides).
- **Products, doses and pre-harvest intervals:** deliberately **not** given. The text tells the user to use a product registered by MEWA and follow its label.
- **Weather rules:**
  - Hutton criteria: Dancey, Skelsey & Cooke (2017), EuroBlight / PAGV Special Report 18.
  - "Three tens" (10-10-24) rule: Baldacci (1947), reviewed in Gessler, Pertot & Perazzolli (2011), *Phytopathologia Mediterranea* 50: 3–44.

**Not verified online:** The URLs and page numbers in `advice/sources.py` could not be opened from the build environment (no internet). They are well-known publisher landing pages, but each must be checked during review. The Hutton page numbers are marked "to be checked" in the file.

## 3. Findings about v1

### 3.1 Things that are wrong or out of date

1. **The committed evaluation JSONs are stale.**
   - `models/cnn/plantdoc_evaluation.json` reports 67.0 % on PlantDoc and `plantwild_evaluation.json` reports 62.7 % on PlantWild, both with PlantVillage at 90.29 %. 90.29 % is the **v2** model's PlantVillage figure in the README table.
   - The README reports v6p2 at 95.44 / 70.81 / 63.79.
   - So the JSONs come from an older model, and they do not support the README numbers.
2. **The PlantDoc test set was used for model selection.**
   - The README's model-evolution table chooses between v4p2…v8p2 by their PlantDoc test accuracy (e.g. v7p2 "regression", v8p2 "worse real-world").
   - So the 370-image PlantDoc test set is no longer a held-out test.
   - With 370 images, a 95 % interval on ~70 % accuracy is about ±4.7 points. The v5p2 → v6p2 difference (70.27 → 70.81) is 2 images, well within noise.
3. **No real-photo validation set existed.** PlantWild's official validation split (domain 2) was never used, so there was nothing except the test sets to choose on. v2 uses it as the field validation split.
4. **No duplicate check between datasets.** PlantDoc and PlantWild were both collected from web image search, and v1 trains on one while testing on the other, and vice versa. Identical or near-identical photos across train and test would inflate real-world accuracy. v2 hashes everything and removes leaks before freezing the benchmark (`split_report.json` records how many).
5. **Crop coverage versus Feature 2.**
   - v1's 7 crops include only 4 of Feature 2's crops: tomato, potato, sweet pepper and corn (v1 covers maize; Feature 2 lists sweet corn, the same species).
   - The plan summary said "3 of 22", which undercounted corn. Feature 2 v2 lists 22 distinct crop names over 24 rows.
6. **Fixed rejection thresholds.** The 0.70 confidence and 0.40 normalised-entropy cut-offs (`training/predict_api.py`) were not derived from a calibration set. The softmax of an uncalibrated network is usually over-confident (Guo et al. 2017), so "70 %" did not mean 70 % correct. v2 fits a temperature and picks thresholds for a stated accuracy on the validation split.

### 3.2 Things v1 gets right (kept in v2)

- **Official splits.** PlantWild train/test use follows the official `trainval.txt` split (domain 1 for training, domain 0 for test). v2 keeps these splits.
- **Label mappings.** The PlantDoc and PlantWild mappings in `training/finetune_combined.py` are correct for the 35 classes. v2's `taxonomy.PLANTDOC`, `taxonomy.PLANTWILD` and `taxonomy.LEGACY_35` reproduce them and extend them to the new crops.
- **Advice framed as a knowledge base.** v1 presents advice as a knowledge base, not as model output. The care texts send users to extension services for products. v2 keeps both principles.
- **Fixed v1 preprocessing.** v1's square resize to 384 px is reproduced exactly by the legacy adapter (`legacy.py`), so v1 is evaluated as it runs in production.

## 4. Design

### 4.1 Data pipeline (plan Step 1)

1. `data/manifest.py`
   - Scans every enabled source (`sources.json`) and maps each raw label to `crop__condition`.
   - Marks each image as field or lab. PlantVillage files are recognised by `___` in the file name; everything else is field.
2. `data/dedupe.py`
   - Computes a 64-bit DCT perceptual hash per image.
   - Groups images within Hamming distance 6 (union-find; exact by the pigeonhole principle on 8-bit chunks, so no pair is missed).
3. `data/splits.py`
   - Lab images are used for training only.
   - Official test and validation splits are kept.
   - Field training images get a stable hash-based validation share.
   - Sources with no official split are split by duplicate group, so near-duplicates stay together.
   - **Leakage:** if a duplicate group spans splits, the test member is kept and the train/validation members are dropped (validation is likewise protected from training).
   - **Label conflict:** groups whose members carry different labels are dropped entirely.
   - **Inclusion rule:** a class needs ≥150 field training images and ≥30 test images.
   - **Freeze:** `benchmark/benchmark.csv` and `FROZEN.json` (SHA-256 of the sorted path/label list).
   - **Guard:** `load_split("test")` raises `PermissionError` without `final=True`, and appends every final use to `benchmark/usage_log.txt`.

### 4.2 Training and evaluation (plan Step 3)

- **`train.py`**
  - Selects on validation macro-F1, so rare diseases count as much as common ones.
  - Two modes: linear probe (frozen backbone) or full fine-tune with layer-wise LR decay.
  - The sampler balances classes and weights field photos ×3, so the much larger lab (PlantVillage) set does not dominate.
  - Augmentations: phone-camera simulation (blur, JPEG quality, white balance, exposure, framing) and background swap (lab leaf pasted onto field backgrounds).
- **`calibrate.py`**
  - Fits a temperature on the validation logits.
  - Chooses thresholds for both modes (auto and crop given) for a target accuracy on accepted photos.
  - Sets the energy threshold at the 95th percentile of supported validation photos.
- **`evaluate.py`**
  - Reports everything in section 1 for a v2 checkpoint or the v1 model.
  - For v1 it also reports the share of photos whose class v1 cannot output.
- **`compare.py`**
  - Paired bootstrap on photos both models can label.
  - Prints "B better", "A better" or "no clear difference".

### 4.3 Prediction (plan Steps 2, 3.3–3.5)

`predictor.py` handles a request in this order:
1. **Views.** Optionally detect leaves (`detector/`) and classify each leaf crop as well as the whole photo. Each view gets TTA (flips, averaged log-probabilities).
2. **"Not a supported leaf".** Checked on the whole photos (unsupported class on top, or energy above threshold), and only when the user did not name the crop.
3. **Crop selector.** If the crop is given, other crops' classes are masked.
4. **Aggregation.**
   - "Mean" (average log-probabilities): used for several photos of one plant.
   - "Worst": used when leaves were detected. A disease seen with confidence above the threshold on any leaf wins over "healthy".
5. **Low-confidence rejection** at the calibrated threshold for that mode. The retake advice is in AR/EN.
6. **Look-alike flag** when the top-two gap is below 0.20.

The advice layer (`service.enrich`) never changes the prediction.

### 4.4 Advice (plan Step 4)

- **Category templates** (`advice/categories.py`): 14 templates, so shared management text is written once:
  - healthy;
  - fungal leaf spot; oomycete; powdery mildew; rust; bacterial;
  - virus: whitefly-borne, aphid-borne, contact-borne, planting-material-borne;
  - mites; bacterial wilt with beetle vector; smut; grapevine trunk disease.
- **Why oomycetes have their own template:** late blight and downy mildews are not true fungi. Several common fungicide groups do not control them, and generic "fungicide" advice would be wrong for them.
- **Entries** (`advice/entries.py`): one per condition, giving:
  - cause (scientific name);
  - symptoms to confirm (AR/EN);
  - one **key sign** (used by the look-alike helper);
  - look-alikes (same crop only, checked by test);
  - a disease-specific note where needed. Examples: TYLCV whitefly focus; ToBRFV reporting; downy mildew of cucumber not being a class; LMV seed testing.
- **Look-alike helper:** when the model is torn between two conditions, it shows each one's key sign, so the user can check the leaf instead of trusting a coin flip.
- **No product names or doses** (checked by test). Every chemical section ends with the MEWA registration and label rule.
- **Review status:** `draft`. The texts are condensed from the cited references but have not yet been reviewed by a plant pathologist or MEWA extension specialist. Do that before release.

### 4.5 Weather risk and season note (plan Step 4)

- **`advice/weather_risk.py`** uses the Open-Meteo hourly forecast, the same service the tracker uses. Only two rules are implemented, both published:
  - **Hutton criteria** for late blight: two consecutive days, each with Tmin ≥ 10 °C and ≥ 6 h of RH ≥ 90 %.
  - **Three tens rule** for grape downy mildew: ≥ 10 mm rain within 24 h at ≥ 10 °C, with shoots ≥ 10 cm stated as an assumption.
  - Each result carries its caveat (e.g. Hutton was built for outdoor potato in Great Britain; greenhouse humidity can be higher).
  - Every other condition returns "no published rule implemented". **No rules were invented.**
- **`advice/season_check.py`** uses Feature 2 v2.
  - A date is "in season" if it falls in the growing period of a **low-stress** sowing day: a candidate sowing day whose temperature-stress degree-days are in the lowest third for that place.
  - The lowest-third cut-off is a heuristic. "Candidate" alone would say lettuce grows in Riyadh in July.
  - The result is a note only, and it mentions greenhouses and off-season planting.

### 4.6 Integration (plan Step 5)

- **`api_router.py`** adds `/v2/disease/crops`, `/v2/disease/predict` and `/v2/disease/advice/{label}`.
  - `predict` accepts 1–3 photos, an optional crop, `lang` (en/ar), and an optional city or lat/lon.
  - The router is not wired into `api/main.py`. RUNBOOK step 9 gives the two lines to add.
- **`demo.html`** is a standalone page showing the new upload flow:
  - crop selector, add-photo (up to 3), Arabic RTL / English;
  - full advice, look-alike help, weather risk, season note and sources.
  - It was checked in headless Chromium at phone width (420 px) in both languages against a stub model: no script errors and no horizontal overflow.
  - `index.html` itself was not changed. The same blocks can be ported into its scan screen once a trained model exists.

## 5. Validation

| What | How | Result |
|---|---|---|
| Label mapping | every PlantWild (89 + 3 renamed), PlantDoc (28) and v1 (35) label maps to a taxonomy label, "unsupported", or a deliberate exclusion | test passes |
| Duplicate detection | synthetic re-encoded / resized copies found; planted cross-split leak removed; label-conflict group dropped | tests pass |
| Benchmark guard | test split refused without `final`; final use logged; re-freeze with changed data refused | tests pass |
| Metrics | accuracy and macro-F1 cross-checked against scikit-learn | identical |
| End-to-end | synthetic dataset → manifest → dedupe → splits → train (tiny ViT, CPU) → calibrate → evaluate val/test → fake v1 checkpoint through the legacy adapter → paired compare → distillation | learns the task (val accuracy > 0.6, student > 0.4); all files produced |
| Predictor rules | stub model with fixed logits per photo colour | each rule checked: unsupported and energy rejection, crop selector resolving cross-crop confusion, invalid crop, look-alike, multi-photo mean, worst-leaf aggregation, default calibration |
| Detector tools | box padding / clipping / ordering; PlantDoc CSV → YOLO conversion with exact expected numbers; benchmark images excluded from detector training only | tests pass |
| Advice KB | every taxonomy label has an entry; AR and EN for every field (Arabic script checked); every source key resolves; look-alikes same crop; oomycete / bacterial categories correct for named diseases; no doses or product units | `kb.validate()` empty; tests pass |
| Weather rules | synthetic forecasts at and just outside each threshold (Tmin 8 vs 12 °C; 5 vs 8 h humid; one vs two days; 8 vs 12 mm rain) | correct high / low in every case |
| Season note | lettuce in Riyadh in January in season, July unusual; grape not available | test passes |
| Resume after disconnect | train 2 epochs, re-run asking for 4: continues at epoch 3, history 1–4; re-running a finished run does nothing | test passes |
| Colab notebook | `python -m feature1_v2.colab.dry_run`: builds a fake Drive folder with the same 5 files the guide asks for (zips with top folders as Windows/Mac make them, GitHub-style code zip, fake v1 model), executes every notebook box on CPU, deletes the local disk mid-training to simulate a disconnect, then runs everything again | every box prints ✅; training resumes at the saved epoch; data preparation is skipped the second time; `results_to_send.zip` produced |
| API | FastAPI TestClient: crops list, AR prediction with advice, invalid crop 400, more than 3 photos 400, non-image 400, advice 404 | tests pass |

Run: `python -m unittest discover -s feature1_v2/tests -t .` (37 tests) and `python -m unittest discover feature2_v2/tests` (29 tests, unchanged by this work).

**What these tests do not show:** anything about accuracy on real photos. That is section 7, after the runbook.

## 6. Development log (problems met while building)

1. **Lab-photo test checked the whole path.** The test that tells lab from field photos checked `___` in the whole path. v1's folder names (`Tomato___Late_blight`) contain it too, which would have marked every legacy field photo as lab. Fixed: only the file name is checked.
2. **Planted leak dropped for the wrong reason.** The leak planted in the pipeline test had a different label from its duplicate, so it was correctly dropped as a label conflict rather than as a leak. The test now plants a same-label leak, and the conflict case is tested separately.
3. **Test attribute name clash.** A test class attribute named `run` shadowed `unittest.TestCase.run` and crashed the runner. Renamed to `run_dir`.
4. **`compare.py` compared nothing.** It inferred "classes the model knows" from the model's predictions, which gave 0 common photos for v1. `evaluate.py` now writes an explicit `label_known_to_model` column.
5. **Rejection reasons were English only.** The demo showed English rejection reasons in Arabic mode. Rejection reasons are now `{en, ar}`.
6. **Network errors overflowed the page.** A failed forecast put the raw network error into the user message, which overflowed the page at phone width. Add-on errors now give a short translated message and keep the raw error in an `error` field.
7. **Season check was too permissive.** It first used every candidate sowing day and said lettuce is in season in Riyadh all year. It was changed to the lowest-third-stress rule (section 4.5).
8. **Colab notebook winner tie-break.** On a tie in "crop known" accuracy, the notebook picked the first model in the list rather than the stronger one (found in the dry run). It now breaks ties on overall accuracy, then macro-F1.
9. **Free Colab loses its disk on disconnect.** The frozen benchmark lived inside the code folder and training could not continue. Fixed: `F1V2_BENCHMARK_DIR` puts the benchmark on Drive, and `train.py --resume` continues from `last.pt` (saved atomically every epoch).

## 7. Results (to fill in from RUNBOOK steps 5–10)

| | v1 (v6p2) | v2 best | v2 − v1 (95 % CI, paired) |
|---|---|---|---|
| Field validation accuracy, auto | | | |
| Field validation accuracy, crop given | | | |
| Benchmark accuracy, auto (final, once) | | | |
| Benchmark accuracy, crop given (final, once) | | | |
| Benchmark macro-F1 | | | |
| Share of benchmark photos v1 cannot label | | n/a | |
| Accuracy on accepted photos / share accepted (crop given) | | | |
| ECE before → after temperature scaling | | | |
| Unsupported photos rejected | | | |

Ablation table (validation, best backbone): background swap, CutMix, field weight, EMA, resolution, TTA, leaf detector. Decision gates: gate 1 (backbone beats v1, interval above 0) and gate 2 (detector gain interval above 0).

## 8. Limitations and open items

- **No trained model yet.** See the status at the top.
- **Not Saudi photos.** Real-photo data is public web and field imagery, mostly not from Saudi Arabia. Saudi farm photos (even a few hundred, labelled by an extension specialist) would be the most valuable addition to the benchmark.
- **Crops not covered yet.** Melon, okra and onion have no class until a real-field dataset with enough photos is added. Feature 2 crops with no public disease photo sets (mulukhiyah, radish, lentil, spinach, carrot) are not covered.
- **Drafted advice.** The advice texts are drafts until expert review. Citations need online verification (section 2.3).
- **Weather rules.**
  - Developed for other climates (Great Britain; European vineyards).
  - Use outdoor forecasts, which can understate greenhouse humidity.
  - Only two diseases have a rule.
- **Season note.** Uses long-term mean climate, and its low-stress cut-off is a heuristic.
- **Severity estimation** (plan Step 4, optional) is not implemented: no public lesion-mask dataset was found for most of the target crops.
- **Grad-CAM spot checks** (plan verification) need a trained model. v1's `training/gradcam.py` can be pointed at a v2 checkpoint via `models.load_checkpoint`.

## 9. File map

| Path | Purpose |
|---|---|
| `config.py`, `taxonomy.py`, `sources.json` | settings, unified labels, dataset list |
| `data/manifest.py`, `data/dedupe.py`, `data/splits.py`, `data/dataset.py` | pipeline, de-duplication, frozen splits, training data and augmentation |
| `models.py`, `train.py`, `distill.py` | backbones, training, distillation |
| `inference.py`, `calibrate.py`, `evaluate.py`, `compare.py`, `metrics.py`, `legacy.py` | inference helpers, calibration, reports, paired comparison, v1 adapter |
| `predictor.py`, `detector/` | prediction service, leaf detector and its decision gate |
| `advice/` | knowledge base, sources, weather rules, season note |
| `service.py`, `api_router.py`, `demo.html` | combined response, FastAPI router, demo page |
| `benchmark/` | frozen benchmark (created by RUNBOOK step 4) and its usage log |
| `tests/` | 37 tests |
| `colab/` | beginner GUIDE.md, click-through Colab notebook (and its builder), fake-drive dry run |
| `RUNBOOK.md`, `README.md`, `requirements.txt` | how to run, overview, extra dependencies |
