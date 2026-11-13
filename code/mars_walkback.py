"""
화성 실제 지형(Gale 크레이터) 위 산소 효율 경로 + 귀환 가능 반경(walk-back radius)

metabolic_navigation.py의 산소 비용 모델(Pandolf, 화성 0.38g)을 실측 화성 지형에 적용한다.

데이터:
  지형 — HiRISE DTM DTEEC_018854_1755_018920_1755_U01 (Gale 크레이터, Curiosity 착륙지 포함,
         1.01 m/px, PDS hirise-pds.lpl.arizona.edu). 경로탐색용으로 10 m/px로 블록 평균한다.
  경로 — Curiosity 실제 주행 경로/웨이포인트 (NASA MMGIS MSL_waypoints.json / MSL_traverse.json).
         DTM 범위 안에 sol 3~1671, 누적 약 16 km가 들어온다.

귀환 가능 반경(Apollo walkback limit 개념, NASA 1979):
  로버가 고장 난 지점 p에서 거점(착륙지)까지 걸어서 돌아오는 데 드는 산소 R(p)를 모든 칸에 대해
  한 번에 구한다 — "모든 칸 -> 거점" 최단경로이므로, 간선 방향을 뒤집은 그래프에서 거점을
  출발점으로 다익스트라 1회. 남은 산소 X에 대해 R(p) <= X - 예비분 인 영역이 안전 반경이다.
  오르막/내리막 때문에 비용이 비대칭이라 "나갈 때 비용"과 "돌아올 때 비용"이 다르다.

설계 가정(측정값 아님):
  - CELL_M = 10 m: 1 m DTM을 블록 평균 — km 규모 탐색 속도를 위해. 10 m 이하 경사(바위 단위)는
    평활되므로 경사 상한은 '보행 경로 규모'의 경사에만 적용된다.
  - 지형계수 eta: 블록 내 1 m 고도의 국소 기복(고역통과 표준편차)을 ROUGH_HIGH_M로 정규화해
    metabolic_navigation.eta_from_rock()에 넣는다 — 바위·요철 부담의 대리 지표.
  - O2_RESERVE_G: Apollo 운용의 "30분 소모품 예비분"을 평지 보행 산소율로 환산.
  - 거점 = Curiosity 착륙지(Bradbury Landing, sol 3 웨이포인트).
"""
from __future__ import annotations

import json
import os

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from metabolic_navigation import (
    metabolic_rate_w, o2_g_per_s, eta_from_rock, slope_deg_grid,
    G_RATIO_MARS, MAX_WALK_SLOPE_DEG, EVA_WALK_SPEED_M_S,
)
from human_mission_navigation import style_ax, _marker

OUT_DIR = "../outputs/mars_walkback"
os.makedirs(OUT_DIR, exist_ok=True)

DTM_PATH = "../data/hirise_dtm/DTEEC_018854_1755_018920_1755_U01.IMG"
WAYPOINTS_PATH = "../data/msl_traverse/MSL_waypoints.json"
TRAVERSE_PATH = "../data/msl_traverse/MSL_traverse.json"

# DTM 라벨 값 (PDS 라벨에서 그대로)
DTM_LINES, DTM_SAMPLES = 15040, 7075
DTM_RECORD_BYTES = 28300           # ^IMAGE = 2 -> 영상은 레코드 1개(라벨) 뒤에서 시작
DTM_MAP_SCALE_M = 1.0117630165416
DTM_MAX_LAT, DTM_WEST_LON = -4.4578635989917, 137.33619755
MARS_RADIUS_M = 3396190.0
DEG_PER_PX = DTM_MAP_SCALE_M / (MARS_RADIUS_M * np.pi / 180)

BLOCK = 10                          # 1 m -> 10 m
CELL_M = DTM_MAP_SCALE_M * BLOCK
CROP_LINES = (7000, 15040)          # Curiosity 착륙지(line ~7710)부터 DTM 남단까지
CROP_SAMPLES = (500, 7075)
ROUGH_HIGH_M = 0.5                  # 설계 가정: 블록 내 국소 기복 0.5 m를 eta 최대로

