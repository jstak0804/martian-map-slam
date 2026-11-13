"""
REMS 실측 기온 비교 시나리오 — 코사인 일교차 가정 vs Curiosity REMS 실측

human_mission_risk.py의 온도 항은 T_MAX=5°C, T_MIN=-95°C, 14시 최고인 코사인 곡선(가정)이다.
이 스크립트는 같은 지형·같은 방사선·같은 경고선에서 온도 항만 Curiosity REMS 실측 기온
(PDS mslrem_1001 ENVRDR, Gale Crater)으로 바꿔, 경보 시각이 어떻게 달라지는지 비교한다.
기존 데모와 산출물은 건드리지 않는다.

데이터 처리:
  - BOOM1_AIR_TEMP(열 28, K)를 사용. BOOM2는 전자부가 -50°C 아래일 때(신뢰도 플래그 byte0=0)
    BOOM1보다 50K 이상 낮은 비현실적 값을 내는 구간이 있어 제외했다 (예: sol 570 02시,
    BOOM1 195K vs BOOM2 139K).
  - -999 결측값 제거 후 지방평균태양시(LMST) 기준 1시간/15분 평균.
  - 원본 TAB 파일은 data/rems/에 두고, 요약 곡선만 data/rems/rems_hourly.json으로 저장한다.
"""
from __future__ import annotations

import base64
import csv
import glob
import json
import os
import re

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import exploration_slam_sim as sim
from anisotropic_risk_exploration import rock_risk_grid, slope_grids
from human_mission_risk import (
    human_mission_risk, shielding_factor_grid, diurnal_temperature, thermal_risk_from_temp,
    radiation_risk, WARNING_THRESHOLD, SPE_START_HOUR, SPE_END_HOUR,
    T_SAFE_LOW_C, T_CRITICAL_LOW_C, T_MIN_C, T_MAX_C,
    W_TERRAIN, W_HUMAN, W_THERMAL, W_RADIATION, SLOPE_W, ROCK_W,
    D_BACKGROUND_MSV_DAY, D_BUDGET_MSV_DAY, SPE_DOSE_MULTIPLIER, SHIELDING_MAX_REDUCTION,
)

DATA_DIR = "../data/rems"
OUT_DIR = "../outputs/rems_temperature"
os.makedirs(OUT_DIR, exist_ok=True)

COL_LMST = 1
COL_BOOM1_AIR_K = 27
FINE_BINS = 96  # 15분


def parse_sol(path):
    lmst, temp = [], []
    with open(path, newline="") as f:
        for r in csv.reader(f):
            try:
                hh, mm, ss = r[COL_LMST].strip().strip('"').split("M")[1].split(":")
                v = float(r[COL_BOOM1_AIR_K])
            except (IndexError, ValueError):
                continue
            if v < -900:
                continue
            lmst.append(int(hh) + int(mm) / 60 + float(ss) / 3600)
            temp.append(v - 273.15)
    return np.array(lmst), np.array(temp)


def bin_circular(lmst, temp, n_bins):
    edges = np.linspace(0, 24, n_bins + 1)
    out = np.full(n_bins, np.nan)
    for i in range(n_bins):
        m = (lmst >= edges[i]) & (lmst < edges[i + 1])
        if m.any():
            out[i] = temp[m].mean()
    if np.isnan(out).any():  # 하루 경계를 넘어 원형 보간
        idx = np.arange(n_bins)
        ok = ~np.isnan(out)
        out = np.interp(idx, np.r_[idx[ok] - n_bins, idx[ok], idx[ok] + n_bins],
                        np.r_[out[ok], out[ok], out[ok]])
    return out


def load_curves():
    curves = {}
    for path in sorted(glob.glob(f"{DATA_DIR}/sol*_RNV.TAB"), key=lambda p: int(re.search(r"sol(\d+)", p).group(1))):
        sol = int(re.search(r"sol(\d+)", path).group(1))
        lmst, temp = parse_sol(path)
        curves[sol] = {
            "n_samples": int(len(temp)),
            "hourly_c": bin_circular(lmst, temp, 24),
            "fine_c": bin_circular(lmst, temp, FINE_BINS),
            "source_file": os.path.basename(path),
        }
    return curves


def temperature_at(curve_hourly, hour):
    """시간당 평균(각 시간 구간의 중앙값 = h+0.5)을 원형 선형보간해 임의 시각의 기온을 준다."""
    xs = np.arange(24) + 0.5
    return float(np.interp(hour % 24, np.r_[xs - 24, xs, xs + 24], np.r_[curve_hourly, curve_hourly, curve_hourly]))


