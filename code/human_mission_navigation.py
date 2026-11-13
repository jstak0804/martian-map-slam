"""
유인 미션 내비게이션 — 위험도 기반 경로탐색 + 안전지대 자동 대피 경로

human_mission_risk.py가 계산한 시간가변 결합 위험도(지형 + 온도 + 방사선) 위에 두 가지
내비게이션 기능을 추가한다.

  1. 임의 목적지 경로탐색(astar) — 사용자가 지정한 목적지까지 위험도 가중 A*로 경로를
     찾는다. reports/07-interactive-pathfinding.html의 JS A* 구현과 동일한 비용 모델
     (비용 = 이동거리 * (1 + weight*risk))을 그대로 포팅해 기존 데모와 비교 가능하게 유지한다.
  2. 안전지대 자동 대피(nearest_safe_zone_path) — 목적지가 "risk < threshold인 가장
     가까운 지점"처럼 좌표로 고정되어 있지 않다. 이건 단일 목표 A*가 아니라 다중목표
     탐색 문제이므로, 목적지까지의 직선거리 휴리스틱을 쓸 수 없다 — 그래서 순수
     다익스트라(목표 조건 충족 시 조기 종료)로 구현한다.

두 기능을 묶어 plan_to_destination()에서 "목적지 지정 -> 위험하면 안전지대로 안내"
흐름을 만든다: 목적지까지의 경로를 먼저 찾고, 그 경로의 최대 위험도가 경고선을
넘으면 원래 목적지 대신 가장 가까운 안전지대로의 경로를 대안으로 제시한다.

human_mission_risk.py의 함수(human_mission_risk, shielding_factor_grid, WARNING_THRESHOLD 등)와
anisotropic_risk_exploration.py의 rock_risk_grid/slope_grids를 코드 변경 없이 재사용한다.

설계 가정(측정값이 아님, human_mission_risk.py의 분리 관례를 그대로 따름):
  - EVA_WALK_SPEED_M_S: Apollo 달 표면 EVA 계획 문서(NASA 1979, "Planning and Conduct of
    Lunar Surface Operations" 계열)의 계획 보행 대사율 1200 BTU/hr @ 3.3 km/h(~0.92 m/s)를
    그대로 사용한다. NASA-STD-3001의 공식 "요구 사양"은 아니고 Apollo 시대 운용 계획값이지만,
    임의의 데모용 추정치보다는 문헌 근거가 있는 값이라 채택했다 — 화성 EVA는 달과 중력·
    우주복이 달라 그대로 들어맞진 않으므로 여전히 근사치로 명시한다.
  - RISK_WEIGHT: 경로비용에서 위험도에 주는 가중치 — reports/07 데모의 슬라이더 기본값과
    동일한 값을 상수로 고정.
"""
from __future__ import annotations

import heapq
import json
import os

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import exploration_slam_sim as sim
from exploration_slam_sim import CELL_M, RISK_CMAP
from anisotropic_risk_exploration import rock_risk_grid, slope_grids
from human_mission_risk import (
    human_mission_risk, shielding_factor_grid,
    WARNING_THRESHOLD, SPE_START_HOUR, SPE_END_HOUR,
)

OUT_DIR = "../outputs/human_mission_navigation"
os.makedirs(OUT_DIR, exist_ok=True)

EVA_WALK_SPEED_M_S = 0.92  # Apollo EVA 계획 보행속도(1200 BTU/hr @ 3.3km/h, NASA 1979) 채택값
RISK_WEIGHT = 6.0         # reports/07 데모와 동일한 비용 모델의 가중치 상수

NEIGHBORS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]


# ============================================================
# 1. 경로탐색 — 단일 목적지 A* / 안전지대 다익스트라
# ============================================================

