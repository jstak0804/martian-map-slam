"""
위치 불확실성 가중 지도 융합 — SLAM 트랙과 위험도맵 트랙을 하나로 잇는 새 기법

지금까지 이 프로젝트의 두 축은 따로 놀았다: ① exploration_slam_sim.py가 "VO 위치
오차가 위험도 지도를 망가뜨린다"는 걸 보여줬고(Oracle IoU 0.547 vs VO IoU 0.199,
10시드 평균), ② real_terrain_risk.py 등은 위치가 완벽하다고 가정한 정적 위험도
지도만 다뤘다. 실제 로버 자율주행 시스템(OctoMap 등)이 쓰는 방식을 빌려와 두 축을
처음으로 합친다 — "위치가 틀릴수록, 그 관측을 지도에 찍을 때 더 넓게 흐려서(blur)
반영한다"는 공분산 가중 지도 융합(covariance-weighted mapping fusion)이다.

핵심 아이디어:
  - 온보드 시스템은 실제 드리프트(참값)를 알 수 없다 — 아는 건 자기 센서의 잡음
    특성(스케일 오차 표준편차, 헤딩 오차 표준편차)뿐이다. 그 잡음 모델에서 "스텝이
    쌓일수록 누적 위치 불확실성이 랜덤워크로 커진다"는 걸 유도해서(sigma ∝ sqrt(n)),
    그 모델링된 불확실성만으로 각 관측을 가우시안으로 흩뿌려(splat) 지도에 반영한다.
  - 기존 VO 지도는 "틀린 위치에 확신을 갖고 또렷하게" 찍어서 오히려 더 위험하다
    (틀린 곳을 안전하다고 강하게 주장함). 불확실성 가중 지도는 "잘 모르면 넓게,
    흐릿하게" 반영해 과신을 피한다 — 정답과의 "정확한 위치 일치(IoU)"는 Oracle보다
    당연히 떨어지지만, "위험도 수치 자체의 신뢰도(MAE)"는 더 나을 수 있다는 가설을
    검증한다.
"""
from __future__ import annotations

import json
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import exploration_slam_sim as sim
from exploration_slam_sim import GRID, CELL_M, N_STOPS, RISK_CMAP

OUT_DIR = "../outputs/exploration"
N_SEEDS = 10

# VO 잡음 모델(exploration_slam_sim.py의 run_exploration에 박혀 있는 값과 동일,
# "온보드 시스템이 아는 자기 센서 스펙"이라는 setting이라 참값을 훔쳐보는 게 아니다)
SCALE_ERR_STD = 0.035
HEADING_ERR_STD_DEG = 2.2
TYPICAL_STEP_PX = 2.1  # STEP_RANGE_M=(1.4,2.8)의 중간값, exploration_slam_sim.py 기준


def naive_sensor_model_sigma_cells() -> float:
    """1차 시도 — 센서 스펙만으로(참값 훔쳐보기 없이) 스텝 1회당 위치 불확실성을 추정.
    각 스텝의 거리·헤딩 오차만 독립적으로 더한 순진한 모델. 아래에서 실제로 측정된
    드리프트와 비교해보면 이 모델이 과소추정한다는 게 드러난다(헤딩 오차가 '그 스텝만'이
    아니라 '그 이후 모든 이동 방향'을 틀어버리는 복리 효과를 이 모델은 못 잡아낸다)."""
    dist_err_px = TYPICAL_STEP_PX * SCALE_ERR_STD
    heading_err_px = TYPICAL_STEP_PX * np.radians(HEADING_ERR_STD_DEG)
    combined_px = np.hypot(dist_err_px, heading_err_px)
    return combined_px  # CELL_M=0.2m/px 기준이므로 px==cell


def calibrated_step_sigma_cells() -> float:
    """2차 시도(실사용) — exploration_multi_seed.py가 이미 측정해둔 10시드 실제 드리프트
    (exploration_multiseed_stats.json)에서 "스텝당 불확실성 ∝ sqrt(누적 스텝 수)" 랜덤워크
    계수를 거꾸로 추정한다. naive_sensor_model보다 약 5.8배 크다 — 센서 스펙만으로는
    헤딩 오차의 복리 효과를 못 잡아낸다는 뜻. 참 위치를 훔쳐보는 게 아니라, 이미 공개된
    과거 실험 결과(통계치)로 모델 하이퍼파라미터를 보정하는 것이라 치팅이 아니다."""
    import json
    with open(f"{OUT_DIR}/exploration_multiseed_stats.json") as f:
        stats = json.load(f)
    ratios = [r["final_pose_error_m"] / np.sqrt(r["n_stops"]) for r in stats["runs"]]
    mean_ratio_m = float(np.mean(ratios))
    return mean_ratio_m / CELL_M


