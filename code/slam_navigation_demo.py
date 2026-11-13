"""
SLAM 지도 구축 -> 위험도 계산 -> 내비게이션 통합 데모

이 스크립트는 세 기존 모듈을 이어붙인다:
  1. exploration_slam_sim.py -- 프런티어 탐사로 지도를 "만든다". 참위치 기준(oracle, 위치추정
     오차 없음)과 VO(visual odometry, 드리프트 포함) 기준으로 서로 다른 재구성 지도가 나온다.
  2. human_mission_risk.py -- 재구성된 고도맵 위에서 시간가변 결합 위험도(지형+온도+방사선)를
     계산한다. exploration_slam_sim.py가 만드는 지도는 "지형 전용" 위험도만 들고 있으므로,
     여기서는 재구성된 고도맵(oracle_h/vo_h)에 anisotropic_risk_exploration의 슬로프/바위
     함수를 그대로 다시 적용해 human_mission_risk()가 요구하는 입력을 새로 만든다.
  3. human_mission_navigation.py -- 그 위험도 위에서 A*/안전지대 다익스트라로 경로를 찾는다.

두 가지를 시연한다.
  (A) 지도 완성도 비교 -- 같은 출발점/목적지를, (참지형 / oracle SLAM맵 / VO SLAM맵) 세
      가지 위험도 추정 위에서 각각 내비게이션했을 때 경로의 최대위험도 추정이 서로 얼마나
      달라지는가. SLAM 위치추정 오차가 "내비게이션이 보는 위험도"에 섞여 들어간다는 것을
      보여준다.
  (B) 시간대 변화 -- (A)에서 쓴 것과 동일한 oracle SLAM맵 위에서, report 11과 같은
      "같은 목적지, 다른 시간대" 비교를 재현한다. SLAM이 만든 지도를 그대로 내비게이션에
      넣어도 시간가변 위험도에 따라 판단이 바뀐다는 것을 끝까지 이어서 보여준다.

범위상 생략한 것(정직하게 밝힘): 탐사가 끝난 시점의 스냅샷 비교만 한다. 실제로 경로를
걸어가는 동안 위치추정 오차가 계속 쌓이는 폐루프(closed-loop) 거동이나 실시간
재위치추정(relocalization)은 시뮬레이션하지 않았다.
"""
from __future__ import annotations

import json
import os

import numpy as np
from scipy.ndimage import binary_erosion, distance_transform_edt
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import exploration_slam_sim as sim
from exploration_slam_sim import GRID, CELL_M, RISK_CMAP
from anisotropic_risk_exploration import rock_risk_grid, slope_grids
from human_mission_risk import (
    human_mission_risk, shielding_factor_grid, thermal_risk, radiation_risk,
    W_TERRAIN, W_HUMAN, W_THERMAL, W_RADIATION,
    WARNING_THRESHOLD, SPE_START_HOUR, SPE_END_HOUR,
)
from human_mission_navigation import (
    astar, nearest_safe_zone_path_minimax, path_stats, plan_to_destination,
    style_ax, _plot_path, _marker,
)

OUT_DIR = "../outputs/slam_navigation"
os.makedirs(OUT_DIR, exist_ok=True)


# ============================================================
# 1. 재구성 고도맵 -> human_mission_risk 입력으로 변환
# ============================================================

def _fill_unknown_nearest(h_recon, known_mask):
    """미탐사 영역(NaN)을 가장 가까운 탐사된 셀의 값으로 채운다 -- 전역 평균 같은
    평탄값으로 채우면 탐사 경계에서 실제로 없는 절벽(가짜 급경사)이 생기는데,
    최근접 이웃 채움은 경계에서 기울기가 0으로 자연스럽게 이어진다."""
    if known_mask.all():
        return h_recon
    nearest_idx = distance_transform_edt(~known_mask, return_distances=False, return_indices=True)
    return h_recon[tuple(nearest_idx)]


