"""
sites.py의 지역 하나를 데모용 자료로 만든다 (Gale 이외 지역).

    python build_site_data.py jezero
    python build_site_data.py columbia
    -> ../outputs/demo/sites/<id>/ data.bin.gz, meta.json, basemap.jpg, hillshade.png, overview.png

Gale(build_demo_data.py)과 같은 계산을 쓰되, 귀환 트리는 넣지 않는다(브라우저가 지역을 열 때 계산).
그래서 파일 하나에 세 지역을 넣어도 크기가 공유 페이지 한도(16 MB) 안에 든다.

지역마다 자동으로 계산하는 것:
  - 10 m 칸 고도, 칸 안 1 m 기복으로 지형계수 η, 경사 20° 초과 = 통행 불가
  - 넘어짐 위험 등급(1 m 지형, fall_risk_map과 같은 정의), 지형 차폐(선량)
  - 거점 안테나 가시권, 중계기 최적 위치(comm_los.pick_relay와 같은 방법)
  - 예시 목적지: 설정에 위경도가 있으면 그 칸, 없으면 귀환 산소 150~230 g 칸 중 장애물에 가장 가까운 칸
  - 모래언덕 후보(dune_mask와 같은 방법). 지역마다 결과를 그림으로 확인하고 sites.py의 "dunes"로 끈다.
"""
from __future__ import annotations

import gzip
import json
import os
import re
import sys

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image
from scipy.ndimage import gaussian_filter, distance_transform_edt
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from sites import SITES
from metabolic_navigation import metabolic_rate_w, o2_g_per_s, eta_from_rock, slope_deg_grid, MAX_WALK_SLOPE_DEG, \
    G_RATIO_MARS, ETA_MIN, ETA_MAX
from human_mission_navigation import EVA_WALK_SPEED_M_S
from human_mission_risk import shielding_factor_grid
from mars_walkback import OFFSETS, O2_RESERVE_G, ROUGH_HIGH_M, hillshade
import comm_los
import fall_risk_map
import mars_walkback
import dune_mask

BLOCK = 10
NONE16 = 65535
TINT = np.array([[22, 14, 10], [92, 52, 32], [168, 104, 64], [222, 170, 120], [246, 222, 188]], float)


def read_label(img_path):
    head = open(img_path, "rb").read(65536).decode("latin-1", "replace")
    lab = {}
    for k in ("RECORD_BYTES", "LINES", "LINE_SAMPLES", "A_AXIS_RADIUS", "CENTER_LATITUDE", "CENTER_LONGITUDE",
              "MAP_SCALE", "LINE_PROJECTION_OFFSET", "SAMPLE_PROJECTION_OFFSET"):
        m = re.search(rf"\b{k}\s*=\s*(-?[\d.]+)", head)
        lab[k] = float(m.group(1))
    m = re.search(r"\^IMAGE\s*=\s*(\d+)", head)
    lab["IMAGE_RECORD"] = int(m.group(1))
    return lab


def lonlat_to_px(lab, lon, lat):
    """PDS 등장방형 투영: 1 m 화소 (line, sample)."""
    R = lab["A_AXIS_RADIUS"] * 1000
    line = lab["LINE_PROJECTION_OFFSET"] - R * np.radians(lat) / lab["MAP_SCALE"]
    sample = lab["SAMPLE_PROJECTION_OFFSET"] + R * np.radians(lon - lab["CENTER_LONGITUDE"]) * np.cos(np.radians(lab["CENTER_LATITUDE"])) / lab["MAP_SCALE"]
    return line, sample


