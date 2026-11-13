"""계획 F 2번: 지형계수 η 효과 민감도 (코드 변경 없음)

실행: cd code && ../recalc/.venv/bin/python ../recalc/f_eta_sensitivity.py
지형 항 (η − 1)을 배수 m배로 키운다(η' = 1 + m(η − 1)). m = 3은 지구 실측 +28%(Voloshina 2013) ÷ 현재 모델
최대 +9%에서 정한 값이며 화성·우주복 근거는 없다.
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
    CELL_M, MAX_WALK_SLOPE_DEG, _wp_lonlat, build_o2_graph, eta_from_rock, load_dtm_crop, load_traverse,
    lonlat_to_cell, slope_deg_grid,
)

OUT = os.path.abspath(os.path.join(os.getcwd(), "..", "recalc", "outputs_f"))


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    h, valid, rough, _ = load_dtm_crop()
    passable = valid & (slope_deg_grid(h, CELL_M) <= MAX_WALK_SLOPE_DEG)
    eta = eta_from_rock(rough)
    wps, _ = load_traverse(h.shape)
    bx, by = (int(round(v)) for v in lonlat_to_cell(wps[0]["lon"], wps[0]["lat"]))
    gx, gy = (int(round(v)) for v in lonlat_to_cell(*_wp_lonlat(wps, 1282)))
    km2 = (CELL_M / 1000) ** 2
    lv = float(mm.metabolic_rate_w(0.0, 1.0))
    res = {"model": mm.describe(), "eta_stats": {"p50": round(float(np.median(eta[passable])), 3),
                                                  "p90": round(float(np.percentile(eta[passable], 90)), 3),
                                                  "share_at_max": round(float(np.mean(eta[passable] >= mm.ETA_MAX - 1e-9)), 4)},
           "cases": {}}
    for m in (1, 2, 3):
        e = 1 + m * (eta - 1)
        ret = dijkstra(build_o2_graph(h, e, passable).T.tocsr(), directed=True, indices=by * h.shape[1] + bx).reshape(h.shape)
        res["cases"][str(m)] = {
            "level_mr_at_eta_max_w": round(float(mm.metabolic_rate_w(0.0, 1 + m * (mm.ETA_MAX - 1))), 1),
            "level_increase_at_eta_max_pct": round((float(mm.metabolic_rate_w(0.0, 1 + m * (mm.ETA_MAX - 1))) / lv - 1) * 100, 1),
            **{f"area_km2_{x}g": round(float((ret <= x - mm.O2_RESERVE_G).sum() * km2), 3) for x in (100, 150, 200)},
            "sol1282_return_o2_g": round(float(ret[gy, gx]), 1)}
        print(m, res["cases"][str(m)], flush=True)
    json.dump(res, open(f"{OUT}/f_eta_sensitivity.json", "w"), ensure_ascii=False, indent=2)
    print(res["eta_stats"])


if __name__ == "__main__":
    main()
