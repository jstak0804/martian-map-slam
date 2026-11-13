"""
ConeQuest 2단계 — U-Net 일반화 테스트 (학습 O, 새 알고리즘 발명 아님)

목적: `train_terrain_segmentation.py`에서 쓴 것과 '완전히 동일한' SmallUNet 아키텍처·학습
레시피(Adam, lr=1e-3, CosineAnnealingLR, 30 에폭, 256×256 입력)를 그대로 재사용해서,
AI4Mars(로버 지상 Navcam, 4-클래스) 밖에서도 작동하는지 확인한다. 이진 분할(cone/no-cone)로
클래스 수만 2로 바꾸고, 데이터는 ConeQuest(궤도 HiRISE/CTX, Isidis Planitia 지역, 144장)의
공식 BM-1 split(train 100 / val 14 / test 30)을 그대로 쓴다 — 직접 split을 새로 짜지 않았다.

한계를 미리 명시: 한 지역(Isidis Planitia)·144장짜리 작은 샘플이고, 이 지역은 양성 비율이
91%로 비정상적으로 높다(EDA 결과, 전체 CSV 기준 양성 비율은 12.1%) — 결과를 과대해석하지 않는다.
"""
from __future__ import annotations

import csv
import json
import os
import random
import sys

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from torch.utils.data import Dataset, DataLoader

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(__file__))
from train_terrain_segmentation import SmallUNet, confusion_matrix, iou_per_class, style_ax  # noqa: E402

DATA_ROOT = "../data/conequest/E084_N12"
CSV_PATH = "../data/conequest/ConeQuest_data.csv"
OUT_DIR = "../outputs/conequest_unet"
os.makedirs(OUT_DIR, exist_ok=True)

IMG_SIZE = 256
N_CLASSES = 2
CLASS_NAMES = ["background", "cone"]
IGNORE_INDEX = 255  # ConeQuest 마스크엔 실제로 등장하지 않음 (0/1만)

BATCH_SIZE = 8
N_EPOCHS = 30
LR = 1e-3
RNG_SEED = 3
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def load_splits():
    with open(CSV_PATH, newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["Patch Id"].startswith("E084_N12")]
    splits = {"train": [], "val": [], "test": []}
    for r in rows:
        s = r["BM-1 Set"]
        if s in splits:
            splits[s].append(r["Patch Id"])
    return splits


class ConeQuestSeg(Dataset):
    def __init__(self, names, augment):
        self.names = names
        self.augment = augment

    def __len__(self):
        return len(self.names)

    def __getitem__(self, idx):
        name = self.names[idx]
        img = Image.open(f"{DATA_ROOT}/input_dir/{name}").convert("L").resize((IMG_SIZE, IMG_SIZE), Image.BILINEAR)
        mask = Image.open(f"{DATA_ROOT}/output_dir/{name}").resize((IMG_SIZE, IMG_SIZE), Image.NEAREST)
        img_arr = np.array(img, dtype=np.float32) / 255.0
        mask_arr = np.array(mask, dtype=np.int64)
        mask_arr = np.where((mask_arr == 0) | (mask_arr == 1), mask_arr, IGNORE_INDEX)

        if self.augment and random.random() < 0.5:
            img_arr = np.fliplr(img_arr).copy()
            mask_arr = np.fliplr(mask_arr).copy()

        return torch.from_numpy(img_arr).unsqueeze(0), torch.from_numpy(mask_arr)


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
            cm += confusion_matrix(pred, mask.cpu().numpy().ravel(), n_classes=N_CLASSES, ignore_index=IGNORE_INDEX)
    return total_loss / max(n_batches, 1), cm


