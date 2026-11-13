"""
차별화된 위험도 공식 — 방향성(anisotropic) 경사 위험도

기존 true_risk_field()는 경사의 '크기'만 본다 — 로버가 그 경사를 어느 방향으로
통과하는지는 전혀 고려하지 않는다. 실제로는 경사를 똑바로 오르내리는 것(피치 방향)과
등고선을 따라 가로지르는 것(롤 방향)은 전복 위험이 다르다 — 실제 로버 운용에서도
롤/피치 허용치를 따로 둔다. 이 스크립트는 그 비대칭을 공식에 반영한다.

  1. 경사 벡터를 진행방향 성분(along, 피치)과 수직 성분(cross, 롤)으로 분해하고,
     롤 성분에 더 큰 가중치(W_ROLL > W_PITCH)를 줘서 "같은 경사라도 등고선을
     가로지르면 더 위험하다"는 공식을 만든다. 가중치 자체는 측정값이 아니라
     "옆으로 기울어지는 쪽이 앞뒤로 기울어지는 쪽보다 더 위험하다"는, 흔히 쓰이는
     단순화된 가정이라는 걸 밝힌다.
  2. W_PITCH=W_ROLL=1일 때 slope_along^2+slope_cross^2=slope^2이므로 기존 등방
     공식과 수치적으로 완전히 같아짐을 코드로 직접 확인한다 — 새 공식이 기존
     공식을 깨는 게 아니라 엄밀히 일반화한 것임을 보증.
  3. 탐사 중 다음 정지 지점을 고르는 의사결정(pick_next_stop)에 이 방향성
     위험도를 꽂아서, 로버가 "경사를 가로지르는 이동"을 적극적으로 피하게 만든다.
  4. 같은 지형(동일 시드) 위에서 기존(등방) 로버와 10시드에 걸쳐 비교한다 — 지도
     IoU는 비슷한지, 로버가 실제로 밟은 경로의 '전복 노출도'(실제 이동 방향 기준
     경사 위험도)는 줄어드는지.

exploration_slam_sim.py의 generate_terrain/scan_from/bilinear/iou_high_risk는
그대로 재사용하고, 의사결정 로직(pick_next_stop)과 탐사 루프(run_exploration)만
방향성 버전으로 새로 작성한다 — 원본 파일은 수정하지 않는다.
"""
from __future__ import annotations

import json
import numpy as np
import matplotlib
from scipy.ndimage import uniform_filter

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import exploration_slam_sim as sim
from exploration_slam_sim import GRID, CELL_M, STEP_RANGE_M, TARGET_RADIUS_M, N_STOPS, RISK_CMAP

OUT_DIR = "../outputs/exploration"
N_SEEDS = 10
W_PITCH = 0.75   # 진행방향(피치) 경사 위험 가중치 — 모델링 가정
W_ROLL = 1.35    # 수직방향(롤) 경사 위험 가중치 — 더 위험하다고 가정 (모델링 가정)


# ============================================================
# 1. 방향성 위험도 공식
# ============================================================

def slope_grids(h):
    gy, gx = np.gradient(h, CELL_M)
    return gx, gy


def rock_risk_grid(h):
    """true_risk_field()의 거칠기(바위 proxy) 항과 동일 공식 — 그대로 재사용."""
    local_mean = uniform_filter(h, 5)
    local_sq = uniform_filter(h ** 2, 5)
    roughness = np.sqrt(np.clip(local_sq - local_mean ** 2, 0, None))
    return np.clip(roughness / 0.12, 0, 1)


