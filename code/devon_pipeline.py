"""
Devon Island Rover Navigation Dataset — 스테레오 Visual Odometry 파이프라인

두 가지 입력 소스를 동일한 파이프라인으로 처리한다:
  - "stills" : 원본 아카이브의 개별 PGM 스테레오 쌍 (seq22.zip)
  - "video"  : 같은 구간을 담은 압축 MPEG 비디오 (sequence-22.mpg, 좌우 합성 1024x384)

두 소스 모두 실제 DGPS 위치(gps-topocentric.txt)와 대조해 정확도를 검증한다.
"""
from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass

import cv2
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

DATA_DIR = "../data/devon_island"
OUT_DIR = "../outputs"

# ---- 실제 카메라 캘리브레이션 (notes.txt, grey-rectified 512x384) ----
BASELINE_M = 0.239977002
FOCAL_PX = 387.599884033
CX = 253.755615234
CY = 185.114852905
K = np.array([[FOCAL_PX, 0, CX], [0, FOCAL_PX, CY], [0, 0, 1]])


# ============================================================
# 1. 프레임 로딩 — stills(zip) vs video, 두 경로를 동일한 반환 형태로
# ============================================================

def load_frames_from_zip(start_idx: int, n_frames: int, zip_name: str = "seq22.zip"):
    """원본 PGM 스테레오 쌍을 zip에서 직접 읽는다 (무압축, 가장 정밀한 기준)."""
    z = zipfile.ZipFile(f"{DATA_DIR}/{zip_name}")
    lefts, rights = [], []
    for i in range(start_idx, start_idx + n_frames):
        ldata = np.frombuffer(z.read(f"grey-rectified-left-0{i}.pgm"), dtype=np.uint8)
        rdata = np.frombuffer(z.read(f"grey-rectified-right-0{i}.pgm"), dtype=np.uint8)
        lefts.append(cv2.imdecode(ldata, cv2.IMREAD_GRAYSCALE))
        rights.append(cv2.imdecode(rdata, cv2.IMREAD_GRAYSCALE))
    return lefts, rights


def load_frames_from_video(start_idx: int, n_frames: int, video_name: str = "sequence-22.mpg",
                            video_start_idx: int = 48978):
    """압축 비디오(좌우 1024x384 합성)를 디코딩해 동일한 (lefts, rights) 형태로 반환한다.
    비디오의 frame N은 실제 image index (video_start_idx + N)에 대응 — 프레임 좌하단에
    이 인덱스가 번인(burn-in)되어 있어 시각적으로도 검증 가능하다."""
    cap = cv2.VideoCapture(f"{DATA_DIR}/{video_name}")
    video_frame_offset = start_idx - video_start_idx
    cap.set(cv2.CAP_PROP_POS_FRAMES, video_frame_offset)

    lefts, rights = [], []
    for _ in range(n_frames):
        ok, frame = cap.read()
        if not ok:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        half = w // 2
        lefts.append(gray[:, :half])
        rights.append(gray[:, half:])
    cap.release()
    return lefts, rights


# ============================================================
# 2. 스테레오 깊이
# ============================================================

