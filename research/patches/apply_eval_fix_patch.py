"""
Fix the reproducibility problems found in v1's real-world evaluation scripts (training/evaluate_plantdoc.py,
training/evaluate_plantwild.py, training/model_loader.py).

What was wrong
  * Both scripts always evaluated "the first checkpoint that exists" in model_loader's priority list, threw the checkpoint
    name away, and wrote nothing about it into the JSON. Which model a JSON describes could not be told from the file.
    (The committed JSONs, 67.03% on PlantDoc and 62.66% on PlantWild, match the README's v8p2 row, not the production v6p2.)
  * Both scripts hard-coded plantvillage_test_accuracy = 90.29 (v2's number) and computed domain_gap from it, so every
    checkpoint reported v2's baseline.
  * Every run overwrote the same JSON file.

What this patch changes
  * --checkpoint PATH   evaluates exactly that file (default unchanged: the best available checkpoint)
  * --pv-acc X          the PlantVillage accuracy of THAT checkpoint, for the domain-gap line; without it the gap is not computed
                        (the hard-coded 90.29 is gone)
  * each JSON records "checkpoint": file name, size, SHA-256 (first 16 hex) and modification date
  * each run also writes models/cnn/<plantdoc|plantwild>_evaluation_<checkpoint name>.json next to the usual file

Same safety rules as the other patch scripts: every anchor must match exactly once or that file is left untouched, a .bak copy is
saved, running it twice is harmless, --dry-run reports without writing.

Run from the project root:
    python apply_eval_fix_patch.py --dry-run
    python apply_eval_fix_patch.py
Then, for the production model:
    python training\\evaluate_plantdoc.py  --checkpoint models\\cnn\\mobilenetv2_sgreenintel_v6p2.pth --pv-acc 95.44
    python training\\evaluate_plantwild.py --checkpoint models\\cnn\\mobilenetv2_sgreenintel_v6p2.pth --pv-acc 95.44
"""

import sys
from pathlib import Path

DRY = "--dry-run" in sys.argv

HELPERS = '''from model_loader import load_best_model, load_model_from_checkpoint, checkpoint_fingerprint

CHECKPOINT_USED = None   # set by build_and_load_model(); recorded in the results JSON


def _pv_acc():
    """PlantVillage accuracy of the evaluated checkpoint, only when given with --pv-acc X. (It used to be a hard-coded
    90.29, which is v2's number, so every checkpoint reported v2's domain gap.)"""
    if "--pv-acc" in sys.argv:
        return float(sys.argv[sys.argv.index("--pv-acc") + 1])
    return None'''

NEW_BODY = '''    # --checkpoint PATH evaluates exactly that file; otherwise the best available checkpoint, as before.
    global CHECKPOINT_USED
    if "--checkpoint" in sys.argv:
        path = Path(sys.argv[sys.argv.index("--checkpoint") + 1])
        model, class_names = load_model_from_checkpoint(path)
        print(f"Using model: {path.name}")
    else:
        model, class_names, path = load_best_model()
    CHECKPOINT_USED = path
    return model, class_names'''

FINGERPRINT_FN = '''    return model, class_names, path


def checkpoint_fingerprint(path):
    """Name, size, SHA-256 (first 16 hex) and modification date of a checkpoint file, for evaluation records."""
    import datetime
    import hashlib
    from pathlib import Path as _Path
    p = _Path(path)
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return {"file": p.name, "bytes": p.stat().st_size, "sha256_16": h.hexdigest()[:16],
            "modified": datetime.datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds")}'''

MODEL_LOADER = ("training/model_loader.py", "def checkpoint_fingerprint", [
    ("fingerprint helper", "    return model, class_names, path", FINGERPRINT_FN, False),
])

