"""
태양입자사건(SPE) on/off에 따른 귀환 가능 반경 — 산소와 방사선 선량을 별도 예산으로 분리

mars_walkback.py의 귀환 반경은 산소(O2) 하나만 제약이었다. SPE가 오면 같은 길을 걸어도
선량이 몇 배로 늘어나므로, 선량을 0~1 위험도 지수에 섞지 않고 "귀환 중 누적 선량(mSv)"이라는
물리량으로 따로 계산해 두 번째 예산으로 둔다.

  귀환 가능(p) = [p->거점 경로의 산소 <= 남은 산소 - 예비분]  AND  [같은 경로의 선량 <= 선량 예산]
                AND [같은 경로의 냉각수 <= 남은 냉각수 - 예비분]   (냉각수 모델은 suit_cooling.py)

경로 선택: 간선 비용 = 산소/산소예산 + 선량/선량예산 (두 자원 중 "남은 몫을 덜 쓰는" 경로).
냉각수가 만충(3.6 kg)보다 적을 때만 + 냉각수/냉각수예산 항을 더한다. 만충이면 산소가 먼저 묶이므로
경로 선택을 바꾸지 않는다(냉각수 항을 넣으면 선량 항의 상대 비중이 줄어 SPE 결과가 조금 달라진다).
SPE off면 선량 항이 작아 사실상 산소 최적 경로와 같고, SPE가 커질수록 짧고 지형에 가려진
(차폐 proxy가 큰) 경로 쪽으로 기운다.

실측/문헌 기반 수치:
  - 배경 선량률 0.655 mSv/day — Curiosity RAD, 원문 0.64 ± 0.12 mSv/day(Hassler et al. 2014)의 오차 안.
  - SPE 관측 배율 x2.9 — 착륙 이후 최대였던 2017년 9월 사건의 GCR 배경 대비 2~3배(Zeitlin et al. 2018,
    GRL) 최고치 수준. 최고치는 몇 시간 지속이라 귀환 내내 적용하면 보수적이다. sol 242 사건(2013년 4월)은
    약 1.3배였다(Hassler 2014). human_mission_risk.py와 같은 값.

설계 가정(측정값 아님):
  - x10, x30 등 관측보다 큰 배율은 "가상 대형 SPE" 스트레스 테스트일 뿐이다. 화성 표면에서
    역사적 대형 사건(1972년 8월, 1989년 10월급)의 배율은 이 프로젝트에서 출처로 확인하지 못했다.
  - 선량 예산 DOSE_BUDGET_MSV = 1.0 mSv: 기존 모델의 "일일 경보 기준선"(D_BUDGET_MSV_DAY)을
    귀환 1회 선량 상한으로 그대로 사용. 공식 한도(SPE 사건당 250 mSv 등)의 환산치가 아니며,
    고장 전까지 이미 받은 선량은 무시한다.
  - 지형 차폐 proxy: human_mission_risk.shielding_factor_grid()를 10 m DTM에 그대로 적용
    (창 25칸 = 약 250 m — "주변보다 낮은 골짜기 바닥"). 최대 50% 감소. 실제 차폐는 머리 위
    암반이 있어야 하므로 근사치다.
  - 산소 기준 시나리오: 고장 시 남은 산소 150 g (mars_walkback의 중간 시나리오).

실행:
  python spe_walkback.py                      # 보고서용: 4개 시나리오 + 배율 스윕 전체
  python spe_walkback.py --spe off            # 상황 하나만: SPE 없음
  python spe_walkback.py --spe on             # SPE 있음(기본 배율 = 관측값 x2.9), off와 나란히 비교
  python spe_walkback.py --spe on --multiplier 10 --o2-left 200
  python spe_walkback.py --spe off --water-left 0.6          # 냉각수 0.6 kg 남음(누수 등)
  python spe_walkback.py --spe off --water-left 0.6 --heat-extra 100   # 환경·PLSS 열 +100 W 가정
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from metabolic_navigation import (
    metabolic_rate_w, o2_g_per_s, eta_from_rock, slope_deg_grid,
    G_RATIO_MARS, MAX_WALK_SLOPE_DEG, EVA_WALK_SPEED_M_S,
)
from human_mission_risk import (
    D_BACKGROUND_MSV_DAY, D_BUDGET_MSV_DAY, SPE_DOSE_MULTIPLIER, SHIELDING_MAX_REDUCTION,
    shielding_factor_grid,
)
from human_mission_navigation import style_ax, _marker
import metabolic_model as _mm  # 2026-11-10
from suit_cooling import (
    water_g_per_s, water_reserve_g, FEEDWATER_FULL_G, Q_EXTRA_W, HEAT_STORAGE_WATER_EQ_G,
)
from mars_walkback import (
    load_dtm_crop, load_traverse, lonlat_to_cell, hillshade, km_extent,
    OFFSETS, CELL_M, O2_RESERVE_G, OUT_DIR, offset_ok,
)

DOSE_BUDGET_MSV = D_BUDGET_MSV_DAY
REF_REMAINING_O2_G = 150
O2_BUDGET_G = REF_REMAINING_O2_G - O2_RESERVE_G

SCENARIOS = [
    ("SPE off", 1.0),
    (f"SPE observed x{SPE_DOSE_MULTIPLIER}", SPE_DOSE_MULTIPLIER),
    ("SPE x10 (hypothetical)", 10.0),
    ("SPE x30 (hypothetical)", 30.0),
]
SWEEP = [1, 2, 2.9, 5, 10, 15, 20, 22, 24, 26, 28, 30, 40, 50]


def dose_rate_msv_h(shielding, multiplier):
    return D_BACKGROUND_MSV_DAY / 24 * multiplier * (1 - SHIELDING_MAX_REDUCTION * shielding)


def edge_values(h, eta, rate, ys_a, xs_a, ys_b, xs_b, q_extra_w=Q_EXTRA_W):
    """a->b 이동 1회의 (산소 g, 선량 mSv, 냉각수 g). 배열 단위로 계산."""
    dist_m = np.hypot(xs_b - xs_a, ys_b - ys_a) * CELL_M
    grade = (h[ys_b, xs_b] - h[ys_a, xs_a]) / dist_m * 100
    e = 0.5 * (eta[ys_a, xs_a] + eta[ys_b, xs_b])
    mr, v = _mm.edge_rate(grade, e, G_RATIO_MARS)   # 2026-11-10: 경사별 속도
    t_s = dist_m / v
    o2 = o2_g_per_s(mr) * t_s
    dose = 0.5 * (rate[ys_a, xs_a] + rate[ys_b, xs_b]) * t_s / 3600
    water = water_g_per_s(mr, q_extra_w) * t_s
    return o2, dose, water


def build_graph(h, eta, rate, passable, o2_budget=O2_BUDGET_G, water_budget=None, q_extra_w=Q_EXTRA_W):
    """water_budget=None이면 냉각수를 경로 비용에 넣지 않는다."""
    rows, cols = h.shape
    yy, xx = np.mgrid[0:rows, 0:cols]
    src, dst, w = [], [], []
    for dx, dy in OFFSETS:
        a, b, ok = offset_ok(passable, dx, dy, h)   # 16방향 + 걸치는 칸 + 간선 경사 상한
        ya, xa, yb, xb = yy[a][ok], xx[a][ok], yy[b][ok], xx[b][ok]
        o2, dose, water = edge_values(h, eta, rate, ya, xa, yb, xb, q_extra_w)
        src.append(ya * cols + xa)
        dst.append(yb * cols + xb)
        cost = o2 / o2_budget + dose / DOSE_BUDGET_MSV
        if water_budget is not None:
            cost = cost + water / max(water_budget, 1.0)
        w.append(cost)
    n = rows * cols
    return csr_matrix((np.concatenate(w), (np.concatenate(src), np.concatenate(dst))), shape=(n, n))


def return_tree_totals(h, eta, rate, cost, pred, q_extra_w=Q_EXTRA_W):
    """귀환 경로 트리(각 칸 -> pred -> ... -> 거점)를 따라 산소·선량·냉각수를 누적한다.
    비용이 작은 칸부터 처리하면 pred가 항상 먼저 계산되어 있다."""
    rows, cols = h.shape
    n = rows * cols
    has = pred >= 0
    v = np.nonzero(has)[0]
    p = pred[v]
    o2_e, dose_e, water_e = edge_values(h, eta, rate, v // cols, v % cols, p // cols, p % cols, q_extra_w)
    edge_o2 = np.zeros(n); edge_o2[v] = o2_e
    edge_dose = np.zeros(n); edge_dose[v] = dose_e
    edge_water = np.zeros(n); edge_water[v] = water_e
    o2 = np.full(n, np.nan); dose = np.full(n, np.nan); water = np.full(n, np.nan)
    order = np.argsort(cost)
    order = order[np.isfinite(cost[order])]
    o2[order[0]] = dose[order[0]] = water[order[0]] = 0.0  # 거점
    for node in order[1:]:
        q = pred[node]
        o2[node] = o2[q] + edge_o2[node]
        dose[node] = dose[q] + edge_dose[node]
        water[node] = water[q] + edge_water[node]
    return o2.reshape(h.shape), dose.reshape(h.shape), water.reshape(h.shape)


def run_scenario(h, eta, shielding, passable, base_idx, multiplier, o2_budget=O2_BUDGET_G,
                 water_left_g=FEEDWATER_FULL_G, q_extra_w=Q_EXTRA_W):
    rate = dose_rate_msv_h(shielding, multiplier)
    water_budget = water_left_g - water_reserve_g(q_extra_w)
    graph = build_graph(h, eta, rate, passable, o2_budget,
                        water_budget if water_left_g < FEEDWATER_FULL_G else None, q_extra_w)
    cost, pred = dijkstra(graph.T.tocsr(), directed=True, indices=base_idx, return_predecessors=True)
    o2, dose, water = return_tree_totals(h, eta, rate, cost, pred, q_extra_w)
    ok_o2 = o2 <= o2_budget
    ok_dose = dose <= DOSE_BUDGET_MSV
    ok_water = water <= water_budget
    # 냉각수가 길 위에서 바닥나고, 남은 길의 대사열을 몸에 쌓아(비상 한계 CDO 이내) 겨우 돌아오는 칸.
    # 예비분을 헐어 쓰는 칸(water_budget < water <= water_left_g)은 여기에 넣지 않는다.
    water_contingency = ok_o2 & ok_dose & (water > water_left_g) & (water <= water_left_g + HEAT_STORAGE_WATER_EQ_G)
    cell_km2 = (CELL_M / 1000) ** 2
    return {
        "o2": o2, "dose": dose, "water": water, "ok_o2": ok_o2, "ok_dose": ok_dose, "ok_water": ok_water,
        "safe": ok_o2 & ok_dose & ok_water, "water_contingency": water_contingency,
        "area_o2_only_km2": float(ok_o2.sum() * cell_km2),
        "area_safe_km2": float((ok_o2 & ok_dose & ok_water).sum() * cell_km2),
        "area_dose_limited_km2": float((ok_o2 & ~ok_dose).sum() * cell_km2),
        "area_water_limited_km2": float((ok_o2 & ok_dose & ~ok_water).sum() * cell_km2),
        "area_water_contingency_km2": float(water_contingency.sum() * cell_km2),
        "max_dose_in_o2_area_msv": float(np.nanmax(np.where(ok_o2, dose, np.nan))),
    }


def plot_scenarios(h, valid, results, traverse_xy, base, remaining_o2_g=REF_REMAINING_O2_G,
                   fname=f"{OUT_DIR}/spe_walkback_scenarios.png"):
    fig, axes = plt.subplots(1, len(results), figsize=(4.3 * len(results), 6.4), facecolor="#0b0e15", squeeze=False)
    ext = km_extent(h.shape)
    k = CELL_M / 1000
    shade = np.where(valid, hillshade(h), np.nan)
    for ax, (name, r) in zip(axes[0], results):
        style_ax(ax)
        ax.imshow(shade, cmap="gray", extent=ext, vmin=0, vmax=1)
        ok_o2 = r["ok_o2"]
        ax.imshow(np.where(r["safe"], 1.0, np.nan), cmap="winter", vmin=0, vmax=1.6, extent=ext, alpha=0.45)
        ax.imshow(np.where(ok_o2 & ~r["ok_dose"], 1.0, np.nan), cmap="autumn", vmin=0, vmax=1, extent=ext, alpha=0.65)
        ax.imshow(np.where(ok_o2 & r["ok_dose"] & ~r["ok_water"], 1.0, np.nan), cmap="cool", vmin=0, vmax=1,
                  extent=ext, alpha=0.65)
        for x, y in traverse_xy:
            ax.plot(x * k, y * k, color="#e9ebf2", lw=0.5, alpha=0.6)
        _marker(ax, (base[0] * k, base[1] * k), "#a7e8a0", marker="*", size=160)
        ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
        water_note = f", water-cut {r['area_water_limited_km2']:.1f}" if r["area_water_limited_km2"] > 0 else ""
        ax.set_title(f"{name}\nsafe {r['area_safe_km2']:.1f} km2, dose-cut {r['area_dose_limited_km2']:.1f} km2"
                     f"{water_note}\n"
                     f"max return dose {r['max_dose_in_o2_area_msv']:.2f} mSv", color="#e9ebf2", fontsize=8.5)
    fig.suptitle(f"Walk-back area with {remaining_o2_g:g} g O2 left -- blue = can return (O2, dose, water OK), "
                 f"yellow = O2 OK but return dose > {DOSE_BUDGET_MSV:.1f} mSv, pink = coolant water runs short",
                 color="#e9ebf2", fontsize=9.5)
    fig.tight_layout()
    fig.savefig(fname, dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"saved {fname}")


def plot_dose_maps(h, valid, results, base):
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 6.4), facecolor="#0b0e15")
    ext = km_extent(h.shape)
    k = CELL_M / 1000
    for ax, (name, r) in zip(axes, results):
        style_ax(ax)
        im = ax.imshow(np.where(valid, r["dose"], np.nan), cmap="inferno", extent=ext,
                       vmin=0, vmax=max(np.nanpercentile(r["dose"], 99), 1e-3))
        _marker(ax, (base[0] * k, base[1] * k), "#a7e8a0", marker="*", size=160)
        ax.set_title(f"return-trip dose (mSv) -- {name}", color="#e9ebf2", fontsize=9)
        cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
        cb.ax.tick_params(colors="#a7aec1", labelsize=7)
    fig.tight_layout()
    fname = f"{OUT_DIR}/spe_return_dose.png"
    fig.savefig(fname, dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"saved {fname}")


def plot_sweep(sweep_rows, breakeven):
    fig, ax = plt.subplots(figsize=(7.6, 4.2), facecolor="#0b0e15")
    style_ax(ax)
    m = [r["multiplier"] for r in sweep_rows]
    ax.plot(m, [r["area_o2_only_km2"] for r in sweep_rows], "--", color="#a7aec1", label="O2 limit only")
    ax.plot(m, [r["area_safe_km2"] for r in sweep_rows], "o-", color="#5cbcc3", label="O2 + dose limits")
    ax.axvspan(2, 3, color="#e0ac53", alpha=0.2, label="observed on Mars surface (x2-3)")
    if breakeven:
        ax.axvline(breakeven, color="#e05a4f", lw=1, ls=":")
        ax.text(breakeven, ax.get_ylim()[0] + 1, f"  dose starts to bind ~x{breakeven:g}", color="#e05a4f", fontsize=8)
    ax.set_xscale("log")
    ax.set_xlabel("SPE dose-rate multiplier vs background (log)", color="#a7aec1", fontsize=8)
    ax.set_ylabel("walk-back area (km2)", color="#a7aec1", fontsize=8)
    ax.set_title(f"How big must an SPE be before dose, not O2, limits the walk back? ({REF_REMAINING_O2_G} g O2 left)",
                 color="#e9ebf2", fontsize=9)
    ax.legend(facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2", fontsize=7.5)
    fig.tight_layout()
    fname = f"{OUT_DIR}/spe_multiplier_sweep.png"
    fig.savefig(fname, dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"saved {fname}")


def load_scene():
    h, valid, rough_r, _ = load_dtm_crop()
    slope = slope_deg_grid(h, CELL_M)
    passable = valid & (slope <= MAX_WALK_SLOPE_DEG)
    eta = eta_from_rock(rough_r)
    shielding = np.where(valid, shielding_factor_grid(h), 0.0)
    wps, traverse_xy = load_traverse(h.shape)
    bx, by = (int(round(v)) for v in lonlat_to_cell(wps[0]["lon"], wps[0]["lat"]))
    return h, valid, eta, shielding, passable, traverse_xy, (bx, by)


def run_situation(spe_on, multiplier, remaining_o2_g, water_left_g=FEEDWATER_FULL_G, q_extra_w=Q_EXTRA_W):
    """SPE 상황 하나를 on/off로 지정해 귀환 가능 영역을 계산한다.
    on이면 같은 조건의 off도 계산해 나란히 그리고, SPE 때문에 줄어든 면적을 보고한다.
    냉각수 잔량·환경 열(q_extra_w)은 두 그림에 똑같이 적용한다."""
    h, valid, eta, shielding, passable, traverse_xy, base = load_scene()
    base_idx = base[1] * h.shape[1] + base[0]
    o2_budget = remaining_o2_g - O2_RESERVE_G
    mult = multiplier if spe_on else 1.0
    if spe_on and mult <= 1.0:
        raise SystemExit("--spe on 이면 --multiplier 는 1보다 커야 합니다")
    label = "SPE on (observed)" if mult == SPE_DOSE_MULTIPLIER else \
        f"SPE on (hypothetical x{mult:g})" if spe_on else "SPE off"
    print(f"상황: {label}, 배율 x{mult:g}, 남은 산소 {remaining_o2_g:g} g "
          f"(예비 {O2_RESERVE_G:.0f} g 제외 {o2_budget:.0f} g), 선량 예산 {DOSE_BUDGET_MSV} mSv")
    print(f"  냉각수 {water_left_g:g} g (예비 {water_reserve_g(q_extra_w):.0f} g 제외 "
          f"{water_left_g - water_reserve_g(q_extra_w):.0f} g), 환경·PLSS 열 {q_extra_w:+g} W")

    off = run_scenario(h, eta, shielding, passable, base_idx, 1.0, o2_budget, water_left_g, q_extra_w)
    results = [("SPE off", off)]
    if spe_on:
        results.append((f"{label} x{mult:g}",
                        run_scenario(h, eta, shielding, passable, base_idx, mult, o2_budget, water_left_g, q_extra_w)))
    cur = results[-1][1]
    print(f"  귀환 가능 {cur['area_safe_km2']:.2f} km2 (산소만 보면 {cur['area_o2_only_km2']:.2f}), "
          f"선량 때문에 잘린 면적 {cur['area_dose_limited_km2']:.2f} km2, "
          f"최대 귀환선량 {cur['max_dose_in_o2_area_msv']:.3f} mSv")
    print(f"  냉각수 때문에 잘린 면적 {cur['area_water_limited_km2']:.2f} km2 "
          f"(그중 체온 비상한계까지 쓰면 돌아오는 칸 {cur['area_water_contingency_km2']:.2f} km2)")
    if spe_on:
        lost = off["safe"] & ~cur["safe"]
        print(f"  SPE off 대비 귀환 불가로 바뀐 면적 {lost.sum() * (CELL_M / 1000) ** 2:.2f} km2")

    tag = f"spe_on_x{mult:g}" if spe_on else "spe_off"
    tag += f"_o2_{remaining_o2_g:g}g"
    if water_left_g != FEEDWATER_FULL_G or q_extra_w != Q_EXTRA_W:
        tag += f"_water_{water_left_g:g}g_q{q_extra_w:+g}W"
    plot_scenarios(h, valid, results, traverse_xy, base, remaining_o2_g, f"{OUT_DIR}/situation_{tag}.png")
    stats = {"spe_on": spe_on, "multiplier": mult, "multiplier_basis": "observed peak level (Zeitlin 2018, Sept 2017 SPE, 2-3x)"
             if mult == SPE_DOSE_MULTIPLIER else ("background" if not spe_on else "hypothetical"),
             "remaining_o2_g": remaining_o2_g, "o2_budget_g": o2_budget, "dose_budget_msv": DOSE_BUDGET_MSV,
             "remaining_water_g": water_left_g, "water_reserve_g": water_reserve_g(q_extra_w), "q_extra_w": q_extra_w,
             **{k: v for k, v in cur.items() if k.endswith(("km2", "msv"))}}
    if spe_on:
        stats["area_lost_vs_off_km2"] = float(lost.sum() * (CELL_M / 1000) ** 2)
    with open(f"{OUT_DIR}/situation_{tag}.json", "w") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    print(f"saved {OUT_DIR}/situation_{tag}.json")
    return stats


def main():
    h, valid, eta, shielding, passable, traverse_xy, (bx, by) = load_scene()
    base_idx = by * h.shape[1] + bx

    print(f"산소 예산 {O2_BUDGET_G:.0f} g (남은 {REF_REMAINING_O2_G} g - 예비 {O2_RESERVE_G:.0f} g), "
          f"선량 예산 {DOSE_BUDGET_MSV} mSv, 배경 선량률 {D_BACKGROUND_MSV_DAY/24*1000:.1f} uSv/h")

    results = []
    for name, mult in SCENARIOS:
        r = run_scenario(h, eta, shielding, passable, base_idx, mult)
        results.append((name, r))
        print(f"  {name:<24} 안전 {r['area_safe_km2']:5.2f} km2 (산소만 {r['area_o2_only_km2']:5.2f}), "
              f"선량 때문에 잘린 면적 {r['area_dose_limited_km2']:5.2f} km2, 산소권 내 최대 귀환선량 "
              f"{r['max_dose_in_o2_area_msv']:.3f} mSv")

    sweep_rows = []
    for mult in SWEEP:
        r = run_scenario(h, eta, shielding, passable, base_idx, mult)
        sweep_rows.append({"multiplier": mult, **{k: v for k, v in r.items() if k.endswith(("km2", "msv"))}})
    # "선량이 묶기 시작" = 산소로는 돌아올 수 있는데 선량 때문에 못 돌아오는 칸이 처음 생기는 배율.
    # (산소권 면적 자체도 배율이 커지면 조금 줄어든다 — 경로가 선량을 피해 돌아가며 산소를 더 쓰기 때문)
    breakeven = next((r["multiplier"] for r in sweep_rows if r["area_dose_limited_km2"] > 0), None)
    print(f"선량이 귀환 반경을 줄이기 시작하는 SPE 배율: ~x{breakeven}")

    plot_scenarios(h, valid, results, traverse_xy, (bx, by))
    plot_dose_maps(h, valid, [results[0], results[-1]], (bx, by))
    plot_sweep(sweep_rows, breakeven)

    stats = {
        "assumptions": {"O2_BUDGET_G": O2_BUDGET_G, "REF_REMAINING_O2_G": REF_REMAINING_O2_G,
                        "DOSE_BUDGET_MSV": DOSE_BUDGET_MSV, "D_BACKGROUND_MSV_DAY": D_BACKGROUND_MSV_DAY,
                        "SHIELDING_MAX_REDUCTION": SHIELDING_MAX_REDUCTION,
                        "route_cost": "O2/O2_BUDGET + dose/DOSE_BUDGET"},
        "scenarios": [{"name": n, "multiplier": m, **{k: v for k, v in r.items() if k.endswith(("km2", "msv"))}}
                      for (n, m), (_, r) in zip(SCENARIOS, results)],
        "sweep": sweep_rows,
        "breakeven_multiplier": breakeven,
    }
    with open(f"{OUT_DIR}/spe_walkback_stats.json", "w") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    print(f"saved {OUT_DIR}/spe_walkback_stats.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="SPE on/off 귀환 가능 반경")
    ap.add_argument("--spe", choices=["on", "off"], help="상황 하나만 계산 (생략하면 보고서용 전체 실행)")
    ap.add_argument("--multiplier", type=float, default=SPE_DOSE_MULTIPLIER,
                    help=f"SPE on일 때 배경 대비 선량률 배율 (기본 관측값 x{SPE_DOSE_MULTIPLIER})")
    ap.add_argument("--o2-left", type=float, default=REF_REMAINING_O2_G, help="고장 시 남은 산소 g")
    ap.add_argument("--water-left", type=float, default=FEEDWATER_FULL_G / 1000,
                    help=f"남은 냉각수 kg (기본 만충 {FEEDWATER_FULL_G / 1000:g} kg)")
    ap.add_argument("--heat-extra", type=float, default=Q_EXTRA_W,
                    help="PLSS 발열 + 환경 열 유입(+)/유출(-) W, 미측정 가정 (기본 0)")
    args = ap.parse_args()
    if args.spe:
        run_situation(args.spe == "on", args.multiplier, args.o2_left, args.water_left * 1000, args.heat_extra)
    else:
        main()
