"""
인터랙티브 경로탐색 데모용 데이터 내보내기

real_terrain_risk.py가 이미 계산한 달 LOLA 위험도 그리드를 다운샘플링해서
브라우저(JS)에서 바로 읽을 수 있는 그레이스케일 PNG(위험도를 0~255로 인코딩)와,
사람이 보기 좋은 하일셰이드+위험도 합성 PNG 두 장을 만든다.
"""
import numpy as np
from PIL import Image

from real_terrain_risk import load_moon_dem, terrain_risk, hillshade, RISK_CMAP

OUT_DIR = "../outputs/real_terrain"
DOWNSAMPLE_TO = 180  # 900x900 -> 180x180 (A*가 브라우저에서 즉시 돌 수 있는 크기)


def block_mean(a, factor):
    h, w = a.shape
    h2, w2 = h // factor, w // factor
    return a[: h2 * factor, : w2 * factor].reshape(h2, factor, w2, factor).mean(axis=(1, 3))


def main():
    h = load_moon_dem()
    slope, rough, risk = terrain_risk(h)
    shade = hillshade(h)

    factor = h.shape[0] // DOWNSAMPLE_TO
    risk_small = block_mean(risk, factor)
    shade_small = block_mean(shade, factor)
    print(f"원본 {h.shape} -> 다운샘플 {risk_small.shape} (factor={factor}, "
          f"셀당 {20*factor}m)")

    # ① A* 비용함수용 — 위험도를 0~255 그레이스케일로 인코딩한 PNG
    risk_u8 = np.clip(risk_small * 255, 0, 255).astype(np.uint8)
    Image.fromarray(risk_u8, mode="L").save(f"{OUT_DIR}/risk_grid_180.png")

    # ② 사람이 보는 배경 지도 — 하일셰이드 + 위험도 컬러를 미리 합성한 PNG
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(DOWNSAMPLE_TO / 40, DOWNSAMPLE_TO / 40), dpi=40)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.imshow(risk_small, cmap=RISK_CMAP, vmin=0, vmax=1, origin="upper")
    ax.imshow(shade_small, cmap="gray", origin="upper", alpha=0.25)  # 지형 질감은 옅게만
    ax.axis("off")
    fig.savefig(f"{OUT_DIR}/risk_basemap_180.png", dpi=200)
    plt.close(fig)

    print(f"saved {OUT_DIR}/risk_grid_180.png (A* 비용함수용)")
    print(f"saved {OUT_DIR}/risk_basemap_180.png (배경 지도용)")
    print(f"위험도 범위: {risk_small.min():.3f} ~ {risk_small.max():.3f}, 평균 {risk_small.mean():.3f}")


if __name__ == "__main__":
    main()
