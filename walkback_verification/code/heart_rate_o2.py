"""
심박수 -> 대사량 -> 산소: 실시간 심박으로 귀환 가능 반경을 보정한다

mars_walkback.py의 귀환 산소는 Pandolf 식(체중·짐·경사·지형)으로 "평균적인 사람"의 대사량을
예측한 값이다. 실제 EVA에서는 같은 길을 걸어도 사람·컨디션·긴장도에 따라 대사량이 다르다.
우주복은 심박(ECG)을 실시간으로 보내므로, 심박으로 "지금 이 사람이 모델보다 몇 배 쓰고 있는가"
(보정계수 k)를 추정하고, 귀환 산소 비용에 k를 곱해 귀환 가능 반경을 갱신한다.

  k = (지난 10분 심박에서 환산한 대사량) / (같은 구간에서 Pandolf가 예측한 대사량)
  보정된 귀환 가능 = k x 귀환 산소(p) <= 남은 산소 - 예비분

문헌 수치 (Hoffmann 2021, NASA NTRS 20210024317, Ch.5 Table 5.1, p.8):
  - 셔틀·ISS EVA 132회(2006~2015), 대사량은 PLSS 산소탱크 압력 감소로 2분마다, 심박은 ECG로 20초마다.
  - 전체 단순회귀: MR(BTU/hr) = 284.55 + 5.984 x HR(bpm)   (SE 10.94 / 0.111, R^2 = 0.402)
  - 개인별 회귀: R^2 > 0.82, 예측 RMSE 89.66 +/- 44.24 BTU/hr. 대사량->심박 예측 RMSE < 10 bpm.
  - EVA 전체 평균: HR 103 +/- 17 bpm, MR 862.9 +/- 125 BTU/hr, MR/HR 0.142 BTU/beat.
  - Apollo도 사람별로 비행 전에 심박-대사량 관계를 보정해 썼다(Waligora et al., NASA TN D-7883).

한계 (원문과 이 코드의 가정):
  - 회귀는 무중력 EVA(손 작업 위주) 데이터다. 화성 0.38 g 보행에서 같은 관계가 성립하는지는 검증되지
    않았다. 원문도 무중력에서 체액 이동 때문에 심박 반응이 다를 수 있다고 논의한다.
  - 전체 회귀 R^2 0.40 -> 사람별 보정 없이 쓰면 오차가 크다. 실제 운용은 개인 회귀(R^2 > 0.82)를 전제한다.
  - k를 귀환 경로 전체에 그대로 곱하는 것은 "지금의 효율이 돌아가는 동안에도 유지된다"는 가정이다.
  - 심박 시계열은 실제 데이터가 없어 합성했다(아래 SYNTH_*). 결과는 방법 시연이지 측정값이 아니다.
"""
from __future__ import annotations

import json
import os

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.sparse.csgraph import dijkstra

from metabolic_navigation import (
    metabolic_rate_w, o2_g_per_s, eta_from_rock, slope_deg_grid,
    G_RATIO_MARS, MAX_WALK_SLOPE_DEG, EVA_WALK_SPEED_M_S,
)
from human_mission_navigation import style_ax, _marker
import metabolic_model as _mm
from mars_walkback import (
    load_dtm_crop, load_traverse, lonlat_to_cell, build_o2_graph, trace, hillshade, km_extent, _wp_lonlat,
    CELL_M, O2_RESERVE_G, LEVEL_O2_G_PER_H,
)

OUT_DIR = "../outputs/heart_rate_o2"
os.makedirs(OUT_DIR, exist_ok=True)

BTU_H_TO_W = 0.29307107
HR_MR_INTERCEPT_BTU_H = 284.55     # Hoffmann 2021 Table 5.1
HR_MR_SLOPE_BTU_H_PER_BPM = 5.984  # Hoffmann 2021 Table 5.1
HR_PRED_RMSE_BPM = 10.0            # 원문: 대사량으로 심박 예측 시 RMSE < 10 bpm (개인 회귀)
# 2026-11-12 (PLAN_D 3번): 원문 대사량 구간의 마지막 경계 1200 BTU/hr(최상위 구간은 ">1200"으로 위가 열려 있음)를
# 회귀 적용 상한으로 쓴다. 이전 값 1400은 근거 없는 가정이었다.
FIT_MAX_MR_W = 1200 * BTU_H_TO_W
VALID_SHARE_MIN = 0.5               # 경로의 절반 넘게 상한 밖이면 심박 환산을 '유효하지 않음'으로 표시
REF_REMAINING_O2_G = 150
GOAL_SOL = 1282
K_GRID = np.round(np.arange(0.8, 1.61, 0.05), 2)
K_MAP = [1.0, 1.2, 1.4]
K_WINDOW_MIN = 10