def aniso_slope_risk(gx_grid, gy_grid, x, y, heading_deg, w_pitch=W_PITCH, w_roll=W_ROLL):
    gx_s = sim.bilinear(gx_grid, x, y)
    gy_s = sim.bilinear(gy_grid, x, y)
    theta = np.radians(heading_deg)
    ux, uy = np.sin(theta), -np.cos(theta)  # scan_from/run_exploration과 동일한 heading 규약
    vx, vy = -uy, ux                         # 진행방향에 수직(90도 회전)
    g_along = gx_s * ux + gy_s * uy
    g_cross = gx_s * vx + gy_s * vy
    return np.clip(np.hypot(w_pitch * g_along, w_roll * g_cross) / 0.9, 0, 1)


def aniso_risk_combined(gx_grid, gy_grid, rock_grid, x, y, heading_deg):
    slope_r = aniso_slope_risk(gx_grid, gy_grid, x, y, heading_deg)
    rock_r = sim.bilinear(rock_grid, x, y)
    return np.clip(0.4 * slope_r + 0.6 * rock_r, 0, 1)


def sanity_check_reduces_to_isotropic(h):
    """W_PITCH=W_ROLL=1이면 기존 true_risk_field와 수치적으로 같아야 한다.

    정확히 격자점(정수 좌표)에서 비교한다 — bilinear 보간은 비선형 clip() 앞에서
    할지 뒤에서 할지에 따라 결과가 미세하게 달라지므로(보간 순서 문제), 보간이
    끼어들지 않는 정수 좌표에서 비교해야 공식 자체의 동등성을 깨끗하게 검증한다."""
    gx_grid, gy_grid = slope_grids(h)
    rock_grid = rock_risk_grid(h)
    iso = sim.true_risk_field(h)
    rng_check = np.random.default_rng(0)
    max_diff = 0.0
    for _ in range(200):
        x = int(rng_check.integers(5, GRID - 5))
        y = int(rng_check.integers(5, GRID - 5))
        heading = rng_check.uniform(0, 360)
        slope_r = aniso_slope_risk(gx_grid, gy_grid, x, y, heading, w_pitch=1.0, w_roll=1.0)
        rock_r = sim.bilinear(rock_grid, x, y)
        combined = np.clip(0.4 * slope_r + 0.6 * rock_r, 0, 1)
        ref = sim.bilinear(iso, x, y)
        max_diff = max(max_diff, abs(combined - ref))
    assert max_diff < 1e-9, f"일반화 검증 실패, max_diff={max_diff}"
    print(f"sanity check 통과: W_PITCH=W_ROLL=1일 때 기존 등방 공식과 격자점에서 완전히 일치 (max diff={max_diff:.2e})")
    print("  -> 방향성 공식은 기존 공식을 깨는 게 아니라 엄밀히 일반화한 것.")


# ============================================================
# 2. 방향성 위험도를 쓰는 탐사 루프
# ============================================================

def pick_next_stop_aniso(known, gx_grid, gy_grid, rock_grid, pos, heading, n_candidates=28):
    candidates = []
    for ang_offset in np.linspace(-80, 80, n_candidates):
        b = heading + ang_offset
        dist_px = sim.rng.uniform(*STEP_RANGE_M) / CELL_M
        theta = np.radians(b)
        cand = pos + dist_px * np.array([np.sin(theta), -np.cos(theta)])
        cx, cy = cand
        if not (10 <= cx < GRID - 10 and 10 <= cy < GRID - 10):
            continue
        if np.hypot(cx - GRID / 2, cy - GRID / 2) * CELL_M > TARGET_RADIUS_M:
            continue

        x0, x1 = int(cx - 6), int(cx + 6)
        y0, y1 = int(cy - 6), int(cy + 6)
        window = known[max(0, y0):y1, max(0, x0):x1]
        unknown_frac = 1.0 - (window.mean() if window.size else 1.0)

        # 기존과의 핵심 차이: 등방 위험도가 아니라 "방향 b로 이동해 cand에 도착하는" 전복 위험도
        risk_here = aniso_risk_combined(gx_grid, gy_grid, rock_grid, cx, cy, b)
        score = unknown_frac - 0.6 * risk_here
        candidates.append((score, cand, risk_here))

    if not candidates:
        return None
    candidates.sort(key=lambda c: -c[0])
    return candidates[0][1]


