"""
AI4Mars 지형 분류 — 실제로 학습시킨 시맨틱 분할 모델

지금까지 이 프로젝트의 "CV 위험도"는 두 갈래였다: ① 전문가 라벨에 숫자만 입힌 것
(label-echo), ② 라벨을 전혀 안 쓰는 그림자 기반 고전 CV(big_rock IoU 0.120, 오탐 심함).
둘 다 "학습된 모델"이 아니었다. 이 스크립트는 처음으로 라벨 데이터로 실제 학습을 돌려,
그 두 극단 사이의 진짜 답 — 지도학습 분할 모델이 어느 정도 성능을 내는지 — 를 확인한다.

데이터: fetch_ai4mars_subset.py로 받은 360장(train 300 + val 60), big_rock 라벨이
있는 이미지를 ~45% 비율로 우선 포함해 희귀 클래스가 아예 안 보이는 걸 방지했다.

모델: 작은 U-Net(4단 인코더/디코더, 채널 16→32→64→128) — CPU로 수십 분 안에 돌아가게
일부러 작게 설계. 큰 모델이 아니라 "라벨로 실제 학습하면 무슨 일이 일어나는가"를
보이는 게 목적이다.
"""
from __future__ import annotations

import glob
import json
import os
import random

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
from torch.utils.data import Dataset, DataLoader

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DATA_DIR = "../data/ai4mars_subset"
OUT_DIR = "../outputs/terrain_segmentation"
os.makedirs(OUT_DIR, exist_ok=True)

IMG_SIZE = 256
N_CLASSES = 4  # 0=soil 1=bedrock 2=sand 3=big_rock (255=unlabeled, loss에서 무시)
CLASS_NAMES = ["soil", "bedrock", "sand", "big_rock"]
IGNORE_INDEX = 255

BATCH_SIZE = 8
N_EPOCHS = 30
LR = 1e-3
RNG_SEED = 3
DEVICE = torch.device("cpu")


# ============================================================
# 1. 데이터셋
# ============================================================

class AI4MarsSeg(Dataset):
    def __init__(self, split: str, augment: bool):
        self.split = split
        self.img_paths = sorted(glob.glob(f"{DATA_DIR}/{split}/images/*"))
        self.augment = augment

    def __len__(self):
        return len(self.img_paths)

    def __getitem__(self, idx):
        img_path = self.img_paths[idx]
        stem = os.path.splitext(os.path.basename(img_path))[0]
        mask_path = f"{DATA_DIR}/{self.split}/masks/{stem}.png"

        img = Image.open(img_path).convert("L").resize((IMG_SIZE, IMG_SIZE), Image.BILINEAR)
        mask = Image.open(mask_path).resize((IMG_SIZE, IMG_SIZE), Image.NEAREST)

        img_arr = np.array(img, dtype=np.float32) / 255.0
        mask_arr = np.array(mask, dtype=np.int64)
        # 255(unlabeled)를 제외한 나머지 값은 전부 0~3 범위 — 혹시 모를 이상값은 unlabeled로 흡수
        mask_arr = np.where((mask_arr >= 0) & (mask_arr <= 3), mask_arr, IGNORE_INDEX)

        if self.augment and random.random() < 0.5:
            img_arr = np.fliplr(img_arr).copy()
            mask_arr = np.fliplr(mask_arr).copy()

        img_t = torch.from_numpy(img_arr).unsqueeze(0)  # (1,H,W)
        mask_t = torch.from_numpy(mask_arr)  # (H,W)
        return img_t, mask_t


# ============================================================
# 2. 작은 U-Net
# ============================================================

def conv_block(cin, cout):
    return nn.Sequential(
        nn.Conv2d(cin, cout, 3, padding=1), nn.BatchNorm2d(cout), nn.ReLU(inplace=True),
        nn.Conv2d(cout, cout, 3, padding=1), nn.BatchNorm2d(cout), nn.ReLU(inplace=True),
    )


class SmallUNet(nn.Module):
    def __init__(self, n_classes=N_CLASSES):
        super().__init__()
        ch = [16, 32, 64, 128]
        self.enc1 = conv_block(1, ch[0])
        self.enc2 = conv_block(ch[0], ch[1])
        self.enc3 = conv_block(ch[1], ch[2])
        self.bottleneck = conv_block(ch[2], ch[3])
        self.pool = nn.MaxPool2d(2)

        self.up3 = nn.ConvTranspose2d(ch[3], ch[2], 2, stride=2)
        self.dec3 = conv_block(ch[2] * 2, ch[2])
        self.up2 = nn.ConvTranspose2d(ch[2], ch[1], 2, stride=2)
        self.dec2 = conv_block(ch[1] * 2, ch[1])
        self.up1 = nn.ConvTranspose2d(ch[1], ch[0], 2, stride=2)
        self.dec1 = conv_block(ch[0] * 2, ch[0])

        self.head = nn.Conv2d(ch[0], n_classes, 1)

    def forward(self, x):
        e1 = self.enc1(x)
        e2 = self.enc2(self.pool(e1))
        e3 = self.enc3(self.pool(e2))
        b = self.bottleneck(self.pool(e3))

        d3 = self.dec3(torch.cat([self.up3(b), e3], dim=1))
        d2 = self.dec2(torch.cat([self.up2(d3), e2], dim=1))
        d1 = self.dec1(torch.cat([self.up1(d2), e1], dim=1))
        return self.head(d1)


