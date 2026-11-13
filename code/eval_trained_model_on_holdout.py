"""
학습된 모델 vs 그림자 기반 고전 CV — 같은 3장짜리 held-out 세트로 직접 비교

boulder_detection_no_labels.py가 big_rock IoU 0.120(평균)을 낸 바로 그 3장
(data/ai4mars_samples/)에, 이번에 학습한 모델을 그대로 돌려 같은 지표로 평가한다.
이 3장은 fetch_ai4mars_subset.py가 받은 학습/검증 서브셋과 겹치지 않는다(확인됨) —
모델 입장에서는 완전히 처음 보는 이미지.
"""
import json
import numpy as np
import torch
from PIL import Image

from train_terrain_segmentation import SmallUNet, IMG_SIZE, N_CLASSES

SAMPLE_DIR = "../data/ai4mars_samples"
OUT_DIR = "../outputs/terrain_segmentation"
CKPT = f"{OUT_DIR}/small_unet_best.pt"

SAMPLES = [
    "NLB_486372898EDR_F0481570NCAM00322M1",
    "NLB_542921313EDR_F0612232NCAM00320M1",
    "NLB_461147286EDR_F0401240NCAM00385M1",
]


def evaluate_big_rock(pred_mask, label_mask):
    gt_rock = label_mask == 3
    gt_unlabeled = label_mask == 255
    valid = ~gt_unlabeled
    det = pred_mask == 3

    tp = (det & gt_rock & valid).sum()
    fp = (det & ~gt_rock & valid).sum()
    fn = (~det & gt_rock & valid).sum()
    precision = tp / (tp + fp) if (tp + fp) > 0 else float("nan")
    recall = tp / (tp + fn) if (tp + fn) > 0 else float("nan")
    iou = tp / (tp + fp + fn) if (tp + fp + fn) > 0 else float("nan")
    return {
        "precision": float(precision), "recall": float(recall), "iou": float(iou),
        "gt_rock_pct": float(gt_rock[valid].mean() * 100),
        "detected_pct": float(det[valid].mean() * 100),
    }


def main():
    model = SmallUNet()
    model.load_state_dict(torch.load(CKPT, map_location="cpu"))
    model.eval()

    results = []
    for name in SAMPLES:
        img = Image.open(f"{SAMPLE_DIR}/{name}.jpg").convert("L")
        label = np.array(Image.open(f"{SAMPLE_DIR}/{name}_mask.png"))
        orig_size = img.size  # (W,H)

        img_small = img.resize((IMG_SIZE, IMG_SIZE), Image.BILINEAR)
        x = torch.from_numpy(np.array(img_small, dtype=np.float32) / 255.0).unsqueeze(0).unsqueeze(0)
        with torch.no_grad():
            logits = model(x)
        pred_small = logits.argmax(dim=1).squeeze(0).numpy().astype(np.uint8)

        pred_full = np.array(
            Image.fromarray(pred_small).resize(orig_size, Image.NEAREST)
        )

        metrics = evaluate_big_rock(pred_full, label)
        metrics["name"] = name
        results.append(metrics)
        print(f"[{name}]  GT big_rock {metrics['gt_rock_pct']:.1f}%  "
              f"Precision {metrics['precision']:.3f}  Recall {metrics['recall']:.3f}  "
              f"IoU {metrics['iou']:.3f}")

    mean_iou = np.nanmean([r["iou"] for r in results])
    mean_p = np.nanmean([r["precision"] for r in results])
    mean_r = np.nanmean([r["recall"] for r in results])
    print(f"\n평균 — Precision {mean_p:.3f} / Recall {mean_r:.3f} / IoU {mean_iou:.3f}")
    print("비교: 그림자 기반 고전 CV(boulder_detection_no_labels.py) 평균 IoU 0.120")

    with open(f"{OUT_DIR}/holdout_comparison_stats.json", "w") as f:
        json.dump({
            "samples": results,
            "mean_precision": float(mean_p), "mean_recall": float(mean_r), "mean_iou": float(mean_iou),
            "classical_cv_baseline_iou": 0.120,
        }, f, indent=2)
    print(f"saved {OUT_DIR}/holdout_comparison_stats.json")


if __name__ == "__main__":
    main()
