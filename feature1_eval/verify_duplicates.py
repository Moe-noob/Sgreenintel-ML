"""
Geometric verification of near-duplicate candidates, plus an audit of label conflicts and a clean-training exclusion list.

WHY THIS EXISTS. data/dedupe.py groups images whose 64-bit perceptual hashes differ in <= 6 bits, TRANSITIVELY (union-find). A manual
review of 24 of the benchmark's dropped "label conflict" photos found that 22 were genuinely the SAME photograph filed in two or more
class folders (7 of them under different CROPS), but 2 were false matches: a spotted strawberry leaf and a plain apple leaf sit at
pHash distance 6 and landed in one group, and a chain of plain-background leaves produced a 4-label group. pHash is a coarse
fingerprint and cannot tell such pairs apart; a feature-matching check can: the two false pairs had 0-1 geometrically consistent
feature matches (ORB + RANSAC), the 22 real duplicates had 29-1,500.

WHAT IT DOES (it never edits dedupe.py, splits.py or the frozen benchmark -- changing them would change the benchmark's fingerprint and
invalidate every comparison made so far; this is a separate layer):
  1. For every pHash group that has more than one label, or contains a frozen-benchmark photo, compares its members pairwise with ORB
     feature matching and keeps only pairs with enough geometrically consistent matches: at least INLIER_THRESHOLD AND at least
     MIN_INLIER_FRACTION of the poorer image's keypoints (or, for textureless images ORB cannot judge, an identical hash).
  2. Rebuilds the groups from those VERIFIED pairs only, which dissolves chains of unrelated images.
  3. Writes work/duplicate_audit.md/.json: how many of the dropped conflicts are real, how many cross crops, which label pairs.
  4. Writes work/clean_train_exclusions.csv: every non-benchmark image that sits in a verified conflict (same photo, different labels)
     or duplicates a frozen-benchmark photo. train_specialist.py --exclude uses it to train on cleaner data.

Needs OpenCV:  pip install opencv-python

Usage (after manifest, dedupe and splits have run):
    python -m feature1_eval.verify_duplicates
"""

import argparse
import csv
import itertools
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

from feature1_eval import config

INLIER_THRESHOLD = 15            # floor, calibrated on the 24 reviewed pairs: false matches 0-1 inliers, real duplicates 29-1,500
MIN_INLIER_FRACTION = 0.02       # ...and at least this share of the poorer image's keypoints: random matches grow with image richness
                                 # (two unrelated feature-rich images gave ~10 inliers), real duplicates match a large share (>= 8%)
HASH_ONLY_MAX_DISTANCE = 0       # identical hash AND too few keypoints for ORB to judge -> accepted (reported separately)
HASH_ONLY_MAX_KEYPOINTS = 30
MAX_SIDE = 640
MAX_PAIRS_PER_GROUP = 400        # very large groups are sampled (and reported), not compared exhaustively
SEED = 0
ORB_FEATURES = 1500
MATCH_DISTANCE = 40


def _cv2():
    try:
        import cv2
        return cv2
    except ImportError:
        raise SystemExit("verify_duplicates needs OpenCV. Install it with:  pip install opencv-python")