def run_timeline(slope_risk, rock_r, shielding, temp_fn):
    rows = []
    for hour in np.arange(0, 24, 1.0):
        spe = SPE_START_HOUR <= hour < SPE_END_HOUR
        t = temp_fn(hour)
        grid = human_mission_risk(slope_risk, rock_r, hour, shielding, spe, temperature_c=t)
        rows.append({
            "hour": float(hour), "temperature_c": t,
            "thermal_risk": float(thermal_risk_from_temp(t)),
            "radiation_risk_mean": float(np.mean(radiation_risk(hour, shielding, spe))),
            "spe_active": bool(spe),
            "mean_total_risk": float(grid.mean()),
            "safe_zone_pct": float((grid < WARNING_THRESHOLD).mean() * 100),
            "warning": bool(grid.mean() > WARNING_THRESHOLD),
        })
    return rows


def export_demo_grids(terrain_term, shielding):
    def q(a):
        return base64.b64encode(np.clip(np.round(a * 255), 0, 255).astype(np.uint8).tobytes()).decode("ascii")
    return {"n": int(terrain_term.shape[0]), "terrain_term_u8": q(terrain_term), "shielding_u8": q(shielding)}


def main():
    print("=== REMS 실측 기온 vs 코사인 가정 -- 경보 시각 비교 ===\n")
    curves = load_curves()
    for sol, c in curves.items():
        h = c["hourly_c"]
        print(f"sol {sol:>4}: n={c['n_samples']:>6}  min {h.min():6.1f}°C @{h.argmin():02d}h  "
              f"max {h.max():6.1f}°C @{h.argmax():02d}h")

    sim.rng = np.random.default_rng(0)
    hmap, _ = sim.generate_terrain()
    gx, gy = slope_grids(hmap)
    slope_risk = np.clip(np.hypot(gx, gy) / 0.9, 0, 1)
    rock_r = rock_risk_grid(hmap)
    shielding = shielding_factor_grid(hmap)

    scenarios = {"cosine": run_timeline(slope_risk, rock_r, shielding, lambda hr: float(diurnal_temperature(hr)))}
    for sol, c in curves.items():
        scenarios[f"sol{sol}"] = run_timeline(slope_risk, rock_r, shielding,
                                              lambda hr, hc=c["hourly_c"]: temperature_at(hc, hr))

    coldest = min(curves, key=lambda s: curves[s]["hourly_c"].min())
    print(f"\n가장 추운 sol: {coldest}")
    print(f"\n{'시나리오':>9} {'최저기온':>8} {'최대 thermal':>12} {'경보 시각'}")
    summary = {}
    for name, rows in scenarios.items():
        warn = [int(r["hour"]) for r in rows if r["warning"]]
        tmin = min(r["temperature_c"] for r in rows)
        th = max(r["thermal_risk"] for r in rows)
        peak = max(rows, key=lambda r: r["mean_total_risk"])
        summary[name] = {"min_temp_c": tmin, "max_thermal_risk": th, "warning_hours": warn,
                         "peak_hour": peak["hour"], "peak_mean_risk": peak["mean_total_risk"],
                         "min_safe_zone_pct": min(r["safe_zone_pct"] for r in rows)}
        print(f"{name:>9} {tmin:8.1f} {th:12.3f}  {warn if warn else '없음'}  "
              f"(최고 평균위험 {peak['mean_total_risk']:.3f} @{peak['hour']:.0f}시)")

    # ---- 그림
    bg, fg, mute = "#0b0e15", "#e9ebf2", "#a7aec1"
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.6), facecolor=bg)
    for ax in axes:
        ax.set_facecolor(bg)
        for s in ax.spines.values():
            s.set_color("#262d3d")
        ax.tick_params(colors=mute, labelsize=8)
        ax.set_xlim(0, 24); ax.set_xticks(range(0, 25, 3))
        ax.axvspan(SPE_START_HOUR, SPE_END_HOUR, color="#e08a76", alpha=0.12)
        ax.set_xlabel("local mean solar time (h)", color=mute, fontsize=9)

    ax = axes[0]
    xf = (np.arange(FINE_BINS) + 0.5) * 24 / FINE_BINS
    for sol, c in curves.items():
        hl = sol in (242, coldest)
        ax.plot(xf, c["fine_c"], color="#5cbcc3" if sol == 242 else "#8fb7ff" if sol == coldest else "#4a5468",
                linewidth=2.0 if hl else 1.0, label=f"REMS sol {sol}" if hl else None, zorder=3 if hl else 2)
    ax.plot([], [], color="#4a5468", linewidth=1.0, label="REMS other sols")
    hh = np.linspace(0, 24, 200)
    ax.plot(hh, diurnal_temperature(hh), "--", color="#e0ac53", linewidth=2.0, label="cosine model (assumption)")
    ax.axhline(T_SAFE_LOW_C, color="#e08a76", linestyle=":", linewidth=1.2, label=f"T_SAFE_LOW {T_SAFE_LOW_C:.0f}°C")
    ax.axhline(T_CRITICAL_LOW_C, color="#ff5c5c", linestyle=":", linewidth=1.2, label=f"T_CRITICAL {T_CRITICAL_LOW_C:.0f}°C")
    ax.set_ylabel("air temperature (°C)", color=mute, fontsize=9)
    ax.set_title("Diurnal air temperature at Gale Crater -- REMS (Boom1) vs cosine assumption", color=fg, fontsize=10.5)
    ax.legend(facecolor="#141926", edgecolor="#262d3d", labelcolor=fg, fontsize=7.5, loc="lower right")

    ax = axes[1]
    hrs = [r["hour"] + 0.5 for r in scenarios["cosine"]]
    for name, color, label in [("cosine", "#e0ac53", "cosine model"), (f"sol242", "#5cbcc3", "REMS sol 242"),
                               (f"sol{coldest}", "#8fb7ff", f"REMS sol {coldest} (coldest sampled)")]:
        rows = scenarios[name]
        ax.step(hrs, [r["mean_total_risk"] for r in rows], where="mid", color=color, linewidth=2.0, label=label)
        for r in rows:
            if r["warning"]:
                ax.scatter([r["hour"] + 0.5], [r["mean_total_risk"]], color=color, edgecolor="white", s=40, zorder=5)
    ax.axhline(WARNING_THRESHOLD, color="#ffffff", linestyle="--", linewidth=1, alpha=0.6, label=f"warning {WARNING_THRESHOLD}")
    ax.set_ylabel("mean combined risk", color=mute, fontsize=9)
    ax.set_title("Combined risk timeline (shaded = SPE window 01-04h, dots = warning)", color=fg, fontsize=10.5)
    ax.legend(facecolor="#141926", edgecolor="#262d3d", labelcolor=fg, fontsize=7.5, loc="upper right")
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/rems_vs_cosine.png", dpi=130, facecolor=bg)
    plt.close(fig)
    print(f"\nsaved {OUT_DIR}/rems_vs_cosine.png")

    # ---- 저장: 요약 곡선 + 비교 결과 + 데모용 격자
    terrain_term = SLOPE_W * slope_risk + ROCK_W * rock_r
    rems_json = {
        "source": "PDS Atmospheres node, MSL REMS ENVRDR (mslrem_1001), column BOOM1_AIR_TEMP",
        "url": "https://atmos.nmsu.edu/PDS/data/mslrem_1001/DATA/",
        "sols": {str(s): {"n_samples": c["n_samples"], "source_file": c["source_file"],
                          "hourly_c": [round(float(v), 2) for v in c["hourly_c"]],
                          "fine_c": [round(float(v), 2) for v in c["fine_c"]]} for s, c in curves.items()},
    }
    with open(f"{DATA_DIR}/rems_hourly.json", "w") as f:
        json.dump(rems_json, f, indent=1)
    with open(f"{OUT_DIR}/rems_comparison_stats.json", "w") as f:
        json.dump({"coldest_sol": coldest, "summary": summary, "timelines": scenarios}, f, indent=1, ensure_ascii=False)
    demo = {
        "params": {"W_TERRAIN": W_TERRAIN, "W_HUMAN": W_HUMAN, "W_THERMAL": W_THERMAL, "W_RADIATION": W_RADIATION,
                   "T_SAFE_LOW_C": T_SAFE_LOW_C, "T_CRITICAL_LOW_C": T_CRITICAL_LOW_C,
                   "T_MIN_C": T_MIN_C, "T_MAX_C": T_MAX_C,
                   "D_BACKGROUND_MSV_DAY": D_BACKGROUND_MSV_DAY, "D_BUDGET_MSV_DAY": D_BUDGET_MSV_DAY,
                   "SPE_DOSE_MULTIPLIER": SPE_DOSE_MULTIPLIER, "SHIELDING_MAX_REDUCTION": SHIELDING_MAX_REDUCTION,
                   "WARNING_THRESHOLD": WARNING_THRESHOLD, "SPE_START_HOUR": SPE_START_HOUR, "SPE_END_HOUR": SPE_END_HOUR},
        "grids": export_demo_grids(terrain_term, shielding),
        "rems": {s: v["fine_c"] for s, v in rems_json["sols"].items()},
        "coldest_sol": coldest,
    }
    with open(f"{OUT_DIR}/demo_data.json", "w") as f:
        json.dump(demo, f)
    print(f"saved {DATA_DIR}/rems_hourly.json, {OUT_DIR}/rems_comparison_stats.json, {OUT_DIR}/demo_data.json")


if __name__ == "__main__":
    main()
