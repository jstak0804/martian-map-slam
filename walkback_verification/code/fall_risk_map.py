"""
넘어짐·장애물 위험지도 — 1 m DTM으로 "10 m 경로 계획이 놓치는 발밑 위험"을 찾는다

귀환 반경·산소 경로(mars_walkback.py)는 10 m 칸으로 계산한다. 10 m 평균 경사가 완만해도 그 안에
1~3 m 크기의 턱·급사면이 있으면 걷다가 넘어질 수 있다. 원래 1 m DTM으로 칸마다
"발 디딜 곳 중 위험한 비율"을 세어 위험 등급을 매기고, 경로와 귀환 반경에 반영한다.

  화소(1 m) 위험 = [3 m 창 안 높이차 >= STEP_M]  또는  [1 m 경사 >= STEEP_1M_DEG]
  칸(10 m) 위험 비율 = 위험 화소 수 / 유효 화소 수
  등급: 높음(통행 금지) >= HIGH_FRAC, 중간 >= MED_FRAC, 나머지 낮음

근거:
  - Apollo 15·16 시간·동작 분석(NASA)에 넘어짐/넘어질 뻔한 사례 분석이 있다. 원인은 작은 웅덩이에
    발이 빠짐, 돌 위에서 미끄러짐, 물건을 줍다 균형을 잃음, 헐거운 표토. 이 지도는 그중
    "지형 단차·급사면"만 다룬다(헐거운 토양·작업 중 낙상은 지형 데이터로 볼 수 없다).
  - 노인 낙상 연구: 2~5 cm에서 걸림 확률이 달라지고 15.2 cm 장애물은 넘기 어렵다(소규모 연구).
  - 우주복(xEMU) 계단 높이 시험: 1/6 g에서 7 cm씩 올려 통제된 스텝업이 안 될 때까지 측정
    (NASA ICES 2025-294). 최종 높이는 원문 확인 필요.
  - HiRISE DTM 수직 정밀도는 수십 cm(1 m 격자에서 약 0.2~0.25 m) — 그래서 이 지도는 걸림(2~15 cm)
    규모를 볼 수 없고, 0.5 m 이상의 확실한 턱만 잡는다. 작은 돌은 헬멧/로버 카메라의 몫이다.

설계 가정(측정값 아님):
  - STEP_M = 0.5 m: DTM 정밀도의 약 2배 — 노이즈와 구분되는 최소 단차. 노인 기준 15 cm의 3배라
    우주복을 입고는 확실히 넘기 어려운 장애물로 본다.
  - STEEP_1M_DEG = 20°: 10 m 칸 보행 상한(MAX_WALK_SLOPE_DEG)과 같은 값을 1 m 규모에 적용.
  - HIGH_FRAC = 0.25, MED_FRAC = 0.05: 칸 면적의 1/4 이상이 위험 화소면 발 디딜 길이 없다고 보고 금지.
  - MED_PENALTY = 1.0: 중간 칸을 지날 때 산소 비용을 2배로 쳐서 피하게 하는 경로 가중(위험 회피용 가중치).
"""
from __future__ import annotations

import json
import os

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from scipy.ndimage import binary_erosion, maximum_filter, minimum_filter
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from metabolic_navigation import eta_from_rock, slope_deg_grid, MAX_WALK_SLOPE_DEG
from human_mission_navigation import style_ax, _marker
from mars_walkback import (
    load_dtm_crop, load_traverse, lonlat_to_cell, build_o2_graph, trace, hillshade, km_extent, _wp_lonlat,
    CELL_M, BLOCK, DTM_MAP_SCALE_M, O2_RESERVE_G,
)

OUT_DIR = "../outputs/fall_risk"
os.makedirs(OUT_DIR, exist_ok=True)

STEP_M = 0.5
STEEP_1M_DEG = 20.0
HIGH_FRAC = 0.25
MED_FRAC = 0.05
MED_PENALTY = 1.0
REF_REMAINING_O2_G = 150
GOAL_SOL = 1282
C_LOW, C_MED, C_HIGH = "#5cbcc3", "#f2d430", "#e05a4f"