# 합성 심박 시나리오 (설계 가정 — 실측 아님)
SYNTH_K_TRUE = [(0, 1.0), (60, 1.25)]   # 60분부터 모델보다 25% 더 씀(더위·긴장·피로 가정)
SYNTH_NOISE_BPM = 8.0
SYNTH_SEED = 7


def hr_to_metabolic_w(hr_bpm):
    return (HR_MR_INTERCEPT_BTU_H + HR_MR_SLOPE_BTU_H_PER_BPM * np.asarray(hr_bpm, float)) * BTU_H_TO_W


def metabolic_w_to_hr(mr_w):
    return (np.asarray(mr_w, float) / BTU_H_TO_W - HR_MR_INTERCEPT_BTU_H) / HR_MR_SLOPE_BTU_H_PER_BPM


def hr_to_o2_g_per_h(hr_bpm):
    return o2_g_per_s(hr_to_metabolic_w(hr_bpm)) * 3600


# ============================================================
# 1. 경로 위 예측 대사량 -> 예상 심박
# ============================================================

def hr_valid(profile) -> bool:
    """경로 시간의 절반 넘게 회귀 상한 밖이면 심박 환산을 유효하지 않다고 본다."""
    return float(np.mean(profile["beyond_fit"])) <= VALID_SHARE_MIN


