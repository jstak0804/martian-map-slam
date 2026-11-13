"""
1인칭 주행 카메라(Mars Curiosity Navcam, AI4Mars 데이터) 데모
- 단일 이미지 기반 pseudo-relief(단순 음영 기반 상대 고도 근사)
- 실제 전문가 라벨(soil/bedrock/sand/big rock) + 지형 거칠기를 결합한 위험도 히트맵

주의: 이것은 진짜 photoclinometry/스테레오 3D 재구성이 아니라,
      단일 이미지의 명암만으로 만든 "정성적" 굴곡 근사입니다 (데모/설명용).
      진짜 3D 재구성에는 스테레오 쌍 또는 다중 시점 + 카메라 포즈가 필요합니다.
"""
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import base64
import io
import json

SAMPLE_DIR = "../data/ai4mars_samples"
OUT_DIR = "../outputs/risk_heatmap"
import os
os.makedirs(OUT_DIR, exist_ok=True)

# AI4Mars label convention (NASA JPL): 0 soil, 1 bedrock, 2 sand, 3 big rock, 255 unlabeled
CLASS_NAMES = {0: "soil", 1: "bedrock", 2: "sand", 3: "big_rock", 255: "unlabeled"}
CLASS_RISK = {0: 0.05, 1: 0.25, 2: 0.45, 3: 0.95, 255: np.nan}
CLASS_COLOR = {  # for the class-map panel
    0: (0.62, 0.55, 0.42),   # soil - tan
    1: (0.55, 0.58, 0.60),   # bedrock - grey-blue
    2: (0.80, 0.68, 0.40),   # sand - sandy gold
    3: (0.70, 0.18, 0.12),   # big_rock - rust red
    255: (0.10, 0.10, 0.12), # unlabeled - near black
}

# project palette: teal (low risk) -> gold (mid) -> rust (high risk)
RISK_CMAP = LinearSegmentedColormap.from_list(
    "risk", [(0.11, 0.42, 0.45), (0.64, 0.47, 0.12), (0.61, 0.29, 0.23)]
)


def frankot_chellappa(gx, gy):
    """FFT 기반 gradient 적분 (Frankot-Chellappa 알고리즘).
    gx, gy: 추정된 표면 기울기(dz/dx, dz/dy) -> 적분해 상대 높이(z) 복원."""
    h, w = gx.shape
    wx = np.fft.fftfreq(w).reshape(1, w) * 2 * np.pi
    wy = np.fft.fftfreq(h).reshape(h, 1) * 2 * np.pi
    Gx = np.fft.fft2(gx)
    Gy = np.fft.fft2(gy)
    denom = (wx ** 2 + wy ** 2)
    denom[0, 0] = 1.0  # avoid div-by-zero at DC
    Z = (-1j * wx * Gx - 1j * wy * Gy) / denom
    Z[0, 0] = 0.0
    z = np.real(np.fft.ifft2(Z))
    return z


def estimate_pseudo_relief(gray):
    """단순화된 '명암 기반 상대 고도' 근사.
    실제 알베도/반사모델 보정은 하지 않음 - 데모용 정성적 근사치."""
    g = gray.astype(np.float64) / 255.0
    g = (g - g.mean()) / (g.std() + 1e-6)
    gy, gx = np.gradient(g)
    z = frankot_chellappa(gx, gy)
    z = (z - z.min()) / (z.max() - z.min() + 1e-9)
    return z


def local_roughness(z, win=15):
    """높이장(z)의 지역 표준편차 -> 지형 거칠기 proxy (0~1 정규화)."""
    from scipy.ndimage import uniform_filter
    mean = uniform_filter(z, size=win)
    mean_sq = uniform_filter(z * z, size=win)
    var = np.clip(mean_sq - mean ** 2, 0, None)
    rough = np.sqrt(var)
    rough = (rough - rough.min()) / (rough.max() - rough.min() + 1e-9)
    return rough


def class_risk_map(mask):
    risk = np.zeros(mask.shape, dtype=np.float64)
    unknown = np.zeros(mask.shape, dtype=bool)
    for cls, r in CLASS_RISK.items():
        sel = mask == cls
        if cls == 255:
            unknown |= sel
            risk[sel] = 0.3  # 모를 때는 중립값
        else:
            risk[sel] = r
    return risk, unknown


def colorize_classes(mask):
    out = np.zeros((*mask.shape, 3), dtype=np.float64)
    for cls, color in CLASS_COLOR.items():
        out[mask == cls] = color
    return out