def hazard_fraction(h1):
    """1 m DTM -> 10 m 칸별 (위험 화소 비율, 턱 비율, 급사면 비율, 1 m 경사 p90)."""
    v1 = np.isfinite(h1)
    core = binary_erosion(v1, iterations=2)        # NoData 경계의 가짜 단차 제거
    f = np.where(v1, h1, 0).astype(np.float32)
    gy, gx = np.gradient(f, DTM_MAP_SCALE_M)
    slope1 = np.degrees(np.arctan(np.hypot(gx, gy)))
    relief3 = maximum_filter(f, 3) - minimum_filter(f, 3)
    step = (relief3 >= STEP_M) & core
    steep = (slope1 >= STEEP_1M_DEG) & core
    rows, cols = h1.shape[0] // BLOCK, h1.shape[1] // BLOCK

    def blk(a):
        return a.reshape(rows, BLOCK, cols, BLOCK).sum(axis=(1, 3)).astype(np.float32)

    n = np.maximum(blk(core), 1)
    s_masked = np.where(core, slope1, np.nan).reshape(rows, BLOCK, cols, BLOCK).transpose(0, 2, 1, 3).reshape(rows, cols, -1)
    p90 = np.nanpercentile(s_masked, 90, axis=2)
    return blk(step | steep) / n, blk(step) / n, blk(steep) / n, p90, blk(core) > BLOCK * BLOCK * 0.5


def penalize(graph, shape, med):
    """도착 칸이 중간 위험이면 간선 비용 x (1 + MED_PENALTY)."""
    coo = graph.tocoo()
    w = coo.data * np.where(med.ravel()[coo.col], 1 + MED_PENALTY, 1.0)
    return csr_matrix((w, (coo.row, coo.col)), shape=graph.shape)


def route_metrics(graph_o2, path, cls, h, slope10):
    idx = [y * h.shape[1] + x for x, y in path]
    seg = [float(np.hypot(b[0] - a[0], b[1] - a[1])) * CELL_M for a, b in zip(path[:-1], path[1:])]
    c = [cls[y, x] for x, y in path[1:]]
    return {"dist_km": sum(seg) / 1000,
            "o2_g": float(sum(graph_o2[a, b] for a, b in zip(idx[:-1], idx[1:]))),
            "med_m": float(sum(s for s, k in zip(seg, c) if k == 1)),
            "high_m": float(sum(s for s, k in zip(seg, c) if k == 2)),
            "max_slope10_deg": float(max(slope10[y, x] for x, y in path))}


