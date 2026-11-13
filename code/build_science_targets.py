"""
지역별 과학 목표 지점(EVA로 들를 곳)을 실제 자료에서 뽑는다. 좌표를 손으로 지어내지 않는다.

    python build_science_targets.py          # gale, jezero, aram
    -> ../outputs/demo/targets/<site>.json   [{x, y, name, why, source, sols?}]

- Gale, Jezero: 로버가 오래 머문 곳 = 드릴·근접 분석 같은 과학 작업을 한 곳.
  웨이포인트를 sol 순서로 보며 반경 CLUSTER_M 안에 머문 구간을 묶고, DWELL_SOLS 이상 머문 곳을 고른다.
  Gale은 sol이 확실한 Curiosity 드릴 지점 이름을 붙인다(아래 MSL_DRILLS: NASA 발표 sol).
- Aram Chaos: 로버 자료가 없어 Mars Trek THEMIS 야간 적외선(열관성 상대값) 상위 덩어리 = 노출 암반 후보.
  문헌상 Aram Chaos의 밝은 층에서 적철석·함수 황산염이 보고되었다(Glotch & Christensen 2005 등, 확인 필요).
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
from scipy.ndimage import label, uniform_filter

CLUSTER_M = 60
DWELL_SOLS = 15
MIN_APART_M = 350
MAX_TARGETS = 7
MSL_DRILLS = {182: "John Klein 드릴 지점", 279: "Cumberland 드릴 지점", 621: "Windjana 드릴 지점",
              759: "Confidence Hills 드릴 지점", 882: "Mojave 드릴 지점", 908: "Telegraph Peak 드릴 지점",
              1060: "Buckskin 드릴 지점", 1119: "Big Sky 드릴 지점", 1137: "Greenhorn 드릴 지점"}


# NASA Mars 2020 시료 목록 (https://science.nasa.gov/mission/mars-2020-perseverance/mars-rock-samples/, 2026-06-20 기준 페이지)
# (번호, 시료 이름, 암석·노두, 채취 구역, 밀봉 sol). 페이지에는 채취 sol이 아니라 밀봉 sol만 있어 그 값을 쓴다.
M20_SAMPLES = [(1, "Roubion", "Roubion", "Polygon Valley", 164), (2, "Montdenier", "Rochette", "Artuby Ridge", 194),
               (3, "Montagnac", "Rochette", "Artuby Ridge", 196), (4, "Salette", "Brac", "South Séítah", 262),
               (5, "Coulettes", "Brac", "South Séítah", 271), (6, "Robine", "Issole", "South Séítah", 298),
               (7, "Malay", "Issole", "South Séítah", 337), (8, "Ha'ahóni", "Sid", "Ch'ał outcrop", 371),
               (9, "Atsá", "Sid", "Ch'ał outcrop", 377), (10, "Swift Run", "Skinner Ridge", "Delta Front", 490),
               (11, "Skyland", "Skinner Ridge", "Delta Front", 495), (12, "Hazeltop", "Wildcat Ridge", "Delta Front", 509),
               (13, "Bearwallow", "Wildcat Ridge", "Delta Front", 516), (14, "Shuyak", "Amalik", "Delta Front", 575),
               (15, "Mageik", "Amalik", "Delta Front", 619), (16, "Kukaklek", "Hidden Harbor", "Delta Front", 631),
               (17, "Atmo Mountain", "Observation Mountain", "Delta Front", 634), (18, "Crosswind Lake", "Observation Mountain", "Delta Front", 639)]


def dwell_clusters(xy_sol, cell, rows, cols, base=None):
    pts = sorted(xy_sol, key=lambda t: t[2])
    clusters, cur = [], []
    for p in pts:
        if cur and np.hypot(p[0] - np.mean([c[0] for c in cur]), p[1] - np.mean([c[1] for c in cur])) * cell > CLUSTER_M:
            clusters.append(cur); cur = []
        cur.append(p)
    if cur:
        clusters.append(cur)
    out = []
    for c in clusters:
        x, y = float(np.mean([p[0] for p in c])), float(np.mean([p[1] for p in c]))
        s0, s1 = c[0][2], c[-1][2]
        near_base = base is not None and np.hypot(x - base[0], y - base[1]) * cell < 300   # 거점 자체는 목표가 아님
        if s1 - s0 >= DWELL_SOLS and 0 <= x < cols and 0 <= y < rows and not near_base:
            out.append({"x": round(x, 1), "y": round(y, 1), "sols": [int(s0), int(s1)]})
    out.sort(key=lambda t: -(t["sols"][1] - t["sols"][0]))
    keep = []
    for t in out:
        if all(np.hypot(t["x"] - k["x"], t["y"] - k["y"]) * cell >= MIN_APART_M for k in keep):
            keep.append(t)
    return keep[:MAX_TARGETS]


def gale():
    from mars_walkback import lonlat_to_cell, CELL_M
    meta = json.load(open("../outputs/demo/demo_meta.json"))
    wps = [f["properties"] for f in json.load(open("../data/msl_traverse/MSL_waypoints.json"))["features"]]
    xs, ys = lonlat_to_cell(np.array([w["lon"] for w in wps]), np.array([w["lat"] for w in wps]))
    T = dwell_clusters([(float(x), float(y), int(w["sol"])) for x, y, w in zip(xs, ys, wps)], CELL_M, meta["rows"], meta["cols"], meta["base"])
    for t in T:
        drill = [(s, n) for s, n in MSL_DRILLS.items() if t["sols"][0] - 2 <= s <= t["sols"][1] + 2]
        t["name"] = " · ".join(n.replace(" 드릴 지점", "") for _, n in drill) + " 드릴 지점" if drill else f"Curiosity 탐사 정지 지점 (sol {t['sols'][0]}–{t['sols'][1]})"
        t["why"] = (f"Curiosity가 sol {t['sols'][0]}–{t['sols'][1]} 동안 머물며 조사한 곳" + (", 드릴 시료 채취 sol " + ", ".join(str(s_) for s_, _ in drill) if drill else ""))
        t["source"] = "NASA MMGIS MSL_waypoints (머문 기간으로 선정)" + (", 드릴 sol: NASA 발표" if drill else "")
    return T


def jezero():
    import build_site_data as B
    from sites import SITES
    S = SITES["jezero"]
    meta = json.load(open("../outputs/demo/sites/jezero/meta.json"))
    lab = B.read_label(S["dtm"])
    wps = [f["properties"] for f in json.load(open("../data/m20_traverse/M20_waypoints.json"))["features"]]
    l0, s0 = S["crop_lines"][0], S["crop_samples"][0]
    xy = []
    for w in wps:
        li, sa = B.lonlat_to_px(lab, w["lon"], w["lat"])
        xy.append(((sa - s0) / B.BLOCK, (li - l0) / B.BLOCK, int(w["sol"])))
    T = dwell_clusters(xy, meta["cell_m"], meta["rows"], meta["cols"], meta["base"])
    for t in T:
        smp = [x for x in M20_SAMPLES if t["sols"][0] - 3 <= x[4] <= t["sols"][1] + 3]
        if smp:
            feats = list(dict.fromkeys(x[2] for x in smp))
            t["name"] = f"{' · '.join(feats)} 시료 채취 지점"
            t["why"] = (f"Perseverance가 sol {t['sols'][0]}–{t['sols'][1]} 동안 머문 곳. 이 기간 밀봉한 시료: "
                        + ", ".join(f"#{x[0]} {x[1]} (sol {x[4]})" for x in smp) + f" · {smp[0][3]}")
            t["samples"] = [{"no": x[0], "name": x[1], "feature": x[2], "area": x[3], "sol_sealed": x[4]} for x in smp]
            t["source"] = "NASA MMGIS M20_waypoints (머문 기간) + NASA Mars 2020 시료 목록 (밀봉 sol로 대조)"
        else:
            t["name"] = f"Perseverance 탐사 정지 지점 (sol {t['sols'][0]}–{t['sols'][1]})"
            t["why"] = f"Perseverance가 sol {t['sols'][0]}–{t['sols'][1]} 동안 머물며 조사한 곳"
            t["source"] = "NASA MMGIS M20_waypoints (머문 기간으로 선정)"
    return T


def aram():
    meta = json.load(open("../outputs/demo/sites/aram/meta.json"))
    import gzip
    raw = gzip.decompress(open("../outputs/demo/sites/aram/data.bin.gz", "rb").read())
    v = lambda n: np.frombuffer(raw[meta["layout"][n][0]: meta["layout"][n][0] + meta["layout"][n][1]], np.uint8).reshape(meta["rows"], meta["cols"])
    fl = v("flags"); valid = (fl & 1) > 0; passable = (fl & 8) > 0
    tir = np.load("../outputs/demo/trek/aram/themis_night.npy").astype(float)
    sm = uniform_filter(np.where(valid, tir, np.nan if False else 0), 9)
    thr = np.percentile(sm[valid], 92)
    lab, n = label((sm >= thr) & valid)
    cand = []
    for k in range(1, n + 1):
        ys, xs = np.nonzero((lab == k) & passable)
        if len(ys) < 40:
            continue
        j = np.argmax(sm[ys, xs])
        cand.append((len(ys), xs[j], ys[j], sm[ys[j], xs[j]]))
    cand.sort(key=lambda c: -c[0])
    keep = []
    for sz, x, y, val in cand:
        if all(np.hypot(x - k["x"], y - k["y"]) * meta["cell_m"] >= MIN_APART_M for k in keep):
            keep.append({"x": float(x) + 0.5, "y": float(y) + 0.5, "name": f"열관성 높은 노출 암반 후보 {len(keep) + 1}",
                         "why": "THEMIS 야간 적외선 상위 8% 덩어리(굳은 암반). Aram Chaos 밝은 층은 적철석·함수 황산염 보고 지역(확인 필요)",
                         "source": "JPL Mars Trek THEMIS 야간 적외선 (자동 선정)"})
        if len(keep) >= 6:
            break
    return keep


def snap(T, site):
    """목표 칸을 거점과 이어진 걸을 수 있는 칸으로 옮긴다(SNAP_M 안). 못 옮기면 그대로 두고 표시."""
    import gzip
    if site == "gale":
        meta = json.load(open("../outputs/demo/demo_meta.json")); raw = gzip.decompress(open("../outputs/demo/demo_data.bin.gz", "rb").read())
    else:
        meta = json.load(open(f"../outputs/demo/sites/{site}/meta.json")); raw = gzip.decompress(open(f"../outputs/demo/sites/{site}/data.bin.gz", "rb").read())
    off, ln, _ = meta["layout"]["flags"]
    fl = np.frombuffer(raw[off:off + ln], np.uint8).reshape(meta["rows"], meta["cols"])
    lab, _ = label((fl & 8) > 0, structure=np.ones((3, 3)))
    bx, by = meta["base"]
    ok = lab == lab[by, bx]
    yy, xx = np.nonzero(ok)
    for t in T:
        d = np.hypot(xx + 0.5 - t["x"], yy + 0.5 - t["y"]) * meta["cell_m"]
        j = np.argmin(d)
        if d[j] <= SNAP_M:
            t["x"], t["y"] = float(xx[j]) + 0.5, float(yy[j]) + 0.5
            if d[j] > 5:
                t["snapped_m"] = round(float(d[j]))
        else:
            t["unreachable"] = True
    gone = [t["name"] for t in T if t.get("unreachable")]
    if gone:
        print(f"  지형 자료 밖이거나 거점과 이어지지 않아 뺀 목표: {', '.join(gone)}")
    return [t for t in T if not t.get("unreachable")]


SNAP_M = 60

if __name__ == "__main__":
    os.makedirs("../outputs/demo/targets", exist_ok=True)
    for s in (sys.argv[1:] or ["gale", "jezero", "aram"]):
        T = snap({"gale": gale, "jezero": jezero, "aram": aram}[s](), s)
        json.dump(T, open(f"../outputs/demo/targets/{s}.json", "w"), ensure_ascii=False, indent=1)
        print(f"[{s}] 과학 목표 {len(T)}곳")
        for t in T:
            print("   ", t["name"], "|", (t["x"], t["y"]), "옮김 %s m" % t["snapped_m"] if "snapped_m" in t else "", "도달 불가" if t.get("unreachable") else "")