def downsample_grid(arr, tile=32):
    h, w = arr.shape
    gh, gw = h // tile, w // tile
    grid = arr[: gh * tile, : gw * tile].reshape(gh, tile, gw, tile).mean(axis=(1, 3))
    return grid


def fig_to_b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def process(name, tile=32):
    img = np.array(Image.open(f"{SAMPLE_DIR}/{name}.jpg").convert("L"))
    mask = np.array(Image.open(f"{SAMPLE_DIR}/{name}_mask.png"))

    relief = estimate_pseudo_relief(img)
    rough = local_roughness(relief, win=15)
    cls_risk, unknown = class_risk_map(mask)

    # 최종 위험도 = 전문가 라벨 기반 위험(0.7) + 지형 거칠기(0.3)
    risk = 0.7 * cls_risk + 0.3 * rough
    risk = np.clip(risk, 0, 1)

    grid_risk = downsample_grid(risk, tile=tile)

    # ---- figure ----
    fig, axes = plt.subplots(1, 4, figsize=(16, 4.2), facecolor="#0b0e15")
    titles = [
        "1. Raw navcam frame\n(real AI4Mars sample)",
        "2. Expert terrain labels\n(soil / bedrock / sand / big_rock)",
        "3. Pseudo-relief\n(single-image shading proxy)",
        "4. Combined risk heatmap\n(0.7*label + 0.3*roughness)",
    ]
    panels = [img, colorize_classes(mask), relief, None]

    for ax, title in zip(axes, titles):
        ax.set_title(title, color="#e9ebf2", fontsize=10.5)
        ax.axis("off")

    axes[0].imshow(img, cmap="gray")
    axes[1].imshow(colorize_classes(mask))
    legend_handles = [
        plt.Rectangle((0, 0), 1, 1, facecolor=CLASS_COLOR[c], edgecolor="#e9ebf2", linewidth=0.6)
        for c in [0, 1, 2, 3, 255]
    ]
    legend_labels = [
        "soil (low risk)",
        "bedrock (low-med)",
        "sand (medium)",
        "big_rock (HIGH risk)",
        "unlabeled",
    ]
    leg = axes[1].legend(
        legend_handles, legend_labels,
        loc="upper center", bbox_to_anchor=(0.5, -0.03),
        ncol=2, frameon=True, fontsize=8.3, handlelength=1.1, handleheight=1.1,
        labelcolor="#e9ebf2", facecolor="#141926", edgecolor="#262d3d",
    )
    leg.get_frame().set_alpha(0.95)
    axes[2].imshow(relief, cmap="gray")

    axes[3].imshow(img, cmap="gray")
    im = axes[3].imshow(risk, cmap=RISK_CMAP, alpha=0.55, vmin=0, vmax=1)
    cbar = fig.colorbar(im, ax=axes[3], fraction=0.046, pad=0.02)
    cbar.set_label("risk score", color="#e9ebf2", fontsize=9)
    cbar.ax.yaxis.set_tick_params(color="#e9ebf2")
    plt.setp(cbar.ax.get_yticklabels(), color="#e9ebf2")

    fig.tight_layout()
    b64 = fig_to_b64(fig)

    stats = {
        "name": name,
        "mean_risk": float(np.nanmean(risk)),
        "max_risk": float(np.nanmax(risk)),
        "high_risk_pct": float((risk > 0.6).mean() * 100),
        "class_pct": {
            CLASS_NAMES[c]: float((mask == c).mean() * 100) for c in CLASS_NAMES
        },
        "grid_shape": list(grid_risk.shape),
    }
    return b64, stats, grid_risk


if __name__ == "__main__":
    results = {}
    for name in [
        "NLB_486372898EDR_F0481570NCAM00322M1",  # big-rock-rich (고위험 예시)
        "NLB_461147286EDR_F0401240NCAM00385M1",  # mostly flat soil (저위험 예시)
        "NLB_542921313EDR_F0612232NCAM00320M1",  # sand/bedrock mix
    ]:
        b64, stats, grid = process(name)
        results[name] = {"b64": b64, "stats": stats}
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        with open(f"{OUT_DIR}/{name}.png.b64", "w") as f:
            f.write(b64)
        np.save(f"{OUT_DIR}/{name}_grid_risk.npy", grid)

    with open(f"{OUT_DIR}/stats.json", "w", encoding="utf-8") as f:
        json.dump({k: v["stats"] for k, v in results.items()}, f, indent=2, ensure_ascii=False)

    print("DONE")
