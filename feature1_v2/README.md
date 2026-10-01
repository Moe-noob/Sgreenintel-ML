# Feature 1 v2: plant disease detection for real user photos

A rebuild of Feature 1 (the leaf-disease CNN). The aim is accuracy on **real phone photos**, coverage of **Feature 2's Saudi crops**, and **useful advice in Arabic and English**. It follows the agreed plan step by step. v1 (`training/`, `models/cnn/`, `care/`, `/predict` in `api/main.py`) is untouched and stays the baseline. **To remove v2, delete this folder.**

What it does, in one request:

1. The user sends 1–3 photos of the same plant. Picking the crop is optional (Feature 2 already knows it).
2. Optionally, leaves are detected and each one is classified, with test-time augmentation.
3. If the crop is known, only that crop's conditions compete (the **crop selector**).
4. Calibrated confidence decides the outcome: **accept**, **retake** (low confidence) or **not a supported leaf**.
5. The response adds:
   - **advice** (symptoms to confirm, look-alikes, what to do now, cultural control, chemical control by FRAC/IRAC group with the MEWA label rule, prevention, when to call extension, sources);
   - **weather risk** from published rules;
   - a **season note** from Feature 2's crop calendar.

```bash
pip install -r feature1_v2/requirements.txt
python -m unittest discover -s feature1_v2/tests -t .      # 36 tests, CPU, synthetic data (~15 s)
python -c "from feature1_v2.advice import kb; import json; print(json.dumps(kb.advice_for('tomato__late_blight','ar'), ensure_ascii=False, indent=1))"
```

**Status:** all code is written and tested; **the model is not trained yet**. Training needs a GPU and the datasets, which were not reachable from the build environment. [`RUNBOOK.md`](RUNBOOK.md) gives the exact Colab steps, from download to the one-time final benchmark run, with two decision gates on the way. Until then, no v2 accuracy is claimed.

**Full audit trail** ([`DOCUMENTATION.md`](DOCUMENTATION.md)) covers:
- what changed from v1 and why;
- problems found in v1 (stale evaluation JSONs, the PlantDoc test set reused for model selection, no field validation set, no cross-dataset duplicate check, fixed thresholds);
- every source, every validation, and the limitations.

| Folder / file | What |
|---|---|
| `data/` | manifest, duplicate detection, frozen benchmark splits |
| `train.py`, `calibrate.py`, `evaluate.py`, `compare.py`, `distill.py` | training and measurement |
| `predictor.py`, `detector/` | prediction rules, leaf detector |
| `advice/` | Arabic/English knowledge base, weather rules, season note |
| `api_router.py`, `demo.html` | `/v2/disease/*` endpoints (not wired in by default), demo upload page |
