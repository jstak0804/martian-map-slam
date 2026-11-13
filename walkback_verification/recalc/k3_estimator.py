"""계획 K3: 생리 지연이 있을 때 k 추정기·여유 비교 (분석만, 데모 기본값 불변)

실행: cd code && env -u PYTHONPATH ../recalc/.venv/bin/python ../recalc/k3_estimator.py
- 목적지·조건: 계획 J9와 같음(25곳 × 시나리오 4 × 심박/압력 × 누설 0/10, 산소 450 g)
- 생리 지연 simLagTau(분): 주 값 2.2(Kim 2023 혼합 지형 정상 상태 6.72분 ≈ 3τ, 추정), 민감도 1.0 / 3.5, 확인용 0
- 추정기 simKEst: ratio10(현재) / aligned10 / aligned5 (aligned = 모델 예측에도 같은 1차 지연, Kim 2025 DF 개념)
- 여유 simKMargin: 1.0 / 1.2
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import defaultdict

sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), "..", "recalc")))
from i3_alarm_sweep import destinations  # noqa: E402
from j9_alarm import extra_destinations  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.getcwd(), ".."))
OUT = os.path.join(ROOT, "recalc", "outputs_k")
RESERVE = 45.0
EST = ("ratio10", "aligned10", "aligned5")
RULES = []   # (tau, rule name, settings)
for tau in (2.2,):
    RULES.append((tau, "off", {"simAuto": False}))
    for est in EST:
        for m in (1.0, 1.2):
            RULES.append((tau, f"{est}|M{m}", {"simKEst": est, "simKMargin": m}))
for tau in (1.0, 3.5):
    RULES.append((tau, "off", {"simAuto": False}))
    for est, m in (("ratio10", 1.0), ("ratio10", 1.2), ("aligned10", 1.2)):
        RULES.append((tau, f"{est}|M{m}", {"simKEst": est, "simKMargin": m}))
RULES.append((0.0, "ratio10|M1.0", {"simKEst": "ratio10", "simKMargin": 1.0}))   # J9 N1 재현 확인
RULES.append((0.0, "off", {"simAuto": False}))
DEFAULTS = {"simAuto": True, "simLookMin": 1, "simKMargin": 1.0, "simKTrend": False, "simKEst": "ratio10"}


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
                    for tau, rn, rs in RULES:
                        jobs.append({"name": f"{sol}|{d}|{sc}|{src}|{lk}|{tau}|{rn}", "preset": "simhr",
                                     "set": {**base, **DEFAULTS, "simLagTau": tau, **rs}})
    jp, op = os.path.join(OUT, "k3_jobs.json"), os.path.join(OUT, "k3_raw.json")
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
    agg = defaultdict(lambda: {"n": 0, "breach": 0, "dead": 0, "over_alarm": 0, "frac": [], "breach_g": []})
    for name, v in runs.items():
        sol, d, sc, src, lk, tau, est, mg = name.split("|") if name.count("|") == 7 else (*name.split("|"), "")
        rn = f"{est}|{mg}" if mg else est
        if rn == "off":
            continue
        off = runs.get(f"{sol}|{d}|{sc}|{src}|{lk}|{tau}|off")
        off_ok = off is not None and off["phase"] == "home" and off["o2"] >= RESERVE
        for key in (f"tau{tau}|{rn}", f"tau{tau}|{rn}|{src}", f"tau{tau}|{rn}|{src}|leak{lk}"):
            a = agg[key]
            a["n"] += 1; a["dead"] += v["phase"] == "dead"
            if v["phase"] == "home" and v["o2"] < RESERVE:
                a["breach"] += 1; a["breach_g"].append(round(RESERVE - v["o2"], 1))
            if v["turn"] >= 0:
                if off_ok:
                    a["over_alarm"] += 1
                if off and off["arrive_min"]:
                    a["frac"].append(v["turn"] / off["arrive_min"])
    summary = {}
    for k, a in sorted(agg.items()):
        f, b = sorted(a.pop("frac")), sorted(a.pop("breach_g"))
        summary[k] = {**a, "breach_pct": round(100 * a["breach"] / max(a["n"], 1), 1), "breach_max_g": max(b) if b else 0.0,
                      "turn_frac_median": round(f[len(f) // 2], 3) if f else None}
    json.dump({"n_runs": len(runs), "summary": summary}, open(os.path.join(OUT, "k3_estimator.json"), "w"),
              ensure_ascii=False, indent=1)
    for k, v in summary.items():
        if k.count("|") == 2:
            print(k, v, flush=True)


if __name__ == "__main__":
    main()
