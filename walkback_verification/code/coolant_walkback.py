"""
냉각수 잔량이 귀환 반경을 언제, 어디서 묶는가

spe_walkback.run_scenario에 냉각수 예산(suit_cooling.py)을 넣어 세 가지를 본다.
  1) 남은 냉각수를 줄여 가며(누수·과소충전 상황) 귀환 가능 면적이 산소보다 먼저 줄어드는 지점
  2) 환경·PLSS 열 Q_extra(-100 / 0 / +100 W, 미측정 가정)에 따라 그 지점이 얼마나 움직이는지
  3) 냉각수가 길 위에서 바닥난 뒤 몸에 열을 쌓아(비상 한계 CDO 2.0 BTU/lb) 겨우 돌아오는 "비상 띠"의 크기
     (30분 예비분을 헐어 쓰는 칸은 비상 띠에 넣지 않는다)

산소는 기준 시나리오(남은 150 g)로 고정하고 SPE는 끈다.
실행: python coolant_walkback.py
"""
from __future__ import annotations

import json
import os

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from human_mission_navigation import style_ax, _marker, EVA_WALK_SPEED_M_S
import metabolic_model as _mm
from mars_walkback import hillshade, km_extent, CELL_M, O2_RESERVE_G
from metabolic_navigation import o2_g_per_s
from spe_walkback import load_scene, run_scenario, REF_REMAINING_O2_G
from suit_cooling import (
    water_g_per_s, water_reserve_g, minutes_to_cdo, FEEDWATER_FULL_G, HEAT_STORAGE_WATER_EQ_G,
    HEAT_STORAGE_CDO_BTU_LB, LEVEL_MR_W, LATENT_HEAT_J_PER_KG,
)

OUT_DIR = "../outputs/coolant"
os.makedirs(OUT_DIR, exist_ok=True)

WATER_SWEEP_G = np.arange(300, 1601, 100)
Q_SCENARIOS = [(-100.0, "cold: suit loses 100 W", "#7fb2e5"),
               (0.0, "neutral: Q_extra = 0", "#5cbcc3"),
               (100.0, "warm: +100 W (sun, PLSS)", "#e0ac53")]
MAP_WATER_G = 600.0     # 지도 예시: 냉각수 0.6 kg 남음 (누수 상황 가정)
C_SAFE, C_WATER, C_CONT = "#5cbcc3", "#d65bd0", "#f2d430"


def water_equiv_of_o2_g(o2_g, q_extra_w=0.0):
    """평지 보행에서 o2_g만큼 쓰는 동안 쓰는 냉각수(g). 산소 예산과 '같은 시간'인 냉각수."""
    return o2_g * float(water_g_per_s(LEVEL_MR_W, q_extra_w) / o2_g_per_s(LEVEL_MR_W))