def run_exploration_aniso(h, risk_iso):
    """sim.run_exploration()과 동일한 구조 — 의사결정에만 방향성 위험도를 쓴다."""
    gx_grid, gy_grid = slope_grids(h)
    rock_grid = rock_risk_grid(h)

    known = np.zeros((GRID, GRID), dtype=bool)
    center = GRID / 2
    true_pos = np.array([center, center])
    true_heading = 0.0
    true_path = [true_pos.copy()]
    vo_pos = true_pos.copy()
    vo_path = [vo_pos.copy()]
    all_readings_log = []
    headings_used = []

    for step in range(N_STOPS):
        readings, _ = sim.scan_from(h, risk_iso, true_pos, true_heading)
        all_readings_log.append((true_pos.copy(), readings))
        for x, y, *_ in readings:
            gx, gy = int(round(x)), int(round(y))
            if 0 <= gx < GRID and 0 <= gy < GRID:
                known[gy, gx] = True

        target = pick_next_stop_aniso(known, gx_grid, gy_grid, rock_grid, true_pos, true_heading)
        if target is None:
            break
        direction = target - true_pos
        dist_px = np.linalg.norm(direction)
        heading_to_target = (np.degrees(np.arctan2(direction[0], -direction[1]))) % 360
        headings_used.append(heading_to_target)

        true_heading = heading_to_target
        true_pos = true_pos + direction
        true_path.append(true_pos.copy())

        scale_err = sim.rng.normal(0.95, 0.035)
        heading_err_deg = sim.rng.normal(0, 2.2)
        est_dist = dist_px * scale_err
        est_heading = heading_to_target + heading_err_deg
        th = np.radians(est_heading)
        vo_pos = vo_pos + est_dist * np.array([np.sin(th), -np.cos(th)])
        vo_path.append(vo_pos.copy())

    known_o = np.zeros((GRID, GRID), dtype=bool)
    rs_o = np.zeros((GRID, GRID)); rw_o = np.zeros((GRID, GRID))
    known_v = np.zeros((GRID, GRID), dtype=bool)
    rs_v = np.zeros((GRID, GRID)); rw_v = np.zeros((GRID, GRID))

    for i, (true_stop_pos, readings) in enumerate(all_readings_log):
        vo_stop_pos = vo_path[i]
        drift = vo_stop_pos - true_stop_pos
        for x, y, mh, mr, r_m, dstd in readings:
            w = 1.0 / (dstd ** 2)
            gx, gy = int(round(x)), int(round(y))
            if 0 <= gx < GRID and 0 <= gy < GRID:
                rs_o[gy, gx] += mr * w; rw_o[gy, gx] += w; known_o[gy, gx] = True
            gx2, gy2 = int(round(x + drift[0])), int(round(y + drift[1]))
            if 0 <= gx2 < GRID and 0 <= gy2 < GRID:
                rs_v[gy2, gx2] += mr * w; rw_v[gy2, gx2] += w; known_v[gy2, gx2] = True

    def finalize(rs, rw):
        r_map = np.full((GRID, GRID), np.nan)
        m = rw > 0
        r_map[m] = rs[m] / rw[m]
        return r_map

    return {
        "true_path": np.array(true_path), "vo_path": np.array(vo_path),
        "headings_used": np.array(headings_used),
        "oracle_known": known_o, "oracle_r": finalize(rs_o, rw_o),
        "vo_known": known_v, "vo_r": finalize(rs_v, rw_v),
    }


# ============================================================
# 3. 평가 지표 — "전복 노출도" (실제로 밟은 경로의 방향성 위험도)
# ============================================================

def headings_from_path(path):
    headings = []
    for i in range(1, len(path)):
        d = path[i] - path[i - 1]
        headings.append(np.degrees(np.arctan2(d[0], -d[1])) % 360)
    return np.array(headings)


