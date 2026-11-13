"""
산소 효율 경로탐색 — 최단거리/위험도 경로가 아니라 "우주인 산소 소모량"을 최소화하는 경로

지금까지의 내비게이션(human_mission_navigation.py)은 비용 = 이동거리 * (1 + weight*risk)였다.
유인 EVA에서 실제로 임무 반경을 묶는 건 PLSS(생명유지장치)의 산소·소모품이고, Apollo도
"남은 소모품으로 착륙선까지 걸어 돌아올 수 있는가(walkback limit)"로 운용 반경을 정했다
(NASA 1979, 3.3 km/h · 1440 BTU/hr 기준). 그래서 경로비용을 "이 칸을 지나는 동안 쓰는
산소 질량(g)"으로 바꾼다.

대사율 모델 — Pandolf 식(Pandolf et al. 1977, 군 보행 부하 대사식. NASA IEEE EMBC 2024에서
EVA 작업부하 추정에 사용):
    M[W] = 1.5*W + 2.0*(W+L)*(L/W)^2 + eta*(W+L)*(1.5*V^2 + 0.35*V*G)
    W: 체중, L: 짐(우주복+PLSS), V: 속도[m/s], G: 경사[%], eta: 지형계수(포장도로 1.0 ~ 모래 2.1)

설계 가정(측정값이 아님 — human_mission_risk.py의 분리 관례를 따름):
  - 부분중력: Pandolf는 지구 1g 실험식이다. 이 식의 질량 항은 사실상 "무게"에 대한 경험식이므로
    W, L에 중력비(g/g_earth)를 곱한 지구등가 질량으로 평가한다. 화성(0.38g)에서 평지 보행
    ~300 W로, Apollo 달 계획 대사율 1200 BTU/hr(~352 W)와 같은 자릿수가 나오는지로 검산한다.
  - 내리막: Pandolf는 G<0에서 대사량을 과소평가한다고 알려져 있다(Santee 보정이 따로 있음).
    여기서는 내리막을 평지와 같은 비용으로 둔다(G<0 -> 0) — 보수적 근사.
  - 속도: 경사와 무관하게 EVA_WALK_SPEED_M_S로 일정 — 실제로는 오르막에서 느려진다.
  - 지형계수 eta: 암석 거칠기 위험(rock_risk 0~1)을 1.0(평탄) ~ 1.5(Pandolf "heavy brush"
    급)로 선형 대응 — 바위 사이를 피해 걷는 추가 부담의 대리 지표.
  - 보행 가능 경사 상한 MAX_WALK_SLOPE_DEG: 부분중력에서 보행 안정성이 떨어진다는 논의를 반영한
    하드 제약. 이 값을 넘는 칸은 비용과 무관하게 통행 불가.
  - 산소 환산: 산소 1 L당 에너지 ~20.1 kJ(호흡상 ~0.85 근방의 일반 생리학 근사), 산소 밀도
    1.429 g/L(STP).
"""
from __future__ import annotations

import heapq
import json
import os

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from human_mission_navigation import EVA_WALK_SPEED_M_S, NEIGHBORS, astar, style_ax, _marker

OUT_DIR = "../outputs/metabolic_navigation"
os.makedirs(OUT_DIR, exist_ok=True)

G_RATIO_MARS = 0.378
G_RATIO_MOON = 0.165

BODY_MASS_KG = 75.0        # 설계 가정: 우주인 체중
SUIT_MASS_KG = 90.0        # 설계 가정: 우주복+PLSS 질량(Apollo A7L+PLSS 지구 질량과 같은 자릿수)
ETA_MIN, ETA_MAX = 1.0, 1.5
MAX_WALK_SLOPE_DEG = 20.0  # 설계 가정: 부분중력 보행 안정성 하드 제약

O2_KJ_PER_L = 20.1
O2_G_PER_L = 1.429
APOLLO_PLAN_W = 1200 * 0.29307  # 1200 BTU/hr -> W (NASA 1979 계획 대사율, 검산용)