# ============================================================
# 3. 지표
# ============================================================

def confusion_matrix(pred, target, n_classes=N_CLASSES, ignore_index=IGNORE_INDEX):
    valid = target != ignore_index
    pred, target = pred[valid], target[valid]
    cm = np.zeros((n_classes, n_classes), dtype=np.int64)
    idx = target * n_classes + pred
    binc = np.bincount(idx, minlength=n_classes * n_classes)
    cm += binc.reshape(n_classes, n_classes)
    return cm


def iou_per_class(cm: np.ndarray) -> np.ndarray:
    ious = np.full(cm.shape[0], np.nan)
    for c in range(cm.shape[0]):
        tp = cm[c, c]
        fp = cm[:, c].sum() - tp
        fn = cm[c, :].sum() - tp
        denom = tp + fp + fn
        if denom > 0:
            ious[c] = tp / denom
    return ious


# ============================================================
# 4. 학습 루프
# ============================================================

def evaluate(model, loader):
    model.eval()
    cm = np.zeros((N_CLASSES, N_CLASSES), dtype=np.int64)
    total_loss, n_batches = 0.0, 0
    with torch.no_grad():
        for img, mask in loader:
            img, mask = img.to(DEVICE), mask.to(DEVICE)
            logits = model(img)
            loss = F.cross_entropy(logits, mask, ignore_index=IGNORE_INDEX)
            total_loss += loss.item(); n_batches += 1
            pred = logits.argmax(dim=1).cpu().numpy().ravel()
            cm += confusion_matrix(pred, mask.cpu().numpy().ravel())
    return total_loss / max(n_batches, 1), cm


def main():
    torch.manual_seed(RNG_SEED)
    random.seed(RNG_SEED)

    train_ds = AI4MarsSeg("train", augment=True)
    val_ds = AI4MarsSeg("val", augment=False)
    print(f"train {len(train_ds)}장, val {len(val_ds)}장")

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=2)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=2)

    model = SmallUNet().to(DEVICE)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"모델 파라미터 수: {n_params:,}")

    optimizer = torch.optim.Adam(model.parameters(), lr=LR)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=N_EPOCHS)

    history = {"train_loss": [], "val_loss": [], "val_miou": [], "val_iou_per_class": []}
    best_miou, best_state = -1.0, None

    for epoch in range(N_EPOCHS):
        model.train()
        running_loss, n_batches = 0.0, 0
        for img, mask in train_loader:
            img, mask = img.to(DEVICE), mask.to(DEVICE)
            optimizer.zero_grad()
            logits = model(img)
            loss = F.cross_entropy(logits, mask, ignore_index=IGNORE_INDEX)
            loss.backward()
            optimizer.step()
            running_loss += loss.item(); n_batches += 1
        scheduler.step()

        train_loss = running_loss / max(n_batches, 1)
        val_loss, cm = evaluate(model, val_loader)
        ious = iou_per_class(cm)
        miou = float(np.nanmean(ious))

        history["train_loss"].append(train_loss)
        history["val_loss"].append(val_loss)
        history["val_miou"].append(miou)
        history["val_iou_per_class"].append(ious.tolist())

        if miou > best_miou:
            best_miou = miou
            best_state = {k: v.clone() for k, v in model.state_dict().items()}

        iou_str = " ".join(f"{n}={v:.3f}" for n, v in zip(CLASS_NAMES, ious))
        print(f"[{epoch + 1:>2}/{N_EPOCHS}] train_loss={train_loss:.4f} val_loss={val_loss:.4f} "
              f"mIoU={miou:.3f} ({iou_str})")

    model.load_state_dict(best_state)
    torch.save(best_state, f"{OUT_DIR}/small_unet_best.pt")
    print(f"\n최고 mIoU={best_miou:.3f} 모델 저장: {OUT_DIR}/small_unet_best.pt")

    # ---- 최종 평가 (최고 체크포인트) ----
    val_loss, cm = evaluate(model, val_loader)
    ious = iou_per_class(cm)
    final_summary = {
        "n_train": len(train_ds), "n_val": len(val_ds), "n_params": n_params,
        "n_epochs": N_EPOCHS, "best_val_miou": float(np.nanmean(ious)),
        "val_iou_per_class": {CLASS_NAMES[i]: float(ious[i]) for i in range(N_CLASSES)},
        "confusion_matrix": cm.tolist(),
        "history": history,
    }
    with open(f"{OUT_DIR}/training_stats.json", "w") as f:
        json.dump(final_summary, f, indent=2)
    print(f"saved {OUT_DIR}/training_stats.json")

    plot_history(history)
    plot_confusion_matrix(cm)
    plot_qualitative(model, val_ds, n_examples=4)

    return model, final_summary


