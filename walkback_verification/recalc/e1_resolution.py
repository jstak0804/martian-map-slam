"""계획 E 1번: 지형 해상도 영향 (코드 변경 없음)

실행: cd code && ../recalc/.venv/bin/python ../recalc/e1_resolution.py
  (a) sol 1282 귀환 경로(10 m 칸, 현재 모델)를 1 m DTM 위에서 1 m 간격으로 다시 따라가며 산소를 계산.
      DTM 잡음이 1 m 경사를 부풀릴 수 있어 가우시안 평활(σ 3 m, 5 m)판도 함께 낸다.
  (b) 격자 수렴: 블록 20 / 10 / 5 m로 같은 계산(16방향, 현재 모델)을 해 산소 100·150·200 g 면적 비교.
      메모리 때문에 모든 해상도에서 거점 주변 같은 창(±WIN_M)만 쓴다.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.getcwd())
import numpy as np  # noqa: E402
from scipy.ndimage import gaussian_filter  # noqa: E402
from scipy.sparse import csr_matrix  # noqa: E402
from scipy.sparse.csgraph import dijkstra  # noqa: E402

import metabolic_model as mm  # noqa: E402
from mars_walkback import (  # noqa: E402
    BLOCK, CELL_M, DTM_MAP_SCALE_M, MAX_WALK_SLOPE_DEG, OFFSETS, ROUGH_HIGH_M, _wp_lonlat, build_o2_graph,
    eta_from_rock, load_dtm_crop, load_traverse, lonlat_to_cell, offset_ok, slope_deg_grid, trace,
)

OUT = os.path.abspath(os.path.join(os.getcwd(), "..", "recalc", "outputs_e"))
WIN_M = 4500.0          # 산소 200 g 평지 반경(약 4.5 km)을 덮는 창


def o2_along(xy_m, h1, scale_m):
    """1 m 간격 점열(1 m 픽셀 좌표)을 따라 걸을 때 산소(g)와 시간(s). 경사는 인접 점 고도차."""
    z = h1[np.round(xy_m[:, 1]).astype(int), np.round(xy_m[:, 0]).astype(int)]
    d = np.hypot(*np.diff(xy_m, axis=0).T) * scale_m
    grade = np.diff(z) / d * 100
    mr, v = mm.edge_rate(grade, 1.0, mm.G_RATIO_MARS)
    t = d / v
    return float(np.sum(mm.o2_g_per_s(mr) * t)), float(np.sum(t)), grade


def part_a(h, eta, passable, h1, wps):
    rows, cols = h.shape
    bx, by = (int(round(v)) for v in lonlat_to_cell(wps[0]["lon"], wps[0]["lat"]))
    gx, gy = (int(round(v)) for v in lonlat_to_cell(*_wp_lonlat(wps, 1282)))
    g = build_o2_graph(h, eta, passable)
    ret, pred = dijkstra(g.T.tocsr(), directed=True, indices=by * cols + bx, return_predecessors=True)
    path = trace(pred, gy * cols + gx, h.shape)[::-1]          # 걷는 순서: 목표 → 거점
    assert path[0] == (gx, gy) and path[-1] == (bx, by)
    # 10 m 경로를 eta=1로 다시 계산(1 m 비교와 같은 조건)
    pts10 = np.array(path, float)
    eta1 = np.ones_like(h)
    o2_10 = 0.0; t_10 = 0.0
    for (x0, y0), (x1, y1) in zip(path[:-1], path[1:]):
        dm = np.hypot(x1 - x0, y1 - y0) * CELL_M
        mr, v = mm.edge_rate(np.array((h[y1, x1] - h[y0, x0]) / dm * 100), np.array(1.0), mm.G_RATIO_MARS)
        o2_10 += float(mm.o2_g_per_s(mr)) * dm / float(v); t_10 += dm / float(v)
    # 1 m 점열: 10 m 칸 중심(1 m 픽셀 좌표 = 칸*BLOCK + (BLOCK-1)/2)을 잇는 선을 1 m 간격으로
    cen = pts10 * BLOCK + (BLOCK - 1) / 2
    seg = []
    for p, q in zip(cen[:-1], cen[1:]):
        n = max(1, int(round(np.hypot(*(q - p)))))
        seg.append(p + (q - p) * (np.arange(n) / n)[:, None])
    seg.append(cen[-1:])
    xy = np.concatenate(seg)
    filled = np.where(np.isfinite(h1), h1, np.nanmean(h1))
    out = {"path_cells": len(path), "path_len_km": round(float(np.sum(np.hypot(*np.diff(xy, axis=0).T)) * DTM_MAP_SCALE_M / 1000), 3),
           "graph_return_o2_g_with_eta": round(float(ret[gy * cols + gx]), 2),
           "o2_10m_eta1_g": round(o2_10, 2), "time_10m_h": round(t_10 / 3600, 3), "one_m": {}}
    nan_on_path = int(np.sum(~np.isfinite(h1[np.round(xy[:, 1]).astype(int), np.round(xy[:, 0]).astype(int)])))
    out["nan_points_on_1m_path"] = nan_on_path
    for name, sig in [("raw", 0), ("gauss_sigma3m", 3), ("gauss_sigma5m", 5)]:
        z = filled if sig == 0 else gaussian_filter(filled, sig)
        o2, t, grade = o2_along(xy, z, DTM_MAP_SCALE_M)
        out["one_m"][name] = {"o2_g": round(o2, 2), "time_h": round(t / 3600, 3), "ratio_to_10m": round(o2 / o2_10, 4),
                              "abs_grade_p50_p90_p99": [round(float(np.percentile(np.abs(grade), q)), 1) for q in (50, 90, 99)],
                              "share_steeper_than_36pct": round(float(np.mean(np.abs(grade) > 36.4)), 4)}
    return out


def grid_at(h1, block, c_line, c_samp):
    """1 m DTM에서 거점 중심 창을 잘라 block m 칸으로 평균. load_dtm_crop과 같은 방법(평균 고도, 거칠기)."""
    half = int(WIN_M / DTM_MAP_SCALE_M) // block * block
    l0, s0 = max(0, c_line - half), max(0, c_samp - half)
    l0 -= (c_line - l0) % block; s0 -= (c_samp - s0) % block   # 거점 픽셀이 블록 경계와 같은 위상이 되게
    l0, s0 = max(0, l0), max(0, s0)
    l1 = l0 + (min(h1.shape[0], c_line + half) - l0) // block * block
    s1 = s0 + (min(h1.shape[1], c_samp + half) - s0) // block * block
    w = h1[l0:l1, s0:s1]
    rows, cols = w.shape[0] // block, w.shape[1] // block
    b = w.reshape(rows, block, cols, block)
    valid = np.isfinite(b).all(axis=(1, 3))
    with np.errstate(all="ignore"):
        h = np.nanmean(b, axis=(1, 3))
        filled = np.where(np.isfinite(w), w, np.nanmean(w))
        hp = w - gaussian_filter(filled, sigma=3)
        rough = np.nanstd(hp.reshape(rows, block, cols, block), axis=(1, 3))
    h[~valid] = np.nanmean(h); rough[~valid] = 0
    eta = eta_from_rock(np.clip(rough / ROUGH_HIGH_M, 0, 1))
    cell = DTM_MAP_SCALE_M * block
    passable = valid & (slope_deg_grid(h, cell) <= MAX_WALK_SLOPE_DEG)
    base = ((c_samp - s0) // block, (c_line - l0) // block)
    return h, eta, passable, cell, base


def graph_at(h, eta, passable, cell):
    rows, cols = h.shape
    idx = np.arange(rows * cols).reshape(rows, cols)
    src, dst, w = [], [], []
    for dx, dy in OFFSETS:
        a, b, ok = offset_ok(passable, dx, dy)
        dist = float(np.hypot(dx, dy)) * cell
        mr, v = mm.edge_rate((h[b] - h[a]) / dist * 100, 0.5 * (eta[a] + eta[b]), mm.G_RATIO_MARS)
        src.append(idx[a][ok]); dst.append(idx[b][ok]); w.append((mm.o2_g_per_s(mr) * dist / v)[ok])
    n = rows * cols
    return csr_matrix((np.concatenate(w), (np.concatenate(src), np.concatenate(dst))), shape=(n, n))


def part_b(h1_full_crop, wps):
    from mars_walkback import CROP_LINES, CROP_SAMPLES  # noqa: F401  (h1은 load_dtm_crop의 잘린 1 m 배열)
    x, y = lonlat_to_cell(wps[0]["lon"], wps[0]["lat"])
    c_line, c_samp = int(round(y * BLOCK)) + BLOCK // 2, int(round(x * BLOCK)) + BLOCK // 2  # 10 m 거점 칸의 중심 픽셀
    res = {}
    for block in (20, 10, 5):
        h, eta, passable, cell, base = grid_at(h1_full_crop, block, c_line, c_samp)
        bx, by = base
        if not passable[by, bx]:
            res[str(block)] = {"error": "base not passable"}; continue
        g = graph_at(h, eta, passable, cell)
        ret = dijkstra(g.T.tocsr(), directed=True, indices=by * h.shape[1] + bx).reshape(h.shape)
        km2 = (cell / 1000) ** 2
        res[str(block)] = {"cell_m": round(cell, 3), "shape": list(h.shape), "n_edges": int(g.nnz),
                           "passable_share": round(float(passable.mean()), 4),
                           **{f"area_km2_{x}g": round(float((ret <= x - mm.O2_RESERVE_G).sum() * km2), 3) for x in (100, 150, 200)}}
        print(block, res[str(block)], flush=True)
        del g
    return res


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    h, valid, rough, h1 = load_dtm_crop()
    passable = valid & (slope_deg_grid(h, CELL_M) <= MAX_WALK_SLOPE_DEG)
    eta = eta_from_rock(rough)
    wps, _ = load_traverse(h.shape)
    res = {"model": mm.describe(), "window_m": WIN_M}
    res["a_route_1m"] = part_a(h, eta, passable, h1, wps)
    print(json.dumps(res["a_route_1m"], ensure_ascii=False, indent=1), flush=True)
    res["b_grid"] = part_b(h1, wps)
    json.dump(res, open(f"{OUT}/e1_resolution.json", "w"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
