"""
ConeQuest 2단계 추가 실험 — 2지역 합산 결과를 반영한 모델 용량·학습 전략 재설계

`conequest_unet_multiregion.py`에서 Isidis(단일지역 cone IoU 0.698)에 Acidalia Planitia를
합쳐서 재학습했더니 전체 평균이 0.603으로 떨어졌다 — 특히 Acidalia(0.508)가 발목을 잡았다.
Isidis(양성 91%)는 유지(0.682)됐지만 Acidalia(양성 46.9%, 더 어려운 분포)는 기존 SmallUNet
용량(48만 파라미터급)으로는 두 지역의 서로 다른 분포를 동시에 학습하기 벅찼다는 해석이었다.

이 스크립트는 그 해석을 직접 검증한다 — 데이터·분할·시드·에폭·LR은 전부 동일하게 두고
(공정 비교), 다음 두 가지만 바꾼다:
  1. 모델 용량 2배 — SmallUNet([16,32,64,128]) -> MediumUNet([32,64,128,256]), 깊이는 동일,
     채널만 2배로 늘려 "용량 부족"이 원인이었는지 검증한다.
  2. 클래스 가중 손실 — 두 지역의 양성 비율이 다르다(91% vs 46.9%) -> 학습셋 픽셀 분포 기준
     역빈도 가중치를 cross-entropy에 적용해 배경 픽셀이 훨씬 많은 Acidalia 쪽 신호가
     과소평가되지 않도록 한다.

conequest_unet_multiregion.py의 REGION_DIRS/load_splits/ConeQuestSeg/evaluate/
evaluate_by_region/plot_* 함수는 그대로 재사용하고(원본 파일 수정 없음), 모델 클래스와
학습 루프(가중 손실 적용)만 새로 작성한다. 플롯 함수들이 참조하는 OUT_DIR은 모듈 속성을
덮어써서 새 출력 폴더로 돌린다 — 원본 2지역 실험 결과물을 덮어쓰지 않기 위함.
"""
from __future__ import annotations

import json
import os
import random

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader

import conequest_unet_multiregion as base
from conequest_unet_multiregion import (
    REGION_DIRS, load_splits, ConeQuestSeg, evaluate, evaluate_by_region,
    plot_history, plot_confusion_matrix, plot_qualitative,
)
from train_terrain_segmentation import conv_block, iou_per_class
from conequest_unet_generalization import N_CLASSES, IGNORE_INDEX

OUT_DIR = "../outputs/conequest_unet_multiregion_v2"
os.makedirs(OUT_DIR, exist_ok=True)
base.OUT_DIR = OUT_DIR  # plot_history/plot_confusion_matrix/plot_qualitative가 이 경로에 저장하도록 리다이렉트

BATCH_SIZE = base.BATCH_SIZE
N_EPOCHS = base.N_EPOCHS
LR = base.LR
RNG_SEED = base.RNG_SEED  # 원본과 동일 시드 -> 동일 train/val/test 분할, 공정 비교
DEVICE = base.DEVICE


# ============================================================
# 1. 용량 2배 U-Net — SmallUNet과 깊이는 동일, 채널만 2배
# ============================================================

class MediumUNet(nn.Module):
    def __init__(self, n_classes=N_CLASSES):
        super().__init__()
        ch = [32, 64, 128, 256]  # SmallUNet의 [16,32,64,128] 대비 2배
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
# 2. 클래스 가중치 — 학습셋 픽셀 분포 기준 역빈도
# ============================================================

def compute_class_weights(train_ds):
    counts = np.zeros(N_CLASSES, dtype=np.int64)
    for i in range(len(train_ds)):
        _, mask = train_ds[i]
        m = mask.numpy()
        valid = m != IGNORE_INDEX
        counts += np.bincount(m[valid], minlength=N_CLASSES)
    freq = counts / counts.sum()
    weights = 1.0 / np.clip(freq, 1e-6, None)
    weights = weights / weights.sum() * N_CLASSES  # 평균 가중치가 1 근처가 되도록 정규화
    print(f"class pixel counts={counts.tolist()}  freq={freq.round(4).tolist()}  weights={weights.round(3).tolist()}")
    return torch.tensor(weights, dtype=torch.float32)


# ============================================================
# 3. 학습 루프 — 가중 손실만 다르고 나머지는 base와 동일 레시피
# ============================================================