def tilt_exposure(path, headings, gx_grid, gy_grid):
    """실제로 밟은 각 구간을, 그 구간의 실제 이동 방향 기준 방향성 경사 위험도로 평가한 평균.
    두 로버(등방/방향성) 모두 '참 지형'과 '실제로 이동한 방향' 기준으로 똑같은 잣대로 채점한다."""
    if len(headings) == 0:
        return float("nan")
    vals = [aniso_slope_risk(gx_grid, gy_grid, path[i][0], path[i][1], headings[i]) for i in range(len(headings))]
    return float(np.mean(vals))


# ============================================================
# 4. 시드 반복 실행
# ============================================================

def run_one_seed(seed: int):
    ss = np.random.SeedSequence(seed)
    terrain_rng, base_rng, aniso_rng = [np.random.default_rng(s) for s in ss.spawn(3)]

    sim.rng = terrain_rng
    h, rocks = sim.generate_terrain()
    risk_iso = sim.true_risk_field(h)
    gx_grid, gy_grid = slope_grids(h)

    sim.rng = base_rng
    result_base = sim.run_exploration(h, risk_iso)

    sim.rng = aniso_rng
    result_aniso = run_exploration_aniso(h, risk_iso)

    headings_base = headings_from_path(result_base["true_path"])
    headings_aniso = result_aniso["headings_used"]

    exposure_base = tilt_exposure(result_base["true_path"], headings_base, gx_grid, gy_grid)
    exposure_aniso = tilt_exposure(result_aniso["true_path"], headings_aniso, gx_grid, gy_grid)

    iou_o_base = sim.iou_high_risk(result_base["oracle_r"], risk_iso, result_base["oracle_known"])
    iou_v_base = sim.iou_high_risk(result_base["vo_r"], risk_iso, result_base["vo_known"])
    iou_o_aniso = sim.iou_high_risk(result_aniso["oracle_r"], risk_iso, result_aniso["oracle_known"])
    iou_v_aniso = sim.iou_high_risk(result_aniso["vo_r"], risk_iso, result_aniso["vo_known"])

    path_len_base = float(np.sum(np.hypot(*np.diff(result_base["true_path"] * CELL_M, axis=0).T)))
    path_len_aniso = float(np.sum(np.hypot(*np.diff(result_aniso["true_path"] * CELL_M, axis=0).T)))

    row = {
        "seed": seed,
        "n_stops_base": int(len(result_base["true_path"]) - 1),
        "n_stops_aniso": int(len(result_aniso["true_path"]) - 1),
        "path_len_base_m": path_len_base, "path_len_aniso_m": path_len_aniso,
        "tilt_exposure_base": exposure_base, "tilt_exposure_aniso": exposure_aniso,
        "iou_oracle_base": float(iou_o_base), "iou_oracle_aniso": float(iou_o_aniso),
        "iou_vo_base": float(iou_v_base), "iou_vo_aniso": float(iou_v_aniso),
    }
    viz = (h, risk_iso, result_base, result_aniso) if seed == 0 else None
    return row, viz