# ============================================================
# 5. 시각화
# ============================================================

def style_ax(ax):
    ax.set_facecolor("#0b0e15")
    for s in ax.spines.values():
        s.set_color("#262d3d")
    ax.tick_params(colors="#a7aec1", labelsize=8)
    ax.grid(color="#1c2230", linewidth=0.6)


def plot_history(history):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), facecolor="#0b0e15")
    ax = axes[0]; style_ax(ax)
    ax.plot(history["train_loss"], color="#e08a76", label="train loss")
    ax.plot(history["val_loss"], color="#5cbcc3", label="val loss")
    ax.set_xlabel("epoch", color="#a7aec1"); ax.set_ylabel("cross-entropy loss", color="#a7aec1")
    ax.set_title("Training curve", color="#e9ebf2", fontsize=10)
    ax.legend(facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2", fontsize=9)

    ax = axes[1]; style_ax(ax)
    ax.plot(history["val_miou"], color="#e0ac53")
    ax.set_xlabel("epoch", color="#a7aec1"); ax.set_ylabel("val mean IoU", color="#a7aec1")
    ax.set_title("Validation mIoU", color="#e9ebf2", fontsize=10)
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/training_curve.png", dpi=135, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"saved {OUT_DIR}/training_curve.png")


def plot_confusion_matrix(cm):
    cm_norm = cm / np.clip(cm.sum(axis=1, keepdims=True), 1, None)
    fig, ax = plt.subplots(figsize=(5.5, 5), facecolor="#0b0e15")
    style_ax(ax)
    im = ax.imshow(cm_norm, cmap="inferno", vmin=0, vmax=1)
    ax.set_xticks(range(N_CLASSES)); ax.set_xticklabels(CLASS_NAMES, rotation=45, ha="right")
    ax.set_yticks(range(N_CLASSES)); ax.set_yticklabels(CLASS_NAMES)
    ax.set_xlabel("predicted", color="#a7aec1"); ax.set_ylabel("ground truth", color="#a7aec1")
    for i in range(N_CLASSES):
        for j in range(N_CLASSES):
            ax.text(j, i, f"{cm_norm[i, j]:.2f}", ha="center", va="center",
                     color="white" if cm_norm[i, j] < 0.6 else "black", fontsize=9)
    ax.set_title("Validation confusion matrix (row-normalized)", color="#e9ebf2", fontsize=10)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/confusion_matrix.png", dpi=135, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"saved {OUT_DIR}/confusion_matrix.png")


CLASS_COLORS = np.array([
    [163, 120, 31], [28, 107, 115], [224, 172, 83], [156, 74, 58],
], dtype=np.uint8)  # soil, bedrock, sand, big_rock


def colorize(mask: np.ndarray) -> np.ndarray:
    out = np.zeros((*mask.shape, 3), dtype=np.uint8)
    for c in range(N_CLASSES):
        out[mask == c] = CLASS_COLORS[c]
    out[mask == IGNORE_INDEX] = [20, 20, 20]
    return out


def plot_qualitative(model, val_ds, n_examples=4):
    model.eval()
    idxs = list(range(min(n_examples, len(val_ds))))
    fig, axes = plt.subplots(len(idxs), 3, figsize=(9, 3 * len(idxs)), facecolor="#0b0e15")
    if len(idxs) == 1:
        axes = axes[None, :]
    with torch.no_grad():
        for row, i in enumerate(idxs):
            img, mask = val_ds[i]
            logits = model(img.unsqueeze(0))
            pred = logits.argmax(dim=1).squeeze(0).numpy()

            for col, (arr, title) in enumerate([
                (img.squeeze(0).numpy(), "input"),
                (colorize(mask.numpy()), "ground truth"),
                (colorize(pred), "prediction"),
            ]):
                ax = axes[row, col]; style_ax(ax)
                if col == 0:
                    ax.imshow(arr, cmap="gray")
                else:
                    ax.imshow(arr)
                if row == 0:
                    ax.set_title(title, color="#e9ebf2", fontsize=10)
                ax.set_xticks([]); ax.set_yticks([])
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/qualitative_predictions.png", dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"saved {OUT_DIR}/qualitative_predictions.png")


if __name__ == "__main__":
    main()
