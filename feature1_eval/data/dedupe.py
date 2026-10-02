"""
Near-duplicate detection across all datasets.

PlantDoc and PlantWild were both collected from web image search, so the
same photo (resized, re-compressed, slightly cropped) can appear in both,
or in both the train and test split of one dataset. A test image whose
twin is in training inflates the score, so duplicates must be found
before the benchmark is frozen.

Method: 64-bit perceptual hash (pHash: 32x32 greyscale -> 2-D DCT -> top-left
8x8 low frequencies -> above-median bits). Two images are near-duplicates
when their hashes differ in <= PHASH_MAX_DISTANCE bits. Search uses
pigeonhole bucketing: if two 64-bit hashes differ in at most 7 bits, at
least one of their 8 bytes is identical, so only images sharing a byte
value at the same position are compared.

Duplicates are grouped with union-find; splits.py keeps each group on one
side of every split.

Usage
  python -m feature1_eval.data.dedupe       # reads work/manifest.csv, writes work/hashes.csv + work/dup_groups.json
"""

import argparse
import csv
import json
import os
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image

from feature1_eval import config
from feature1_eval.data import manifest as mf

_N = 32
_k = np.arange(_N)
_DCT = np.sqrt(2.0 / _N) * np.cos(np.pi * (2 * _k[None, :] + 1) * _k[:, None] / (2 * _N))
_DCT[0] /= np.sqrt(2.0)


def phash(img):
    """64-bit perceptual hash of a PIL image (int)."""
    g = np.asarray(img.convert("L").resize((_N, _N), Image.BILINEAR), dtype=np.float64)
    d = _DCT @ g @ _DCT.T
    low = d[:8, :8].flatten()
    bits = low > np.median(low[1:])          # DC term excluded from the median
    return int("".join("1" if b else "0" for b in bits), 2)


def hamming(a, b):
    return bin(a ^ b).count("1")


def _hash_file(path):
    try:
        with Image.open(path) as im:
            return phash(im)
    except Exception:                         # noqa: BLE001 -- unreadable image
        return None


def hash_paths(paths, workers=None):
    with ProcessPoolExecutor(max_workers=workers or os.cpu_count()) as ex:
        return list(ex.map(_hash_file, paths, chunksize=64))


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


_POP8 = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint8)


def _popcount64(x):
    """Vectorised popcount of a uint64 array."""
    return _POP8[x.view(np.uint8).reshape(-1, 8)].sum(axis=1)


def group_duplicates(hashes, max_distance=None):
    """
    hashes: list of int or None. Returns a list of group ids (same id = near-duplicates;
    None hash -> its own group). Exact for max_distance <= 7 (pigeonhole on 8 bytes).
    """
    max_distance = config.PHASH_MAX_DISTANCE if max_distance is None else max_distance
    assert max_distance <= 7, "byte bucketing is only exact up to 7 differing bits"
    uf = _UF(len(hashes))
    idx = np.array([i for i, h in enumerate(hashes) if h is not None], dtype=np.int64)
    if len(idx) == 0:
        return list(range(len(hashes)))
    hv = np.array([hashes[i] for i in idx], dtype=np.uint64)
    for b in range(8):
        key = ((hv >> np.uint64(8 * b)) & np.uint64(0xFF)).astype(np.int64)
        order = np.argsort(key, kind="stable")
        bounds = np.flatnonzero(np.diff(key[order])) + 1
        for members in np.split(order, bounds):
            if len(members) < 2:
                continue
            hm = hv[members]
            for x in range(len(members) - 1):
                d = _popcount64(hm[x + 1:] ^ hm[x])
                for y in np.flatnonzero(d <= max_distance):
                    uf.union(int(idx[members[x]]), int(idx[members[x + 1 + y]]))
    return [uf.find(i) for i in range(len(hashes))]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(config.WORK_DIR / "manifest.csv"))
    ap.add_argument("--data-root", default=str(config.DATA_ROOT))
    ap.add_argument("--max-distance", type=int, default=config.PHASH_MAX_DISTANCE)
    a = ap.parse_args(argv)

    rows = mf.read(a.manifest)
    paths = [str(Path(a.data_root) / r["path"]) for r in rows]
    hashes = hash_paths(paths)
    groups = group_duplicates(hashes, a.max_distance)
    out = Path(a.manifest).parent
    with open(out / "hashes.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["path", "phash", "group"])
        for r, h, g in zip(rows, hashes, groups):
            w.writerow([r["path"], "" if h is None else f"{h:016x}", g])
    multi = defaultdict(list)
    for i, g in enumerate(groups):
        multi[g].append(i)
    dup = {g: m for g, m in multi.items() if len(m) > 1}
    unreadable = sum(h is None for h in hashes)
    (out / "dup_groups.json").write_text(json.dumps(
        {"max_distance": a.max_distance, "n_images": len(rows), "unreadable": unreadable,
         "n_groups_with_duplicates": len(dup), "n_images_in_duplicate_groups": sum(len(m) for m in dup.values())}, indent=1))
    print(f"{len(rows)} images, {unreadable} unreadable, {len(dup)} duplicate groups "
          f"covering {sum(len(m) for m in dup.values())} images -> {out / 'hashes.csv'}")


if __name__ == "__main__":
    main()
