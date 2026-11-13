"""근거 기반 보정계수 k, 예비분 정의, 냉각수 잔량, 산소 누설에 따른 귀환 가능 면적 (PLAN.md 안 A)

실행 (원본 코드가 상대 경로를 쓰므로 code/ 안에서):
    cd code && ../recalc/.venv/bin/python ../recalc/k_scenarios.py

원본 code/ 는 수정하지 않고 import만 한다. 장면 구성은 heart_rate_o2.main()과 같다.
"""
from __future__ import annotations

import csv
import json
import os
import platform
import sys

# 2026-11-12: 이 스크립트는 "원본 모델(Pandolf, 8방향)" 기준으로 쓰였다. 원본 code/의 기본값이 바뀌었으므로
# 원본 모듈을 불러오기 전에 고정한다(PLAN_D 1번).
os.environ["GALE_METABOLIC_MODEL"] = "pandolf_legacy"
os.environ["GALE_GRID_NEIGHBORS"] = "8"
os.environ["GALE_EDGE_SLOPE_CAP"] = "0"   # 계획 E 7번 이전 결과 재현
sys.path.insert(0, os.getcwd())  # code/

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import scipy  # noqa: E402
from scipy.sparse.csgraph import dijkstra  # noqa: E402

from human_mission_navigation import _marker, style_ax  # noqa: E402
from mars_walkback import (  # noqa: E402
    CELL_M, LEVEL_O2_G_PER_H, O2_RESERVE_G, _wp_lonlat, build_o2_graph, hillshade, km_extent,
    load_dtm_crop, load_traverse, lonlat_to_cell, trace,
)
from metabolic_navigation import (  # noqa: E402
    EVA_WALK_SPEED_M_S, MAX_WALK_SLOPE_DEG, eta_from_rock, o2_g_per_s, slope_deg_grid,
)
from suit_cooling import FEEDWATER_FULL_G, LEVEL_MR_W, water_g_per_s, water_reserve_g  # noqa: E402

OUT_DIR = "../recalc/outputs"
GOAL_SOL = 1282

K_GRID = np.round(np.arange(0.80, 2.501, 0.05), 2)
K_EVIDENCE = {
    1.00: "Pandolf (current model)",
    1.16: "Mars PLSS design avg 350 W",
    1.33: "Apollo 14, leak removed",
    1.40: "Apollo walk plan 1440 BTU/h",
    1.60: "Apollo 14 measured (Moon, terrain+leak)",
    1.84: "EWT Mars suited, stage 1",
    2.15: "EWT Mars suited, slowest speed",
}
O2_LEFT_G = [100, 150, 200]
WATER_LEFT_G = [FEEDWATER_FULL_G, 600.0]
# 50 kcal/h (Waligora 1975, Apollo 사양상 최대 누설) -> W -> g/h
LEAK_MAX_G_PER_H = 50 * 4184 / 3600 / 20100 * 1.429 * 3600
# Apollo 15 계획 누설률 0.01/0.02/0.03 lb/h (Bellcomm B70 10028, 1970) = 4.5/9.1/13.6 g/h
LEAK_G_PER_H = [0.0, 4.5, 9.1, 13.6]
RESERVE_DEFS = ("fixed", "scaled")
RESERVE_H = 0.5
WATER_PER_O2 = float(water_g_per_s(LEVEL_MR_W) / o2_g_per_s(LEVEL_MR_W))  # Q_extra = 0이면 상수
W_RESERVE_G = water_reserve_g(0.0)

# 기준 실행에서 확인한 값 (recalc/baseline_heart_rate_o2.log, 보고서 16·17)
BASELINE_O2_ONLY = {1.0: 18.64, 1.2: 13.29, 1.4: 10.03}
BASELINE_WATER_0P6 = 7.4
ROUTE_KM_SOL1282 = 7.26


