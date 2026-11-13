"""
주변 탐사형 SLAM — 애니메이션 렌더러

exploration_slam_sim.py의 시뮬레이션 결과(동일 시드 -> 완전히 동일한 지형/경로/스캔)를
그대로 재사용해, 46회 정지-스캔이 진행되며 Oracle 지도와 VO 지도가 어떻게 갈라지는지
프레임 단위로 렌더링하고 mp4로 묶는다. 시뮬레이션 로직 자체는 건드리지 않는다.
"""
from __future__ import annotations

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation

from exploration_slam_sim import (
    generate_terrain, true_risk_field, run_exploration, scan_from,
    GRID, CELL_M, RISK_CMAP, style_ax, MAST_HEIGHT_M,
)

OUT_DIR = "../outputs/exploration"
import os
os.makedirs(OUT_DIR, exist_ok=True)

N_INTERP = 3  # 정지 사이 보간 프레임 수 (이동하는 모습을 보여주기 위함)
FPS = 7


def recover_headings(true_path: np.ndarray) -> np.ndarray:
    """true_path의 연속된 점으로부터, 각 정지에서 스캔할 때 썼던 heading을 복원한다."""
    headings = [0.0]
    for i in range(1, len(true_path)):
        d = true_path[i] - true_path[i - 1]
        headings.append(np.degrees(np.arctan2(d[0], -d[1])) % 360)
    return np.array(headings)


def build_frame_plan(result):
    """각 정지(scan)와 그 사이 이동(move)을 프레임 단위 계획으로 펼친다."""
    true_path = result["true_path"]
    vo_path = result["vo_path"]
    headings = recover_headings(true_path)
    n_stops = len(result["all_readings_log"])

    plan = []  # list of dicts: {kind, step, true_pos, vo_pos, heading}
    for step in range(n_stops):
        plan.append({"kind": "scan", "step": step, "true_pos": true_path[step],
                     "vo_pos": vo_path[step], "heading": headings[step]})
        if step + 1 < len(true_path):
            p0, p1 = true_path[step], true_path[step + 1]
            v0, v1 = vo_path[step], vo_path[step + 1]
            for k in range(1, N_INTERP + 1):
                t = k / N_INTERP
                plan.append({"kind": "move", "step": step,
                             "true_pos": p0 + (p1 - p0) * t,
                             "vo_pos": v0 + (v1 - v0) * t,
                             "heading": headings[step]})
    return plan


def incremental_maps(result):
    """매 스텝 이후의 oracle/vo 누적 지도 상태를 리스트로 반환 (인덱스 = step 번호)."""
    hs_o = np.zeros((GRID, GRID)); hw_o = np.zeros((GRID, GRID))
    rs_o = np.zeros((GRID, GRID)); rw_o = np.zeros((GRID, GRID))
    hs_v = np.zeros((GRID, GRID)); hw_v = np.zeros((GRID, GRID))
    rs_v = np.zeros((GRID, GRID)); rw_v = np.zeros((GRID, GRID))

    true_path = result["true_path"]
    vo_path = result["vo_path"]
    snapshots = []

    for i, (true_stop_pos, readings) in enumerate(result["all_readings_log"]):
        drift = vo_path[i] - true_path[i]
        for x, y, mh, mr, r_m, dstd in readings:
            w = 1.0 / (dstd ** 2)
            gx, gy = int(round(x)), int(round(y))
            if 0 <= gx < GRID and 0 <= gy < GRID:
                hs_o[gy, gx] += mh * w; hw_o[gy, gx] += w
                rs_o[gy, gx] += mr; rw_o[gy, gx] += 1
            gx2, gy2 = int(round(x + drift[0])), int(round(y + drift[1]))
            if 0 <= gx2 < GRID and 0 <= gy2 < GRID:
                hs_v[gy2, gx2] += mh * w; hw_v[gy2, gx2] += w
                rs_v[gy2, gx2] += mr; rw_v[gy2, gx2] += 1

        r_o = np.full((GRID, GRID), np.nan); m = rw_o > 0; r_o[m] = rs_o[m] / rw_o[m]
        r_v = np.full((GRID, GRID), np.nan); m2 = rw_v > 0; r_v[m2] = rs_v[m2] / rw_v[m2]
        snapshots.append((r_o.copy(), r_v.copy()))

    return snapshots


