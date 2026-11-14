"""
지도 둘레 배경: CTX 모자이크(JPL Mars Trek / Esri OnMars, 약 5 m)를 데모 격자보다 넓게(사방으로 격자 크기만큼) 받아,
같은 좌표에 맞춘 배경 그림을 만든다. HiRISE 띠 바깥과 화면 여백을 실제 화성 지형으로 채운다.

    python build_context_layers.py            # gale, jezero, aram
    -> ../outputs/demo/context/<site>.jpg, <site>.json  ({x, y, w, h}: 격자 칸 단위 배치)

타일: https://astro.arcgis.com/arcgis/rest/services/OnMars/CTX/MapServer/tile/{z}/{row}/{col}
      (Mars Trek WMTS CTX_beta01_uncontrolled_5m_Caltech의 ResourceURL) 등장방형, 512 px, 타일 한 장 = 180/2^z 도.
색은 HiRISE 바탕 사진과 같은 표시용 가색(TINT)으로 입힌다.
"""
from __future__ import annotations

import io
import json
import os
import sys
import urllib.request

import numpy as np
from PIL import Image
from scipy.ndimage import map_coordinates

from build_trek_layers import cell_lonlat

URL = "https://astro.arcgis.com/arcgis/rest/services/OnMars/CTX/MapServer/tile/{z}/{y}/{x}"
Z = 11                    # 타일 한 장 0.088°, 화소 약 10 m
TILE = 512
CACHE = "../data/ctx_tiles"
MARGIN = 1.0              # 격자 크기의 몇 배만큼 사방으로 넓힐지
SCALE = 0.5               # 배경 화소 = 격자 칸 2개 (20 m)
TINT = np.array([[22, 14, 10], [92, 52, 32], [168, 104, 64], [222, 170, 120], [246, 222, 188]], float)


def tile(z, y, x):
    """타일 받기: 연결이 끊겨 잘린 파일은 지우고 최대 4번까지 다시 받음."""
    import time
    p = f"{CACHE}/{z}/{y}/{x}.png"
    os.makedirs(os.path.dirname(p), exist_ok=True)
    for attempt in range(4):
        if not os.path.exists(p):
            import subprocess                        # 이 서버는 curl이 더 안정적
            r = subprocess.run(["curl", "-s", "-f", "-A", "Mozilla/5.0", "--max-time", "90", "-o", p, URL.format(z=z, y=y, x=x)])
            if r.returncode != 0:
                if os.path.exists(p): os.remove(p)
                print("  tile retry", z, y, x, r.returncode); time.sleep(2 + attempt * 2); continue
        try:
            return np.asarray(Image.open(p).convert("L"), np.float32)
        except Exception:
            os.remove(p); time.sleep(2 + attempt * 2)
    print("  tile miss", z, y, x)
    return np.zeros((TILE, TILE), np.float32)


# 사용자가 받아 둔 로컬 CTX 모자이크 (ISIS 등장방형, 라벨의 Mapping 그룹 값)
LOCAL = {
    "jezero": {"path": "../data/ctx_jezero/JEZ_ctx_B_soc_008_orthoMosaic_6m_Eqc_latTs0_lon0.tif",
               "lon0": 77.1604654592236727, "lat0": 18.7211944818728036, "ppd": 9879.11625388436914,
               "source": "CTX orthomosaic 6 m (Jezero, Mars 2020 project / MRO CTX, NASA/JPL-Caltech/MSSS)"},
}