def main():
    torch.manual_seed(RNG_SEED)
    random.seed(RNG_SEED)

    splits = load_splits()
    for s in splits:
        random.Random(RNG_SEED).shuffle(splits[s])
    by_region_counts = {s: {r: sum(1 for n in splits[s] if base.patch_region(n) == r) for r in REGION_DIRS}
                         for s in splits}
    print(f"split sizes: train={len(splits['train'])} val={len(splits['val'])} test={len(splits['test'])}")
    print("per-region counts:", json.dumps(by_region_counts, indent=2))

    train_ds = ConeQuestSeg(splits["train"], augment=True)
    val_ds = ConeQuestSeg(splits["val"], augment=False)
    test_ds = ConeQuestSeg(splits["test"], augment=False)

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)
    test_loader = DataLoader(test_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)

    class_weights = compute_class_weights(ConeQuestSeg(splits["train"], augment=False)).to(DEVICE)

    model = MediumUNet(n_classes=N_CLASSES).to(DEVICE)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"device={DEVICE}  params={n_params:,}  (SmallUNet 대비 참고: 약 479,000)")

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
            loss = F.cross_entropy(logits, mask, weight=class_weights, ignore_index=IGNORE_INDEX)
            loss.backward()
            optimizer.step()
            running_loss += loss.item(); n_batches += 1
        scheduler.step()

        train_loss = running_loss / max(n_batches, 1)
        val_loss, cm = evaluate(model, val_loader)  # base.evaluate: 비교 가능하도록 비가중 CE로 보고
        ious = iou_per_class(cm)
        miou = float(np.nanmean(ious))

        history["train_loss"].append(train_loss)
        history["val_loss"].append(val_loss)
        history["val_miou"].append(miou)

        if miou > best_miou:
            best_miou = miou
            best_state = {k: v.clone() for k, v in model.state_dict().items()}

        print(f"[{epoch + 1:>2}/{N_EPOCHS}] train_loss(weighted)={train_loss:.4f} val_loss(unweighted)={val_loss:.4f} "
              f"mIoU={miou:.3f} (bg={ious[0]:.3f} cone={ious[1]:.3f})")

    model.load_state_dict(best_state)
    torch.save(best_state, f"{OUT_DIR}/medium_unet_cone_best_multiregion.pt")

    val_loss, val_cm = evaluate(model, val_loader)
    val_ious = iou_per_class(val_cm)
    test_loss, test_cm = evaluate(model, test_loader)
    test_ious = iou_per_class(test_cm)
    test_by_region = evaluate_by_region(model, splits["test"])

    print(f"\nFINAL val  mIoU={np.nanmean(val_ious):.3f}  cone IoU={val_ious[1]:.3f}")
    print(f"FINAL test mIoU={np.nanmean(test_ious):.3f}  cone IoU={test_ious[1]:.3f}  "
          f"(held-out, never seen during training)")
    print("test by region:", json.dumps(test_by_region, indent=2))

    # 이전(v1, SmallUNet, 비가중) 결과와 직접 비교
    prev_path = "../outputs/conequest_unet_multiregion/training_stats.json"
    comparison = None
    if os.path.exists(prev_path):
        with open(prev_path) as f:
            prev = json.load(f)
        comparison = {
            "v1_small_unet_unweighted": {
                "test_cone_iou_overall": prev["test"]["cone_iou"],
                "test_by_region": prev["test_by_region"],
            },
            "v2_medium_unet_weighted": {
                "test_cone_iou_overall": float(test_ious[1]),
                "test_by_region": test_by_region,
            },
        }
        print("\n=== v1(SmallUNet, 비가중) vs v2(MediumUNet, 가중손실) ===")
        print(json.dumps(comparison, indent=2))

    summary = {
        "device": str(DEVICE),
        "model": "MediumUNet (ch=[32,64,128,256], SmallUNet 대비 2배 채널)",
        "class_weighted_loss": class_weights.cpu().tolist(),
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
        "note": "v1(conequest_unet_multiregion.py: SmallUNet, 비가중 손실) 대비 모델 용량을 2배로 늘리고 "
                "클래스 가중 손실을 적용 — 데이터/분할/시드/에폭/LR은 전부 동일하게 유지한 공정 비교.",
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
