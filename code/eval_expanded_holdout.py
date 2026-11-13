"""
확장된 held-out 20장 — 그림자 CV / 모델 단독 / 캐스케이드 융합 재평가

expand_holdout_set.py로 받은 20장(기존 train/val 서브셋, 기존 3장짜리 held-out과
전부 겹치지 않음)에서 세 방법을 다시 비교한다. 캐스케이드 임계값은 cascade_fusion_
detection.py가 validation 60장에서 이미 튠한 0.20을 그대로 쓴다 — 여기서 새로
튜닝하면 held-out이 아니게 된다.

기존 3장짜리 세트는 2장이 big_rock 0%인 퇴화 샘플이라 지표가 사실상 이미지 1장에서만
나온 것과 같았다(cascade_fusion_stats.json의 mean_iou=0.170이 실제로는 [0.340, 0.0]
두 값의 평균이었고, 세 번째 이미지는 NaN으로 집계에서 빠졌다). 이번엔 N=20이라 그런
단일 이미지 의존이 훨씬 줄어든다.
"""
from __future__ import annotations

import glob
import json
import os
import numpy as np
import torch
from PIL import Image

from train_terrain_segmentation import SmallUNet
from boulder_detection_no_labels import detect_boulder_shadows
from eval_trained_model_on_holdout import evaluate_big_rock
from cascade_fusion_detection import precompute_blobs_and_probs, apply_threshold, as_label_mask

CKPT = "../outputs/terrain_segmentation/small_unet_best.pt"
HOLDOUT_V2_DIR = "../data/ai4mars_holdout_v2"
OUT_DIR = "../outputs/terrain_segmentation"
CASCADE_THRESH = 0.20  # cascade_fusion_detection.py가 val 60장에서 튠한 값, 재튜닝 없이 그대로 재사용


def main():
    model = SmallUNet()
    model.load_state_dict(torch.load(CKPT, map_location="cpu"))
    model.eval()

    from train_terrain_segmentation import IMG_SIZE

    img_paths = sorted(glob.glob(f"{HOLDOUT_V2_DIR}/images/*"))
    print(f"확장 held-out {len(img_paths)}장 평가 (캐스케이드 임계값={CASCADE_THRESH}, 재튜닝 없음)\n")

    cv_results, model_results, cascade_results = [], [], []
    for img_path in img_paths:
        stem = os.path.splitext(os.path.basename(img_path))[0]
        mask_path = f"{HOLDOUT_V2_DIR}/masks/{stem}.png"
        if not os.path.exists(mask_path):
            print(f"  [마스크 없음, 건너뜀] {stem}")
            continue
        gray = np.array(Image.open(img_path).convert("L"))
        label = np.array(Image.open(mask_path))
        orig_size = (gray.shape[1], gray.shape[0])

        # 1) 그림자 기반 고전 CV
        cv_mask, _ = detect_boulder_shadows(gray)
        m_cv = evaluate_big_rock(as_label_mask(cv_mask), label)
        m_cv["name"] = stem
        cv_results.append(m_cv)

        # 2) 학습 모델 단독 (argmax, eval_trained_model_on_holdout.py와 동일 방식)
        img_small = Image.fromarray(gray).resize((IMG_SIZE, IMG_SIZE), Image.BILINEAR)
        x = torch.from_numpy(np.array(img_small, dtype=np.float32) / 255.0).unsqueeze(0).unsqueeze(0)
        with torch.no_grad():
            logits = model(x)
        pred_small = logits.argmax(dim=1).squeeze(0).numpy().astype(np.uint8)
        pred_full = np.array(Image.fromarray(pred_small).resize(orig_size, Image.NEAREST))
        m_model = evaluate_big_rock(pred_full, label)
        m_model["name"] = stem
        model_results.append(m_model)

        # 3) 캐스케이드 융합 (고정 임계값 0.20, 재튜닝 없음)
        blobs = precompute_blobs_and_probs(gray, model)
        detected = apply_threshold(gray.shape, blobs, CASCADE_THRESH)
        m_cascade = evaluate_big_rock(as_label_mask(detected), label)
        m_cascade["name"] = stem
        cascade_results.append(m_cascade)

        print(f"  [{stem}]  GT {m_cv['gt_rock_pct']:5.1f}%  "
              f"CV IoU {m_cv['iou']:.3f}  모델 IoU {m_model['iou']:.3f}  캐스케이드 IoU {m_cascade['iou']:.3f}")

    def agg(results, key):
        vals = [r[key] for r in results]
        n_nan = sum(1 for v in vals if v != v)
        strict_vals = [0.0 if v != v else v for v in vals]
        return {
            "nanmean": float(np.nanmean(vals)),
            "n_nan": n_nan, "n_total": len(vals),
            "strict_mean_nan_as_zero": float(np.mean(strict_vals)),
        }

    summary = {
        "n_images": len(cv_results),
        "cascade_threshold_reused": CASCADE_THRESH,
        "classical_cv": {
            "per_sample": cv_results,
            "iou": agg(cv_results, "iou"), "precision": agg(cv_results, "precision"), "recall": agg(cv_results, "recall"),
        },
        "trained_model_only": {
            "per_sample": model_results,
            "iou": agg(model_results, "iou"), "precision": agg(model_results, "precision"), "recall": agg(model_results, "recall"),
        },
        "cascade_fusion": {
            "per_sample": cascade_results,
            "iou": agg(cascade_results, "iou"), "precision": agg(cascade_results, "precision"), "recall": agg(cascade_results, "recall"),
        },
        "original_3image_holdout_for_reference": {
            "classical_cv_only_iou": 0.120, "trained_model_only_iou": 0.052, "cascade_fusion_iou": 0.170,
            "note": "3장 중 2장이 big_rock 0%인 퇴화 샘플 — 사실상 1장 점수에 의존, 이번 20장 결과로 대체",
        },
    }

    print("\n" + "=" * 70)
    print(f"{'방법':<14}{'IoU(nanmean)':>14}{'IoU(NaN=0)':>14}{'NaN 개수':>10}")
    for label_name, key in [("그림자 CV", "classical_cv"), ("모델 단독", "trained_model_only"), ("캐스케이드 융합", "cascade_fusion")]:
        a = summary[key]["iou"]
        print(f"{label_name:<14}{a['nanmean']:>14.3f}{a['strict_mean_nan_as_zero']:>14.3f}{a['n_nan']:>6}/{a['n_total']}")

    with open(f"{OUT_DIR}/expanded_holdout_stats.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nsaved {OUT_DIR}/expanded_holdout_stats.json")


if __name__ == "__main__":
    main()
