"""계획 I4: 냉각수 추가 열(환경·PLSS 열 q) → 기준 면적·구조 예시·심박 예시 (분석만)

실행: cd code && ../recalc/.venv/bin/python ../recalc/i4_extra_heat.py
- 근거: 계획 E 3번(JSC-20597 그림 대조)에서 역산한 추가 열 22~44 W(가용 8.35 lb) 또는 58~77 W(9.1 lb).
  결정 E-a는 0 유지. 데모의 "환경 열" q가 같은 역할이므로 q = 0/25/50/75 W를 돌린다.
"""
from __future__ import annotations

import json
import os
import re
import subprocess

ROOT = os.path.abspath(os.path.join(os.getcwd(), ".."))
OUT = os.path.join(ROOT, "recalc", "outputs_i")
QS = [0, 25, 50, 75]


def num(s: str) -> float:
    return float(s.replace(",", ""))


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    jobs = []
    for q in QS:
        jobs += [
            {"name": f"base|{q}", "preset": "base", "set": {"mode": "inspect", "q": q}},
            {"name": f"water06|{q}", "preset": "base", "set": {"mode": "inspect", "q": q, "water": 0.6}},
            {"name": f"rescue|{q}", "preset": "rescue", "set": {"q": q}, "read": ["pt-verdict", "pt-meters", "supply"]},
            {"name": f"simhr|{q}", "preset": "simhr", "set": {"q": q}},
        ]
    jp, op = os.path.join(OUT, "i4_jobs.json"), os.path.join(OUT, "i4_raw.json")
    json.dump(jobs, open(jp, "w"))
    r = subprocess.run(["node", os.path.join(ROOT, "recalc", "h1_demo_harness.mjs"),
                        os.path.join(ROOT, "demo", "gale-eva-walkback-demo.html"), jp, op], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-3000:])
    res = {"q_w": QS, "tank_g": 3600, "cases": {}}
    for x in json.load(open(op)):
        kind, q = x["name"].split("|")
        c = res["cases"].setdefault(q, {})
        if kind in ("base", "water06"):
            c[f"{kind}_area_km2"] = round(x["summary"]["safe"], 3)
        elif kind == "rescue":
            t = x["text"]
            m = re.search(r"구조대원 출발 시 최소량 ([\d,]+) g · ([\d,]+) g", t["supply"])
            c["rescue_verdict"] = t["pt-verdict"]
            c["rescuer_min_o2_g"], c["rescuer_min_water_g"] = num(m.group(1)), num(m.group(2))
            c["rescuer_water_margin_g"] = 3600 - c["rescuer_min_water_g"]
        else:
            s = x["sim"]; last = s["log"][-1]["text"]
            c["simhr_turn_min"] = s["turnMin"]; c["simhr_last_log"] = last
    json.dump(res, open(os.path.join(OUT, "i4_extra_heat.json"), "w"), ensure_ascii=False, indent=1)
    for q in QS:
        print(q, res["cases"][str(q)])


if __name__ == "__main__":
    main()