LEVEL_O2_G_PER_M = float(o2_g_per_s(metabolic_rate_w(0.0, 1.0, G_RATIO_MARS))) / EVA_WALK_SPEED_M_S
LEVEL_O2_G_PER_H = LEVEL_O2_G_PER_M * EVA_WALK_SPEED_M_S * 3600
O2_RESERVE_G = LEVEL_O2_G_PER_H * 0.5          # Apollo 30분 예비분
REMAINING_O2_G = [100, 150, 200]                # 로버 고장 시점에 남은 산소 시나리오

OFFSETS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]


# ============================================================
# 1. 데이터 로드
# ============================================================

def load_dtm_crop():
    raw = np.memmap(DTM_PATH, dtype="<f4", mode="r", offset=DTM_RECORD_BYTES,
                    shape=(DTM_LINES, DTM_SAMPLES))
    l0, l1 = CROP_LINES
    s0, s1 = CROP_SAMPLES
    l1 = l0 + (l1 - l0) // BLOCK * BLOCK
    s1 = s0 + (s1 - s0) // BLOCK * BLOCK
    h1 = np.array(raw[l0:l1, s0:s1], dtype=np.float64)
    valid1 = h1 > -1e30                      # MISSING_CONSTANT = 16#FF7FFFFB# (~-3.4e38)
    h1[~valid1] = np.nan

    rows, cols = h1.shape[0] // BLOCK, h1.shape[1] // BLOCK
    blocks = h1.reshape(rows, BLOCK, cols, BLOCK)
    valid = np.isfinite(blocks).all(axis=(1, 3))
    h = np.nanmean(blocks, axis=(1, 3))

    filled = np.where(valid1, h1, np.nanmean(h1))
    highpass = h1 - gaussian_filter(filled, sigma=3)
    rough = np.nanstd(highpass.reshape(rows, BLOCK, cols, BLOCK), axis=(1, 3))
    h[~valid] = np.nanmean(h)                # 무효 칸은 통행 불가로 막으므로 값 자체는 무의미
    rough[~valid] = 0
    return h, valid, np.clip(rough / ROUGH_HIGH_M, 0, 1), h1


def _wp_lonlat(wps, sol):
    p = [w for w in wps if w["sol"] == sol][-1]
    return p["lon"], p["lat"]


def lonlat_to_cell(lon, lat):
    line = (DTM_MAX_LAT - np.asarray(lat)) / DEG_PER_PX - CROP_LINES[0]
    sample = (np.asarray(lon) - DTM_WEST_LON) / DEG_PER_PX - CROP_SAMPLES[0]
    return sample / BLOCK, line / BLOCK


def load_traverse(shape):
    rows, cols = shape
    with open(WAYPOINTS_PATH) as f:
        wps = [ft["properties"] for ft in json.load(f)["features"]]
    with open(TRAVERSE_PATH) as f:
        lines = []
        for ft in json.load(f)["features"]:
            g = ft["geometry"]
            segs = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
            lines.extend(segs)
    xy = []
    for seg in lines:
        arr = np.array(seg)
        x, y = lonlat_to_cell(arr[:, 0], arr[:, 1])
        inside = (x >= 0) & (x < cols) & (y >= 0) & (y < rows)
        xy.append((x[inside], y[inside]))
    return wps, xy


# ============================================================
# 2. 방향성 산소 비용 그래프 (scipy 희소행렬 다익스트라)
# ============================================================

def build_o2_graph(h, eta, passable):
    """간선 u->v 가중치 = u에서 v로 걸을 때 쓰는 산소(g). 오르막 방향만 비싸서 비대칭."""
    rows, cols = h.shape
    idx = np.arange(rows * cols).reshape(rows, cols)
    src, dst, w = [], [], []
    for dx, dy in OFFSETS:
        ys, ye = max(0, -dy), rows - max(0, dy)
        xs, xe = max(0, -dx), cols - max(0, dx)
        a = (slice(ys, ye), slice(xs, xe))
        b = (slice(ys + dy, ye + dy), slice(xs + dx, xe + dx))
        ok = passable[a] & passable[b]
        dist_m = float(np.hypot(dx, dy)) * CELL_M
        grade = (h[b] - h[a]) / dist_m * 100
        e = 0.5 * (eta[a] + eta[b])
        cost = o2_g_per_s(metabolic_rate_w(grade, e, G_RATIO_MARS)) * dist_m / EVA_WALK_SPEED_M_S
        src.append(idx[a][ok]); dst.append(idx[b][ok]); w.append(cost[ok])
    n = rows * cols
    return csr_matrix((np.concatenate(w), (np.concatenate(src), np.concatenate(dst))), shape=(n, n))


