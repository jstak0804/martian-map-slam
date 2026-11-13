"""
slam_to_evac_journey_video.py를 한 사이클 더 반복한 버전 -- 영상 하나에 다음을 전부 담는다.

  1. SLAM 지형지물 인식(탐사)
  2. [1차] 같은 목적지로 출발(22시, 안전) -> 이동 중 시간 경과(1시, SPE) -> 위험 재확인 ->
     1차 안전지대로 대피
  3. 대기(시간이 더 흘러 2,3,4시 -- 다시 안전해질 때까지 그 자리에서 위험도 재확인)
  4. [2차] 다시 안전해진 뒤(4시) 같은 목적지를 향해 재출발 -> 이동 중 또 시간 경과(다음
     주기의 1시, SPE) -> 위험 재확인 -> 2차 안전지대로 대피

두 사이클 모두 "직행 경로의 30% 지점에서 그 시점 기준으로 위험을 재확인한다"는 동일한
규칙을 그대로 적용했다 -- 2차 사이클의 대피가 더 짧게(4스텝, 0.68m) 나온 것도 연출로 늘리지
않고 실제 계산값 그대로 썼다.
"""
from __future__ import annotations

import os

import numpy as np
import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["animation.ffmpeg_path"] = "/usr/bin/ffmpeg"
import matplotlib.pyplot as plt
import matplotlib.animation as animation

import exploration_slam_sim as sim
from exploration_slam_sim import GRID, RISK_CMAP
from human_mission_risk import WARNING_THRESHOLD, SPE_START_HOUR, SPE_END_HOUR
from human_mission_navigation import astar, nearest_safe_zone_path_minimax, path_stats, style_ax, _marker
from slam_navigation_demo import risk_from_reconstructed_terrain
from slam_to_evac_journey_video import START, build_context, known_mask_up_to_step, pick_destination

OUT_DIR = "../outputs/slam_navigation"
os.makedirs(OUT_DIR, exist_ok=True)

FPS = 10
TRIGGER_FRAC = 0.3
ALERT_HOLD = 14
ARRIVAL_HOLD = 12
WAIT_HOLD = 11  # 대기 중 시간대 한 틱당 유지 프레임 수

# (출발 시각, 경고 시각) -- 2차 사이클의 "경고 시각"은 다음 주기의 SPE 창(1시)을 다시 쓴다.
LEG_PLAN = [
    dict(hour_depart=22.0, hour_alert=1.0, label="LEG 1"),
    dict(hour_depart=4.0, hour_alert=1.0, label="LEG 2"),
]
WAIT_HOURS = [2.0, 3.0, 4.0]  # 1차 대피 후 다시 안전해질 때까지 확인하는 시간대


def risk_at(result, oracle_h, known_o, hour):
    spe_active = SPE_START_HOUR <= hour < SPE_END_HOUR
    return risk_from_reconstructed_terrain(result["oracle_r"], oracle_h, known_o, hour, spe_active), spe_active


def plan_legs(known_o, oracle_h, result, dest):
    legs = []
    pos = START
    for cfg in LEG_PLAN:
        risk_depart, _ = risk_at(result, oracle_h, known_o, cfg["hour_depart"])
        direct = astar(risk_depart, pos, dest, passable=known_o)
        trig_idx = int(len(direct) * TRIGGER_FRAC)
        trig_pos = direct[trig_idx]
        risk_alert, spe_active = risk_at(result, oracle_h, known_o, cfg["hour_alert"])
        r_trig = float(risk_alert[trig_pos[1], trig_pos[0]])
        safe_path, path_max = nearest_safe_zone_path_minimax(risk_alert, trig_pos, WARNING_THRESHOLD, passable=known_o)
        legs.append(dict(
            label=cfg["label"], start=pos, dest=dest,
            hour_depart=cfg["hour_depart"], risk_depart=risk_depart,
            direct=direct, trig_idx=trig_idx, trig_pos=trig_pos,
            hour_alert=cfg["hour_alert"], risk_alert=risk_alert, spe_active=spe_active,
            r_trig=r_trig, safe_path=safe_path,
        ))
        pos = safe_path[-1] if safe_path else trig_pos
    return legs


