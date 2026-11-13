"""
N=3 (퇴화된 기존 held-out) vs N=20 (확장된 held-out) IoU 비교 그림

cascade_fusion_detection.py가 "셋 중 최고"라고 보고했던 IoU 0.170은 사실상 이미지
1장(big_rock이 있는 유일한 샘플)에 좌우된 값이었다. N=20으로 확장하자 순위가
바뀐다 — 모델 단독이 그림자 CV와 캐스케이드 융합을 모두 앞선다. 이 반전을 한눈에
보여주는 그림.
"""
import json
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT_DIR = "../outputs/terrain_segmentation"

with open(f"{OUT_DIR}/expanded_holdout_stats.json") as f:
    d = json.load(f)

methods = ["classical_cv", "trained_model_only", "cascade_fusion"]
labels = ["Shadow CV", "Model only", "Cascade fusion"]
colors = ["#c98a3d", "#5cbcc3", "#b85c5c"]

old_iou = [0.120, 0.052, 0.170]  # N=3 (degenerate: 2/3 samples had 0% ground-truth big_rock)
new_iou = [d[m]["iou"]["nanmean"] for m in methods]
new_precision = [d[m]["precision"]["nanmean"] for m in methods]
new_recall = [d[m]["recall"]["nanmean"] for m in methods]

fig, axes = plt.subplots(1, 2, figsize=(12.5, 5), facecolor="#0b0e15")

ax = axes[0]
ax.set_facecolor("#0b0e15")
x = np.arange(len(methods))
w = 0.32
ax.bar(x - w/2, old_iou, width=w, color="#4a5166", label="old holdout N=3 (2/3 degenerate)")
ax.bar(x + w/2, new_iou, width=w, color=colors, label="expanded holdout N=20")
for i, v in enumerate(old_iou):
    ax.text(i - w/2, v + 0.01, f"{v:.3f}", ha="center", color="#a7aec1", fontsize=8)
for i, v in enumerate(new_iou):
    ax.text(i + w/2, v + 0.01, f"{v:.3f}", ha="center", color="#e9ebf2", fontsize=8)
ax.set_xticks(x); ax.set_xticklabels(labels, color="#e9ebf2")
ax.set_ylabel("big_rock IoU", color="#a7aec1")
ax.set_title("N=3 -> N=20: the ranking flips", color="#e9ebf2", fontsize=10)
for s in ax.spines.values(): s.set_color("#262d3d")
ax.tick_params(colors="#a7aec1")
ax.legend(fontsize=7, facecolor="#11141c", edgecolor="#262d3d", labelcolor="#a7aec1")

ax2 = axes[1]
ax2.set_facecolor("#0b0e15")
ax2.bar(x - w/2, new_precision, width=w, color="#5a6b8c", label="Precision")
ax2.bar(x + w/2, new_recall, width=w, color="#8c6b5a", label="Recall")
for i, v in enumerate(new_precision):
    ax2.text(i - w/2, v + 0.01, f"{v:.2f}", ha="center", color="#a7aec1", fontsize=8)
for i, v in enumerate(new_recall):
    ax2.text(i + w/2, v + 0.01, f"{v:.2f}", ha="center", color="#a7aec1", fontsize=8)
ax2.set_xticks(x); ax2.set_xticklabels(labels, color="#e9ebf2")
ax2.set_title("Cascade: precision up slightly, recall drops a lot", color="#e9ebf2", fontsize=10)
for s in ax2.spines.values(): s.set_color("#262d3d")
ax2.tick_params(colors="#a7aec1")
ax2.legend(fontsize=8, facecolor="#11141c", edgecolor="#262d3d", labelcolor="#a7aec1")

fig.tight_layout()
fig.savefig(f"{OUT_DIR}/expanded_holdout_comparison.png", dpi=135, bbox_inches="tight", facecolor=fig.get_facecolor())
print(f"saved {OUT_DIR}/expanded_holdout_comparison.png")
