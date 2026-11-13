"""
고전 CV + 학습 모델 캐스케이드 융합 — held-out 음성 결과를 실제로 개선

report 08에서 드러난 문제: 그림자 기반 고전 CV는 재현율은 높지만 오탐이 심하고
(바위 없는 사진에서 64.7% 오탐), 학습 모델은 오탐은 거의 없지만 재현율이 낮다
(10.4%). 두 검출기의 실패 양상이 정반대라는 건 거꾸로 "서로를 보완할 수 있다"는
뜻이기도 하다 — 전통적인 2단계 캐스케이드 검출 구조(1단계: 재현율 높은 후보 생성,
2단계: 정밀도 높은 검증)를 그대로 적용한다.

방법:
  1. 고전 CV(detect_boulder_shadows)로 후보 블롭을 생성한다 — 재현율은 이미 충분히
     높으니 후보 생성 단계로만 쓴다.
  2. 학습 모델의 big_rock 소프트맥스 확률 맵으로 각 블롭을 검증한다 — 블롭 내부의
     평균 확률이 임계값을 넘는 것만 최종 검출로 인정한다.
  3. 임계값은 테스트셋(held-out 3장)이 아니라 **validation 60장**에서만 튜닝한다 —
     held-out은 마지막에 한 번만 평가해 과적합(치팅) 없이 정직하게 비교한다.
"""
from __future__ import annotations

import json
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

from train_terrain_segmentation import SmallUNet, IMG_SIZE, AI4MarsSeg
from boulder_detection_no_labels import detect_boulder_shadows
from eval_trained_model_on_holdout import evaluate_big_rock, SAMPLE_DIR as HOLDOUT_DIR, SAMPLES as HOLDOUT_SAMPLES

CKPT = "../outputs/terrain_segmentation/small_unet_best.pt"
VAL_DIR = "../data/ai4mars_subset/val"
OUT_DIR = "../outputs/terrain_segmentation"

THRESH_SWEEP = np.arange(0.0, 1.01, 0.05)


def model_big_rock_prob(model, gray_img: Image.Image, orig_size) -> np.ndarray:
    """학습 모델의 big_rock 클래스 소프트맥스 확률을 원본 해상도로 되돌려 반환."""
    img_small = gray_img.resize((IMG_SIZE, IMG_SIZE), Image.BILINEAR)
    x = torch.from_numpy(np.array(img_small, dtype=np.float32) / 255.0).unsqueeze(0).unsqueeze(0)
    with torch.no_grad():
        logits = model(x)
        probs = F.softmax(logits, dim=1)[0, 3].numpy()  # class 3 = big_rock
    prob_img = Image.fromarray((probs * 255).astype(np.uint8)).resize(orig_size, Image.BILINEAR)
    return np.array(prob_img, dtype=np.float32) / 255.0


def precompute_blobs_and_probs(gray: np.ndarray, model):
    """이미지당 단 한 번만: 그림자 블롭(컨투어)과 모델 확률맵을 미리 계산해둔다.
    임계값 스윕 시 이 결과를 재사용하면 이미지당 중복 추론을 피할 수 있다.

    메모리 주의: 블롭이 수백 개(한 이미지에 500개+)까지 나올 수 있어서, 블롭마다
    전체 이미지 크기(1024x1024) bool 마스크를 따로 들고 있으면 이미지 한 장만으로도
    수백 MB~GB까지 치솟아 OOM이 난다(실제로 한 번 터졌다) — 바운딩박스 안으로 잘라낸
    작은 마스크만 저장한다."""
    import cv2
    orig_size = (gray.shape[1], gray.shape[0])
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    _, dark = cv2.threshold(blurred, 35, 255, cv2.THRESH_BINARY_INV)
    kernel = np.ones((3, 3), np.uint8)
    dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, kernel)
    contours, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    prob_map = model_big_rock_prob(model, Image.fromarray(gray), orig_size)

    blobs = []  # (y0, x0, local_bool_mask, mean_prob) — local_bool_mask는 bbox 크기만큼만
    for c in contours:
        area = cv2.contourArea(c)
        if area < 6:
            continue
        x, y, w, h = cv2.boundingRect(c)
        local_mask = np.zeros((h, w), dtype=np.uint8)
        shifted = c - [x, y]
        cv2.drawContours(local_mask, [shifted], -1, 1, thickness=-1)
        local_bool = local_mask.astype(bool)
        prob_crop = prob_map[y:y + h, x:x + w]
        mean_prob = float(prob_crop[local_bool].mean()) if local_bool.any() else 0.0
        blobs.append((y, x, local_bool, mean_prob))
    return blobs


def apply_threshold(gray_shape, blobs, thresh: float) -> np.ndarray:
    verified = np.zeros(gray_shape, dtype=bool)
    for y, x, local_bool, mean_prob in blobs:
        if mean_prob >= thresh:
            h, w = local_bool.shape
            verified[y:y + h, x:x + w] |= local_bool
    return verified


