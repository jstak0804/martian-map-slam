"""심박과 잔여 냉각수가 귀환 가능 면적에 주는 영향 비교 (안 B 중심 모델: 90 kg, ㄱ 0.92 m/s, 예비분 고정)

실행: cd code && ../recalc/.venv/bin/python ../recalc/sensitivity_hr_water.py  (model_b.py를 먼저 실행)

생각의 틀:
  - 산소를 쓰는 것은 대사(근육의 일)이고 심박은 그 결과로 따라 오르는 지표다. 오르막에서 심박이 오르는 것은
    대사량이 오르기 때문이며, 대사량은 이미 경사 항 ΔG로 모델에 들어 있다.
  - 그래서 심박이 계산에 끼어드는 길은 "모델 대사량과 실제 대사량의 차이"(보고서 16의 k)를 재는 것뿐이다.
    심박의 영향 = k가 사람마다·상황마다 얼마나 흔들리는가 + 심박으로 k를 잴 때의 오차.
"""
from __future__ import annotations

import json
import os
import sys

# 2026-11-12: 이 스크립트는 "원본 모델(Pandolf, 8방향)" 기준으로 쓰였다. 원본 code/의 기본값이 바뀌었으므로
# 원본 모듈을 불러오기 전에 고정한다(PLAN_D 1번).
os.environ["GALE_METABOLIC_MODEL"] = "pandolf_legacy"
os.environ["GALE_GRID_NEIGHBORS"] = "8"
os.environ["GALE_EDGE_SLOPE_CAP"] = "0"   # 계획 E 7번 이전 결과 재현
sys.path.insert(0, os.getcwd())  # code/
sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), "..", "recalc")))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from scipy.sparse.csgraph import dijkstra  # noqa: E402

import model_b as mb  # noqa: E402
from human_mission_navigation import style_ax  # noqa: E402

OUT = mb.OUT
CELL_KM2 = (mb.CELL_M / 1000) ** 2
O2_LEFT = 150.0
LEAK_NOMINAL = 9.1        # Apollo 15 계획 누설 중간값 (EVA 2)
BTU_H_PER_W = 1 / 0.29307
HR_A, HR_B = 284.55, 5.984          # 보고서 16이 인용한 Hoffmann 2021: MR(BTU/h) = 284.55 + 5.984·HR
HR_FIT_MAX_BTU_H = 1400.0           # 보고서 16: 회귀 데이터 범위 약 1400 BTU/h
HR_IND_RMSE_BTU_H = 89.66           # 보고서 16: 개인별 예측 RMSE (± 44.24)


RES = {}  # 고정 예비분(444 W 30분치), main()에서 채움


def area(ret_o2, ret_t, k=1.0, water_left=mb.FEEDWATER_FULL_G, leak=LEAK_NOMINAL, pad=1.0):
    with np.errstate(invalid="ignore"):
        ok_o2 = k * pad * ret_o2 + leak * ret_t <= O2_LEFT - RES["o2"]
        ok_w = k * pad * ret_o2 * mb.WATER_PER_O2 <= water_left - RES["w"]
    return float((ok_o2 & ok_w).sum() * CELL_KM2)


def hr_from_w(w):
    return (np.asarray(w) * BTU_H_PER_W - HR_A) / HR_B


def route_profile(model, route, h, eta):
    """귀환 경로(칸 -> 거점)를 따라 칸 이동별 경사·대사량·심박."""
    g, w, d = [], [], []
    for (x1, y1), (x2, y2) in zip(route[:-1], route[1:]):
        dist = np.hypot(x2 - x1, y2 - y1) * mb.CELL_M
        grade = (h[y2, x2] - h[y1, x1]) / dist * 100
        mr, v = model["rate"](np.array(grade), np.array(0.5 * (eta[y1, x1] + eta[y2, x2])))
        g.append(grade); w.append(float(mr)); d.append(dist)
    g, w, d = map(np.array, (g, w, d))
    return {"grade": g, "w": w, "hr": hr_from_w(w), "dist": d}


