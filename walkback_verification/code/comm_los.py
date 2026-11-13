"""
세 번째 제약: 통신 가시선(line of sight) — 거점·동료와 무전이 닿는가

산소(mars_walkback.py)와 선량(spe_walkback.py)은 둘 다 "걸린 시간·대사량"에 비례하는 자원이라
지도 위에서 거의 같은 모양으로 줄어든다. 통신은 지형이 정한다는 점에서 성격이 다르다 — 거점에서
300 m 떨어진 골짜기 바닥이 4 km 떨어진 능선보다 더 고립될 수 있다.

같은 HiRISE DTM(Gale, 10 m/px) 위에서 세 가지를 계산한다.
  1. 거점 가시권(viewshed): 거점 안테나에서 각 칸의 우주복 안테나까지 지형이 가리지 않는가.
     화성 곡률을 넣는다(반경 3396 km — 2 m 안테나의 지평선은 약 3.7 km).
  2. 귀환 가능 영역 x 가시권: "걸어서 돌아올 수는 있지만 고장 신호가 거점에 닿지 않는 곳"을 표시.
     거점 가시권 안의 높은 곳에 중계기 1대를 둘 때 가장 많이 메워 주는 위치를 탐욕적으로 고른다.
  3. 2인 EVA 타임라인: A는 산소 최적 경로로 끝까지, B는 중간 조사 지점에 머문다.
     매 분 이격 거리, A-B / A-거점 / B-거점 가시선을 계산해 알림 상태를 낸다.
       정상 = A가 거점과 직접 연결, 중계 = A-B-거점으로만 연결, 두절 = 어느 쪽으로도 안 닿음.

근거:
  - 화성 지표 링크는 가시선이면 자유공간에 가깝고, 언덕·골짜기·크레이터가 차단·음영을 만든다
    (Koktas et al. 2023, arXiv:2308.05571). 지형 DEM으로 화성 근접 네트워크의 가시 거리를 계산한
    선행 연구: Chukkala et al. 2005 (Computer Networks).
  - 화성 모의기지(MDRS) EVA에서 능선 뒤로 가면 UHF 핸드헬드 무전이 끊겼다는 현장 보고
    (Mars Society Canada, 2021) — 정량 연구는 아님.

설계 가정(측정값 아님):
  - 안테나 높이: 거점 마스트 BASE_ANT_M = 3 m, 우주복 SUIT_ANT_M = 2 m, 중계기 RELAY_ANT_M = 3 m.
  - 가시선이면 통신 가능, 아니면 불가(회절·반사·출력·거리 감쇠 무시). 링크 예산은 넣지 않았다.
  - 대기 굴절 무시(화성 대기는 지구의 약 1% 밀도).
  - 이격 주의 거리 SEP_WARN_M = 500 m: 설계 가정. 출처 있는 기준이 아니며 조정 가능.
  - SPE: 2017년 9월 SPE 때 전파 흡수는 HF(수 MHz)와 궤도 레이더에서 보고됐고, 지표 UHF 가시선
    링크의 흡수량은 출처를 찾지 못했다. 그래서 SPE on/off에 따라 가시권을 바꾸지 않는다.
"""
from __future__ import annotations

import json
import os

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from scipy.sparse.csgraph import dijkstra

from metabolic_navigation import eta_from_rock, slope_deg_grid, MAX_WALK_SLOPE_DEG, EVA_WALK_SPEED_M_S
from human_mission_navigation import style_ax, _marker
import metabolic_model as _mm
from mars_walkback import (
    load_dtm_crop, load_traverse, lonlat_to_cell, build_o2_graph, trace, hillshade, km_extent, _wp_lonlat,
    CELL_M, MARS_RADIUS_M, O2_RESERVE_G,
)

OUT_DIR = "../outputs/comm_los"
os.makedirs(OUT_DIR, exist_ok=True)

BASE_ANT_M = 3.0
SUIT_ANT_M = 2.0
RELAY_ANT_M = 3.0
SEP_WARN_M = 500.0
REF_REMAINING_O2_G = 150
STEP = 0.5                       # 가시선 표본 간격(칸)
B_STOP_FRACTION = 0.35           # B가 머무는 조사 지점 = A 경로의 35% 지점
GOAL_SOL = 1282                  # mars_walkback의 경로 목적지와 동일


# ============================================================
# 1. 가시선 계산
# ============================================================