def build_scene() -> dict:
    """heart_rate_o2.main() 241~259행과 같은 순서로 칸별 귀환 산소와 귀환 트리를 만든다."""
    h, valid, rough_r, _ = load_dtm_crop()
    slope = slope_deg_grid(h, CELL_M)
    passable = valid & (slope <= MAX_WALK_SLOPE_DEG)
    eta = eta_from_rock(rough_r)
    wps, traverse_xy = load_traverse(h.shape)
    bx, by = (int(round(v)) for v in lonlat_to_cell(wps[0]["lon"], wps[0]["lat"]))
    base_idx = by * h.shape[1] + bx
    graph = build_o2_graph(h, eta, passable)
    ret_o2, ret_pred = dijkstra(graph.T.tocsr(), directed=True, indices=base_idx, return_predecessors=True)
    gx, gy = (int(round(v)) for v in lonlat_to_cell(*_wp_lonlat(wps, GOAL_SOL)))
    return {
        "h": h, "valid": valid, "traverse_xy": traverse_xy, "base": (bx, by), "shape": h.shape,
        "ret_o2_flat": ret_o2, "ret_pred": ret_pred, "goal_idx": gy * h.shape[1] + gx,
    }


def tree_distance_m(cost: np.ndarray, pred: np.ndarray, cols: int) -> np.ndarray:
    """귀환 트리를 비용 순으로 따라가며 거점까지의 경로 길이(m)를 누적한다.
    간선 비용이 양수라 부모 칸은 항상 먼저 처리된다(spe_walkback.return_tree_totals와 같은 방식)."""
    n = cost.size
    dist = np.full(n, np.nan)
    order = np.argsort(cost)
    order = order[np.isfinite(cost[order])]
    dist[order[0]] = 0.0
    v = order[1:]
    p = pred[v]
    step = np.hypot(v % cols - p % cols, v // cols - p // cols) * CELL_M
    step_of = np.zeros(n)
    step_of[v] = step
    for node in v:
        dist[node] = dist[pred[node]] + step_of[node]
    return dist


def returnable(o2: np.ndarray, time_h: np.ndarray, k: float, o2_left: float, water_left: float,
               leak: float, reserve_def: str) -> tuple[np.ndarray, np.ndarray]:
    """칸별 (산소 OK, 냉각수 OK). 정의 fixed = 예비분 g 고정(보고서 16), scaled = 실제 소비율로 30분."""
    tank_o2 = k * o2 + leak * time_h
    water = k * o2 * WATER_PER_O2
    if reserve_def == "fixed":
        o2_res, w_res = O2_RESERVE_G, W_RESERVE_G
    else:
        o2_res = RESERVE_H * (k * LEVEL_O2_G_PER_H + leak)
        w_res = k * W_RESERVE_G
    with np.errstate(invalid="ignore"):
        return tank_o2 <= o2_left - o2_res, water <= water_left - w_res


def compute_rows(o2: np.ndarray, time_h: np.ndarray) -> list[dict]:
    cell_km2 = (CELL_M / 1000) ** 2
    ks = sorted(set(K_GRID.tolist()) | set(K_EVIDENCE))
    rows = []
    for o2_left in O2_LEFT_G:
        for water_left in WATER_LEFT_G:
            for leak in LEAK_G_PER_H:
                for rdef in RESERVE_DEFS:
                    for k in ks:
                        ok_o2, ok_w = returnable(o2, time_h, k, o2_left, water_left, leak, rdef)
                        rows.append({
                            "o2_left_g": o2_left, "water_left_g": water_left, "leak_g_per_h": leak,
                            "reserve_def": rdef, "k": round(k, 2), "evidence": K_EVIDENCE.get(round(k, 2), ""),
                            "area_km2": round(float((ok_o2 & ok_w).sum() * cell_km2), 3),
                            "area_o2_only_km2": round(float(ok_o2.sum() * cell_km2), 3),
                            "binding": "water" if (ok_o2 & ~ok_w).any() else "o2",
                        })
    return rows


def pick(rows: list[dict], **kw) -> list[dict]:
    return [r for r in rows if all(r[a] == b for a, b in kw.items())]


def verify(rows: list[dict], scene: dict, dist_m: np.ndarray) -> dict:
    checks = {}
    main = dict(o2_left_g=150, water_left_g=FEEDWATER_FULL_G, leak_g_per_h=0.0, reserve_def="fixed")
    for k, want in BASELINE_O2_ONLY.items():
        got = pick(rows, k=k, **main)[0]["area_km2"]
        assert abs(got - want) < 0.006, (k, got, want)
        checks[f"o2_only_k{k}"] = {"got": got, "want": want}
    for combo in {(r["o2_left_g"], r["water_left_g"], r["leak_g_per_h"], r["reserve_def"]) for r in rows}:
        sub = sorted(pick(rows, o2_left_g=combo[0], water_left_g=combo[1], leak_g_per_h=combo[2],
                          reserve_def=combo[3]), key=lambda r: r["k"])
        areas = [r["area_km2"] for r in sub]
        assert all(a >= b for a, b in zip(areas, areas[1:])), combo
    checks["monotonic_in_k"] = True
    # 누설 0이면 시간 항이 사라져 정의 fixed의 산소 판정은 보고서 16 방식과 같다 (위 assert가 이를 확인)
    w06 = pick(rows, k=1.0, o2_left_g=150, water_left_g=600.0, leak_g_per_h=0.0, reserve_def="fixed")[0]
    checks["water_0p6_k1"] = {"got": w06["area_km2"], "report17": BASELINE_WATER_0P6,
                              "note": "보고서 17은 선량·냉각수 결합 비용 경로라 근소한 차이 허용(±0.15)"}
    assert abs(w06["area_km2"] - BASELINE_WATER_0P6) <= 0.15, w06
    route_km = float(dist_m[scene["goal_idx"]] / 1000)
    checks["route_km_sol1282"] = {"got": round(route_km, 2), "report15": ROUTE_KM_SOL1282}
    assert abs(route_km - ROUTE_KM_SOL1282) < 0.02, route_km
    r184 = pick(rows, k=1.84, **main)[0]["area_km2"]
    radius_km = (150 - O2_RESERVE_G) / (1.84 * LEVEL_O2_G_PER_H) * EVA_WALK_SPEED_M_S * 3.6
    checks["flat_circle_k1.84"] = {"area_km2": r184, "circle_km2": round(np.pi * radius_km ** 2, 2)}
    assert r184 < np.pi * radius_km ** 2
    return checks


def plot_area_vs_k(rows: list[dict], path: str) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), facecolor="#0b0f17")
    styles = {(FEEDWATER_FULL_G, 0.0): ("#5cbcc3", "-", "water full, no leak"),
              (FEEDWATER_FULL_G, LEAK_G_PER_H[-1]): ("#e3a857", "-", f"water full, leak {LEAK_G_PER_H[-1]} g/h"),
              (600.0, 0.0): ("#9b8cff", "--", "water 0.6 kg, no leak (same as leak: water binds)"),
              (600.0, LEAK_G_PER_H[-1]): ("#ff6b8a", "--", f"water 0.6 kg, leak {LEAK_G_PER_H[-1]} g/h")}
    for ax, rdef, title in zip(axes, RESERVE_DEFS, ("reserve fixed 38.6 g (main)", "reserve = 30 min at k x rate")):
        style_ax(ax)
        for (wl, lk), (c, ls, lab) in styles.items():
            sub = sorted(pick(rows, o2_left_g=150, water_left_g=wl, leak_g_per_h=lk, reserve_def=rdef),
                         key=lambda r: r["k"])
            ax.plot([r["k"] for r in sub], [r["area_km2"] for r in sub], ls, color=c, lw=1.8, label=lab)
        for k, lab in K_EVIDENCE.items():
            ax.axvline(k, color="#6b7280", lw=0.8, ls=":")
            ax.text(k, ax.get_ylim()[1] * 0.98, lab, rotation=90, va="top", ha="right",
                    color="#a7aec1", fontsize=6.5)
        ax.set_xlabel("k (actual / model metabolic rate)", color="#a7aec1", fontsize=8)
        ax.set_ylabel("walk-back area (km2), 150 g O2 left", color="#a7aec1", fontsize=8)
        ax.set_title(title, color="#e6e9ef", fontsize=9)
        ax.legend(fontsize=7, facecolor="#141a26", labelcolor="#e6e9ef", edgecolor="#2a3142")
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)