def astar(risk_grid, start, goal, risk_weight=RISK_WEIGHT, passable=None):
    """단일 목적지 A* -- reports/07 JS 구현과 동일한 비용 모델(거리 * (1+weight*risk)).

    passable: SLAM으로 아직 탐사하지 못한 영역처럼 "애초에 갈 수 없는" 칸을 표시하는
    bool 그리드(None이면 전부 통행 가능, 기존 호출부와 하위호환). risk_weight로 기피시키는
    것과는 다르다 -- 미탐사 영역은 위험도를 모르는 게 아니라 그 지점에 지형이 있는지조차
    모르므로, 가중치가 아니라 완전 배제로 다룬다."""
    n = risk_grid.shape[0]
    sx, sy = start
    gx, gy = goal

    def heuristic(x, y):
        return float(np.hypot(x - gx, y - gy))

    g_score = {start: 0.0}
    came_from = {}
    open_heap = [(heuristic(sx, sy), sx, sy)]
    visited = set()

    while open_heap:
        _, cx, cy = heapq.heappop(open_heap)
        if (cx, cy) in visited:
            continue
        visited.add((cx, cy))
        if (cx, cy) == (gx, gy):
            break
        for dx, dy in NEIGHBORS:
            nx, ny = cx + dx, cy + dy
            if not (0 <= nx < n and 0 <= ny < n) or (nx, ny) in visited:
                continue
            if passable is not None and not passable[ny, nx]:
                continue
            step = float(np.hypot(dx, dy)) * (1 + risk_weight * float(risk_grid[ny, nx]))
            cand = g_score[(cx, cy)] + step
            if cand < g_score.get((nx, ny), np.inf):
                g_score[(nx, ny)] = cand
                came_from[(nx, ny)] = (cx, cy)
                heapq.heappush(open_heap, (cand + heuristic(nx, ny), nx, ny))

    if (gx, gy) not in g_score:
        return None
    path = [(gx, gy)]
    cur = (gx, gy)
    while cur != (sx, sy):
        cur = came_from[cur]
        path.append(cur)
    path.reverse()
    return path


def nearest_safe_zone_path(risk_grid, start, threshold=WARNING_THRESHOLD, risk_weight=RISK_WEIGHT):
    """다익스트라(이동비용 최소) -- 좌표가 고정된 목적지가 아니라 "risk<threshold를
    만족하는 가장 가까운(이동비용 최소) 지점"까지의 경로를 찾는다. 목표 좌표를 모르므로
    직선거리 휴리스틱을 쓸 수 없다 -- A*가 아니라 순수 다익스트라가 맞는 알고리즘이다.

    주의: 이 비용 모델은 '총 이동비용(거리+위험 누적)'을 최소화할 뿐, 경로 중간에 거치는
    "순간 최대 위험"은 보장하지 않는다 -- 도착지는 경고선 아래라도 가는 길에 더 위험한
    지점을 잠깐 지나칠 수 있다. 그 순간 최대 위험까지 안전하게 보장하려면
    nearest_safe_zone_path_minimax()를 쓴다."""
    n = risk_grid.shape[0]
    sx, sy = start

    if float(risk_grid[sy, sx]) < threshold:
        return [(sx, sy)], 0.0  # 이미 안전지대에 있음

    g_score = {start: 0.0}
    came_from = {}
    open_heap = [(0.0, sx, sy)]
    visited = set()

    while open_heap:
        cost, cx, cy = heapq.heappop(open_heap)
        if (cx, cy) in visited:
            continue
        visited.add((cx, cy))

        if float(risk_grid[cy, cx]) < threshold:
            path = [(cx, cy)]
            cur = (cx, cy)
            while cur != (sx, sy):
                cur = came_from[cur]
                path.append(cur)
            path.reverse()
            return path, cost

        for dx, dy in NEIGHBORS:
            nx, ny = cx + dx, cy + dy
            if not (0 <= nx < n and 0 <= ny < n) or (nx, ny) in visited:
                continue
            step = float(np.hypot(dx, dy)) * (1 + risk_weight * float(risk_grid[ny, nx]))
            cand = cost + step
            if cand < g_score.get((nx, ny), np.inf):
                g_score[(nx, ny)] = cand
                came_from[(nx, ny)] = (cx, cy)
                heapq.heappush(open_heap, (cand, nx, ny))

    return None, None  # 그리드 전체가 경고선 이상 -- 안전지대 없음