def compute_disparity(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    stereo = cv2.StereoSGBM_create(
        minDisparity=0, numDisparities=64, blockSize=7,
        P1=8 * 1 * 7 ** 2, P2=32 * 1 * 7 ** 2,
        disp12MaxDiff=1, uniquenessRatio=10,
        speckleWindowSize=80, speckleRange=2,
    )
    return stereo.compute(left, right).astype(np.float32) / 16.0


def disparity_to_depth(disp: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore"):
        depth = (BASELINE_M * FOCAL_PX) / disp
    depth[disp <= 0.5] = np.nan
    depth[depth > 30] = np.nan  # 30m 밖은 노이즈로 간주
    return depth


# ============================================================
# 3. Visual Odometry — ORB 매칭 + 3D-2D PnP (실스케일, 임의 보폭 가정 없음)
# ============================================================

def visual_odometry(lefts: list[np.ndarray], depths: list[np.ndarray], verbose: bool = False) -> tuple[np.ndarray, dict]:
    orb = cv2.ORB_create(nfeatures=1000)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

    R_world, t_world = np.eye(3), np.zeros(3)
    poses = [t_world.copy()]
    stats = {"total": len(lefts) - 1, "ok": 0, "fail_features": 0, "fail_depth_pts": 0, "fail_pnp": 0}

    for t in range(len(lefts) - 1):
        kp1, des1 = orb.detectAndCompute(lefts[t], None)
        kp2, des2 = orb.detectAndCompute(lefts[t + 1], None)
        if des1 is None or des2 is None or len(kp1) < 8 or len(kp2) < 8:
            poses.append(poses[-1])
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
            poses.append(poses[-1])
            stats["fail_depth_pts"] += 1
            continue

        ok, rvec, tvec, inliers = cv2.solvePnPRansac(
            np.float32(obj_pts), np.float32(img_pts), K, None,
            reprojectionError=3.0, confidence=0.999, iterationsCount=200,
        )
        if not ok or inliers is None or len(inliers) < 6:
            poses.append(poses[-1])
            stats["fail_pnp"] += 1
            continue

        R_rel, _ = cv2.Rodrigues(rvec)
        R_world_new = R_rel @ R_world
        cam_center_rel = -R_rel.T @ tvec.flatten()
        t_world = t_world + R_world.T @ cam_center_rel
        R_world = R_world_new
        poses.append(t_world.copy())
        stats["ok"] += 1

    if verbose:
        print(f"  VO step outcomes: {stats}")
    return np.array(poses), stats


# ============================================================
# 4. Ground truth
# ============================================================

def load_gt_segment(start_idx: int, n_frames: int):
    idx, east, north = [], [], []
    with open(f"{DATA_DIR}/gps-topocentric.txt") as f:
        for line in f:
            p = line.split()
            i = int(p[0])
            if start_idx <= i < start_idx + n_frames:
                idx.append(i)
                east.append(float(p[1]))
                north.append(float(p[2]))
    east, north = np.array(east), np.array(north)
    return idx, east - east[0], north - north[0]


# ============================================================
# 5. 실험 실행
# ============================================================

@dataclass
class ExperimentResult:
    label: str
    n_frames: int
    gt_east: np.ndarray
    gt_north: np.ndarray
    vo_x: np.ndarray
    vo_z: np.ndarray
    gt_distance_m: float
    vo_distance_m: float
    sample_frame: np.ndarray
    vo_stats: dict


def run_experiment(label: str, lefts, rights, start_idx: int) -> ExperimentResult:
    n = len(lefts)
    print(f"[{label}] {n}개 프레임 로드됨, 깊이 계산 중...")
    depths = [disparity_to_depth(compute_disparity(l, r)) for l, r in zip(lefts, rights)]

    print(f"[{label}] Visual Odometry 추정 중...")
    poses, vo_stats = visual_odometry(lefts, depths, verbose=True)
    vo_x, vo_z = poses[:, 0], poses[:, 2]
    vo_dist = float(np.sum(np.hypot(np.diff(vo_x), np.diff(vo_z))))

    _, gt_e, gt_n = load_gt_segment(start_idx, n)
    gt_dist = float(np.sum(np.hypot(np.diff(gt_e), np.diff(gt_n))))

    print(f"[{label}] 실측 {gt_dist:.2f}m vs VO추정 {vo_dist:.2f}m "
          f"(오차 {abs(vo_dist - gt_dist) / gt_dist * 100:.1f}%)")

    return ExperimentResult(label, n, gt_e, gt_n, vo_x, vo_z, gt_dist, vo_dist, lefts[len(lefts) // 2], vo_stats)


def plot_comparison(results: list[ExperimentResult], out_path: str):
    fig, axes = plt.subplots(1, len(results), figsize=(7 * len(results), 6.5), facecolor="#0b0e15")
    if len(results) == 1:
        axes = [axes]
    for ax, r in zip(axes, results):
        ax.set_facecolor("#0b0e15")
        for s in ax.spines.values():
            s.set_color("#262d3d")
        ax.tick_params(colors="#a7aec1")
        ax.plot(r.gt_east, r.gt_north, "-", color="#5cbcc3", linewidth=2, label=f"DGPS ground truth ({r.n_frames} pts)")
        ax.plot(r.vo_x, r.vo_z, "-", color="#e08a76", linewidth=1.5, label=f"VO estimate ({r.n_frames} pts)")
        err_pct = abs(r.vo_distance_m - r.gt_distance_m) / r.gt_distance_m * 100
        ax.set_title(
            f"{r.label}\nreal {r.gt_distance_m:.1f}m vs VO {r.vo_distance_m:.1f}m (err {err_pct:.1f}%)",
            color="#e9ebf2", fontsize=11,
        )
        ax.set_xlabel("east / camera-x (m)", color="#a7aec1")
        ax.set_ylabel("north / camera-forward (m)", color="#a7aec1")
        ax.legend(facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2", fontsize=9)
        ax.grid(color="#1c2230", linewidth=0.6)
        ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(out_path, dpi=135, bbox_inches="tight", facecolor=fig.get_facecolor())
    print("saved", out_path)


def main():
    START_IDX = 48978
    GT_LAST_IDX = 49410  # gps-topocentric.txt 상 s22 구간의 마지막 인덱스
    FULL_N = GT_LAST_IDX - START_IDX  # 432 프레임 (full s22 range)

    # ---- 실험 A: 원본 무압축 PGM 스틸컷, 짧은 구간(25프레임) ----
    lefts_a, rights_a = load_frames_from_zip(START_IDX, 25)
    result_a = run_experiment("A. Stills (PGM, 25 frames)", lefts_a, rights_a, START_IDX)

    # ---- 실험 B: 압축 비디오, 전체 구간(432프레임) ----
    lefts_b, rights_b = load_frames_from_video(START_IDX, FULL_N)
    result_b = run_experiment(f"B. Video (MPEG, {len(lefts_b)} frames)", lefts_b, rights_b, START_IDX)

    plot_comparison([result_a, result_b], f"{OUT_DIR}/stills_vs_video.png")

    summary = {
        "stills_25frame": {
            "n_frames": result_a.n_frames,
            "gt_distance_m": result_a.gt_distance_m,
            "vo_distance_m": result_a.vo_distance_m,
            "error_pct": abs(result_a.vo_distance_m - result_a.gt_distance_m) / result_a.gt_distance_m * 100,
            "vo_step_stats": result_a.vo_stats,
        },
        "video_full_segment": {
            "n_frames": result_b.n_frames,
            "gt_distance_m": result_b.gt_distance_m,
            "vo_distance_m": result_b.vo_distance_m,
            "error_pct": abs(result_b.vo_distance_m - result_b.gt_distance_m) / result_b.gt_distance_m * 100,
            "vo_step_stats": result_b.vo_stats,
        },
    }
    with open(f"{OUT_DIR}/stills_vs_video_stats.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