class Features:
    """ORB keypoints/descriptors per image (one group's worth at a time; the caller clears it between groups)."""

    def __init__(self, root):
        self.cv2 = _cv2()
        self.root = Path(root)
        self.orb = self.cv2.ORB_create(ORB_FEATURES)
        self.matcher = self.cv2.BFMatcher(self.cv2.NORM_HAMMING, crossCheck=True)
        self.cache = {}

    def clear(self):
        self.cache.clear()

    def _compute(self, rel):
        try:
            with Image.open(self.root / rel) as im:
                im = im.convert("L")
                im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
                arr = np.asarray(im)
        except Exception:                                               # noqa: BLE001 -- unreadable image
            return None
        kp, des = self.orb.detectAndCompute(arr, None)
        pts = np.float32([k.pt for k in kp]) if kp else np.zeros((0, 2), np.float32)
        return pts, des

    def get(self, rel):
        if rel not in self.cache:
            self.cache[rel] = self._compute(rel)
        return self.cache[rel]

    def compare(self, a, b):
        """{"inliers": geometrically consistent matches (None if unreadable), "n_kp": keypoints in the poorer image}."""
        fa, fb = self.get(a), self.get(b)
        if fa is None or fb is None:
            return {"inliers": None, "n_kp": 0}
        (pa, da), (pb, db) = fa, fb
        n_kp = min(len(pa), len(pb))
        if da is None or db is None or n_kp < 4:
            return {"inliers": 0, "n_kp": n_kp}
        matches = [m for m in self.matcher.match(da, db) if m.distance < MATCH_DISTANCE]
        if len(matches) < 4:
            return {"inliers": len(matches), "n_kp": n_kp}
        src = pa[[m.queryIdx for m in matches]].reshape(-1, 1, 2)
        dst = pb[[m.trainIdx for m in matches]].reshape(-1, 1, 2)
        _, mask = self.cv2.findHomography(src, dst, self.cv2.RANSAC, 5.0)
        return {"inliers": int(mask.sum()) if mask is not None else 0, "n_kp": n_kp}


def hamming(a, b):
    return bin(a ^ b).count("1")


def is_verified(info, hash_distance, inlier_threshold=INLIER_THRESHOLD):
    """Returns (verified, how). 'orb' = enough geometric matches; 'hash' = identical hash on an image too plain for ORB.
    Required matches = max(inlier_threshold, MIN_INLIER_FRACTION x keypoints of the poorer image)."""
    inl = info.get("inliers")
    if inl is None:                                                     # an image could not be read: never verified
        return False, ""
    required = max(inlier_threshold, MIN_INLIER_FRACTION * info.get("n_kp", 0))
    if inl >= required:
        return True, "orb"
    if (hash_distance is not None and hash_distance <= HASH_ONLY_MAX_DISTANCE
            and info.get("n_kp", 0) < HASH_ONLY_MAX_KEYPOINTS):
        return True, "hash"
    return False, ""


class _UF:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        if a != b:
            self.p[max(a, b)] = min(a, b)


def _crop(label):
    return label.split("__")[0]


