"""
ConeQuest 2단계 추가 실험 v3 — 정규화(weight decay)만 추가, 그 외엔 v1(SmallUNet, 비가중)과 완전히 동일

v2(용량 2배 + 클래스 가중 손실)는 가설과 반대로 더 나빠졌다 — 학습 곡선이 중간 에폭에서 크게
요동치는 불안정한 패턴을 보였다. v2 보고서의 다음 단계 제안 중 "정규화(dropout, weight decay)
강화"를 가장 단순한 형태로 먼저 시도한다: 아키텍처(SmallUNet, 48만 파라미터)와 손실 함수(비가중
cross-entropy)는 v1과 완전히 동일하게 두고, 옵티마이저만 Adam -> AdamW(weight_decay=1e-4)로
바꾼다. 용량 증가와 손실 재가중이라는 두 confound를 모두 제거하고 "표준 L2 정규화 하나만
추가하면 2지역 일반화가 나아지는가"를 깨끗하게 분리해서 검증한다.

conequest_unet_multiregion.py의 REGION_DIRS/load_splits/ConeQuestSeg/evaluate/evaluate_by_region/
plot_* 함수와 SmallUNet 그대로 재사용(원본 파일 수정 없음). plot_* 함수들이 참조하는 OUT_DIR은
모듈 속성을 덮어써서 새 출력 폴더로 돌린다.
"""
from __future__ import annotations

import json
import os
import random

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

import conequest_unet_multiregion as base
from conequest_unet_multiregion import (
    REGION_DIRS, load_splits, ConeQuestSeg, evaluate, evaluate_by_region,
    plot_history, plot_confusion_matrix, plot_qualitative,
)
from train_terrain_segmentation import SmallUNet, iou_per_class
from conequest_unet_generalization import N_CLASSES, IGNORE_INDEX

OUT_DIR = "../outputs/conequest_unet_multiregion_v3"
os.makedirs(OUT_DIR, exist_ok=True)
base.OUT_DIR = OUT_DIR

BATCH_SIZE = base.BATCH_SIZE
N_EPOCHS = base.N_EPOCHS
LR = base.LR
WEIGHT_DECAY = 1e-4  # 유일한 변경점 — 표준적인 가벼운 L2 정규화 값
RNG_SEED = base.RNG_SEED  # 원본과 동일 시드 -> 동일 train/val/test 분할, 공정 비교
DEVICE = base.DEVICE


def main():
    torch.manual_seed(RNG_SEED)
    random.seed(RNG_SEED)

    splits = load_splits()
    for s in splits:
        random.Random(RNG_SEED).shuffle(splits[s])
    by_region_counts = {s: {r: sum(1 for n in splits[s] if base.patch_region(n) == r) for r in REGION_DIRS}
                         for s in splits}
    print(f"split sizes: train={len(splits['train'])} val={len(splits['val'])} test={len(splits['test'])}")

    train_ds = ConeQuestSeg(splits["train"], augment=True)
    val_ds = ConeQuestSeg(splits["val"], augment=False)
    test_ds = ConeQuestSeg(splits["test"], augment=False)

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)
    test_loader = DataLoader(test_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)

    model = SmallUNet(n_classes=N_CLASSES).to(DEVICE)  # v1과 동일한 용량 — 의도적으로 바꾸지 않음
    n_params = sum(p.numel() for p in model.parameters())
    print(f"device={DEVICE}  params={n_params:,}  weight_decay={WEIGHT_DECAY}")

    optimizer = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
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
            loss = F.cross_entropy(logits, mask, ignore_index=IGNORE_INDEX)  # v1과 동일: 비가중
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
    torch.save(best_state, f"{OUT_DIR}/small_unet_cone_best_multiregion_v3.pt")

    val_loss, val_cm = evaluate(model, val_loader)
    val_ious = iou_per_class(val_cm)
    test_loss, test_cm = evaluate(model, test_loader)
    test_ious = iou_per_class(test_cm)
    test_by_region = evaluate_by_region(model, splits["test"])

    print(f"\nFINAL val  mIoU={np.nanmean(val_ious):.3f}  cone IoU={val_ious[1]:.3f}")
    print(f"FINAL test mIoU={np.nanmean(test_ious):.3f}  cone IoU={test_ious[1]:.3f}  (held-out)")
    print("test by region:", json.dumps(test_by_region, indent=2))

    prev_path = "../outputs/conequest_unet_multiregion/training_stats.json"
    comparison = None
    if os.path.exists(prev_path):
        with open(prev_path) as f:
            prev = json.load(f)
        comparison = {
            "v1_small_unet_no_wd": {
                "test_cone_iou_overall": prev["test"]["cone_iou"],
                "test_by_region": prev["test_by_region"],
            },
            "v3_small_unet_weight_decay": {
                "test_cone_iou_overall": float(test_ious[1]),
                "test_by_region": test_by_region,
            },
        }
        print("\n=== v1(SmallUNet, weight_decay=0) vs v3(SmallUNet, weight_decay=1e-4) ===")
        print(json.dumps(comparison, indent=2))

    summary = {
        "device": str(DEVICE),
        "model": "SmallUNet (v1과 동일 용량, 48만 파라미터)",
        "optimizer": f"AdamW, weight_decay={WEIGHT_DECAY} (v1은 Adam, weight_decay=0)",
        "loss": "비가중 cross-entropy (v1과 동일)",
        "n_train": len(train_ds), "n_val": len(val_ds), "n_test": len(test_ds),
        "n_params": n_params, "n_epochs": N_EPOCHS,
        "regions": list(REGION_DIRS.keys()),
        "per_region_split_counts": by_region_counts,
        "val": {"miou": float(np.nanmean(val_ious)), "cone_iou": float(val_ious[1]),
                "bg_iou": float(val_ious[0]), "confusion_matrix": val_cm.tolist()},
        "test": {"miou": float(np.nanmean(test_ious)), "cone_iou": float(test_ious[1]),
                 "bg_iou": float(test_ious[0]), "confusion_matrix": test_cm.tolist()},
        "test_by_region": test_by_region,
        "history": history,
        "comparison_vs_v1": comparison,
        "note": "v1(conequest_unet_multiregion.py) 대비 AdamW weight_decay=1e-4만 추가 — 용량과 손실 함수는 "
                "동일하게 유지해 정규화 하나만의 효과를 분리 측정.",
    }
    with open(f"{OUT_DIR}/training_stats.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"saved {OUT_DIR}/training_stats.json")

    plot_history(history)
    plot_confusion_matrix(val_cm, "val")
    plot_confusion_matrix(test_cm, "test")
    plot_qualitative(model, test_ds, splits["test"], n_examples=6)


if __name__ == "__main__":
    main()