def viewshed(h, valid, obs, obs_ant, tgt_ant):
    """obs(x, y) 안테나에서 각 칸 위 tgt_ant 높이가 보이는가. 경계 칸 전체로 광선을 쏘아
    광선마다 '지금까지 가장 높이 올려다본 지형 기울기'를 누적한다(곡률 포함).
    반환: visible(bool), known(bool — 광선이 NoData를 지나 판정 불가인 칸은 False)."""
    rows, cols = h.shape
    ox, oy = obs
    eye = h[oy, ox] + obs_ant
    border = ([(x, 0) for x in range(cols)] + [(x, rows - 1) for x in range(cols)]
              + [(0, y) for y in range(1, rows - 1)] + [(cols - 1, y) for y in range(1, rows - 1)])
    border = [b for b in border if np.hypot(b[0] - ox, b[1] - oy) >= 1]  # 거점이 지도 가장자리에 있음
    n = rows * cols
    vis_cnt = np.zeros(n); tot_cnt = np.zeros(n); unk_cnt = np.zeros(n)
    for i in range(0, len(border), 400):
        tx = np.array([b[0] for b in border[i:i + 400]], float)
        ty = np.array([b[1] for b in border[i:i + 400]], float)
        L = np.hypot(tx - ox, ty - oy)
        t = np.arange(STEP, L.max() + STEP, STEP)[None, :]
        inside = t <= L[:, None]
        fx = ox + (tx - ox)[:, None] * t / L[:, None]
        fy = oy + (ty - oy)[:, None] * t / L[:, None]
        ix = np.clip(np.rint(fx).astype(int), 0, cols - 1)
        iy = np.clip(np.rint(fy).astype(int), 0, rows - 1)
        d = t * CELL_M
        hs = h[iy, ix] - d ** 2 / (2 * MARS_RADIUS_M)
        s = (hs - eye) / d
        s = np.where(inside, s, -np.inf)
        prev_max = np.concatenate([np.full((len(tx), 1), -np.inf), np.maximum.accumulate(s, axis=1)[:, :-1]], axis=1)
        vis = (hs + tgt_ant - eye) / d >= prev_max
        unknown = np.logical_or.accumulate(~valid[iy, ix], axis=1)
        idx = (iy * cols + ix)[inside]
        tot_cnt += np.bincount(idx, minlength=n)
        vis_cnt += np.bincount(idx, weights=vis[inside].astype(float), minlength=n)
        unk_cnt += np.bincount(idx, weights=unknown[inside].astype(float), minlength=n)
    tot = np.maximum(tot_cnt, 1)
    visible = (vis_cnt / tot >= 0.5).reshape(rows, cols)
    known = ((unk_cnt / tot < 0.5) & (tot_cnt > 0)).reshape(rows, cols) & valid
    visible[oy, ox] = known[oy, ox] = True
    return visible & known, known


def los(h, valid, p, q, ant_p, ant_q):
    """두 점 사이 가시선. 사이 지형이 두 안테나를 잇는 직선(곡률 보정)보다 높으면 가려진다."""
    (px, py), (qx, qy) = p, q
    L = float(np.hypot(qx - px, qy - py))
    if L < 1.5:
        return True
    t = np.arange(1.0, L - 0.99, STEP)
    if t.size == 0:
        return True
    ix = np.rint(px + (qx - px) * t / L).astype(int)
    iy = np.rint(py + (qy - py) * t / L).astype(int)
    if not valid[iy, ix].all():
        return False                       # 판정 불가 구간은 보수적으로 끊김 처리
    x = t * CELL_M
    D = L * CELL_M
    line = h[py, px] + ant_p + (h[qy, qx] + ant_q - h[py, px] - ant_p) * x / D
    bulge = x * (D - x) / (2 * MARS_RADIUS_M)
    return bool(np.all(h[iy, ix] + bulge <= line))


# ============================================================
# 2. 귀환 가능 영역 x 가시권, 중계기 위치
# ============================================================

