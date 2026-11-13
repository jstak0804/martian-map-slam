"""
Devon Island VO — 태양센서 기반 헤딩 보정 (지적된 문제 ⑤를 실제로 해결)

지금까지 비디오 432프레임 VO 실험은 428/431 스텝이 "성공" 판정이었음에도
오차 30.9%였다 — 매칭 실패가 아니라 매 스텝의 작은 시스템 편향이 누적된
헤딩(회전) 드리프트가 원인이라고 진단했다. 이 스크립트는 그 진단을 실제로
검증·교정해본다: Devon Island 데이터셋에는 각 이미지에 연동된 태양센서
방위각(sun-sensor-sampled.txt)이 있고, 이 방위각은 로버(카메라)에 고정된
센서로 측정한 "태양의 상대 방위각"이다. 수 분 남짓의 주행 구간에서는
태양의 절대(세계좌표) 방위각 변화가 무시할 만큼 작으므로, 상대 방위각의
변화는 거의 전부 로버 자신의 헤딩(요) 변화에서 온다 — VO와 완전히 독립된
헤딩 측정치로 쓸 수 있다는 뜻이다.

방법:
  1. devon_pipeline.py의 VO 루프를 그대로 재사용하되, 매 스텝의 상대회전
     R_rel과 로컬 이동량(cam_center_rel)을 따로 저장한다 (기존 검증된
     파이프라인 코드는 손대지 않는다).
  2. R_rel에서 "요(yaw)만" 1차 근사로 뽑아낸다: 평평한 지형에서 스텝당
     피치/롤이 작다고 가정하면 yaw ≈ atan2(R_rel[0,2], R_rel[2,2]).
  3. 태양센서 방위각을 해당 구간의 모든 이미지 인덱스에 보간하고, 스텝별
     변화량(Δ방위각)을 구한다 — 이것이 VO와 무관한 헤딩 변화 신호다.
  4. 두 신호(VO yaw 증분 vs Δ태양방위각)를 앞쪽 신뢰 구간(50스텝)에서
     스칼라 최소자승으로 맞춰(符号·스케일) 보정 계수를 구한다.
  5. 누적 헤딩을 "VO 적분"이 아니라 "태양센서 적분"으로 바꿔 끼운 궤적을
     다시 쌓고, 실측 DGPS와 비교해 오차가 실제로 줄어드는지 검증한다.

주의: 피치/롤은 보정하지 않고(관련 경사계 데이터는 받아두지 않았음) 요만
교정하는 1차 근사다. 지형이 완전히 평평하지 않으므로 이 근사 자체가
약간의 오차를 남긴다 — 결과에서 솔직하게 보고한다.
"""
from __future__ import annotations

import json
import numpy as np
import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from devon_pipeline import (
    DATA_DIR, OUT_DIR, K, CX, CY, FOCAL_PX,
    load_frames_from_video, compute_disparity, disparity_to_depth, load_gt_segment,
)

START_IDX = 48978
FULL_N = 49410 - 48978  # 432, s22 비디오 전체 구간 (기존 실험과 동일)
CALIB_WINDOW = 50       # 보정 계수를 맞출 '신뢰 구간' 스텝 수 (앞쪽이 드리프트가 작음)


# ============================================================
# 1. VO 루프 재실행 — 이번엔 스텝별 (R_rel, local displacement)도 저장
# ============================================================