# ============================================================
# 1. 대사율 / 산소 모델
# ============================================================

def metabolic_rate_w(grade_pct, eta=1.0, g_ratio=G_RATIO_MARS, v=EVA_WALK_SPEED_M_S):
    """Pandolf 식 — 질량 항을 중력비로 스케일한 지구등가 질량으로 평가."""
    w = BODY_MASS_KG * g_ratio
    l = SUIT_MASS_KG * g_ratio
    g = np.maximum(grade_pct, 0.0)  # 내리막 = 평지 (보수적)
    return 1.5 * w + 2.0 * (w + l) * (l / w) ** 2 + eta * (w + l) * (1.5 * v ** 2 + 0.35 * v * g)


def o2_g_per_s(metabolic_w):
    return metabolic_w / (O2_KJ_PER_L * 1000) * O2_G_PER_L


def eta_from_rock(rock_risk):
    return ETA_MIN + (ETA_MAX - ETA_MIN) * np.clip(rock_risk, 0, 1)


def slope_deg_grid(h, cell_m):
    gy, gx = np.gradient(h, cell_m)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def step_o2_g(h, eta, cell_m, cx, cy, nx, ny, g_ratio):
    """(cx,cy)->(nx,ny) 한 칸 이동의 산소 소모(g). 경사는 이동 방향의 고도차로 계산 — 비대칭
    (같은 칸 사이라도 오르막 방향이 더 비싸다)."""
    dist_m = float(np.hypot(nx - cx, ny - cy)) * cell_m
    grade_pct = (float(h[ny, nx]) - float(h[cy, cx])) / dist_m * 100
    e = 0.5 * (float(eta[cy, cx]) + float(eta[ny, nx]))
    return float(o2_g_per_s(metabolic_rate_w(grade_pct, e, g_ratio))) * dist_m / EVA_WALK_SPEED_M_S


# ============================================================
# 2. 산소 최소 A*
# ============================================================

def astar_o2(h, eta, passable, start, goal, cell_m, g_ratio=G_RATIO_MARS):
    """휴리스틱 = 직선거리 * (평지·eta=1의 m당 산소) — 내리막을 평지로 두고 eta>=1이므로 어떤
    실제 경로도 이보다 싸질 수 없어 admissible."""
    rows, cols = h.shape
    gx, gy = goal
    o2_per_m_floor = float(o2_g_per_s(metabolic_rate_w(0.0, ETA_MIN, g_ratio))) / EVA_WALK_SPEED_M_S

    def heuristic(x, y):
        return float(np.hypot(x - gx, y - gy)) * cell_m * o2_per_m_floor

    g_score = {start: 0.0}
    came_from = {}
    open_heap = [(heuristic(*start), start[0], start[1])]
    visited = set()
    while open_heap:
        _, cx, cy = heapq.heappop(open_heap)
        if (cx, cy) in visited:
            continue
        visited.add((cx, cy))
        if (cx, cy) == goal:
            break
        for dx, dy in NEIGHBORS:
            nx, ny = cx + dx, cy + dy
            if not (0 <= nx < cols and 0 <= ny < rows) or (nx, ny) in visited or not passable[ny, nx]:
                continue
            cand = g_score[(cx, cy)] + step_o2_g(h, eta, cell_m, cx, cy, nx, ny, g_ratio)
            if cand < g_score.get((nx, ny), np.inf):
                g_score[(nx, ny)] = cand
                came_from[(nx, ny)] = (cx, cy)
                heapq.heappush(open_heap, (cand + heuristic(nx, ny), nx, ny))

    if goal not in g_score:
        return None
    path = [goal]
    while path[-1] != start:
        path.append(came_from[path[-1]])
    return path[::-1]


