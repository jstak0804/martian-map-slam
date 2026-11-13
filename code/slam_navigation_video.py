"""
SLAM 지도 구축 + 시간대별 내비게이션 전체 시연 -- 영상(mp4)으로 저장.

slam_navigation_demo.py와 동일한 시드/로직으로 두 장면을 이어붙인다.
  1장. 탐사 진행 -- 프런티어 탐사가 한 스텝씩 지도를 채워가는 과정 (oracle vs VO 궤적)
  2장. 같은(oracle) SLAM 지도 위에서 시간대(14시 -> 2시)를 따라가며 내비게이션이
       DESTINATION_OK에서 SAFE_ZONE_REDIRECT로 바뀌는 과정

ffmpeg(/usr/bin/ffmpeg)가 설치돼 있어 matplotlib FFMpegWriter로 바로 mp4를 쓴다.
"""
from __future__ import annotations

import os

import numpy as np
from scipy.ndimage import binary_erosion
import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["animation.ffmpeg_path"] = "/usr/bin/ffmpeg"
import matplotlib.pyplot as plt
import matplotlib.animation as animation

import exploration_slam_sim as sim
from exploration_slam_sim import GRID, CELL_M, RISK_CMAP
from human_mission_risk import WARNING_THRESHOLD, SPE_START_HOUR, SPE_END_HOUR
from human_mission_navigation import plan_to_destination, style_ax, _plot_path, _marker
from slam_navigation_demo import risk_from_reconstructed_terrain, _reconstruct_height_maps

OUT_DIR = "../outputs/slam_navigation"
os.makedirs(OUT_DIR, exist_ok=True)

FPS = 10
EDGE_MARGIN = 5