def plot_sweep(rows, o2_area, crossover, path):
    fig, ax = plt.subplots(figsize=(7.8, 4.4), facecolor="#0b0e15")
    style_ax(ax)
    ax.axhline(o2_area, color="#a7aec1", ls="--", lw=1, label=f"O2 limit only ({REF_REMAINING_O2_G} g O2 left)")
    for q, label, color in Q_SCENARIOS:
        rr = [r for r in rows if r["q_extra_w"] == q]
        w = [r["water_left_g"] / 1000 for r in rr]
        ax.plot(w, [r["area_safe_km2"] for r in rr], "o-", color=color, ms=3.5, label=f"O2 + water, {label}")
        if crossover[q] is not None:
            ax.axvline(crossover[q] / 1000, color=color, lw=0.8, alpha=0.6)
    ax.set_xlabel("coolant water left at the failure (kg)", color="#a7aec1", fontsize=8)
    ax.set_ylabel("walk-back area (km2)", color="#a7aec1", fontsize=8)
    ax.set_title(f"Below which water level does coolant, not O2, limit the walk back? ({REF_REMAINING_O2_G} g O2 left, "
                 "vertical lines = first water level that cuts area)", color="#e9ebf2", fontsize=9)
    ax.legend(facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2", fontsize=7.2, loc="lower right")
    fig.tight_layout()
    fig.savefig(path, dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"saved {path}")


def plot_maps(h, valid, base, traverse_xy, panels, path):
    fig, axes = plt.subplots(1, len(panels), figsize=(4.3 * len(panels), 6.4), facecolor="#0b0e15", squeeze=False)
    ext = km_extent(h.shape)
    k = CELL_M / 1000
    shade = np.where(valid, hillshade(h), np.nan)
    for ax, (title, r) in zip(axes[0], panels):
        style_ax(ax)
        ax.imshow(shade, cmap="gray", extent=ext, vmin=0, vmax=1)
        for mask, color in ((r["safe"], C_SAFE), (r["ok_o2"] & ~r["ok_water"] & ~r["water_contingency"], C_WATER),
                            (r["water_contingency"], C_CONT)):
            rgba = np.zeros(h.shape + (4,))
            rgba[mask] = matplotlib.colors.to_rgba(color, 0.55)
            ax.imshow(rgba, extent=ext)
        for x, y in traverse_xy:
            ax.plot(x * k, y * k, color="#e9ebf2", lw=0.5, alpha=0.6)
        _marker(ax, (base[0] * k, base[1] * k), "#a7e8a0", marker="*", size=160)
        ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
        ax.set_title(f"{title}\nsafe {r['area_safe_km2']:.1f} km2, water-cut {r['area_water_limited_km2']:.1f} km2\n"
                     f"of which dry-tank body-heat band {r['area_water_contingency_km2']:.1f} km2",
                     color="#e9ebf2", fontsize=8.5)
    fig.suptitle(f"{REF_REMAINING_O2_G} g O2 and {MAP_WATER_G / 1000:g} kg coolant water left -- blue = can return, "
                 f"pink = O2 OK but water runs short, yellow = tank runs dry on the way; home only by storing body heat up to the "
                 f"{HEAT_STORAGE_CDO_BTU_LB} BTU/lb contingency limit", color="#e9ebf2", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"saved {path}")


def main():
    h, valid, eta, shielding, passable, traverse_xy, base = load_scene()
    base_idx = base[1] * h.shape[1] + base[0]
    o2_budget = REF_REMAINING_O2_G - O2_RESERVE_G
    cell_km2 = (CELL_M / 1000) ** 2

    lvl_w = float(water_g_per_s(LEVEL_MR_W)) * 3600
    print(f"평지 보행 {LEVEL_MR_W:.0f} W: 산소 {float(o2_g_per_s(LEVEL_MR_W)) * 3600:.0f} g/h, 냉각수 {lvl_w:.0f} g/h "
          f"(증발잠열 {LATENT_HEAT_J_PER_KG / 1e6:.3f} MJ/kg) -> 만충 {FEEDWATER_FULL_G / 1000:.1f} kg = "
          f"{FEEDWATER_FULL_G / lvl_w:.1f} h")
    print(f"물이 떨어진 뒤 비상 한계까지 평지 보행 {float(minutes_to_cdo(LEVEL_MR_W)):.0f}분 "
          f"(~{float(minutes_to_cdo(LEVEL_MR_W)) * 60 * _mm.LEVEL_SPEED_M_S / 1000:.1f} km) = "
          f"냉각수 {HEAT_STORAGE_WATER_EQ_G:.0f} g어치")

    ref = run_scenario(h, eta, shielding, passable, base_idx, 1.0, o2_budget)
    o2_area = ref["area_o2_only_km2"]
    print(f"산소 {REF_REMAINING_O2_G} g만 볼 때 {o2_area:.2f} km2")

    rows, crossover, equiv = [], {}, {}
    for q, label, _ in Q_SCENARIOS:
        equiv[q] = water_equiv_of_o2_g(o2_budget, q) + water_reserve_g(q)
        crossover[q] = None
        for w in WATER_SWEEP_G:
            r = run_scenario(h, eta, shielding, passable, base_idx, 1.0, o2_budget, float(w), q)
            rows.append({"q_extra_w": q, "water_left_g": float(w),
                         **{kk: v for kk, v in r.items() if kk.endswith("km2")}})
        # 냉각수가 묶기 시작 = 남은 냉각수를 위에서부터 줄일 때 처음으로 산소만 볼 때보다 면적이 줄어드는 수준
        for row in sorted((r for r in rows if r["q_extra_w"] == q), key=lambda r: -r["water_left_g"]):
            if row["area_water_limited_km2"] > 0.01:
                crossover[q] = row["water_left_g"]
                break
        print(f"  Q_extra {q:+.0f} W ({label}): 예비분 {water_reserve_g(q):.0f} g, 산소 {REF_REMAINING_O2_G} g과 "
              f"같은 시간어치 냉각수 {equiv[q]:.0f} g, 면적이 줄기 시작하는 잔량 ~{crossover[q]} g")
        for row in rows:
            if row["q_extra_w"] == q and row["water_left_g"] in (400.0, 600.0, 800.0):
                print(f"     냉각수 {row['water_left_g']:.0f} g: 귀환 {row['area_safe_km2']:.2f} km2 "
                      f"(냉각수 때문에 잘림 {row['area_water_limited_km2']:.2f}, 비상 띠 "
                      f"{row['area_water_contingency_km2']:.2f})")

    panels = []
    for q, label, _ in Q_SCENARIOS:
        r = run_scenario(h, eta, shielding, passable, base_idx, 1.0, o2_budget, MAP_WATER_G, q)
        panels.append((label, r))
    plot_sweep(rows, o2_area, crossover, f"{OUT_DIR}/water_vs_o2_sweep.png")
    plot_maps(h, valid, base, traverse_xy, panels, f"{OUT_DIR}/coolant_walkback_map.png")
    # 지형 효과: 귀환 냉각수를 "같은 귀환 산소를 평지 보행 비율로 환산한 냉각수"로 나눈 값.
    # 1에서 멀수록 경로의 경사 때문에 냉각수가 산소와 다른 속도로 준다는 뜻.
    warm = run_scenario(h, eta, shielding, passable, base_idx, 1.0, o2_budget, FEEDWATER_FULL_G, 100.0)
    eq = warm["o2"] * float(water_g_per_s(LEVEL_MR_W, 100.0) / o2_g_per_s(LEVEL_MR_W))
    ratio = (warm["water"] / np.maximum(eq, 1e-9))[valid & (warm["o2"] > 5)]
    ratio_stats = {"median": float(np.median(ratio)), "p10": float(np.percentile(ratio, 10)),
                   "p90": float(np.percentile(ratio, 90))}
    print(f"  Q_extra +100 W 귀환 냉각수/산소 환산비: 중앙값 {ratio_stats['median']:.3f}, "
          f"p10 {ratio_stats['p10']:.3f}, p90 {ratio_stats['p90']:.3f}")

    stats = {
        "sources": {
            "latent_heat": "water at 10 C, SWME operating temp (ICES-2026-126 p.10)",
            "feedwater_full": "3.6 kg (8 lbm) for 8 h EVA, Nabity et al. 07ICES-221 abstract; EMU 3.9 kg @ 7 h x 1000 BTU/hr (Akin UMD ENAE 697 p.8)",
            "heat_storage_limits": "nominal <= 1.3 BTU/lb, contingency CDO <= 2.0 BTU/lb (ICES-2026-170 slide 5)",
            "mars_cooling": "sublimator infeasible on Mars; SWME tested to 10 Torr; sites assumed <= 7-8 Torr (ICES-2026-126 p.4,7,10)",
        },
        "assumptions": {"q_extra_scenarios_w": [q for q, _, _ in Q_SCENARIOS], "all_metabolic_heat_to_evaporator": True,
                        "water_reserve": "30 min level walk (same rule as O2)", "body_mass_kg_for_heat_storage": 75},
        "level_walk": {"mr_w": LEVEL_MR_W, "water_g_h": lvl_w, "full_tank_hours": FEEDWATER_FULL_G / lvl_w,
                       "minutes_to_cdo_after_dry": float(minutes_to_cdo(LEVEL_MR_W)),
                       "heat_storage_water_eq_g": HEAT_STORAGE_WATER_EQ_G},
        "o2_only_area_km2": o2_area,
        "water_equiv_of_o2_budget_g": equiv,
        "crossover_water_left_g": crossover,
        "map_water_left_g": MAP_WATER_G,
        "map_panels": [{"label": t, **{kk: v for kk, v in r.items() if kk.endswith("km2")}} for t, r in panels],
        "ratio_warm_q100": ratio_stats,
        "sweep": rows,
    }
    with open(f"{OUT_DIR}/coolant_stats.json", "w") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    print(f"saved {OUT_DIR}/coolant_stats.json")


if __name__ == "__main__":
    main()
