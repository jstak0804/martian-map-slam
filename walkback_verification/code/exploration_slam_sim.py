"""
주변 탐사형 SLAM 시뮬레이션 — 착륙지점 주변을 능동적으로 탐색하며 위험도 지도를 구축

지금까지(Devon Island)는 "이미 정해진 길을 따라가며" 포즈를 추정하는 문제였다.
이번은 반대 방향 문제다 — "아직 아무도 안 가본 착륙지점 주변을, 어디로 갈지부터
스스로 정하면서" 위험도 지도를 채워나가는 문제. 우주 환경 제약을 다음과 같이 반영한다.

  1. GPS 없음        — 지구처럼 위성항법이 없으므로 VO(Visual Odometry)가 유일한 위치 추정 수단.
                        드리프트가 지도 자체를 오염시킨다 (Devon Island 실험에서 실측한 현상).
  2. 통신 지연/대역폭 — 연속 영상을 지구로 실시간 스트리밍할 수 없다. 실제 화성 로버처럼
                        "이동 -> 정지 -> 마스트 카메라로 주변 스캔 -> (지상/온보드) 다음 목적지
                        결정 -> 이동" 사이클로 동작한다 (continuous video가 아님).
  3. 스테레오 깊이 오차 — 베이스라인이 짧은 마스트 카메라는 깊이 오차가 거리의 제곱에 비례해
                        커진다 (depth_std ~ range^2 / baseline). 먼 지형일수록 측정이 부정확하다.
  4. 지형에 의한 카메라 가림 — 마스트 높이에서 레이캐스팅(viewshed)으로 실제로 보이는 지형만
                        관측 가능 — CLPS 지평선 마스킹과 동일한 원리를 지역 스케일에 적용.
  5. 위험 회피형 경로 — 무작정 넓게 도는 게 아니라, 미탐사 영역(frontier)을 최대화하면서
                        고위험 지형(바위·급경사)은 피하는 방향으로 다음 정지 지점을 고른다.
"""
from __future__ import annotations

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from scipy.ndimage import gaussian_filter, uniform_filter

OUT_DIR = "../outputs/exploration"
import os
os.makedirs(OUT_DIR, exist_ok=True)

# ============================================================
# 0. 파라미터 (우주 임무 카메라/운용 스펙 — Devon Island 실측값 기반으로 설정)
# ============================================================

GRID = 220                 # 셀 수 (한 변)
CELL_M = 0.2                # 셀당 실제 거리 (m) — Devon Island 프레임 간격과 동일 스케일
SIZE_M = GRID * CELL_M       # 44m x 44m 패치

MAST_HEIGHT_M = 1.2          # 마스트 카메라 높이 (실제 로버 평균치)
BASELINE_M = 0.24            # 스테레오 베이스라인 (Devon Island 실측값 재사용)
MAX_RANGE_M = 6.0            # 마스트 카메라 신뢰 가능 최대 관측 거리
SCAN_FOV_DEG = 180           # 1회 정지-스캔에서 커버하는 전방 시야각
N_BEARINGS = 61              # 스캔당 레이 개수 (FOV를 61방향으로 샘플)

N_STOPS = 46                 # 탐사 정지 횟수
STEP_RANGE_M = (1.4, 2.8)    # 한 번 이동 시 거리 범위
TARGET_RADIUS_M = 15.0       # 착륙지점 기준 목표 탐사 반경 (안전 여유 포함)

RNG_SEED = 11
rng = np.random.default_rng(RNG_SEED)


# ============================================================
# 1. 지형 생성 — 착륙 직후에는 상세 지도가 없다는 전제 (궤도 DEM보다 고해상도 지형은 미지)
# ============================================================

def generate_terrain():
    h = np.zeros((GRID, GRID))
    for sigma, amp in [(45, 0.22), (20, 0.10), (9, 0.05), (3.5, 0.025)]:
        h += amp * gaussian_filter(rng.normal(size=(GRID, GRID)), sigma=sigma)
    h -= h.min()

    yy, xx = np.mgrid[0:GRID, 0:GRID]
    rocks = []
    for _ in range(38):
        cx, cy = rng.uniform(20, GRID - 20, 2)
        r_px = rng.uniform(2.5, 10)
        height_m = rng.uniform(0.12, 0.55) * (r_px / 10)
        d = np.hypot(xx - cx, yy - cy)
        h += np.clip(1 - d / r_px, 0, 1) ** 2 * height_m
        rocks.append((cx, cy, r_px, height_m))
    return h, rocks


