"""
실제 지형 데이터 기반 위험도 히트맵 — 지구(Devon Island) vs 달(LOLA 남극)

지금까지의 위험도 히트맵(AI4Mars, 절차적 탐사 시뮬레이션)은 각각 '실제 카메라 이미지'와
'절차적으로 생성한 가상 지형'이었다. 이번에는 두 실제 궤도 유래 DEM(Digital Elevation Model)을
동일한 20m/px 해상도로 맞춰 정확히 같은 risk_score 공식으로 비교한다 — CLPS/탐사 시뮬레이션에서
써온 "경사 + 거칠기" 설계를 실제 지구·달 지형에 그대로 적용하는 검증이다.

데이터:
  지구 — Devon Island Rover Navigation Dataset, 궤도사진측량 DEM (UTIAS, 실측, ~23.7m 간격 포인트클라우드)
  달   — LOLA(Lunar Orbiter Laser Altimeter) 남극 20m/px DEM (NASA LRO, PDS Geosciences Node)

위험도 기준(두 데이터셋에 동일하게 적용):
  경사 위험  — 15도를 '고위험' 기준으로 정규화 (CLPS/Artemis급 착륙선의 일반적 안전 경사 한계와 같은 자릿수)
  거칠기 위험 — 100m 창 내 고도 표준편차를 2m 기준으로 정규화 (휴리스틱, 교육용 근사치)
"""
from __future__ import annotations

import json
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from scipy.ndimage import uniform_filter, distance_transform_edt
from scipy.stats import binned_statistic_2d

OUT_DIR = "../outputs/real_terrain"
import os
os.makedirs(OUT_DIR, exist_ok=True)

CELL_M = 20.0            # 두 데이터셋 모두 이 해상도로 맞춘다 (공정 비교)
SLOPE_HIGH_DEG = 15.0     # 착륙선/로버 급 경사 안전 한계 자릿수 (공학적으로 흔히 쓰이는 기준)
ROUGHNESS_HIGH_M = 2.0    # 100m 창 내 고도 표준편차 기준 (휴리스틱)
ROUGH_WIN_PX = 5          # 100m 상당 (5 x 20m)

RISK_CMAP = LinearSegmentedColormap.from_list("risk", [(0.11, 0.42, 0.45), (0.64, 0.47, 0.12), (0.61, 0.29, 0.23)])


# ============================================================
# 1. 지구 — Devon Island 궤도 DEM 포인트클라우드 -> 정규격자
# ============================================================

def load_earth_dem():
    data = np.loadtxt("../data/devon_island_dem/Orbital Maps/mapHiRes.txt")
    e, n, z = data[:, 0], data[:, 1], data[:, 2]

    nx = int(np.ceil((e.max() - e.min()) / CELL_M))
    ny = int(np.ceil((n.max() - n.min()) / CELL_M))
    stat, _, _, _ = binned_statistic_2d(e, n, z, statistic="mean", bins=[nx, ny])
    h = np.flipud(stat.T)  # north-up

    mask = np.isnan(h)
    idx = distance_transform_edt(mask, return_distances=False, return_indices=True)
    h_filled = h[tuple(idx)]
    coverage_pct = 100 * (~mask).mean()
    return h_filled, coverage_pct


# ============================================================
# 2. 달 — LOLA 남극 20m DEM (PDS IMG 원시 바이너리)
# ============================================================

def load_moon_dem(row0=4600, col0=5200, size=900):
    arr = np.fromfile("../data/moon_lola/ldem_875s_20m.img", dtype="<i2")
    arr = arr.reshape(7584, 7584).astype(np.float32) * 0.5  # SCALING_FACTOR = 0.5 m (label 파일 명시)
    crop = arr[row0:row0 + size, col0:col0 + size]
    return crop


# ============================================================
# 3. 위험도 — 두 데이터셋에 동일한 공식 적용
# ============================================================

def terrain_risk(h, cell_m=CELL_M):
    gy, gx = np.gradient(h, cell_m)
    slope_deg = np.degrees(np.arctan(np.hypot(gx, gy)))
    slope_risk = np.clip(slope_deg / SLOPE_HIGH_DEG, 0, 1)

    mean = uniform_filter(h, ROUGH_WIN_PX)
    mean_sq = uniform_filter(h ** 2, ROUGH_WIN_PX)
    roughness_m = np.sqrt(np.clip(mean_sq - mean ** 2, 0, None))
    roughness_risk = np.clip(roughness_m / ROUGHNESS_HIGH_M, 0, 1)

    risk = np.clip(0.5 * slope_risk + 0.5 * roughness_risk, 0, 1)
    return slope_deg, roughness_m, risk


def hillshade(h, cell_m=CELL_M, az_deg=315, alt_deg=45):
    gy, gx = np.gradient(h, cell_m)
    slope = np.pi / 2 - np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    az = np.radians(360 - az_deg + 90)
    alt = np.radians(alt_deg)
    shaded = np.sin(alt) * np.sin(slope) + np.cos(alt) * np.cos(slope) * np.cos(az - aspect)
    return np.clip(shaded, 0, 1)