def path_metrics(path, h, eta, slope_deg, cell_m, g_ratio=G_RATIO_MARS, risk=None):
    dist_m = o2 = ascent = 0.0
    for (cx, cy), (nx, ny) in zip(path[:-1], path[1:]):
        dist_m += float(np.hypot(nx - cx, ny - cy)) * cell_m
        o2 += step_o2_g(h, eta, cell_m, cx, cy, nx, ny, g_ratio)
        ascent += max(float(h[ny, nx]) - float(h[cy, cx]), 0.0)
    slopes = [float(slope_deg[y, x]) for x, y in path]
    out = {
        "dist_m": dist_m,
        "time_min": dist_m / EVA_WALK_SPEED_M_S / 60,
        "o2_g": o2,
        "ascent_m": ascent,
        "max_slope_deg": max(slopes),
        "n_cells_over_slope_cap": int(sum(s > MAX_WALK_SLOPE_DEG for s in slopes)),
    }
    if risk is not None:
        out["max_risk"] = float(max(risk[y, x] for x, y in path))
    return out


def compare_planners(h, rock_risk, risk, start, goal, cell_m, g_ratio, risk_weight):
    """네 경로 비교 — 최단거리 / 최단거리+경사 상한 / 기존 위험도 가중 / 산소 최소+경사 상한.
    "최단거리+경사 상한"을 넣어야 산소 이득이 경사 제약 때문인지 비용함수 때문인지 분리된다."""
    slope = slope_deg_grid(h, cell_m)
    eta = eta_from_rock(rock_risk)
    passable = slope <= MAX_WALK_SLOPE_DEG
    paths = {
        "shortest": astar(risk, start, goal, risk_weight=0.0),
        "shortest_capped": astar(risk, start, goal, risk_weight=0.0, passable=passable),
        "risk_weighted": astar(risk, start, goal, risk_weight=risk_weight),
        "o2_optimal": astar_o2(h, eta, passable, start, goal, cell_m, g_ratio),
    }
    metrics = {k: path_metrics(p, h, eta, slope, cell_m, g_ratio, risk) if p else None for k, p in paths.items()}
    return paths, metrics, slope


# ============================================================
# 3. 시각화
# ============================================================

PATH_STYLE = {
    "shortest": ("#a7aec1", "--", "shortest distance"),
    "shortest_capped": ("#a7e8a0", ":", "shortest + slope cap"),
    "risk_weighted": ("#e0ac53", "-", "risk-weighted (existing)"),
    "o2_optimal": ("#5cbcc3", "-", "O2-optimal + slope cap"),
}