def true_risk_field(h):
    """지형 경사 + 국소 거칠기(바위 proxy)를 결합한 실제 위험도 — CLPS/AI4Mars와 동일한 설계."""
    gy, gx = np.gradient(h, CELL_M)
    slope = np.hypot(gx, gy)
    slope_risk = np.clip(slope / 0.9, 0, 1)

    local_mean = uniform_filter(h, 5)
    local_sq = uniform_filter(h ** 2, 5)
    roughness = np.sqrt(np.clip(local_sq - local_mean ** 2, 0, None))
    rock_risk = np.clip(roughness / 0.12, 0, 1)

    return np.clip(0.4 * slope_risk + 0.6 * rock_risk, 0, 1)


def bilinear(field, x, y):
    x = np.clip(x, 0, GRID - 1.001)
    y = np.clip(y, 0, GRID - 1.001)
    x0, y0 = int(x), int(y)
    x1, y1 = x0 + 1, y0 + 1
    fx, fy = x - x0, y - y0
    return (field[y0, x0] * (1 - fx) * (1 - fy) + field[y0, x1] * fx * (1 - fy)
            + field[y1, x0] * (1 - fx) * fy + field[y1, x1] * fx * fy)


# ============================================================
# 2. 정지-스캔 카메라 모델 — 지형 가림(occlusion) + 거리 제곱에 비례하는 깊이 오차
# ============================================================

def scan_from(h, risk, pos_xy, heading_deg, record_rays=False):
    """한 번의 '정지 후 마스트 스캔'을 시뮬레이션.
    반환: [(x, y, measured_h, measured_risk, range_m, depth_std), ...], rays(선택)
    """
    px, py = pos_xy
    base_h = bilinear(h, px, py) + MAST_HEIGHT_M
    half_fov = SCAN_FOV_DEG / 2
    bearings = heading_deg + np.linspace(-half_fov, half_fov, N_BEARINGS)

    readings = []
    rays = [] if record_rays else None

    for b in bearings:
        theta = np.radians(b)
        dx, dy = np.sin(theta), -np.cos(theta)
        max_elev = -90.0
        ray_pts = [] if record_rays else None

        for r_m in np.arange(CELL_M, MAX_RANGE_M, CELL_M):
            x = px + dx * r_m / CELL_M
            y = py + dy * r_m / CELL_M
            if not (0 <= x < GRID - 1 and 0 <= y < GRID - 1):
                break
            terrain_h = bilinear(h, x, y)
            elev = np.degrees(np.arctan2(terrain_h - base_h, r_m))

            visible = elev >= max_elev
            if record_rays:
                ray_pts.append((x, y, visible))
            if visible:
                max_elev = elev
                depth_std = max(0.01, (r_m ** 2) / (BASELINE_M * 28.0))  # 거리^2에 비례하는 깊이 오차
                measured_h = terrain_h + rng.normal(0, depth_std)
                measured_risk = np.clip(bilinear(risk, x, y) + rng.normal(0, 0.05), 0, 1)
                readings.append((x, y, measured_h, measured_risk, r_m, depth_std))
        if record_rays:
            rays.append(ray_pts)

    return readings, rays


# ============================================================
# 3. 위험 회피형 프런티어 탐사 — 다음 정지 지점을 스스로 결정
# ============================================================