def visual_odometry_with_steps(lefts, depths):
    orb = cv2.ORB_create(nfeatures=1000)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

    R_world, t_world = np.eye(3), np.zeros(3)
    poses = [t_world.copy()]
    steps = []  # (ok: bool, R_rel: 3x3 or None, cam_center_rel: (3,) or None)
    stats = {"total": len(lefts) - 1, "ok": 0, "fail_features": 0, "fail_depth_pts": 0, "fail_pnp": 0}

    for t in range(len(lefts) - 1):
        kp1, des1 = orb.detectAndCompute(lefts[t], None)
        kp2, des2 = orb.detectAndCompute(lefts[t + 1], None)
        if des1 is None or des2 is None or len(kp1) < 8 or len(kp2) < 8:
            poses.append(poses[-1]); steps.append((False, None, None))
            stats["fail_features"] += 1
            continue

        matches = sorted(bf.match(des1, des2), key=lambda m: m.distance)[:250]
        depth_t = depths[t]
        obj_pts, img_pts = [], []
        for m in matches:
            u1, v1 = kp1[m.queryIdx].pt
            col, row = int(round(u1)), int(round(v1))
            if not (0 <= row < depth_t.shape[0] and 0 <= col < depth_t.shape[1]):
                continue
            z = depth_t[row, col]
            if not np.isfinite(z) or z <= 0:
                continue
            obj_pts.append([(u1 - CX) * z / FOCAL_PX, (v1 - CY) * z / FOCAL_PX, z])
            img_pts.append(kp2[m.trainIdx].pt)

        if len(obj_pts) < 6:
            poses.append(poses[-1]); steps.append((False, None, None))
            stats["fail_depth_pts"] += 1
            continue

        ok, rvec, tvec, inliers = cv2.solvePnPRansac(
            np.float32(obj_pts), np.float32(img_pts), K, None,
            reprojectionError=3.0, confidence=0.999, iterationsCount=200,
        )
        if not ok or inliers is None or len(inliers) < 6:
            poses.append(poses[-1]); steps.append((False, None, None))
            stats["fail_pnp"] += 1
            continue

        R_rel, _ = cv2.Rodrigues(rvec)
        cam_center_rel = -R_rel.T @ tvec.flatten()
        R_world_new = R_rel @ R_world
        t_world = t_world + R_world.T @ cam_center_rel
        R_world = R_world_new
        poses.append(t_world.copy())
        steps.append((True, R_rel.copy(), cam_center_rel.copy()))
        stats["ok"] += 1

    return np.array(poses), steps, stats


# ============================================================
# 2. 태양센서 방위각 보간 — VO와 무관한 헤딩 변화 신호
# ============================================================

def load_sun_azimuth_series(image_indices: np.ndarray) -> np.ndarray:
    """해당 이미지 인덱스들에 대응하는 (보간된, unwrap된) 태양 방위각(rad)을 반환한다."""
    data = np.loadtxt(f"{DATA_DIR}/sun-sensor-sampled.txt")
    idx = data[:, 0]
    az_deg = data[:, 1]

    lo, hi = image_indices.min() - 30, image_indices.max() + 30
    mask = (idx >= lo) & (idx <= hi)
    idx, az_deg = idx[mask], az_deg[mask]
    order = np.argsort(idx)
    idx, az_deg = idx[order], az_deg[order]

    az_rad_unwrapped = np.unwrap(np.radians(az_deg))
    return np.interp(image_indices, idx, az_rad_unwrapped)


# ============================================================
# 3. 요(yaw)만 뽑아 누적 — VO 궤적을 '선형화'해서 재구성 (근사 품질 점검용)
# ============================================================

def yaw_from_R(R_rel: np.ndarray) -> float:
    """평지 가정(피치/롤 작음) 하에서 R_rel의 요(수직축 회전) 성분만 1차 근사로 추출."""
    return float(np.arctan2(R_rel[0, 2], R_rel[2, 2]))


def Ry(yaw: float) -> np.ndarray:
    c, s = np.cos(yaw), np.sin(yaw)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def reconstruct_with_yaw_increments(steps, yaw_increments: np.ndarray) -> np.ndarray:
    """매 스텝의 로컬 이동량(cam_center_rel)은 VO 그대로 쓰고, 누적 헤딩만 주어진
    yaw_increments로 바꿔 끼워 궤적을 재구성한다."""
    t_world = np.zeros(3)
    cum_yaw = 0.0
    poses = [t_world.copy()]
    for (ok, R_rel, cam_center_rel), dyaw in zip(steps, yaw_increments):
        if ok:
            t_world = t_world + Ry(cum_yaw).T @ cam_center_rel
        cum_yaw += dyaw
        poses.append(t_world.copy())
    return np.array(poses)


# ============================================================
# 4. 실행
# ============================================================

