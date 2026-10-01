"""
Step 1+2 follow-up (small): two edits to index.html.

  1. The chart note quotes how our water figures compare with the independent AquaCrop model. After the Rev.1 Kc and
     humidity corrections, the re-run gives (median ratio ours/AquaCrop at the model's pick, 11 cities each):
         tomato 1.03 (was 1.06)   potato 1.14 (was 1.31)   corn up to 1.48 (was 1.53), cold-season, northern cities
     so "about 6% higher for tomato, about 30% higher for potato" becomes "about 3% ... about 14%".
  2. Style the new "Plants per m2" box like the other Track-form fields (it was using the browser default: shorter, grey).

Same safety rules as the other patch scripts: exact-match anchors, backup (.bak), idempotent, --dry-run.
Run from the project root:   python apply_step12b_patch.py [--dry-run]
"""

import sys
from pathlib import Path

DRY = "--dry-run" in sys.argv
PATH = "index.html"
MARKER_NOTE = "about 3% higher for tomato"
EDITS = [
    ("AquaCrop percentages in the chart note",
     "about 6% higher for tomato, about 30% higher for potato (our cycle is longer)",
     "about 3% higher for tomato, about 14% higher for potato (our cycle is longer)", False),
    ("style the plants-per-m2 input",
     '  .search-row input:hover { border-color: var(--gold-dim); }',
     '''  .search-row input:hover { border-color: var(--gold-dim); }

  .field input[type="number"] {
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--paper);
    padding: 10px 12px;
    border-radius: var(--radius-sm);
    font-size: 14px;
    width: 150px;
  }

  .field input[type="number"]:hover { border-color: var(--gold-dim); }''', True),
]


def main():
    path = Path(PATH)
    if not path.exists():
        print(f"{PATH}: NOT FOUND. Run this from the project root.")
        return 1
    raw = path.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in raw else "\n"
    if MARKER_NOTE in raw:
        print(f"{PATH}: already applied.")
        return 0
    text, notes = raw, []
    for label, old, new, optional in EDITS:
        o, n = old.replace("\n", nl), new.replace("\n", nl)
        c = text.count(o)
        if c == 1:
            text = text.replace(o, n)
        elif optional:
            notes.append(f"optional edit '{label}' skipped (anchor found {c} times)")
        else:
            print(f"{PATH}: NOT CHANGED -- '{label}' anchor found {c} times, expected 1.")
            return 1
    if not DRY:
        path.with_name(path.name + ".bak2").write_bytes(raw.encode("utf-8"))
        path.write_bytes(text.encode("utf-8"))
    print(f"{PATH}: {'would be changed' if DRY else 'done (backup index.html.bak2)'}" + ("; " + "; ".join(notes) if notes else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
