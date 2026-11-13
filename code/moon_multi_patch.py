"""
LOLA 달 DEM — 다중 패치 반복 (n=1 문제 해결)

앞서 real_terrain_risk.py는 달 남극 DEM에서 패치 하나(크레이터/능선 지대)만 잘라
"평균 위험도 0.83, 고위험 93.1%"라는 결과를 냈다. 이미 전체 7584x7584 DEM을
다운로드해뒀으므로, 추가 다운로드 없이 서로 다른 9곳을 더 잘라 분포를 확인한다.
"""
import json
import numpy as np

from real_terrain_risk import terrain_risk, CELL_M, SLOPE_HIGH_DEG, ROUGHNESS_HIGH_M

OUT_DIR = "../outputs/real_terrain"
PATCH = 900  # 18km x 18km, 기존 패치와 동일 크기

# 7584x7584 전체에서 가장자리를 피해 3x3 격자로 고르게 샘플링 (가장자리 150px 여백)
STARTS = []
for r in np.linspace(150, 7584 - PATCH - 150, 3):
    for c in np.linspace(150, 7584 - PATCH - 150, 3):
        STARTS.append((int(r), int(c)))


def main():
    print("LOLA 남극 DEM 전체 로딩...")
    arr = np.fromfile("../data/moon_lola/ldem_875s_20m.img", dtype="<i2")
    arr = arr.reshape(7584, 7584).astype(np.float32) * 0.5

    rows = []
    for i, (r0, c0) in enumerate(STARTS):
        patch = arr[r0:r0 + PATCH, c0:c0 + PATCH]
        slope, rough, risk = terrain_risk(patch)
        row = {
            "patch_id": i,
            "row0": r0, "col0": c0,
            "elevation_range_m": [float(patch.min()), float(patch.max())],
            "mean_slope_deg": float(slope.mean()),
            "pct_slope_over_15deg": float((slope > SLOPE_HIGH_DEG).mean() * 100),
            "mean_risk": float(risk.mean()),
            "pct_high_risk": float((risk > 0.5).mean() * 100),
        }
        rows.append(row)
        print(f"  patch {i} @ (row={r0},col={c0}): mean_risk={row['mean_risk']:.3f}  "
              f"high_risk%={row['pct_high_risk']:.1f}  mean_slope={row['mean_slope_deg']:.2f}deg")

    risks = np.array([r["mean_risk"] for r in rows])
    highs = np.array([r["pct_high_risk"] for r in rows])
    print(f"\n패치 {len(rows)}곳 — mean_risk: {risks.mean():.3f} +/- {risks.std():.3f} "
          f"(범위 {risks.min():.3f}~{risks.max():.3f})")
    print(f"고위험 비율: {highs.mean():.1f}% +/- {highs.std():.1f}% (범위 {highs.min():.1f}~{highs.max():.1f}%)")
    print("\n참고: 기존 real_terrain_risk.py가 쓴 패치는 (row0=4600, col0=5200) 근처 "
          "능선/크레이터 밀집 지대로, 아래 9곳 중 가장 험한 축에 속하는지 비교해볼 것.")

    with open(f"{OUT_DIR}/moon_multipatch_stats.json", "w") as f:
        json.dump({
            "patches": rows,
            "mean_risk_overall": float(risks.mean()), "mean_risk_std": float(risks.std()),
            "pct_high_risk_overall": float(highs.mean()), "pct_high_risk_std": float(highs.std()),
            "original_patch_mean_risk": 0.829, "original_patch_pct_high_risk": 93.1,
        }, f, indent=2)
    print(f"\nsaved {OUT_DIR}/moon_multipatch_stats.json")


if __name__ == "__main__":
    main()
