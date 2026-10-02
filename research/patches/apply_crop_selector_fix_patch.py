"""
Fixes a bug in apply_crop_selector_patch.py (api/main.py, index.html): run this AFTER that patch.

The bug: the crop dropdown's <option value="..."> was the PRETTY display text ("Corn (Maize)", "Pepper, Bell"), not
the raw key predict_structured(crop=...) looks up. Lower-casing the pretty text to match loses information for any
crop whose key contains punctuation:

    stored key        displayed as      sent back, lower-cased      looked up        match?
    corn_(maize)   -> "Corn (Maize)"  -> "corn (maize)"           -> corn_(maize)   -> NO (space, not underscore)
    pepper,_bell   -> "Pepper, Bell"  -> "pepper, bell"           -> pepper,_bell   -> NO (space, not underscore)

Every other crop (tomato, potato, apple, grape, strawberry) has no punctuation in its key, so the round trip happened
to work for those and the bug only showed up on two of the seven crops -- exactly what was reported.

Fix: GET /predict/crops now returns {"crops": [{"key": ..., "label": ...}, ...]}; the dropdown's <option value> is the
exact key (already lower-case, already matches CROP_CLASS_INDICES, no further transformation needed), and its visible
text is the pretty label. Also: the scan page showed "Can't reach the API" for a 400 (bad request) response, which is
misleading -- the API WAS reached, it rejected the request. A 400 now shows the server's actual reason.

Same safety rules as the other patch scripts: every anchor must match exactly once or that file is left untouched, a
.bak4 copy is saved, running it twice is harmless, --dry-run reports without writing.

Run from the project root, AFTER apply_crop_selector_patch.py has already been applied:
    python apply_crop_selector_fix_patch.py --dry-run
    python apply_crop_selector_fix_patch.py
Then restart the API and hard-refresh (Ctrl+Shift+R) -- the dropdown is rebuilt from the fixed endpoint on load.
"""

import sys
from pathlib import Path

DRY = "--dry-run" in sys.argv

API_MAIN = ("api/main.py", '"key": c, "label"', [
    ("return key + label pairs, not just the pretty text",
     '''    """The crop names /predict accepts in its optional 'crop' field, title-cased for display."""
    return {"crops": [c.replace("_", " ").title() for c in available_crops()]}''',
     '''    """The crops /predict accepts in its 'crop' field. Each entry's "key" is the exact value to send back (it is what
    predict_structured(crop=...) looks up, unchanged by this endpoint); "label" is only for display."""
    return {"crops": [{"key": c, "label": c.replace("_", " ").title()} for c in available_crops()]}''', False),
])

HTML = ("index.html", "option.key", [
    ("dropdown uses the key as the value, the label as the text",
     '''    const { crops } = await res.json();
    const sel = document.getElementById('cropSelect');
    for (const c of crops) sel.insertAdjacentHTML('beforeend', `<option value="${c}">${c}</option>`);''',
     '''    const { crops } = await res.json();
    const sel = document.getElementById('cropSelect');
    for (const option of crops) sel.insertAdjacentHTML('beforeend', `<option value="${option.key}">${option.label}</option>`);''', False),
    ("a 400 shows its real reason instead of the generic unreachable-API message",
     '''  try {
    const res = await fetch(API_BASE + '/predict', { method: 'POST', body: form });
    if (!res.ok) throw new Error();
    const data = await res.json();
    renderScanResult(data);
  } catch {
    scanResult.innerHTML = apiErrorHtml('the scan');
  }''',
     '''  try {
    const res = await fetch(API_BASE + '/predict', { method: 'POST', body: form });
    if (res.status === 400) {
      const err = await res.json().catch(() => ({}));
      scanResult.innerHTML = `<div class="result-band rejected"><span class="band-dot"></span>${err.detail || 'The server could not use this request.'}</div>`;
      return;
    }
    if (!res.ok) throw new Error();
    const data = await res.json();
    renderScanResult(data);
  } catch {
    scanResult.innerHTML = apiErrorHtml('the scan');
  }''', False),
])

PLAN = [API_MAIN, HTML]


def process(path_str, marker, edits):
    path = Path(path_str)
    if not path.exists():
        return f"{path_str}: NOT FOUND. Run this from the project root."
    raw = path.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in raw else "\n"
    if marker in raw:
        return f"{path_str}: already applied."
    if '"crops": [c.replace' not in raw and '{ crops } = await res.json' not in raw:
        return f"{path_str}: the crop-selector patch (apply_crop_selector_patch.py) does not look applied yet. Apply that first."
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
    if path_str.endswith(".py"):
        try:
            compile(text, path_str, "exec")
        except SyntaxError as exc:
            return f"{path_str}: NOT CHANGED -- the edit would break the file ({exc})"
    if not DRY:
        path.with_name(path.name + ".bak4").write_bytes(raw.encode("utf-8"))
        path.write_bytes(text.encode("utf-8"))
    return f"{path_str}: " + ("would be changed" if DRY else f"done (backup {path.name}.bak4)")


def main():
    print("DRY RUN: nothing will be written.\n" if DRY else "")
    for entry in PLAN:
        print(process(*entry))
    print("\nNext: restart the API server and hard-refresh the page (Ctrl+Shift+R).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
