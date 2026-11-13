"""
demo_template.html + 지형 자료 -> 파일 하나짜리 데모 reports/18-eva-walkback-demo.html

- Gale: build_demo_data.py + build_demo_basemap.py 출력 (outputs/demo/)
- 그 밖의 지역: build_site_data.py 출력 (outputs/demo/sites/<id>/), sites.DEMO_SITES 순서

실행: python build_demo_data.py && python build_demo_basemap.py && python build_site_data.py && python build_demo_html.py
"""
import base64
import gzip
import json
import os

import numpy as np

from sites import GALE, DEMO_SITES

OUT = "../reports/18-eva-walkback-demo.html"
b64 = lambda p: base64.b64encode(open(p, "rb").read()).decode()


def gale_site(meta):
    """Gale 자료에서 다른 지역과 같은 형식의 지역 정보·통계를 만든다."""
    raw = gzip.decompress(open("../outputs/demo/demo_data.bin.gz", "rb").read())
    view = lambda n, dt: np.frombuffer(raw[meta["layout"][n][0]: meta["layout"][n][0] + meta["layout"][n][1]], dt)
    fl, cls = view("flags", np.uint8), view("cls", np.uint8)
    hq, o2q = view("h", "<u2"), view("plain_o2", "<u2")
    valid = (fl & 1) > 0
    km2 = (meta["cell_m"] / 1000) ** 2
    budget = 150 - meta["const"]["o2_reserve_g"]
    reach = (o2q != meta["none16"]) & (o2q / meta["o2_scale"] <= budget)
    (bx, by), (rx, ry), (gx, gy) = meta["base"], meta["relay"], meta["goal"]
    stats = {"valid_km2": float(valid.sum() * km2), "relief_m": float((hq[valid].max() - hq[valid].min()) * meta["h_step"]),
             "impassable_pct": float(((fl & 8) == 0)[valid].mean() * 100), "fall_high_pct": float((cls == 2)[valid].mean() * 100),
             "baseline_km2": float((reach & valid).sum() * km2), "base_vis_km2": float(((fl & 2) > 0).sum() * km2),
             "dune_km2": float(((fl & 16) > 0).sum() * km2), "relay_km_from_base": float(np.hypot(rx - bx, ry - by) * meta["cell_m"] / 1000),
             "goal_km_from_base": float(np.hypot(gx - bx, gy - by) * meta["cell_m"] / 1000)}
    return {"id": "gale", "name": GALE["name"], "short": GALE["short"], "description": GALE["description"], "source": GALE["source"],
            "base_name": GALE["base_name"], "goal_name": GALE["goal_name"], "stats": stats}


def roadview(site):
    d = f"../outputs/demo/roadview/{site}"
    if not os.path.exists(f"{d}/roadview.json"):
        return []
    out = json.load(open(f"{d}/roadview.json", encoding="utf-8"))
    for st in out:
        for f in st["frames"]:
            fn = f.pop("file")
            if f["az"] is None:                   # 한 장짜리는 로버 사진(photos)과 같은 사진: sol로 다시 씀
                f["photo_sol"] = st["sol"]
            else:
                f["img"] = "data:image/jpeg;base64," + b64(f"{d}/{fn}")
    return out


def targets(site):
    p = f"../outputs/demo/targets/{site}.json"
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else []


def tir(site):
    """build_trek_layers.py 결과(THEMIS 야간 적외선, 데모 격자)를 8비트 PNG data URI로."""
    p = f"../outputs/demo/trek/{site}/themis_night.npy"
    if not os.path.exists(p):
        return None
    import io
    from PIL import Image
    buf = io.BytesIO(); Image.fromarray(np.load(p)).save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def photos(site):
    """build_rover_photos.py 결과를 data URI로 (없으면 빈 목록)."""
    d = f"../outputs/demo/photos/{site}"
    if not os.path.exists(f"{d}/photos.json"):
        return []
    out = []
    for p in json.load(open(f"{d}/photos.json", encoding="utf-8")):
        q = {k: p[k] for k in ("x", "y", "sol", "rover", "date", "camera", "credit", "url")}
        q["img"] = "data:image/jpeg;base64," + b64(f"{d}/{p['file']}")
        out.append(q)
    return out


def main():
    html = open("demo_template.html", encoding="utf-8").read()
    meta = json.load(open("../outputs/demo/demo_meta.json", encoding="utf-8"))
    meta["site"] = gale_site(meta)
    meta["photos"] = photos("gale")
    meta["tir"] = tir("gale")
    meta["targets"] = targets("gale")
    meta["roadview"] = roadview("gale")
    sites = []
    for sid in DEMO_SITES:
        d = f"../outputs/demo/sites/{sid}"
        if not os.path.exists(f"{d}/meta.json"):
            print(f"  {sid}: 자료 없음 (python build_site_data.py {sid}) -> 건너뜀"); continue
        sm = json.load(open(f"{d}/meta.json", encoding="utf-8"))
        sm["photos"] = photos(sid)
        sm["tir"] = tir(sid)
        sm["targets"] = targets(sid)
        sm["roadview"] = roadview(sid)
        sites.append({"meta": sm, "data": b64(f"{d}/data.bin.gz"),
                      "shade": "data:image/png;base64," + b64(f"{d}/hillshade.png"),
                      "ortho": "data:image/jpeg;base64," + b64(f"{d}/basemap.jpg")})
    rep = {"__META__": json.dumps(meta, ensure_ascii=False).replace("</", "<\\/"),
           "__DATA__": b64("../outputs/demo/demo_data.bin.gz"),
           "__SITES__": json.dumps(sites, ensure_ascii=False).replace("</", "<\\/"),
           "__SHADE__": "data:image/png;base64," + b64("../outputs/demo/hillshade.png"),
           "__ORTHO__": "data:image/jpeg;base64," + b64("../outputs/demo/basemap.jpg")}
    for key, val in rep.items():
        assert html.count(key) == 1, key
        html = html.replace(key, val)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"saved {OUT} ({len(html.encode()) / 1e6:.2f} MB), 지형 {1 + len(sites)}개: gale, {', '.join(s['meta']['site']['id'] for s in sites)}")
    print("  Gale 통계:", {k: round(v, 2) for k, v in meta["site"]["stats"].items()})


if __name__ == "__main__":
    main()