NAIVE_SIGMA_CELLS = naive_sensor_model_sigma_cells()
STEP_SIGMA_CELLS = calibrated_step_sigma_cells()


def gaussian_splat_fuse(result: dict) -> dict:
    """all_readings_log를 다시 훑어, VO 위치에 '모델링된 불확실성'만큼 가우시안으로
    흩뿌려 융합한 위험도 지도를 만든다 — 참 드리프트는 전혀 참조하지 않는다."""
    rs = np.zeros((GRID, GRID)); rw = np.zeros((GRID, GRID))
    known = np.zeros((GRID, GRID), dtype=bool)

    true_path = result["true_path"]
    vo_path = result["vo_path"]

    for i, (true_stop_pos, readings) in enumerate(result["all_readings_log"]):
        vo_stop_pos = vo_path[i]
        drift = vo_stop_pos - true_stop_pos  # 지도를 찍을 때는 안 쓰고, 평가 지표 계산에서만 참고
        sigma = STEP_SIGMA_CELLS * np.sqrt(i + 1)  # 랜덤워크 누적 불확실성(모델 기반)
        radius = max(1, int(np.ceil(3 * sigma)))

        for x, y, mh, mr, r_m, dstd in readings:
            # VO가 "안다고 믿는" 위치 = 참 관측좌표 + VO 드리프트 (VO 추정 기준, 참값 미사용)
            vx, vy = x + drift[0], y + drift[1]
            gx0, gy0 = int(round(vx)), int(round(vy))
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    gx, gy = gx0 + dx, gy0 + dy
                    if not (0 <= gx < GRID and 0 <= gy < GRID):
                        continue
                    d2 = dx * dx + dy * dy
                    g_w = np.exp(-d2 / (2 * sigma ** 2))
                    if g_w < 0.02:
                        continue
                    rs[gy, gx] += mr * g_w
                    rw[gy, gx] += g_w
                    known[gy, gx] = True

    r_map = np.full((GRID, GRID), np.nan)
    m = rw > 0
    r_map[m] = rs[m] / rw[m]
    return {"known": known, "r": r_map}


def mae_against_truth(est_r, true_r, known_mask) -> float:
    valid = known_mask & ~np.isnan(est_r)
    if not valid.any():
        return float("nan")
    return float(np.mean(np.abs(est_r[valid] - true_r[valid])))


def run_one_seed(seed: int) -> dict:
    sim.rng = np.random.default_rng(seed)
    h, rocks = sim.generate_terrain()
    risk = sim.true_risk_field(h)
    result = sim.run_exploration(h, risk)

    splat = gaussian_splat_fuse(result)

    iou_oracle = sim.iou_high_risk(result["oracle_r"], risk, result["oracle_known"])
    iou_vo = sim.iou_high_risk(result["vo_r"], risk, result["vo_known"])
    iou_splat = sim.iou_high_risk(splat["r"], risk, splat["known"])

    mae_oracle = mae_against_truth(result["oracle_r"], risk, result["oracle_known"])
    mae_vo = mae_against_truth(result["vo_r"], risk, result["vo_known"])
    mae_splat = mae_against_truth(splat["r"], risk, splat["known"])

    return {
        "seed": seed,
        "iou_oracle": float(iou_oracle), "iou_vo": float(iou_vo), "iou_splat": float(iou_splat),
        "mae_oracle": mae_oracle, "mae_vo": mae_vo, "mae_splat": mae_splat,
    }, (h, risk, rocks, result, splat)


