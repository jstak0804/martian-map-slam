"""
위치 불확실성 기반 "선택적 신뢰" — 공간 블러 대신 셀별 신뢰도로 재도전

exploration_uncertainty_fusion.py의 1차 시도(가우시안 공간 블러)는 실패했다 —
IoU 0.199(크리스프 VO) -> 0.016(블러), MAE도 0.033 -> 0.035로 더 나빠졌다. 그림으로
보면 원인이 명확하다: 블러가 바위의 또렷한 경계 자체를 뭉개버려서, "어디가 위험한가"
라는 공간 정보를 잃어버린다 — 불확실성을 지도에 "흡수"시키는 방식 자체가 잘못됐다.

이번엔 지도는 손대지 않고(크리스프 VO 지도 그대로), 대신 "이 칸은 몇 번째 스텝에서
찍혔는가"만으로 신뢰도를 매긴다 — 탐사 초반(드리프트가 거의 없을 때) 찍힌 칸은 믿을
만하고, 후반(드리프트가 누적된 뒤) 찍힌 칸은 의심해야 한다는, 로버가 자기 센서 스펙만
알아도(참 드리프트를 훔쳐보지 않아도) 스스로 판단할 수 있는 정보다. "전체 지도를 다
쓰되 덜 정확하게" 대신 "일부만 쓰되 그 안에서는 확실하게"로 접근을 바꾼다.
"""
from __future__ import annotations

import json
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import exploration_slam_sim as sim
from exploration_slam_sim import GRID, RISK_CMAP
from exploration_uncertainty_fusion import STEP_SIGMA_CELLS, mae_against_truth

OUT_DIR = "../outputs/exploration"
N_SEEDS = 10
TRUST_SIGMA_BUDGET = 3.0  # 이 값(셀) 이하로 모델링된 불확실성을 가진 스텝까지만 "신뢰" (46스텝 중 약 절반)


def build_trust_filtered_map(result: dict, sigma_budget: float):
    """크리스프 VO 지도는 그대로 쓰되, 모델링된 누적 불확실성이 sigma_budget을 넘는
    스텝에서 찍힌 관측은 아예 지도에 넣지 않는다 — 참 드리프트는 안 쓴다."""
    rs = np.zeros((GRID, GRID)); rw = np.zeros((GRID, GRID))
    known = np.zeros((GRID, GRID), dtype=bool)

    true_path = result["true_path"]
    vo_path = result["vo_path"]
    n_trusted_steps = 0

    for i, (true_stop_pos, readings) in enumerate(result["all_readings_log"]):
        sigma = STEP_SIGMA_CELLS * np.sqrt(i + 1)
        if sigma > sigma_budget:
            continue
        n_trusted_steps += 1
        vo_stop_pos = vo_path[i]
        drift = vo_stop_pos - true_stop_pos
        for x, y, mh, mr, r_m, dstd in readings:
            gx, gy = int(round(x + drift[0])), int(round(y + drift[1]))
            if 0 <= gx < GRID and 0 <= gy < GRID:
                w = 1.0 / (dstd ** 2)
                rs[gy, gx] += mr * w; rw[gy, gx] += w
                known[gy, gx] = True

    r_map = np.full((GRID, GRID), np.nan)
    m = rw > 0
    r_map[m] = rs[m] / rw[m]
    return {"known": known, "r": r_map, "n_trusted_steps": n_trusted_steps,
            "coverage_frac": float(known.mean())}


def run_one_seed(seed: int, sigma_budget: float) -> dict:
    sim.rng = np.random.default_rng(seed)
    h, rocks = sim.generate_terrain()
    risk = sim.true_risk_field(h)
    result = sim.run_exploration(h, risk)

    trusted = build_trust_filtered_map(result, sigma_budget)

    iou_vo_full = sim.iou_high_risk(result["vo_r"], risk, result["vo_known"])
    iou_trusted = sim.iou_high_risk(trusted["r"], risk, trusted["known"])
    mae_vo_full = mae_against_truth(result["vo_r"], risk, result["vo_known"])
    mae_trusted = mae_against_truth(trusted["r"], risk, trusted["known"])

    return {
        "seed": seed,
        "iou_vo_full": float(iou_vo_full), "iou_trusted": float(iou_trusted),
        "mae_vo_full": mae_vo_full, "mae_trusted": mae_trusted,
        "coverage_full": float(result["vo_known"].mean()),
        "coverage_trusted": trusted["coverage_frac"],
        "n_trusted_steps": trusted["n_trusted_steps"],
    }, (h, risk, result, trusted) if seed == 0 else None