def plot_history(history):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), facecolor="#0b0e15")
    ax = axes[0]; style_ax(ax)
    ax.plot(history["train_loss"], color="#e08a76", label="train loss")
    ax.plot(history["val_loss"], color="#5cbcc3", label="val loss")
    ax.set_xlabel("epoch", color="#a7aec1"); ax.set_ylabel("cross-entropy loss", color="#a7aec1")
    ax.set_title("Training curve (ConeQuest, binary)", color="#e9ebf2", fontsize=10)
    ax.legend(facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2", fontsize=9)
    ax = axes[1]; style_ax(ax)
    ax.plot(history["val_miou"], color="#e0ac53")
    ax.set_xlabel("epoch", color="#a7aec1"); ax.set_ylabel("val mean IoU", color="#a7aec1")
    ax.set_title("Validation mIoU", color="#e9ebf2", fontsize=10)
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/training_curve.png", dpi=135, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"saved {OUT_DIR}/training_curve.png")


def plot_confusion_matrix(cm, tag):
    cm_norm = cm / np.clip(cm.sum(axis=1, keepdims=True), 1, None)
    fig, ax = plt.subplots(figsize=(4.5, 4), facecolor="#0b0e15")
    style_ax(ax)
    im = ax.imshow(cm_norm, cmap="inferno", vmin=0, vmax=1)
    ax.set_xticks(range(N_CLASSES)); ax.set_xticklabels(CLASS_NAMES, rotation=30, ha="right")
    ax.set_yticks(range(N_CLASSES)); ax.set_yticklabels(CLASS_NAMES)
    ax.set_xlabel("predicted", color="#a7aec1"); ax.set_ylabel("ground truth", color="#a7aec1")
    for i in range(N_CLASSES):
        for j in range(N_CLASSES):
            ax.text(j, i, f"{cm_norm[i, j]:.2f}", ha="center", va="center",
                     color="white" if cm_norm[i, j] < 0.6 else "black", fontsize=10)
    ax.set_title(f"{tag} confusion matrix (row-norm)", color="#e9ebf2", fontsize=10)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/confusion_matrix_{tag}.png", dpi=135, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"saved {OUT_DIR}/confusion_matrix_{tag}.png")


def plot_qualitative(model, test_ds, n_examples=4):
    model.eval()
    idxs = list(range(min(n_examples, len(test_ds))))
    fig, axes = plt.subplots(len(idxs), 3, figsize=(9, 3 * len(idxs)), facecolor="#0b0e15")
    if len(idxs) == 1:
        axes = axes[None, :]
    with torch.no_grad():
        for row, i in enumerate(idxs):
            img, mask = test_ds[i]
            logits = model(img.unsqueeze(0).to(DEVICE))
            pred = logits.argmax(dim=1)[0].cpu().numpy()
            panels = [("input", img[0].numpy(), "gray"),
                      ("ground truth", mask.numpy(), None),
                      ("prediction", pred, None)]
            for col, (title, arr, cmap) in enumerate(panels):
                ax = axes[row, col]; style_ax(ax)
                if cmap:
                    ax.imshow(arr, cmap=cmap)
                else:
                    ax.imshow(arr, cmap="gray", vmin=0, vmax=1)
                if row == 0:
                    ax.set_title(title, color="#e9ebf2", fontsize=10)
                ax.set_xticks([]); ax.set_yticks([])
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/qualitative_predictions.png", dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"saved {OUT_DIR}/qualitative_predictions.png")


def main():
    torch.manual_seed(RNG_SEED)
    random.seed(RNG_SEED)

    splits = load_splits()
    print(f"split sizes: train={len(splits['train'])} val={len(splits['val'])} test={len(splits['test'])}")
    train_ds = ConeQuestSeg(splits["train"], augment=True)
    val_ds = ConeQuestSeg(splits["val"], augment=False)
    test_ds = ConeQuestSeg(splits["test"], augment=False)

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)
    test_loader = DataLoader(test_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)

    model = SmallUNet(n_classes=N_CLASSES).to(DEVICE)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"device={DEVICE}  params={n_params:,}")

    optimizer = torch.optim.Adam(model.parameters(), lr=LR)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=N_EPOCHS)

    history = {"train_loss": [], "val_loss": [], "val_miou": []}
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

        if miou > best_miou:
            best_miou = miou
            best_state = {k: v.clone() for k, v in model.state_dict().items()}

        print(f"[{epoch + 1:>2}/{N_EPOCHS}] train_loss={train_loss:.4f} val_loss={val_loss:.4f} "
              f"mIoU={miou:.3f} (bg={ious[0]:.3f} cone={ious[1]:.3f})")

    model.load_state_dict(best_state)
    torch.save(best_state, f"{OUT_DIR}/small_unet_cone_best.pt")

    val_loss, val_cm = evaluate(model, val_loader)
    val_ious = iou_per_class(val_cm)
    test_loss, test_cm = evaluate(model, test_loader)
    test_ious = iou_per_class(test_cm)

    print(f"\nFINAL val  mIoU={np.nanmean(val_ious):.3f}  cone IoU={val_ious[1]:.3f}")
    print(f"FINAL test mIoU={np.nanmean(test_ious):.3f}  cone IoU={test_ious[1]:.3f}  "
          f"(held-out, never seen during training)")

    summary = {
        "device": str(DEVICE),
        "n_train": len(train_ds), "n_val": len(val_ds), "n_test": len(test_ds),
        "n_params": n_params, "n_epochs": N_EPOCHS,
        "val": {"miou": float(np.nanmean(val_ious)), "cone_iou": float(val_ious[1]),
                "bg_iou": float(val_ious[0]), "confusion_matrix": val_cm.tolist()},
        "test": {"miou": float(np.nanmean(test_ious)), "cone_iou": float(test_ious[1]),
                 "bg_iou": float(test_ious[0]), "confusion_matrix": test_cm.tolist()},
        "history": history,
        "note": "single region (Isidis Planitia, E084_N12), 144 samples total, "
                "positive-rate 91% (vs 12.1% full-dataset average) — small & skewed sample.",
    }
    with open(f"{OUT_DIR}/training_stats.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"saved {OUT_DIR}/training_stats.json")

    plot_history(history)
    plot_confusion_matrix(val_cm, "val")
    plot_confusion_matrix(test_cm, "test")
    plot_qualitative(model, test_ds, n_examples=4)


if __name__ == "__main__":
    main()
