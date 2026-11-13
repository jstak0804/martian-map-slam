"""
"데이터셋을 여러 개 결합하면 어떨까?" — MSL+MER+M2020 혼합 학습

train_terrain_segmentation.py와 정확히 같은 모델·하이퍼파라미터·총 예산(train 300 /
val 60)을 쓰되, 이번엔 MSL 단일 출처가 아니라 MSL 150 + MER 100 + M2020 50(val도
동일 비율)으로 섞은 데이터로 처음부터 다시 학습한다 — "데이터 양은 그대로, 출처
다양성만 추가"했을 때 효과가 있는지를 보는 공정한 비교.

평가는 두 가지:
  ① 이 혼합 데이터셋 자체의 val split (MSL+MER+M2020 섞임)
  ② 기존 MSL-only 베이스라인과 완전히 같은 held-out 3장(MSL 전용) — 교차 비교용
"""
from __future__ import annotations

import json
import os

import numpy as np
import torch
from torch.utils.data import DataLoader

from train_terrain_segmentation import (
    SmallUNet, AI4MarsSeg, N_CLASSES, CLASS_NAMES, IGNORE_INDEX, IMG_SIZE,
    BATCH_SIZE, N_EPOCHS, LR, RNG_SEED, DEVICE,
    confusion_matrix, iou_per_class, evaluate, plot_history, plot_confusion_matrix,
    plot_qualitative,
)
import train_terrain_segmentation as base_module

DATA_DIR = "../data/ai4mars_multirover"
OUT_DIR = "../outputs/terrain_segmentation_multirover"
os.makedirs(OUT_DIR, exist_ok=True)

HOLDOUT_SAMPLE_DIR = "../data/ai4mars_samples"
HOLDOUT_SAMPLES = [
    "NLB_486372898EDR_F0481570NCAM00322M1",
    "NLB_542921313EDR_F0612232NCAM00320M1",
    "NLB_461147286EDR_F0401240NCAM00385M1",
]


def main():
    torch.manual_seed(RNG_SEED)
    import random
    random.seed(RNG_SEED)

    # train_terrain_segmentation의 전역 DATA_DIR/OUT_DIR을 이 실험용으로 바꿔치기
    base_module.DATA_DIR = DATA_DIR
    base_module.OUT_DIR = OUT_DIR

    train_ds = AI4MarsSeg("train", augment=True)
    val_ds = AI4MarsSeg("val", augment=False)
    print(f"[혼합 데이터셋] train {len(train_ds)}장, val {len(val_ds)}장")

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=2)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=2)

    model = SmallUNet().to(DEVICE)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"모델 파라미터 수: {n_params:,} (MSL-only 베이스라인과 동일 아키텍처)")

    optimizer = torch.optim.Adam(model.parameters(), lr=LR)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=N_EPOCHS)

    history = {"train_loss": [], "val_loss": [], "val_miou": [], "val_iou_per_class": []}
    best_miou, best_state = -1.0, None

    import torch.nn.functional as F
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
    torch.save(best_state, f"{OUT_DIR}/small_unet_multirover_best.pt")
    print(f"\n최고 mIoU={best_miou:.3f} 모델 저장: {OUT_DIR}/small_unet_multirover_best.pt")

    val_loss, cm = evaluate(model, val_loader)
    ious = iou_per_class(cm)

    plot_history(history)
    plot_confusion_matrix(cm)
    plot_qualitative(model, val_ds, n_examples=4)

    # ---- 교차 비교: MSL-only 베이스라인과 동일한 held-out 3장 ----
    print("\n[교차 비교] MSL-only 베이스라인과 동일한 held-out 3장 평가...")
    from eval_trained_model_on_holdout import evaluate_big_rock
    from PIL import Image

    holdout_results = []
    for name in HOLDOUT_SAMPLES:
        img = Image.open(f"{HOLDOUT_SAMPLE_DIR}/{name}.jpg").convert("L")
        label = np.array(Image.open(f"{HOLDOUT_SAMPLE_DIR}/{name}_mask.png"))
        orig_size = img.size

        img_small = img.resize((IMG_SIZE, IMG_SIZE), Image.BILINEAR)
        x = torch.from_numpy(np.array(img_small, dtype=np.float32) / 255.0).unsqueeze(0).unsqueeze(0)
        with torch.no_grad():
            logits = model(x)
        pred_small = logits.argmax(dim=1).squeeze(0).numpy().astype(np.uint8)
        pred_full = np.array(Image.fromarray(pred_small).resize(orig_size, Image.NEAREST))

        metrics = evaluate_big_rock(pred_full, label)
        metrics["name"] = name
        holdout_results.append(metrics)
        print(f"  [{name}] Precision {metrics['precision']:.3f}  Recall {metrics['recall']:.3f}  "
              f"IoU {metrics['iou']:.3f}")

    mean_holdout_iou = float(np.nanmean([r["iou"] for r in holdout_results]))
    mean_holdout_p = float(np.nanmean([r["precision"] for r in holdout_results]))
    mean_holdout_r = float(np.nanmean([r["recall"] for r in holdout_results]))
    print(f"\n  held-out 평균 — Precision {mean_holdout_p:.3f} / Recall {mean_holdout_r:.3f} / "
          f"IoU {mean_holdout_iou:.3f}")
    print(f"  비교: MSL-only 베이스라인 held-out IoU 0.052 / 그림자 CV 0.120")

    summary = {
        "n_train": len(train_ds), "n_val": len(val_ds), "n_params": n_params,
        "sources": {"msl": 150, "mer": 100, "m2020": 50, "val_msl": 30, "val_mer": 20, "val_m2020": 10},
        "best_val_miou": float(np.nanmean(ious)),
        "val_iou_per_class": {CLASS_NAMES[i]: float(ious[i]) for i in range(N_CLASSES)},
        "confusion_matrix": cm.tolist(),
        "history": history,
        "holdout_vs_msl_baseline": {
            "multirover_mean_precision": mean_holdout_p,
            "multirover_mean_recall": mean_holdout_r,
            "multirover_mean_iou": mean_holdout_iou,
            "msl_only_baseline_iou": 0.052,
            "classical_cv_baseline_iou": 0.120,
            "per_sample": holdout_results,
        },
    }
    with open(f"{OUT_DIR}/training_stats.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"saved {OUT_DIR}/training_stats.json")


if __name__ == "__main__":
    main()
