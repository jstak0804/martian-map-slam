"""계획 I6: Apollo 14 한 점 점검 (검증 아님)

실행: cd code && ../recalc/.venv/bin/python ../recalc/i6_apollo14.py
비교 대상 [확인: Waligora & Horrigan 1975, references/Waligora1975_metabolic_cost_EVA.pdf, p.780]:
  "Apollo 14 보행 2.9 km, 평균 2.4 km/h, 대사량 300 kcal/h" → 0.667 m/s, 348.9 W
질량 [미확인, 범위로 둠]:
  - 체중 70~80 kg (가정)
  - A7L 우주복 + PLSS 80~95 kg. 2차 자료(위키백과 계열)는 Apollo 7~14 EVA 우주복 총 91 kg(200 lb)이나 출처끼리 엇갈림
모델:
  - IST 평지식(data/ist_model_coefs.json): VO2[mL/kg/min] = a v² + b v + c, 계수 = slope × TGAW + intercept,
    TGAW = (체중 + 우주복) × 1.62 m/s². 대사량 = VO2 × 체중 × 20.1 kJ/L / 60
  - 이전 방식: Pandolf 식 전체 × 달 중력비(0.165), metabolic_model.pandolf_metabolic_rate_w와 같은 식
경사 보정은 하지 않는다(Apollo 14 경로에 Cone 크레이터 오르막 포함 → 실측이 평지 모델보다 높게 나오는 방향).
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.getcwd())
import numpy as np  # noqa: E402

import metabolic_model as mm  # noqa: E402

OUT = os.path.abspath(os.path.join(os.getcwd(), "..", "recalc", "outputs_i"))
G_MOON = 1.62
V = 2.4 / 3.6
MEASURED_W = 300 * 4184 / 3600   # 300 kcal/h
BODY = (70.0, 75.0, 80.0)
SUIT = (80.0, 91.0, 95.0)


def ist_mr_w(body: float, suit: float, v: float) -> tuple[float, float]:
    tgaw = (body + suit) * G_MOON
    a, b, c = (s * tgaw + i for s, i in mm._IST["level_lin"])
    vo2 = a * v * v + b * v + c
    return vo2 * body * mm.O2_KJ_PER_L / 60, tgaw


def pandolf_mr_w(body: float, suit: float, v: float) -> float:
    w, l = body * mm.G_RATIO_MOON, suit * mm.G_RATIO_MOON
    return 1.5 * w + 2.0 * (w + l) * (l / w) ** 2 + (w + l) * (1.5 * v ** 2)


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    rng = mm._IST.get("tgaw_range_n")
    vr = mm._IST.get("level_v_range_m_s")
    rows = []
    for b in BODY:
        for s in SUIT:
            ist, tgaw = ist_mr_w(b, s, V)
            rows.append({"body_kg": b, "suit_kg": s, "tgaw_n": round(tgaw, 1), "tgaw_in_ist_range": rng[0] <= tgaw <= rng[1],
                         "ist_w": round(ist, 1), "ist_ratio_measured": round(ist / MEASURED_W, 3),
                         "pandolf_moon_w": round(pandolf_mr_w(b, s, V), 1),
                         "pandolf_ratio_measured": round(pandolf_mr_w(b, s, V) / MEASURED_W, 3)})
    ist_all = [r["ist_w"] for r in rows]; pan_all = [r["pandolf_moon_w"] for r in rows]
    res = {"measured": {"source": "Waligora & Horrigan 1975 p.780 (Apollo 14, 2.9 km, 2.4 km/h, 300 kcal/h)",
                        "v_m_s": round(V, 3), "mr_w": round(MEASURED_W, 1)},
           "v_in_ist_level_range": vr[0] <= V <= vr[1], "ist_level_v_range": vr, "ist_tgaw_range_n": rng,
           "ist_w_range": [min(ist_all), max(ist_all)], "pandolf_moon_w_range": [min(pan_all), max(pan_all)],
           "rows": rows,
           "note": "한 점 점검이며 검증 아님. 평지 모델 vs 오르막 섞인 실측 평균, 보행 외 활동 혼입 가능, 질량은 범위."}
    json.dump(res, open(f"{OUT}/i6_apollo14.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, ensure_ascii=False, indent=1))
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