def risk_from_reconstructed_terrain(terrain_risk_recon, h_recon, known_mask, hour, spe_active):
    """SLAM이 재구성한 '지형전용 위험도'(oracle_r/vo_r)에 시간가변 항(온도+방사선)을 결합한다.

    처음엔 재구성된 고도맵(oracle_h/vo_h)에서 slope_risk/rock_risk를 직접 다시 계산했는데,
    exploration_slam_sim.py의 깊이 노이즈 모델(depth_std가 거리^2에 비례, 먼 거리에서는
    표준편차가 지형 고도 변화량 자체보다 커짐)이 고도값 자체를 거의 못 쓰게 만들어
    재구성 지도의 거의 모든 셀이 risk=1.0로 포화되는 문제가 실제로 나왔다(known 영역의
    100%가 경고선 이상, 중앙값 0.995 -- 비교가 무의미해짐). exploration_slam_sim.py는
    애초에 "지형 위험도"를 훨씬 작은 노이즈(std=0.05) 채널(oracle_r/vo_r)로 직접
    재구성하도록 이미 설계돼 있었다 -- 그래서 지형 항은 그 기존 채널을 그대로 쓰고,
    차폐(shielding)만 재구성 고도맵(최근접 채움)에서 계산한다."""
    h_filled = _fill_unknown_nearest(h_recon, known_mask)
    shielding = shielding_factor_grid(h_filled)
    thermal_term = thermal_risk(hour)
    rad_term = radiation_risk(hour, shielding, spe_active)
    human_term = W_THERMAL * thermal_term + W_RADIATION * rad_term
    return np.clip(W_TERRAIN * terrain_risk_recon + W_HUMAN * human_term, 0, 1)


# ============================================================
# 2. 시각화
# ============================================================

def plot_map_building(result, known_o, known_v, true_path_m, vo_path_m):
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 6.4), facecolor="#0b0e15")
    titles = ["Oracle SLAM map (perfect localization)", "VO SLAM map (odometry drift)"]
    knowns = [known_o, known_v]
    paths = [result["true_path"], result["vo_path"]]
    path_colors = ["#5cbcc3", "#e0ac53"]
    for ax, title, known, path, pc in zip(axes, titles, knowns, paths, path_colors):
        style_ax(ax)
        ax.imshow(known.astype(float), cmap="Greys_r", vmin=0, vmax=1.4, origin="upper", alpha=0.85)
        ax.plot(path[:, 0], path[:, 1], "-", color=pc, linewidth=2.0)
        ax.scatter([path[0, 0]], [path[0, 1]], color="#e9ebf2", s=70, zorder=5, marker="s")
        ax.scatter([path[-1, 0]], [path[-1, 1]], color=pc, s=110, zorder=5, marker="*")
        ax.set_title(title, color="#e9ebf2", fontsize=11)
    drift_final = float(np.hypot(*(vo_path_m[-1] - true_path_m[-1])))
    fig.suptitle(f"Map built by frontier exploration -- final VO drift = {drift_final:.2f} m",
                 color="#e9ebf2", fontsize=12.5)
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/slam_map_build.png", dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"saved {OUT_DIR}/slam_map_build.png")


