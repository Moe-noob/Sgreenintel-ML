"""
Train one Feature 1 v2 model (plan, Step 3).

Model selection uses the FIELD VALIDATION split only (macro-F1); the frozen
benchmark is never touched here.

Examples (Colab T4, see RUNBOOK.md)
  python -m feature1_v2.train --backbone dinov2_s --mode linear   --epochs 10 --out work/runs/dinov2_s_linear
  python -m feature1_v2.train --backbone dinov2_s --mode finetune --epochs 25 --out work/runs/dinov2_s_ft
  python -m feature1_v2.train --backbone convnextv2_t --mode finetune --epochs 25 --out work/runs/convnextv2_ft
"""

import argparse
import json
import math
import random
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from feature1_v2 import config, metrics, models
from feature1_v2.data import splits as sp
from feature1_v2.data.dataset import (BackgroundSwap, RowsDataset, balanced_sampler, eval_transform,
                                      train_transform)


def seed_all(s):
    random.seed(s)
    np.random.seed(s)
    torch.manual_seed(s)


def cosine_with_warmup(optimizer, warmup, total):
    def f(step):
        if step < warmup:
            return (step + 1) / max(1, warmup)
        return 0.5 * (1 + math.cos(math.pi * (step - warmup) / max(1, total - warmup)))
    return torch.optim.lr_scheduler.LambdaLR(optimizer, f)


@torch.no_grad()
def evaluate_loader(model, loader, dev, amp):
    model.eval()
    ys, ps, logits = [], [], []
    for x, y in loader:
        x = x.to(dev, non_blocking=True)
        with torch.autocast(dev.type, enabled=amp and dev.type == "cuda"):
            z = model(x).float()
        logits.append(z.cpu())
        ys.append(y)
        ps.append(z.argmax(1).cpu())
    y, p = torch.cat(ys).numpy(), torch.cat(ps).numpy()
    return {"accuracy": metrics.accuracy(y, p), "macro_f1": metrics.macro_f1(y, p)}, torch.cat(logits).numpy(), y