def main() -> None:
    cur = mb.load_curves()
    m_b = mb.make_model("suit90_A_all092", cur, "A_all092", 90.0)
    m_p = mb.make_model("pandolf", None, None, mb.SUIT_MASS_KG)
    RES.update({"o2": 0.5 * m_b["level_o2_g_h"], "w": 0.5 * m_b["level_o2_g_h"] * mb.WATER_PER_O2})
    fb = np.load(os.path.join(OUT, "b_return_suit90_A_all092.npz"))
    ret_o2, ret_t = fb["ret_o2"].astype(float), fb["ret_t_h"].astype(float)

    # ---------- 1. 경로를 따라 본 심박 (평지 vs 오르막) ----------
    h, valid, rough_r, _ = mb.load_dtm_crop()
    slope = mb.slope_deg_grid(h, mb.CELL_M)
    passable = valid & (slope <= mb.MAX_WALK_SLOPE_DEG)
    eta = mb.eta_from_rock(rough_r)
    wps, _ = mb.load_traverse(h.shape)
    bx, by = (int(round(v)) for v in mb.lonlat_to_cell(wps[0]["lon"], wps[0]["lat"]))
    gx, gy = (int(round(v)) for v in mb.lonlat_to_cell(*mb._wp_lonlat(wps, mb.GOAL_SOL)))
    base_idx, goal = by * h.shape[1] + bx, gy * h.shape[1] + gx
    profiles = {}
    for m in (m_p, m_b):
        g_o2, _ = mb.edge_arrays(h, eta, passable, m)
        _, pred = dijkstra(g_o2, directed=True, indices=base_idx, return_predecessors=True)
        route = mb.trace(pred, goal, h.shape)  # 갈 때(오르막이 많은 방향)
        profiles[m["name"]] = route_profile(m, route, h, eta)

    def band(p, lo, hi):
        sel = (p["grade"] >= lo) & (p["grade"] < hi)
        return {"share_dist": round(float(p["dist"][sel].sum() / p["dist"].sum()), 3),
                "mean_w": round(float(p["w"][sel].mean()), 0) if sel.any() else None,
                "mean_hr": round(float(p["hr"][sel].mean()), 0) if sel.any() else None}

    hr_table = {name: {"downhill(<-2%)": band(p, -100, -2), "flat(-2~2%)": band(p, -2, 2),
                       "uphill(2~10%)": band(p, 2, 10), "steep(>=10%)": band(p, 10, 100),
                       "beyond_fit_share_dist": round(float(p["dist"][p["w"] * BTU_H_PER_W > HR_FIT_MAX_BTU_H].sum()
                                                            / p["dist"].sum()), 3)}
                for name, p in profiles.items()}

    # ---------- 2. 심박으로 k를 잴 때의 오차 ----------
    lvl_btu = m_b["level_w"] * BTU_H_PER_W
    k_err_meas = HR_IND_RMSE_BTU_H / lvl_btu        # 개인별 회귀식이 있을 때 1σ
    hr_level_b = float(hr_from_w(m_b["level_w"]))

    # ---------- 3. 민감도: k vs 냉각수 ----------
    base = area(ret_o2, ret_t)
    ks = np.round(np.arange(0.70, 1.501, 0.05), 2)
    waters = np.array([300, 400, 500, 600, 700, 800, 900, 1000, 1200, 1500, 2000, 3600], float)
    grid = np.array([[area(ret_o2, ret_t, k=k, water_left=wl) for k in ks] for wl in waters])
    # 냉각수가 반경을 정하기 시작하는 잔량 (k별)
    thresh = {}
    for k in (0.85, 1.0, 1.15, 1.3):
        o2_only = area(ret_o2, ret_t, k=k, water_left=1e9)
        lo, hi = 0.0, 3600.0
        for _ in range(40):
            mid = 0.5 * (lo + hi)
            lo, hi = (lo, mid) if area(ret_o2, ret_t, k=k, water_left=mid) >= o2_only - 1e-9 else (mid, hi)
        thresh[str(k)] = round(hi, 0)
    # 토네이도: 같은 "그럴듯한 범위"에서 면적 변화
    cv = 0.15  # 개인차 1σ 가정 (아래 근거 참조)
    tornado = {
        "k_individual_±1σ(0.85~1.15)": [area(ret_o2, ret_t, k=1 - cv), area(ret_o2, ret_t, k=1 + cv)],
        "k_HR_measurement_±1σ": [area(ret_o2, ret_t, k=1 - k_err_meas), area(ret_o2, ret_t, k=1 + k_err_meas)],
        "water_full_vs_1.0kg": [area(ret_o2, ret_t, water_left=1000), base],
        "water_full_vs_0.6kg": [area(ret_o2, ret_t, water_left=600), base],
        "water_full_vs_0.3kg": [area(ret_o2, ret_t, water_left=300), base],
        "leak_0_vs_13.6": [area(ret_o2, ret_t, leak=13.6), area(ret_o2, ret_t, leak=0.0)],
        "pad_1.0_vs_1.2": [area(ret_o2, ret_t, pad=1.2), base],
    }
    # 국소 탄력도 (면적 % / 입력 %)
    def elastic(f, x0, dx):
        a0 = f(x0)
        return ((f(x0 * (1 + dx)) - f(x0 * (1 - dx))) / (2 * dx)) / a0 if a0 else None
    elast = {
        "k_at_1.0": elastic(lambda k: area(ret_o2, ret_t, k=k), 1.0, 0.05),
        "water_at_0.6kg": elastic(lambda w: area(ret_o2, ret_t, water_left=w), 600.0, 0.05),
        "water_at_1.5kg": elastic(lambda w: area(ret_o2, ret_t, water_left=w), 1500.0, 0.05),
    }

    # ---------- 그림 ----------
    fig, axes = plt.subplots(1, 3, figsize=(17, 5), facecolor="#0b0f17")
    ax = axes[0]; style_ax(ax)
    for name, col in (("pandolf", "#e6e9ef"), ("suit90_A_all092", "#5cbcc3")):
        p = profiles[name]
        t_min = np.cumsum(p["dist"]) / 0.92 / 60
        ax.plot(t_min, p["hr"], color=col, lw=1, label=f"{name}")
    ax.axhline((HR_FIT_MAX_BTU_H - HR_A) / HR_B, color="#ff6b8a", ls=":", lw=1)
    ax.text(2, (HR_FIT_MAX_BTU_H - HR_A) / HR_B + 3, "edge of HR regression data", color="#ff6b8a", fontsize=7)
    ax.set_xlabel("minutes along landing -> sol 1282 (outbound)", color="#a7aec1", fontsize=8)
    ax.set_ylabel("HR implied by model metabolic rate (bpm)", color="#a7aec1", fontsize=8)
    ax.legend(fontsize=7, facecolor="#141a26", labelcolor="#e6e9ef")
    ax.set_title("Uphill raises HR because it raises metabolic rate", color="#e6e9ef", fontsize=9)

    ax = axes[1]; style_ax(ax)
    im = ax.imshow(grid, origin="lower", aspect="auto", cmap="viridis",
                   extent=[ks[0] - 0.025, ks[-1] + 0.025, -0.5, len(waters) - 0.5])
    ax.set_yticks(range(len(waters))); ax.set_yticklabels([f"{w/1000:.1f}" for w in waters])
    ax.set_xlabel("k (actual / model metabolic; what HR would reveal)", color="#a7aec1", fontsize=8)
    ax.set_ylabel("coolant left (kg)", color="#a7aec1", fontsize=8)
    ax.set_title("Walk-back area (km2), 150 g O2, leak 9.1 g/h", color="#e6e9ef", fontsize=9)
    fig.colorbar(im, ax=ax, fraction=0.04)

    ax = axes[2]; style_ax(ax)
    names = list(tornado)
    for i, n in enumerate(names):
        lo, hi = sorted(tornado[n])
        ax.barh(i, hi - lo, left=lo, color="#5cbcc3" if n.startswith("k") else "#e3a857" if "water" in n else "#9b8cff")
    ax.axvline(base, color="white", lw=0.8)
    ax.set_yticks(range(len(names))); ax.set_yticklabels(names, fontsize=7, color="#a7aec1")
    ax.set_xlabel("walk-back area (km2)", color="#a7aec1", fontsize=8)
    ax.set_title(f"Range of area for each factor (base {base:.2f} km2)", color="#e6e9ef", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "b_hr_water_sensitivity.png"), dpi=140,
                                    facecolor=fig.get_facecolor()); plt.close(fig)

    res = {"reserve_fixed444": dict(RES), "base_area_km2": base, "hr_profile_by_grade": hr_table,
           "hr_at_level_model_b": round(hr_level_b, 0), "level_w_model_b": round(m_b["level_w"], 0),
           "k_error_from_hr_measurement_1sigma": round(k_err_meas, 3),
           "water_threshold_g_where_water_binds_by_k": thresh,
           "tornado_km2": {k: [round(a, 2) for a in v] for k, v in tornado.items()},
           "elasticity_area_pct_per_input_pct": {k: (round(v, 2) if v is not None else None) for k, v in elast.items()},
           "grid": {"k": ks.tolist(), "water_g": waters.tolist(), "area_km2": np.round(grid, 3).tolist()}}
    with open(os.path.join(OUT, "b_hr_water_sensitivity.json"), "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in res.items() if k != "grid"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
