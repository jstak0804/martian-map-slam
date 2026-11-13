"""계획 J8: 남은 가정 민감도 (분석만, 원본 기본값 불변 — 이 프로세스 안에서만 모듈 값을 바꿈)

실행: cd code && env -u PYTHONPATH ../recalc/.venv/bin/python ../recalc/j8_assumptions.py
(a) 귀환 1회 선량 예산 0.5 / 1(현재) / 2 mSv × SPE ×2.9 / ×30 / ×50  → spe_walkback.run_scenario 안전 면적(150 g)
(b) 넘어짐 기준: 턱 높이차 0.3 / 0.5(현재) / 0.7 m × "높음" 비율 0.15 / 0.25(현재) / 0.35 → "높음" 칸 금지 시 150 g 면적
(c) 통신: (거점, 우주복) 안테나 (3, 2)(현재) / (10, 2) / (3, 1.5) m → 150 g 영역 중 가시선 음영 비율
(d) 내리막 비용: 현재(LCDA × 우주복 경사 민감도 축소) / 축소 없음(LCDA 비율 그대로) / 평지와 같음 → 150 g 면적, sol 1282 귀환 산소
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.getcwd())
import numpy as np  # noqa: E402
from scipy.sparse.csgraph import dijkstra  # noqa: E402

import comm_los as cl  # noqa: E402
import fall_risk_map as fr  # noqa: E402
import mars_walkback as mw  # noqa: E402
import metabolic_model as mm  # noqa: E402
import spe_walkback as sw  # noqa: E402

OUT = os.path.abspath(os.path.join(os.getcwd(), "..", "recalc", "outputs_j"))
KM2 = (mw.CELL_M / 1000) ** 2
BUDGET = 150 - mm.O2_RESERVE_G


def ret_tree(h, eta, passable, base):
    return dijkstra(mw.build_o2_graph(h, eta, passable).T.tocsr(), directed=True, indices=base).reshape(h.shape)


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    res = {}
    h, valid, eta, shielding, passable, _, (bx, by) = sw.load_scene()
    base = by * h.shape[1] + bx
    _, _, _, h1 = mw.load_dtm_crop()
    ret0 = ret_tree(h, eta, passable, base)
    area0 = float((ret0 <= BUDGET).sum() * KM2)
    res["check_area150"] = round(area0, 3)
    print("check", area0, flush=True)

    # (a) 선량 예산
    res["a_dose_budget"] = {}
    for bud in (0.5, 1.0, 2.0):
        sw.DOSE_BUDGET_MSV = bud
        for mult in (2.9, 30, 50):
            r = sw.run_scenario(h, eta, shielding, passable, base, mult)
            res["a_dose_budget"][f"{bud}mSv_x{mult}"] = {k: round(r[k], 3) for k in ("area_safe_km2", "area_o2_only_km2", "area_dose_limited_km2")}
            print("a", bud, mult, res["a_dose_budget"][f"{bud}mSv_x{mult}"], flush=True)
    sw.DOSE_BUDGET_MSV = 1.0

    # (b) 넘어짐 기준
    res["b_fall"] = {}
    for step in (0.3, 0.5, 0.7):
        fr.STEP_M = step
        frac, *_ = fr.hazard_fraction(h1)
        for hf in (0.15, 0.25, 0.35):
            high = frac >= hf
            ret = ret_tree(h, eta, passable & ~high, base)
            a = float((ret <= BUDGET).sum() * KM2)
            res["b_fall"][f"step{step}_high{hf}"] = {"area150_nofall": round(a, 3), "loss_km2": round(area0 - a, 3),
                                                     "high_share_valid_pct": round(float(high[valid].mean() * 100), 2)}
            print("b", step, hf, res["b_fall"][f"step{step}_high{hf}"], flush=True)
    fr.STEP_M = 0.5

    # (c) 통신
    res["c_comm"] = {}
    inside = ret0 <= BUDGET
    for ab, asu in ((3.0, 2.0), (10.0, 2.0), (3.0, 1.5)):
        vis, known = cl.viewshed(h, valid, (bx, by), ab, asu)
        dark = inside & ~vis
        res["c_comm"][f"base{ab}_suit{asu}"] = {"dark_km2": round(float(dark.sum() * KM2), 3),
                                                "dark_share_pct": round(float(dark.sum() / max(inside.sum(), 1) * 100), 1)}
        print("c", ab, asu, res["c_comm"][f"base{ab}_suit{asu}"], flush=True)

    # (d) 내리막 비용
    res["d_downhill"] = {}
    wps, _ = mw.load_traverse(h.shape)
    gx, gy = (int(round(v)) for v in mw.lonlat_to_cell(*mw._wp_lonlat(wps, 1282)))
    orig_scale, orig_ratio = mm.grade_effect_scale, mm.downhill_cost_ratio
    variants = {
        "current": (orig_scale, orig_ratio),
        "no_suit_scaling": (lambda g: np.ones_like(np.asarray(g, dtype=float)), orig_ratio),
        "flat_cost": (orig_scale, lambda g, v=None: np.ones_like(np.asarray(g, dtype=float))),
    }
    for name, (sc, rt) in variants.items():
        mm.grade_effect_scale, mm.downhill_cost_ratio = sc, rt
        ret = ret_tree(h, eta, passable, base)
        res["d_downhill"][name] = {"area150": round(float((ret <= BUDGET).sum() * KM2), 3),
                                   "sol1282_return_o2_g": round(float(ret[gy, gx]), 1),
                                   "speed_at_minus20pct": round(float(mm.walk_speed(-20.0)), 3),
                                   "cost_ratio_at_minus20pct": round(float(mm.downhill_cost_ratio(-20.0)), 3)}
        print("d", name, res["d_downhill"][name], flush=True)
    mm.grade_effect_scale, mm.downhill_cost_ratio = orig_scale, orig_ratio
    json.dump(res, open(f"{OUT}/j8_assumptions.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
