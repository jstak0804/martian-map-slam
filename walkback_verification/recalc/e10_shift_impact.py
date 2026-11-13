"""계획 E 10번 보조: 웨이포인트를 DTM에 맞추는 수평 이동(e_quick_checks의 최적 이동)을 적용하면
거점 산소 150 g 면적과 sol 1282 귀환 산소가 얼마나 바뀌는지 본다. 코드 변경 없음.

실행: cd code && ../recalc/.venv/bin/python ../recalc/e10_shift_impact.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.getcwd())
import numpy as np  # noqa: E402
from scipy.sparse.csgraph import dijkstra  # noqa: E402

import metabolic_model as mm  # noqa: E402
from mars_walkback import (  # noqa: E402
    BLOCK, CELL_M, MAX_WALK_SLOPE_DEG, _wp_lonlat, build_o2_graph, eta_from_rock, load_dtm_crop, load_traverse,
    lonlat_to_cell, slope_deg_grid,
)

OUT = os.path.abspath(os.path.join(os.getcwd(), "..", "recalc", "outputs_e"))


def _common_subset_std(q) -> dict:
    """이동 전후 모두 DTM 값이 있는 웨이포인트만으로 표준편차를 비교(점 구성이 달라지는 효과 제거)."""
    h, _, _, h1 = load_dtm_crop()
    wps, _ = load_traverse(h.shape)
    def errs(sx, sy):
        out = []
        for p in wps:
            x, y = lonlat_to_cell(p["lon"], p["lat"])
            l, s = int(round(y * BLOCK)) + sy, int(round(x * BLOCK)) + sx
            ok = 0 <= l < h1.shape[0] and 0 <= s < h1.shape[1]
            out.append(float(h1[l, s]) - p["elev_geoid"] if ok else np.nan)
        return np.array(out)
    e0, e1 = errs(0, 0), errs(q["dx"], q["dy"])
    c = np.isfinite(e0) & np.isfinite(e1)
    return {"n_common": int(c.sum()), "std_as_is_m": round(float(e0[c].std()), 3), "std_shifted_m": round(float(e1[c].std()), 3),
            "median_as_is_m": round(float(np.median(e0[c])), 3), "median_shifted_m": round(float(np.median(e1[c])), 3)}


def main() -> None:
    q = json.load(open(f"{OUT}/e_quick_checks.json"))["e10_georef"]["best_shift_px_1m"]
    sx, sy = q["dx"] / BLOCK, q["dy"] / BLOCK  # 1 m 픽셀 → 10 m 칸
    h, valid, rough, _ = load_dtm_crop()
    passable = valid & (slope_deg_grid(h, CELL_M) <= MAX_WALK_SLOPE_DEG)
    eta = eta_from_rock(rough)
    wps, _ = load_traverse(h.shape)
    gT = build_o2_graph(h, eta, passable).T.tocsr()
    cell_km2 = (CELL_M / 1000) ** 2
    res = {"shift_cells": [round(sx, 2), round(sy, 2)], "model": mm.describe(), "cases": {}}
    for name, (ox, oy) in {"as_is": (0, 0), "shifted": (sx, sy)}.items():
        bx, by = (int(round(v)) for v in np.add(lonlat_to_cell(wps[0]["lon"], wps[0]["lat"]), (ox, oy)))
        gx, gy = (int(round(v)) for v in np.add(lonlat_to_cell(*_wp_lonlat(wps, 1282)), (ox, oy)))
        ok = bool(passable[by, bx])
        moved_m = 0.0
        if not ok:  # 이동한 거점이 DTM 결측·통행 불가 칸이면 가장 가까운 통행 가능 칸으로 옮긴다
            cand = np.argwhere(passable)
            d = np.hypot(cand[:, 1] - bx, cand[:, 0] - by)
            k = int(np.argmin(d)); moved_m = float(d[k] * CELL_M)
            by, bx = (int(v) for v in cand[k])
        ret = dijkstra(gT, directed=True, indices=by * h.shape[1] + bx).reshape(h.shape)
        res["cases"][name] = {"base_cell": [bx, by], "base_passable": ok, "base_moved_to_nearest_passable_m": round(moved_m, 1),
                              **{f"area_km2_{x}g": round(float((ret <= x - mm.O2_RESERVE_G).sum() * cell_km2), 3)
                                 for x in (100, 150, 200)},
                              "sol1282_return_o2_g": round(float(ret[gy, gx]), 2)}
    common = _common_subset_std(q)
    res["common_subset_check"] = common
    json.dump(res, open(f"{OUT}/e10_shift_impact.json", "w"), ensure_ascii=False, indent=2)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