def plot_three_way_nav(true_risk, oracle_risk, vo_risk, known_o, known_v, start, dest, plans, hour):
    fig, axes = plt.subplots(1, 3, figsize=(16.5, 6.0), facecolor="#0b0e15")
    grids = [true_risk, oracle_risk, vo_risk]
    masks = [None, known_o, known_v]
    labels = ["Ground truth (full map)", "Oracle SLAM map", "VO SLAM map (drifted)"]
    for ax, grid, mask, label, plan in zip(axes, grids, masks, labels, plans):
        style_ax(ax)
        im = ax.imshow(grid, cmap=RISK_CMAP, vmin=0, vmax=1, origin="upper")
        if mask is not None:
            ax.contour((~mask).astype(float), levels=[0.5], colors="#6d7488", linewidths=1.0, linestyles=":")
        path = plan["direct_path"]
        if path:
            stat = plan["direct_stats"]
            _plot_path(ax, path, "#e9ebf2", lw=2.2, label=f"max risk={stat['max_risk']:.2f}")
        else:
            label += "\n(destination unreachable on this map)"
        _marker(ax, start, "#5cbcc3", marker="s")
        _marker(ax, dest, "#e9ebf2", marker="X", size=110)
        ax.set_title(label, color="#e9ebf2", fontsize=10.5)
        ax.legend(facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2", fontsize=8, loc="upper right")
    fig.suptitle(f"Same start/destination, three risk estimates -- hour {hour:02.0f}:00", color="#e9ebf2", fontsize=12.5)
    fig.colorbar(axes[0].images[0], ax=axes, fraction=0.025, pad=0.02)
    fig.savefig(f"{OUT_DIR}/slam_navigation_three_way.png", dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"saved {OUT_DIR}/slam_navigation_three_way.png")


def plot_timeofday_on_slam_map(oracle_risk_day, oracle_risk_night, known_o, start, dest, plan_day, plan_night):
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 6.4), facecolor="#0b0e15")
    for ax, grid, plan, hour, label in [
        (axes[0], oracle_risk_day, plan_day, 14.0, "daytime"),
        (axes[1], oracle_risk_night, plan_night, 2.0, "night + SPE"),
    ]:
        style_ax(ax)
        im = ax.imshow(grid, cmap=RISK_CMAP, vmin=0, vmax=1, origin="upper")
        ax.contour((~known_o).astype(float), levels=[0.5], colors="#6d7488", linewidths=1.0, linestyles=":")
        _plot_path(ax, plan["direct_path"], "#a7aec1", style="--", lw=2.0,
                   label=f"direct (max risk={plan['direct_stats']['max_risk']:.2f})")
        if plan["unsafe"] and plan.get("safe_zone_path"):
            _plot_path(ax, plan["safe_zone_path"], "#e0ac53", lw=2.4,
                       label=f"redirected (max risk={plan['safe_zone_stats']['max_risk']:.2f})")
            _marker(ax, plan["safe_zone_path"][-1], "#e0ac53", marker="*", size=140)
        _marker(ax, start, "#5cbcc3", marker="s")
        _marker(ax, dest, "#e9ebf2", marker="X", size=110)
        status = "UNSAFE -> redirected" if plan["unsafe"] else "destination OK"
        ax.set_title(f"hour {hour:02.0f}:00 ({label})\nstatus: {status}", color="#e9ebf2", fontsize=10.5)
        ax.legend(facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2", fontsize=8, loc="upper right")
    fig.suptitle("Same SLAM-built map, same destination -- time of day changes the plan",
                 color="#e9ebf2", fontsize=12, y=1.04)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(f"{OUT_DIR}/slam_navigation_timeofday.png", dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"saved {OUT_DIR}/slam_navigation_timeofday.png")


# ============================================================
# 3. 실행
# ============================================================

def main():
    print("=== SLAM 지도 구축 -> 위험도 계산 -> 내비게이션 통합 데모 ===\n")

    sim.rng = np.random.default_rng(0)
    h_true, _ = sim.generate_terrain()
    terrain_only_risk = sim.true_risk_field(h_true)

    print("[1/3] 프런티어 탐사로 지도 구축 중...")
    result = sim.run_exploration(h_true, terrain_only_risk)
    known_o, known_v = result["oracle_known"], result["vo_known"]
    true_path_m, vo_path_m = result["true_path"] * CELL_M, result["vo_path"] * CELL_M
    final_drift_m = float(np.hypot(*(vo_path_m[-1] - true_path_m[-1])))
    print(f"  탐사 스텝 {len(result['true_path'])}개, 커버리지(oracle) {known_o.mean()*100:.1f}%, "
          f"최종 VO 드리프트 {final_drift_m:.2f} m")
    plot_map_building(result, known_o, known_v, true_path_m, vo_path_m)

    # oracle_h/vo_h는 run_exploration이 돌려주지 않으므로(지형전용 risk만 저장) 여기서
    # 동일한 reconstruction 로직을 재사용해 고도맵도 함께 얻는다 -- finalize()와 동일한 방식.
    oracle_h, vo_h = _reconstruct_height_maps(result)

    hour_warn = 2.0
    spe_active = SPE_START_HOUR <= hour_warn < SPE_END_HOUR
    hour_day = 14.0

    true_risk_warn = human_mission_risk(*_terrain_terms(h_true), hour_warn, shielding_factor_grid(h_true), spe_active)
    oracle_risk_warn = risk_from_reconstructed_terrain(result["oracle_r"], oracle_h, known_o, hour_warn, spe_active)
    vo_risk_warn = risk_from_reconstructed_terrain(result["vo_r"], vo_h, known_v, hour_warn, spe_active)

    # ---- (A) 지도 완성도 비교: 같은 출발점/목적지를 세 가지 위험도 추정 위에서 내비게이션
    print("\n[2/3] (A) 지도 완성도 비교 -- 참지형 vs oracle SLAM맵 vs VO SLAM맵")
    n = GRID
    start = (n // 2, n // 2)  # 탐사 시작점 -- 모든 재구성에서 드리프트 0으로 알려진 유일한 공통 지점
    # 탐사 경계(frontier) 바로 위 셀은 미탐사 영역을 평탄하게 채운 보조 표면과 맞닿아
    # 인위적인 급경사(절벽) 아티팩트가 생길 수 있다 -- 목적지는 경계에서 몇 셀 안쪽인
    # "확실히 아는" 영역에서만 고른다(5셀 ~= 1m 침식).
    EDGE_MARGIN = 5
    common_known_core = binary_erosion(known_o, iterations=EDGE_MARGIN) & binary_erosion(known_v, iterations=EDGE_MARGIN)
    yy, xx = np.mgrid[0:n, 0:n]
    dist_from_start = np.hypot(xx - start[0], yy - start[1])
    dist_masked = np.where(common_known_core, dist_from_start, -1)
    fy, fx = np.unravel_index(np.argmax(dist_masked), dist_masked.shape)
    dest = (int(fx), int(fy))  # 두 지도 모두가 "확실히 안다"고 믿는 가장 먼 지점
    print(f"  start={start}, dest={dest} (공통 확실 지역 {common_known_core.mean()*100:.1f}%)")

    plan_true = plan_to_destination(true_risk_warn, start, dest, WARNING_THRESHOLD)
    plan_oracle = plan_to_destination(oracle_risk_warn, start, dest, WARNING_THRESHOLD, passable=known_o)
    plan_vo = plan_to_destination(vo_risk_warn, start, dest, WARNING_THRESHOLD, passable=known_v)
    for label, plan in [("참지형(ground truth)", plan_true), ("oracle SLAM맵", plan_oracle), ("VO SLAM맵", plan_vo)]:
        if plan["direct_path"]:
            print(f"  {label}: max_risk={plan['direct_stats']['max_risk']:.3f} -> {plan['recommendation']}")
        else:
            print(f"  {label}: 목적지에 도달하는 경로를 찾지 못함 (탐사 영역 밖이거나 전부 차단됨)")
    plot_three_way_nav(true_risk_warn, oracle_risk_warn, vo_risk_warn, known_o, known_v,
                        start, dest, [plan_true, plan_oracle, plan_vo], hour_warn)

    # ---- (B) 같은(oracle) SLAM 지도 위에서 시간대만 바꿔 내비게이션 판단 변화를 재현
    print("\n[3/3] (B) 같은 SLAM 지도, 다른 시간대 -- 내비게이션 판단이 바뀌는가")
    oracle_risk_day = risk_from_reconstructed_terrain(result["oracle_r"], oracle_h, known_o, hour_day, spe_active=False)
    # 주간 기준으로 "지형상 가장 무난해 보이는" 알려진 지점을 목적지로 고른다 (report 11과 동일한 취지)
    core_o = binary_erosion(known_o, iterations=EDGE_MARGIN)
    candidates_mask = core_o & (dist_from_start > 15)
    risk_candidates = np.where(candidates_mask, oracle_risk_day, np.inf)
    fy2, fx2 = np.unravel_index(np.argmin(risk_candidates), risk_candidates.shape)
    dest_b = (int(fx2), int(fy2))

    plan_day = plan_to_destination(oracle_risk_day, start, dest_b, WARNING_THRESHOLD, passable=known_o)
    plan_night = plan_to_destination(oracle_risk_warn, start, dest_b, WARNING_THRESHOLD, passable=known_o)
    print(f"  dest={dest_b} (oracle 지도 기준)")
    print(f"  낮(14시): max_risk={plan_day['direct_stats']['max_risk']:.3f} -> {plan_day['recommendation']}")
    print(f"  야간+SPE(2시): max_risk={plan_night['direct_stats']['max_risk']:.3f} -> {plan_night['recommendation']}")
    plot_timeofday_on_slam_map(oracle_risk_day, oracle_risk_warn, known_o, start, dest_b, plan_day, plan_night)

    stats = {
        "exploration": {
            "n_steps": int(len(result["true_path"])),
            "coverage_oracle_pct": float(known_o.mean() * 100),
            "coverage_vo_pct": float(known_v.mean() * 100),
            "final_vo_drift_m": final_drift_m,
        },
        "scenario_A_map_fidelity_vs_navigation": {
            "hour": hour_warn, "start": start, "dest": dest,
            "ground_truth": _brief(plan_true),
            "oracle_slam_map": _brief(plan_oracle),
            "vo_slam_map": _brief(plan_vo),
        },
        "scenario_B_timeofday_on_slam_map": {
            "start": start, "dest": dest_b,
            "daytime_14h": _brief(plan_day),
            "night_spe_2h": _brief(plan_night),
        },
        "scope_note": "탐사 종료 시점의 스냅샷 비교만 수행함 -- 실주행 중 위치추정 오차가 "
                       "누적되는 폐루프 거동이나 실시간 재위치추정은 시뮬레이션하지 않음.",
    }
    with open(f"{OUT_DIR}/slam_navigation_stats.json", "w") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    print(f"\nsaved {OUT_DIR}/slam_navigation_stats.json")


def _brief(plan):
    out = {"recommendation": plan["recommendation"]}
    if plan["direct_stats"]:
        out["direct_max_risk"] = plan["direct_stats"]["max_risk"]
        out["direct_dist_m"] = plan["direct_stats"]["dist_m"]
    else:
        out["direct_max_risk"] = None
    if plan.get("safe_zone_stats"):
        out["safe_zone_max_risk"] = plan["safe_zone_stats"]["max_risk"]
    return out


def _terrain_terms(h):
    gx, gy = slope_grids(h)
    slope_risk = np.clip(np.hypot(gx, gy) / 0.9, 0, 1)
    rock_r = rock_risk_grid(h)
    return slope_risk, rock_r


def _reconstruct_height_maps(result):
    """run_exploration()과 동일한 관측 로그로부터 고도맵만 다시 쌓는다 (risk는 이미
    있지만 고도맵은 반환하지 않으므로 이 데모에서만 필요한 재계산)."""
    n = GRID
    hs_o = np.zeros((n, n)); hw_o = np.zeros((n, n))
    hs_v = np.zeros((n, n)); hw_v = np.zeros((n, n))
    true_path, vo_path = result["true_path"], result["vo_path"]
    for i, (true_stop_pos, readings) in enumerate(result["all_readings_log"]):
        vo_stop_pos = vo_path[i]
        drift = vo_stop_pos - true_stop_pos
        for x, y, mh, mr, r_m, dstd in readings:
            w = 1.0 / (dstd ** 2)
            gx, gy = int(round(x)), int(round(y))
            if 0 <= gx < n and 0 <= gy < n:
                hs_o[gy, gx] += mh * w; hw_o[gy, gx] += w
            gx2, gy2 = int(round(x + drift[0])), int(round(y + drift[1]))
            if 0 <= gx2 < n and 0 <= gy2 < n:
                hs_v[gy2, gx2] += mh * w; hw_v[gy2, gx2] += w
    oracle_h = np.full((n, n), np.nan); vo_h = np.full((n, n), np.nan)
    m_o, m_v = hw_o > 0, hw_v > 0
    oracle_h[m_o] = hs_o[m_o] / hw_o[m_o]
    vo_h[m_v] = hs_v[m_v] / hw_v[m_v]
    return oracle_h, vo_h


if __name__ == "__main__":
    main()