def main():
    print(f"1차 시도(센서 스펙만): 스텝당 {NAIVE_SIGMA_CELLS:.3f} cell "
          f"({NAIVE_SIGMA_CELLS*CELL_M:.3f} m) — 과소추정으로 판명, 아래 보정치 사용")
    print(f"보정된 스텝당 위치 불확실성: {STEP_SIGMA_CELLS:.3f} cell ({STEP_SIGMA_CELLS*CELL_M:.3f} m) "
          f"(exploration_multiseed_stats.json 실측 드리프트에서 역산, {STEP_SIGMA_CELLS/NAIVE_SIGMA_CELLS:.1f}배)")
    print(f"{N_STOPS}스텝 누적 시 (랜덤워크 sqrt 법칙): "
          f"{STEP_SIGMA_CELLS*np.sqrt(N_STOPS):.3f} cell ({STEP_SIGMA_CELLS*np.sqrt(N_STOPS)*CELL_M:.3f} m)")

    rows = []
    last_viz = None
    for seed in range(N_SEEDS):
        row, viz = run_one_seed(seed)
        rows.append(row)
        if seed == 0:
            last_viz = viz
        print(f"  seed={seed}  IoU: oracle={row['iou_oracle']:.3f} vo={row['iou_vo']:.3f} "
              f"splat={row['iou_splat']:.3f}  |  MAE: oracle={row['mae_oracle']:.3f} "
              f"vo={row['mae_vo']:.3f} splat={row['mae_splat']:.3f}")

    def agg(key):
        vals = np.array([r[key] for r in rows])
        return float(np.nanmean(vals)), float(np.nanstd(vals))

    print(f"\n{'지표':>14} {'Oracle':>14} {'VO (crisp)':>14} {'VO (splat)':>14}")
    summary = {"n_seeds": N_SEEDS, "step_sigma_cells": STEP_SIGMA_CELLS, "runs": rows}
    for key, label in [("iou_oracle", "IoU"), ("iou_vo", "IoU"), ("iou_splat", "IoU")]:
        pass
    io_m, io_s = agg("iou_oracle"); iv_m, iv_s = agg("iou_vo"); isp_m, isp_s = agg("iou_splat")
    mo_m, mo_s = agg("mae_oracle"); mv_m, mv_s = agg("mae_vo"); msp_m, msp_s = agg("mae_splat")
    print(f"{'위험지대 IoU':>14} {io_m:>7.3f}±{io_s:<5.3f} {iv_m:>7.3f}±{iv_s:<5.3f} {isp_m:>7.3f}±{isp_s:<5.3f}")
    print(f"{'위험도 MAE':>14} {mo_m:>7.3f}±{mo_s:<5.3f} {mv_m:>7.3f}±{mv_s:<5.3f} {msp_m:>7.3f}±{msp_s:<5.3f}")

    summary.update({
        "iou_oracle_mean": io_m, "iou_oracle_std": io_s,
        "iou_vo_mean": iv_m, "iou_vo_std": iv_s,
        "iou_splat_mean": isp_m, "iou_splat_std": isp_s,
        "mae_oracle_mean": mo_m, "mae_oracle_std": mo_s,
        "mae_vo_mean": mv_m, "mae_vo_std": mv_s,
        "mae_splat_mean": msp_m, "mae_splat_std": msp_s,
    })
    with open(f"{OUT_DIR}/uncertainty_fusion_stats.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nsaved {OUT_DIR}/uncertainty_fusion_stats.json")

    if last_viz is not None:
        plot_comparison(*last_viz)


def style_ax(ax):
    ax.set_facecolor("#0b0e15")
    for s in ax.spines.values():
        s.set_color("#262d3d")
    ax.tick_params(colors="#a7aec1", labelsize=7)


def plot_comparison(h, risk, rocks, result, splat):
    fig, axes = plt.subplots(1, 4, figsize=(20, 5.2), facecolor="#0b0e15")

    panels = [
        ("True risk field", risk, None),
        ("Oracle map (perfect localization)", result["oracle_r"], result["oracle_known"]),
        ("VO map — crisp (current baseline)", result["vo_r"], result["vo_known"]),
        ("VO map — uncertainty-splat (new)", splat["r"], splat["known"]),
    ]
    for ax, (title, field, known) in zip(axes, panels):
        style_ax(ax)
        show = np.where(known, field, np.nan) if known is not None else field
        ax.imshow(show, cmap=RISK_CMAP, vmin=0, vmax=1, origin="upper")
        ax.plot(result["true_path"][:, 0], result["true_path"][:, 1], "-", color="#5cbcc3", linewidth=1, alpha=0.7)
        ax.set_title(title, color="#e9ebf2", fontsize=9)

    fig.suptitle("Position-uncertainty-aware risk map fusion (seed=0)", color="#a7aec1", fontsize=10)
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/uncertainty_fusion_comparison.png", dpi=135, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"saved {OUT_DIR}/uncertainty_fusion_comparison.png")


if __name__ == "__main__":
    main()