def build_context():
    sim.rng = np.random.default_rng(0)
    h_true, _ = sim.generate_terrain()
    terrain_only_risk = sim.true_risk_field(h_true)
    result = sim.run_exploration(h_true, terrain_only_risk)
    known_o, known_v = result["oracle_known"], result["vo_known"]
    oracle_h, vo_h = _reconstruct_height_maps(result)

    n = GRID
    start = (n // 2, n // 2)
    oracle_risk_day = risk_from_reconstructed_terrain(result["oracle_r"], oracle_h, known_o, 14.0, spe_active=False)
    core_o = binary_erosion(known_o, iterations=EDGE_MARGIN)
    yy, xx = np.mgrid[0:n, 0:n]
    dist_from_start = np.hypot(xx - start[0], yy - start[1])
    candidates_mask = core_o & (dist_from_start > 15)
    risk_candidates = np.where(candidates_mask, oracle_risk_day, np.inf)
    fy, fx = np.unravel_index(np.argmin(risk_candidates), risk_candidates.shape)
    dest = (int(fx), int(fy))
    return result, known_o, oracle_h, start, dest


def known_mask_up_to_step(result, i, n):
    known = np.zeros((n, n), dtype=bool)
    for true_pos, readings in result["all_readings_log"][: i + 1]:
        for x, y, *_ in readings:
            gx, gy = int(round(x)), int(round(y))
            if 0 <= gx < n and 0 <= gy < n:
                known[gy, gx] = True
    return known


def main():
    print("=== SLAM + 내비게이션 시연 영상 생성 ===\n")
    result, known_o, oracle_h, start, dest = build_context()
    n = GRID
    true_path, vo_path = result["true_path"], result["vo_path"]
    n_steps = len(true_path)

    hours = [14.0, 11.0, 8.0, 5.0, 3.0, 2.0]
    HOLD = 16  # 시간대 한 프레임당 유지 프레임 수 (FPS=10 -> 1.6초)
    plans = {}
    risks = {}
    for hr in hours:
        spe_active = SPE_START_HOUR <= hr < SPE_END_HOUR
        risk = risk_from_reconstructed_terrain(result["oracle_r"], oracle_h, known_o, hr, spe_active)
        plan = plan_to_destination(risk, start, dest, WARNING_THRESHOLD, passable=known_o)
        risks[hr] = risk
        plans[hr] = plan
        status = plan["recommendation"]
        mr = plan["direct_stats"]["max_risk"]
        print(f"  hour={hr:>4.1f}  max_risk={mr:.3f}  -> {status}")

    # 프레임 스케줄: (phase, payload)
    frames = [("explore", i) for i in range(n_steps)]
    frames += [("explore", n_steps - 1)] * (FPS)  # 탐사 완료 상태 1초 정지
    for hr in hours:
        frames += [("nav", hr)] * HOLD

    fig, ax = plt.subplots(figsize=(7.4, 6.8), dpi=110, facecolor="#0b0e15")

    def draw_explore(ax, i):
        ax.clear()
        style_ax(ax)
        known = known_mask_up_to_step(result, i, n)
        ax.imshow(known.astype(float), cmap="Greys_r", vmin=0, vmax=1.4, origin="upper")
        tp = true_path[: i + 1]
        vp = vo_path[: i + 1]
        ax.plot(tp[:, 0], tp[:, 1], "-", color="#5cbcc3", linewidth=2.0, label="true path (oracle)")
        ax.plot(vp[:, 0], vp[:, 1], "-", color="#e0ac53", linewidth=2.0, label="VO path (drifted)")
        ax.scatter([tp[-1, 0]], [tp[-1, 1]], color="#5cbcc3", s=70, zorder=5, marker="o")
        ax.scatter([vp[-1, 0]], [vp[-1, 1]], color="#e0ac53", s=70, zorder=5, marker="o")
        cov = known.mean() * 100
        drift = float(np.hypot(*(vp[-1] - tp[-1]))) * CELL_M
        ax.set_title(f"1/2 · Frontier exploration -- step {i+1}/{n_steps}\n"
                     f"coverage {cov:.1f}%, current VO drift {drift:.2f} m",
                     color="#e9ebf2", fontsize=12)
        ax.legend(facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2", fontsize=8, loc="lower right")
        ax.set_xlim(0, n); ax.set_ylim(n, 0)

    def draw_nav(ax, hr):
        ax.clear()
        style_ax(ax)
        risk = risks[hr]
        plan = plans[hr]
        im = ax.imshow(risk, cmap=RISK_CMAP, vmin=0, vmax=1, origin="upper")
        ax.contour((~known_o).astype(float), levels=[0.5], colors="#6d7488", linewidths=1.0, linestyles=":")
        _plot_path(ax, plan["direct_path"], "#a7aec1", style="--", lw=2.0,
                   label=f"direct (max risk={plan['direct_stats']['max_risk']:.2f})")
        if plan["unsafe"] and plan.get("safe_zone_path"):
            _plot_path(ax, plan["safe_zone_path"], "#e0ac53", lw=2.4,
                       label=f"redirected (max risk={plan['safe_zone_stats']['max_risk']:.2f})")
            _marker(ax, plan["safe_zone_path"][-1], "#e0ac53", marker="*", size=140)
        _marker(ax, start, "#5cbcc3", marker="s")
        _marker(ax, dest, "#e9ebf2", marker="X", size=110)
        status = "UNSAFE -> SAFE_ZONE_REDIRECT" if plan["unsafe"] else "DESTINATION_OK"
        ax.set_title(f"2/2 · Same SLAM map, hour {hr:02.0f}:00\nstatus: {status}", color="#e9ebf2", fontsize=12)
        ax.legend(facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2", fontsize=8, loc="lower right")
        ax.set_xlim(0, n); ax.set_ylim(n, 0)

    def update(frame_idx):
        phase, payload = frames[frame_idx]
        if phase == "explore":
            draw_explore(ax, payload)
        else:
            draw_nav(ax, payload)
        return []

    anim = animation.FuncAnimation(fig, update, frames=len(frames), blit=False)
    writer = animation.FFMpegWriter(fps=FPS, bitrate=2200, codec="libx264",
                                     extra_args=["-pix_fmt", "yuv420p"])
    out_path = f"{OUT_DIR}/slam_navigation_demo.mp4"
    anim.save(out_path, writer=writer)
    plt.close(fig)
    print(f"\nsaved {out_path}  ({len(frames)} frames, {len(frames)/FPS:.1f}s)")

    # 포스터 프레임(PPT용) -- 2장(내비게이션) 첫 시간대를 별도 PNG로 저장
    fig2, ax2 = plt.subplots(figsize=(7.4, 6.8), dpi=110, facecolor="#0b0e15")
    draw_nav(ax2, hours[0])
    poster_path = f"{OUT_DIR}/slam_navigation_demo_poster.png"
    fig2.savefig(poster_path, dpi=110, bbox_inches="tight", facecolor=fig2.get_facecolor())
    plt.close(fig2)
    print(f"saved {poster_path}")


if __name__ == "__main__":
    main()
