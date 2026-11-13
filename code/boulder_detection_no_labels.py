"""
라벨 없는 바위 탐지 — 지적된 문제 ①을 실제로 해결

지금까지 "CV 위험도"는 AI4Mars의 사람이 매긴 정답 라벨(big_rock 등)에 숫자만 입힌 것이었다.
이 스크립트는 그 라벨을 입력으로 쓰지 않고, 그림자 기반 고전 CV 탐지(CLPS 심화학습에서
설계만 하고 실제로 돌려본 적 없는 detect_boulder_shadows)를 원본 픽셀에만 적용한다.
정답 라벨은 오직 '탐지가 실제로 맞았는지' 채점하는 데만 사후적으로 사용한다 — 즉,
이번에는 라벨이 입력이 아니라 평가 기준이다.
"""
import json
import numpy as np
import cv2
from PIL import Image

SAMPLE_DIR = "../data/ai4mars_samples"
OUT_DIR = "../outputs/boulder_detection_no_labels"
import os
os.makedirs(OUT_DIR, exist_ok=True)

SAMPLES = [
    "NLB_486372898EDR_F0481570NCAM00322M1",  # big_rock 33.7% (전문가 라벨 기준)
    "NLB_542921313EDR_F0612232NCAM00320M1",  # big_rock 0%
    "NLB_461147286EDR_F0401240NCAM00385M1",  # big_rock 0%
]


def detect_boulder_shadows(gray, dark_thresh=35, min_area_px=6):
    """그림자(어두운 반점) 컨투어 탐지 — 라벨/정답을 전혀 참조하지 않는다."""
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    _, dark = cv2.threshold(blurred, dark_thresh, 255, cv2.THRESH_BINARY_INV)
    kernel = np.ones((3, 3), np.uint8)
    dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mask = np.zeros_like(gray, dtype=bool)
    boxes = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area_px:
            continue
        cv2.drawContours(mask.view(np.uint8), [c], -1, 1, thickness=-1)
        x, y, w, h = cv2.boundingRect(c)
        boxes.append((x, y, w, h, float(area)))
    return mask, boxes


def evaluate_against_labels(detected_mask, label_mask):
    """정답 라벨은 여기서만, 채점 용도로만 사용한다."""
    gt_rock = (label_mask == 3)  # big_rock
    gt_unlabeled = (label_mask == 255)
    valid = ~gt_unlabeled

    tp = (detected_mask & gt_rock & valid).sum()
    fp = (detected_mask & ~gt_rock & valid).sum()
    fn = (~detected_mask & gt_rock & valid).sum()
    tn = (~detected_mask & ~gt_rock & valid).sum()

    precision = tp / (tp + fp) if (tp + fp) > 0 else float("nan")
    recall = tp / (tp + fn) if (tp + fn) > 0 else float("nan")
    iou = tp / (tp + fp + fn) if (tp + fp + fn) > 0 else float("nan")
    return {
        "tp_px": int(tp), "fp_px": int(fp), "fn_px": int(fn), "tn_px": int(tn),
        "precision": float(precision), "recall": float(recall), "iou": float(iou),
        "gt_rock_pct": float(gt_rock[valid].mean() * 100),
        "detected_pct": float(detected_mask[valid].mean() * 100),
    }


def main():
    results = []
    for name in SAMPLES:
        gray = np.array(Image.open(f"{SAMPLE_DIR}/{name}.jpg").convert("L"))
        label = np.array(Image.open(f"{SAMPLE_DIR}/{name}_mask.png"))

        detected_mask, boxes = detect_boulder_shadows(gray)
        metrics = evaluate_against_labels(detected_mask, label)
        metrics["name"] = name
        metrics["n_detections"] = len(boxes)
        results.append(metrics)

        print(f"[{name}]")
        print(f"  탐지된 그림자 블롭: {len(boxes)}개 (라벨 미참조)")
        print(f"  전문가 라벨 big_rock 비율: {metrics['gt_rock_pct']:.1f}%  "
              f"vs 우리 탐지 비율: {metrics['detected_pct']:.1f}%")
        print(f"  Precision: {metrics['precision']:.3f}  Recall: {metrics['recall']:.3f}  "
              f"IoU: {metrics['iou']:.3f}\n")

    with open(f"{OUT_DIR}/no_label_detection_stats.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"saved {OUT_DIR}/no_label_detection_stats.json")

    mean_iou = np.nanmean([r["iou"] for r in results])
    mean_precision = np.nanmean([r["precision"] for r in results])
    mean_recall = np.nanmean([r["recall"] for r in results])
    print(f"\n평균 — Precision {mean_precision:.3f} / Recall {mean_recall:.3f} / IoU {mean_iou:.3f}")
    print("참고: 그림자 기반 탐지는 '모든 어두운 반점'을 잡기 때문에 그림자 없는 평평한 바위,")
    print("또는 바위가 아닌 다른 어두운 질감(균열 등)까지 오탐할 수 있음 — 아래가 그 증거.")


if __name__ == "__main__":
    main()
