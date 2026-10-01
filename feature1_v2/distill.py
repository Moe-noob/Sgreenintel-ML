"""
Optional (plan, Step 3.6): distil the best model (teacher) into a small,
fast student (default MobileNetV3-Large) for CPU or phone inference.

Loss = alpha * T^2 * KL(student/T || teacher/T) + (1 - alpha) * CE(label)
(Hinton, Vinyals & Dean 2015). The student sees the same augmented images;
they are re-normalised and resized for the teacher, so the two may use
different input sizes and normalisation. Selection by field-validation
macro-F1 as in train.py. Then run calibrate.py / evaluate.py on the student
like any other checkpoint and compare it with the teacher (compare.py).

  python -m feature1_v2.distill --teacher work/runs/dinov2_b_ft/best.pt --student mnv3_l --epochs 30 --out work/runs/mnv3_distilled
"""

import argparse
import json
import random
from pathlib import Path

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

from feature1_v2 import config, models
from feature1_v2.data import splits as sp
from feature1_v2.data.dataset import RowsDataset, balanced_sampler, eval_transform, train_transform
from feature1_v2.train import cosine_with_warmup, evaluate_loader, seed_all


def to_teacher(x, s_meta, t_meta):
    mean_s = torch.tensor(s_meta["mean"], device=x.device).view(1, 3, 1, 1)
    std_s = torch.tensor(s_meta["std"], device=x.device).view(1, 3, 1, 1)
    mean_t = torch.tensor(t_meta["mean"], device=x.device).view(1, 3, 1, 1)
    std_t = torch.tensor(t_meta["std"], device=x.device).view(1, 3, 1, 1)
    x = (x * std_s + mean_s - mean_t) / std_t
    if t_meta["img_size"] != x.shape[-1]:
        x = F.interpolate(x, size=(t_meta["img_size"], t_meta["img_size"]), mode="bilinear", align_corners=False)
    return x


def kd_loss(s_logits, t_logits, y, T=4.0, alpha=0.7):
    kl = F.kl_div(F.log_softmax(s_logits / T, 1), F.softmax(t_logits / T, 1), reduction="batchmean") * T * T
    return alpha * kl + (1 - alpha) * F.cross_entropy(s_logits, y)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--teacher", required=True)
    ap.add_argument("--student", default="mnv3_l", choices=sorted(models.BACKBONES))
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--img-size", type=int, default=config.IMAGE_SIZE)
    ap.add_argument("--temperature", type=float, default=4.0)
    ap.add_argument("--alpha", type=float, default=0.7)
    ap.add_argument("--field-weight", type=float, default=3.0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--no-pretrained", action="store_true")
    ap.add_argument("--splits", default=str(config.WORK_DIR / "splits.csv"))
    ap.add_argument("--data-root", default=str(config.DATA_ROOT))
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=config.SEED)
    a = ap.parse_args(argv)
    seed_all(a.seed)
    random.seed(a.seed)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    teacher, tck = models.load_checkpoint(a.teacher)
    teacher.to(dev).eval()
    classes, t_meta = tck["classes"], tck["meta"]
    c2i = {c: i for i, c in enumerate(classes)}
    student, s_meta = models.create(a.student, len(classes), a.img_size, pretrained=not a.no_pretrained)
    student.to(dev)

    tr_rows = [r for r in sp.load_split("train", a.splits) if r["label"] in c2i]
    va_rows = [r for r in sp.load_split("val", a.splits) if r["label"] in c2i]
    tr_ds = RowsDataset(tr_rows, a.data_root, c2i, train_transform(a.img_size, s_meta["mean"], s_meta["std"]))
    va_ds = RowsDataset(va_rows, a.data_root, c2i, eval_transform(a.img_size, s_meta["mean"], s_meta["std"]))
    tr = DataLoader(tr_ds, batch_size=a.batch, sampler=balanced_sampler(tr_ds.rows, a.field_weight),
                    num_workers=a.workers, drop_last=len(tr_ds) > a.batch)
    va = DataLoader(va_ds, batch_size=a.batch * 2, num_workers=a.workers)

    opt = torch.optim.AdamW(student.parameters(), lr=a.lr, weight_decay=0.05)
    sched = cosine_with_warmup(opt, warmup=min(300, a.epochs * len(tr) // 10), total=a.epochs * max(1, len(tr)))
    best, history = -1.0, []
    for epoch in range(a.epochs):
        student.train()
        loss_sum, seen = 0.0, 0
        for x, y in tr:
            x, y = x.to(dev), y.to(dev)
            with torch.no_grad():
                t_logits = teacher(to_teacher(x, s_meta, t_meta)).float()
            loss = kd_loss(student(x).float(), t_logits, y, a.temperature, a.alpha)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            sched.step()
            loss_sum += loss.item() * len(x)
            seen += len(x)
        val, _, _ = evaluate_loader(student, va, dev, amp=False)
        rec = {"epoch": epoch + 1, "train_loss": loss_sum / max(seen, 1), **{f"val_{k}": v for k, v in val.items()}}
        history.append(rec)
        print(json.dumps(rec))
        if val["macro_f1"] > best:
            best = val["macro_f1"]
            models.save_checkpoint(out / "best.pt", student, s_meta, classes,
                                   {"val": val, "epoch": epoch + 1, "teacher": str(a.teacher), "args": vars(a)})
        (out / "history.json").write_text(json.dumps(history, indent=1))
    return out / "best.pt"


if __name__ == "__main__":
    main()