def build_args(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--backbone", default="dinov2_s", choices=sorted(models.BACKBONES))
    ap.add_argument("--mode", default="finetune", choices=["linear", "finetune"])
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--lr", type=float, default=None, help="default 1e-3 linear, 5e-5 finetune (x batch/32)")
    ap.add_argument("--llrd", type=float, default=0.75)
    ap.add_argument("--weight-decay", type=float, default=0.05)
    ap.add_argument("--img-size", type=int, default=config.IMAGE_SIZE)
    ap.add_argument("--field-weight", type=float, default=3.0)
    ap.add_argument("--epoch-size", type=int, default=None, help="samples per epoch (default: size of train split)")
    ap.add_argument("--cutmix", type=float, default=0.3, help="probability of CutMix per batch (0 = off)")
    ap.add_argument("--label-smoothing", type=float, default=0.1)
    ap.add_argument("--background-swap", type=float, default=0.5)
    ap.add_argument("--ema", type=float, default=0.9998, help="EMA decay (0 = off)")
    ap.add_argument("--no-amp", action="store_true")
    ap.add_argument("--no-pretrained", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--splits", default=str(config.WORK_DIR / "splits.csv"))
    ap.add_argument("--data-root", default=str(config.DATA_ROOT))
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=None, help="debug: cap images per split")
    ap.add_argument("--seed", type=int, default=config.SEED)
    return ap.parse_args(argv)


def main(argv=None):
    a = build_args(argv)
    seed_all(a.seed)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    amp = not a.no_amp
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    classes = sp.classes(a.splits)
    c2i = {c: i for i, c in enumerate(classes)}
    train_rows = sp.load_split("train", a.splits)
    val_rows = sp.load_split("val", a.splits)
    if a.limit:
        random.shuffle(train_rows)
        train_rows, val_rows = train_rows[:a.limit], val_rows[:a.limit]
    train_rows = [r for r in train_rows if r["label"] in c2i]
    val_rows = [r for r in val_rows if r["label"] in c2i]

    model, meta = models.create(a.backbone, len(classes), a.img_size, pretrained=not a.no_pretrained)
    model.to(dev)
    lr = a.lr or ((1e-3 if a.mode == "linear" else 5e-5) * a.batch / 32)
    if a.mode == "linear":
        models.freeze_backbone(model)
        groups = [{"params": models.head_parameters(model), "lr": lr, "weight_decay": 1e-4}]
    else:
        groups = models.param_groups(model, lr, a.weight_decay, a.llrd)
    opt = torch.optim.AdamW(groups, lr=lr)

    field_bg = [str(Path(a.data_root) / r["path"]) for r in train_rows if r.get("domain") == "field"]
    swap = BackgroundSwap(field_bg, p=a.background_swap) if a.background_swap > 0 else None
    tr_ds = RowsDataset(train_rows, a.data_root, c2i, train_transform(a.img_size, meta["mean"], meta["std"]), swap)
    va_ds = RowsDataset(val_rows, a.data_root, c2i, eval_transform(a.img_size, meta["mean"], meta["std"]))
    sampler = balanced_sampler(tr_ds.rows, a.field_weight, a.epoch_size)
    tr = DataLoader(tr_ds, batch_size=a.batch, sampler=sampler, num_workers=a.workers,
                    pin_memory=dev.type == "cuda", drop_last=len(tr_ds) > a.batch)
    va = DataLoader(va_ds, batch_size=a.batch * 2, shuffle=False, num_workers=a.workers)

    mix = None
    if a.cutmix > 0:
        from timm.data import Mixup
        mix = Mixup(mixup_alpha=0.0, cutmix_alpha=1.0, prob=a.cutmix, label_smoothing=a.label_smoothing,
                    num_classes=len(classes))
        from timm.loss import SoftTargetCrossEntropy
        crit = SoftTargetCrossEntropy()
    else:
        crit = nn.CrossEntropyLoss(label_smoothing=a.label_smoothing)

    ema = None
    if a.ema > 0:
        from timm.utils import ModelEmaV3
        ema = ModelEmaV3(model, decay=a.ema)

    steps = a.epochs * max(1, len(tr))
    sched = cosine_with_warmup(opt, warmup=min(500, steps // 10), total=steps)
    scaler = torch.amp.GradScaler(enabled=amp and dev.type == "cuda")
    best, history = -1.0, []
    (out / "args.json").write_text(json.dumps(vars(a), indent=1))
    print(f"{len(classes)} classes | train {len(tr_ds)} | val {len(va_ds)} | {meta['timm_name']} {a.mode} on {dev}")

    for epoch in range(a.epochs):
        model.train()
        t0, seen, loss_sum = time.time(), 0, 0.0
        for x, y in tr:
            x, y = x.to(dev, non_blocking=True), y.to(dev, non_blocking=True)
            if mix is not None and len(x) % 2 == 0:
                x, y_t = mix(x, y)
            else:
                y_t = y
                if mix is not None:                     # odd last batch: hard labels with smoothing
                    y_t = torch.nn.functional.one_hot(y, len(classes)).float() * (1 - a.label_smoothing) \
                        + a.label_smoothing / len(classes)
            with torch.autocast(dev.type, enabled=amp and dev.type == "cuda"):
                loss = crit(model(x), y_t)
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(opt)
            scaler.update()
            sched.step()
            if ema is not None:
                ema.update(model)
            seen += len(x)
            loss_sum += loss.item() * len(x)
        eval_model = ema.module if ema is not None else model
        val, _, _ = evaluate_loader(eval_model, va, dev, amp)
        rec = {"epoch": epoch + 1, "train_loss": loss_sum / max(seen, 1), **{f"val_{k}": v for k, v in val.items()},
               "seconds": round(time.time() - t0, 1)}
        history.append(rec)
        print(json.dumps(rec))
        if val["macro_f1"] > best:
            best = val["macro_f1"]
            models.save_checkpoint(out / "best.pt", eval_model, meta, classes,
                                   {"val": val, "epoch": epoch + 1, "args": vars(a)})
        (out / "history.json").write_text(json.dumps(history, indent=1))
    print(f"best val macro-F1 {best:.4f} -> {out / 'best.pt'}")
    return out / "best.pt"


if __name__ == "__main__":
    main()