def plot_boundary_map(scene: dict, o2: np.ndarray, time_h: np.ndarray, path: str) -> None:
    h, shape = scene["h"], scene["shape"]
    fig, ax = plt.subplots(figsize=(7, 8), facecolor="#0b0f17")
    style_ax(ax)
    ext = km_extent(shape)
    ax.imshow(np.where(scene["valid"], hillshade(h), np.nan), cmap="gray", extent=ext)
    xs = np.arange(shape[1]) * CELL_M / 1000
    ys = np.arange(shape[0]) * CELL_M / 1000
    colors = {1.00: "#5cbcc3", 1.60: "#e3a857", 1.84: "#ff6b8a", 2.15: "#c084fc"}
    handles = []
    cell_km2 = (CELL_M / 1000) ** 2
    for k, c in colors.items():
        ok_o2, ok_w = returnable(o2, time_h, k, 150, FEEDWATER_FULL_G, 0.0, "fixed")
        ok = (ok_o2 & ok_w).astype(float)
        ax.contour(xs, ys, ok, levels=[0.5], colors=c, linewidths=1.6)
        handles.append(plt.Line2D([], [], color=c, lw=1.8, label=f"k = {k:.2f}: {ok.sum() * cell_km2:.1f} km2"))
    for tx, ty in scene["traverse_xy"]:
        ax.plot(tx * CELL_M / 1000, ty * CELL_M / 1000, color="white", lw=0.5, alpha=0.6)
    bx, by = scene["base"]
    _marker(ax, (bx * CELL_M / 1000, by * CELL_M / 1000), "#ffd166", marker="*", size=160)
    ax.legend(handles=handles, fontsize=7, loc="lower left", facecolor="#141a26", labelcolor="#e6e9ef",
              edgecolor="#2a3142")
    ax.set_title("Walk-back boundary, 150 g O2, water full, no leak, reserve fixed", color="#e6e9ef", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    scene = build_scene()
    shape = scene["shape"]
    cost = scene["ret_o2_flat"]
    dist_m = tree_distance_m(cost, scene["ret_pred"], shape[1])
    o2 = cost.reshape(shape)
    time_h = (dist_m / EVA_WALK_SPEED_M_S / 3600).reshape(shape)

    rows = compute_rows(o2, time_h)
    checks = verify(rows, scene, dist_m)

    with open(f"{OUT_DIR}/k_area_table.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    plot_area_vs_k(rows, f"{OUT_DIR}/k_area_vs_k.png")
    plot_boundary_map(scene, o2, time_h, f"{OUT_DIR}/k_boundary_map.png")

    evidence = [r for r in rows if r["evidence"]]
    summary = {
        "assumptions": {
            "o2_reserve_fixed_g": round(O2_RESERVE_G, 2), "water_reserve_fixed_g": round(W_RESERVE_G, 1),
            "water_per_o2": round(WATER_PER_O2, 3), "leak_max_g_per_h": round(LEAK_MAX_G_PER_H, 2),
            "speed_m_s": EVA_WALK_SPEED_M_S, "level_o2_g_per_h": round(LEVEL_O2_G_PER_H, 2),
            "route": "누설 없는 산소 최적 귀환 트리를 모든 시나리오에 공통 사용",
        },
        "checks": checks,
        "evidence_rows": evidence,
        "env": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
                "matplotlib": matplotlib.__version__},
    }
    with open(f"{OUT_DIR}/k_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("검증:", json.dumps(checks, ensure_ascii=False))
    print("\n산소 150 g, 근거 지점별 면적 (km2)")
    print(f"{'k':>5} {'근거':<40} {'만충·누설0·고정':>14} {'만충·누설0·k배':>14} {'만충·누설·고정':>14} "
          f"{'0.6kg·누설0·고정':>16} {'0.6kg·누설·k배':>14}")
    for k, lab in K_EVIDENCE.items():
        def a(wl, lk, rd):
            return pick(rows, k=k, o2_left_g=150, water_left_g=wl, leak_g_per_h=lk, reserve_def=rd)[0]["area_km2"]
        lk = LEAK_G_PER_H[-1]
        print(f"{k:5.2f} {lab:<40} {a(FEEDWATER_FULL_G, 0.0, 'fixed'):14.2f} {a(FEEDWATER_FULL_G, 0.0, 'scaled'):14.2f} "
              f"{a(FEEDWATER_FULL_G, lk, 'fixed'):14.2f} {a(600.0, 0.0, 'fixed'):16.2f} {a(600.0, lk, 'scaled'):14.2f}")
    print(f"\nsaved {OUT_DIR}/k_area_table.csv, k_area_vs_k.png, k_boundary_map.png, k_summary.json")


if __name__ == "__main__":
    main()
