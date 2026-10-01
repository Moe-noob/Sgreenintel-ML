"""
Backbones compared in plan Step 3.1, all via timm (pretrained weights are
downloaded from the Hugging Face hub on first use, e.g. on Colab).

  dinov2_s    vit_small_patch14_dinov2.lvd142m     22 M params, self-supervised (Oquab et al. 2023)
  dinov2_b    vit_base_patch14_dinov2.lvd142m      86 M
  convnextv2_t convnextv2_tiny.fcmae_ft_in22k_in1k 28 M, CNN (Woo et al. 2023)
  effv2_s     tf_efficientnetv2_s.in21k_ft_in1k    21 M, CNN (Tan & Le 2021)
  siglip_b    vit_base_patch16_siglip_224.webli    86 M, image-text pretrained (Zhai et al. 2023)
  mnv3_l      mobilenetv3_large_100.ra_in1k        5 M, small student for distillation / phone
  test        test_vit (tiny random model, unit tests only)

Modes
  linear    backbone frozen, only the classification head trains (fast "linear probe")
  finetune  everything trains, with layer-wise learning-rate decay (LLRD): the
            head gets lr, each earlier block lr * decay^depth, so pretrained
            low-level features change least.
"""

import timm
import torch
from timm.data import resolve_data_config

BACKBONES = {
    "dinov2_s": "vit_small_patch14_dinov2.lvd142m",
    "dinov2_b": "vit_base_patch14_dinov2.lvd142m",
    "convnextv2_t": "convnextv2_tiny.fcmae_ft_in22k_in1k",
    "effv2_s": "tf_efficientnetv2_s.in21k_ft_in1k",
    "siglip_b": "vit_base_patch16_siglip_224.webli",
    "mnv3_l": "mobilenetv3_large_100.ra_in1k",
    "test": "test_vit",
}


def create(backbone, num_classes, img_size=224, pretrained=True, drop_path=0.1):
    name = BACKBONES.get(backbone, backbone)
    kwargs = {"num_classes": num_classes, "pretrained": pretrained}
    if "vit" in name or "dinov2" in name or "siglip" in name:
        kwargs["img_size"] = img_size
    if backbone not in ("test", "mnv3_l"):
        kwargs["drop_path_rate"] = drop_path
    model = timm.create_model(name, **kwargs)
    cfg = resolve_data_config({}, model=model)
    meta = {"backbone": backbone, "timm_name": name, "img_size": img_size,
            "mean": list(cfg["mean"]), "std": list(cfg["std"])}
    return model, meta


def head_parameters(model):
    head = model.get_classifier()
    return list(head.parameters())


def freeze_backbone(model):
    for p in model.parameters():
        p.requires_grad = False
    for p in head_parameters(model):
        p.requires_grad = True


def _block_index(name, n_blocks):
    """Depth index of a parameter for LLRD: 0 = stem/embeddings ... n_blocks + 1 = head."""
    parts = name.split(".")
    for key in ("blocks", "stages", "layers"):
        if key in parts:
            i = parts.index(key)
            try:
                return int(parts[i + 1]) + 1
            except (IndexError, ValueError):
                return 1
    if any(k in name for k in ("patch_embed", "cls_token", "pos_embed", "reg_token", "stem", "conv_stem", "bn1")):
        return 0
    return n_blocks + 1


def param_groups(model, lr, weight_decay=0.05, llrd=0.75):
    """AdamW parameter groups with layer-wise LR decay and no weight decay on norms/biases."""
    head_ids = {id(p) for p in head_parameters(model)}
    names = [n for n, _ in model.named_parameters()]
    n_blocks = 0
    for n in names:
        for key in ("blocks", "stages", "layers"):
            parts = n.split(".")
            if key in parts:
                try:
                    n_blocks = max(n_blocks, int(parts[parts.index(key) + 1]) + 1)
                except (IndexError, ValueError):
                    pass
    groups = {}
    for n, p in model.named_parameters():
        if not p.requires_grad:
            continue
        depth = n_blocks + 1 if id(p) in head_ids else _block_index(n, n_blocks)
        scale = llrd ** (n_blocks + 1 - depth)
        no_wd = p.ndim <= 1 or n.endswith(".bias") or "token" in n or "pos_embed" in n
        key = (depth, no_wd)
        if key not in groups:
            groups[key] = {"params": [], "lr": lr * scale, "lr_scale": scale,
                           "weight_decay": 0.0 if no_wd else weight_decay}
        groups[key]["params"].append(p)
    return list(groups.values())


def save_checkpoint(path, model, meta, classes, extra=None):
    torch.save({"state_dict": model.state_dict(), "meta": meta, "classes": classes, **(extra or {})}, path)


def load_checkpoint(path, map_location="cpu"):
    ck = torch.load(path, map_location=map_location, weights_only=False)
    model, _ = create(ck["meta"]["backbone"], len(ck["classes"]), ck["meta"]["img_size"], pretrained=False)
    model.load_state_dict(ck["state_dict"])
    model.eval()
    return model, ck