def trace(pred, target, shape):
    path = []
    cur = target
    while cur >= 0:
        path.append(cur)
        cur = pred[cur]
    ys, xs = np.unravel_index(np.array(path[::-1]), shape)
    return list(zip(xs.tolist(), ys.tolist()))


def path_o2(graph, path, shape):
    idx = [np.ravel_multi_index((y, x), shape) for x, y in path]
    return float(sum(graph[a, b] for a, b in zip(idx[:-1], idx[1:])))


# ============================================================
# 3. 시각화
# ============================================================

def hillshade(h):
    gy, gx = np.gradient(h, CELL_M)
    slope = np.pi / 2 - np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    az, alt = np.radians(360 - 315 + 90), np.radians(45)
    return np.clip(np.sin(alt) * np.sin(slope) + np.cos(alt) * np.cos(slope) * np.cos(az - aspect), 0, 1)


def km_extent(shape):
    rows, cols = shape
    return [0, cols * CELL_M / 1000, rows * CELL_M / 1000, 0]


def plot_walkback(h, valid, slope, return_o2, traverse_xy, base, summary):
    fig, ax = plt.subplots(figsize=(8.2, 9.4), facecolor="#0b0e15")
    style_ax(ax)
    ext = km_extent(h.shape)
    k = CELL_M / 1000
    ax.imshow(np.where(valid, hillshade(h), np.nan), cmap="gray", extent=ext, vmin=0, vmax=1)
    blocked = np.where(valid & (slope > MAX_WALK_SLOPE_DEG), 1.0, np.nan)
    ax.imshow(blocked, cmap="Reds", vmin=0, vmax=1.2, extent=ext, alpha=0.8)

    colors = ["#5cbcc3", "#e0ac53", "#b48ef0"]
    handles = []
    for x_g, c in zip(REMAINING_O2_G, colors):
        budget = x_g - O2_RESERVE_G
        # 도달 불가 칸(NoData·경사 상한 초과)은 NaN — 그 둘레에 가짜 등고선이 그려지지 않게 한다
        field = np.where(np.isfinite(return_o2), return_o2, np.nan)
        ax.contour(np.arange(h.shape[1]) * k, np.arange(h.shape[0]) * k, field, levels=[budget],
                   colors=c, linewidths=1.8)
        r_km = budget / LEVEL_O2_G_PER_M / 1000
        ax.add_patch(plt.Circle((base[0] * k, base[1] * k), r_km, fill=False, ls=":", color=c, lw=1.2,
                                clip_on=True))
        s = summary[str(x_g)]
        handles.append(plt.Line2D([], [], color=c, lw=1.8,
                                  label=f"{x_g} g left: safe area {s['area_km2']:.1f} km2 "
                                        f"(flat-circle {s['circle_area_km2']:.1f})"))

    for x, y in traverse_xy:
        ax.plot(x * k, y * k, color="#e9ebf2", lw=0.7, alpha=0.8)
    handles.append(plt.Line2D([], [], color="#e9ebf2", lw=0.8, label="Curiosity traverse (sol 3-1671)"))
    handles.append(plt.Line2D([], [], color="#a7aec1", lw=1.2, ls=":", label="flat-ground circle (same O2)"))
    handles.append(plt.Rectangle((0, 0), 1, 1, color="#c0392b", label=f"slope > {MAX_WALK_SLOPE_DEG:.0f} deg (no walk)"))
    _marker(ax, (base[0] * k, base[1] * k), "#a7e8a0", marker="*", size=220)
    ax.set_xlim(ext[0], ext[1])
    ax.set_ylim(ext[2], ext[3])
    ax.set_xlabel("km", color="#a7aec1", fontsize=8)
    ax.set_ylabel("km", color="#a7aec1", fontsize=8)
    ax.set_title(f"Walk-back radius to Bradbury Landing -- Gale crater HiRISE DTM ({CELL_M:.0f} m/px, 0.38 g)\n"
                 f"contour = O2 to walk home <= remaining - {O2_RESERVE_G:.0f} g reserve (30 min)",
                 color="#e9ebf2", fontsize=9.5)
    ax.legend(handles=handles, facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2",
              fontsize=7.5, loc="lower left")
    fig.tight_layout()
    fname = f"{OUT_DIR}/walkback_radius.png"
    fig.savefig(fname, dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"saved {fname}")