def pick_relay(h, valid, base_vis, returnable, block=40):
    """후보 = 거점 가시권 안에서 400 m 블록마다 가장 높은 칸. '귀환 가능하지만 거점과 안 닿는' 칸을
    가장 많이 메우는 후보 하나를 고른다(중계기도 거점과 가시선이어야 백홀이 된다)."""
    rows, cols = h.shape
    gap = returnable & ~base_vis
    cands = []
    for y0 in range(0, rows, block):
        for x0 in range(0, cols, block):
            sub = np.where(base_vis[y0:y0 + block, x0:x0 + block], h[y0:y0 + block, x0:x0 + block], -np.inf)
            if np.isfinite(sub.max()):
                yy, xx = np.unravel_index(np.argmax(sub), sub.shape)
                cands.append((x0 + xx, y0 + yy))
    best, best_gain, best_vis = None, -1, None
    for c in cands:
        v, _ = viewshed(h, valid, c, RELAY_ANT_M, SUIT_ANT_M)
        gain = int((gap & v).sum())
        if gain > best_gain:
            best, best_gain, best_vis = c, gain, v
    return best, best_vis, len(cands)


# ============================================================
# 3. 2인 EVA 타임라인
# ============================================================

def route_cum_m(route):
    seg = np.hypot(np.diff([p[0] for p in route]), np.diff([p[1] for p in route])) * CELL_M
    return np.concatenate([[0], np.cumsum(seg)])


def buddy_timeline(h, valid, base, route, stop_m):
    """A는 route를 끝까지, B는 경로상 stop_m 지점에서 멈춘다. 둘 다 EVA 보행속도.
    1분 간격으로 위치·이격·가시선·알림 상태를 낸다."""
    cum = route_cum_m(route)

    def at(dist):
        i = int(np.searchsorted(cum, min(dist, cum[-1]), side="right") - 1)
        return route[min(i, len(route) - 1)]

    rows_ = []
    # 2026-11-10: 경사별 속도. 구간마다 걸리는 시간을 누적해 시각 -> 거리로 바꾼다.
    xs = np.array([p[0] for p in route]); ys = np.array([p[1] for p in route])
    seg_m = np.diff(cum)
    grade = (h[ys[1:], xs[1:]] - h[ys[:-1], xs[:-1]]) / np.maximum(seg_m, 1e-9) * 100
    cum_t = np.concatenate([[0.0], np.cumsum(seg_m / _mm.walk_speed(grade))])
    t_end = cum_t[-1]
    for t in np.arange(0, t_end + 60, 60):
        da = float(np.interp(min(t, t_end), cum_t, cum))
        a, b = at(da), at(min(da, stop_m))
        ab = los(h, valid, a, b, SUIT_ANT_M, SUIT_ANT_M)
        a0 = los(h, valid, base, a, BASE_ANT_M, SUIT_ANT_M)
        b0 = los(h, valid, base, b, BASE_ANT_M, SUIT_ANT_M)
        sep = float(np.hypot(a[0] - b[0], a[1] - b[1]) * CELL_M)
        if a0:
            state = "direct"
        elif ab and b0:
            state = "relay"
        else:
            state = "lost"
        rows_.append({"t_min": float(t / 60), "a_dist_km": da / 1000, "a": a, "b": b, "sep_m": sep,
                      "los_ab": ab, "los_a_base": a0, "los_b_base": b0, "state": state,
                      "sep_warn": sep > SEP_WARN_M})
    return rows_


def longest_streak(flags):
    best = cur = 0
    for f in flags:
        cur = cur + 1 if f else 0
        best = max(best, cur)
    return best


def best_b_stop(h, valid, base, route, every=5):
    """B가 어디서 기다려야 A의 두절 시간이 가장 짧은가 — 경로상 후보 지점을 모두 시뮬레이션."""
    cum = route_cum_m(route)
    best = None
    for i in range(every, len(route) - 1, every):
        if not los(h, valid, base, route[i], BASE_ANT_M, SUIT_ANT_M):
            continue                     # B 자신이 거점과 안 닿으면 중계가 안 된다
        lost = sum(r["state"] == "lost" for r in buddy_timeline(h, valid, base, route, cum[i]))
        if best is None or lost < best[1]:
            best = (float(cum[i]), lost)
    return best[0]


# ============================================================
# 4. 그림
# ============================================================