def cascade_detect(gray: np.ndarray, model, thresh: float) -> np.ndarray:
    """단일 이미지용 편의 함수(최종 held-out 평가에서만 사용)."""
    blobs = precompute_blobs_and_probs(gray, model)
    return apply_threshold(gray.shape, blobs, thresh)


def as_label_mask(detected_bool: np.ndarray) -> np.ndarray:
    """evaluate_big_rock은 label-값 배열(3=big_rock)을 기대하므로 bool 마스크를 변환."""
    return np.where(detected_bool, 3, 0)


def evaluate_on_set(precomputed, thresh):
    ious = []
    for gray_shape, blobs, label in precomputed:
        detected = apply_threshold(gray_shape, blobs, thresh)
        m = evaluate_big_rock(as_label_mask(detected), label)
        if not np.isnan(m["iou"]):
            ious.append(m["iou"])
    return float(np.mean(ious)) if ious else float("nan")


def main():
    model = SmallUNet()
    model.load_state_dict(torch.load(CKPT, map_location="cpu"))
    model.eval()

    print("validation 60장 로딩 + 블롭/확률맵 사전계산 (이미지당 1회만)...")
    import glob, os
    precomputed = []
    for i, img_path in enumerate(glob.glob(f"{VAL_DIR}/images/*")):
        stem = os.path.splitext(os.path.basename(img_path))[0]
        mask_path = f"{VAL_DIR}/masks/{stem}.png"
        gray = np.array(Image.open(img_path).convert("L"))
        label = np.array(Image.open(mask_path))
        blobs = precompute_blobs_and_probs(gray, model)
        precomputed.append((gray.shape, blobs, label))
        if (i + 1) % 20 == 0:
            print(f"  {i + 1}장 처리됨")
    print(f"  {len(precomputed)}장 완료")

    print("\n임계값 스윕 (validation에서만, 사전계산 재사용이라 빠름)...")
    best_thresh, best_iou = 0.0, -1.0
    sweep_results = []
    for t in THRESH_SWEEP:
        iou = evaluate_on_set(precomputed, t)
        sweep_results.append({"thresh": float(t), "val_mean_iou": iou})
        marker = ""
        if not np.isnan(iou) and iou > best_iou:
            best_iou, best_thresh = iou, t
            marker = "  <- best so far"
        print(f"  thresh={t:.2f}  val_mean_iou={iou:.4f}{marker}")

    print(f"\n선택된 임계값: {best_thresh:.2f} (validation mean IoU {best_iou:.4f})")

    print("\n[최종 평가] held-out 3장 — 임계값은 이미 고정, 여기서는 딱 한 번만 측정")
    holdout_results = []
    for name in HOLDOUT_SAMPLES:
        gray = np.array(Image.open(f"{HOLDOUT_DIR}/{name}.jpg").convert("L"))
        label = np.array(Image.open(f"{HOLDOUT_DIR}/{name}_mask.png"))
        detected = cascade_detect(gray, model, best_thresh)
        m = evaluate_big_rock(as_label_mask(detected), label)
        m["name"] = name
        holdout_results.append(m)
        print(f"  [{name}] Precision {m['precision']:.3f}  Recall {m['recall']:.3f}  IoU {m['iou']:.3f}")

    mean_p = float(np.nanmean([r["precision"] for r in holdout_results]))
    mean_r = float(np.nanmean([r["recall"] for r in holdout_results]))
    mean_iou = float(np.nanmean([r["iou"] for r in holdout_results]))

    print(f"\n캐스케이드 융합 held-out 평균 — Precision {mean_p:.3f} / Recall {mean_r:.3f} / IoU {mean_iou:.3f}")
    print(f"비교 — 그림자 CV만: Precision 0.279 / Recall 0.386 / IoU 0.120")
    print(f"비교 — 학습 모델만: Precision 0.473 / Recall 0.104 / IoU 0.052")

    with open(f"{OUT_DIR}/cascade_fusion_stats.json", "w") as f:
        json.dump({
            "threshold_sweep": sweep_results,
            "selected_threshold": float(best_thresh),
            "selected_threshold_val_iou": float(best_iou),
            "holdout_results": {
                "per_sample": holdout_results,
                "mean_precision": mean_p, "mean_recall": mean_r, "mean_iou": mean_iou,
            },
            "baselines": {
                "classical_cv_only": {"precision": 0.279, "recall": 0.386, "iou": 0.120},
                "trained_model_only": {"precision": 0.473, "recall": 0.104, "iou": 0.052},
            },
        }, f, indent=2)
    print(f"\nsaved {OUT_DIR}/cascade_fusion_stats.json")


if __name__ == "__main__":
    main()
