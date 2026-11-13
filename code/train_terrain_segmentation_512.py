"""
256 -> 512 해상도 재학습 — "낮은 재현율의 유력한 원인" ①을 실제로 검증

report 08에서 big_rock 재현율이 낮았던(held-out 10.4%) 유력한 원인으로 "256×256
다운샘플링이 작고 먼 바위의 디테일을 지웠을 가능성"을 지목했다. 이 스크립트는 그
가설을 실제로 검증한다 — 다른 건 전부 그대로 두고 입력 해상도만 256→512로 올려
같은 MSL-only 데이터(299train/60val)로 처음부터 재학습한다.

전처리 확인: AI4Mars MSL 서브셋 359장은 전부 1024×1024 정사각형이라(확인됨),
512로 리사이즈해도 화면비 왜곡이 없다 — 다중 로버 실험에서 M2020의 1280×240
파노라마가 겪었던 종횡비 문제가 여기선 애초에 발생하지 않는다. 따라서 별도의
letterbox/pad 전처리는 필요 없고, 단순 2배 다운샘플(1024→512, 기존은 4배
1024→256)이 유일한 변경점이다.

모델 구조(483K 파라미터 작은 U-Net)는 완전 합성곱이라 입력 해상도를 그대로
받아들인다 — 구조 변경 없이 해상도만 바꾼 공정한 비교.
"""
from __future__ import annotations

import json
import os

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

from train_terrain_segmentation import (
    SmallUNet, AI4MarsSeg, N_CLASSES, CLASS_NAMES, IGNORE_INDEX,
    BATCH_SIZE, N_EPOCHS, LR, RNG_SEED, DEVICE,
    iou_per_class, evaluate, plot_history, plot_confusion_matrix, plot_qualitative,
)
import train_terrain_segmentation as base_module

NEW_IMG_SIZE = 512
OUT_DIR = "../outputs/terrain_segmentation_512"
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

    # train_terrain_segmentation의 전역 IMG_SIZE/OUT_DIR을 이 실험용으로 바꿔치기
    # (DATA_DIR은 그대로 — 기존 MSL-only 서브셋 재사용, 전부 1024x1024라 왜곡 없음)
    base_module.IMG_SIZE = NEW_IMG_SIZE
    base_module.OUT_DIR = OUT_DIR

    train_ds = AI4MarsSeg("train", augment=True)
    val_ds = AI4MarsSeg("val", augment=False)
    print(f"[512 해상도] train {len(train_ds)}장, val {len(val_ds)}장, IMG_SIZE={base_module.IMG_SIZE}")

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=2)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=2)

    model = SmallUNet().to(DEVICE)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"모델 파라미터 수: {n_params:,} (256 해상도 베이스라인과 동일 아키텍처)")

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
    torch.save(best_state, f"{OUT_DIR}/small_unet_512_best.pt")
    print(f"\n최고 mIoU={best_miou:.3f} 모델 저장: {OUT_DIR}/small_unet_512_best.pt")

    val_loss, cm = evaluate(model, val_loader)
    ious = iou_per_class(cm)

    plot_history(history)
    plot_confusion_matrix(cm)
    plot_qualitative(model, val_ds, n_examples=4)

    # ---- 교차 비교: 256 베이스라인과 동일한 held-out 3장 ----
    print("\n[교차 비교] 256 베이스라인과 동일한 held-out 3장 평가...")
    from eval_trained_model_on_holdout import evaluate_big_rock
    from PIL import Image

    holdout_results = []
    for name in HOLDOUT_SAMPLES:
        img = Image.open(f"{HOLDOUT_SAMPLE_DIR}/{name}.jpg").convert("L")
        label = np.array(Image.open(f"{HOLDOUT_SAMPLE_DIR}/{name}_mask.png"))
        orig_size = img.size

        img_small = img.resize((NEW_IMG_SIZE, NEW_IMG_SIZE), Image.BILINEAR)
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
    print(f"  비교: 256 베이스라인 held-out Precision 0.473 / Recall 0.104 / IoU 0.052")
    print(f"  비교: 그림자 CV held-out IoU 0.120")

    summary = {
        "img_size": NEW_IMG_SIZE, "n_train": len(train_ds), "n_val": len(val_ds), "n_params": n_params,
        "best_val_miou": float(np.nanmean(ious)),
        "val_iou_per_class": {CLASS_NAMES[i]: float(ious[i]) for i in range(N_CLASSES)},
        "confusion_matrix": cm.tolist(),
        "history": history,
        "holdout_vs_256_baseline": {
            "512_mean_precision": mean_holdout_p, "512_mean_recall": mean_holdout_r, "512_mean_iou": mean_holdout_iou,
            "baseline_256_precision": 0.473, "baseline_256_recall": 0.104, "baseline_256_iou": 0.052,
            "classical_cv_iou": 0.120,
            "per_sample": holdout_results,
        },
    }
    with open(f"{OUT_DIR}/training_stats.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"saved {OUT_DIR}/training_stats.json")


if __name__ == "__main__":
    main()
