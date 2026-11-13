"""
유인 미션 내비게이션 -- 1인칭(EVA 시점) 시뮬레이션 영상.

human_mission_navigation.py가 계산한 안전지대 대피 경로(야간+SPE 중첩, 최악의 시나리오)를
사람 눈높이에서 걷는 것처럼 보이도록 렌더링한다. matplotlib에 내장된 3D 카메라는 항상
데이터 전체를 바깥에서 바라보는 궤도(orbit) 카메라만 지원하고 "지면 위에 서서 앞을 보는"
임의의 위치/방향의 카메라를 지원하지 않는다 -- 그래서 고전적인 하이트필드 레이마칭(복셀
스페이스, voxel-space landscape rendering) 방식으로 화면을 직접 그린다: 화면의 각 열(column)
마다 광선을 전방으로 쏘아 지형을 따라가며, 더 먼 지점이 더 가까운 지점보다 화면상 더 위로
튀어나올 때만 그 열을 새로 칠한다(페인터 알고리즘).

이 지역 탐사 패치의 실제 고도 기복은 매우 작다(표준편차 2.7cm, 범위 0~0.47m, 44m x 44m 패치
기준) -- 맨눈 그대로 렌더링하면 거의 평평해 보여 구분이 안 된다. 그래서 수직 과장
(vertical exaggeration)을 적용한다 -- 실제 지형이 아니라 "위험도가 지형과 어떻게 연관되는지
보기 쉽게 만든" 시각화라는 점을 화면에도 명시한다.
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
from exploration_slam_sim import GRID, CELL_M, RISK_CMAP
from anisotropic_risk_exploration import rock_risk_grid, slope_grids
from human_mission_risk import (
    human_mission_risk, shielding_factor_grid,
    WARNING_THRESHOLD, SPE_START_HOUR, SPE_END_HOUR,
)
from human_mission_navigation import nearest_safe_zone_path_minimax, path_stats, EVA_WALK_SPEED_M_S

OUT_DIR = "../outputs/human_mission_navigation"
os.makedirs(OUT_DIR, exist_ok=True)

EYE_HEIGHT_M = 1.6        # 설계 가정: 우주복 헬멧 카메라/눈높이 예시치 (사양값 아님)
VERTICAL_EXAGGERATION = 10.0  # 시각화 전용 과장 배율 -- 지형 기복(요철)에만 적용, 눈높이 자체에는 적용 안 함
FOV_DEG = 100.0
SCREEN_W, SCREEN_H = 300, 180
MIN_RENDER_DIST_M = 2.0   # 이보다 가까운 "발밑"은 렌더링하지 않음(일반적 시야각 밖)
MAX_RENDER_DIST_M = 16.0
N_MARCH_STEPS = 260
HORIZON_FRAC = 0.42
# 지면(바닥)이 MIN_RENDER_DIST_M 거리에서 화면 맨 아래에 닿도록 역산한 원근 스케일.
PERSPECTIVE_K = (SCREEN_H - SCREEN_H * HORIZON_FRAC) * MIN_RENDER_DIST_M / (SCREEN_H * EYE_HEIGHT_M)
FPS = 10

SKY_TOP = np.array([0.03, 0.035, 0.06])
SKY_HORIZON = np.array([0.09, 0.10, 0.14])


def bilinear_vec(field, x, y):
    n = field.shape[0]
    x = np.clip(x, 0, n - 1.001)
    y = np.clip(y, 0, n - 1.001)
    x0 = x.astype(int); y0 = y.astype(int)
    x1 = x0 + 1; y1 = y0 + 1
    fx = x - x0; fy = y - y0
    return (field[y0, x0] * (1 - fx) * (1 - fy) + field[y0, x1] * fx * (1 - fy)
            + field[y1, x0] * (1 - fx) * fy + field[y1, x1] * fx * fy)


def render_frame(h, risk, cam_gx, cam_gy, heading_deg):
    n = h.shape[0]
    horizon_row = SCREEN_H * HORIZON_FRAC
    bearings = np.radians(heading_deg + np.linspace(-FOV_DEG / 2, FOV_DEG / 2, SCREEN_W))
    dx, dy = np.sin(bearings), -np.cos(bearings)  # exploration_slam_sim과 동일한 heading 규약

    th0 = float(bilinear_vec(h, np.array([cam_gx]), np.array([cam_gy]))[0])  # 카메라가 선 지점의 지면 높이
    cam_h = th0 + EYE_HEIGHT_M

    img = np.empty((SCREEN_H, SCREEN_W, 3))
    row_frac = np.linspace(0, 1, SCREEN_H)[:, None]
    sky_col = SKY_TOP[None, :] * (1 - row_frac) + SKY_HORIZON[None, :] * row_frac
    img[:, :, :] = sky_col[:, None, :]

    y_buffer = np.full(SCREEN_W, float(SCREEN_H))
    rows = np.arange(SCREEN_H)[:, None]
    dists = np.linspace(MIN_RENDER_DIST_M, MAX_RENDER_DIST_M, N_MARCH_STEPS)

    for t in dists:
        wx = cam_gx + dx * (t / CELL_M)
        wy = cam_gy + dy * (t / CELL_M)
        valid = (wx >= 0) & (wx <= n - 1.001) & (wy >= 0) & (wy <= n - 1.001)
        th = bilinear_vec(h, wx, wy)
        rv = bilinear_vec(risk, wx, wy)
        # 지형 '기복'만 과장한다 -- 카메라가 선 지점 기준 상대고도(th-th0)에만 배율을 적용하고,
        # 눈높이(EYE_HEIGHT_M) 자체는 과장하지 않아야 원근(바닥이 수평선으로 수렴하는 것)이 안 깨진다.
        th_exag = th0 + (th - th0) * VERTICAL_EXAGGERATION

        screen_y = horizon_row - (th_exag - cam_h) / t * PERSPECTIVE_K * SCREEN_H
        screen_y = np.clip(screen_y, 0, SCREEN_H)
        draw_mask = valid & (screen_y < y_buffer)
        if draw_mask.any():
            rgb = RISK_CMAP(rv)[:, :3]  # (SCREEN_W, 3)
            # 위험도 색만으로는 평지/바위가 구분되지 않는다(이 시간대는 배경 위험도 자체가
            # 높아 지형과 무관하게 전체적으로 진한 색이 됨) -- 높이에 따른 간이 음영(높을수록
            # 밝게)을 곱해 실루엣(지형 굴곡)을 읽을 수 있게 한다. 이것도 시각화 보조 장치이지
            # 실제 조명 시뮬레이션은 아니다.
            shade = np.clip(0.55 + 2.2 * th, 0.45, 1.35)
            rgb = np.clip(rgb * shade[:, None], 0, 1)
            fog = float(np.clip(t / MAX_RENDER_DIST_M, 0, 1) ** 1.3)
            rgb = rgb * (1 - fog) + SKY_HORIZON[None, :] * fog
            seg_mask = (rows >= screen_y[None, :]) & (rows < y_buffer[None, :]) & draw_mask[None, :]
            rgb_full = np.broadcast_to(rgb[None, :, :], (SCREEN_H, SCREEN_W, 3))
            img[seg_mask] = rgb_full[seg_mask]
            y_buffer = np.where(draw_mask, screen_y, y_buffer)

    return np.clip(img, 0, 1)


def build_scenario():
    sim.rng = np.random.default_rng(0)
    h, _ = sim.generate_terrain()
    n = h.shape[0]

    gx_grid, gy_grid = slope_grids(h)
    slope = np.hypot(gx_grid, gy_grid)
    slope_risk = np.clip(slope / 0.9, 0, 1)
    rock_r = rock_risk_grid(h)
    shielding = shielding_factor_grid(h)

    hour = 2.0
    spe_active = SPE_START_HOUR <= hour < SPE_END_HOUR
    risk = human_mission_risk(slope_risk, rock_r, hour, shielding, spe_active)

    start = (20, 20)
    path, path_max = nearest_safe_zone_path_minimax(risk, start, WARNING_THRESHOLD)
    stats = path_stats(path, risk)
    return h, risk, hour, spe_active, path, stats


def headings_along(path):
    pts = np.array(path, dtype=float)
    headings = np.zeros(len(pts))
    for i in range(len(pts)):
        j = min(i + 2, len(pts) - 1)
        d = pts[j] - pts[i]
        if np.hypot(*d) < 1e-6:
            headings[i] = headings[i - 1] if i > 0 else 0.0
        else:
            headings[i] = np.degrees(np.arctan2(d[0], -d[1])) % 360
    # 급격한 좌우 흔들림을 줄이기 위해 헤딩을 살짝 평활화
    sm = headings.copy()
    for i in range(1, len(headings) - 1):
        a, b, c = headings[i - 1], headings[i], headings[i + 1]
        sm[i] = np.degrees(np.angle(np.mean(np.exp(1j * np.radians([a, b, c])))))
    return sm % 360


def main():
    print("=== 유인 미션 내비게이션 -- 1인칭(EVA) 시뮬레이션 영상 ===\n")
    h, risk, hour, spe_active, path, stats = build_scenario()
    print(f"hour={hour:.0f} SPE={spe_active} -- 대피 경로 {stats['n_steps']}스텝, "
          f"{stats['dist_m']:.1f} m, max_risk={stats['max_risk']:.3f}")

    headings = headings_along(path)
    n_steps = len(path)
    cum_dist_m = [0.0]
    for i in range(1, n_steps):
        px, py = path[i - 1]; cx, cy = path[i]
        cum_dist_m.append(cum_dist_m[-1] + float(np.hypot(cx - px, cy - py)) * CELL_M)

    fig, ax = plt.subplots(figsize=(8.0, 5.0), dpi=110, facecolor="#0b0e15")
    ax.set_position([0, 0.16, 1, 0.78])
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)

    im = ax.imshow(np.zeros((SCREEN_H, SCREEN_W, 3)), origin="upper", interpolation="bilinear")
    hud = fig.text(0.02, 0.975, "", color="#e9ebf2", fontsize=11, family="monospace", va="top")
    hud2 = fig.text(0.02, 0.095, "", color="#a7aec1", fontsize=8.8, family="monospace", va="top")
    crosshair, = ax.plot([SCREEN_W / 2], [SCREEN_H * HORIZON_FRAC], "+", color="#e9ebf2", markersize=10, mew=1.2)

    def update(i):
        gx, gy = path[i]
        frame = render_frame(h, risk, gx, gy, headings[i])
        im.set_data(frame)
        r_here = float(risk[int(round(gy)), int(round(gx))])
        status = "DANGER" if r_here >= WARNING_THRESHOLD else "nominal"
        hud.set_text(
            f"EVA NAV -- hour {hour:02.0f}:00 {'(SPE ACTIVE) ' if spe_active else ''}\n"
            f"step {i+1}/{n_steps}  dist {cum_dist_m[i]:4.1f}/{stats['dist_m']:.1f} m  "
            f"current risk {r_here:.2f} [{status}]"
        )
        hud2.set_text(
            f"target: nearest safe zone (risk<{WARNING_THRESHOLD})  walk speed {EVA_WALK_SPEED_M_S} m/s (Apollo EVA planning rate, NASA 1979)\n"
            f"vertical exaggeration x{VERTICAL_EXAGGERATION:.0f} -- visualization only, not true terrain relief"
        )
        return [im, hud, hud2, crosshair]

    anim = animation.FuncAnimation(fig, update, frames=n_steps, blit=False)
    writer = animation.FFMpegWriter(fps=FPS, bitrate=2400, codec="libx264",
                                     extra_args=["-pix_fmt", "yuv420p"])
    out_path = f"{OUT_DIR}/first_person_evac_walk.mp4"
    anim.save(out_path, writer=writer)
    plt.close(fig)
    print(f"\nsaved {out_path}  ({n_steps} frames, {n_steps/FPS:.1f}s)")

    # 포스터 프레임
    fig2, ax2 = plt.subplots(figsize=(8.0, 5.0), dpi=110, facecolor="#0b0e15")
    ax2.set_position([0, 0.12, 1, 0.82])
    ax2.set_xticks([]); ax2.set_yticks([])
    for s in ax2.spines.values():
        s.set_visible(False)
    mid = n_steps // 2
    frame = render_frame(h, risk, path[mid][0], path[mid][1], headings[mid])
    ax2.imshow(frame, origin="upper", interpolation="bilinear")
    fig2.text(0.02, 0.965, f"EVA NAV -- hour {hour:02.0f}:00 (SPE ACTIVE)\nstep {mid+1}/{n_steps}",
               color="#e9ebf2", fontsize=11, family="monospace", va="top")
    poster_path = f"{OUT_DIR}/first_person_evac_walk_poster.png"
    fig2.savefig(poster_path, dpi=110, facecolor=fig2.get_facecolor())
    plt.close(fig2)
    print(f"saved {poster_path}")


if __name__ == "__main__":
    main()
