"""
로버 1인칭 사진(챌린지 공식 자료 "Mars Perseverance Raw Images Gallery"와 같은 원본 사진 API)을 지도 위 지점에 붙인다.
"도착하면 무엇이 보이는가"를 미리 보여 주기 위한 것 (챌린지: point-of-view images).

    python build_rover_photos.py            # gale, jezero
    -> ../outputs/demo/photos/<site>/photos.json + 사진(400 px JPEG)
       jezero는 Perseverance 주행 경로도 ../outputs/demo/sites/jezero/meta.json 에 넣는다

- 웨이포인트: Curiosity = MMGIS MSL_waypoints.json(이미 있음), Perseverance = MMGIS M20_waypoints.json / M20_traverse.json
- 사진: 그 sol에 찍은 왼쪽 Navcam 전체 화면 사진 중 수평선에 가장 가깝게 본 것 (Perseverance는 mastEl, Curiosity는 카메라 벡터로 판단)
- 지점은 서로 MIN_SPACING_M 이상 떨어지게, 지역당 MAX_PHOTOS개까지
- 출처 표기: NASA/JPL-Caltech (원본 사진, 공개 자료)
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
import urllib.request

import numpy as np
from PIL import Image

MIN_SPACING_M = 400
MAX_PHOTOS = 24
WIDTH = 400
UA = {"User-Agent": "Mozilla/5.0"}
M20_WP = "https://mars.nasa.gov/mmgis-maps/M20/Layers/json/M20_waypoints.json"
M20_TR = "https://mars.nasa.gov/mmgis-maps/M20/Layers/json/M20_traverse.json"


def get_json(url):
    for k in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return json.load(r)
        except Exception:
            time.sleep(2 * (k + 1))
    raise RuntimeError(url)


def get_bytes(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def cached(url, path):
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "wb").write(get_bytes(url))
    return json.load(open(path))


def pick_points(xy_sol, cell, rows, cols):
    pts = []
    for x, y, sol in sorted(xy_sol, key=lambda t: t[2]):
        if not (0 <= x < cols and 0 <= y < rows):
            continue
        if all(np.hypot(x - px, y - py) * cell >= MIN_SPACING_M for px, py, _ in pts):
            pts.append((x, y, sol))
    if len(pts) > MAX_PHOTOS:                          # 경로 전체에 고르게
        idx = np.linspace(0, len(pts) - 1, MAX_PHOTOS).round().astype(int)
        pts = [pts[i] for i in idx]
    return pts


def m20_image(sol):
    d = get_json(f"https://mars.nasa.gov/rss/api/?feed=raw_images&category=mars2020&feedtype=json&sol={sol}")
    cands = []
    for it in d.get("images", []):
        url = it["image_files"].get("medium") or it["image_files"]["full_res"]
        if it["camera"]["instrument"] != "NAVCAM_LEFT" or it["extended"].get("dimension") not in ("(1280,960)", "(5120,3840)") \
                or "SAPP" in url.split("/")[-1]:      # SAPP = 태양·하늘 관측
            continue
        try:
            el = float(it["extended"]["mastEl"])
        except (KeyError, ValueError):
            continue
        cands.append((abs(el + 8), {"url": url, "date": it["date_taken_utc"][:10], "camera": "Navcam (왼쪽)", "credit": "NASA/JPL-Caltech"}))
    return [c for _, c in sorted(cands, key=lambda t: t[0])][:6]


def msl_image(sol):
    for inst in ("NAV_LEFT_B", "NAV_LEFT_A"):
        d = get_json("https://mars.nasa.gov/api/v1/raw_image_items/?order=sol%20desc&per_page=100&page=0"
                     f"&condition_1=msl:mission&condition_2={sol}:sol:gte&condition_3={sol}:sol:lte&condition_4={inst}:instrument")
        cands = []
        for it in d.get("items", []):
            if it.get("subframe_rect") not in ("(1,1,1024,1024)",):
                continue
            try:
                v = [float(t) for t in it["camera_vector"].strip("()").split(",")]
            except Exception:
                continue
            cands.append((abs(v[2] - 0.15), {"url": it["https_url"], "date": (it.get("date_taken") or "")[:10],
                                             "camera": "Navcam (왼쪽)", "credit": "NASA/JPL-Caltech"}))
        if cands:
            return [c for _, c in sorted(cands, key=lambda t: t[0])][:6]
    return []


def build(site):
    out = f"../outputs/demo/photos/{site}"
    os.makedirs(out, exist_ok=True)
    if site == "gale":
        from mars_walkback import lonlat_to_cell, CELL_M
        meta = json.load(open("../outputs/demo/demo_meta.json"))
        wps = [f["properties"] for f in json.load(open("../data/msl_traverse/MSL_waypoints.json"))["features"]]
        xs, ys = lonlat_to_cell(np.array([w["lon"] for w in wps]), np.array([w["lat"] for w in wps]))
        xy_sol = [(float(x), float(y), int(w["sol"])) for x, y, w in zip(xs, ys, wps)]
        cell, getimg, rover = CELL_M, msl_image, "Curiosity"
    else:
        import build_site_data as B
        from sites import SITES
        S = SITES[site]
        meta = json.load(open(f"../outputs/demo/sites/{site}/meta.json"))
        lab = B.read_label(S["dtm"])
        wj = cached(M20_WP, "../data/m20_traverse/M20_waypoints.json")
        tj = cached(M20_TR, "../data/m20_traverse/M20_traverse.json")
        l0, s0 = S["crop_lines"][0], S["crop_samples"][0]
        to_cell = lambda lon, lat: ((B.lonlat_to_px(lab, lon, lat)[1] - s0) / B.BLOCK, (B.lonlat_to_px(lab, lon, lat)[0] - l0) / B.BLOCK)
        wps = [f["properties"] for f in wj["features"]]
        xy_sol = [(*to_cell(w["lon"], w["lat"]), int(w["sol"])) for w in wps]
        cell, getimg, rover = meta["cell_m"], m20_image, "Perseverance"
        segs = []                                      # 주행 경로를 이 지도 칸 좌표로
        for f in tj["features"]:
            g = f["geometry"]
            for seg in (g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]):
                a = np.array(seg)[:, :2]
                x, y = to_cell(a[:, 0], a[:, 1])
                ok = (x >= 0) & (y >= 0) & (x < meta["cols"]) & (y < meta["rows"])
                if ok.sum() > 1:
                    segs.append([[round(float(px), 1), round(float(py), 1)] for px, py in zip(x[ok], y[ok])][::3])
        meta["traverse"] = segs
        json.dump(meta, open(f"../outputs/demo/sites/{site}/meta.json", "w"), ensure_ascii=False)
        print(f"  {rover} 주행 경로 {len(segs)}구간을 지도에 넣음")
    pts = pick_points(xy_sol, cell, meta["rows"], meta["cols"])
    print(f"[{site}] 지도 안 웨이포인트 {sum(0 <= x < meta['cols'] and 0 <= y < meta['rows'] for x, y, _ in xy_sol)}개 중 {len(pts)}곳")
    photos = []
    for x, y, sol in pts:
        try:
            im = info = None
            for c in (getimg(sol) + getimg(sol + 1)):     # 지형이 보이는 첫 사진 (하늘·태양·너무 어두운 사진 거름)
                cand = Image.open(io.BytesIO(get_bytes(c["url"]))).convert("RGB")
                g = np.asarray(cand.convert("L"), float)
                low = g[g.shape[0] // 2:]
                tex = np.abs(np.diff(low, axis=1)).mean()
                if 40 < low.mean() < 215 and tex > 3.0:
                    im, info = cand, c; break
            if im is None:
                print(f"  sol {sol}: 쓸 만한 사진 없음"); continue
            im = im.resize((WIDTH, round(im.size[1] * WIDTH / im.size[0])), Image.LANCZOS)
            fn = f"sol{sol:04d}.jpg"
            im.save(f"{out}/{fn}", quality=72, optimize=True, progressive=True)
            photos.append({"x": round(x, 1), "y": round(y, 1), "sol": sol, "rover": rover, "file": fn, **info})
            print(f"  sol {sol}: {info['url'].split('/')[-1][:40]} ({os.path.getsize(out + '/' + fn) // 1024} KB)")
        except Exception as e:
            print(f"  sol {sol}: 실패 {type(e).__name__}: {e}")
    json.dump(photos, open(f"{out}/photos.json", "w"), ensure_ascii=False, indent=1)
    print(f"[{site}] 사진 {len(photos)}장, {sum(os.path.getsize(out + '/' + p['file']) for p in photos) / 1e6:.2f} MB")


if __name__ == "__main__":
    for s in (sys.argv[1:] or ["gale", "jezero"]):
        build(s)