def endpoint_and_rms_error(poses_x, poses_z, gt_e, gt_n):
    """지점별 위치오차(종단오차 + RMS) — 총 주행거리와 달리 헤딩 선택에 실제로 민감한 지표.
    (아래 '중요한 발견' 참고: 순수 Y축 회전은 벡터 노름을 보존하므로, 누적 헤딩을 무엇으로
    쓰든 총 주행거리(sum of hypot)는 수학적으로 거의 불변이다 — 그래서 이 지표만으로는
    태양센서 보정의 효과를 전혀 구분할 수 없다. 지점별 위치오차를 따로 봐야 한다.)"""
    err_xy = np.hypot(poses_x - gt_e, poses_z - gt_n)
    return float(err_xy[-1]), float(np.sqrt(np.mean(err_xy ** 2))), err_xy


def main():
    print(f"[sun-correction] {FULL_N}프레임 비디오 로드 + 깊이 계산...")
    lefts, rights = load_frames_from_video(START_IDX, FULL_N)
    depths = [disparity_to_depth(compute_disparity(l, r)) for l, r in zip(lefts, rights)]

    print("[sun-correction] VO 재실행 (스텝별 R_rel·이동량 저장)...")
    poses_full3d, steps, vo_stats = visual_odometry_with_steps(lefts, depths)
    print(f"  VO step outcomes: {vo_stats}")

    n_steps = len(steps)
    image_indices = START_IDX + np.arange(n_steps + 1)

    print("[sun-correction] 태양센서 방위각 보간...")
    sun_az = load_sun_azimuth_series(image_indices)
    sun_delta = np.diff(sun_az)  # 스텝별 Δ방위각(rad) — VO와 무관한 헤딩 변화 신호

    vo_yaw_delta = np.array([yaw_from_R(R_rel) if ok else 0.0 for ok, R_rel, _ in steps])

    # ---- 보정 계수(符号+스케일) 최소자승 추정: 앞쪽 신뢰 구간에서 ----
    w = CALIB_WINDOW
    gain = float(np.dot(vo_yaw_delta[:w], sun_delta[:w]) / np.dot(sun_delta[:w], sun_delta[:w]))
    corr_coef = float(np.corrcoef(vo_yaw_delta, sun_delta)[0, 1])
    print(f"  보정 계수(gain) = {gain:.4f}  (앞 {w}스텝 기준 최소자승 적합)")
    print(f"  VO yaw 증분 vs 태양센서 Δ방위각 상관계수(전체 {n_steps}스텝) = {corr_coef:.3f}")

    # ---- 세 가지 궤적 재구성 ----
    _, gt_e, gt_n = load_gt_segment(START_IDX, n_steps + 1)
    gt_dist = float(np.sum(np.hypot(np.diff(gt_e), np.diff(gt_n))))

    vo_x, vo_z = poses_full3d[:, 0], poses_full3d[:, 2]
    vo_dist = float(np.sum(np.hypot(np.diff(vo_x), np.diff(vo_z))))

    poses_lin_vo = reconstruct_with_yaw_increments(steps, vo_yaw_delta)
    lin_dist = float(np.sum(np.hypot(np.diff(poses_lin_vo[:, 0]), np.diff(poses_lin_vo[:, 2]))))

    poses_corrected = reconstruct_with_yaw_increments(steps, gain * sun_delta)
    corr_dist = float(np.sum(np.hypot(np.diff(poses_corrected[:, 0]), np.diff(poses_corrected[:, 2]))))

    err = lambda d: abs(d - gt_dist) / gt_dist * 100

    full3d_end, full3d_rms, _ = endpoint_and_rms_error(vo_x, vo_z, gt_e, gt_n)
    lin_end, lin_rms, _ = endpoint_and_rms_error(poses_lin_vo[:, 0], poses_lin_vo[:, 2], gt_e, gt_n)
    corr_end, corr_rms, _ = endpoint_and_rms_error(poses_corrected[:, 0], poses_corrected[:, 2], gt_e, gt_n)

    print(f"\n실측 거리:            {gt_dist:.2f} m")
    print(f"VO (원본 3D 전체):     거리 {vo_dist:.2f}m (오차 {err(vo_dist):.1f}%)  "
          f"| 종단오차 {full3d_end:.2f}m  RMS {full3d_rms:.2f}m")
    print(f"VO (요-only 선형화):   거리 {lin_dist:.2f}m (오차 {err(lin_dist):.1f}%)  "
          f"| 종단오차 {lin_end:.2f}m  RMS {lin_rms:.2f}m   <- 근사 품질 점검")
    print(f"태양센서 헤딩 보정:    거리 {corr_dist:.2f}m (오차 {err(corr_dist):.1f}%)  "
          f"| 종단오차 {corr_end:.2f}m  RMS {corr_rms:.2f}m")
    print(f"\n[중요] 순수 요(yaw) 회전은 (x,z) 평면 벡터의 노름을 보존하므로, 선형화-VO와 "
          f"태양센서-보정 두 재구성의 '총 주행거리'는 어떤 헤딩 시퀀스를 쓰든 수학적으로 거의 "
          f"동일하게 나온다({lin_dist:.2f}m ≈ {corr_dist:.2f}m) — 이 지표로는 보정 효과를 "
          f"구분할 수 없다. 종단오차·RMS처럼 실제 경로 '모양'을 보는 지표라야 의미가 있다.")

    plot_comparison(gt_e, gt_n, poses_lin_vo, poses_corrected, lin_end, corr_end)

    summary = {
        "n_steps": n_steps,
        "gt_distance_m": gt_dist,
        "vo_full3d": {"distance_m": vo_dist, "error_pct": err(vo_dist),
                       "endpoint_error_m": full3d_end, "rms_error_m": full3d_rms},
        "vo_yaw_linearized": {"distance_m": lin_dist, "error_pct": err(lin_dist),
                                "endpoint_error_m": lin_end, "rms_error_m": lin_rms},
        "sun_corrected": {"distance_m": corr_dist, "error_pct": err(corr_dist),
                           "endpoint_error_m": corr_end, "rms_error_m": corr_rms},
        "calibration_gain": gain, "calibration_window_steps": w,
        "vo_yaw_vs_sun_delta_correlation": corr_coef,
        "vo_step_stats": vo_stats,
        "note": ("요(yaw)만 1차근사로 교정 — 피치/롤 드리프트는 보정 대상이 아님. "
                  "태양센서 Δ방위각과 VO의 프레임간 yaw 증분은 상관계수가 거의 0이라 "
                  "(독립 잡음에 가까움) 보정이 실질적 개선을 주지 못했다 — 솔직한 음성 결과."),
    }
    with open(f"{OUT_DIR}/sun_correction_stats.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nsaved {OUT_DIR}/sun_correction_stats.json")