def build(site):
    lon, lat, meta = cell_lonlat(site)
    lon = np.where(lon > 180, lon - 360, lon)
    R, C = meta["rows"], meta["cols"]
    # 격자 (x, y) -> (경도, 위도) 는 거의 선형: 모서리로 맞춰 바깥으로 연장
    A = np.c_[np.ones(4), [0.5, C - 0.5, 0.5, C - 0.5], [0.5, 0.5, R - 0.5, R - 0.5]]
    corners = [(0, 0), (0, C - 1), (R - 1, 0), (R - 1, C - 1)]
    clon = np.linalg.lstsq(A, [lon[r, c] for r, c in corners], rcond=None)[0]
    clat = np.linalg.lstsq(A, [lat[r, c] for r, c in corners], rcond=None)[0]
    mx, my = MARGIN * C, MARGIN * R
    w, h = int((C + 2 * mx) * SCALE), int((R + 2 * my) * SCALE)
    yy, xx = np.mgrid[0:h, 0:w]
    gx, gy = -mx + (xx + 0.5) / SCALE, -my + (yy + 0.5) / SCALE
    LON = clon[0] + clon[1] * gx + clon[2] * gy
    LAT = clat[0] + clat[1] * gx + clat[2] * gy
    loc = LOCAL.get(site)
    if loc and os.path.exists(loc["path"]):
        Image.MAX_IMAGE_PIXELS = None
        mosaic = np.asarray(Image.open(loc["path"]).convert("L"), np.float32)
        print(f"[{site}] 로컬 CTX {mosaic.shape[1]}x{mosaic.shape[0]}")
        px = (LON - loc["lon0"]) * loc["ppd"] - 0.5
        py = (loc["lat0"] - LAT) * loc["ppd"] - 0.5
        return finish(site, map_coordinates(mosaic, [py, px], order=1, mode="constant", cval=0), mx, my, C, R, w, h, loc["source"])
    dpt = 180 / 2 ** Z
    x0, x1 = int((LON.min() + 180) // dpt), int((LON.max() + 180) // dpt)
    y0, y1 = int((90 - LAT.max()) // dpt), int((90 - LAT.min()) // dpt)
    print(f"[{site}] 타일 {(x1 - x0 + 1) * (y1 - y0 + 1)}장 (z={Z})")
    mosaic = np.vstack([np.hstack([tile(Z, y, x) for x in range(x0, x1 + 1)]) for y in range(y0, y1 + 1)])
    ppd = TILE / dpt
    px = (LON + 180 - x0 * dpt) * ppd - 0.5
    py = (90 - LAT - y0 * dpt) * ppd - 0.5
    g = map_coordinates(mosaic, [py, px], order=1, mode="nearest")
    return finish(site, g, mx, my, C, R, w, h, "CTX mosaic (MRO Context Camera, Caltech Murray Lab / Esri OnMars via JPL Mars Trek)")


def finish(site, g, mx, my, C, R, w, h, source):
    valid = g > 1
    lo, hi = np.percentile(g[valid], [0.5, 99.5]) if valid.any() else (0, 255)
    t = np.clip((g - lo) / max(1, hi - lo), 0, 1) ** 0.9
    pos = t * (len(TINT) - 1)
    i0 = np.clip(pos.astype(int), 0, len(TINT) - 2)
    f = (pos - i0)[..., None]
    rgb = TINT[i0] * (1 - f) + TINT[i0 + 1] * f
    rgb[~valid] = 0
    out = "../outputs/demo/context"
    os.makedirs(out, exist_ok=True)
    Image.fromarray(rgb.astype(np.uint8)).save(f"{out}/{site}.jpg", quality=78, optimize=True, progressive=True)
    json.dump({"x": -mx, "y": -my, "w": C + 2 * mx, "h": R + 2 * my,
               "source": source},
              open(f"{out}/{site}.json", "w"))
    print(f"  saved {w}x{h} px, {os.path.getsize(f'{out}/{site}.jpg') / 1e6:.2f} MB")


def register(site, search=25):
    """CTX(무기준 모자이크)와 HiRISE 바탕 사진의 어긋남을 상관계수 최대 이동으로 맞춰 json의 x, y에 반영."""
    base = "../outputs/demo/basemap.jpg" if site == "gale" else f"../outputs/demo/sites/{site}/basemap.jpg"
    jp = f"../outputs/demo/context/{site}.json"
    j = json.load(open(jp)); ctx = np.asarray(Image.open(f"../outputs/demo/context/{site}.jpg").convert("L"), float)
    s = ctx.shape[1] / j["w"]; y0, x0 = int(-j["y"] * s), int(-j["x"] * s)
    w, h = int(round((j["w"] + 2 * j["x"]) * s)), int(round((j["h"] + 2 * j["y"]) * s))
    b = np.asarray(Image.open(base).convert("L").resize((w, h)), float); m = b > 5
    best = (-2, 0, 0)
    for dy in range(-search, search + 1):
        for dx in range(-search, search + 1):
            a = ctx[y0 - dy:y0 - dy + h, x0 - dx:x0 - dx + w]; mm = m & (a > 5)
            u, v = a[mm] - a[mm].mean(), b[mm] - b[mm].mean()
            c = (u * v).sum() / np.sqrt((u * u).sum() * (v * v).sum())
            if c > best[0]: best = (c, dy, dx)
    c, dy, dx = best
    j["x"] += dx / s; j["y"] += dy / s; j["registered_shift_cells"] = [dx / s, dy / s]; j["registered_corr"] = round(float(c), 3)
    json.dump(j, open(jp, "w"))
    print(f"  {site}: 정합 이동 {dx / s:+.0f}, {dy / s:+.0f} 칸 (상관 {c:.3f})")


if __name__ == "__main__":
    for s in (sys.argv[1:] or ["gale", "jezero", "aram"]):
        build(s)
        register(s)
