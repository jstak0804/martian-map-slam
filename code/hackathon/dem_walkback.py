"""
새 지형(DEM)이 오면 바로 귀환 반경을 계산한다. 보고서 15와 같은 모델(Pandolf, 화성 0.38 g, 경사 20° 한도).

    python -m hackathon.dem_walkback --dem ../data/hackathon_2026/site.tif --name hackathon_2026 \
        [--pixel-m 1.0] [--base-rc 120 340] [--crop r0 r1 c0 c1] [--cell-m 10]

- 1 m급 지형이면 칸 안 기복으로 지형계수 η(바위 부담)를 만든다(mars_walkback과 같은 방법).
- 거점을 안 주면 지도 가운데에서 가장 평평한 칸을 고른다.
- 결과: 귀환 산소 격자(.npy), 귀환 반경 그림, 면적 통계(JSON).
  이 격자는 나중에 올인원 데모를 새 지역으로 만들 때 입력이 된다(README의 "새 지역 데모" 참고).
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from hackathon.loaders import load_dem
from metabolic_navigation import metabolic_rate_w, o2_g_per_s, eta_from_rock, MAX_WALK_SLOPE_DEG, G_RATIO_MARS
from human_mission_navigation import EVA_WALK_SPEED_M_S
from mars_walkback import O2_RESERVE_G, OFFSETS, ROUGH_HIGH_M

OUT_ROOT = "../outputs/hackathon"


def block_mean(h1, block):
    r, c = h1.shape[0] // block, h1.shape[1] // block
    b = h1[: r * block, : c * block].reshape(r, block, c, block)
    fin = np.isfinite(b).mean(axis=(1, 3))
    with np.errstate(invalid="ignore"):
        h = np.nanmean(b, axis=(1, 3))
    return h, fin >= 0.9, b


def walkback(dem, name, pixel_m=None, base_rc=None, crop=None, cell_m=10.0, o2_list=(150, 300, 450)):
    h1, px, info = load_dem(dem)
    px = pixel_m or px
    if not px:
        raise SystemExit("화소 크기를 알 수 없습니다: --pixel-m 으로 주세요.")
    if crop:
        r0, r1, c0, c1 = crop
        h1 = h1[r0:r1, c0:c1]
    block = max(1, int(round(cell_m / px)))
    cell = px * block
    h, valid, blocks = block_mean(h1, block)
    if px <= 2.0 and block > 1:                     # 1 m급: 칸 안 기복 -> η
        filled = np.where(np.isfinite(h1), h1, np.nanmean(h1))
        hp = (filled - gaussian_filter(filled, sigma=3))[: h.shape[0] * block, : h.shape[1] * block]
        rough = hp.reshape(h.shape[0], block, h.shape[1], block).std(axis=(1, 3))
        eta = eta_from_rock(np.clip(rough / ROUGH_HIGH_M, 0, 1))
    else:
        eta = np.ones_like(h)
    h = np.where(valid, h, np.nanmean(h))
    gy, gx = np.gradient(h, cell)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    passable = valid & (slope <= MAX_WALK_SLOPE_DEG)
    rows, cols = h.shape
    if base_rc is None:                             # 가운데 근처에서 가장 평평한 칸
        cy, cx = rows // 2, cols // 2
        rr = max(5, min(rows, cols) // 10)
        win = np.where(passable[cy - rr:cy + rr, cx - rr:cx + rr], slope[cy - rr:cy + rr, cx - rr:cx + rr], np.inf)
        iy, ix = np.unravel_index(np.argmin(win), win.shape)
        base_rc = (cy - rr + iy, cx - rr + ix)
    by, bx = base_rc
    passable[by, bx] = True
    idx = np.arange(rows * cols).reshape(rows, cols)
    src, dst, w = [], [], []
    for dx, dy in OFFSETS:
        ys, ye = max(0, -dy), rows - max(0, dy)
        xs, xe = max(0, -dx), cols - max(0, dx)
        a = (slice(ys, ye), slice(xs, xe)); b = (slice(ys + dy, ye + dy), slice(xs + dx, xe + dx))
        ok = passable[a] & passable[b]
        d = float(np.hypot(dx, dy)) * cell
        grade = (h[b] - h[a]) / d * 100
        cost = o2_g_per_s(metabolic_rate_w(grade, 0.5 * (eta[a] + eta[b]), G_RATIO_MARS)) * d / EVA_WALK_SPEED_M_S
        src.append(idx[a][ok]); dst.append(idx[b][ok]); w.append(cost[ok])
    g = csr_matrix((np.concatenate(w), (np.concatenate(src), np.concatenate(dst))), shape=(rows * cols,) * 2)
    ret = dijkstra(g.T.tocsr(), directed=True, indices=by * cols + bx).reshape(rows, cols)   # 각 칸 -> 거점
    km2 = (cell / 1000) ** 2
    stats = {"dem": dem, "format": info.get("format"), "pixel_m": px, "cell_m": cell, "grid": [rows, cols],
             "base_rc": [int(by), int(bx)], "valid_km2": float(valid.sum() * km2),
             "passable_km2": float(passable.sum() * km2), "eta_from_roughness": bool(px <= 2.0 and block > 1),
             "relief_m": float(np.nanmax(h[valid]) - np.nanmin(h[valid])),
             "areas_km2": {str(o): float(((ret <= o - O2_RESERVE_G) & valid).sum() * km2) for o in o2_list}}
    out_dir = os.path.join(OUT_ROOT, name, "dem_walkback", os.path.splitext(os.path.basename(dem))[0])
    os.makedirs(out_dir, exist_ok=True)
    np.save(os.path.join(out_dir, "return_o2_g.npy"), ret.astype(np.float32))
    np.save(os.path.join(out_dir, "elevation_cell.npy"), np.where(valid, h, np.nan).astype(np.float32))
    with open(os.path.join(out_dir, "walkback_stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=1)
    ls = (np.pi / 2 - np.arctan(np.hypot(gx, gy)))
    shade = np.clip(np.sin(np.radians(45)) * np.sin(ls) + np.cos(np.radians(45)) * np.cos(ls) * np.cos(np.radians(45) - np.arctan2(-gx, gy)), 0, 1)
    ext = [0, cols * cell / 1000, rows * cell / 1000, 0]
    fig, ax = plt.subplots(figsize=(7, 7 * rows / max(cols, 1) + 0.6))
    ax.imshow(np.where(valid, shade, np.nan), cmap="gray", extent=ext)
    ax.imshow(np.where(valid & ~passable, 1.0, np.nan), cmap="Reds", vmin=0, vmax=1.5, alpha=0.5, extent=ext)
    yy, xx = (np.arange(rows) + 0.5) * cell / 1000, (np.arange(cols) + 0.5) * cell / 1000
    cs = ax.contour(xx, yy, np.where(valid & np.isfinite(ret), ret, np.nan), levels=[o - O2_RESERVE_G for o in o2_list],
                    colors=["#3fc1cc", "#ffd23f", "#ff8a65"], linewidths=1.4)
    ax.clabel(cs, fmt={o - O2_RESERVE_G: f"{o} g" for o in o2_list}, fontsize=8)
    ax.plot((bx + 0.5) * cell / 1000, (by + 0.5) * cell / 1000, marker="*", color="#a7e8a0", ms=14, mec="k")
    ax.set_xlabel("km"); ax.set_ylabel("km")
    ax.set_title(f"walk-back radius by O2 left (reserve {O2_RESERVE_G:.0f} g), red = slope > {MAX_WALK_SLOPE_DEG:.0f} deg\n"
                 + ", ".join(f"{o} g: {stats['areas_km2'][str(o)]:.2f} km2" for o in o2_list), fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(out_dir, "walkback_map.png"), dpi=120); plt.close(fig)
    print(f"귀환 반경 ({os.path.basename(dem)}): 격자 {rows}x{cols} @ {cell:.1f} m, "
          + ", ".join(f"{o} g {stats['areas_km2'][str(o)]:.2f} km²" for o in o2_list) + f" -> {out_dir}")
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dem", required=True)
    ap.add_argument("--name", default="hackathon_2026")
    ap.add_argument("--pixel-m", type=float)
    ap.add_argument("--base-rc", type=int, nargs=2)
    ap.add_argument("--crop", type=int, nargs=4, metavar=("R0", "R1", "C0", "C1"))
    ap.add_argument("--cell-m", type=float, default=10.0)
    a = ap.parse_args()
    walkback(a.dem, a.name, a.pixel_m, a.base_rc, a.crop, a.cell_m)
