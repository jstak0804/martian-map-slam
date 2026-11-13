"""
JPL Mars Trek(챌린지 공식 자료) 타일 서비스에서 THEMIS 야간 적외선 모자이크(100 m)를 받아 데모 지역 격자에 맞춘다.

    python build_trek_layers.py            # gale, jezero, aram
    -> ../outputs/demo/trek/<site>/themis_night.npy (uint8, 데모 격자), themis_night_check.png (정렬 확인)

왜: 챌린지는 "세 종류 이상 자료"(광학·열·분광·지형·대기·방사선 …)를 겹치라고 한다. 지금까지 광학(HiRISE)·
지형(DTM)·방사선(RAD)이었고, 이것이 열(thermal) 자료다. 밤에 밝은 곳 = 열을 오래 품는 곳(암반·굳은 지반,
열관성 높음), 어두운 곳 = 먼지·고운 모래(열관성 낮음). 정량 열관성이 아니라 상대 지표다(Trek 표시용 8비트 모자이크).

타일: https://trek.nasa.gov/tiles/Mars/EQ/<layer>/1.0.0/default/default028mm/{z}/{row}/{col}.png
      등장방형, 256 px, z 단계에서 타일 한 장 = 180/2^z 도 (z=9: 0.35°, 화소 약 81 m)
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

LAYER = "THEMIS_NightIR_ControlledMosaics_100m_v2_oct2018"
URL = "https://trek.nasa.gov/tiles/Mars/EQ/{L}/1.0.0/default/default028mm/{z}/{y}/{x}.png"
Z = 9
TILE = 256
CACHE = "../data/trek_tiles"


def cell_lonlat(site):
    """데모 격자 칸 중심의 (경도, 위도) 배열과 메타."""
    if site == "gale":
        import mars_walkback as M
        meta = json.load(open("../outputs/demo/demo_meta.json"))
        R, C = meta["rows"], meta["cols"]
        yy, xx = np.mgrid[0:R, 0:C] + 0.5
        lon = M.DTM_WEST_LON + (xx * M.BLOCK + M.CROP_SAMPLES[0]) * M.DEG_PER_PX
        lat = M.DTM_MAX_LAT - (yy * M.BLOCK + M.CROP_LINES[0]) * M.DEG_PER_PX
        return lon, lat, meta
    import build_site_data as B
    from sites import SITES
    S = SITES[site]
    meta = json.load(open(f"../outputs/demo/sites/{site}/meta.json"))
    lab = B.read_label(S["dtm"])
    R, C = meta["rows"], meta["cols"]
    yy, xx = np.mgrid[0:R, 0:C] + 0.5
    line = S["crop_lines"][0] + yy * B.BLOCK
    sample = S["crop_samples"][0] + xx * B.BLOCK
    Rm = lab["A_AXIS_RADIUS"] * 1000
    lat = np.degrees((lab["LINE_PROJECTION_OFFSET"] - line) * lab["MAP_SCALE"] / Rm)
    lon = lab["CENTER_LONGITUDE"] + np.degrees((sample - lab["SAMPLE_PROJECTION_OFFSET"]) * lab["MAP_SCALE"] / (Rm * np.cos(np.radians(lab["CENTER_LATITUDE"]))))
    return lon, lat, meta


def tile(z, y, x):
    p = f"{CACHE}/{LAYER}/{z}/{y}/{x}.png"
    if not os.path.exists(p):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        req = urllib.request.Request(URL.format(L=LAYER, z=z, y=y, x=x), headers={"User-Agent": "Mozilla/5.0"})
        open(p, "wb").write(urllib.request.urlopen(req, timeout=60).read())
    return np.asarray(Image.open(p).convert("L"), np.float32)


def build(site):
    lon, lat, meta = cell_lonlat(site)
    lon = np.where(lon > 180, lon - 360, lon)
    dpt = 180 / 2 ** Z
    x0, x1 = int((lon.min() + 180) // dpt), int((lon.max() + 180) // dpt)
    y0, y1 = int((90 - lat.max()) // dpt), int((90 - lat.min()) // dpt)
    mosaic = np.vstack([np.hstack([tile(Z, y, x) for x in range(x0, x1 + 1)]) for y in range(y0, y1 + 1)])
    ppd = TILE / dpt                                       # 도당 화소
    px = (lon + 180 - x0 * dpt) * ppd - 0.5
    py = (90 - lat - y0 * dpt) * ppd - 0.5
    v = map_coordinates(mosaic, [py, px], order=1, mode="nearest")
    out = f"../outputs/demo/trek/{site}"
    os.makedirs(out, exist_ok=True)
    np.save(f"{out}/themis_night.npy", np.clip(v, 0, 255).astype(np.uint8))
    # 정렬 확인: 바탕 사진 옆에 나란히
    base_p = "../outputs/demo/basemap.jpg" if site == "gale" else f"../outputs/demo/sites/{site}/basemap.jpg"
    bm = Image.open(base_p).convert("L").resize((meta["cols"], meta["rows"]))
    tv = Image.fromarray(np.clip((v - np.percentile(v, 2)) / (np.percentile(v, 98) - np.percentile(v, 2) + 1e-6) * 255, 0, 255).astype(np.uint8))
    canvas = Image.new("L", (meta["cols"] * 2 + 10, meta["rows"]), 0)
    canvas.paste(bm, (0, 0)); canvas.paste(tv, (meta["cols"] + 10, 0))
    canvas.save(f"{out}/themis_night_check.png")
    print(f"[{site}] 타일 {(x1 - x0 + 1) * (y1 - y0 + 1)}장 (z={Z}, 화소 약 {dpt / TILE * 59274:.0f} m), 값 범위 {v.min():.0f}~{v.max():.0f}")


if __name__ == "__main__":
    for s in (sys.argv[1:] or ["gale", "jezero", "aram"]):
        build(s)
