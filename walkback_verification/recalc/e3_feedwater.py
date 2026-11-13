"""계획 E 3번: 냉각수 모델(대사열 ÷ 잠열)을 ISS EMU 운용 자료(JSC-20597)와 대조

실행: recalc/.venv/bin/python recalc/e3_feedwater.py
- JSC-20597 Vol.4 Rev.B 그림 2.9-9(중립 사례: 우주복-환경 열 교환이 거의 없음)의 50% 남성 곡선을 눈으로 읽은 값(±0.5 h).
  그림이 래스터 이미지라 벡터 판독은 불가. 원문 사본: research/sources/EVA_Console_Handbook_EMU_Ops_JSC20597_ibiblio.pdf 158쪽.
- EMU 냉각은 승화기(얼음 승화). 승화열 약 2834 J/g(0 °C, 일반 물성값 — 원문 미확인). 화성 PLSS의 SWME는 증발열 2477 J/g.
- 냉각수 전량: 본문 "three tanks hold 9.1 lb", 표 1.1-1 "8.35 lb primary + 0.83 lb reserve = 9.18 lb". 쓸 수 있는 양이
  명시되지 않아 9.1 lb와 8.35 lb(주 탱크만) 두 경우로 본다.
"""
import json, os
BTU = 0.29307
L_SUB = 2834.0
fig = {400: 18.5, 800: 10.7, 1600: 6.0, 2000: 4.9}   # BTU/h -> h (그림 2.9-9, 50% male, 눈 판독)
out = {"figure_read": fig, "cases": {}}
for name, water_lb in (("9.1 lb", 9.1), ("8.35 lb", 8.35)):
    w_g = water_lb * 453.592
    rows = []
    for mr_btu, life_h in fig.items():
        mr_w = mr_btu * BTU
        model_h = w_g / (mr_w / L_SUB * 3600)
        heat_w = w_g / life_h / 3600 * L_SUB
        rows.append({"mr_btu_h": mr_btu, "mr_w": round(mr_w, 1), "chart_h": life_h, "model_h_q0": round(model_h, 1),
                     "implied_total_heat_w": round(heat_w, 1), "implied_extra_heat_w": round(heat_w - mr_w, 1)})
    out["cases"][name] = rows
out["text_values"] = {"conservative_usage_lb_h": 0.8, "sts61_average_lb_h": 0.72,
                      "model_at_1000btu_h_g_h": round(1000 * BTU / L_SUB * 3600, 0), "0.8_lb_h_in_g_h": round(0.8 * 453.592, 0)}
os.makedirs("outputs_e", exist_ok=True)
json.dump(out, open("outputs_e/e3_feedwater.json", "w"), ensure_ascii=False, indent=2)
for k, rows in out["cases"].items():
    print(k)
    for r in rows: print("  ", r)
print(out["text_values"])