def run_exploration(h, risk):
    known = np.zeros((GRID, GRID), dtype=bool)  # "이미 가본 적 있어 아는 영역" (frontier 판단용)

    center = GRID / 2
    true_pos = np.array([center, center])
    true_heading = 0.0

    true_path = [true_pos.copy()]
    vo_pos = true_pos.copy()
    vo_path = [vo_pos.copy()]

    all_readings_log = []

    for step in range(N_STOPS):
        # --- (a) 현재 참위치에서 정지-스캔 ---
        readings, _ = scan_from(h, risk, true_pos, true_heading)
        all_readings_log.append((true_pos.copy(), readings))
        for x, y, *_ in readings:  # 탐사 의사결정용 "알고 있는 영역" 갱신 (참좌표 기준)
            gx, gy = int(round(x)), int(round(y))
            if 0 <= gx < GRID and 0 <= gy < GRID:
                known[gy, gx] = True

        # --- (b) 프런티어 기반 다음 목적지 선택 (참위치 기준 "실제" 의사결정) ---
        target = pick_next_stop(known, risk, true_pos, true_heading)
        if target is None:
            break
        direction = target - true_pos
        dist_px = np.linalg.norm(direction)
        heading_to_target = (np.degrees(np.arctan2(direction[0], -direction[1]))) % 360

        # --- (c) 참위치는 정확히 이동 ---
        true_heading = heading_to_target
        true_pos = true_pos + direction
        true_path.append(true_pos.copy())

        # --- (d) VO 추정 위치는 드리프트를 포함해 이동 (실제 온보드 시스템의 상황) ---
        scale_err = rng.normal(0.95, 0.035)
        heading_err_deg = rng.normal(0, 2.2)
        est_dist = dist_px * scale_err
        est_heading = heading_to_target + heading_err_deg
        th = np.radians(est_heading)
        vo_pos = vo_pos + est_dist * np.array([np.sin(th), -np.cos(th)])
        vo_path.append(vo_pos.copy())

    # --- 지도 두 종류 재구성 ---
    # Oracle 지도: 모든 관측을 "참위치"에 배치 (완벽한 위치 추정 가정)
    known_o = np.zeros((GRID, GRID), dtype=bool)
    hs_o = np.zeros((GRID, GRID)); hw_o = np.zeros((GRID, GRID))
    rs_o = np.zeros((GRID, GRID)); rw_o = np.zeros((GRID, GRID))
    # VO 지도: 모든 관측을 "VO 추정위치" 기준 상대좌표로 배치 (실제 온보드 지도 생성과 동일)
    known_v = np.zeros((GRID, GRID), dtype=bool)
    hs_v = np.zeros((GRID, GRID)); hw_v = np.zeros((GRID, GRID))
    rs_v = np.zeros((GRID, GRID)); rw_v = np.zeros((GRID, GRID))

    for i, (true_stop_pos, readings) in enumerate(all_readings_log):
        vo_stop_pos = vo_path[i]
        drift = vo_stop_pos - true_stop_pos  # 이 스텝에서 쌓인 위치 오차
        for x, y, mh, mr, r_m, dstd in readings:
            w = 1.0 / (dstd ** 2)
            # oracle: 참위치 기준 (오차 없음)
            gx, gy = int(round(x)), int(round(y))
            if 0 <= gx < GRID and 0 <= gy < GRID:
                hs_o[gy, gx] += mh * w; hw_o[gy, gx] += w
                rs_o[gy, gx] += mr; rw_o[gy, gx] += 1
                known_o[gy, gx] = True
            # VO: 드리프트만큼 밀려서 지도에 찍힘
            gx2, gy2 = int(round(x + drift[0])), int(round(y + drift[1]))
            if 0 <= gx2 < GRID and 0 <= gy2 < GRID:
                hs_v[gy2, gx2] += mh * w; hw_v[gy2, gx2] += w
                rs_v[gy2, gx2] += mr; rw_v[gy2, gx2] += 1
                known_v[gy2, gx2] = True

    def finalize(hs, hw, rs, rw, known):
        h_map = np.full((GRID, GRID), np.nan)
        r_map = np.full((GRID, GRID), np.nan)
        m = hw > 0
        h_map[m] = hs[m] / hw[m]
        m2 = rw > 0
        r_map[m2] = rs[m2] / rw[m2]
        return h_map, r_map

    oracle_h, oracle_r = finalize(hs_o, hw_o, rs_o, rw_o, known_o)
    vo_h, vo_r = finalize(hs_v, hw_v, rs_v, rw_v, known_v)

    return {
        "true_path": np.array(true_path), "vo_path": np.array(vo_path),
        "oracle_known": known_o, "oracle_r": oracle_r,
        "vo_known": known_v, "vo_r": vo_r,
        "all_readings_log": all_readings_log,
    }