def plot_comparison(h, slope, paths, metrics, cell_m, title, fname):
    fig, (ax, axb) = plt.subplots(1, 2, figsize=(12.5, 6.2), facecolor="#0b0e15",
                                  gridspec_kw={"width_ratios": [1.35, 1]})
    style_ax(ax)
    im = ax.imshow(slope, cmap="magma", vmin=0, vmax=max(MAX_WALK_SLOPE_DEG * 1.5, 1), origin="upper")
    ax.contour(slope > MAX_WALK_SLOPE_DEG, levels=[0.5], colors="#e9ebf2", linewidths=0.6)
    for k, p in paths.items():
        if not p:
            continue
        c, ls, lab = PATH_STYLE[k]
        m = metrics[k]
        ax.plot([q[0] for q in p], [q[1] for q in p], ls, color=c, lw=2.0,
                label=f"{lab}: {m['dist_m']:.0f} m, O2 {m['o2_g']:.1f} g")
    start, goal = paths["shortest"][0], paths["shortest"][-1]
    _marker(ax, start, "#a7e8a0", marker="s")
    _marker(ax, goal, "#e9ebf2", marker="X", size=110)
    ax.set_title(title, color="#e9ebf2", fontsize=10.5)
    ax.legend(facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2", fontsize=7.5, loc="lower right")
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
    cb.set_label(f"slope (deg), white line = {MAX_WALK_SLOPE_DEG:.0f} deg cap", color="#a7aec1", fontsize=8)
    cb.ax.tick_params(colors="#a7aec1", labelsize=7)

    style_ax(axb)
    keys = [k for k in paths if metrics[k]]
    labels = [PATH_STYLE[k][2] for k in keys]
    o2 = [metrics[k]["o2_g"] for k in keys]
    bars = axb.barh(labels, o2, color=[PATH_STYLE[k][0] for k in keys])
    for b, k in zip(bars, keys):
        m = metrics[k]
        axb.text(b.get_width(), b.get_y() + b.get_height() / 2,
                 f"  {m['o2_g']:.1f} g | {m['dist_m']:.0f} m | climb {m['ascent_m']:.0f} m | "
                 f"max {m['max_slope_deg']:.0f} deg",
                 va="center", color="#e9ebf2", fontsize=7.5)
    axb.set_xlim(0, max(o2) * 1.9)
    axb.invert_yaxis()
    axb.set_xlabel("O2 consumed (g)", color="#a7aec1", fontsize=8)
    axb.set_title("O2 / distance / climb per planner", color="#e9ebf2", fontsize=10.5)
    fig.tight_layout()
    fig.savefig(fname, dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"saved {fname}")


# ============================================================
# 4. 실행
# ============================================================

def run_mars_sim_patch():
    """기존 화성 시뮬레이션 패치(44m) — 기존 위험도/대피 데모와 같은 지형."""
    import exploration_slam_sim as sim
    from exploration_slam_sim import CELL_M
    from anisotropic_risk_exploration import rock_risk_grid, slope_grids
    from human_mission_risk import human_mission_risk, shielding_factor_grid
    from human_mission_navigation import RISK_WEIGHT

    sim.rng = np.random.default_rng(0)
    h, _ = sim.generate_terrain()
    gx, gy = slope_grids(h)
    slope_risk = np.clip(np.hypot(gx, gy) / 0.9, 0, 1)
    rock_r = rock_risk_grid(h)
    risk = human_mission_risk(slope_risk, rock_r, 14.0, shielding_factor_grid(h), spe_active=False)

    n = h.shape[0]
    start, goal = (15, n - 20), (n - 20, 20)
    paths, metrics, slope = compare_planners(h, rock_r, risk, start, goal, CELL_M, G_RATIO_MARS, RISK_WEIGHT)
    plot_comparison(h, slope, paths, metrics, CELL_M,
                    "Mars sim patch (44 m, 0.38 g) -- 14:00", f"{OUT_DIR}/mars_sim_patch.png")
    return {"terrain": "Mars procedural patch 44 m x 44 m, cell 0.2 m", "g_ratio": G_RATIO_MARS,
            "start": start, "goal": goal, "metrics": metrics}


def run_lola_patch():
    """달 LOLA 실측 DEM(20 m/px) 6 km 패치 — km 규모에서 산소 경로가 실제로 갈라지는지 확인.
    지형 형상만 실측 DEM을 빌리고 중력은 화성(0.38g)으로 평가한다(형상 대용). 같은 경로를
    달 중력으로 재평가한 값도 함께 남긴다."""
    from real_terrain_risk import load_moon_dem, terrain_risk, CELL_M as LOLA_CELL_M
    from human_mission_navigation import RISK_WEIGHT

    h = load_moon_dem(row0=4600, col0=5200, size=300).astype(np.float64)
    _, roughness_m, risk = terrain_risk(h, LOLA_CELL_M)
    rock_r = np.clip(roughness_m / 2.0, 0, 1)  # real_terrain_risk의 ROUGHNESS_HIGH_M 정규화와 동일

    n = h.shape[0]
    start, goal = (20, n - 20), (n - 20, 20)
    paths, metrics, slope = compare_planners(h, rock_r, risk, start, goal, LOLA_CELL_M, G_RATIO_MARS, RISK_WEIGHT)
    plot_comparison(h, slope, paths, metrics, LOLA_CELL_M,
                    "LOLA real DEM (6 km, 20 m/px), evaluated at Mars 0.38 g", f"{OUT_DIR}/lola_patch.png")

    eta = eta_from_rock(rock_r)
    moon_check = {k: path_metrics(p, h, eta, slope, LOLA_CELL_M, G_RATIO_MOON) if p else None
                  for k, p in paths.items()}
    # 왕복 비대칭: 산소 최적 경로를 그대로 되돌아올 때(오르막/내리막 뒤바뀜)
    back = paths["o2_optimal"][::-1] if paths["o2_optimal"] else None
    back_metrics = path_metrics(back, h, eta, slope, LOLA_CELL_M, G_RATIO_MARS) if back else None
    return {"terrain": "LOLA south pole 20 m/px, 300x300 (6 km), row0=4600 col0=5200",
            "g_ratio": G_RATIO_MARS, "start": start, "goal": goal, "metrics": metrics,
            "same_paths_at_moon_g": moon_check, "o2_optimal_reverse_trip": back_metrics,
            "pct_cells_over_slope_cap": float((slope > MAX_WALK_SLOPE_DEG).mean() * 100)}


def main():
    level_mars = float(metabolic_rate_w(0.0, 1.0, G_RATIO_MARS))
    level_moon = float(metabolic_rate_w(0.0, 1.0, G_RATIO_MOON))
    print(f"평지 대사율: 화성 {level_mars:.0f} W, 달 {level_moon:.0f} W "
          f"(Apollo 계획값 {APOLLO_PLAN_W:.0f} W) -> 화성 O2 {o2_g_per_s(level_mars)*3600:.0f} g/h")
    for g in [5, 10, 20, 36]:
        print(f"  경사 {g:>2}%: {metabolic_rate_w(g, 1.0, G_RATIO_MARS):.0f} W")

    mars = run_mars_sim_patch()
    lola = run_lola_patch()
    for name, r in [("Mars sim", mars), ("LOLA", lola)]:
        print(f"\n[{name}]")
        for k, m in r["metrics"].items():
            if m:
                print(f"  {k:<14} dist {m['dist_m']:7.1f} m  O2 {m['o2_g']:7.2f} g  climb {m['ascent_m']:6.1f} m  "
                      f"max slope {m['max_slope_deg']:5.1f}  over-cap cells {m['n_cells_over_slope_cap']}")
    print("  같은 경로를 달 중력으로 재평가:",
          {k: round(m["o2_g"], 1) for k, m in lola["same_paths_at_moon_g"].items() if m})
    if lola["o2_optimal_reverse_trip"]:
        print(f"  O2 경로 되돌아오기: {lola['o2_optimal_reverse_trip']['o2_g']:.2f} g")

    stats = {
        "model": {
            "equation": "Pandolf 1977, mass terms scaled by g ratio; downhill treated as level",
            "BODY_MASS_KG": BODY_MASS_KG, "SUIT_MASS_KG": SUIT_MASS_KG,
            "EVA_WALK_SPEED_M_S": EVA_WALK_SPEED_M_S, "MAX_WALK_SLOPE_DEG": MAX_WALK_SLOPE_DEG,
            "ETA_RANGE": [ETA_MIN, ETA_MAX], "O2_KJ_PER_L": O2_KJ_PER_L,
            "level_metabolic_w": {"mars": level_mars, "moon": level_moon, "apollo_plan": APOLLO_PLAN_W},
            "level_o2_g_per_h_mars": float(o2_g_per_s(level_mars) * 3600),
        },
        "mars_sim_patch": mars,
        "lola_patch": lola,
    }
    with open(f"{OUT_DIR}/metabolic_stats.json", "w") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False, default=lambda o: list(o) if isinstance(o, tuple) else str(o))
    print(f"\nsaved {OUT_DIR}/metabolic_stats.json")


if __name__ == "__main__":
    main()
