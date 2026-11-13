"""계획 E 5·6·10번 검증 (코드 변경 없음)

실행: cd code && ../recalc/.venv/bin/python ../recalc/e_quick_checks.py
  5. A* 최적성: metabolic_navigation.astar_o2 경로 비용 vs 같은 이웃·비용의 다익스트라 최적값
  6. 가시선: 고도 0 합성 지형에서 comm_los.viewshed 최대 가시거리 vs 이론값
  10. Curiosity 웨이포인트 고도 대 DTM 고도: 원본 수치 재현 + 수평 이동 탐색
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.getcwd())
import numpy as np  # noqa: E402
from scipy.sparse import csr_matrix  # noqa: E402
from scipy.sparse.csgraph import dijkstra  # noqa: E402

import metabolic_model as mm  # noqa: E402
from human_mission_navigation import NEIGHBORS  # noqa: E402
from metabolic_navigation import astar_o2, path_metrics, step_o2_g  # noqa: E402
from mars_walkback import (  # noqa: E402
    BLOCK, CELL_M, MAX_WALK_SLOPE_DEG, MARS_RADIUS_M, _wp_lonlat, eta_from_rock, load_dtm_crop, load_traverse,
    lonlat_to_cell, slope_deg_grid,
)
from comm_los import BASE_ANT_M, SUIT_ANT_M, viewshed  # noqa: E402

OUT = os.path.abspath(os.path.join(os.getcwd(), "..", "recalc", "outputs_e"))
os.makedirs(OUT, exist_ok=True)


def _dijkstra_opt(hh, ee, pp, s, g):
    """astar_o2와 같은 이웃(NEIGHBORS)·같은 비용(step_o2_g와 같은 식)의 다익스트라. 간선 비용은 벡터로 계산."""
    r, c = hh.shape
    src, dst, w = [], [], []
    yy, xx = np.mgrid[0:r, 0:c]
    for dx, dy in NEIGHBORS:
        nx, ny = xx + dx, yy + dy
        ok = (nx >= 0) & (nx < c) & (ny >= 0) & (ny < r)
        ok[ok] &= pp[yy[ok], xx[ok]] & pp[ny[ok], nx[ok]]
        y0, x0, y1, x1 = yy[ok], xx[ok], ny[ok], nx[ok]
        dist = np.hypot(dx, dy) * CELL_M
        grade = (hh[y1, x1] - hh[y0, x0]) / dist * 100
        mr, v = mm.edge_rate(grade, 0.5 * (ee[y0, x0] + ee[y1, x1]), mm.G_RATIO_MARS)
        src.append(y0 * c + x0); dst.append(y1 * c + x1); w.append(mm.o2_g_per_s(mr) * dist / v)
    gph = csr_matrix((np.concatenate(w), (np.concatenate(src), np.concatenate(dst))), shape=(r * c, r * c))
    return float(dijkstra(gph, directed=True, indices=s[1] * c + s[0])[g[1] * c + g[0]])


def check_astar(h, eta, passable, base, n_pairs=6, half=30, seed=0):
    """거점 주변 창(±half 칸) 안의 무작위 목표 n_pairs개에 대해 A* 경로 비용 = 다익스트라 최적값인지 본다."""
    rng = np.random.default_rng(seed)
    x0, y0 = base[0] - half, base[1] - half
    hh = h[y0:y0 + 2 * half + 1, x0:x0 + 2 * half + 1]
    ee = eta[y0:y0 + 2 * half + 1, x0:x0 + 2 * half + 1]
    pp = passable[y0:y0 + 2 * half + 1, x0:x0 + 2 * half + 1]
    s = (half, half)
    cand = np.argwhere(pp)
    out = []
    for k in rng.choice(len(cand), n_pairs * 3, replace=False):
        g = (int(cand[k][1]), int(cand[k][0]))
        if np.hypot(g[0] - s[0], g[1] - s[1]) < half * 0.5:
            continue
        path = astar_o2(hh, ee, pp, s, g, CELL_M)
        opt = _dijkstra_opt(hh, ee, pp, s, g)
        if path is None:
            out.append({"goal": g, "astar": None, "dijkstra_opt_g": opt}); continue
        a = float(sum(step_o2_g(hh, ee, CELL_M, *p, *q, mm.G_RATIO_MARS) for p, q in zip(path[:-1], path[1:])))
        out.append({"goal": g, "astar_cost_g": round(a, 5), "dijkstra_opt_g": round(opt, 5), "rel_diff": abs(a - opt) / opt})
        if len(out) >= n_pairs:
            break
    worst = max(o.get("rel_diff", 0) for o in out)
    # 휴리스틱 하한이 실제 지도 간선 m당 최소 비용 이하인지(창 안 전체 간선)
    return {"neighbors_used_by_astar": len(NEIGHBORS), "window_cells": int(2 * half + 1), "pairs": out,
            "max_rel_diff": worst, "pass": worst < 1e-9, "heuristic_floor_g_per_m": mm_floor()}


def mm_floor():
    from metabolic_navigation import o2_per_m_floor
    gr = np.linspace(-100, 100, 4001)
    mr, v = mm.edge_rate(gr, np.ones_like(gr), mm.G_RATIO_MARS)
    return {"floor_used(-50..50%)": o2_per_m_floor(), "min_over_-100..100%": float(np.min(mm.o2_g_per_s(mr) / v))}


def check_viewshed():
    n = 1001
    cell = 10.0
    h = np.zeros((3, n)); valid = np.ones_like(h, bool)
    vis, known = viewshed(h, valid, (0, 1), BASE_ANT_M, SUIT_ANT_M)
    xs = np.nonzero(vis[1])[0]
    vmax_km = float(xs.max() * cell / 1000)
    theory = (np.sqrt(2 * MARS_RADIUS_M * BASE_ANT_M) + np.sqrt(2 * MARS_RADIUS_M * SUIT_ANT_M)) / 1000
    return {"note": "viewshed는 셀 크기를 mars_walkback.CELL_M(10.1 m)로 가정하므로 합성 격자도 그 셀 크기로 해석",
            "max_visible_cells": int(xs.max()), "max_visible_km_at_CELL_M": round(float(xs.max() * CELL_M / 1000), 3),
            "theory_km": round(float(theory), 3)}


def check_georef(wps, h1):
    def errs_for(sx, sy):
        e = []
        for p in wps:
            x, y = lonlat_to_cell(p["lon"], p["lat"])
            line, samp = int(round(y * BLOCK)) + sy, int(round(x * BLOCK)) + sx
            if 0 <= line < h1.shape[0] and 0 <= samp < h1.shape[1] and np.isfinite(h1[line, samp]):
                e.append(float(h1[line, samp]) - p["elev_geoid"])
        return np.array(e)
    e0 = errs_for(0, 0)

    def search(cx, cy, half, step):
        best = None
        for sy in range(cy - half, cy + half + 1, step):
            for sx in range(cx - half, cx + half + 1, step):
                e = errs_for(sx, sy)
                if len(e) > 300 and (best is None or e.std() < best[2]):
                    best = (sx, sy, float(e.std()), float(np.median(e)), len(e))
        return best
    coarse = search(0, 0, 200, 10)            # 1 m 픽셀 기준 ±200 px
    best = search(coarse[0], coarse[1], 10, 1)  # 그 주변 ±10 px 정밀 탐색
    # 최솟값이 뚜렷한지: 최적점에서 ±50 px 떨어진 네 점의 표준편차
    ring = {f"{dx:+d},{dy:+d}": round(float(errs_for(best[0] + dx, best[1] + dy).std()), 3)
            for dx, dy in [(50, 0), (-50, 0), (0, 50), (0, -50)]}
    return {"n": int(len(e0)), "median_m": round(float(np.median(e0)), 3), "std_m": round(float(e0.std()), 3),
            "abs_p90_m": round(float(np.percentile(np.abs(e0), 90)), 3),
            "best_shift_px_1m": {"dx": best[0], "dy": best[1], "std_m": round(best[2], 3), "median_m": round(best[3], 3),
                                 "n": best[4], "shift_m": round(float(np.hypot(best[0], best[1]) * 1.0117630165416), 1),
                                 "std_at_plus_minus_50px": ring},
            "report15": "318개, 중앙값 +7.7 m, 표준편차 5.1 m"}


def main() -> None:
    h, valid, rough, h1 = load_dtm_crop()
    slope = slope_deg_grid(h, CELL_M)
    passable = valid & (slope <= MAX_WALK_SLOPE_DEG)
    eta = eta_from_rock(rough)
    wps, _ = load_traverse(h.shape)
    base = tuple(int(round(v)) for v in lonlat_to_cell(wps[0]["lon"], wps[0]["lat"]))
    goal = tuple(int(round(v)) for v in lonlat_to_cell(*_wp_lonlat(wps, 1282)))
    res = {"model": mm.describe(), "e5_astar": check_astar(h, eta, passable, base),
           "e6_viewshed": check_viewshed(), "e10_georef": check_georef(wps, h1)}
    json.dump(res, open(f"{OUT}/e_quick_checks.json", "w"), ensure_ascii=False, indent=2, default=float)
    print(json.dumps(res, ensure_ascii=False, indent=1, default=float))


if __name__ == "__main__":
    main()