def plot_coverage(h, valid, base_vis, relay_vis, returnable, relay, base, traverse_xy, stats):
    fig, axes = plt.subplots(1, 2, figsize=(13.6, 8.6), facecolor="#0b0e15")
    ext = km_extent(h.shape)
    k = CELL_M / 1000
    shade = np.where(valid, hillshade(h), np.nan)

    ax = axes[0]
    style_ax(ax)
    ax.imshow(shade, cmap="gray", extent=ext, vmin=0, vmax=1)
    ax.imshow(np.where(base_vis, 1.0, np.nan), cmap=ListedColormap([C_OK]), extent=ext, alpha=0.5)
    for x, y in traverse_xy:
        ax.plot(x * k, y * k, color="#e9ebf2", lw=0.5, alpha=0.6)
    _marker(ax, (base[0] * k, base[1] * k), "#a7e8a0", marker="*", size=200)
    ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
    ax.set_title(f"Line of sight to base antenna ({BASE_ANT_M:.0f} m mast -> {SUIT_ANT_M:.0f} m suit, Mars curvature)\n"
                 f"blue = radio reaches base: {stats['base_visible_km2']:.1f} km2 of {stats['valid_km2']:.1f} km2 mapped",
                 color="#e9ebf2", fontsize=9)

    ax = axes[1]
    style_ax(ax)
    ax.imshow(shade, cmap="gray", extent=ext, vmin=0, vmax=1)
    ok = returnable & base_vis
    via_relay = returnable & ~base_vis & relay_vis
    dark = returnable & ~base_vis & ~relay_vis
    ax.imshow(np.where(ok, 1.0, np.nan), cmap=ListedColormap([C_OK]), extent=ext, alpha=0.5)
    ax.imshow(np.where(via_relay, 1.0, np.nan), cmap=ListedColormap([C_RELAY]), extent=ext, alpha=0.7)
    ax.imshow(np.where(dark, 1.0, np.nan), cmap=ListedColormap([C_DARK]), extent=ext, alpha=0.85)
    _marker(ax, (base[0] * k, base[1] * k), "#a7e8a0", marker="*", size=200)
    _marker(ax, (relay[0] * k, relay[1] * k), "#f5f0ff", marker="^", size=150)
    ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
    handles = [plt.Rectangle((0, 0), 1, 1, color=C_OK, label=f"can walk back + radio to base ({stats['returnable_and_visible_km2']:.1f} km2)"),
               plt.Rectangle((0, 0), 1, 1, color=C_RELAY, label=f"fixed by one relay ({stats['gap_fixed_by_relay_km2']:.1f} km2)"),
               plt.Rectangle((0, 0), 1, 1, color=C_DARK, label=f"can walk back but radio dark ({stats['gap_after_relay_km2']:.1f} km2)")]
    ax.legend(handles=handles, facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2", fontsize=7.5, loc="lower left")
    ax.set_title(f"Walk-back area ({REF_REMAINING_O2_G} g O2 left) x radio coverage\n"
                 f"no relay: {stats['returnable_dark_km2']:.1f} km2 dark ({stats['returnable_dark_pct']:.0f}%) -- "
                 f"triangle = best relay site", color="#e9ebf2", fontsize=9)
    fig.tight_layout()
    fname = f"{OUT_DIR}/comm_coverage.png"
    fig.savefig(fname, dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"saved {fname}")


C_OK, C_RELAY, C_DARK = "#3fb6c0", "#d65bd0", "#f2d430"
STATE_COLORS = {"direct": "#5cbcc3", "relay": "#e0ac53", "lost": "#e05a4f"}


def plot_buddy(h, valid, base, route, policies):
    """policies: [(제목, stop_m, timeline), ...] — 위쪽은 정책별 지도, 아래는 이격 거리와 알림 띠."""
    fig = plt.figure(figsize=(13.6, 10.4), facecolor="#0b0e15")
    gs = fig.add_gridspec(2, len(policies), height_ratios=[1.6, 0.42])
    ext = km_extent(h.shape)
    k = CELL_M / 1000
    shade = np.where(valid, hillshade(h), np.nan)

    for j, (title, stop_m, tl, _) in enumerate(policies):
        ax = fig.add_subplot(gs[0, j])
        style_ax(ax)
        ax.imshow(shade, cmap="gray", extent=ext, vmin=0, vmax=1)
        for r0, r1 in zip(tl[:-1], tl[1:]):
            ax.plot([r0["a"][0] * k, r1["a"][0] * k], [r0["a"][1] * k, r1["a"][1] * k],
                    color=STATE_COLORS[r1["state"]], lw=2.4)
        b = tl[-1]["b"]
        _marker(ax, (base[0] * k, base[1] * k), "#a7e8a0", marker="*", size=200)
        _marker(ax, (b[0] * k, b[1] * k), "#f5f0ff", marker="o", size=90)
        _marker(ax, (route[-1][0] * k, route[-1][1] * k), "#e9ebf2", marker="X", size=100)
        ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
        n_lost = sum(r["state"] == "lost" for r in tl)
        ax.set_title(f"{title}: B waits at {stop_m/1000:.1f} km (circle)\nA radio lost {n_lost} of {len(tl)} min",
                     color="#e9ebf2", fontsize=9.5)
        if j == 0:
            handles = [plt.Line2D([], [], color=c, lw=2.4, label=lab) for lab, c in
                       [("A: direct to base", STATE_COLORS["direct"]), ("A: only via B (relay)", STATE_COLORS["relay"]),
                        ("A: radio lost", STATE_COLORS["lost"])]]
            ax.legend(handles=handles, facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2",
                      fontsize=7.5, loc="lower left")

    ax = fig.add_subplot(gs[1, :])
    style_ax(ax)
    for j, (title, stop_m, tl, _) in enumerate(policies):
        t = np.array([r["t_min"] for r in tl])
        ax.scatter(t, np.full(len(t), j), c=[STATE_COLORS[r["state"]] for r in tl], s=22, marker="s")
        warn = np.array([r["sep_warn"] for r in tl])
        ax.scatter(t[warn], np.full(warn.sum(), j + 0.28), color="#e9ebf2", s=4, marker="|")
    ax.set_yticks(range(len(policies)))
    ax.set_yticklabels([p[3] for p in policies], color="#a7aec1", fontsize=8.5)
    ax.set_ylim(len(policies) - 0.2, -0.6)
    ax.set_xlabel(f"minutes since leaving base (A walks {route_cum_m(route)[-1]/1000:.1f} km at "
                  f"flat {_mm.LEVEL_SPEED_M_S} m/s, slower uphill)  --  tick marks = A-B separation > {SEP_WARN_M:.0f} m (design assumption)",
                  color="#a7aec1", fontsize=8)
    ax.set_title("A's alert state per minute: blue direct, amber relay through B, red lost", color="#e9ebf2", fontsize=9.5)
    fig.tight_layout()
    fname = f"{OUT_DIR}/buddy_timeline.png"
    fig.savefig(fname, dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"saved {fname}")


# ============================================================
# 5. 실행
# ============================================================

def main():
    h, valid, rough_r, _ = load_dtm_crop()
    slope = slope_deg_grid(h, CELL_M)
    passable = valid & (slope <= MAX_WALK_SLOPE_DEG)
    eta = eta_from_rock(rough_r)
    wps, traverse_xy = load_traverse(h.shape)
    bx, by = (int(round(v)) for v in lonlat_to_cell(wps[0]["lon"], wps[0]["lat"]))
    base = (bx, by)
    base_idx = by * h.shape[1] + bx
    cell_km2 = (CELL_M / 1000) ** 2

    horizon_km = (np.sqrt(2 * MARS_RADIUS_M * BASE_ANT_M) + np.sqrt(2 * MARS_RADIUS_M * SUIT_ANT_M)) / 1000
    print(f"매끈한 화성 구면에서 {BASE_ANT_M:.0f} m 마스트 - {SUIT_ANT_M:.0f} m 우주복 최대 가시거리 {horizon_km:.1f} km")

    base_vis, known = viewshed(h, valid, base, BASE_ANT_M, SUIT_ANT_M)

    graph = build_o2_graph(h, eta, passable)
    ret_o2, _ = dijkstra(graph.T.tocsr(), directed=True, indices=base_idx, return_predecessors=True)
    ret_o2 = ret_o2.reshape(h.shape)
    returnable = ret_o2 <= REF_REMAINING_O2_G - O2_RESERVE_G

    relay, relay_vis, n_cand = pick_relay(h, valid, base_vis, returnable)
    gap = returnable & ~base_vis
    stats = {
        "valid_km2": float(valid.sum() * cell_km2),
        "base_visible_km2": float(base_vis.sum() * cell_km2),
        "returnable_km2": float(returnable.sum() * cell_km2),
        "returnable_and_visible_km2": float((returnable & base_vis).sum() * cell_km2),
        "returnable_dark_km2": float(gap.sum() * cell_km2),
        "returnable_dark_pct": float(gap.sum() / max(returnable.sum(), 1) * 100),
        "relay_cell": [int(relay[0]), int(relay[1])],
        "relay_km_from_base": float(np.hypot(relay[0] - bx, relay[1] - by) * CELL_M / 1000),
        "relay_candidates": n_cand,
        "gap_fixed_by_relay_km2": float((gap & relay_vis).sum() * cell_km2),
        "gap_after_relay_km2": float((gap & ~relay_vis).sum() * cell_km2),
    }
    print(f"거점 가시권 {stats['base_visible_km2']:.2f} km2 / 지도 {stats['valid_km2']:.2f} km2")
    print(f"귀환 가능({REF_REMAINING_O2_G} g) {stats['returnable_km2']:.2f} km2 중 무전이 거점에 안 닿는 곳 "
          f"{stats['returnable_dark_km2']:.2f} km2 ({stats['returnable_dark_pct']:.0f}%)")
    print(f"중계기 1대(후보 {n_cand}곳 중 최적, 거점에서 {stats['relay_km_from_base']:.2f} km): "
          f"{stats['gap_fixed_by_relay_km2']:.2f} km2 메움, 남은 음영 {stats['gap_after_relay_km2']:.2f} km2")

    # 2인 EVA: 산소 최적 경로(착륙지 -> sol GOAL_SOL 지점)
    _, out_pred = dijkstra(graph, directed=True, indices=base_idx, return_predecessors=True)
    gx, gy = (int(round(v)) for v in lonlat_to_cell(*_wp_lonlat(wps, GOAL_SOL)))
    route = trace(out_pred, gy * h.shape[1] + gx, h.shape)
    route_km = route_cum_m(route)[-1] / 1000
    naive_m = route_km * 1000 * B_STOP_FRACTION
    best_m = best_b_stop(h, valid, base, route)
    policies, buddy = [], {"route_km": route_km}
    print(f"\n2인 EVA: A는 산소 최적 경로 {route_km:.2f} km를 끝까지, B는 경로 위 한 지점에서 대기")
    for key, title, short, stop_m in [
            ("fixed_stop", f"B stops at {B_STOP_FRACTION:.0%} of route", "fixed stop", naive_m),
            ("comm_aware_stop", "B stops where A stays connected longest", "comm-aware stop", best_m)]:
        tl = buddy_timeline(h, valid, base, route, stop_m)
        policies.append((title, stop_m, tl, short))
        counts = {s: sum(r["state"] == s for r in tl) for s in ("direct", "relay", "lost")}
        first_lost = next((r for r in tl if r["state"] == "lost"), None)
        first_warn = next((r for r in tl if r["sep_warn"]), None)
        buddy[key] = {"b_stop_km": stop_m / 1000, "minutes": len(tl),
                      "minutes_direct": counts["direct"], "minutes_relay": counts["relay"],
                      "minutes_lost": counts["lost"],
                      "first_lost_min": first_lost and first_lost["t_min"],
                      "first_lost_a_km": first_lost and first_lost["a_dist_km"],
                      "first_sep_warn_min": first_warn and first_warn["t_min"],
                      "longest_lost_streak_min": longest_streak([r["state"] == "lost" for r in tl])}
        print(f"  [{key}] B {stop_m/1000:.2f} km 지점: {len(tl)}분 중 직접 {counts['direct']} / 중계 "
              f"{counts['relay']} / 두절 {counts['lost']}"
              + f", 최장 연속 두절 {buddy[key]['longest_lost_streak_min']}분"
              + (f", 첫 두절 {first_lost['t_min']:.0f}분(A {first_lost['a_dist_km']:.2f} km)" if first_lost else ""))
    timeline = policies[-1][2]

    plot_coverage(h, valid, base_vis, relay_vis, returnable, relay, base, traverse_xy, stats)
    plot_buddy(h, valid, base, route, policies)

    out = {"assumptions": {"BASE_ANT_M": BASE_ANT_M, "SUIT_ANT_M": SUIT_ANT_M, "RELAY_ANT_M": RELAY_ANT_M,
                           "SEP_WARN_M": SEP_WARN_M, "REF_REMAINING_O2_G": REF_REMAINING_O2_G,
                           "B_STOP_FRACTION": B_STOP_FRACTION, "los_model": "terrain + Mars curvature, no refraction/diffraction",
                           "spe_effect": "not modeled (no source for UHF surface-link absorption)"},
           "smooth_sphere_max_range_km": horizon_km, "coverage": stats, "buddy": buddy,
           "timeline_comm_aware_stop": [{k_: v for k_, v in r.items() if k_ not in ("a", "b")} for r in timeline]}
    with open(f"{OUT_DIR}/comm_stats.json", "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"saved {OUT_DIR}/comm_stats.json")


if __name__ == "__main__":
    main()