def route_profile(h, eta, route):
    """경로를 1분 단위로 다시 나눠 (시간, 거리, 고도, 대사량 W, 예상 심박, 누적 산소)를 낸다."""
    xs = np.array([p[0] for p in route]); ys = np.array([p[1] for p in route])
    d = np.hypot(np.diff(xs), np.diff(ys)) * CELL_M
    grade = (h[ys[1:], xs[1:]] - h[ys[:-1], xs[:-1]]) / d * 100
    e = 0.5 * (eta[ys[1:], xs[1:]] + eta[ys[:-1], xs[:-1]])
    mr, v = _mm.edge_rate(grade, e, G_RATIO_MARS)   # 2026-11-10: 경사별 속도
    t_end = np.cumsum(d / v)
    # 1초 간격으로 펼친 뒤 1분 평균 — 10 m 칸 하나의 급경사가 1분 전체 값이 되지 않게
    t_s = np.arange(0, t_end[-1], 1.0)
    seg_s = np.minimum(np.searchsorted(t_end, t_s, side="right"), len(d) - 1)
    n_min = int(np.ceil(len(t_s) / 60))
    minute = (np.arange(len(t_s)) // 60)
    mr_min = np.bincount(minute, weights=mr[seg_s], minlength=n_min) / np.bincount(minute, minlength=n_min)
    seg = seg_s[::60]
    o2_cum = np.cumsum(o2_g_per_s(mr_min) * np.bincount(minute, minlength=n_min))
    return {"t_min": np.arange(n_min, dtype=float), "dist_km": np.concatenate([[0], np.cumsum(d)])[seg] / 1000,
            "elev_m": h[ys[seg], xs[seg]], "mr_w": mr_min, "hr_bpm": metabolic_w_to_hr(mr_min),
            "beyond_fit": mr_min > FIT_MAX_MR_W, "o2_cum_g": o2_cum, "o2_total_g": float(o2_cum[-1])}


# ============================================================
# 2. 합성 심박으로 k 추정 시연
# ============================================================

def k_true_at(t):
    k = SYNTH_K_TRUE[0][1]
    for t0, kk in SYNTH_K_TRUE:
        if t >= t0:
            k = kk
    return k


def simulate_k(profile):
    rng = np.random.default_rng(SYNTH_SEED)
    t = profile["t_min"]
    k_true = np.array([k_true_at(x) for x in t])
    hr_meas = metabolic_w_to_hr(profile["mr_w"] * k_true) + rng.normal(0, SYNTH_NOISE_BPM, len(t))
    mr_from_hr = hr_to_metabolic_w(hr_meas)
    k_est = np.full(len(t), np.nan)
    for i in range(K_WINDOW_MIN - 1, len(t)):
        sl = slice(i - K_WINDOW_MIN + 1, i + 1)
        k_est[i] = mr_from_hr[sl].sum() / profile["mr_w"][sl].sum()
    return {"k_true": k_true, "hr_meas": hr_meas, "k_est": k_est,
            "o2_cum_hr_g": np.cumsum(o2_g_per_s(mr_from_hr) * 60)}


# ============================================================
# 3. 그림
# ============================================================

def plot_conversion(path):
    fig, ax = plt.subplots(figsize=(7.4, 4.4), facecolor="#0b0e15")
    style_ax(ax)
    hr = np.linspace(70, 170, 101)
    ax.plot(hr, hr_to_o2_g_per_h(hr), color="#5cbcc3", lw=2, label="Hoffmann 2021 group fit (R2 0.40)")
    band = HR_MR_SLOPE_BTU_H_PER_BPM * HR_PRED_RMSE_BPM * BTU_H_TO_W
    ax.fill_between(hr, o2_g_per_s(hr_to_metabolic_w(hr) - band) * 3600, o2_g_per_s(hr_to_metabolic_w(hr) + band) * 3600,
                    color="#5cbcc3", alpha=0.15, label="+/- 10 bpm (individual-fit error)")
    for label, w, c, y, ha in [("Mars level walk\n(Pandolf, this model)", metabolic_rate_w(0.0, 1.0, G_RATIO_MARS), "#e0ac53", 50, "right"),
                               ("Apollo plan\n1200 BTU/hr", 1200 * BTU_H_TO_W, "#b48ef0", 50, "left")]:
        hr_x = float(metabolic_w_to_hr(w))
        ax.axvline(hr_x, color=c, ls="--", lw=1)
        ax.text(hr_x + (1 if ha == "left" else -1), y, f"{label}\n{w:.0f} W -> {hr_x:.0f} bpm", color=c, fontsize=7.5, ha=ha)
    ax.axvspan(103 - 17, 103 + 17, color="#a7aec1", alpha=0.08, label="Shuttle/ISS EVA HR 103 +/- 17")
    ax.set_xlabel("heart rate (bpm)", color="#a7aec1", fontsize=8)
    ax.set_ylabel("O2 consumption (g/h)", color="#a7aec1", fontsize=8)
    ax.set_title("Heart rate -> metabolic rate -> O2 (20.1 kJ/L, 1.429 g/L)", color="#e9ebf2", fontsize=9.5)
    ax.legend(facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2", fontsize=7.5, loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"saved {path}")


def plot_route_and_k(out_p, back_p, sim, path):
    fig, axes = plt.subplots(3, 1, figsize=(10.4, 9.0), facecolor="#0b0e15", sharex=False)
    ax = axes[0]
    style_ax(ax)
    for p, c, lab in [(out_p, "#5cbcc3", "out (base -> site)"), (back_p, "#e0ac53", "back (site -> base)")]:
        ax.plot(p["t_min"], p["hr_bpm"], color=c, lw=1.4,
                label=f"{lab}: O2 {p['o2_total_g']:.0f} g, {p['beyond_fit'].sum()} min beyond fit range")
        ax.fill_between(p["t_min"], p["hr_bpm"] - HR_PRED_RMSE_BPM, p["hr_bpm"] + HR_PRED_RMSE_BPM, color=c, alpha=0.12)
    hr_fit_max = float(metabolic_w_to_hr(FIT_MAX_MR_W))
    ax.set_ylim(100, 240)
    ax.axhspan(hr_fit_max, 240, color="#e05a4f", alpha=0.08)
    ax.text(0, hr_fit_max + 1, f" above 1200 BTU/hr ({hr_fit_max:.0f} bpm): beyond Hoffmann 2021 data bins, extrapolated",
            color="#e05a4f", fontsize=7.5, va="bottom")
    ax.set_ylabel("expected HR (bpm)", color="#a7aec1", fontsize=8)
    title = "Expected heart rate along the O2-optimal route (model MR -> inverse of HR fit)"
    if not hr_valid(out_p):
        title += "\nHR conversion NOT valid for this metabolic model (beyond Hoffmann 2021 data)"
    ax.set_title(title, color="#e05a4f" if not hr_valid(out_p) else "#e9ebf2", fontsize=9.5)
    ax.legend(facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2", fontsize=7.5)
    ax2 = ax.twinx()
    ax2.plot(out_p["t_min"], out_p["elev_m"], color="#a7aec1", lw=0.8, alpha=0.5)
    ax2.set_ylabel("elevation on outbound (m)", color="#a7aec1", fontsize=7)
    ax2.tick_params(colors="#a7aec1", labelsize=7)

    ax = axes[1]
    style_ax(ax)
    ax.plot(out_p["t_min"], out_p["hr_bpm"], color="#5cbcc3", lw=1.2, label="expected HR (model, k = 1)")
    ax.scatter(out_p["t_min"], sim["hr_meas"], s=6, color="#e9ebf2", label="measured HR (SYNTHETIC: k = 1.25 after 60 min, noise 8 bpm)")
    ax.set_ylim(100, 240)   # 그 위는 회귀 외삽 구간이라 잘라서 보여 준다(k 계산에는 전부 사용)
    ax.set_ylabel("HR (bpm)", color="#a7aec1", fontsize=8)
    ax.legend(facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2", fontsize=7.5)

    ax = axes[2]
    style_ax(ax)
    ax.plot(out_p["t_min"], sim["k_true"], color="#a7aec1", ls="--", lw=1, label="true k (synthetic)")
    ax.plot(out_p["t_min"], sim["k_est"], color="#e05a4f", lw=1.6, label=f"k estimated from HR ({K_WINDOW_MIN}-min window)")
    if not hr_valid(out_p):
        ax.set_title("method demo only: synthetic HR, and the HR fit is extrapolated for this model", color="#e05a4f", fontsize=8.5)
    ax.set_xlabel("minutes on outbound walk", color="#a7aec1", fontsize=8)
    ax.set_ylabel("k = MR from HR / model MR", color="#a7aec1", fontsize=8)
    ax.legend(facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2", fontsize=7.5)
    fig.tight_layout()
    fig.savefig(path, dpi=125, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"saved {path}")


def plot_k_walkback(h, valid, ret_o2, base, traverse_xy, area_rows, path):
    fig, axes = plt.subplots(1, 2, figsize=(13.2, 7.6), facecolor="#0b0e15", gridspec_kw={"width_ratios": [1.1, 1]})
    ext = km_extent(h.shape)
    k = CELL_M / 1000
    budget = REF_REMAINING_O2_G - O2_RESERVE_G
    ax = axes[0]
    style_ax(ax)
    ax.imshow(np.where(valid, hillshade(h), np.nan), cmap="gray", extent=ext, vmin=0, vmax=1)
    field = np.where(np.isfinite(ret_o2), ret_o2, np.nan)
    handles = []
    for kk, c in zip(K_MAP, ["#5cbcc3", "#e0ac53", "#e05a4f"]):
        ax.contour(np.arange(h.shape[1]) * k, np.arange(h.shape[0]) * k, field * kk, levels=[budget], colors=c, linewidths=1.8)
        a = next(r["area_km2"] for r in area_rows if abs(r["k"] - kk) < 1e-9)
        handles.append(plt.Line2D([], [], color=c, lw=1.8, label=f"k = {kk:.1f}: {a:.1f} km2"))
    for x, y in traverse_xy:
        ax.plot(x * k, y * k, color="#e9ebf2", lw=0.5, alpha=0.5)
    _marker(ax, (base[0] * k, base[1] * k), "#a7e8a0", marker="*", size=200)
    ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
    ax.legend(handles=handles, facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2", fontsize=8, loc="lower left")
    ax.set_title(f"Walk-back boundary with {REF_REMAINING_O2_G} g O2 left, return cost scaled by HR factor k",
                 color="#e9ebf2", fontsize=9)

    ax = axes[1]
    style_ax(ax)
    ks = [r["k"] for r in area_rows]
    ax.plot(ks, [r["area_km2"] for r in area_rows], "o-", color="#5cbcc3")
    ax.axvline(1.0, color="#a7aec1", ls=":", lw=1)
    ax.set_xlabel("k (actual / model metabolic rate)", color="#a7aec1", fontsize=8)
    ax.set_ylabel("walk-back area (km2)", color="#a7aec1", fontsize=8)
    ax.set_title("Same O2 left, different body: area vs k", color="#e9ebf2", fontsize=9.5)
    fig.tight_layout()
    fig.savefig(path, dpi=125, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"saved {path}")


# ============================================================
# 4. 실행
# ============================================================

def main():
    h, valid, rough_r, _ = load_dtm_crop()
    slope = slope_deg_grid(h, CELL_M)
    passable = valid & (slope <= MAX_WALK_SLOPE_DEG)
    eta = eta_from_rock(rough_r)
    wps, traverse_xy = load_traverse(h.shape)
    bx, by = (int(round(v)) for v in lonlat_to_cell(wps[0]["lon"], wps[0]["lat"]))
    base_idx = by * h.shape[1] + bx
    cell_km2 = (CELL_M / 1000) ** 2

    lvl_w = float(metabolic_rate_w(0.0, 1.0, G_RATIO_MARS))
    print(f"회귀식 MR = {HR_MR_INTERCEPT_BTU_H} + {HR_MR_SLOPE_BTU_H_PER_BPM} x HR (BTU/hr)")
    print(f"  화성 평지 보행 {lvl_w:.0f} W ({LEVEL_O2_G_PER_H:.0f} g/h) <-> 예상 심박 {float(metabolic_w_to_hr(lvl_w)):.0f} bpm")
    print(f"  Shuttle/ISS EVA 평균 심박 103 bpm -> {float(hr_to_metabolic_w(103)):.0f} W, 산소 {float(hr_to_o2_g_per_h(103)):.0f} g/h")

    graph = build_o2_graph(h, eta, passable)
    _, out_pred = dijkstra(graph, directed=True, indices=base_idx, return_predecessors=True)
    ret_o2, ret_pred = dijkstra(graph.T.tocsr(), directed=True, indices=base_idx, return_predecessors=True)
    ret_o2 = ret_o2.reshape(h.shape)
    gx, gy = (int(round(v)) for v in lonlat_to_cell(*_wp_lonlat(wps, GOAL_SOL)))
    goal = gy * h.shape[1] + gx
    out_route = trace(out_pred, goal, h.shape)
    back_route = trace(ret_pred, goal, h.shape)[::-1]

    out_p = route_profile(h, eta, out_route)
    back_p = route_profile(h, eta, back_route)
    print(f"\n착륙지 -> sol {GOAL_SOL}: 예상 심박 평균 {out_p['hr_bpm'].mean():.0f}, 최고 {out_p['hr_bpm'].max():.0f} bpm "
          f"(산소 {out_p['o2_total_g']:.0f} g) / 귀환 평균 {back_p['hr_bpm'].mean():.0f}, 최고 {back_p['hr_bpm'].max():.0f} bpm "
          f"(산소 {back_p['o2_total_g']:.0f} g)")
    print(f"  회귀 데이터 범위(1200 BTU/hr = {FIT_MAX_MR_W:.0f} W) 밖인 시간: 갈 때 {out_p['beyond_fit'].sum()}분 / "
          f"{len(out_p['t_min'])}분, 올 때 {back_p['beyond_fit'].sum()}분 / {len(back_p['t_min'])}분")
    if not (hr_valid(out_p) and hr_valid(back_p)):
        print("  [경고] 이 대사 모델의 보행 대사량은 Hoffmann 2021 심박 회귀의 자료 범위(> 1200 BTU/hr 구간 위)를 넘는다. "
              "위 심박 값은 외삽이며 유효하지 않다. 심박으로 k를 잡으려면 화성 보행 조건의 개인별 보정이 필요하다.")

    sim = simulate_k(out_p)
    after = out_p["t_min"] >= SYNTH_K_TRUE[-1][0] + K_WINDOW_MIN
    k_err = np.abs(sim["k_est"][after] - sim["k_true"][after])
    lag = next((float(t - SYNTH_K_TRUE[-1][0]) for t, ke in zip(out_p["t_min"], sim["k_est"])
                if t >= SYNTH_K_TRUE[-1][0] and abs(ke - SYNTH_K_TRUE[-1][1]) <= 0.1), None)
    print(f"합성 심박 k 추정: 변화 후 |오차| 중앙값 {np.median(k_err):.3f}, p90 {np.percentile(k_err, 90):.3f}, "
          f"k 변화 후 ±0.1 안에 들어오기까지 {lag} 분")
    print(f"  모델 기준 누적 산소 {out_p['o2_cum_g'][-1]:.0f} g vs 심박 기준 {sim['o2_cum_hr_g'][-1]:.0f} g")

    budget = REF_REMAINING_O2_G - O2_RESERVE_G
    area_rows = [{"k": float(kk), "area_km2": float((ret_o2 * kk <= budget).sum() * cell_km2)} for kk in K_GRID]
    a1 = next(r["area_km2"] for r in area_rows if r["k"] == 1.0)
    for r in area_rows:
        if r["k"] in K_MAP:
            print(f"  k = {r['k']:.2f}: 귀환 가능 {r['area_km2']:.2f} km2 ({(r['area_km2'] / a1 - 1) * 100:+.0f}%)")

    base = (bx, by)
    plot_conversion(f"{OUT_DIR}/hr_to_o2.png")
    plot_route_and_k(out_p, back_p, sim, f"{OUT_DIR}/route_hr_and_k.png")
    plot_k_walkback(h, valid, ret_o2, base, traverse_xy, area_rows, f"{OUT_DIR}/walkback_vs_k.png")

    stats = {
        "source": "Hoffmann 2021, NASA NTRS 20210024317, Ch.5 Table 5.1 (132 Shuttle/ISS EVAs)",
        "fit": {"intercept_btu_h": HR_MR_INTERCEPT_BTU_H, "slope_btu_h_per_bpm": HR_MR_SLOPE_BTU_H_PER_BPM,
                "r2_group": 0.402, "r2_individual": ">0.82", "individual_rmse_btu_h": "89.66 +/- 44.24"},
        "mars_level_walk": {"w": lvl_w, "o2_g_h": LEVEL_O2_G_PER_H, "expected_hr_bpm": float(metabolic_w_to_hr(lvl_w))},
        "route": {"goal_sol": GOAL_SOL,
                  "out": {"hr_mean": float(out_p["hr_bpm"].mean()), "hr_max": float(out_p["hr_bpm"].max()),
                          "o2_g": out_p["o2_total_g"], "minutes": int(len(out_p["t_min"])),
                          "minutes_beyond_fit": int(out_p["beyond_fit"].sum())},
                  "back": {"hr_mean": float(back_p["hr_bpm"].mean()), "hr_max": float(back_p["hr_bpm"].max()),
                           "o2_g": back_p["o2_total_g"], "minutes": int(len(back_p["t_min"])),
                           "minutes_beyond_fit": int(back_p["beyond_fit"].sum())},
                  "fit_max_mr_w": FIT_MAX_MR_W,
                  "hr_conversion_valid": bool(hr_valid(out_p) and hr_valid(back_p)),
                  "validity_rule": f"valid if <= {VALID_SHARE_MIN:.0%} of route minutes exceed fit_max_mr_w (Hoffmann 2021 bins top at >1200 BTU/hr)"},
        "synthetic_k_demo": {"k_true": SYNTH_K_TRUE, "noise_bpm": SYNTH_NOISE_BPM, "window_min": K_WINDOW_MIN,
                             "abs_err_median": float(np.median(k_err)), "abs_err_p90": float(np.percentile(k_err, 90)),
                             "minutes_to_within_0.1": lag, "note": "synthetic HR, not measured"},
        "walkback_vs_k": area_rows,
    }
    with open(f"{OUT_DIR}/heart_rate_o2_stats.json", "w") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    print(f"saved {OUT_DIR}/heart_rate_o2_stats.json")


if __name__ == "__main__":
    main()