def nearest_safe_zone_path_minimax(risk_grid, start, threshold=WARNING_THRESHOLD, passable=None):
    """병목(bottleneck) 다익스트라 -- "총 이동비용"이 아니라 "경로상 거치는 순간 최대
    위험"을 최소화하면서 risk<threshold인 가장 가까운 지점을 찾는다. 우선순위를
    (경로 중 최대 위험, 누적거리) 튜플로 두면 -- 경로를 늘려도 최대값은 줄어들 수 없으므로
    단조성이 유지되어 다익스트라가 그대로 성립한다. "안전지대로 대피"라는 기능의
    의도(그 과정에서 더 위험해지지 않기)에 맞는 올바른 비용 모델은 거리 가중합이 아니라
    이쪽이다 -- nearest_safe_zone_path()의 총비용 최소화는 더 멀리 돌아가더라도 순간
    위험 스파이크를 허용할 수 있다는 걸 실험으로 확인했다(2b 야간 시나리오에서 재현)."""
    n = risk_grid.shape[0]
    sx, sy = start
    start_risk = float(risk_grid[sy, sx])

    if start_risk < threshold:
        return [(sx, sy)], start_risk

    best = {start: (start_risk, 0.0)}
    came_from = {}
    open_heap = [(start_risk, 0.0, sx, sy)]
    visited = set()

    while open_heap:
        path_max, dist, cx, cy = heapq.heappop(open_heap)
        if (cx, cy) in visited:
            continue
        visited.add((cx, cy))

        # 종료조건은 "현재 칸의 위험도"지, "지금까지의 경로 최대 위험도(path_max)"가 아니다 --
        # 출발지 자체가 이미 경고선 이상일 수 있어 path_max는 처음부터 threshold를 넘어
        # 있을 수 있다(그 경우 path_max<threshold는 영원히 불가능해진다). 우리가 보장하려는
        # 건 "도착지는 안전하다"는 것과 "가는 동안의 최악의 순간을 가능한 한 낮춘다"는 것이지,
        # 경로 전체가 처음부터 이미 안전하라는 게 아니다.
        if float(risk_grid[cy, cx]) < threshold:
            path = [(cx, cy)]
            cur = (cx, cy)
            while cur != (sx, sy):
                cur = came_from[cur]
                path.append(cur)
            path.reverse()
            return path, path_max

        for dx, dy in NEIGHBORS:
            nx, ny = cx + dx, cy + dy
            if not (0 <= nx < n and 0 <= ny < n) or (nx, ny) in visited:
                continue
            if passable is not None and not passable[ny, nx]:
                continue
            n_risk = float(risk_grid[ny, nx])
            cand_max = max(path_max, n_risk)
            cand_dist = dist + float(np.hypot(dx, dy))
            cand = (cand_max, cand_dist)
            if cand < best.get((nx, ny), (np.inf, np.inf)):
                best[(nx, ny)] = cand
                came_from[(nx, ny)] = (cx, cy)
                heapq.heappush(open_heap, (cand_max, cand_dist, nx, ny))

    return None, None  # 그리드 전체가 경고선 이상 -- 안전지대 없음


def path_stats(path, risk_grid):
    dist_m = 0.0
    risks = []
    for i, (x, y) in enumerate(path):
        risks.append(float(risk_grid[y, x]))
        if i > 0:
            px, py = path[i - 1]
            dist_m += float(np.hypot(x - px, y - py)) * CELL_M
    return {
        "n_steps": len(path),
        "dist_m": dist_m,
        "eta_min": dist_m / EVA_WALK_SPEED_M_S / 60,
        "mean_risk": float(np.mean(risks)),
        "max_risk": float(np.max(risks)),
    }


# ============================================================
# 2. 목적지 지정 -> 위험하면 안전지대로 안내
# ============================================================