# ============================================================
# 4. 실행 + 시각화
# ============================================================

def style_ax(ax):
    ax.set_facecolor("#0b0e15")
    for s in ax.spines.values():
        s.set_color("#262d3d")
    ax.tick_params(colors="#a7aec1", labelsize=7)


def summarize(name, h, slope_deg, roughness_m, risk):
    return {
        "name": name,
        "shape": list(h.shape),
        "extent_km": [h.shape[1] * CELL_M / 1000, h.shape[0] * CELL_M / 1000],
        "elevation_range_m": [float(h.min()), float(h.max())],
        "mean_slope_deg": float(slope_deg.mean()),
        "pct_slope_over_15deg": float((slope_deg > SLOPE_HIGH_DEG).mean() * 100),
        "mean_roughness_m": float(roughness_m.mean()),
        "mean_risk": float(risk.mean()),
        "pct_high_risk_gt0.5": float((risk > 0.5).mean() * 100),
    }


def main():
    print("지구 DEM 로딩 (Devon Island 궤도사진측량)...")
    earth_h, earth_cov = load_earth_dem()
    print(f"  격자 크기 {earth_h.shape}, 포인트 실측 커버리지 {earth_cov:.1f}% (나머지는 최근접 보간)")

    print("달 DEM 로딩 (LOLA 남극 20m)...")
    moon_h = load_moon_dem()
    print(f"  격자 크기 {moon_h.shape}")

    earth_slope, earth_rough, earth_risk = terrain_risk(earth_h)
    moon_slope, moon_rough, moon_risk = terrain_risk(moon_h)

    earth_stats = summarize("Earth (Devon Island)", earth_h, earth_slope, earth_rough, earth_risk)
    moon_stats = summarize("Moon (LOLA south pole)", moon_h, moon_slope, moon_rough, moon_risk)

    for s in (earth_stats, moon_stats):
        print(f"\n[{s['name']}]")
        print(f"  범위: {s['extent_km'][0]:.2f} x {s['extent_km'][1]:.2f} km, "
              f"고도 {s['elevation_range_m'][0]:.0f}~{s['elevation_range_m'][1]:.0f} m")
        print(f"  평균 경사: {s['mean_slope_deg']:.2f} deg, 15도 초과 비율: {s['pct_slope_over_15deg']:.1f}%")
        print(f"  평균 위험도: {s['mean_risk']:.3f}, 고위험(>0.5) 비율: {s['pct_high_risk_gt0.5']:.1f}%")

    plot_comparison(earth_h, earth_slope, earth_risk, moon_h, moon_slope, moon_risk)

    with open(f"{OUT_DIR}/real_terrain_stats.json", "w") as f:
        json.dump({"earth": earth_stats, "moon": moon_stats,
                    "method": {"cell_m": CELL_M, "slope_high_deg": SLOPE_HIGH_DEG,
                               "roughness_high_m": ROUGHNESS_HIGH_M}}, f, indent=2)
    print(f"\nsaved {OUT_DIR}/real_terrain_stats.json")


def plot_comparison(earth_h, earth_slope, earth_risk, moon_h, moon_slope, moon_risk):
    fig, axes = plt.subplots(2, 3, figsize=(16, 10.8), facecolor="#0b0e15")

    rows = [
        ("Earth — Devon Island (real orbital DEM)", earth_h, earth_slope, earth_risk),
        ("Moon — LOLA south pole 87.5-90S (real LOLA DEM)", moon_h, moon_slope, moon_risk),
    ]
    for r, (label, h, slope, risk) in enumerate(rows):
        shade = hillshade(h)

        ax = axes[r, 0]; style_ax(ax)
        ax.imshow(shade, cmap="gray", origin="upper")
        ax.set_title(f"{label}\nHillshade", color="#e9ebf2", fontsize=10)

        ax = axes[r, 1]; style_ax(ax)
        im = ax.imshow(slope, cmap="inferno", vmin=0, vmax=30, origin="upper")
        ax.set_title("Slope (deg)", color="#e9ebf2", fontsize=10)
        cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
        cb.ax.yaxis.set_tick_params(color="#e9ebf2")
        plt.setp(cb.ax.get_yticklabels(), color="#e9ebf2")

        ax = axes[r, 2]; style_ax(ax)
        ax.imshow(shade, cmap="gray", origin="upper", alpha=0.45)
        im = ax.imshow(risk, cmap=RISK_CMAP, vmin=0, vmax=1, origin="upper")
        ax.set_title(f"Risk heatmap (mean={risk.mean():.2f})", color="#e9ebf2", fontsize=10)
        cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
        cb.ax.yaxis.set_tick_params(color="#e9ebf2")
        plt.setp(cb.ax.get_yticklabels(), color="#e9ebf2")

    fig.suptitle("Real terrain risk heatmap — same 20m/px grid, same risk formula", color="#a7aec1", fontsize=10)
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/real_terrain_comparison.png", dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"saved {OUT_DIR}/real_terrain_comparison.png")


if __name__ == "__main__":
    main()
