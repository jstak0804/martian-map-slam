"""
SLAM으로 주변 지형지물을 인식하는 것부터 -> 목적지로 이동 -> 이동 중 위험 재확인 ->
안전지대로 대피까지, 하나의 이어지는 여정으로 보여주는 2D 탑다운 영상.

앞서 만든 두 데모를 하나의 서사로 합친다.
  1. slam_navigation_demo.py 류의 프런티어 탐사(지도를 모르는 상태에서 지형지물을 인식)
  2. human_mission_navigation.py의 목적지 경로탐색(A*)으로 출발
  3. 이동 중간 지점에서 시간이 흘러(출발 시 22시 안전 -> 1시 SPE+한파) 위험도를 다시 확인하고,
     경고선을 넘으면 그 지점 기준으로 새로 안전지대 경로를 계산해 경로를 바꾼다(재계획)
  4. 안전지대 도착

트리거 지점(직행 경로의 30% 지점)은 실제로 안전지대까지 22스텝(5.3m)이 걸리는, 극단적으로
짧지도 길지도 않은 지점을 그대로 골랐다 -- 영상을 위해 경로를 조작하지 않았다.
"""
from __future__ import annotations

import os

import numpy as np
import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["animation.ffmpeg_path"] = "/usr/bin/ffmpeg"
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from scipy.ndimage import binary_erosion

import exploration_slam_sim as sim
from exploration_slam_sim import GRID, CELL_M, RISK_CMAP
from human_mission_risk import WARNING_THRESHOLD, SPE_START_HOUR, SPE_END_HOUR
from human_mission_navigation import astar, nearest_safe_zone_path_minimax, path_stats, style_ax, _marker
from slam_navigation_demo import risk_from_reconstructed_terrain, _reconstruct_height_maps

OUT_DIR = "../outputs/slam_navigation"
os.makedirs(OUT_DIR, exist_ok=True)

FPS = 10
START = (110, 110)
HOUR_DEPART = 22.0   # 출발 시각 -- 안전
HOUR_ALERT = 1.0     # 이동 중 시간이 흘러 바뀐 시각 -- SPE + 극저온
TRIGGER_FRAC = 0.3   # 직행 경로의 이 비율 지점에서 위험 재확인 트리거
ALERT_HOLD = 16
ARRIVAL_HOLD = 16
EXPLORE_STRIDE = 1   # 탐사 스텝을 몇 개씩 묶어 보여줄지(1=매 스텝)


def build_context():
    sim.rng = np.random.default_rng(0)
    h_true, _ = sim.generate_terrain()
    terrain_only_risk = sim.true_risk_field(h_true)
    result = sim.run_exploration(h_true, terrain_only_risk)
    known_o = result["oracle_known"]
    oracle_h, _ = _reconstruct_height_maps(result)
    return known_o, oracle_h, result


def known_mask_up_to_step(result, i, n):
    known = np.zeros((n, n), dtype=bool)
    for true_pos, readings in result["all_readings_log"][: i + 1]:
        for x, y, *_ in readings:
            gx, gy = int(round(x)), int(round(y))
            if 0 <= gx < n and 0 <= gy < n:
                known[gy, gx] = True
    return known


def pick_destination(known_o, start, n):
    core = binary_erosion(known_o, iterations=5)
    yy, xx = np.mgrid[0:n, 0:n]
    dist = np.hypot(xx - start[0], yy - start[1])
    dm = np.where(core, dist, -1)
    fy, fx = np.unravel_index(np.argmax(dm), dm.shape)
    return (int(fx), int(fy))


def build_journey(known_o, oracle_h, result):
    n = GRID
    dest = pick_destination(known_o, START, n)
    risk_depart = risk_from_reconstructed_terrain(result["oracle_r"], oracle_h, known_o, HOUR_DEPART, False)
    direct = astar(risk_depart, START, dest, passable=known_o)
    trigger_idx = int(len(direct) * TRIGGER_FRAC)
    trigger_pos = direct[trigger_idx]

    spe_active = SPE_START_HOUR <= HOUR_ALERT < SPE_END_HOUR
    risk_alert = risk_from_reconstructed_terrain(result["oracle_r"], oracle_h, known_o, HOUR_ALERT, spe_active)
    r_trigger = float(risk_alert[trigger_pos[1], trigger_pos[0]])
    safe_path, path_max = nearest_safe_zone_path_minimax(risk_alert, trigger_pos, WARNING_THRESHOLD, passable=known_o)

    return dict(dest=dest, risk_depart=risk_depart, direct=direct, trigger_idx=trigger_idx,
                trigger_pos=trigger_pos, risk_alert=risk_alert, r_trigger=r_trigger,
                safe_path=safe_path, path_max=path_max)