def render_video(h, risk, rocks, result):
    plan = build_frame_plan(result)
    maps_by_step = incremental_maps(result)
    true_path = result["true_path"]
    vo_path = result["vo_path"]

    fig, axes = plt.subplots(1, 3, figsize=(16.5, 6), facecolor="#0b0e15")
    for ax in axes:
        style_ax(ax)

    ax_scene, ax_oracle, ax_vo = axes

    def draw_static_rocks(ax, color="#e08a76", alpha=0.6):
        for cx, cy, r, _ in rocks:
            ax.add_patch(plt.Circle((cx, cy), r, fill=False, color=color, linewidth=0.8, alpha=alpha))

    def frame_at(i):
        f = plan[i]
        step = f["step"]
        oracle_r, vo_r = maps_by_step[step] if step < len(maps_by_step) else maps_by_step[-1]
        path_so_far = true_path[: step + 2] if f["kind"] == "scan" else true_path[: step + 1]
        vo_path_so_far = vo_path[: step + 2] if f["kind"] == "scan" else vo_path[: step + 1]
        return f, oracle_r, vo_r, path_so_far, vo_path_so_far

    def update(i):
        for ax in axes:
            ax.cla()
            style_ax(ax)

        f, oracle_r, vo_r, path_so_far, vo_path_so_far = frame_at(i)
        rover_true = f["true_pos"]
        rover_vo = f["vo_pos"]

        # ---- left: true scene ----
        ax_scene.imshow(h, cmap="copper", origin="upper")
        draw_static_rocks(ax_scene)
        ax_scene.plot(path_so_far[:, 0], path_so_far[:, 1], "-", color="#5cbcc3", linewidth=1.4)
        if f["kind"] == "scan":
            _, rays = scan_from(h, risk, rover_true, f["heading"], record_rays=True)
            for ray in rays:
                xs = [p[0] for p in ray]; ys = [p[1] for p in ray]; vis = [p[2] for p in ray]
                for k in range(len(xs) - 1):
                    c = "#5cbcc3" if vis[k] else "#e08a76"
                    ax_scene.plot(xs[k:k+2], ys[k:k+2], color=c, linewidth=0.6, alpha=0.55)
        ax_scene.plot(*true_path[0], "o", color="#e0ac53", markersize=8)
        ax_scene.plot(*rover_true, "o", color="#e9ebf2", markersize=7, markeredgecolor="#5cbcc3", markeredgewidth=1.5)
        ax_scene.set_title(f"Live scene — stop {f['step']+1}/{len(result['all_readings_log'])} "
                            f"({'scanning' if f['kind']=='scan' else 'moving'})", color="#e9ebf2", fontsize=10.5)
        ax_scene.set_xlim(0, GRID); ax_scene.set_ylim(GRID, 0)

        # ---- middle: oracle map ----
        ax_oracle.imshow(h, cmap="gray", origin="upper", alpha=0.3)
        masked_o = np.ma.masked_invalid(oracle_r)
        ax_oracle.imshow(masked_o, cmap=RISK_CMAP, vmin=0, vmax=1, origin="upper")
        draw_static_rocks(ax_oracle, color="#e9ebf2", alpha=0.45)
        ax_oracle.plot(path_so_far[:, 0], path_so_far[:, 1], "-", color="#5cbcc3", linewidth=1.1)
        ax_oracle.plot(*rover_true, "o", color="#e9ebf2", markersize=6, markeredgecolor="#5cbcc3", markeredgewidth=1.3)
        ax_oracle.set_title("Oracle map (perfect localization)", color="#e9ebf2", fontsize=10.5)
        ax_oracle.set_xlim(0, GRID); ax_oracle.set_ylim(GRID, 0)

        # ---- right: VO map (drift) ----
        ax_vo.imshow(h, cmap="gray", origin="upper", alpha=0.22)
        masked_v = np.ma.masked_invalid(vo_r)
        ax_vo.imshow(masked_v, cmap=RISK_CMAP, vmin=0, vmax=1, origin="upper")
        draw_static_rocks(ax_vo, color="#e9ebf2", alpha=0.45)
        ax_vo.plot(vo_path_so_far[:, 0], vo_path_so_far[:, 1], "-", color="#e08a76", linewidth=1.1)
        ax_vo.plot(*rover_vo, "o", color="#e9ebf2", markersize=6, markeredgecolor="#e08a76", markeredgewidth=1.3)
        pose_err = np.linalg.norm(rover_vo - rover_true) * CELL_M
        ax_vo.set_title(f"VO map (drift) — pose err {pose_err:.2f} m", color="#e9ebf2", fontsize=10.5)
        ax_vo.set_xlim(0, GRID); ax_vo.set_ylim(GRID, 0)

        fig.suptitle("Exploration SLAM — stop-scan-move cycle", color="#a7aec1", fontsize=9, y=0.995)
        return []

    ani = animation.FuncAnimation(fig, update, frames=len(plan), blit=False)
    out_path = f"{OUT_DIR}/exploration_animation.mp4"
    writer = animation.FFMpegWriter(fps=FPS, bitrate=2600)
    ani.save(out_path, writer=writer, dpi=120)
    plt.close(fig)
    print(f"saved {out_path}  ({len(plan)} frames @ {FPS}fps = {len(plan)/FPS:.1f}s)")
    return out_path


def main():
    h, rocks = generate_terrain()
    risk = true_risk_field(h)
    result = run_exploration(h, risk)
    render_video(h, risk, rocks, result)


if __name__ == "__main__":
    main()