def main():
    print("=== 방향성(anisotropic) 위험도 공식 — 등방 공식 대비 검증 ===\n")

    h0, _ = sim.generate_terrain()
    sanity_check_reduces_to_isotropic(h0)
    print()

    rows = []
    viz = None
    for seed in range(N_SEEDS):
        row, v = run_one_seed(seed)
        rows.append(row)
        if v is not None:
            viz = v
        print(f"  seed={seed}  전복노출도: 등방={row['tilt_exposure_base']:.3f} 방향성={row['tilt_exposure_aniso']:.3f}  |  "
              f"IoU(oracle): 등방={row['iou_oracle_base']:.3f} 방향성={row['iou_oracle_aniso']:.3f}  |  "
              f"IoU(vo): 등방={row['iou_vo_base']:.3f} 방향성={row['iou_vo_aniso']:.3f}")

    def agg(key):
        vals = np.array([r[key] for r in rows], dtype=float)
        return float(np.nanmean(vals)), float(np.nanstd(vals)), int(np.isnan(vals).sum())

    keys = ["tilt_exposure_base", "tilt_exposure_aniso", "iou_oracle_base", "iou_oracle_aniso",
            "iou_vo_base", "iou_vo_aniso", "path_len_base_m", "path_len_aniso_m"]
    summary = {"n_seeds": N_SEEDS, "w_pitch": W_PITCH, "w_roll": W_ROLL, "runs": rows}
    print(f"\n{'지표':>22} {'등방(기존)':>16} {'방향성(신규)':>16}")
    for base_key, aniso_key, label in [
        ("tilt_exposure_base", "tilt_exposure_aniso", "전복 노출도"),
        ("iou_oracle_base", "iou_oracle_aniso", "위험지대 IoU(oracle)"),
        ("iou_vo_base", "iou_vo_aniso", "위험지대 IoU(vo)"),
        ("path_len_base_m", "path_len_aniso_m", "총 이동거리(m)"),
    ]:
        bm, bs, bn = agg(base_key)
        am, asd, an = agg(aniso_key)
        summary[f"{base_key}_mean"] = bm; summary[f"{base_key}_std"] = bs
        summary[f"{aniso_key}_mean"] = am; summary[f"{aniso_key}_std"] = asd
        print(f"{label:>22} {bm:>10.3f}±{bs:<5.3f} {am:>10.3f}±{asd:<5.3f}")

    with open(f"{OUT_DIR}/anisotropic_risk_stats.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nsaved {OUT_DIR}/anisotropic_risk_stats.json")

    if viz is not None:
        plot_comparison(*viz)


# ============================================================
# 5. 시각화
# ============================================================

def style_ax(ax):
    ax.set_facecolor("#0b0e15")
    for s in ax.spines.values():
        s.set_color("#262d3d")
    ax.tick_params(colors="#a7aec1", labelsize=7)


def plot_comparison(h, risk, result_base, result_aniso):
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2), facecolor="#0b0e15")

    ax = axes[0]; style_ax(ax)
    ax.imshow(risk, cmap=RISK_CMAP, vmin=0, vmax=1, origin="upper")
    ax.set_title("True risk field (ground truth)", color="#e9ebf2", fontsize=9.5)

    ax = axes[1]; style_ax(ax)
    ax.imshow(h, cmap="copper", origin="upper", alpha=0.55)
    tp = result_base["true_path"]
    ax.plot(tp[:, 0], tp[:, 1], "-o", color="#e08a76", markersize=2.5, linewidth=1.3, label="isotropic (baseline)")
    ax.set_title("Baseline path (isotropic risk)", color="#e9ebf2", fontsize=9.5)
    ax.legend(facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2", fontsize=7.5)

    ax = axes[2]; style_ax(ax)
    ax.imshow(h, cmap="copper", origin="upper", alpha=0.55)
    ta = result_aniso["true_path"]
    ax.plot(tp[:, 0], tp[:, 1], "--", color="#e08a76", linewidth=0.9, alpha=0.6, label="isotropic (baseline)")
    ax.plot(ta[:, 0], ta[:, 1], "-o", color="#5cbcc3", markersize=2.5, linewidth=1.3, label="anisotropic (new)")
    ax.set_title("Anisotropic path — same terrain, same start", color="#e9ebf2", fontsize=9.5)
    ax.legend(facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2", fontsize=7.5)

    fig.suptitle("Anisotropic (direction-aware) risk vs isotropic baseline — seed=0, same terrain", color="#a7aec1", fontsize=10)
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/anisotropic_risk_comparison.png", dpi=135, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"saved {OUT_DIR}/anisotropic_risk_comparison.png")


if __name__ == "__main__":
    main()