def plot_asymmetry(h, valid, out_o2, return_o2, base):
    """같은 지점이라도 '나가는 산소'와 '돌아오는 산소'가 다르다 — 비율 지도."""
    fig, ax = plt.subplots(figsize=(7.6, 8.6), facecolor="#0b0e15")
    style_ax(ax)
    ratio = np.where(valid & np.isfinite(out_o2) & np.isfinite(return_o2) & (out_o2 > 5),
                     return_o2 / np.maximum(out_o2, 1e-9), np.nan)
    im = ax.imshow(ratio, cmap="coolwarm", vmin=0.6, vmax=1.4, extent=km_extent(h.shape))
    k = CELL_M / 1000
    _marker(ax, (base[0] * k, base[1] * k), "#a7e8a0", marker="*", size=220)
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
    cb.set_label("return O2 / outbound O2  (>1 = coming home costs more)", color="#a7aec1", fontsize=8)
    cb.ax.tick_params(colors="#a7aec1", labelsize=7)
    ax.set_title("Out-and-back asymmetry from Bradbury Landing (O2-optimal both ways)",
                 color="#e9ebf2", fontsize=10)
    fig.tight_layout()
    fname = f"{OUT_DIR}/walkback_asymmetry.png"
    fig.savefig(fname, dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"saved {fname}")