def plot_map(h, valid, cls, base, traverse_xy, routes, stats, path):
    fig, axes = plt.subplots(1, 2, figsize=(13.6, 8.6), facecolor="#0b0e15")
    ext = km_extent(h.shape)
    k = CELL_M / 1000
    shade = np.where(valid, hillshade(h), np.nan)

    ax = axes[0]
    style_ax(ax)
    ax.imshow(shade, cmap="gray", extent=ext, vmin=0, vmax=1)
    ax.imshow(np.where(valid & (cls == 1), 1.0, np.nan), cmap=ListedColormap([C_MED]), extent=ext, alpha=0.75)
    ax.imshow(np.where(valid & (cls == 2), 1.0, np.nan), cmap=ListedColormap([C_HIGH]), extent=ext, alpha=0.85)
    for x, y in traverse_xy:
        ax.plot(x * k, y * k, color="#e9ebf2", lw=0.5, alpha=0.6)
    _marker(ax, (base[0] * k, base[1] * k), "#a7e8a0", marker="*", size=200)
    ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
    handles = [plt.Rectangle((0, 0), 1, 1, color=C_MED, label=f"medium: {MED_FRAC:.0%}+ of 1 m footing hazardous ({stats['med_km2']:.1f} km2)"),
               plt.Rectangle((0, 0), 1, 1, color=C_HIGH, label=f"high (no walk): {HIGH_FRAC:.0%}+ ({stats['high_km2']:.1f} km2)"),
               plt.Line2D([], [], color="#e9ebf2", lw=0.8, label="Curiosity traverse")]
    ax.legend(handles=handles, facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2", fontsize=7.5, loc="lower left")
    ax.set_title(f"Fall / obstacle risk from the 1 m DTM\nhazard pixel = step >= {STEP_M} m within 3 m, or 1 m slope >= {STEEP_1M_DEG:.0f} deg; "
                 f"{stats['hidden_high_km2']:.1f} km2 of 'high' passes the 10 m slope check", color="#e9ebf2", fontsize=8.5)

    ax = axes[1]
    style_ax(ax)
    ax.imshow(shade, cmap="gray", extent=ext, vmin=0, vmax=1)
    ax.imshow(np.where(valid & (cls == 2), 1.0, np.nan), cmap=ListedColormap([C_HIGH]), extent=ext, alpha=0.55)
    ax.imshow(np.where(valid & (cls == 1), 1.0, np.nan), cmap=ListedColormap([C_MED]), extent=ext, alpha=0.35)
    for label, (p, color, ls) in routes.items():
        ax.plot([q[0] * k for q in p], [q[1] * k for q in p], ls, color=color, lw=2.0, label=label)
    first = next(iter(routes.values()))[0]
    _marker(ax, (base[0] * k, base[1] * k), "#a7e8a0", marker="*", size=200)
    _marker(ax, (first[-1][0] * k, first[-1][1] * k), "#e9ebf2", marker="X", size=100)
    ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
    ax.legend(facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2", fontsize=7.5, loc="lower left")
    ax.set_title(f"Routes to sol {GOAL_SOL} site: O2-only vs fall-aware", color="#e9ebf2", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"saved {path}")


def plot_walkback(h, valid, cls, base, ret_plain, ret_safe, budget, areas, path):
    fig, ax = plt.subplots(figsize=(7.8, 9.0), facecolor="#0b0e15")
    style_ax(ax)
    ext = km_extent(h.shape)
    k = CELL_M / 1000
    ax.imshow(np.where(valid, hillshade(h), np.nan), cmap="gray", extent=ext, vmin=0, vmax=1)
    ax.imshow(np.where(valid & (cls == 2), 1.0, np.nan), cmap=ListedColormap([C_HIGH]), extent=ext, alpha=0.6)
    lost = (ret_plain <= budget) & ~(ret_safe <= budget)
    ax.imshow(np.where(lost, 1.0, np.nan), cmap=ListedColormap(["#d65bd0"]), extent=ext, alpha=0.8)
    xs, ys = np.arange(h.shape[1]) * k, np.arange(h.shape[0]) * k
    ax.contour(xs, ys, np.where(np.isfinite(ret_plain), ret_plain, np.nan), levels=[budget], colors="#a7aec1", linewidths=1.2, linestyles="--")
    ax.contour(xs, ys, np.where(np.isfinite(ret_safe), ret_safe, np.nan), levels=[budget], colors=C_LOW, linewidths=1.8)
    _marker(ax, (base[0] * k, base[1] * k), "#a7e8a0", marker="*", size=200)
    ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
    handles = [plt.Line2D([], [], color="#a7aec1", ls="--", label=f"O2 only: {areas['plain_km2']:.1f} km2"),
               plt.Line2D([], [], color=C_LOW, lw=1.8, label=f"O2 + avoid high fall risk: {areas['safe_km2']:.1f} km2"),
               plt.Rectangle((0, 0), 1, 1, color="#d65bd0", label=f"no longer returnable ({areas['lost_km2']:.1f} km2)"),
               plt.Rectangle((0, 0), 1, 1, color=C_HIGH, label="high fall risk (no walk)")]
    ax.legend(handles=handles, facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2", fontsize=7.5, loc="lower left")
    ax.set_title(f"Walk-back area ({REF_REMAINING_O2_G} g O2 left) when high-fall-risk cells are closed", color="#e9ebf2", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=125, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"saved {path}")


def main():
    h, valid, rough_r, h1 = load_dtm_crop()
    slope10 = slope_deg_grid(h, CELL_M)
    passable = valid & (slope10 <= MAX_WALK_SLOPE_DEG)
    eta = eta_from_rock(rough_r)
    frac, step_frac, steep_frac, p90, enough = hazard_fraction(h1)
    del h1
    ok = valid & enough
    cls = np.where(frac >= HIGH_FRAC, 2, np.where(frac >= MED_FRAC, 1, 0))
    cls = np.where(ok, cls, 0)
    cell_km2 = (CELL_M / 1000) ** 2
    hidden = ok & (cls == 2) & passable
    stats = {"valid_km2": float(ok.sum() * cell_km2),
             "low_km2": float((ok & (cls == 0)).sum() * cell_km2),
             "med_km2": float((ok & (cls == 1)).sum() * cell_km2),
             "high_km2": float((ok & (cls == 2)).sum() * cell_km2),
             "hidden_high_km2": float(hidden.sum() * cell_km2),
             "hidden_high_pct_of_high": float(hidden.sum() / max((ok & (cls == 2)).sum(), 1) * 100),
             "step_pixel_pct": float(np.average(step_frac[ok]) * 100),
             "steep_pixel_pct": float(np.average(steep_frac[ok]) * 100),
             "slope1m_p90_median_deg": float(np.nanmedian(p90[ok]))}
    print(f"지도 {stats['valid_km2']:.1f} km2: 낮음 {stats['low_km2']:.1f} / 중간 {stats['med_km2']:.1f} / 높음 {stats['high_km2']:.1f} km2")
    print(f"  위험 화소: 턱(>= {STEP_M} m) {stats['step_pixel_pct']:.2f}%, 1 m 급사면(>= {STEEP_1M_DEG:.0f}°) {stats['steep_pixel_pct']:.2f}%")
    print(f"  '높음' 중 10 m 경사 검사는 통과하는 칸 {stats['hidden_high_km2']:.2f} km2 ({stats['hidden_high_pct_of_high']:.0f}%) "
          f"— 10 m 계획만으로는 못 보는 위험")

    wps, traverse_xy = load_traverse(h.shape)
    bx, by = (int(round(v)) for v in lonlat_to_cell(wps[0]["lon"], wps[0]["lat"]))
    base = (bx, by)
    base_idx = by * h.shape[1] + bx
    gx, gy = (int(round(v)) for v in lonlat_to_cell(*_wp_lonlat(wps, GOAL_SOL)))
    goal = gy * h.shape[1] + gx

    g_plain = build_o2_graph(h, eta, passable)
    safe_pass = passable & ~(cls == 2)
    safe_pass[by, bx] = True
    g_safe = build_o2_graph(h, eta, safe_pass)
    g_pen = penalize(g_safe, h.shape, cls == 1)

    routes, rstats = {}, {}
    for key, g, color, ls in [("o2_only", g_plain, "#f5f0ff", "--"), ("avoid_high", g_safe, C_LOW, "-"),
                              ("avoid_high_and_medium", g_pen, "#b48ef0", "-")]:
        _, pred = dijkstra(g, directed=True, indices=base_idx, return_predecessors=True)
        p = trace(pred, goal, h.shape)
        m = route_metrics(g_plain, p, cls, h, slope10)
        rstats[key] = m
        routes[f"{key}: O2 {m['o2_g']:.0f} g, {m['dist_km']:.2f} km, medium {m['med_m']:.0f} m, high {m['high_m']:.0f} m"] = (p, color, ls)
        print(f"  [{key}] {json.dumps({a: round(b, 2) for a, b in m.items()})}")

    budget = REF_REMAINING_O2_G - O2_RESERVE_G
    ret_plain = dijkstra(g_plain.T.tocsr(), directed=True, indices=base_idx).reshape(h.shape)
    ret_safe = dijkstra(g_safe.T.tocsr(), directed=True, indices=base_idx).reshape(h.shape)
    areas = {"plain_km2": float((ret_plain <= budget).sum() * cell_km2),
             "safe_km2": float((ret_safe <= budget).sum() * cell_km2)}
    areas["lost_km2"] = float(((ret_plain <= budget) & ~(ret_safe <= budget)).sum() * cell_km2)
    print(f"귀환 가능({REF_REMAINING_O2_G} g): 산소만 {areas['plain_km2']:.2f} km2 -> 높음 칸 금지 {areas['safe_km2']:.2f} km2 "
          f"(잃은 면적 {areas['lost_km2']:.2f} km2, 그중 높음 칸 자체가 아닌 곳 "
          f"{(((ret_plain <= budget) & ~(ret_safe <= budget)) & (cls != 2)).sum() * cell_km2:.2f} km2)")

    plot_map(h, valid, cls, base, traverse_xy, routes, stats, f"{OUT_DIR}/fall_risk_map.png")
    plot_walkback(h, valid, cls, base, ret_plain, ret_safe, budget, areas, f"{OUT_DIR}/fall_risk_walkback.png")
    np.savez_compressed(f"{OUT_DIR}/fall_risk_grid.npz", cls=cls.astype(np.int8), frac=frac.astype(np.float32),
                        valid=ok, cell_m=CELL_M)

    out = {"assumptions": {"STEP_M": STEP_M, "STEEP_1M_DEG": STEEP_1M_DEG, "HIGH_FRAC": HIGH_FRAC,
                           "MED_FRAC": MED_FRAC, "MED_PENALTY": MED_PENALTY,
                           "dtm_vertical_precision": "tens of cm (~0.2-0.25 m at 1 m post spacing)"},
           "classes": stats, "routes": rstats, "walkback": areas}
    with open(f"{OUT_DIR}/fall_risk_stats.json", "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"saved {OUT_DIR}/fall_risk_stats.json")


if __name__ == "__main__":
    main()
