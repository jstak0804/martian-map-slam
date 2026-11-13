"""
지형 분할 U-Net 미세조정: 해커톤 영상·마스크 쌍으로 기존 SmallUNet(AI4Mars 학습)을 이어서 학습한다.

    code/.venv/bin/python -m hackathon.finetune_segmentation --drop ../data/hackathon_2026 --name hackathon_2026 \
        [--class-map class_map.json] [--epochs 15] [--from ../outputs/terrain_segmentation/small_unet_best.pt]

- torch가 있는 code/.venv 로 실행한다.
- 영상·마스크 쌍은 이름으로 맞춘다(loaders.find_image_mask_pairs). 폴더 이름에 train/val/test가 있으면 따르고,
  없으면 파일 이름 해시로 70/15/15 고정 분할한다(다시 돌려도 같은 분할).
- 마스크 값 -> 우리 클래스: --class-map JSON. 키는 마스크 값(정수) 또는 색("#rrggbb"), 값은 클래스 번호(무시는 255).
  예: {"0": 0, "1": 1, "2": 2, "3": 3, "255": 255}  (AI4Mars: soil, bedrock, sand, big_rock)
  클래스 이름을 바꾸려면 {"classes": ["soil", "rock", "sand"], "map": {...}} 형식.
- 클래스 수가 기존(4)과 같으면 기존 가중치 전체에서, 다르면 머리(head)만 새로 만들고 나머지를 이어 받는다.
- 비교: 미세조정 전(기존 모델 그대로)과 후의 시험셋 클래스별 IoU를 함께 기록한다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from torch.utils.data import DataLoader, Dataset

from hackathon.loaders import find_image_mask_pairs
from train_terrain_segmentation import SmallUNet, confusion_matrix, iou_per_class, CLASS_NAMES, IGNORE_INDEX

OUT_ROOT = "../outputs/hackathon"
DEFAULT_FROM = "../outputs/terrain_segmentation/small_unet_best.pt"
IMG_SIZE = 256


def load_class_map(path):
    if not path:
        return CLASS_NAMES, {i: i for i in range(len(CLASS_NAMES))}
    js = json.load(open(path, encoding="utf-8"))
    classes = js.get("classes", CLASS_NAMES)
    raw = js.get("map", js)
    cmap = {}
    for k, v in raw.items():
        if k == "classes":
            continue
        cmap[k.lower() if str(k).startswith("#") else int(k)] = int(v)
    return classes, cmap


def split_of(path):
    low = path.replace("\\", "/").lower()
    for s in ("train", "val", "test"):
        if f"/{s}/" in low or f"/{s}_" in low:
            return s
    hsh = int(hashlib.md5(os.path.basename(path).encode()).hexdigest(), 16) % 100
    return "train" if hsh < 70 else "val" if hsh < 85 else "test"


class PairSet(Dataset):
    def __init__(self, pairs, cmap, augment):
        self.pairs, self.cmap, self.augment = pairs, cmap, augment

    def __len__(self):
        return len(self.pairs)

    def _mask(self, p):
        m = Image.open(p)
        if any(isinstance(k, str) for k in self.cmap):          # 색으로 칠한 마스크
            a = np.asarray(m.convert("RGB").resize((IMG_SIZE, IMG_SIZE), Image.NEAREST))
            out = np.full(a.shape[:2], IGNORE_INDEX, np.int64)
            for k, v in self.cmap.items():
                if isinstance(k, str):
                    rgb = tuple(int(k[i:i + 2], 16) for i in (1, 3, 5))
                    out[(a == rgb).all(-1)] = v
            return out
        a = np.asarray(m.convert("L") if m.mode not in ("L", "P", "I", "I;16") else m).astype(np.int64)
        a = np.asarray(Image.fromarray(a.astype(np.int32)).resize((IMG_SIZE, IMG_SIZE), Image.NEAREST)).astype(np.int64)
        out = np.full(a.shape, IGNORE_INDEX, np.int64)
        for k, v in self.cmap.items():
            out[a == k] = v
        return out

    def __getitem__(self, i):
        ip, mp = self.pairs[i]
        img = np.asarray(Image.open(ip).convert("L").resize((IMG_SIZE, IMG_SIZE), Image.BILINEAR), np.float32) / 255
        msk = self._mask(mp)
        if self.augment and random.random() < 0.5:
            img, msk = np.fliplr(img).copy(), np.fliplr(msk).copy()
        return torch.from_numpy(img).unsqueeze(0), torch.from_numpy(msk)


def evaluate(model, loader, n):
    model.eval()
    cm = np.zeros((n, n), np.int64)
    with torch.no_grad():
        for x, y in loader:
            p = model(x).argmax(1).numpy().ravel()
            cm += confusion_matrix(p, y.numpy().ravel(), n_classes=n)
    iou = iou_per_class(cm)
    return iou, float(np.nanmean(iou))


def main(args):
    torch.manual_seed(0); random.seed(0); np.random.seed(0)
    classes, cmap = load_class_map(args.class_map)
    n = len(classes)
    pairs, _, _ = find_image_mask_pairs(args.drop)
    sets = {s: [p for p in pairs if split_of(p[0]) == s] for s in ("train", "val", "test")}
    print("분할: " + ", ".join(f"{s} {len(v)}" for s, v in sets.items()))
    if not sets["train"] or not sets["test"]:
        raise SystemExit("학습·시험에 쓸 쌍이 부족합니다.")
    if not sets["val"]:
        sets["val"] = sets["test"]
    dl = {s: DataLoader(PairSet(v, cmap, s == "train"), batch_size=args.batch, shuffle=(s == "train"))
          for s, v in sets.items()}
    model = SmallUNet(n_classes=n)
    init = "scratch"
    if args.init and os.path.exists(args.init):
        sd = torch.load(args.init, map_location="cpu")
        if sd["head.weight"].shape[0] != n:
            sd = {k: v for k, v in sd.items() if not k.startswith("head.")}
            init = f"{os.path.basename(args.init)} (head 새로 만듦: 클래스 {n}개)"
        else:
            init = os.path.basename(args.init)
        model.load_state_dict(sd, strict=False)
    base_iou, base_m = evaluate(model, dl["test"], n) if init != "scratch" and "head" not in init else (np.full(n, np.nan), np.nan)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    best, best_state, hist = -1, None, []
    for ep in range(args.epochs):
        model.train(); tot = 0
        for x, y in dl["train"]:
            opt.zero_grad()
            loss = F.cross_entropy(model(x), y, ignore_index=IGNORE_INDEX)
            loss.backward(); opt.step(); tot += loss.item()
        _, vm = evaluate(model, dl["val"], n)
        hist.append({"epoch": ep + 1, "train_loss": tot / max(1, len(dl["train"])), "val_miou": vm})
        if vm > best:
            best, best_state = vm, {k: v.clone() for k, v in model.state_dict().items()}
        print(f"  epoch {ep + 1}/{args.epochs}: loss {hist[-1]['train_loss']:.3f}, val mIoU {vm:.3f}")
    model.load_state_dict(best_state)
    ft_iou, ft_m = evaluate(model, dl["test"], n)
    out_dir = os.path.join(OUT_ROOT, args.name, "segmentation")
    os.makedirs(out_dir, exist_ok=True)
    torch.save(model.state_dict(), os.path.join(out_dir, "small_unet_finetuned.pt"))
    res = {"classes": classes, "init": init, "splits": {s: len(v) for s, v in sets.items()},
           "test_iou_before": dict(zip(classes, map(lambda v: None if np.isnan(v) else float(v), base_iou))),
           "test_miou_before": None if np.isnan(base_m) else base_m,
           "test_iou_after": dict(zip(classes, map(lambda v: None if np.isnan(v) else float(v), ft_iou))),
           "test_miou_after": ft_m, "history": hist, "synthetic": args.synthetic}
    with open(os.path.join(out_dir, "segmentation_metrics.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(f"분할 미세조정: 시험 mIoU {res['test_miou_before']} -> {ft_m:.3f} ({out_dir})")
    return res


def add_args(ap):
    ap.add_argument("--class-map")
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--init", "--from", dest="init", default=DEFAULT_FROM)
    ap.add_argument("--synthetic", action="store_true", help=argparse.SUPPRESS)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--drop", default="../data/hackathon_2026")
    ap.add_argument("--name", default="hackathon_2026")
    add_args(ap)
    main(ap.parse_args())
