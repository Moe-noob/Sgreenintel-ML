"""
Where did the benchmark photos go?

The split step silently removes photos. This report accounts for EVERY official test photo of PlantDoc and PlantWild (the
benchmark candidates) so the frozen benchmark can be judged:

  kept                       it is in the frozen benchmark
  dropped: label conflict    a near-duplicate of it carries a different label somewhere in the data, so the whole duplicate
                             group is removed (it may be a mislabelled or ambiguous photo; dropping it can make the benchmark
                             slightly easier, so its size matters)
  dropped: class excluded    its class failed the inclusion rule (too few test photos, or too few field training photos when
                             the split was run with the default --min-train)

It also reports the EFFECTIVE benchmark size: kept photos that are near-copies of each other (same duplicate group) count once,
because near-identical photos make the confidence intervals look narrower than they are.

Reads work/splits.csv and work/classes.json (written by feature1_eval.data.splits).

Usage
  python -m feature1_eval.drops_report
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from feature1_eval import config
from feature1_eval.data import manifest as mf


def analyse(rows, included):
    """rows: dicts from splits.csv (path, source, domain, raw_label, label, official_split, group, split)."""
    included = set(included)
    group_labels = defaultdict(set)
    for r in rows:
        if r["label"]:
            group_labels[r["group"]].add(r["label"])

    cand = [r for r in rows if r["domain"] == "field" and r["official_split"] == "test" and r["label"]]
    per_source, per_class, pair_counts = defaultdict(Counter), defaultdict(Counter), Counter()
    kept = []
    for r in cand:
        if r["split"] == "test":
            status = "kept"
            kept.append(r)
        elif len(group_labels[r["group"]]) > 1:
            status = "dropped: label conflict"
            pair_counts[" vs ".join(sorted(group_labels[r["group"]]))] += 1
        elif r["label"] not in included:
            status = "dropped: class excluded"
        else:
            status = "dropped: other"
        per_source[r["source"]][status] += 1
        per_class[r["label"]][status] += 1

    groups = Counter(r["group"] for r in kept)
    effective = len(groups)
    in_shared = sum(n for n in groups.values() if n > 1)
    return {
        "official_test_photos": len(cand),
        "kept": len(kept),
        "by_status": dict(Counter(s for c in per_source.values() for s, n in c.items() for _ in range(n))),
        "by_source": {k: dict(v) for k, v in sorted(per_source.items())},
        "by_class": {k: dict(v) for k, v in sorted(per_class.items())},
        "top_conflicting_label_pairs": pair_counts.most_common(10),
        "benchmark_effective_size": effective,
        "benchmark_photos_sharing_a_duplicate_group": in_shared,
    }


def to_markdown(res):
    pct = lambda a, b: f"{100 * a / b:.1f}%" if b else "n/a"
    n, k = res["official_test_photos"], res["kept"]
    lines = ["# Where did the benchmark photos go?", "",
             f"- Official test photos (PlantDoc test + PlantWild test, mapped labels): **{n}**",
             f"- Kept in the frozen benchmark: **{k}** ({pct(k, n)})"]
    for s in ("dropped: label conflict", "dropped: class excluded", "dropped: other"):
        c = res["by_status"].get(s, 0)
        lines.append(f"- {s}: **{c}** ({pct(c, n)})")
    lines += ["", f"- Effective benchmark size, counting near-copies once: **{res['benchmark_effective_size']}** of {k} photos "
                  f"({res['benchmark_photos_sharing_a_duplicate_group']} photos share a duplicate group)", "",
              "| Source | Official test | Kept | Label conflict | Class excluded |", "|---|---|---|---|---|"]
    for s, c in res["by_source"].items():
        tot = sum(c.values())
        lines.append(f"| {s} | {tot} | {c.get('kept', 0)} | {c.get('dropped: label conflict', 0)} | {c.get('dropped: class excluded', 0)} |")
    lines += ["", "| Class | Official test | Kept | Label conflict | Class excluded |", "|---|---|---|---|---|"]
    for cls, c in res["by_class"].items():
        tot = sum(c.values())
        lines.append(f"| {cls} | {tot} | {c.get('kept', 0)} | {c.get('dropped: label conflict', 0)} | {c.get('dropped: class excluded', 0)} |")
    if res["top_conflicting_label_pairs"]:
        lines += ["", "Most common label conflicts among dropped test photos:", ""]
        lines += [f"- {pair}: {n}" for pair, n in res["top_conflicting_label_pairs"]]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default=str(config.WORK_DIR))
    a = ap.parse_args(argv)
    work = Path(a.work)
    rows = mf.read(work / "splits.csv")
    included = json.loads((work / "classes.json").read_text(encoding="utf-8"))
    res = analyse(rows, included)
    (work / "drops_report.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    md = to_markdown(res)
    (work / "drops_report.md").write_text(md, encoding="utf-8")
    print(md)
    print(f"-> {work / 'drops_report.md'}")


if __name__ == "__main__":
    main()
