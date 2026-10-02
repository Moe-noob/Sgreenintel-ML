"""
Evaluation metrics (numpy only, so they are easy to test and audit).

  accuracy, macro_f1, per_class      standard classification scores
  bootstrap_ci                       95 % interval by resampling images
  ece                                expected calibration error (15 bins)
  coverage_curve                     accuracy on accepted photos vs share accepted
  threshold_for_accuracy             confidence cut-off that reaches a target accuracy
"""

import numpy as np


def accuracy(y, p):
    y, p = np.asarray(y), np.asarray(p)
    return float((y == p).mean()) if len(y) else float("nan")


def per_class(y, p, labels=None):
    y, p = np.asarray(y), np.asarray(p)
    labels = sorted(set(y.tolist())) if labels is None else labels
    out = {}
    for c in labels:
        tp = int(((p == c) & (y == c)).sum())
        fp = int(((p == c) & (y != c)).sum())
        fn = int(((p != c) & (y == c)).sum())
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        out[c] = {"precision": prec, "recall": rec, "f1": f1, "support": int((y == c).sum())}
    return out


def macro_f1(y, p, labels=None):
    pc = per_class(y, p, labels)
    vals = [v["f1"] for v in pc.values() if v["support"] > 0]
    return float(np.mean(vals)) if vals else float("nan")


def bootstrap_ci(metric, y, p, n=2000, seed=0, alpha=0.05):
    """(point, low, high) for metric(y, p), resampling images with replacement."""
    y, p = np.asarray(y), np.asarray(p)
    rng = np.random.default_rng(seed)
    point = metric(y, p)
    stats = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        stats.append(metric(y[i], p[i]))
    lo, hi = np.nanpercentile(stats, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(point), float(lo), float(hi)


def paired_bootstrap_diff(metric, y, p_a, p_b, n=2000, seed=0):
    """Difference metric(B) - metric(A) on the same images, with a 95 % interval."""
    y, p_a, p_b = map(np.asarray, (y, p_a, p_b))
    rng = np.random.default_rng(seed)
    d = metric(y, p_b) - metric(y, p_a)
    stats = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        stats.append(metric(y[i], p_b[i]) - metric(y[i], p_a[i]))
    lo, hi = np.percentile(stats, [2.5, 97.5])
    return float(d), float(lo), float(hi)


def ece(confidence, correct, bins=15):
    c, k = np.asarray(confidence, float), np.asarray(correct, float)
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for a, b in zip(edges[:-1], edges[1:]):
        m = (c > a) & (c <= b) if a > 0 else (c >= a) & (c <= b)
        if m.any():
            total += m.mean() * abs(k[m].mean() - c[m].mean())
    return float(total)


def coverage_curve(confidence, correct, points=21):
    """[(threshold, coverage, accuracy_on_accepted)] for thresholds 0..1."""
    c, k = np.asarray(confidence, float), np.asarray(correct, bool)
    out = []
    for t in np.linspace(0, 1, points):
        m = c >= t
        out.append((float(t), float(m.mean()), float(k[m].mean()) if m.any() else float("nan")))
    return out


def threshold_for_accuracy(confidence, correct, target):
    """
    Lowest confidence threshold whose accepted photos reach `target` accuracy
    (fit this on the VALIDATION split only). Returns (threshold, coverage, accuracy)
    or (1.0, 0.0, nan) if the target cannot be met.
    """
    c, k = np.asarray(confidence, float), np.asarray(correct, bool)
    order = np.argsort(-c)
    cs, ks = c[order], k[order]
    acc = np.cumsum(ks) / np.arange(1, len(ks) + 1)
    ok = np.flatnonzero(acc >= target)
    if len(ok) == 0:
        return 1.0, 0.0, float("nan")
    n = ok.max() + 1                      # largest accepted set still meeting the target
    return float(cs[n - 1]), float(n / len(cs)), float(acc[n - 1])
