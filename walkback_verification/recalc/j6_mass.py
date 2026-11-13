"""계획 J6: 체중·우주복 질량 민감도 (분석만, 코드 기본값 불변)

실행: cd code && env -u PYTHONPATH ../recalc/.venv/bin/python ../recalc/j6_mass.py
- metabolic_model의 BODY_MASS_KG·SUIT_MASS_KG와, 질량에서 파생되는 모듈 값(_W_MARS_N, IST 계수, STANDING_MR_W)을
  이 프로세스 안에서만 바꿔 다시 계산한다. 예비분(352 W 고정)은 질량과 무관하다.
- IST VO2는 체중당(mL/kg/min)이고 계수는 TGAW에 선형이다. TGAW가 IST 범위(236~627 N)를 넘으면 외삽으로 표시한다.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.getcwd())
import numpy as np  # noqa: E402
from scipy.sparse.csgraph import dijkstra  # noqa: E402

import metabolic_model as mm  # noqa: E402
from mars_walkback import (CELL_M, MAX_WALK_SLOPE_DEG, _wp_lonlat, build_o2_graph, eta_from_rock,  # noqa: E402
                           load_dtm_crop, load_traverse, lonlat_to_cell, slope_deg_grid)

OUT = os.path.abspath(os.path.join(os.getcwd(), "..", "recalc", "outputs_j"))
BODY = (60.0, 75.0, 90.0)
SUIT = (70.0, 90.0, 110.0)


def set_mass(body: float, suit: float) -> None:
    mm.BODY_MASS_KG, mm.SUIT_MASS_KG = body, suit
    mm._W_MARS_N = (body + suit) * mm.G_MARS_M_S2
    mm._LA, mm._LB, mm._LC = (s * mm._W_MARS_N + i for s, i in mm._IST["level_lin"])
    mm._GA, mm._GB = (s * mm._W_MARS_N + i for s, i in mm._IST["grade_lin"])
    mm.STANDING_MR_W = float(mm.pandolf_metabolic_rate_w(0.0, 1.0, mm.G_RATIO_MARS, 0.0))


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    h, valid, rough, _ = load_dtm_crop()
    passable = valid & (slope_deg_grid(h, CELL_M) <= MAX_WALK_SLOPE_DEG)
    eta = eta_from_rock(rough)
    wps, _ = load_traverse(h.shape)
    W = h.shape[1]
    cell = lambda lon, lat: tuple(int(round(v)) for v in lonlat_to_cell(lon, lat))  # noqa: E731
    bx, by = cell(wps[0]["lon"], wps[0]["lat"])
    sx, sy = cell(*_wp_lonlat(wps, 746))
    base, s746 = by * W + bx, sy * W + sx
    km2 = (CELL_M / 1000) ** 2
    lo, hi = mm._IST["tgaw_range_n"]
    rows = []
    for b in BODY:
        for s in SUIT:
            set_mass(b, s)
            g = build_o2_graph(h, eta, passable)
            ret = dijkstra(g.T.tocsr(), directed=True, indices=base)
            out = dijkstra(g, directed=True, indices=base)
            tgaw = (b + s) * mm.G_MARS_M_S2
            r = {"body_kg": b, "suit_kg": s, "tgaw_n": round(tgaw, 1), "tgaw_extrapolated": not (lo <= tgaw <= hi),
                 "level_mr_w": round(float(mm.metabolic_rate_w(0.0, 1.0)), 1),
                 "standing_mr_w": round(mm.STANDING_MR_W, 1),
                 **{f"area_km2_{x}g": round(float((ret <= x - mm.O2_RESERVE_G).sum() * km2), 3) for x in (100, 150, 200)},
                 "sol746_roundtrip_o2_g": round(float(out[s746] + ret[s746]), 1),
                 "sol746_roundtrip_plus_reserve_le_450": bool(out[s746] + ret[s746] + mm.O2_RESERVE_G <= 450)}
            rows.append(r)
            print(r, flush=True)
    set_mass(75.0, 90.0)
    json.dump({"o2_reserve_g": round(mm.O2_RESERVE_G, 1), "ist_tgaw_range_n": [lo, hi], "rows": rows},
              open(f"{OUT}/j6_mass.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