def plot_route(h, valid, slope, routes, traverse_xy, title, fname):
    fig, ax = plt.subplots(figsize=(8.2, 9.4), facecolor="#0b0e15")
    style_ax(ax)
    ext = km_extent(h.shape)
    k = CELL_M / 1000
    ax.imshow(np.where(valid, hillshade(h), np.nan), cmap="gray", extent=ext, vmin=0, vmax=1)
    ax.imshow(np.where(valid & (slope > MAX_WALK_SLOPE_DEG), 1.0, np.nan), cmap="Reds", vmin=0, vmax=1.2,
              extent=ext, alpha=0.8)
    for x, y in traverse_xy:
        ax.plot(x * k, y * k, color="#e9ebf2", lw=0.6, alpha=0.5)
    for label, (path, color, ls) in routes.items():
        ax.plot([p[0] * k for p in path], [p[1] * k for p in path], ls, color=color, lw=2.0, label=label)
    first = next(iter(routes.values()))[0]
    _marker(ax, (first[0][0] * k, first[0][1] * k), "#a7e8a0", marker="*", size=200)
    _marker(ax, (first[-1][0] * k, first[-1][1] * k), "#e9ebf2", marker="X", size=110)
    ax.set_title(title, color="#e9ebf2", fontsize=9.5)
    ax.legend(facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2", fontsize=7.5, loc="lower left")
    fig.tight_layout()
    fig.savefig(fname, dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"saved {fname}")


# ============================================================
# 4. 실행
# ============================================================

def main():
    h, valid, rough_r, h1 = load_dtm_crop()
    rows, cols = h.shape
    slope = slope_deg_grid(h, CELL_M)
    passable = valid & (slope <= MAX_WALK_SLOPE_DEG)
    eta = eta_from_rock(rough_r)
    print(f"DTM crop {rows}x{cols} @ {CELL_M:.1f} m ({cols*CELL_M/1000:.1f} x {rows*CELL_M/1000:.1f} km), "
          f"valid {valid.mean()*100:.1f}%, slope>{MAX_WALK_SLOPE_DEG:.0f}deg {((slope > MAX_WALK_SLOPE_DEG) & valid).mean()*100:.1f}%")

    wps, traverse_xy = load_traverse(h.shape)

    # 검증: Curiosity 웨이포인트 고도 vs DTM 고도 (지오레퍼런스 확인)
    errs = []
    for p in wps:
        x, y = lonlat_to_cell(p["lon"], p["lat"])
        line, samp = int(round(y * BLOCK)), int(round(x * BLOCK))
        if 0 <= line < h1.shape[0] and 0 <= samp < h1.shape[1] and np.isfinite(h1[line, samp]):
            errs.append(float(h1[line, samp]) - p["elev_geoid"])
    errs = np.array(errs)
    print(f"웨이포인트 {len(errs)}개 고도 차(DTM - rover): median {np.median(errs):+.2f} m, "
          f"|err| p90 {np.percentile(np.abs(errs), 90):.2f} m, std {errs.std():.2f} m (일정한 오프셋이면 경사에는 무관)")

    base_wp = wps[0]  # sol 3, Bradbury Landing
    bx, by = (int(round(v)) for v in lonlat_to_cell(base_wp["lon"], base_wp["lat"]))
    base = (bx, by)
    base_idx = np.ravel_multi_index((by, bx), h.shape)
    assert passable[by, bx], "거점 칸이 통행 불가"

    graph = build_o2_graph(h, eta, passable)
    out_o2, out_pred = dijkstra(graph, directed=True, indices=base_idx, return_predecessors=True)
    ret_o2, ret_pred = dijkstra(graph.T.tocsr(), directed=True, indices=base_idx, return_predecessors=True)
    out_o2 = out_o2.reshape(h.shape)
    ret_o2 = ret_o2.reshape(h.shape)

    cell_km2 = (CELL_M / 1000) ** 2
    summary = {}
    for x_g in REMAINING_O2_G:
        budget = x_g - O2_RESERVE_G
        area = float((ret_o2 <= budget).sum() * cell_km2)
        r_m = budget / LEVEL_O2_G_PER_M
        yy, xx = np.mgrid[0:rows, 0:cols]
        circle = (np.hypot(xx - bx, yy - by) * CELL_M <= r_m) & valid
        circle_area = float(circle.sum() * cell_km2)
        unsafe_in_circle = float((circle & ~(ret_o2 <= budget)).sum() * cell_km2)
        summary[str(x_g)] = {"budget_after_reserve_g": budget, "area_km2": area,
                             "flat_radius_km": r_m / 1000, "circle_area_km2": circle_area,
                             "circle_area_actually_unsafe_km2": unsafe_in_circle}
        print(f"남은 O2 {x_g} g (예비 {O2_RESERVE_G:.0f} g 제외 {budget:.0f} g): 안전영역 {area:.2f} km2 | "
              f"평지 원(반경 {r_m/1000:.2f} km) {circle_area:.2f} km2 중 실제로는 못 돌아오는 면적 {unsafe_in_circle:.2f} km2")

    # 트래버스 웨이포인트별 귀환 산소 — "Curiosity가 갔던 곳에 사람이 있었다면 걸어서 돌아올 수 있나"
    wp_rows = []
    for p in wps:
        x, y = (int(round(v)) for v in lonlat_to_cell(p["lon"], p["lat"]))
        if 0 <= x < cols and 0 <= y < rows:
            r = float(ret_o2[y, x])
            wp_rows.append({"sol": p["sol"], "dist_total_m": p["dist_total_m"],
                            "straight_km": float(np.hypot(x - bx, y - by) * CELL_M / 1000),
                            "return_o2_g": r if np.isfinite(r) else None})

    # 화성 지형 경로 비교: 착륙지 -> DTM 내 마지막 웨이포인트(sol ~1671)
    # 목적지 = DTM 안에서 왕복 모두 도달 가능한 가장 마지막 sol의 웨이포인트(남쪽 끝은 NoData 경계)
    reachable = [r for r in wp_rows if r["return_o2_g"] is not None
                 and np.isfinite(out_o2[int(round(lonlat_to_cell(*_wp_lonlat(wps, r["sol"]))[1])),
                                        int(round(lonlat_to_cell(*_wp_lonlat(wps, r["sol"]))[0]))])]
    last = [p for p in wps if p["sol"] == max(r["sol"] for r in reachable)][-1]
    gx_, gy_ = (int(round(v)) for v in lonlat_to_cell(last["lon"], last["lat"]))
    goal_idx = np.ravel_multi_index((gy_, gx_), h.shape)
    o2_path = trace(out_pred, goal_idx, h.shape)
    o2_path_back = trace(ret_pred, goal_idx, h.shape)[::-1]  # goal -> base

    # 최단거리(경사 상한 동일 적용): 간선 길이로 재가중
    coo = graph.tocoo()
    r0, c0 = np.unravel_index(coo.row, h.shape)
    r1, c1 = np.unravel_index(coo.col, h.shape)
    dist_graph = csr_matrix((np.hypot(r1 - r0, c1 - c0) * CELL_M, (coo.row, coo.col)), shape=graph.shape)
    _, sp_pred = dijkstra(dist_graph, directed=True, indices=base_idx, return_predecessors=True)
    short_path = trace(sp_pred, goal_idx, h.shape)

    # Curiosity 실제 경로를 칸 단위로 이산화해 같은 산소 모델로 평가 (경사 상한 무시 — 로버 경로라)
    rover_cells = []
    for p in wps:
        if p["sol"] > last["sol"]:
            break
        x, y = (int(round(v)) for v in lonlat_to_cell(p["lon"], p["lat"]))
        if 0 <= x < cols and 0 <= y < rows and (not rover_cells or rover_cells[-1] != (x, y)):
            rover_cells.append((x, y))
    rover_o2 = rover_dist = 0.0
    from metabolic_navigation import step_o2_g
    for (x0, y0), (x1, y1) in zip(rover_cells[:-1], rover_cells[1:]):
        rover_o2 += step_o2_g(h, eta, CELL_M, x0, y0, x1, y1, G_RATIO_MARS)
        rover_dist += float(np.hypot(x1 - x0, y1 - y0)) * CELL_M

    def m(path):
        d = sum(float(np.hypot(b[0] - a[0], b[1] - a[1])) for a, b in zip(path[:-1], path[1:])) * CELL_M
        climb = sum(max(h[b[1], b[0]] - h[a[1], a[0]], 0) for a, b in zip(path[:-1], path[1:]))
        return {"dist_km": d / 1000, "o2_g": path_o2(graph, path, h.shape), "climb_m": float(climb),
                "max_slope_deg": float(max(slope[y, x] for x, y in path))}

    route_stats = {"shortest_capped": m(short_path), "o2_optimal_out": m(o2_path),
                   "o2_optimal_back": m(o2_path_back),
                   "curiosity_waypoints_as_walk": {"dist_km": rover_dist / 1000, "o2_g": rover_o2,
                                                   "note": "웨이포인트 직선 연결 — 실제 주행거리보다 짧게 잡힘"}}
    print(f"\n착륙지 -> sol {last['sol']} 지점:")
    for k_, v in route_stats.items():
        print(f"  {k_:<28} {json.dumps({a: (round(b, 2) if isinstance(b, float) else b) for a, b in v.items()}, ensure_ascii=False)}")

    plot_walkback(h, valid, slope, ret_o2, traverse_xy, base, summary)
    plot_asymmetry(h, valid, out_o2, ret_o2, base)
    plot_route(h, valid, slope, {
        f"shortest + slope cap: {route_stats['shortest_capped']['dist_km']:.1f} km, "
        f"O2 {route_stats['shortest_capped']['o2_g']:.0f} g": (short_path, "#a7e8a0", ":"),
        f"O2-optimal out: {route_stats['o2_optimal_out']['dist_km']:.1f} km, "
        f"O2 {route_stats['o2_optimal_out']['o2_g']:.0f} g": (o2_path, "#5cbcc3", "-"),
        f"O2-optimal back: {route_stats['o2_optimal_back']['dist_km']:.1f} km, "
        f"O2 {route_stats['o2_optimal_back']['o2_g']:.0f} g": (o2_path_back, "#e0ac53", "--"),
    }, traverse_xy, f"Bradbury Landing -> sol {last['sol']} site, Gale crater (0.38 g)",
        f"{OUT_DIR}/route_landing_to_sol{last['sol']}.png")

    stats = {
        "data": {"dtm": os.path.basename(DTM_PATH), "cell_m": CELL_M, "shape": [rows, cols],
                 "traverse": "NASA MMGIS MSL_waypoints.json / MSL_traverse.json"},
        "georef_check_dtm_minus_rover_elev_m": {"n": int(len(errs)), "median": float(np.median(errs)),
                                                "abs_p90": float(np.percentile(np.abs(errs), 90)),
                                                "std": float(errs.std())},
        "assumptions": {"MAX_WALK_SLOPE_DEG": MAX_WALK_SLOPE_DEG, "ROUGH_HIGH_M": ROUGH_HIGH_M,
                        "O2_RESERVE_G": O2_RESERVE_G, "LEVEL_O2_G_PER_H": LEVEL_O2_G_PER_H,
                        "base": "Bradbury Landing (sol 3 waypoint)"},
        "walkback": summary,
        "routes": route_stats,
        "waypoints_return_o2": wp_rows,
    }
    with open(f"{OUT_DIR}/walkback_stats.json", "w") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    print(f"saved {OUT_DIR}/walkback_stats.json")


if __name__ == "__main__":
    main()