def pick_next_stop(known, risk, pos, heading, n_candidates=28):
    """알려진 영역 경계(frontier) 중, 미탐사 쪽으로 더 나아가면서도 고위험 지형은 피하는 지점을 고른다."""
    candidates = []
    for ang_offset in np.linspace(-80, 80, n_candidates):
        b = heading + ang_offset
        dist_px = rng.uniform(*STEP_RANGE_M) / CELL_M
        theta = np.radians(b)
        cand = pos + dist_px * np.array([np.sin(theta), -np.cos(theta)])
        cx, cy = cand
        if not (10 <= cx < GRID - 10 and 10 <= cy < GRID - 10):
            continue
        if np.hypot(cx - GRID / 2, cy - GRID / 2) * CELL_M > TARGET_RADIUS_M:
            continue

        # frontier score: 후보 주변 작은 창(window) 안에 '아직 모르는' 셀이 얼마나 있는지
        x0, x1 = int(cx - 6), int(cx + 6)
        y0, y1 = int(cy - 6), int(cy + 6)
        window = known[max(0, y0):y1, max(0, x0):x1]
        unknown_frac = 1.0 - (window.mean() if window.size else 1.0)

        risk_here = bilinear(risk, cx, cy)
        score = unknown_frac - 0.6 * risk_here
        candidates.append((score, cand, risk_here))

    if not candidates:
        return None
    candidates.sort(key=lambda c: -c[0])
    return candidates[0][1]


# ============================================================
# 4. 실행 + 정량 평가
# ============================================================

def iou_high_risk(est_r, true_r, known_mask, thresh=0.55):
    valid = known_mask & ~np.isnan(est_r)
    if valid.sum() == 0:
        return float("nan")
    est_hi = (est_r > thresh) & valid
    true_hi = (true_r > thresh) & valid
    inter = (est_hi & true_hi).sum()
    union = (est_hi | true_hi).sum()
    return inter / union if union else float("nan")


def main():
    h, rocks = generate_terrain()
    risk = true_risk_field(h)

    result = run_exploration(h, risk)

    coverage_o = result["oracle_known"].sum() / (np.pi * (TARGET_RADIUS_M / CELL_M) ** 2) * 100
    iou_oracle = iou_high_risk(result["oracle_r"], risk, result["oracle_known"])
    iou_vo = iou_high_risk(result["vo_r"], risk, result["vo_known"])

    true_path_m = result["true_path"] * CELL_M
    vo_path_m = result["vo_path"] * CELL_M
    path_len_true = np.sum(np.hypot(*np.diff(true_path_m, axis=0).T))
    final_pose_err_m = np.linalg.norm(result["true_path"][-1] - result["vo_path"][-1]) * CELL_M

    print(f"정지 횟수: {len(result['true_path']) - 1}")
    print(f"총 이동 거리(참값): {path_len_true:.1f} m")
    print(f"탐사 영역 커버리지(오라클 기준, 목표반경 대비): {coverage_o:.1f}%")
    print(f"최종 위치 오차 (VO vs 참값): {final_pose_err_m:.2f} m")
    print(f"고위험지대 IoU — Oracle 지도: {iou_oracle:.3f}")
    print(f"고위험지대 IoU — VO 지도(드리프트 포함): {iou_vo:.3f}")

    plot_results(h, risk, rocks, result)

    import json
    with open(f"{OUT_DIR}/exploration_stats.json", "w") as f:
        json.dump({
            "n_stops": int(len(result["true_path"]) - 1),
            "path_length_true_m": float(path_len_true),
            "coverage_pct_oracle": float(coverage_o),
            "final_pose_error_m": float(final_pose_err_m),
            "iou_high_risk_oracle": float(iou_oracle),
            "iou_high_risk_vo": float(iou_vo),
        }, f, indent=2)


# ============================================================
# 5. 시각화
# ============================================================

RISK_CMAP = LinearSegmentedColormap.from_list("risk", [(0.11, 0.42, 0.45), (0.64, 0.47, 0.12), (0.61, 0.29, 0.23)])


def style_ax(ax):
    ax.set_facecolor("#0b0e15")
    for s in ax.spines.values():
        s.set_color("#262d3d")
    ax.tick_params(colors="#a7aec1", labelsize=7)


