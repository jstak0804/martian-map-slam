"""계획 J9: 경보 규칙 재검토 — 미리 보기 N분, k 여유 배수, k 추세 비교 (분석만, 데모 기본값 불변)

실행: cd code && env -u PYTHONPATH ../recalc/.venv/bin/python ../recalc/j9_alarm.py
- 목적지: 계획 I3의 15곳 + 거점에서 4.6~6.0 km 웨이포인트 10곳(450 g이 아슬아슬한 구간)
- 조건: 시나리오 surge/high/fatigue/model × 심박/압력 × 누설 0/10 g/h, 산소 450 g
- 규칙: 경보 없음, N = 1(현재)/2/3/5/7/10분, k 여유 1.1/1.2(N=1), k 추세(N=1)
- 판정(J5): ISS 비행 규칙은 에어록 진입 시점에 30분 예비분이 남아 있어야 한다 → 도착 산소 < 45 g이면 "예비분 침범"
- 비용 지표: 경보로 돌아선 경우, 돌아선 시각 ÷ (경보 없이 목적지에 도착한 시각) = 간 비율
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from collections import defaultdict

sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), "..", "recalc")))
import mars_walkback as mw  # noqa: E402
from i3_alarm_sweep import destinations  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.getcwd(), ".."))
OUT = os.path.join(ROOT, "recalc", "outputs_j")
RESERVE = 45.0
RULES = {"off": {"simAuto": False}, "N1": {"simLookMin": 1}, "N2": {"simLookMin": 2}, "N3": {"simLookMin": 3},
         "N5": {"simLookMin": 5}, "N7": {"simLookMin": 7}, "N10": {"simLookMin": 10},
         "M1.1": {"simKMargin": 1.1}, "M1.2": {"simKMargin": 1.2}, "trend": {"simKTrend": True}}
DEFAULTS = {"simAuto": True, "simLookMin": 1, "simKMargin": 1.0, "simKTrend": False}


def extra_destinations(have: set[int], n: int = 10) -> list[tuple[int, float, int]]:
    meta = json.load(open(os.path.join(ROOT, "outputs", "demo", "demo_meta.json")))
    W, R = meta["cols"], meta["rows"]; bx, by = meta["base"]
    wps = [f["properties"] for f in json.load(open(mw.WAYPOINTS_PATH))["features"]]
    seen, c = set(), []
    for p in wps:
        x, y = (int(round(float(v))) for v in mw.lonlat_to_cell(p["lon"], p["lat"]))
        if not (0 <= x < W and 0 <= y < R) or (x, y) in seen or y * W + x in have:
            continue
        d = math.hypot(x - bx, y - by) * meta["cell_m"] / 1000
        if 4.6 <= d <= 6.0:
            seen.add((x, y)); c.append((p["sol"], round(d, 2), y * W + x))
    idx = [round(i * (len(c) - 1) / (n - 1)) for i in range(n)]
    return [c[i] for i in idx]


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    d15 = destinations()
    dests = d15 + extra_destinations({c for _, _, c in d15})
    jobs = []
    for sol, d, cell in dests:
        for sc in ("surge", "high", "fatigue", "model"):
            for src in ("hr", "press"):
                for lk in (0, 10):
                    base = {"simTarget": cell, "simScenario": sc, "simSrc": src, "simLeak": lk, "simLeakSub": False,
                            "simPNoise": 10, "simTcomp": True, "o2": 450, "water": 3.6}
                    for rn, rs in RULES.items():
                        jobs.append({"name": f"{sol}|{d}|{sc}|{src}|{lk}|{rn}", "preset": "simhr",
                                     "set": {**base, **DEFAULTS, **rs}})
    jp, op = os.path.join(OUT, "j9_jobs.json"), os.path.join(OUT, "j9_raw.json")
    json.dump(jobs, open(jp, "w"))
    r = subprocess.run(["node", os.path.join(ROOT, "recalc", "h1_demo_harness.mjs"),
                        os.path.join(ROOT, "demo", "gale-eva-walkback-demo.html"), jp, op], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-3000:])
    runs = {}
    for x in json.load(open(op)):
        s = x["sim"]
        if not s.get("ok"):
            continue
        arrive = next((l["m"] for l in s["log"] if "목적지 도착" in l["text"]), None)
        runs[x["name"]] = {"turn": s["turnMin"], "phase": s["last"]["phase"], "o2": s["last"]["o2True"], "arrive_min": arrive}
    agg = defaultdict(lambda: {"n": 0, "breach": 0, "dead": 0, "over_alarm": 0, "turned": 0, "frac": [], "breach_g": []})
    for name, v in runs.items():
        sol, d, sc, src, lk, rn = name.split("|")
        if rn == "off":
            continue
        off = runs.get(f"{sol}|{d}|{sc}|{src}|{lk}|off")
        off_ok = off is not None and off["phase"] == "home" and off["o2"] >= RESERVE
        for key in (rn, f"{rn}|{src}", f"{rn}|{src}|leak{lk}"):
            a = agg[key]
            a["n"] += 1
            a["dead"] += v["phase"] == "dead"
            if v["phase"] == "home" and v["o2"] < RESERVE:
                a["breach"] += 1; a["breach_g"].append(round(RESERVE - v["o2"], 1))
            if v["turn"] >= 0:
                a["turned"] += 1
                if off_ok:
                    a["over_alarm"] += 1
                if off and off["arrive_min"]:
                    a["frac"].append(v["turn"] / off["arrive_min"])
    summary = {}
    for k, a in sorted(agg.items()):
        f, b = sorted(a.pop("frac")), sorted(a.pop("breach_g"))
        summary[k] = {**a, "breach_pct": round(100 * a["breach"] / max(a["n"], 1), 1),
                      "breach_max_g": max(b) if b else 0.0,
                      "turn_frac_median": round(f[len(f) // 2], 3) if f else None}
    json.dump({"n_dest": len(dests), "destinations": [{"sol": s, "dist_km": d} for s, d, _ in dests],
               "n_runs": len(runs), "summary": summary}, open(os.path.join(OUT, "j9_alarm.json"), "w"),
              ensure_ascii=False, indent=1)
    for k in RULES:
        if k in summary:
            print(k, summary[k], flush=True)


if __name__ == "__main__":
    main()