def build(site_id):
    S = SITES[site_id]
    out = f"../outputs/demo/sites/{site_id}"
    os.makedirs(out, exist_ok=True)
    lab = read_label(S["dtm"])
    px = lab["MAP_SCALE"]
    cell = px * BLOCK
    # 도우미 모듈의 Gale 화소 크기를 이 지역 값으로
    comm_los.CELL_M = cell
    fall_risk_map.DTM_MAP_SCALE_M = px
    L, Sm = int(lab["LINES"]), int(lab["LINE_SAMPLES"])
    raw = np.memmap(S["dtm"], dtype="<f4", mode="r", offset=int(lab["RECORD_BYTES"]) * (lab["IMAGE_RECORD"] - 1), shape=(L, Sm))
    l0, l1 = S["crop_lines"]; s0, s1 = S["crop_samples"]
    l1 = l0 + (min(l1, L) - l0) // BLOCK * BLOCK
    s1 = s0 + (min(s1, Sm) - s0) // BLOCK * BLOCK
    h1 = np.array(raw[l0:l1, s0:s1], dtype=np.float32)
    h1[~(h1 > -1e30)] = np.nan
    rows, cols = h1.shape[0] // BLOCK, h1.shape[1] // BLOCK
    blocks = h1.reshape(rows, BLOCK, cols, BLOCK)
    valid = np.isfinite(blocks).all(axis=(1, 3))
    with np.errstate(invalid="ignore"):
        h = np.nanmean(blocks, axis=(1, 3)).astype(np.float64)
    filled = np.where(np.isfinite(h1), h1, np.nanmean(h1)).astype(np.float32)
    rough = np.nanstd((h1 - gaussian_filter(filled, sigma=3)).reshape(rows, BLOCK, cols, BLOCK), axis=(1, 3))
    h[~valid] = np.nanmean(h[valid]); rough[~valid] = 0
    eta = eta_from_rock(np.clip(rough / ROUGH_HIGH_M, 0, 1))
    slope = slope_deg_grid(h, cell)
    passable = valid & (slope <= MAX_WALK_SLOPE_DEG)
    shielding = np.where(valid, shielding_factor_grid(h), 0.0)

    if S["base"].get("auto") == "flat":        # 착륙지가 없는 지역: 반경 1 km 안에 걸을 수 있는 평탄한 칸이 가장 많은 곳
        from scipy.ndimage import uniform_filter
        good = (passable & (slope < 8)).astype(float)
        score = uniform_filter(good, size=int(2000 / cell)) * passable * (slope < 5)
        by, bx = np.unravel_index(np.argmax(score), score.shape)
        bx, by = int(bx), int(by)
    else:
        bl, bs = lonlat_to_px(lab, S["base"]["lon"], S["base"]["lat"])
        bx, by = int((bs - s0) // BLOCK), int((bl - l0) // BLOCK)
    assert 0 <= bx < cols and 0 <= by < rows and valid[by, bx], f"거점이 범위 밖이거나 NoData: {(bx, by)}"
    passable[by, bx] = True

    # 넘어짐 위험 (1 m)
    frac, _, _, _, enough = fall_risk_map.hazard_fraction(h1)
    ok = valid & enough
    cls = np.where(ok, np.where(frac >= fall_risk_map.HIGH_FRAC, 2, np.where(frac >= fall_risk_map.MED_FRAC, 1, 0)), 0).astype(np.uint8)
    del h1, filled

    # 귀환 산소 (기본 모델) -> 기준 면적, 중계기 후보, 예시 목적지
    idx = np.arange(rows * cols).reshape(rows, cols)
    src, dst, w = [], [], []
    for dx, dy in OFFSETS:
        ys, ye = max(0, -dy), rows - max(0, dy); xs, xe = max(0, -dx), cols - max(0, dx)
        a = (slice(ys, ye), slice(xs, xe)); b = (slice(ys + dy, ye + dy), slice(xs + dx, xe + dx))
        okk = passable[a] & passable[b]
        d = float(np.hypot(dx, dy)) * cell
        cost = o2_g_per_s(metabolic_rate_w((h[b] - h[a]) / d * 100, 0.5 * (eta[a] + eta[b]), G_RATIO_MARS)) * d / EVA_WALK_SPEED_M_S
        src.append(idx[a][okk]); dst.append(idx[b][okk]); w.append(cost[okk])
    g = csr_matrix((np.concatenate(w), (np.concatenate(src), np.concatenate(dst))), shape=(rows * cols,) * 2)
    ret = dijkstra(g.T.tocsr(), directed=True, indices=by * cols + bx).reshape(rows, cols)
    km2 = (cell / 1000) ** 2
    budget = 150 - O2_RESERVE_G
    returnable = valid & (ret <= budget)

    base_vis, _ = comm_los.viewshed(h, valid, (bx, by), comm_los.BASE_ANT_M, comm_los.SUIT_ANT_M)
    relay, relay_vis, n_cand = comm_los.pick_relay(h, valid, base_vis, returnable)

    gcfg = S["goal"]
    if "lat" in gcfg:
        gl, gs = lonlat_to_px(lab, gcfg["lon"], gcfg["lat"])
        gx, gy = int((gs - s0) // BLOCK), int((gl - l0) // BLOCK)
        if not np.isfinite(ret[gy, gx]):          # 못 가는 칸이면 가장 가까운 갈 수 있는 칸
            yy, xx = np.nonzero(np.isfinite(ret))
            k = np.argmin((yy - gy) ** 2 + (xx - gx) ** 2); gx, gy = int(xx[k]), int(yy[k])
    else:                                       # 우회 비율(귀환 산소 ÷ 직선으로 걸을 때 산소)이 가장 큰 칸 = 장애물을 돌아가야 하는 곳
        from scipy.ndimage import binary_erosion
        inner = binary_erosion(valid, iterations=15)          # NoData 가장자리 150 m 안쪽만
        yy, xx = np.mgrid[0:rows, 0:cols]
        straight = np.hypot(yy - by, xx - bx) * cell * float(o2_g_per_s(metabolic_rate_w(0.0, 1.0, G_RATIO_MARS))) / EVA_WALK_SPEED_M_S
        cand = inner & np.isfinite(ret) & (ret >= 150) & (ret <= 230) & (straight > 0)
        detour = np.where(cand, ret / np.maximum(straight, 1e-9), -np.inf)
        gy, gx = np.unravel_index(np.argmax(detour), detour.shape); gx, gy = int(gx), int(gy)
    dunes = np.zeros_like(valid)
    if S.get("dunes", True):
        dunes, _, thr = dune_mask.build((rows, cols), S["ortho"], (l0, l1), (s0, s1))
        dunes &= valid

    flags = (valid.astype(np.uint8) | (base_vis.astype(np.uint8) << 1) | (relay_vis.astype(np.uint8) << 2)
             | (passable.astype(np.uint8) << 3) | (dunes.astype(np.uint8) << 4))
    blobs, layout, off = [], {}, 0

    def add(name, arr):
        nonlocal off
        bb = np.ascontiguousarray(arr).tobytes()
        layout[name] = [off, len(bb), str(arr.dtype)]
        blobs.append(bb); off += len(bb)

    h_min = float(h[valid].min())
    h_step = 0.01 if h[valid].max() - h_min < 650 else 0.02
    add("cls", cls); add("flags", flags)
    add("h", np.where(valid, np.clip(np.rint((h - h_min) / h_step), 0, NONE16 - 1), 0).astype("<u2"))
    add("eta", np.clip(np.rint((eta - ETA_MIN) / (ETA_MAX - ETA_MIN) * 255), 0, 255).astype(np.uint8))
    add("shield", np.clip(np.rint(shielding * 255), 0, 255).astype(np.uint8))
    gz = gzip.compress(b"".join(blobs), compresslevel=9)
    open(f"{out}/data.bin.gz", "wb").write(gz)

    # 바탕 사진 (4 m) + 음영도
    full = dune_mask.decode_ortho_4m(S["ortho"])
    gq = full[l0 // 4:l1 // 4, s0 // 4:s1 // 4].astype(float)
    vm = gq > 0
    lo, hi = np.percentile(gq[vm], [0.5, 99.5])
    t = np.clip((gq - lo) / (hi - lo), 0, 1) ** 0.9
    pos = t * (len(TINT) - 1); i0 = np.clip(pos.astype(int), 0, len(TINT) - 2); f = (pos - i0)[..., None]
    rgb = TINT[i0] * (1 - f) + TINT[i0 + 1] * f; rgb[~vm] = 0
    Image.fromarray(rgb.astype(np.uint8)).save(f"{out}/basemap.jpg", quality=72, optimize=True, progressive=True)
    mars_walkback.CELL_M = cell
    plt.imsave(f"{out}/hillshade.png", np.nan_to_num(np.where(valid, hillshade(h), np.nan), nan=0.0), cmap="gray", vmin=0, vmax=1)

    stats = {"valid_km2": float(valid.sum() * km2), "relief_m": float(h[valid].max() - h_min),
             "impassable_pct": float((valid & ~passable).sum() / valid.sum() * 100),
             "fall_high_pct": float((cls == 2).sum() / valid.sum() * 100),
             "baseline_km2": float(returnable.sum() * km2), "base_vis_km2": float(base_vis.sum() * km2),
             "dune_km2": float(dunes.sum() * km2), "relay_km_from_base": float(np.hypot(relay[0] - bx, relay[1] - by) * cell / 1000),
             "goal_km_from_base": float(np.hypot(gx - bx, gy - by) * cell / 1000), "goal_return_o2_g": float(ret[gy, gx]),
             "goal_detour_ratio": float(ret[gy, gx] / (np.hypot(gx - bx, gy - by) * cell * float(o2_g_per_s(metabolic_rate_w(0.0, 1.0, G_RATIO_MARS))) / EVA_WALK_SPEED_M_S))}
    meta = {"site": {"id": site_id, "name": S["name"], "short": S["short"], "description": S["description"], "description_en": S.get("description_en", ""), "source": S["source"],
                     "base_name": S["base"]["name"], "goal_name": gcfg["name"], "stats": stats},
            "rows": rows, "cols": cols, "cell_m": cell, "layout": layout, "h_min": h_min, "h_step": h_step,
            "eta_min": ETA_MIN, "eta_max": ETA_MAX, "none16": NONE16, "offsets": OFFSETS,
            "base": [bx, by], "relay": [int(relay[0]), int(relay[1])], "goal": [gx, gy], "traverse": []}
    json.dump(meta, open(f"{out}/meta.json", "w"), ensure_ascii=False)

    # 확인용 그림
    fig, ax = plt.subplots(figsize=(7, 7 * rows / cols))
    ext = [0, cols * cell / 1000, rows * cell / 1000, 0]
    ax.imshow(np.where(valid, hillshade(h), np.nan), cmap="gray", extent=ext)
    ax.imshow(np.where(valid & ~passable, 1.0, np.nan), cmap="Reds", vmin=0, vmax=1.3, alpha=0.6, extent=ext)
    ax.imshow(np.where(returnable, 1.0, np.nan), cmap="winter", vmin=0, vmax=1.6, alpha=0.35, extent=ext)
    ax.imshow(np.where(dunes, 1.0, np.nan), cmap="autumn", vmin=0, vmax=1, alpha=0.5, extent=ext)
    k = cell / 1000
    for (x, y), m, c in (((bx, by), "*", "#a7e8a0"), ((gx, gy), "o", "#ffd23f"), (relay, "D", "#e2794d")):
        ax.plot((x + 0.5) * k, (y + 0.5) * k, marker=m, color=c, ms=12, mec="k")
    ax.set_title(f"{S['short']}: blue = return with 150 g O2 ({stats['baseline_km2']:.1f} km2), red = slope > 20 deg "
                 f"({stats['impassable_pct']:.1f}%), orange = dune candidates ({stats['dune_km2']:.1f} km2)", fontsize=8)
    fig.tight_layout(); fig.savefig(f"{out}/overview.png", dpi=110); plt.close(fig)
    print(f"[{site_id}] {rows}x{cols} @ {cell:.2f} m, gz {len(gz) / 1e6:.2f} MB, basemap {os.path.getsize(out + '/basemap.jpg') / 1e6:.2f} MB, "
          + ", ".join(f"{k_} {v:.2f}" for k_, v in stats.items()))
    return meta


if __name__ == "__main__":
    from sites import DEMO_SITES
    for sid in (sys.argv[1:] or DEMO_SITES):
        build(sid)