def plan_to_destination(risk_grid, start, dest, threshold=WARNING_THRESHOLD, risk_weight=RISK_WEIGHT, passable=None):
    """목적지까지 경로를 먼저 찾고, 경로의 최대 위험도가 경고선을 넘으면 원래 목적지 대신
    가장 가까운 안전지대로의 경로를 대안으로 제시한다."""
    direct_path = astar(risk_grid, start, dest, risk_weight, passable=passable)
    direct_stats = path_stats(direct_path, risk_grid) if direct_path else None

    unsafe = direct_stats is None or direct_stats["max_risk"] >= threshold
    result = {
        "start": start, "dest": dest,
        "direct_path": direct_path, "direct_stats": direct_stats,
        "unsafe": unsafe,
        "recommendation": "SAFE_ZONE_REDIRECT" if unsafe else "DESTINATION_OK",
    }
    if unsafe:
        safe_path, safe_path_max = nearest_safe_zone_path_minimax(risk_grid, start, threshold, passable=passable)
        result["safe_zone_path"] = safe_path
        result["safe_zone_stats"] = path_stats(safe_path, risk_grid) if safe_path else None
    return result


# ============================================================
# 3. 시각화
# ============================================================

def style_ax(ax):
    ax.set_facecolor("#0b0e15")
    for s in ax.spines.values():
        s.set_color("#262d3d")
    ax.tick_params(colors="#a7aec1", labelsize=7)


def _plot_path(ax, path, color, style="-", lw=2.2, label=None):
    if not path:
        return
    xs = [p[0] for p in path]
    ys = [p[1] for p in path]
    ax.plot(xs, ys, style, color=color, linewidth=lw, label=label)


def _marker(ax, p, color, marker="o", size=60):
    ax.scatter([p[0]], [p[1]], color=color, s=size, zorder=5, edgecolor="#e9ebf2", linewidth=1.2, marker=marker)


def plot_evacuation(risk_grid, safe_mask, evac_results, hour, title_suffix):
    fig, ax = plt.subplots(figsize=(7.2, 7.2), facecolor="#0b0e15")
    style_ax(ax)
    im = ax.imshow(risk_grid, cmap=RISK_CMAP, vmin=0, vmax=1, origin="upper")
    ax.contour(safe_mask.astype(float), levels=[0.5], colors="#5cbcc3", linewidths=1.8)
    colors = ["#e9ebf2", "#a7e8a0", "#f2c879"]
    for i, r in enumerate(evac_results):
        c = colors[i % len(colors)]
        _plot_path(ax, r["path"], c, label=f"start {i+1} -> safe zone ({r['stats']['dist_m']:.1f} m)")
        _marker(ax, r["path"][0], c, marker="s")
        _marker(ax, r["path"][-1], c, marker="*", size=120)
    ax.set_title(f"Evacuation to nearest safe zone -- hour {hour:02.0f}:00{title_suffix}",
                 color="#e9ebf2", fontsize=11)
    ax.legend(facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2", fontsize=8, loc="upper right")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/evacuation_to_safe_zone.png", dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"saved {OUT_DIR}/evacuation_to_safe_zone.png")


