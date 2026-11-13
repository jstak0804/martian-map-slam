"""
SLAM 지도 구축 이후 -- 시간이 지나며 위험도를 주기적으로 재확인하고, 경고선을 넘으면
가장 가까운 안전지대로 대피하는 과정을 2D 탑다운 영상으로 만든다.

슬롯 하나짜리 "목적지 리다이렉트" 데모(slam_navigation_video.py)와 달리, 이번엔 매 시간
(한 시간 단위) 현재 위치의 위험도를 다시 확인하고, 경고선을 넘을 때만 그 시점의 위험도
기준으로 새로 안전지대를 찾아 이동하는 연속 감시 루프를 그대로 시뮬레이션한다 -- 연출을
위해 경로/시점을 미리 짜 넣지 않고, 실제로 루프를 돌려 나온 결과를 그대로 영상화했다.
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
from human_mission_navigation import nearest_safe_zone_path_minimax, path_stats, style_ax, _marker
from slam_navigation_demo import risk_from_reconstructed_terrain, _reconstruct_height_maps

OUT_DIR = "../outputs/slam_navigation"
os.makedirs(OUT_DIR, exist_ok=True)

FPS = 10
HOME = (110, 110)
HOURS = [18.0, 19.0, 20.0, 21.0, 22.0, 23.0, 0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
MONITOR_HOLD = 13   # 모니터링(정상) 틱 유지 프레임 수 (1.3초)
ARRIVAL_HOLD = 14   # 대피 완료 후 유지 프레임 수


def build_context():
    sim.rng = np.random.default_rng(0)
    h_true, _ = sim.generate_terrain()
    terrain_only_risk = sim.true_risk_field(h_true)
    result = sim.run_exploration(h_true, terrain_only_risk)
    known_o = result["oracle_known"]
    oracle_h, _ = _reconstruct_height_maps(result)
    return known_o, oracle_h, result


def simulate_timeline(known_o, oracle_h, result):
    """시간 순으로 돌며 실제 감시/대피 루프를 실행 -- 연출이 아니라 계산 결과."""
    events = []  # each: dict(hour, risk_grid, pos_before, status, path(optional), pos_after)
    pos = HOME
    for hr in HOURS:
        spe_active = SPE_START_HOUR <= hr < SPE_END_HOUR
        risk = risk_from_reconstructed_terrain(result["oracle_r"], oracle_h, known_o, hr, spe_active)
        r_here = float(risk[pos[1], pos[0]])
        if r_here >= WARNING_THRESHOLD:
            path, path_max = nearest_safe_zone_path_minimax(risk, pos, WARNING_THRESHOLD, passable=known_o)
            if path and path[-1] != pos:
                st = path_stats(path, risk)
                events.append(dict(hour=hr, risk_grid=risk, pos_before=pos, status="EVACUATE",
                                    r_here=r_here, path=path, stats=st))
                pos = path[-1]
                continue
        events.append(dict(hour=hr, risk_grid=risk, pos_before=pos, status="MONITOR",
                            r_here=r_here, path=None, stats=None))
    return events


def main():
    print("=== SLAM 지도 위 연속 위험 감시 + 자동 대피 -- 2D 영상 ===\n")
    known_o, oracle_h, result = build_context()
    events = simulate_timeline(known_o, oracle_h, result)
    for e in events:
        if e["status"] == "MONITOR":
            print(f"hour={e['hour']:>4.1f}  risk={e['r_here']:.3f}  MONITOR  pos={e['pos_before']}")
        else:
            print(f"hour={e['hour']:>4.1f}  risk={e['r_here']:.3f}  EVACUATE "
                  f"{e['pos_before']}->{e['path'][-1]}  ({e['stats']['n_steps']} steps, "
                  f"{e['stats']['dist_m']:.1f} m)")

    n = GRID
    fig, ax = plt.subplots(figsize=(7.4, 7.0), dpi=110, facecolor="#0b0e15")
    cax = fig.add_axes([0.05, 0.05, 0.02, 0.6])

    # ---- 프레임 스케줄 생성 ----
    # 각 항목: (kind, payload) -- kind in {"intro", "monitor", "evac_step"}
    frames = []
    frames += [("intro", None)] * (FPS + FPS // 2)  # 1.5초 인트로(지도 구축 완료)
    evac_count = 0
    for e in events:
        if e["status"] == "MONITOR":
            frames += [("monitor", e)] * MONITOR_HOLD
        else:
            evac_count += 1
            path = e["path"]
            # 경로를 프레임별로 1~2스텝씩 점진적으로 보여준다 (너무 길면 2스텝씩 묶음)
            step = 1 if len(path) <= 40 else 2
            for k in range(1, len(path) + 1, step):
                frames += [("evac_step", (e, k, evac_count))]
            frames += [("evac_step", (e, len(path), evac_count))] * ARRIVAL_HOLD

    print(f"\n총 프레임 {len(frames)} ({len(frames)/FPS:.1f}초), 대피 {evac_count}회")

    def draw_heatmap(ax, cax, risk_grid):
        ax.clear()
        style_ax(ax)
        im = ax.imshow(risk_grid, cmap=RISK_CMAP, vmin=0, vmax=1, origin="upper")
        ax.contour((~known_o).astype(float), levels=[0.5], colors="#6d7488", linewidths=1.0, linestyles=":")
        ax.set_xlim(0, n); ax.set_ylim(n, 0)
        cax.clear()
        im.figure.colorbar(im, cax=cax)
        cax.tick_params(colors="#a7aec1", labelsize=7)
        cax.set_ylabel("combined risk", color="#a7aec1", fontsize=8)

    def draw_frame(ax, cax, i):
        kind, payload = frames[i]
        if kind == "intro":
            draw_heatmap(ax, cax, events[0]["risk_grid"])
            _marker(ax, HOME, "#5cbcc3", marker="s", size=90)
            ax.set_title("SLAM map complete -> navigation online\n(checking risk at home position every hour)",
                          color="#e9ebf2", fontsize=12.5)
            return

        if kind == "monitor":
            e = payload
            draw_heatmap(ax, cax, e["risk_grid"])
            _marker(ax, e["pos_before"], "#5cbcc3", marker="s", size=90)
            spe_tag = " · SPE" if SPE_START_HOUR <= e["hour"] < SPE_END_HOUR else ""
            ax.set_title(f"hour {e['hour']:02.0f}:00{spe_tag}  --  MONITOR\n"
                         f"current risk {e['r_here']:.2f} (< {WARNING_THRESHOLD}) -- nominal, staying put",
                         color="#a7e8a0", fontsize=12.5)
            # (아래 ax.set_title는 영문으로 고정 -- matplotlib 저장용 폰트에 한글 글리프가 없어
            # 영상에서 깨져 보이는 문제를 피하려고 전부 영어로 작성했다)
            return

        e, k, n_evac = payload
        draw_heatmap(ax, cax, e["risk_grid"])
        path = e["path"]
        shown = path[:k]
        xs = [p[0] for p in shown]; ys = [p[1] for p in shown]
        ax.plot(xs, ys, "-", color="#e0ac53", linewidth=2.6, zorder=4)
        _marker(ax, path[0], "#5cbcc3", marker="s", size=80)
        _marker(ax, shown[-1], "#e0ac53", marker="o", size=90)
        spe_tag = " · SPE" if SPE_START_HOUR <= e["hour"] < SPE_END_HOUR else ""
        reached = k >= len(path)
        status_txt = "SAFE ZONE REACHED" if reached else f"EVACUATING ({k}/{len(path)})"
        color = "#5cbcc3" if reached else "#e08a76"
        ax.set_title(f"hour {e['hour']:02.0f}:00{spe_tag}  --  evacuation #{n_evac}\n"
                     f"current risk {e['r_here']:.2f} >= {WARNING_THRESHOLD} -- {status_txt}",
                     color=color, fontsize=12.5)

    def update(i):
        draw_frame(ax, cax, i)
        return []

    anim = animation.FuncAnimation(fig, update, frames=len(frames), blit=False)
    writer = animation.FFMpegWriter(fps=FPS, bitrate=2400, codec="libx264",
                                     extra_args=["-pix_fmt", "yuv420p"])
    out_path = f"{OUT_DIR}/slam_navigation_evac_timeline.mp4"
    anim.save(out_path, writer=writer)
    plt.close(fig)
    print(f"\nsaved {out_path}  ({len(frames)} frames, {len(frames)/FPS:.1f}s)")

    # 포스터 프레임: 첫 번째 대피의 중간 지점
    first_evac_idx = next(i for i, (k, p) in enumerate(frames) if k == "evac_step")
    mid_idx = first_evac_idx + 3
    fig2, ax2 = plt.subplots(figsize=(7.4, 7.0), dpi=110, facecolor="#0b0e15")
    cax2 = fig2.add_axes([0.05, 0.05, 0.02, 0.6])
    draw_frame(ax2, cax2, mid_idx)
    poster_path = f"{OUT_DIR}/slam_navigation_evac_timeline_poster.png"
    fig2.savefig(poster_path, dpi=110, facecolor=fig2.get_facecolor())
    plt.close(fig2)
    print(f"saved {poster_path}")


if __name__ == "__main__":
    main()