def main():
    print("=== SLAM 인식 -> 목적지 이동 -> 위험 재확인 -> 대피, 통합 여정 영상 ===\n")
    known_o, oracle_h, result = build_context()
    j = build_journey(known_o, oracle_h, result)
    direct, trig_idx, trig_pos = j["direct"], j["trigger_idx"], j["trigger_pos"]
    safe_path = j["safe_path"]
    dest = j["dest"]
    depart_stats = path_stats(direct[: trig_idx + 1], j["risk_depart"])
    evac_stats = path_stats(safe_path, j["risk_alert"]) if safe_path else None

    print(f"destination: {dest}  (direct path {len(direct)} steps at hour {HOUR_DEPART:.0f}:00)")
    print(f"trigger at step {trig_idx}/{len(direct)} = {trig_pos}  "
          f"risk at hour {HOUR_ALERT:.0f}:00 = {j['r_trigger']:.3f} (threshold {WARNING_THRESHOLD})")
    if safe_path:
        print(f"re-routed to safe zone: {evac_stats['n_steps']} steps, {evac_stats['dist_m']:.2f} m, "
              f"max_risk {evac_stats['max_risk']:.3f}")

    true_path = result["true_path"]
    n_explore = len(true_path)
    n = GRID

    # ---- 프레임 스케줄 ----
    frames = []
    for i in range(0, n_explore, EXPLORE_STRIDE):
        frames.append(("explore", i))
    frames += [("explore", n_explore - 1)] * (FPS // 2)  # 탐사 완료 0.5초 정지
    frames += [("transition", None)] * int(FPS * 1.2)
    for k in range(1, trig_idx + 2):
        frames.append(("depart", k))
    frames += [("alert", None)] * ALERT_HOLD
    if safe_path:
        for k in range(1, len(safe_path) + 1):
            frames.append(("evac", k))
        frames += [("evac", len(safe_path))] * ARRIVAL_HOLD

    print(f"\n총 프레임 {len(frames)} ({len(frames)/FPS:.1f}초)")

    fig, ax = plt.subplots(figsize=(7.4, 7.0), dpi=110, facecolor="#0b0e15")
    cax = fig.add_axes([0.05, 0.05, 0.02, 0.6])

    def draw_frame(ax, cax, i):
        kind, payload = frames[i]
        ax.clear()
        style_ax(ax)

        if kind == "explore":
            known = known_mask_up_to_step(result, payload, n)
            ax.imshow(known.astype(float), cmap="Greys_r", vmin=0, vmax=1.4, origin="upper")
            tp = true_path[: payload + 1]
            ax.plot(tp[:, 0], tp[:, 1], "-", color="#5cbcc3", linewidth=2.0)
            ax.scatter([tp[-1, 0]], [tp[-1, 1]], color="#5cbcc3", s=70, zorder=5, marker="o")
            ax.set_title(f"1/3 · SLAM exploration -- step {payload+1}/{n_explore}\n"
                         f"recognizing surrounding terrain (coverage {known.mean()*100:.1f}%)",
                         color="#e9ebf2", fontsize=12)
            ax.set_xlim(0, n); ax.set_ylim(n, 0)
            cax.clear(); cax.axis("off")
            return

        # 이후 장면은 전부 결합 위험도 히트맵 위에서 진행
        if kind == "transition":
            risk_bg = j["risk_depart"]
        elif kind == "depart":
            risk_bg = j["risk_depart"]
        else:
            risk_bg = j["risk_alert"]

        im = ax.imshow(risk_bg, cmap=RISK_CMAP, vmin=0, vmax=1, origin="upper")
        ax.contour((~known_o).astype(float), levels=[0.5], colors="#6d7488", linewidths=1.0, linestyles=":")
        ax.set_xlim(0, n); ax.set_ylim(n, 0)
        cax.clear()
        im.figure.colorbar(im, cax=cax)
        cax.tick_params(colors="#a7aec1", labelsize=7)
        cax.set_ylabel("combined risk", color="#a7aec1", fontsize=8)

        if kind == "transition":
            _marker(ax, START, "#5cbcc3", marker="s", size=90)
            _marker(ax, dest, "#e9ebf2", marker="X", size=110)
            ax.set_title("2/3 · SLAM map ready -- departing for destination\n"
                         f"hour {HOUR_DEPART:02.0f}:00, risk looks nominal",
                         color="#e9ebf2", fontsize=12.5)
            return

        if kind == "depart":
            k = payload
            shown = direct[:k]
            xs = [p[0] for p in shown]; ys = [p[1] for p in shown]
            ax.plot(xs, ys, "--", color="#a7aec1", linewidth=2.2, zorder=4)
            _marker(ax, direct[0], "#5cbcc3", marker="s", size=80)
            _marker(ax, dest, "#e9ebf2", marker="X", size=110)
            _marker(ax, shown[-1], "#5cbcc3", marker="o", size=90)
            at_trigger = k - 1 >= trig_idx
            status = "RISK CHECK TRIGGERED" if at_trigger else f"EN ROUTE TO DESTINATION ({k}/{len(direct)})"
            color = "#e08a76" if at_trigger else "#a7e8a0"
            ax.set_title(f"2/3 · hour {HOUR_DEPART:02.0f}:00  --  {status}",
                         color=color, fontsize=12.5)
            return

        if kind == "alert":
            xs = [p[0] for p in direct[: trig_idx + 1]]; ys = [p[1] for p in direct[: trig_idx + 1]]
            ax.plot(xs, ys, "--", color="#a7aec1", linewidth=2.2, zorder=4)
            _marker(ax, direct[0], "#5cbcc3", marker="s", size=80)
            _marker(ax, dest, "#e9ebf2", marker="X", size=110)
            _marker(ax, trig_pos, "#e08a76", marker="o", size=110)
            ax.set_title(f"2/3 · time passed -- hour {HOUR_ALERT:02.0f}:00 (SPE)\n"
                         f"risk here {j['r_trigger']:.2f} >= {WARNING_THRESHOLD} -- REPLANNING to nearest safe zone",
                         color="#e08a76", fontsize=12.5)
            return

        # evac
        k = payload
        xs0 = [p[0] for p in direct[: trig_idx + 1]]; ys0 = [p[1] for p in direct[: trig_idx + 1]]
        ax.plot(xs0, ys0, "--", color="#6d7488", linewidth=1.8, zorder=3)
        _marker(ax, direct[0], "#5cbcc3", marker="s", size=70)
        _marker(ax, dest, "#e9ebf2", marker="X", size=100)
        shown = safe_path[:k]
        xs = [p[0] for p in shown]; ys = [p[1] for p in shown]
        ax.plot(xs, ys, "-", color="#e0ac53", linewidth=2.6, zorder=4)
        _marker(ax, trig_pos, "#e08a76", marker="o", size=80)
        _marker(ax, shown[-1], "#e0ac53", marker="o", size=100)
        reached = k >= len(safe_path)
        status = "SAFE ZONE REACHED" if reached else f"EVACUATING ({k}/{len(safe_path)})"
        color = "#5cbcc3" if reached else "#e08a76"
        ax.set_title(f"3/3 · hour {HOUR_ALERT:02.0f}:00 (SPE)  --  {status}",
                     color=color, fontsize=12.5)

    def update(i):
        draw_frame(ax, cax, i)
        return []

    anim = animation.FuncAnimation(fig, update, frames=len(frames), blit=False)
    writer = animation.FFMpegWriter(fps=FPS, bitrate=2400, codec="libx264",
                                     extra_args=["-pix_fmt", "yuv420p"])
    out_path = f"{OUT_DIR}/slam_to_evac_journey.mp4"
    anim.save(out_path, writer=writer)
    plt.close(fig)
    print(f"\nsaved {out_path}  ({len(frames)} frames, {len(frames)/FPS:.1f}s)")

    fig2, ax2 = plt.subplots(figsize=(7.4, 7.0), dpi=110, facecolor="#0b0e15")
    cax2 = fig2.add_axes([0.05, 0.05, 0.02, 0.6])
    alert_idx = next(i for i, (k, p) in enumerate(frames) if k == "alert")
    draw_frame(ax2, cax2, alert_idx)
    poster_path = f"{OUT_DIR}/slam_to_evac_journey_poster.png"
    fig2.savefig(poster_path, dpi=110, facecolor=fig2.get_facecolor())
    plt.close(fig2)
    print(f"saved {poster_path}")


if __name__ == "__main__":
    main()