def analyse(rows, hash_int, edge_fn, inlier_threshold=INLIER_THRESHOLD, max_pairs=MAX_PAIRS_PER_GROUP, progress=None, after_group=None):
    """
    rows: dicts from splits.csv (path, source, domain, label, official_split, group, split).
    hash_int: path -> int pHash or None.   edge_fn(path_a, path_b) -> {"inliers", "n_kp"}  (injectable for tests).
    """
    by_group = defaultdict(list)
    for r in rows:
        by_group[r["group"]].append(r)
    candidates = {}
    for g, ms in by_group.items():
        if len(ms) < 2:
            continue
        labels = {m["label"] for m in ms if m["label"]}
        if len(labels) > 1 or any(m["split"] == "test" for m in ms):
            candidates[g] = ms

    edges, components = [], []
    n_pairs = n_pairs_all = n_hash_only = partial_groups = 0
    phash_conflict_groups = 0
    true_conflict_groups = 0
    for gi, (g, ms) in enumerate(candidates.items()):
        labels = {m["label"] for m in ms if m["label"]}
        if len(labels) > 1:
            phash_conflict_groups += 1
        pairs = list(itertools.combinations(range(len(ms)), 2))
        n_pairs_all += len(pairs)
        if len(pairs) > max_pairs:
            pairs = random.Random(f"{SEED}-{g}").sample(pairs, max_pairs)
            partial_groups += 1
        uf = _UF(len(ms))
        for i, j in pairs:
            a, b = ms[i]["path"], ms[j]["path"]
            ha, hb = hash_int.get(a), hash_int.get(b)
            dist = hamming(ha, hb) if ha is not None and hb is not None else None
            info = edge_fn(a, b)
            n_pairs += 1
            ok, how = is_verified(info, dist, inlier_threshold)
            if ok:
                uf.union(i, j)
                n_hash_only += how == "hash"
                edges.append({"path_a": a, "path_b": b, "label_a": ms[i]["label"], "label_b": ms[j]["label"],
                              "inliers": info.get("inliers"), "how": how})
        comps = defaultdict(list)
        for i in range(len(ms)):
            comps[uf.find(i)].append(ms[i])
        group_has_true_conflict = False
        for ci, members in enumerate(comps.values()):
            if len(members) < 2:
                continue
            labs = {m["label"] for m in members if m["label"]}
            conflict = len(labs) > 1
            group_has_true_conflict |= conflict
            components.append({"id": f"{g}.{ci}", "phash_group": g, "members": members, "labels": sorted(labs), "conflict": conflict,
                               "cross_crop": len({_crop(l) for l in labs}) > 1,
                               "has_benchmark": any(m["split"] == "test" for m in members)})
        if len(labels) > 1 and group_has_true_conflict:
            true_conflict_groups += 1
        if after_group:
            after_group()                                               # e.g. drop this group's cached image features
        if progress and (gi + 1) % 100 == 0:
            progress(gi + 1, len(candidates))

    comp_of = {m["path"]: c for c in components for m in c["members"]}
    # the benchmark candidates the split step dropped for a (pHash) label conflict -- the "98" -- and what verification says
    dropped = [r for r in rows if r["domain"] == "field" and r["official_split"] == "test" and r["label"] and r["split"] == "drop"
               and r["group"] in candidates and len({m["label"] for m in candidates[r["group"]] if m["label"]}) > 1]
    verified_true = [r for r in dropped if comp_of.get(r["path"], {}).get("conflict")]
    cross = [r for r in verified_true if comp_of[r["path"]]["cross_crop"]]

    exclusions = []
    for c in components:
        reason = "conflict" if c["conflict"] else ("benchmark_duplicate" if c["has_benchmark"] else None)
        if not reason:
            continue
        for m in c["members"]:
            # only images that could actually be trained on: never the frozen benchmark's rows, and never any official-test photo
            # (those are not training images, so listing them would only inflate the exclusion counts)
            if m["split"] != "test" and m["official_split"] != "test":
                exclusions.append({"path": m["path"], "label": m["label"], "source": m.get("source", ""), "reason": reason,
                                   "component": c["id"], "component_labels": " | ".join(c["labels"])})
    pair_counts = Counter(" vs ".join(c["labels"]) for c in components if c["conflict"])
    stats = {
        "candidate_phash_groups": len(candidates), "pairs_compared": n_pairs, "pairs_total_in_those_groups": n_pairs_all,
        "groups_sampled_not_exhaustive": partial_groups, "verified_pairs": len(edges), "verified_by_hash_only": n_hash_only,
        "phash_conflict_groups": phash_conflict_groups, "groups_with_a_verified_conflict": true_conflict_groups,
        "groups_dissolved_by_verification": phash_conflict_groups - true_conflict_groups,
        "verified_conflict_components": sum(c["conflict"] for c in components),
        "cross_crop_conflict_components": sum(c["conflict"] and c["cross_crop"] for c in components),
        "benchmark_candidates_dropped_for_conflict": len(dropped), "of_which_verified_true_conflict": len(verified_true),
        "of_which_not_verified_false_positive": len(dropped) - len(verified_true), "of_which_cross_crop": len(cross),
        "exclusions_total": len(exclusions), "exclusions_by_reason": dict(Counter(e["reason"] for e in exclusions)),
        "exclusions_by_source": dict(Counter(e["source"] for e in exclusions)),
        "exclusions_by_label": dict(Counter(e["label"] for e in exclusions)),
        "top_conflicting_label_sets": pair_counts.most_common(15),
    }
    return {"edges": edges, "components": components, "exclusions": exclusions, "stats": stats}