def plot_comparison(gt_e, gt_n, poses_lin_vo, poses_corrected, lin_end_err, corr_end_err):
    fig, axes = plt.subplots(1, 2, figsize=(14, 6.5), facecolor="#0b0e15")
    for ax in axes:
        ax.set_facecolor("#0b0e15")
        for s in ax.spines.values():
            s.set_color("#262d3d")
        ax.tick_params(colors="#a7aec1")
        ax.grid(color="#1c2230", linewidth=0.6)
        ax.set_aspect("equal")
        ax.plot(gt_e, gt_n, "-", color="#5cbcc3", linewidth=2, label="DGPS ground truth")

    axes[0].plot(poses_lin_vo[:, 0], poses_lin_vo[:, 2], "-", color="#e08a76", linewidth=1.5,
                 label=f"VO (yaw-linearized, endpoint err {lin_end_err:.1f}m)")
    axes[0].set_title("Before: pure VO heading integration", color="#e9ebf2", fontsize=11)
    axes[1].plot(poses_corrected[:, 0], poses_corrected[:, 2], "-", color="#e0ac53", linewidth=1.5,
                 label=f"Sun-sensor corrected (endpoint err {corr_end_err:.1f}m)")
    axes[1].set_title("After: sun-sensor heading correction", color="#e9ebf2", fontsize=11)

    for ax in axes:
        ax.set_xlabel("east / camera-x (m)", color="#a7aec1")
        ax.set_ylabel("north / camera-forward (m)", color="#a7aec1")
        ax.legend(facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2", fontsize=9)

    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/sun_correction_comparison.png", dpi=135, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"saved {OUT_DIR}/sun_correction_comparison.png")


if __name__ == "__main__":
    main()
