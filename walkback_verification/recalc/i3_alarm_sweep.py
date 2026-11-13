"""계획 I3: 귀환 경보 규칙의 예비분 침범 스윕 (분석만, 데모 기본 동작 불변)

실행: cd code && env -u PYTHONPATH ../recalc/.venv/bin/python ../recalc/i3_alarm_sweep.py
- 목적지: 거점에서 직선 3~6.5 km인 Curiosity 웨이포인트 칸 중 15곳(균등 추출)
- 시나리오 surge/high/fatigue/model × k 근거 심박/압력 × 누설 0/10 g/h × 미리 보기 N = 1/2/3/5분, 산소 450 g
- 같은 조건에서 경보를 끈 경우도 돌려 "경보 없이도 다녀올 수 있었는가"를 본다(과잉 경보 판단).
- 빌드된 데모를 recalc/h1_demo_harness.mjs로 그대로 실행한다.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from collections import defaultdict

sys.path.insert(0, os.getcwd())
import mars_walkback as mw  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.getcwd(), ".."))
OUT = os.path.join(ROOT, "recalc", "outputs_i")
SCEN = ["surge", "high", "fatigue", "model"]
SRC = ["hr", "press"]
LEAK = [0, 10]
LOOK = [1, 2, 3, 5]
N_DEST = 15


def destinations() -> list[tuple[int, float, int]]:
    meta = json.load(open(os.path.join(ROOT, "outputs", "demo", "demo_meta.json")))
    W, R = meta["cols"], meta["rows"]
    bx, by = meta["base"]
    wps = [f["properties"] for f in json.load(open(mw.WAYPOINTS_PATH))["features"]]
    seen, c = set(), []
    for p in wps:
        x, y = (int(round(float(v))) for v in mw.lonlat_to_cell(p["lon"], p["lat"]))
        if not (0 <= x < W and 0 <= y < R) or (x, y) in seen:
            continue
        d = math.hypot(x - bx, y - by) * meta["cell_m"] / 1000
        if 3.0 <= d <= 6.5:
            seen.add((x, y)); c.append((p["sol"], round(d, 2), y * W + x))
    idx = [round(i * (len(c) - 1) / (N_DEST - 1)) for i in range(N_DEST)]
    return [c[i] for i in idx]


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    dests = destinations()
    jobs = []
    for sol, d, cell in dests:
        for sc in SCEN:
            for src in SRC:
                for lk in LEAK:
                    base = {"simTarget": cell, "simScenario": sc, "simSrc": src, "simLeak": lk, "simLeakSub": False,
                            "simPNoise": 10, "simTcomp": True, "o2": 450, "water": 3.6}
                    jobs.append({"name": f"{sol}|{d}|{sc}|{src}|{lk}|off", "preset": "simhr", "set": {**base, "simAuto": False}})
                    for n in LOOK:
                        jobs.append({"name": f"{sol}|{d}|{sc}|{src}|{lk}|{n}", "preset": "simhr",
                                     "set": {**base, "simAuto": True, "simLookMin": n}})
    jp, op = os.path.join(OUT, "i3_jobs.json"), os.path.join(OUT, "i3_raw.json")
    json.dump(jobs, open(jp, "w"))
    r = subprocess.run(["node", os.path.join(ROOT, "recalc", "h1_demo_harness.mjs"),
                        os.path.join(ROOT, "demo", "gale-eva-walkback-demo.html"), jp, op], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-3000:])
    raw = json.load(open(op))
    reserve = 45.0
    rows = {}
    for x in raw:
        s = x["sim"]
        if not s.get("ok"):
            continue
        last = s["last"]
        rows[x["name"]] = {"turn": s["turnMin"], "phase": last["phase"], "o2_true": last["o2True"], "end_min": s["minutes"]}
    agg = defaultdict(lambda: {"n": 0, "turned": 0, "home": 0, "dead": 0, "reserve_breach": 0, "breach_g": [],
                               "over_alarm": 0, "off_would_fail": 0})
    for name, v in rows.items():
        sol, d, sc, src, lk, n = name.split("|")
        if n == "off":
            continue
        off = rows.get(f"{sol}|{d}|{sc}|{src}|{lk}|off")
        for key in (f"N{n}", f"N{n}|{src}", f"N{n}|{src}|leak{lk}"):
            a = agg[key]
            a["n"] += 1
            a["turned"] += v["turn"] >= 0
            a["home"] += v["phase"] == "home"
            a["dead"] += v["phase"] == "dead"
            if v["phase"] == "home" and v["o2_true"] < reserve - 1e-6:
                a["reserve_breach"] += 1; a["breach_g"].append(round(reserve - v["o2_true"], 1))
            off_ok = off is not None and off["phase"] == "home" and off["o2_true"] >= reserve
            a["off_would_fail"] += off is not None and not off_ok
            if v["turn"] >= 0 and off_ok:
                a["over_alarm"] += 1
    summary = {}
    for k, a in sorted(agg.items()):
        b = sorted(a.pop("breach_g"))
        summary[k] = {**a, "breach_max_g": max(b) if b else 0.0, "breach_median_g": b[len(b) // 2] if b else 0.0}
    res = {"destinations": [{"sol": s, "dist_km": d, "cell": c} for s, d, c in dests], "reserve_g": reserve,
           "n_runs": len(raw), "summary": summary, "runs": rows}
    json.dump(res, open(os.path.join(OUT, "i3_alarm_sweep.json"), "w"), ensure_ascii=False, indent=1)
    for k in sorted(summary):
        if k.count("|") <= 1:
            print(k, summary[k], flush=True)


if __name__ == "__main__":
    main()