def plot_destination_redirect(risk_grid, plan, hour, label):
    fig, ax = plt.subplots(figsize=(7.2, 7.2), facecolor="#0b0e15")
    style_ax(ax)
    im = ax.imshow(risk_grid, cmap=RISK_CMAP, vmin=0, vmax=1, origin="upper")

    _plot_path(ax, plan["direct_path"], "#a7aec1", style="--", lw=2.0,
               label=f"direct to destination (max risk={plan['direct_stats']['max_risk']:.2f})")
    _marker(ax, plan["start"], "#5cbcc3", marker="s")
    _marker(ax, plan["dest"], "#e9ebf2", marker="X", size=120)

    if plan["unsafe"] and plan.get("safe_zone_path"):
        _plot_path(ax, plan["safe_zone_path"], "#e0ac53", lw=2.4,
                   label=f"redirected to safe zone (max risk={plan['safe_zone_stats']['max_risk']:.2f})")
        _marker(ax, plan["safe_zone_path"][-1], "#e0ac53", marker="*", size=140)

    status = "UNSAFE -> redirected" if plan["unsafe"] else "destination OK"
    ax.set_title(f"Destination request -- hour {hour:02.0f}:00 ({label})\nstatus: {status}",
                 color="#e9ebf2", fontsize=10.5)
    ax.legend(facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2", fontsize=8, loc="upper right")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
    fig.tight_layout()
    fname = f"{OUT_DIR}/destination_{label}.png"
    fig.savefig(fname, dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"saved {fname}")


# ============================================================
# 4. 실행
# ============================================================

def main():
    print("=== 유인 미션 내비게이션 -- 위험도 기반 경로탐색 + 안전지대 자동 대피 ===\n")

    sim.rng = np.random.default_rng(0)
    h, _ = sim.generate_terrain()
    n = h.shape[0]

    gx_grid, gy_grid = slope_grids(h)
    slope = np.hypot(gx_grid, gy_grid)
    slope_risk = np.clip(slope / 0.9, 0, 1)
    rock_r = rock_risk_grid(h)
    shielding = shielding_factor_grid(h)

    # ---- 시나리오 1: 야간 + SPE 중첩(hour=2, human_mission_risk.py가 이미 보여준 최악의 경우)
    #      에서 세 지점에서 각각 가장 가까운 안전지대로 대피 경로를 찾는다.
    hour_warn = 2.0
    spe_active = SPE_START_HOUR <= hour_warn < SPE_END_HOUR
    risk_warn = human_mission_risk(slope_risk, rock_r, hour_warn, shielding, spe_active)
    safe_mask_warn = risk_warn < WARNING_THRESHOLD
    print(f"hour={hour_warn:.0f} (SPE={spe_active}) 전체 평균 위험도={risk_warn.mean():.3f}, "
          f"안전지대 비율={safe_mask_warn.mean()*100:.1f}%")

    starts = [(20, 20), (n - 30, n - 40), (n // 2, 25)]
    evac_results = []
    for s in starts:
        # 비교: 총 이동비용 최소화(cost) vs 경로상 순간 최대위험 최소화(minimax).
        cost_path, _ = nearest_safe_zone_path(risk_warn, s, WARNING_THRESHOLD, RISK_WEIGHT)
        path, path_max = nearest_safe_zone_path_minimax(risk_warn, s, WARNING_THRESHOLD)
        if path is None:
            print(f"  start={s}: 안전지대를 찾지 못함 (그리드 전체가 경고선 이상)")
            continue
        stats = path_stats(path, risk_warn)
        cost_stats = path_stats(cost_path, risk_warn) if cost_path else None
        evac_results.append({"start": s, "path": path, "stats": stats})
        print(f"  start={s} -> safe zone {path[-1]} [minimax]: {stats['dist_m']:.1f} m, "
              f"ETA {stats['eta_min']:.1f} min, mean_risk={stats['mean_risk']:.3f}, "
              f"max_risk={stats['max_risk']:.3f}")
        if cost_stats and cost_path[-1] != path[-1]:
            print(f"    (참고: 총비용 최소화 버전은 다른 안전지대 {cost_path[-1]}로 안내 -- "
                  f"max_risk={cost_stats['max_risk']:.3f} vs minimax {stats['max_risk']:.3f})")

    plot_evacuation(risk_warn, safe_mask_warn, evac_results, hour_warn,
                     title_suffix=" (extreme cold + SPE overlap)")

    # ---- 시나리오 2: 임의 목적지 지정 -- 지형이 위험한 지점을 목적지로 잡으면
    #      시간(낮/밤)과 무관하게 경고가 뜨고 안전지대로 안내되는지 확인.
    terrain_only_term = 0.4 * slope_risk + 0.6 * rock_r
    rocky_idx = np.unravel_index(np.argmax(terrain_only_term), terrain_only_term.shape)
    dest_risky = (int(rocky_idx[1]), int(rocky_idx[0]))  # (x, y)
    start_a = (15, n - 20)

    hour_day = 14.0
    risk_day = human_mission_risk(slope_risk, rock_r, hour_day, shielding, spe_active=False)
    plan_risky_dest = plan_to_destination(risk_day, start_a, dest_risky, WARNING_THRESHOLD, RISK_WEIGHT)
    print(f"\n[시나리오 2a] 낮(14시)에 지형 위험 최대 지점을 목적지로 지정: {dest_risky}")
    print(f"  직행 경로 max_risk={plan_risky_dest['direct_stats']['max_risk']:.3f} "
          f"(경고선 {WARNING_THRESHOLD}) -> {plan_risky_dest['recommendation']}")
    if plan_risky_dest["unsafe"]:
        print(f"  안전지대로 안내: {plan_risky_dest['safe_zone_stats']}")
    plot_destination_redirect(risk_day, plan_risky_dest, hour_day, "risky_terrain_daytime")

    # ---- 시나리오 2b: 지형은 평범하지만, 야간+SPE 시간대에 같은 목적지를 지정하면
    #      전역적으로 위험도가 올라가 있어 더 쉽게 경고선을 넘는지 비교.
    safe_looking_idx = np.unravel_index(np.argmin(terrain_only_term), terrain_only_term.shape)
    dest_calm = (int(safe_looking_idx[1]), int(safe_looking_idx[0]))
    plan_calm_dest_day = plan_to_destination(risk_day, start_a, dest_calm, WARNING_THRESHOLD, RISK_WEIGHT)
    plan_calm_dest_night = plan_to_destination(risk_warn, start_a, dest_calm, WARNING_THRESHOLD, RISK_WEIGHT)
    print(f"\n[시나리오 2b] 지형상 가장 안전한 지점({dest_calm})을 목적지로 지정:")
    print(f"  낮(14시): max_risk={plan_calm_dest_day['direct_stats']['max_risk']:.3f} "
          f"-> {plan_calm_dest_day['recommendation']}")
    print(f"  야간+SPE(2시): max_risk={plan_calm_dest_night['direct_stats']['max_risk']:.3f} "
          f"-> {plan_calm_dest_night['recommendation']}")
    plot_destination_redirect(risk_day, plan_calm_dest_day, hour_day, "calm_terrain_daytime")
    plot_destination_redirect(risk_warn, plan_calm_dest_night, hour_warn, "calm_terrain_night_spe")

    # ---- 저장
    def _serialize_plan(p):
        out = {k: v for k, v in p.items() if k not in ("direct_path", "safe_zone_path")}
        out["direct_path_n"] = len(p["direct_path"]) if p["direct_path"] else 0
        if p.get("safe_zone_path"):
            out["safe_zone_path_n"] = len(p["safe_zone_path"])
        return out

    stats = {
        "design_assumptions": {
            "EVA_WALK_SPEED_M_S": EVA_WALK_SPEED_M_S,
            "RISK_WEIGHT": RISK_WEIGHT,
            "WARNING_THRESHOLD": WARNING_THRESHOLD,
            "note": "EVA_WALK_SPEED_M_S는 Apollo EVA 계획 문헌치(NASA 1979, 0.92 m/s) 채택값, "
                    "RISK_WEIGHT는 실제 사양이 아닌 설계 가정 -- human_mission_risk.py와 동일한 "
                    "분리 관례를 따른다.",
        },
        "scenario_1_evacuation": {
            "hour": hour_warn, "spe_active": spe_active,
            "mean_risk": float(risk_warn.mean()),
            "safe_zone_area_pct": float(safe_mask_warn.mean() * 100),
            "results": [{"start": r["start"], "safe_zone": r["path"][-1], **r["stats"]} for r in evac_results],
        },
        "scenario_2a_risky_terrain_destination": _serialize_plan(plan_risky_dest),
        "scenario_2b_calm_terrain_destination_day": _serialize_plan(plan_calm_dest_day),
        "scenario_2b_calm_terrain_destination_night_spe": _serialize_plan(plan_calm_dest_night),
    }
    with open(f"{OUT_DIR}/navigation_stats.json", "w") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    print(f"\nsaved {OUT_DIR}/navigation_stats.json")


if __name__ == "__main__":
    main()
