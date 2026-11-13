"""
ConeQuest 3단계 — 위험도 함수에 실제 편입 (탐지 결과 -> 위험도 채널)

목적: 2단계에서 학습한 콘 탐지 모델의 출력을, 기존 위험도 공식
risk = clip(0.4*A + 0.6*B, 0, 1) 과 같은 형태로 지형 위험도 채널에 직접 결합해본다.

중요한 한계(숨기지 않고 먼저 명시):
  - ConeQuest에는 DEM(고도) 데이터가 없다 — 궤도 광학영상(HiRISE/CTX)과 이진 마스크뿐이다.
    그래서 기존 real_terrain_risk.py처럼 '진짜 경사'를 계산할 수 없다.
  - 픽셀 스케일도 다르다 — 이 프로젝트의 로버 위험도(경사·거칠기)는 cm~m 스케일의 국소
    지형을 다루지만, ConeQuest 패치는 궤도 영상(대략 수 m~수십 m/px 추정, 메타데이터에
    정확한 GSD가 없어 단정하지 않음)이라 "로버가 밟는 위험"과는 물리적 스케일이 다르다.
  - 따라서 여기서는 "진짜 로버 위험도"를 만든다고 주장하지 않는다. 대신 경사 항을
    텍스처 거칠기(이미지 밝기의 국소 표준편차 — 기존 rock_risk와 수학적으로 동일한 형태,
    입력만 고도 대신 밝기)로 대체하고, 거칠기 항을 모델이 실제로 예측한 콘 확률로
    대체해, "실제 탐지기 출력 -> 위험도 공식"이라는 메커니즘 자체가 작동하는지만 확인한다.

  risk_orbital = clip(0.4 * texture_risk + 0.6 * cone_prob_risk, 0, 1)
    texture_risk   = clip(local_std(intensity, win=5) / NORM_TEX, 0, 1)   -- 기존 rock_risk와 동일한 수식 형태
    cone_prob_risk = clip(model_cone_prob / NORM_CONE, 0, 1)             -- 모델이 직접 예측한 값

  가중치는 기존 공식(0.4/0.6)과 반대로 텍스처(0.4) < 콘확률(0.6)을 줬다 — 모델이 직접
  예측한 콘 확률이 밝기 텍스처보다 훨씬 신뢰도 높은 신호라고 보기 때문.
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np
import torch
from PIL import Image
from scipy.ndimage import uniform_filter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(__file__))
from train_terrain_segmentation import SmallUNet, style_ax  # noqa: E402
from conequest_unet_generalization import DATA_ROOT, CSV_PATH, IMG_SIZE, DEVICE  # noqa: E402

OUT_DIR = "../outputs/conequest_risk_fusion"
os.makedirs(OUT_DIR, exist_ok=True)
CKPT = "../outputs/conequest_unet/small_unet_cone_best.pt"

NORM_TEX = 0.10   # 텍스처(밝기 국소표준편차, 0~1 정규화된 intensity 기준) 정규화 상수
NORM_CONE = 0.5   # 콘 확률 정규화 상수 — 0.5 이상이면 이미 risk=1로 포화(보수적으로 조기 포화)


def load_split(name):
    with open(CSV_PATH, newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["Patch Id"].startswith("E084_N12")]
    return [r["Patch Id"] for r in rows if r["BM-1 Set"] == name]


def load_model():
    model = SmallUNet(n_classes=2).to(DEVICE)
    model.load_state_dict(torch.load(CKPT, map_location=DEVICE))
    model.eval()
    return model


def compute_risk(name, model):
    img = Image.open(f"{DATA_ROOT}/input_dir/{name}").convert("L").resize((IMG_SIZE, IMG_SIZE), Image.BILINEAR)
    img_arr = np.array(img, dtype=np.float32) / 255.0

    with torch.no_grad():
        logits = model(torch.from_numpy(img_arr).unsqueeze(0).unsqueeze(0).to(DEVICE))
        prob_cone = torch.softmax(logits, dim=1)[0, 1].cpu().numpy()

    local_mean = uniform_filter(img_arr, 5)
    local_sq = uniform_filter(img_arr ** 2, 5)
    texture = np.sqrt(np.clip(local_sq - local_mean ** 2, 0, None))
    texture_risk = np.clip(texture / NORM_TEX, 0, 1)
    cone_prob_risk = np.clip(prob_cone / NORM_CONE, 0, 1)

    risk = np.clip(0.4 * texture_risk + 0.6 * cone_prob_risk, 0, 1)
    return img_arr, texture_risk, cone_prob_risk, risk


def plot_examples(names, results):
    fig, axes = plt.subplots(len(names), 4, figsize=(13, 3.1 * len(names)), facecolor="#0b0e15")
    titles = ["input", "texture_risk (0.4×)", "cone_prob_risk (0.6×)", "combined risk"]
    cmaps = ["gray", "inferno", "inferno", "inferno"]
    for row, (name, (img, tex, cone, risk)) in enumerate(zip(names, results)):
        for col, (arr, cmap, title) in enumerate(zip([img, tex, cone, risk], cmaps, titles)):
            ax = axes[row, col]; style_ax(ax)
            im = ax.imshow(arr, cmap=cmap, vmin=0, vmax=1)
            if row == 0:
                ax.set_title(title, color="#e9ebf2", fontsize=10)
            ax.set_xticks([]); ax.set_yticks([])
            if col == 3:
                fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
    fig.suptitle("ConeQuest risk fusion -- detector output wired into risk formula (step 3/3, orbital scale)",
                  color="#e9ebf2", fontsize=12, y=0.995)
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/risk_fusion_examples.png", dpi=135, bbox_inches="tight", facecolor=fig.get_facecolor())
    print("saved", f"{OUT_DIR}/risk_fusion_examples.png")


def main():
    model = load_model()
    test_names = load_split("test")
    print(f"test split: {len(test_names)} patches")

    # 콘이 있는 패치 2장 + 콘이 없는 패치 1장을 섞어서 보여준다 (양성/음성 모두 확인)
    with open(CSV_PATH, newline="") as f:
        rows = {r["Patch Id"]: r for r in csv.DictReader(f) if r["Patch Id"].startswith("E084_N12")}
    test_pos = [n for n in test_names if rows[n]["Number of Cones"] not in ("0", "")]
    test_neg = [n for n in test_names if rows[n]["Number of Cones"] in ("0", "")]
    chosen = (test_pos[:2] if len(test_pos) >= 2 else test_pos) + (test_neg[:1] if test_neg else [])
    if not chosen:
        chosen = test_names[:3]
    print("chosen patches:", chosen)

    results = [compute_risk(n, model) for n in chosen]
    plot_examples(chosen, results)

    stats = []
    for name, (img, tex, cone, risk) in zip(chosen, results):
        stats.append({
            "patch": name,
            "n_cones_label": rows[name]["Number of Cones"],
            "mean_texture_risk": float(tex.mean()),
            "mean_cone_prob_risk": float(cone.mean()),
            "mean_combined_risk": float(risk.mean()),
            "high_risk_frac_gt_0.5": float((risk > 0.5).mean()),
        })
    with open(f"{OUT_DIR}/risk_fusion_stats.json", "w") as f:
        json.dump({"patches": stats,
                    "note": "orbital-scale demo only -- no DEM, no validated physical risk; "
                            "shows the detector-to-risk-formula mechanism, not rover-ready output."},
                   f, indent=2)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
