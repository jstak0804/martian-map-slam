"""
탐사형 SLAM — 다중 시드 반복 (n=1 문제 해결)

exploration_slam_sim.py를 시드 10개로 반복 실행해, 앞서 시드 11 하나에서만 관찰했던
"Oracle IoU 0.800 vs VO IoU 0.091" 결과가 우연인지 일관된 패턴인지 확인한다.
원본 시뮬레이션 코드는 전혀 수정하지 않고, 모듈의 전역 rng만 바꿔치기해서 재사용한다.
"""
import json
import numpy as np
import exploration_slam_sim as sim

OUT_DIR = "../outputs/exploration"
N_SEEDS = 10


def run_one(seed: int) -> dict:
    sim.rng = np.random.default_rng(seed)  # 모듈 전역 rng 교체 -> 이후 호출에 그대로 반영됨

    h, rocks = sim.generate_terrain()
    risk = sim.true_risk_field(h)
    result = sim.run_exploration(h, risk)

    true_path = result["true_path"]
    vo_path = result["vo_path"]
    path_len = float(np.sum(np.hypot(*np.diff(true_path * sim.CELL_M, axis=0).T)))
    final_err = float(np.linalg.norm(true_path[-1] - vo_path[-1]) * sim.CELL_M)
    iou_o = sim.iou_high_risk(result["oracle_r"], risk, result["oracle_known"])
    iou_v = sim.iou_high_risk(result["vo_r"], risk, result["vo_known"])

    return {
        "seed": seed,
        "n_stops": len(result["true_path"]) - 1,
        "path_length_m": path_len,
        "final_pose_error_m": final_err,
        "iou_oracle": float(iou_o),
        "iou_vo": float(iou_v),
    }


def main():
    rows = [run_one(seed) for seed in range(N_SEEDS)]

    print(f"{'seed':>4} {'stops':>6} {'path_m':>8} {'pose_err_m':>11} {'IoU_oracle':>11} {'IoU_vo':>8}")
    for r in rows:
        print(f"{r['seed']:>4} {r['n_stops']:>6} {r['path_length_m']:>8.1f} "
              f"{r['final_pose_error_m']:>11.2f} {r['iou_oracle']:>11.3f} {r['iou_vo']:>8.3f}")

    def agg(key):
        vals = np.array([r[key] for r in rows])
        return float(vals.mean()), float(vals.std())

    summary = {"n_seeds": N_SEEDS, "runs": rows}
    for key in ["path_length_m", "final_pose_error_m", "iou_oracle", "iou_vo"]:
        m, s = agg(key)
        summary[f"{key}_mean"] = m
        summary[f"{key}_std"] = s
        print(f"\n{key}: mean={m:.3f} std={s:.3f}")

    with open(f"{OUT_DIR}/exploration_multiseed_stats.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nsaved {OUT_DIR}/exploration_multiseed_stats.json")


if __name__ == "__main__":
    main()
