"""계획 J14: "산소 최소 경로 하나만 보는" 가정 점검 (분석만)

실행: cd code && env -u PYTHONPATH ../recalc/.venv/bin/python ../recalc/j14_single_path.py
- 같은 간선(16방향, 간선 경사 상한)에서 비용을 산소 / 냉각수 / 선량 / 혼합(spe_walkback 방식)으로 바꾼 귀환 트리 4개를 만든다.
- 각 트리 위에서 세 자원을 spe_walkback.return_tree_totals로 합산하고, 칸마다 세 조건(산소·냉각수·선량 예산)을 판정한다.
- "놓친 칸" = 산소 최소 트리로는 불가인데 다른 트리 중 하나로는 세 조건을 모두 만족하는 칸.
  다목적 탐색의 하한 근사다(네 경로만 봄).
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.getcwd())
import numpy as np  # noqa: E402
from scipy.sparse import csr_matrix  # noqa: E402
from scipy.sparse.csgraph import dijkstra  # noqa: E402

import mars_walkback as mw  # noqa: E402
import spe_walkback as sw  # noqa: E402
from suit_cooling import FEEDWATER_FULL_G, water_reserve_g  # noqa: E402

OUT = os.path.abspath(os.path.join(os.getcwd(), "..", "recalc", "outputs_j"))
KM2 = (mw.CELL_M / 1000) ** 2
CASES = [  # (이름, 남은 산소 g, 남은 냉각수 g, 추가 열 W, SPE 배율)
    ("water0.6", 150, 600, 0.0, 1.0),
    ("water0.6_q100", 150, 600, 100.0, 1.0),
    ("water1.0_q50", 200, 1000, 50.0, 1.0),
    ("spe_x30", 150, FEEDWATER_FULL_G, 0.0, 30.0),
    ("spe_x50", 150, FEEDWATER_FULL_G, 0.0, 50.0),
]


def graphs(h, eta, rate, passable, q, o2_b, w_b):
    rows, cols = h.shape
    yy, xx = np.mgrid[0:rows, 0:cols]
    src, dst, wo, ww, wd = [], [], [], [], []
    for dx, dy in mw.OFFSETS:
        a, b, ok = mw.offset_ok(passable, dx, dy, h)
        ya, xa, yb, xb = yy[a][ok], xx[a][ok], yy[b][ok], xx[b][ok]
        o2, dose, water = sw.edge_values(h, eta, rate, ya, xa, yb, xb, q)
        src.append(ya * cols + xa); dst.append(yb * cols + xb); wo.append(o2); ww.append(water); wd.append(dose)
    s, d = np.concatenate(src), np.concatenate(dst)
    o, w, ds = np.concatenate(wo), np.concatenate(ww), np.concatenate(wd)
    n = rows * cols
    mk = lambda c: csr_matrix((np.maximum(c, 1e-12), (s, d)), shape=(n, n))  # noqa: E731
    return {"o2": mk(o), "water": mk(w), "dose": mk(ds),
            "mixed": mk(o / o2_b + ds / sw.DOSE_BUDGET_MSV + w / max(w_b, 1.0))}


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    h, valid, eta, shielding, passable, _, (bx, by) = sw.load_scene()
    base = by * h.shape[1] + bx
    res = {}
    for name, o2_left, w_left, q, mult in CASES:
        rate = sw.dose_rate_msv_h(shielding, mult)
        o2_b = o2_left - mw.O2_RESERVE_G
        w_b = w_left - water_reserve_g(q)
        gs = graphs(h, eta, rate, passable, q, o2_b, w_b)
        ok = {}
        for k, g in gs.items():
            cost, pred = dijkstra(g.T.tocsr(), directed=True, indices=base, return_predecessors=True)
            o2, dose, water = sw.return_tree_totals(h, eta, rate, cost, pred, q)
            ok[k] = (o2 <= o2_b) & (dose <= sw.DOSE_BUDGET_MSV) & (water <= w_b)
        union = ok["o2"] | ok["water"] | ok["dose"] | ok["mixed"]
        r = {f"area_{k}_tree_km2": round(float(v.sum() * KM2), 3) for k, v in ok.items()}
        r["area_union_km2"] = round(float(union.sum() * KM2), 3)
        r["missed_by_o2_tree_km2"] = round(float((union & ~ok["o2"]).sum() * KM2), 3)
        r["missed_share_pct"] = round(float((union & ~ok["o2"]).sum() / max(union.sum(), 1) * 100), 2)
        res[name] = r
        print(name, r, flush=True)
    json.dump(res, open(f"{OUT}/j14_single_path.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