def plot_results(h, risk, rocks, result):
    fig, axes = plt.subplots(2, 3, figsize=(17, 11), facecolor="#0b0e15")
    true_path = result["true_path"]
    vo_path = result["vo_path"]

    # (1) true terrain + rocks + true exploration path
    ax = axes[0, 0]; style_ax(ax)
    ax.imshow(h, cmap="copper", origin="upper")
    for cx, cy, r, _ in rocks:
        ax.add_patch(plt.Circle((cx, cy), r, fill=False, color="#e08a76", linewidth=0.8, alpha=0.7))
    ax.plot(true_path[:, 0], true_path[:, 1], "-", color="#5cbcc3", linewidth=1.6, label="true path")
    ax.plot(*true_path[0], "o", color="#e0ac53", markersize=9, label="landing site")
    ax.set_title("1. True terrain + rocks + true path", color="#e9ebf2", fontsize=10.5)
    ax.legend(facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2", fontsize=8)

    # (2) true risk field (ground truth)
    ax = axes[0, 1]; style_ax(ax)
    ax.imshow(risk, cmap=RISK_CMAP, vmin=0, vmax=1, origin="upper")
    ax.set_title("2. True risk field (ground truth)", color="#e9ebf2", fontsize=10.5)

    # (3) example stop-scan — occluded vs visible rays
    ax = axes[0, 2]; style_ax(ax)
    mid_pos, mid_readings = result["all_readings_log"][len(result["all_readings_log"]) // 2]
    _, rays = scan_from(h, risk, mid_pos, 0, record_rays=True)
    ax.imshow(h, cmap="copper", origin="upper", alpha=0.6)
    for ray in rays:
        xs = [p[0] for p in ray]; ys = [p[1] for p in ray]; vis = [p[2] for p in ray]
        for i in range(len(xs) - 1):
            c = "#5cbcc3" if vis[i] else "#e08a76"
            ax.plot(xs[i:i+2], ys[i:i+2], color=c, linewidth=0.6, alpha=0.5)
    ax.plot(*mid_pos, "o", color="#e0ac53", markersize=7)
    ax.set_title("3. Example scan (teal=visible, orange=occluded)", color="#e9ebf2", fontsize=9.5)

    # (4) Oracle map — true rock outlines overlaid so drift is directly visible vs (5)
    ax = axes[1, 0]; style_ax(ax)
    ax.imshow(h, cmap="gray", origin="upper", alpha=0.35)
    masked = np.ma.masked_invalid(result["oracle_r"])
    ax.imshow(masked, cmap=RISK_CMAP, vmin=0, vmax=1, origin="upper")
    for cx, cy, r, _ in rocks:
        ax.add_patch(plt.Circle((cx, cy), r, fill=False, color="#e9ebf2", linewidth=0.7, alpha=0.6))
    ax.plot(true_path[:, 0], true_path[:, 1], "-", color="#5cbcc3", linewidth=1.2, alpha=0.8)
    ax.set_title("4. Oracle map (perfect localization)", color="#e9ebf2", fontsize=10.5)

    # (5) VO map (drift included) — same true rock outlines for direct comparison
    ax = axes[1, 1]; style_ax(ax)
    ax.imshow(h, cmap="gray", origin="upper", alpha=0.25)
    masked_v = np.ma.masked_invalid(result["vo_r"])
    ax.imshow(masked_v, cmap=RISK_CMAP, vmin=0, vmax=1, origin="upper")
    for cx, cy, r, _ in rocks:
        ax.add_patch(plt.Circle((cx, cy), r, fill=False, color="#e9ebf2", linewidth=0.7, alpha=0.6))
    ax.plot(true_path[:, 0], true_path[:, 1], "--", color="#5cbcc3", linewidth=1, alpha=0.5, label="true path")
    ax.plot(vo_path[:, 0], vo_path[:, 1], "-", color="#e08a76", linewidth=1.3, label="VO estimated path")
    ax.set_title("5. VO map (drift) — white circles = true rocks", color="#e9ebf2", fontsize=10.5)
    ax.legend(facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2", fontsize=8)

    # (6) path comparison (true vs VO)
    ax = axes[1, 2]; style_ax(ax)
    ax.plot(true_path[:, 0] * CELL_M, true_path[:, 1] * CELL_M, "-o", color="#5cbcc3", markersize=3, linewidth=1.3, label="true path")
    ax.plot(vo_path[:, 0] * CELL_M, vo_path[:, 1] * CELL_M, "-o", color="#e08a76", markersize=3, linewidth=1.3, label="VO estimated path")
    ax.set_xlabel("x (m)", color="#a7aec1", fontsize=8)
    ax.set_ylabel("y (m)", color="#a7aec1", fontsize=8)
    ax.set_aspect("equal")
    ax.grid(color="#1c2230", linewidth=0.5)
    ax.legend(facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2", fontsize=8)
    ax.set_title("6. Path comparison (true vs VO)", color="#e9ebf2", fontsize=10.5)

    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/exploration_slam.png", dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    print("saved", f"{OUT_DIR}/exploration_slam.png")


if __name__ == "__main__":
    main()