def to_markdown(stats):
    s = stats
    pct = lambda a, b: f"{100 * a / b:.0f}%" if b else "n/a"
    d, t = s["benchmark_candidates_dropped_for_conflict"], s["of_which_verified_true_conflict"]
    lines = ["# Duplicate and label-conflict audit (feature-matching verified)", "",
             f"- pHash groups examined (more than one label, or containing a frozen-benchmark photo): **{s['candidate_phash_groups']}**; "
             f"image pairs compared: {s['pairs_compared']} (verified as the same photo: {s['verified_pairs']}, of which {s['verified_by_hash_only']} "
             f"by identical hash on images too plain for feature matching)",
             f"- Of **{s['phash_conflict_groups']}** pHash groups carrying more than one label, **{s['groups_with_a_verified_conflict']}** contain a "
             f"verified conflict (the same photo under different labels); **{s['groups_dissolved_by_verification']}** dissolve (false matches)",
             f"- Verified conflicts: **{s['verified_conflict_components']}** distinct photos filed under different labels, "
             f"**{s['cross_crop_conflict_components']}** of them across different CROPS",
             f"- The benchmark photos the split step dropped for a conflict: **{d}**; verified true conflicts **{t}** ({pct(t, d)}), "
             f"false positives **{d - t}** ({pct(d - t, d)}); {s['of_which_cross_crop']} of the true ones are cross-crop",
             "", f"## Clean-training exclusions: {s['exclusions_total']} images", "",
             f"- by reason: {s['exclusions_by_reason']}", f"- by source: {s['exclusions_by_source']}", "",
             "| Label | Images excluded |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in sorted(s["exclusions_by_label"].items(), key=lambda kv: -kv[1])]
    lines += ["", "## Most frequent conflicting label sets", ""]
    lines += [f"- {k}: {v}" for k, v in s["top_conflicting_label_sets"]]
    if s["groups_sampled_not_exhaustive"]:
        lines += ["", f"Note: {s['groups_sampled_not_exhaustive']} very large groups were sampled, not compared exhaustively."]
    lines += ["", f"Method: ORB feature matching with RANSAC; a pair counts as the same photo with at least {INLIER_THRESHOLD} geometrically "
                  f"consistent matches and at least {MIN_INLIER_FRACTION:.0%} of the poorer image's keypoints. On the 24 pairs reviewed by eye, "
                  "real duplicates had 30-1,500 matches and false matches 0."]
    return "\n".join(lines) + "\n"


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--splits", default=str(config.WORK_DIR / "splits.csv"))
    ap.add_argument("--hashes", default=str(config.WORK_DIR / "hashes.csv"))
    ap.add_argument("--data-root", default=str(config.DATA_ROOT))
    ap.add_argument("--inlier-threshold", type=int, default=INLIER_THRESHOLD)
    a = ap.parse_args(argv)
    out = Path(a.splits).parent

    rows = read_csv(a.splits)
    hash_int = {r["path"]: (int(r["phash"], 16) if r["phash"] else None) for r in read_csv(a.hashes)}
    feats = Features(a.data_root)
    print(f"Verifying duplicate candidates in {len(rows)} images (this reads the images again; a few minutes) ...")
    res = analyse(rows, hash_int, feats.compare, a.inlier_threshold, after_group=feats.clear,
                  progress=lambda i, n: print(f"  {i}/{n} groups", flush=True))
    with open(out / "verified_duplicates.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["path_a", "path_b", "label_a", "label_b", "inliers", "how"])
        w.writeheader()
        w.writerows(res["edges"])
    with open(out / "clean_train_exclusions.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["path", "label", "source", "reason", "component", "component_labels"])
        w.writeheader()
        w.writerows(res["exclusions"])
    (out / "duplicate_audit.json").write_text(json.dumps(res["stats"], indent=1, ensure_ascii=False), encoding="utf-8")
    md = to_markdown(res["stats"])
    (out / "duplicate_audit.md").write_text(md, encoding="utf-8")
    print(md)
    print(f"-> {out / 'duplicate_audit.md'}\n-> {out / 'clean_train_exclusions.csv'}")


if __name__ == "__main__":
    main()
