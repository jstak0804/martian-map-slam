"""
로드뷰 자료: 로버가 멈춘 지점마다 여러 방향으로 찍은 Navcam 사진을 방위각 순서로 모은다.

    python build_roadview.py         # jezero (Perseverance), gale (Curiosity: 지점별 사진 한 장)
    -> ../outputs/demo/roadview/<site>.json + 사진(320 px)

- Perseverance: 공개 원본 사진 API(챌린지 Resources의 Raw Images Gallery와 같은 자료)에서 그 sol의 왼쪽 Navcam
  전체 화면 사진을 받아, 마스트 방위각(mastAz)을 60° 칸으로 나눠 칸마다 한 장(수평선 근처, 지형이 보이는 것).
  MMGIS의 360° 파노라마 모자이크는 서버가 외부 요청을 막아(403) 쓰지 않았다.
- 방위각은 사진 자료의 mastAz 값 그대로이며, 화면에는 "카메라 방위각(자료값)"으로만 표시한다.
- Curiosity: build_rover_photos.py의 지점별 사진을 그대로 쓴다(방향 자료 형식이 달라 여러 장 묶지 않음).
"""
from __future__ import annotations

import io
import json
import os
import sys

import numpy as np
from PIL import Image

from build_rover_photos import get_json, get_bytes

W_PX = 320
BIN_DEG = 60


def ok_texture(im):
    g = np.asarray(im.convert("L"), float)
    low = g[g.shape[0] // 3:] if g.shape[0] * 3 < g.shape[1] else g[g.shape[0] // 2:]
    return 40 < low.mean() < 215 and np.abs(np.diff(low, axis=1)).mean() > 3.0


def m20_frames(sol):
    d = get_json(f"https://mars.nasa.gov/rss/api/?feed=raw_images&category=mars2020&feedtype=json&sol={sol}")
    bins = {}
    for it in d.get("images", []):
        url = it["image_files"].get("medium") or it["image_files"].get("full_res")
        dim = it["extended"].get("dimension")
        if it["camera"]["instrument"] != "NAVCAM_LEFT" or "SAPP" in url.split("/")[-1] \
                or dim not in ("(1280,240)", "(1280,960)", "(5120,3840)"):
            continue
        try:
            az, el = float(it["extended"]["mastAz"]), float(it["extended"]["mastEl"])
        except (KeyError, ValueError):
            continue
        if not -20 <= el <= 5:
            continue
        b = int((az % 360) // BIN_DEG)
        strip = dim == "(1280,240)"                     # 수평선 360° 파노라마용 가로 띠 사진을 우선
        bins.setdefault(b, []).append((0 if strip else 1, abs(el + 5), az, el, url))
    out = []
    for b in sorted(bins):
        for _, _, az, el, url in sorted(bins[b])[:3]:            # 칸마다 후보 3장 중 지형이 보이는 첫 장
            try:
                im = Image.open(io.BytesIO(get_bytes(url))).convert("RGB")
            except Exception:
                continue
            if ok_texture(im):
                out.append((az, el, im)); break
    return sorted(out, key=lambda t: t[0])


def jezero_stops(max_stops=12, spacing_m=250):
    """웨이포인트를 훑어 360° 수평선 띠가 있는 날만 로드뷰 지점으로."""
    import build_site_data as B
    from sites import SITES
    S = SITES["jezero"]
    meta = json.load(open("../outputs/demo/sites/jezero/meta.json"))
    lab = B.read_label(S["dtm"])
    wps = [f["properties"] for f in json.load(open("../data/m20_traverse/M20_waypoints.json"))["features"]]
    cand = []
    for w in sorted(wps, key=lambda q: q["sol"]):
        li, sa = B.lonlat_to_px(lab, w["lon"], w["lat"])
        x, y = (sa - S["crop_samples"][0]) / B.BLOCK, (li - S["crop_lines"][0]) / B.BLOCK
        if 0 <= x < meta["cols"] and 0 <= y < meta["rows"] and all(np.hypot(x - c[0], y - c[1]) * meta["cell_m"] >= spacing_m for c in cand):
            cand.append((x, y, int(w["sol"])))
    print(f"  후보 웨이포인트 {len(cand)}곳")
    stops = []
    for x, y, sol in cand:
        for s_ in (sol, sol + 1):
            fr = [f for f in m20_frames(s_) if f[2].size[0] / f[2].size[1] > 3]
            if len(fr) >= 4:
                stops.append((x, y, s_, fr)); print(f"  sol {s_}: 띠 {len(fr)}장"); break
        if len(stops) >= max_stops:
            break
    return stops


def build(site):
    out_dir = f"../outputs/demo/roadview/{site}"
    os.makedirs(out_dir, exist_ok=True)
    P = json.load(open(f"../outputs/demo/photos/{site}/photos.json", encoding="utf-8"))
    stops = []
    if site == "jezero":
        for x, y, sol, fr in jezero_stops():
            frames = []
            for az, el, im in fr:
                im = im.resize((480, round(im.size[1] * 480 / im.size[0])), Image.LANCZOS)
                fn = f"sol{sol:04d}_az{int(az):03d}.jpg"
                im.save(f"{out_dir}/{fn}", quality=68, optimize=True, progressive=True)
                frames.append({"az": round(az, 1), "el": round(el, 1), "file": fn})
            stops.append({"x": round(x, 1), "y": round(y, 1), "sol": sol, "date": "", "rover": "Perseverance", "frames": frames})
        # 띠 사진 지점과 150 m 안에 겹치는 사진 지점은 빼고, 나머지 사진 지점은 한 장짜리로 합친다
        P = [p for p in P if all(np.hypot(p["x"] - q["x"], p["y"] - q["y"]) * 10.1 > 150 for q in stops)]
    for p in sorted(P, key=lambda q: q["sol"]):
        frames = []
        if False:
            for az, el, im in m20_frames(p["sol"]):
                w = 480 if im.size[0] / im.size[1] > 3 else W_PX      # 띠 사진은 가로 480 px
                im = im.resize((w, round(im.size[1] * w / im.size[0])), Image.LANCZOS)
                fn = f"sol{p['sol']:04d}_az{int(az):03d}.jpg"
                im.save(f"{out_dir}/{fn}", quality=68, optimize=True, progressive=True)
                frames.append({"az": round(az, 1), "el": round(el, 1), "file": fn})
        if not frames:                                          # 한 장짜리 (Gale, 또는 방향별 사진이 없을 때)
            im = Image.open(f"../outputs/demo/photos/{site}/{p['file']}")
            fn = f"sol{p['sol']:04d}_single.jpg"
            im.save(f"{out_dir}/{fn}", quality=72)
            frames.append({"az": None, "el": None, "file": fn})
        stops.append({"x": p["x"], "y": p["y"], "sol": p["sol"], "date": p["date"], "rover": p["rover"], "frames": frames})
        print(f"  sol {p['sol']}: 사진 {len(frames)}장" + (f" (방위각 {', '.join(str(int(f['az'])) for f in frames)})" if frames[0]["az"] is not None else ""))
    stops.sort(key=lambda q: q["sol"])
    json.dump(stops, open(f"{out_dir}/roadview.json", "w"), ensure_ascii=False, indent=1)
    size = sum(os.path.getsize(f"{out_dir}/{f['file']}") for s in stops for f in s["frames"])
    print(f"[{site}] 로드뷰 지점 {len(stops)}곳, 사진 {sum(len(s['frames']) for s in stops)}장, {size / 1e6:.2f} MB")


if __name__ == "__main__":
    for s in (sys.argv[1:] or ["jezero", "gale"]):
        build(s)
