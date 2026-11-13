"""계획 K2: 지형·내리막 — Kim 2023 실측 대조, η 기준 맞춤, Minetti 내리막 경계 사례 (분석만, 기본값 불변)

실행: cd code && env -u PYTHONPATH ../recalc/.venv/bin/python ../recalc/k2_terrain.py
- K2a: η 값별 평지 대사량 증가 vs Kim 2023 바위밭(+10% 시간당, p = 0.13) / 혼합(+58%). 대리 지표 η 분포.
- K2b: η 효과를 Richmond 기준(Pandolf 움직임 항이 전체에서 차지하는 비율, 지구 조건)으로 맞춘 배수 s를 지형 항에 곱함.
       η' = 1 + s(η − 1). 기준 면적, 바닥값 1.2, 모래(Hidden Valley 귀환 산소)
- K2c: 내리막 비용비를 Minetti 2002 식 그대로(Cw(i)/Cw(0), i < 0) 쓴 경계 사례. 같은 속도에서 거리당 비 = 시간당 비로 가정.
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

OUT = os.path.abspath(os.path.join(os.getcwd(), "..", "recalc", "outputs_k"))
KM2 = (mw.CELL_M / 1000) ** 2
BUDGET = 150 - mm.O2_RESERVE_G
KIM = {"flat_btu_h": 1311, "obst_btu_h": 1439, "mixed_btu_h": 2071, "flat_kmh": 5.18, "obst_kmh": 4.96, "mixed_kmh": 4.84}


def minetti_cw(i):
    i = np.asarray(i, dtype=float)
    return 280.5 * i ** 5 - 58.7 * i ** 4 - 76.8 * i ** 3 + 51.9 * i ** 2 + 19.6 * i + 2.5


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    h, valid, rough, _ = mw.load_dtm_crop()
    passable = valid & (mw.slope_deg_grid(h, mw.CELL_M) <= mw.MAX_WALK_SLOPE_DEG)
    eta = mw.eta_from_rock(rough)
    wps, _ = mw.load_traverse(h.shape)
    W = h.shape[1]
    cell = lambda lon, lat: tuple(int(round(v)) for v in mw.lonlat_to_cell(lon, lat))  # noqa: E731
    bx, by = cell(wps[0]["lon"], wps[0]["lat"]); base = by * W + bx
    targets = {s: (lambda c: c[1] * W + c[0])(cell(*mw._wp_lonlat(wps, s))) for s in (708, 746, 1282)}

    def run(e):
        ret = dijkstra(mw.build_o2_graph(h, e, passable).T.tocsr(), directed=True, indices=base)
        return {"area150": round(float((ret <= BUDGET).sum() * KM2), 3),
                **{f"ret_sol{s}_g": round(float(ret[c]), 1) for s, c in targets.items()}}

    res = {}
    # K2a
    lv = float(mm.metabolic_rate_w(0.0, 1.0))
    slice_w = (mm.BODY_MASS_KG + mm.SUIT_MASS_KG) * mm.G_RATIO_MARS * 1.5 * mm.V_FLAT_M_S ** 2
    res["k2a"] = {
        "kim_obst_per_time_pct": round((KIM["obst_btu_h"] / KIM["flat_btu_h"] - 1) * 100, 1),
        "kim_obst_per_dist_pct": round((KIM["obst_btu_h"] / KIM["obst_kmh"] / (KIM["flat_btu_h"] / KIM["flat_kmh"]) - 1) * 100, 1),
        "kim_mixed_per_time_pct": round((KIM["mixed_btu_h"] / KIM["flat_btu_h"] - 1) * 100, 1),
        "kim_mixed_per_dist_pct": round((KIM["mixed_btu_h"] / KIM["mixed_kmh"] / (KIM["flat_btu_h"] / KIM["flat_kmh"]) - 1) * 100, 1),
        "ours_pct_per_unit_eta": round(slice_w / lv * 100, 1),
        "ours_pct_at_eta": {f"{e:.2f}": round((float(mm.metabolic_rate_w(0.0, e)) / lv - 1) * 100, 1) for e in (1.1, 1.2, 1.3, 1.5)},
        "eta_reproducing_kim_obst_per_time": round(1 + (KIM["obst_btu_h"] / KIM["flat_btu_h"] - 1) / (slice_w / lv), 3),
        "eta_percentiles_passable": {f"p{q}": round(float(np.percentile(eta[passable], q)), 3) for q in (50, 90, 95, 99)},
        "share_cells_eta_ge_1.3_pct": round(float((eta[passable] >= 1.3).mean() * 100), 2),
    }
    print("K2a", res["k2a"], flush=True)

    # K2b: Richmond 기준 배수 (지구, 같은 질량·속도: Pandolf 움직임 항 / Pandolf 전체)
    W_, L_, V_ = mm.BODY_MASS_KG, mm.SUIT_MASS_KG, mm.V_FLAT_M_S
    earth_total = 1.5 * W_ + 2.0 * (W_ + L_) * (L_ / W_) ** 2 + (W_ + L_) * 1.5 * V_ ** 2
    earth_share = (W_ + L_) * 1.5 * V_ ** 2 / earth_total
    s = earth_share / (slice_w / lv)
    res["k2b"] = {"earth_dynamic_share": round(earth_share, 3), "ours_share": round(slice_w / lv, 3), "scale": round(s, 3), "cases": {}}
    sand = mw.sand_mask(h.shape)
    for name, e0 in (("current", eta), ("floor1.2", eta + 0.2), ("sand", np.where(sand, np.maximum(eta, mw.SAND_ETA), eta))):
        for tag, sc in (("as_is", 1.0), ("richmond_basis", s)):
            r = run(1 + sc * (e0 - 1))
            res["k2b"]["cases"][f"{name}|{tag}"] = r
            print("K2b", name, tag, r, flush=True)

    # K2c: 내리막 경계 사례
    orig_ratio, orig_scale = mm.downhill_cost_ratio, mm.grade_effect_scale
    def minetti_ratio(g, v=None):
        g = np.asarray(g, dtype=float)
        return np.where(g < 0, minetti_cw(np.minimum(g, 0.0) / 100) / minetti_cw(0.0), 1.0)
    variants = {"current": (orig_ratio, orig_scale),
                "no_suit_scaling": (orig_ratio, lambda g: np.ones_like(np.asarray(g, dtype=float))),
                "flat_cost": (lambda g, v=None: np.ones_like(np.asarray(g, dtype=float)), orig_scale),
                "minetti_raw": (minetti_ratio, orig_scale)}
    res["k2c"] = {"minetti_ratio_at": {f"{g}%": round(float(minetti_ratio(g)), 3) for g in (-5, -10, -20, -30)}}
    for name, (rt, sc) in variants.items():
        mm.downhill_cost_ratio, mm.grade_effect_scale = rt, sc
        r = run(eta); r["ratio_at_-10"] = round(float(mm.downhill_cost_ratio(-10.0)), 3); r["ratio_at_-20"] = round(float(mm.downhill_cost_ratio(-20.0)), 3)
        res["k2c"][name] = r
        print("K2c", name, r, flush=True)
    mm.downhill_cost_ratio, mm.grade_effect_scale = orig_ratio, orig_scale
    json.dump(res, open(f"{OUT}/k2_terrain.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
