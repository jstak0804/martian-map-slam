"""
위험도 임계값 민감도 분석 (지적된 문제 ⑥을 실제로 해결)

real_terrain_risk.py의 위험도 공식은 SLOPE_HIGH_DEG=15°, ROUGHNESS_HIGH_M=2m라는
두 임계값을 하드코딩해서 썼다 — "공학적으로 흔히 쓰이는 자릿수"/"휴리스틱"이라고만
적었을 뿐, 이 특정 숫자를 바꾸면 결론("달이 지구보다 위험하다")이 얼마나
흔들리는지는 한 번도 확인하지 않았다. 이 스크립트는 두 임계값을 각각 넓은 범위로
스윕하면서 지구·달의 평균 위험도·고위험 비율이 어떻게 변하는지 측정한다.
"""
from __future__ import annotations

import json
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.ndimage import uniform_filter

from real_terrain_risk import load_earth_dem, load_moon_dem, CELL_M, ROUGH_WIN_PX

OUT_DIR = "../outputs/real_terrain"

SLOPE_SWEEP = [8, 10, 12.5, 15, 17.5, 20, 25, 30]      # deg, 기준값 15
ROUGH_SWEEP = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]  # m, 기준값 2.0
BASELINE_SLOPE, BASELINE_ROUGH = 15.0, 2.0


def slope_and_roughness(h, cell_m=CELL_M):
    """임계값에 의존하지 않는 원시 지형량만 계산 — 경사(deg), 거칠기(m)."""
    gy, gx = np.gradient(h, cell_m)
    slope_deg = np.degrees(np.arctan(np.hypot(gx, gy)))

    mean = uniform_filter(h, ROUGH_WIN_PX)
    mean_sq = uniform_filter(h ** 2, ROUGH_WIN_PX)
    roughness_m = np.sqrt(np.clip(mean_sq - mean ** 2, 0, None))
    return slope_deg, roughness_m


def risk_at_thresholds(slope_deg, roughness_m, slope_high, rough_high):
    slope_risk = np.clip(slope_deg / slope_high, 0, 1)
    roughness_risk = np.clip(roughness_m / rough_high, 0, 1)
    risk = np.clip(0.5 * slope_risk + 0.5 * roughness_risk, 0, 1)
    return float(risk.mean()), float((risk > 0.5).mean() * 100)


def sweep_one_axis(slope_deg, roughness_m, sweep_values, axis):
    rows = []
    for v in sweep_values:
        if axis == "slope":
            mean_risk, pct_high = risk_at_thresholds(slope_deg, roughness_m, v, BASELINE_ROUGH)
            rows.append({"slope_high_deg": v, "roughness_high_m": BASELINE_ROUGH,
                          "mean_risk": mean_risk, "pct_high_risk": pct_high})
        else:
            mean_risk, pct_high = risk_at_thresholds(slope_deg, roughness_m, BASELINE_SLOPE, v)
            rows.append({"slope_high_deg": BASELINE_SLOPE, "roughness_high_m": v,
                          "mean_risk": mean_risk, "pct_high_risk": pct_high})
    return rows


