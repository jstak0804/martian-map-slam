"""
학습 모델 vs 그림자 기반 고전 CV — 같은 3장에 대한 정성적 비교 그림
"""
import numpy as np
import torch
from PIL import Image
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from train_terrain_segmentation import SmallUNet, IMG_SIZE
from boulder_detection_no_labels import detect_boulder_shadows

SAMPLE_DIR = "../data/ai4mars_samples"
OUT_DIR = "../outputs/terrain_segmentation"
CKPT = f"{OUT_DIR}/small_unet_best.pt"

SAMPLES = [
    "NLB_486372898EDR_F0481570NCAM00322M1",
    "NLB_542921313EDR_F0612232NCAM00320M1",
    "NLB_461147286EDR_F0401240NCAM00385M1",
]


def style_ax(ax):
    ax.set_facecolor("#0b0e15")
    for s in ax.spines.values():
        s.set_color("#262d3d")
    ax.set_xticks([]); ax.set_yticks([])


def model_predict_big_rock(model, img):
    orig_size = img.size
    img_small = img.resize((IMG_SIZE, IMG_SIZE), Image.BILINEAR)
    x = torch.from_numpy(np.array(img_small, dtype=np.float32) / 255.0).unsqueeze(0).unsqueeze(0)
    with torch.no_grad():
        logits = model(x)
    pred_small = logits.argmax(dim=1).squeeze(0).numpy().astype(np.uint8)
    pred_full = np.array(Image.fromarray(pred_small).resize(orig_size, Image.NEAREST))
    return pred_full == 3


def main():
    model = SmallUNet()
    model.load_state_dict(torch.load(CKPT, map_location="cpu"))
    model.eval()

    fig, axes = plt.subplots(len(SAMPLES), 4, figsize=(14, 3.6 * len(SAMPLES)), facecolor="#0b0e15")
    col_titles = ["input", "ground truth (big_rock)", "classical CV (shadow)", "trained model"]

    for row, name in enumerate(SAMPLES):
        img = Image.open(f"{SAMPLE_DIR}/{name}.jpg").convert("L")
        gray = np.array(img)
        label = np.array(Image.open(f"{SAMPLE_DIR}/{name}_mask.png"))
        gt_rock = label == 3

        classical_mask, _ = detect_boulder_shadows(gray)
        model_mask = model_predict_big_rock(model, img)

        panels = [gray, gt_rock, classical_mask, model_mask]
        for col, (arr, title) in enumerate(zip(panels, col_titles)):
            ax = axes[row, col]; style_ax(ax)
            if col == 0:
                ax.imshow(arr, cmap="gray")
            else:
                ax.imshow(arr, cmap="gray_r" if col == 1 else "Reds", vmin=0, vmax=1)
            if row == 0:
                ax.set_title(title, color="#e9ebf2", fontsize=10)
            if col == 0:
                ax.set_ylabel(name[:18], color="#a7aec1", fontsize=8)

    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/model_vs_classical.png", dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"saved {OUT_DIR}/model_vs_classical.png")


if __name__ == "__main__":
    main()