def main():
    print(f"신뢰 기준: 모델링된 누적 불확실성 <= {TRUST_SIGMA_BUDGET} cell인 스텝까지만 지도에 반영\n")

    rows = []
    viz = None
    for seed in range(N_SEEDS):
        row, v = run_one_seed(seed, TRUST_SIGMA_BUDGET)
        rows.append(row)
        if v is not None:
            viz = v
        print(f"  seed={seed}  IoU: 전체={row['iou_vo_full']:.3f} 신뢰구간만={row['iou_trusted']:.3f}  |  "
              f"MAE: 전체={row['mae_vo_full']:.3f} 신뢰구간만={row['mae_trusted']:.3f}  |  "
              f"커버리지 {row['coverage_full']*100:.1f}%->{row['coverage_trusted']*100:.1f}% "
              f"({row['n_trusted_steps']}스텝)")

    def agg(key):
        vals = np.array([r[key] for r in rows])
        return float(np.nanmean(vals)), float(np.nanstd(vals))

    iou_f_m, iou_f_s = agg("iou_vo_full")
    iou_t_m, iou_t_s = agg("iou_trusted")
    mae_f_m, mae_f_s = agg("mae_vo_full")
    mae_t_m, mae_t_s = agg("mae_trusted")
    cov_f_m, _ = agg("coverage_full")
    cov_t_m, _ = agg("coverage_trusted")

    print(f"\n{'지표':>12} {'전체 VO 지도':>16} {'신뢰구간만':>16}")
    print(f"{'위험지대 IoU':>12} {iou_f_m:>10.3f}±{iou_f_s:<5.3f} {iou_t_m:>10.3f}±{iou_t_s:<5.3f}")
    print(f"{'위험도 MAE':>12} {mae_f_m:>10.3f}±{mae_f_s:<5.3f} {mae_t_m:>10.3f}±{mae_t_s:<5.3f}")
    print(f"{'커버리지':>12} {cov_f_m*100:>14.1f}% {cov_t_m*100:>14.1f}%")

    summary = {
        "n_seeds": N_SEEDS, "sigma_budget_cells": TRUST_SIGMA_BUDGET, "runs": rows,
        "iou_vo_full_mean": iou_f_m, "iou_vo_full_std": iou_f_s,
        "iou_trusted_mean": iou_t_m, "iou_trusted_std": iou_t_s,
        "mae_vo_full_mean": mae_f_m, "mae_vo_full_std": mae_f_s,
        "mae_trusted_mean": mae_t_m, "mae_trusted_std": mae_t_s,
        "coverage_full_mean": cov_f_m, "coverage_trusted_mean": cov_t_m,
    }
    with open(f"{OUT_DIR}/selective_trust_stats.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nsaved {OUT_DIR}/selective_trust_stats.json")

    if viz is not None:
        plot_comparison(*viz)


def style_ax(ax):
    ax.set_facecolor("#0b0e15")
    for s in ax.spines.values():
        s.set_color("#262d3d")
    ax.tick_params(colors="#a7aec1", labelsize=7)


def plot_comparison(h, risk, result, trusted):
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 5.2), facecolor="#0b0e15")
    panels = [
        ("True risk field", risk, None),
        ("VO map — full (current baseline)", result["vo_r"], result["vo_known"]),
        (f"VO map — trusted steps only ({trusted['n_trusted_steps']} steps)", trusted["r"], trusted["known"]),
    ]
    for ax, (title, field, known) in zip(axes, panels):
        style_ax(ax)
        show = np.where(known, field, np.nan) if known is not None else field
        ax.imshow(show, cmap=RISK_CMAP, vmin=0, vmax=1, origin="upper")
        ax.plot(result["true_path"][:, 0], result["true_path"][:, 1], "-", color="#5cbcc3", linewidth=1, alpha=0.7)
        ax.set_title(title, color="#e9ebf2", fontsize=9)
    fig.suptitle("Selective trust — keep only low-uncertainty-step observations (seed=0)", color="#a7aec1", fontsize=10)
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/selective_trust_comparison.png", dpi=135, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"saved {OUT_DIR}/selective_trust_comparison.png")


if __name__ == "__main__":
    main()
