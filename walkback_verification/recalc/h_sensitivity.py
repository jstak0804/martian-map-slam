"""계획 H4: 경사 상한·η 바닥값(·모래) 민감도 (분석만, 기본 모델 변경 없음)

실행: cd code && env -u PYTHONPATH ../recalc/.venv/bin/python ../recalc/h_sensitivity.py [--sand]
- 경사 상한: 칸 경사(slope_deg_grid) 상한과 간선 경사 상한(mars_walkback.MAX_EDGE_GRADE_PCT)을 같은 값으로 바꾼다.
- η 바닥값: η' = η + (바닥값 − 1). 모든 칸을 같이 올린다(Richmond 2015 표 11: 자갈·흙길 1.2).
- --sand: mars_walkback.sand_mask()가 있으면 모래 칸 η = max(η, SAND_ETA) 사례를 더한다(계획 H3).
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.getcwd())
import numpy as np  # noqa: E402
from scipy.sparse.csgraph import dijkstra  # noqa: E402

import mars_walkback as mw  # noqa: E402
import metabolic_model as mm  # noqa: E402
from mars_walkback import (  # noqa: E402
    CELL_M, _wp_lonlat, build_o2_graph, eta_from_rock, load_dtm_crop, load_traverse, lonlat_to_cell,
    slope_deg_grid, trace,
)

OUT = os.path.abspath(os.path.join(os.getcwd(), "..", "recalc", "outputs_h"))
CAPS_DEG = (15.0, 17.0, 20.0)
FLOORS = (1.0, 1.2)
BUDGETS_G = (100, 150, 200)
HV_SOLS = (706, 708, 709)   # Hidden Valley 진입·후퇴 웨이포인트 (2014-08)


def run_case(h: np.ndarray, valid: np.ndarray, slope: np.ndarray, eta: np.ndarray, cap: float,
             base_i: int, targets: dict[str, int]) -> dict:
    mw.MAX_EDGE_GRADE_PCT = float(np.tan(np.radians(cap)) * 100)
    passable = valid & (slope <= cap)
    g = build_o2_graph(h, eta, passable)
    ret, pred = dijkstra(g.T.tocsr(), directed=True, indices=base_i, return_predecessors=True)
    ret = ret.reshape(h.shape)
    km2 = (CELL_M / 1000) ** 2
    res = {f"area_km2_{x}g": round(float((ret <= x - mm.O2_RESERVE_G).sum() * km2), 3) for x in BUDGETS_G}
    for name, ti in targets.items():
        ty, tx = np.unravel_index(ti, h.shape)
        if not np.isfinite(ret[ty, tx]):
            res[name] = {"return_o2_g": None}
            continue
        path = trace(pred, ti, h.shape)   # 역방향 그래프의 선행 칸 = 거점 쪽 다음 칸 → 목표에서 거점까지
        length = sum(float(np.hypot(x1 - x0, y1 - y0)) * CELL_M for (x0, y0), (x1, y1) in zip(path[:-1], path[1:]))
        res[name] = {"return_o2_g": round(float(ret[ty, tx]), 1), "return_len_km": round(length / 1000, 3),
                     "path_cells": [int(y * h.shape[1] + x) for x, y in path]}
    res["_ret"] = ret
    return res


def main() -> None:
    use_sand = "--sand" in sys.argv
    os.makedirs(OUT, exist_ok=True)
    h, valid, rough, _ = load_dtm_crop()
    slope = slope_deg_grid(h, CELL_M)
    eta0 = eta_from_rock(rough)
    wps, _ = load_traverse(h.shape)
    W = h.shape[1]
    cell = lambda lon, lat: tuple(int(round(v)) for v in lonlat_to_cell(lon, lat))  # noqa: E731
    bx, by = cell(wps[0]["lon"], wps[0]["lat"])
    gx, gy = cell(*_wp_lonlat(wps, 1282))
    hx, hy = cell(*_wp_lonlat(wps, 708))
    sx, sy = cell(*_wp_lonlat(wps, 746))
    targets = {"sol1282": gy * W + gx, "hidden_valley_sol708": hy * W + hx, "sol746": sy * W + sx}

    sand = None
    if use_sand:
        radius = float(sys.argv[sys.argv.index("--sand-radius") + 1]) if "--sand-radius" in sys.argv else None
        sand = mw.sand_mask(h.shape, radius)
        print(f"모래 칸 {int(sand.sum())}개, η = {mw.SAND_ETA:.2f}", flush=True)

    cases = [(cap, fl, False) for fl in FLOORS for cap in CAPS_DEG]
    if "--sand-radius" in sys.argv:   # 계획 I5: 반경 민감도는 20°, 바닥값 1.0, 모래 켬/끔만
        cases = [(20.0, 1.0, False)]
    if sand is not None:
        cases += [(20.0, 1.0, True), (20.0, 1.2, True)]
    res = {"model": mm.describe(), "o2_reserve_g": round(mm.O2_RESERVE_G, 1), "cases": {}}
    rets = {}
    for cap, fl, sd in cases:
        eta = eta0 + (fl - 1.0)
        if sd:
            eta = np.where(sand, np.maximum(eta, mw.SAND_ETA), eta)
        key = f"cap{cap:.0f}_floor{fl:.1f}" + ("_sand" if sd else "")
        r = run_case(h, valid, slope, eta, cap, by * W + bx, targets)
        rets[key] = r.pop("_ret")
        if sand is not None:
            for tk in ("sol1282", "sol746"):
                r[tk]["crosses_sand"] = bool(r[tk].get("path_cells") and sand.ravel()[r[tk]["path_cells"]].any())
        for t in targets:
            r[t].pop("path_cells", None)
        res["cases"][key] = r
        print(key, r, flush=True)

    # 상한을 낮췄을 때 새로 막히는 칸 중, 기준(20°, 1.0) 150 g 영역 안에 있던 칸의 면적
    km2 = (CELL_M / 1000) ** 2
    ref_in = rets["cap20_floor1.0"] <= 150 - mm.O2_RESERVE_G
    res["newly_blocked_in_ref150_km2"] = {
        f"cap{c:.0f}": round(float((ref_in & valid & (slope > c)).sum() * km2), 3) for c in CAPS_DEG[:-1]}
    res["slope_share_pct_valid"] = {f"{a}-{b}": round(float(((slope >= a) & (slope < b))[valid].mean() * 100), 2)
                                    for a, b in ((0, 10), (10, 15), (15, 17), (17, 20), (20, 90))}
    if "--sand-radius" in sys.argv:
        res["sand_radius_m"] = radius; res["sand_cells"] = int(sand.sum())
        out_i = os.path.abspath(os.path.join(os.getcwd(), "..", "recalc", "outputs_i"))
        os.makedirs(out_i, exist_ok=True)
        json.dump(res, open(f"{out_i}/i5_sand_radius_{radius:g}.json", "w"), ensure_ascii=False, indent=2)
        print(json.dumps(res["cases"], ensure_ascii=False)); return
    name = "h_sensitivity_sand.json" if use_sand else "h_sensitivity.json"
    json.dump(res, open(f"{OUT}/{name}", "w"), ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in res.items() if k != "cases"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