def main():
    print("지구 DEM 로딩...")
    earth_h, _ = load_earth_dem()
    earth_slope, earth_rough = slope_and_roughness(earth_h)

    print("달 DEM 로딩...")
    moon_h = load_moon_dem()
    moon_slope, moon_rough = slope_and_roughness(moon_h)

    results = {"baseline": {"slope_high_deg": BASELINE_SLOPE, "roughness_high_m": BASELINE_ROUGH}}
    for name, slope_deg, roughness_m in [("earth", earth_slope, earth_rough), ("moon", moon_slope, moon_rough)]:
        results[name] = {
            "slope_sweep": sweep_one_axis(slope_deg, roughness_m, SLOPE_SWEEP, "slope"),
            "roughness_sweep": sweep_one_axis(slope_deg, roughness_m, ROUGH_SWEEP, "roughness"),
        }

    # ---- "달이 지구보다 위험하다"는 결론이 임계값 전 범위에서 뒤집히는 지점이 있는지 ----
    gap_slope = [(r_e["mean_risk"], r_m["mean_risk"])
                 for r_e, r_m in zip(results["earth"]["slope_sweep"], results["moon"]["slope_sweep"])]
    gap_rough = [(r_e["mean_risk"], r_m["mean_risk"])
                 for r_e, r_m in zip(results["earth"]["roughness_sweep"], results["moon"]["roughness_sweep"])]
    slope_always_moon_higher = all(m > e for e, m in gap_slope)
    rough_always_moon_higher = all(m > e for e, m in gap_rough)
    results["conclusion_robust"] = {
        "moon_always_riskier_across_slope_sweep": slope_always_moon_higher,
        "moon_always_riskier_across_roughness_sweep": rough_always_moon_higher,
    }

    print(f"\n경사 임계값(8~30deg) 스윕에서 '달이 항상 더 위험' 유지됨: {slope_always_moon_higher}")
    print(f"거칠기 임계값(0.5~5m) 스윕에서 '달이 항상 더 위험' 유지됨: {rough_always_moon_higher}")
    print("\n[경사 임계값 스윕] (거칠기=2.0m 고정)")
    print(f"{'threshold':>10} {'earth_risk':>11} {'moon_risk':>10} {'earth_high%':>12} {'moon_high%':>11}")
    for r_e, r_m in zip(results["earth"]["slope_sweep"], results["moon"]["slope_sweep"]):
        print(f"{r_e['slope_high_deg']:>10.1f} {r_e['mean_risk']:>11.3f} {r_m['mean_risk']:>10.3f} "
              f"{r_e['pct_high_risk']:>12.1f} {r_m['pct_high_risk']:>11.1f}")

    print("\n[거칠기 임계값 스윕] (경사=15deg 고정)")
    print(f"{'threshold':>10} {'earth_risk':>11} {'moon_risk':>10} {'earth_high%':>12} {'moon_high%':>11}")
    for r_e, r_m in zip(results["earth"]["roughness_sweep"], results["moon"]["roughness_sweep"]):
        print(f"{r_e['roughness_high_m']:>10.1f} {r_e['mean_risk']:>11.3f} {r_m['mean_risk']:>10.3f} "
              f"{r_e['pct_high_risk']:>12.1f} {r_m['pct_high_risk']:>11.1f}")

    plot_sensitivity(results)

    with open(f"{OUT_DIR}/threshold_sensitivity_stats.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nsaved {OUT_DIR}/threshold_sensitivity_stats.json")


def style_ax(ax):
    ax.set_facecolor("#0b0e15")
    for s in ax.spines.values():
        s.set_color("#262d3d")
    ax.tick_params(colors="#a7aec1", labelsize=8)
    ax.grid(color="#1c2230", linewidth=0.6)


def plot_sensitivity(results):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5), facecolor="#0b0e15")

    ax = axes[0]; style_ax(ax)
    xs = [r["slope_high_deg"] for r in results["earth"]["slope_sweep"]]
    ax.plot(xs, [r["mean_risk"] for r in results["earth"]["slope_sweep"]], "o-", color="#5cbcc3", label="Earth")
    ax.plot(xs, [r["mean_risk"] for r in results["moon"]["slope_sweep"]], "o-", color="#e08a76", label="Moon")
    ax.axvline(BASELINE_SLOPE, color="#a7aec1", linestyle="--", linewidth=1, label="used in report (15°)")
    ax.set_xlabel("slope_high_deg threshold", color="#a7aec1")
    ax.set_ylabel("mean risk", color="#a7aec1")
    ax.set_title("Sensitivity to slope threshold\n(roughness fixed at 2.0m)", color="#e9ebf2", fontsize=10)
    ax.legend(facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2", fontsize=9)

    ax = axes[1]; style_ax(ax)
    xs = [r["roughness_high_m"] for r in results["earth"]["roughness_sweep"]]
    ax.plot(xs, [r["mean_risk"] for r in results["earth"]["roughness_sweep"]], "o-", color="#5cbcc3", label="Earth")
    ax.plot(xs, [r["mean_risk"] for r in results["moon"]["roughness_sweep"]], "o-", color="#e08a76", label="Moon")
    ax.axvline(BASELINE_ROUGH, color="#a7aec1", linestyle="--", linewidth=1, label="used in report (2.0m)")
    ax.set_xlabel("roughness_high_m threshold", color="#a7aec1")
    ax.set_ylabel("mean risk", color="#a7aec1")
    ax.set_title("Sensitivity to roughness threshold\n(slope fixed at 15°)", color="#e9ebf2", fontsize=10)
    ax.legend(facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2", fontsize=9)

    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/threshold_sensitivity.png", dpi=135, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"saved {OUT_DIR}/threshold_sensitivity.png")


if __name__ == "__main__":
    main()