PLANTDOC = ("training/evaluate_plantdoc.py", "CHECKPOINT_USED", [
    ("imports and helpers", "from model_loader import load_best_model", HELPERS, False),
    ("explicit checkpoint",
     "    model, class_names, _ = load_best_model()\n    return model, class_names", NEW_BODY, False),
    ("domain gap printout",
     r'''    print(f"\nFor comparison: PlantVillage held-out test set accuracy: 90.29%")
    print(f"Domain gap (lab vs real-world): {90.29 - overall_acc:.2f} percentage points")''',
     r'''    pv_acc = _pv_acc()
    if pv_acc is not None:
        print(f"\nFor comparison: PlantVillage held-out test set accuracy of this checkpoint: {pv_acc}%")
        print(f"Domain gap (lab vs real-world): {pv_acc - overall_acc:.2f} percentage points")
    else:
        print("\nNo PlantVillage accuracy given (pass --pv-acc X): domain gap not computed.")''', False),
    ("JSON fields",
     '        "plantvillage_test_accuracy": 90.29,\n        "domain_gap": 90.29 - overall_acc,',
     '        "plantvillage_test_accuracy": pv_acc,\n        "domain_gap": (pv_acc - overall_acc) if pv_acc is not None else None,\n'
     '        "checkpoint": checkpoint_fingerprint(CHECKPOINT_USED) if CHECKPOINT_USED else None,', False),
    ("per-checkpoint copy",
     r'''    print(f"\nResults saved to: {out_path}")''',
     r'''    print(f"\nResults saved to: {out_path}")
    if CHECKPOINT_USED:
        copy_path = out_path.with_name(f"plantdoc_evaluation_{Path(CHECKPOINT_USED).stem}.json")
        copy_path.write_text(json.dumps(results, indent=2))
        print(f"Also saved: {copy_path}")''', False),
])

PLANTWILD = ("training/evaluate_plantwild.py", "CHECKPOINT_USED", [
    ("import sys", "import json\nfrom pathlib import Path", "import sys\nimport json\nfrom pathlib import Path", False),
    ("imports and helpers", "from model_loader import load_best_model", HELPERS, False),
    ("explicit checkpoint",
     "    model, class_names, _ = load_best_model()\n    return model, class_names", NEW_BODY, False),
    ("PlantVillage constant", "    pv_baseline = 90.29", "    pv_baseline = _pv_acc()", False),
    ("domain gap printout",
     r'''    print(f"\nFor comparison: PlantVillage held-out test accuracy: {pv_baseline}%")
    print(f"Domain gap (lab vs PlantWild): {pv_baseline - overall_acc:.2f} pp")''',
     r'''    if pv_baseline is not None:
        print(f"\nFor comparison: PlantVillage held-out test accuracy of this checkpoint: {pv_baseline}%")
        print(f"Domain gap (lab vs PlantWild): {pv_baseline - overall_acc:.2f} pp")
    else:
        print("\nNo PlantVillage accuracy given (pass --pv-acc X): domain gap not computed.")''', False),
    ("JSON fields",
     '        "plantvillage_test_accuracy": pv_baseline,\n        "domain_gap": pv_baseline - overall_acc,',
     '        "plantvillage_test_accuracy": pv_baseline,\n        "domain_gap": (pv_baseline - overall_acc) if pv_baseline is not None else None,\n'
     '        "checkpoint": checkpoint_fingerprint(CHECKPOINT_USED) if CHECKPOINT_USED else None,', False),
    ("per-checkpoint copy",
     r'''    print(f"\nResults saved to: {out_path}")''',
     r'''    print(f"\nResults saved to: {out_path}")
    if CHECKPOINT_USED:
        copy_path = out_path.with_name(f"plantwild_evaluation_{Path(CHECKPOINT_USED).stem}.json")
        copy_path.write_text(json.dumps(results, indent=2))
        print(f"Also saved: {copy_path}")''', False),
])

PLAN = [MODEL_LOADER, PLANTDOC, PLANTWILD]


def process(path_str, marker, edits):
    path = Path(path_str)
    if not path.exists():
        return f"{path_str}: NOT FOUND. Run this from the project root."
    raw = path.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in raw else "\n"
    if marker in raw:
        return f"{path_str}: already applied."
    text, failed = raw, []
    for label, old, new, optional in edits:
        o, n = old.replace("\n", nl), new.replace("\n", nl)
        c = text.count(o)
        if c == 1:
            text = text.replace(o, n)
        elif not optional:
            failed.append(f"'{label}' (anchor found {c} times, expected 1)")
    if failed:
        return f"{path_str}: NOT CHANGED -- " + "; ".join(failed)
    try:
        compile(text, path_str, "exec")
    except SyntaxError as exc:
        return f"{path_str}: NOT CHANGED -- the edit would break the file ({exc})"
    if not DRY:
        path.with_name(path.name + ".bak").write_bytes(raw.encode("utf-8"))
        path.write_bytes(text.encode("utf-8"))
    return f"{path_str}: " + ("would be changed" if DRY else f"done (backup {path.name}.bak)")


def main():
    print("DRY RUN: nothing will be written.\n" if DRY else "")
    for entry in PLAN:
        print(process(*entry))
    return 0


if __name__ == "__main__":
    sys.exit(main())