def main():
    print("=== SLAM 인식 -> [출발-대피] 2회 반복, 하나의 영상 ===\n")
    known_o, oracle_h, result = build_context()
    n = GRID
    dest = pick_destination(known_o, START, n)
    legs = plan_legs(known_o, oracle_h, result, dest)

    for i, leg in enumerate(legs, 1):
        st = path_stats(leg["direct"][: leg["trig_idx"] + 1], leg["risk_depart"])
        print(f"[{leg['label']}] depart {leg['start']} -> dest {dest} at hour {leg['hour_depart']:.0f}:00 "
              f"({len(leg['direct'])} steps)")
        print(f"   trigger at step {leg['trig_idx']}/{len(leg['direct'])} = {leg['trig_pos']}, "
              f"risk at hour {leg['hour_alert']:.0f}:00 = {leg['r_trig']:.3f}")
        if leg["safe_path"]:
            sst = path_stats(leg["safe_path"], leg["risk_alert"])
            print(f"   -> evacuate {sst['n_steps']} steps, {sst['dist_m']:.2f} m to {leg['safe_path'][-1]}\n")

    true_path = result["true_path"]
    n_explore = len(true_path)

    # ---- 프레임 스케줄 ----
    frames = []
    for i in range(n_explore):
        frames.append(("explore", i))
    frames += [("explore", n_explore - 1)] * (FPS // 2)
    frames += [("transition", legs[0])] * int(FPS * 1.1)

    for li, leg in enumerate(legs):
        direct, trig_idx = leg["direct"], leg["trig_idx"]
        for k in range(1, trig_idx + 2):
            frames.append(("depart", (leg, k)))
        frames += [("alert", leg)] * ALERT_HOLD
        safe_path = leg["safe_path"]
        if safe_path:
            for k in range(1, len(safe_path) + 1):
                frames.append(("evac", (leg, k)))
            frames += [("evac", (leg, len(safe_path)))] * ARRIVAL_HOLD

        if li == 0:  # 1차 대피 후 -- 다시 안전해질 때까지 대기하며 재확인
            pos = safe_path[-1]
            for hr in WAIT_HOURS:
                risk_wait, spe_wait = risk_at(result, oracle_h, known_o, hr)
                r_here = float(risk_wait[pos[1], pos[0]])
                frames += [("wait", (pos, hr, risk_wait, r_here, spe_wait))] * WAIT_HOLD
            frames += [("transition", legs[1])] * int(FPS * 1.1)

    print(f"총 프레임 {len(frames)} ({len(frames)/FPS:.1f}초)")

    fig, ax = plt.subplots(figsize=(7.4, 7.0), dpi=110, facecolor="#0b0e15")
    cax = fig.add_axes([0.05, 0.05, 0.02, 0.6])

    def draw_risk_bg(ax, cax, risk_grid):
        im = ax.imshow(risk_grid, cmap=RISK_CMAP, vmin=0, vmax=1, origin="upper")
        ax.contour((~known_o).astype(float), levels=[0.5], colors="#6d7488", linewidths=1.0, linestyles=":")
        ax.set_xlim(0, n); ax.set_ylim(n, 0)
        cax.clear()
        im.figure.colorbar(im, cax=cax)
        cax.tick_params(colors="#a7aec1", labelsize=7)
        cax.set_ylabel("combined risk", color="#a7aec1", fontsize=8)

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
            ax.set_title(f"SLAM exploration -- step {payload+1}/{n_explore}\n"
                         f"recognizing surrounding terrain (coverage {known.mean()*100:.1f}%)",
                         color="#e9ebf2", fontsize=12)
            ax.set_xlim(0, n); ax.set_ylim(n, 0)
            cax.clear(); cax.axis("off")
            return

        if kind == "transition":
            leg = payload
            draw_risk_bg(ax, cax, leg["risk_depart"])
            _marker(ax, leg["start"], "#5cbcc3", marker="s", size=90)
            _marker(ax, dest, "#e9ebf2", marker="X", size=110)
            tag = "map ready -- departing" if leg["label"] == "LEG 1" else "safe again -- resuming toward destination"
            ax.set_title(f"{leg['label']}: {tag}\nhour {leg['hour_depart']:02.0f}:00, risk looks nominal",
                         color="#e9ebf2", fontsize=12.5)
            return

        if kind == "wait":
            pos, hr, risk_wait, r_here, spe_wait = payload
            draw_risk_bg(ax, cax, risk_wait)
            _marker(ax, pos, "#5cbcc3", marker="s", size=90)
            _marker(ax, dest, "#e9ebf2", marker="X", size=110)
            ok = r_here < WARNING_THRESHOLD
            spe_tag = " (SPE)" if spe_wait else ""
            status = "safe again" if ok else "still above threshold"
            color = "#a7e8a0" if ok else "#e08a76"
            ax.set_title(f"STANDBY at safe zone -- hour {hr:02.0f}:00{spe_tag}\n"
                         f"risk here {r_here:.2f} ({'<' if ok else '>='} {WARNING_THRESHOLD}) -- {status}",
                         color=color, fontsize=12.5)
            return

        if kind == "depart":
            leg, k = payload
            direct, trig_idx = leg["direct"], leg["trig_idx"]
            draw_risk_bg(ax, cax, leg["risk_depart"])
            shown = direct[:k]
            xs = [p[0] for p in shown]; ys = [p[1] for p in shown]
            ax.plot(xs, ys, "--", color="#a7aec1", linewidth=2.2, zorder=4)
            _marker(ax, direct[0], "#5cbcc3", marker="s", size=80)
            _marker(ax, dest, "#e9ebf2", marker="X", size=110)
            _marker(ax, shown[-1], "#5cbcc3", marker="o", size=90)
            at_trigger = k - 1 >= trig_idx
            status = "RISK CHECK TRIGGERED" if at_trigger else f"EN ROUTE TO DESTINATION ({k}/{len(direct)})"
            color = "#e08a76" if at_trigger else "#a7e8a0"
            ax.set_title(f"{leg['label']}: hour {leg['hour_depart']:02.0f}:00  --  {status}",
                         color=color, fontsize=12.5)
            return

        if kind == "alert":
            leg = payload
            direct, trig_idx, trig_pos = leg["direct"], leg["trig_idx"], leg["trig_pos"]
            draw_risk_bg(ax, cax, leg["risk_alert"])
            xs = [p[0] for p in direct[: trig_idx + 1]]; ys = [p[1] for p in direct[: trig_idx + 1]]
            ax.plot(xs, ys, "--", color="#a7aec1", linewidth=2.2, zorder=4)
            _marker(ax, direct[0], "#5cbcc3", marker="s", size=80)
            _marker(ax, dest, "#e9ebf2", marker="X", size=110)
            _marker(ax, trig_pos, "#e08a76", marker="o", size=110)
            spe_tag = " (SPE)" if leg["spe_active"] else ""
            ax.set_title(f"{leg['label']}: time passed -- hour {leg['hour_alert']:02.0f}:00{spe_tag}\n"
                         f"risk here {leg['r_trig']:.2f} >= {WARNING_THRESHOLD} -- REPLANNING to nearest safe zone",
                         color="#e08a76", fontsize=12.5)
            return

        # evac
        leg, k = payload
        direct, trig_idx, trig_pos = leg["direct"], leg["trig_idx"], leg["trig_pos"]
        safe_path = leg["safe_path"]
        draw_risk_bg(ax, cax, leg["risk_alert"])
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
        spe_tag = " (SPE)" if leg["spe_active"] else ""
        ax.set_title(f"{leg['label']}: hour {leg['hour_alert']:02.0f}:00{spe_tag}  --  {status}",
                     color=color, fontsize=12.5)

    def update(i):
        draw_frame(ax, cax, i)
        return []

    anim = animation.FuncAnimation(fig, update, frames=len(frames), blit=False)
    writer = animation.FFMpegWriter(fps=FPS, bitrate=2400, codec="libx264",
                                     extra_args=["-pix_fmt", "yuv420p"])
    out_path = f"{OUT_DIR}/slam_evac_double_journey.mp4"
    anim.save(out_path, writer=writer)
    plt.close(fig)
    print(f"\nsaved {out_path}  ({len(frames)} frames, {len(frames)/FPS:.1f}s)")

    fig2, ax2 = plt.subplots(figsize=(7.4, 7.0), dpi=110, facecolor="#0b0e15")
    cax2 = fig2.add_axes([0.05, 0.05, 0.02, 0.6])
    idx2 = next(i for i, (k, p) in enumerate(frames) if k == "alert" and p["label"] == "LEG 2")
    draw_frame(ax2, cax2, idx2)
    poster_path = f"{OUT_DIR}/slam_evac_double_journey_poster.png"
    fig2.savefig(poster_path, dpi=110, facecolor=fig2.get_facecolor())
    plt.close(fig2)
    print(f"saved {poster_path}")


if __name__ == "__main__":
    main()
