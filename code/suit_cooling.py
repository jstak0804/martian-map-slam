"""
우주복 냉각수(feedwater) 소모 모델 — 귀환 반경의 세 번째 소모품

우주복은 몸에서 나온 열을 액체냉각복(LCVG)으로 모아 PLSS의 증발기에서 물을 날려 버린다.
버린 물은 돌아오지 않으므로 냉각수도 산소처럼 "다 쓰면 끝"인 소모품이다.

  냉각수 소모율(g/s) = max(0, 대사량 W + Q_extra W) / 물의 증발잠열(J/kg) x 1000
  Q_extra = PLSS 내부 발열 + 환경에서 들어오는 열(+) 또는 빠져나가는 열(-)

Q_extra = 0이면 냉각수와 산소가 둘 다 대사량에 비례하므로 "남은 비율이 더 작은 쪽"이 귀환을 묶는다.
Q_extra가 0이 아니면 시간에 비례하는 항이 생겨, 느리고 긴 경로일수록 냉각수가 산소보다 빨리 준다.

문헌 수치:
  - 증발잠열 2.477 MJ/kg: 물 10 °C 증기표 값. 화성용으로 검토 중인 SWME는 보통 10 °C(50 °F)에서
    작동한다(Ogilvie et al., ICES-2026-126, NTRS 20260003024, p.10).
  - 만충 냉각수 3.6 kg(8 lbm): 8시간 EVA용 승화기에 싣는 물, "8시간 EVA에서 가장 큰 소모품"
    (Nabity et al., ICES 2007, 07ICES-221, NTRS 20070013698, 초록). Shuttle/ISS EMU PLSS는 3.9 kg을 싣고
    7 h @ 1000 BTU/hr로 정격(Akin, UMD ENAE 697 강의 p.8) — 같은 자릿수.
  - 승화기는 물의 삼중점(611 Pa)보다 낮은 압력에서만 작동해 화성 표면에서는 쓸 수 없고(ICES-2026-126 p.4,
    UMD p.9), SWME는 10 Torr(1333 Pa)까지 시험되어 화성에서도 작동 가능하나 성능 저하·먼지 필터 문제가
    남아 있다(ICES-2026-126 p.10~11). 그래서 화성 EVA 후보지는 7~8 Torr 이하로 가정한다(p.7).
  - 체온 축적 한계: 정상 운용 쾌적 범위 <= 1.3 BTU/lb, 비상 운용 "인지 저하 시작(CDO)" <= 2.0 BTU/lb
    (Mah & Machak, ICES-2026-170, NTRS 20260005313, slide 5). 1 BTU/lb = 2.326 kJ/kg.
  - 기존 EMU는 냉각수 잔량을 연속으로 재지 못했다: 1차 주머니가 비면 2차 주머니가 열리는 압력 변화로만
    알았다. 연속 잔량 센서는 지금 개발 중이다(ICES-2026-126 p.13, "Feedwater Supply Volume Sensing").

설계 가정(측정값 아님):
  - 대사량 전부가 열이 되어 증발기로 간다고 본다(오르막에서 위치에너지로 가는 몫·호흡 손실 무시 -> 보수적).
  - Q_extra 기본값 0 W. 화성에서는 MLI 단열이 대기압 때문에 크게 떨어지고(진공 <1 W/m^2 -> 화성 >100 W/m^2,
    ICES-2026-126 p.10) 평균 기온이 -60 °C라 우주복이 열을 잃는 쪽(-)일 가능성이 크지만, 햇빛·PLSS 발열로
    +가 될 수도 있다. 이 값은 측정치가 없으므로 시나리오로 돌린다.
  - 냉각수 예비분: 산소와 같은 원칙(Apollo 30분 예비분)으로 평지 보행 30분어치.
  - 물이 떨어진 뒤에는 대사열이 전부 몸에 쌓인다고 본다(최악). 그러면 비상 한계(2.0 BTU/lb)까지
    버틸 수 있는 열은 "물 몇 g어치"로 바꿔 쓸 수 있다: HEAT_STORAGE_WATER_EQ_G.
"""
from __future__ import annotations

import numpy as np

from metabolic_navigation import metabolic_rate_w, BODY_MASS_KG, G_RATIO_MARS
from human_mission_navigation import EVA_WALK_SPEED_M_S

LATENT_HEAT_J_PER_KG = 2.477e6     # 물 증발잠열 @ 10 °C (SWME 작동 온도)
FEEDWATER_FULL_G = 3600.0          # Nabity et al. 2007: 8 h EVA 승화기 냉각수 3.6 kg (8 lbm)
Q_EXTRA_W = 0.0                    # 설계 가정: PLSS 발열 + 환경 열 유입/유출 (미측정, 시나리오 변수)

BTU_PER_LB_TO_J_PER_KG = 2326.0
HEAT_STORAGE_COMFORT_BTU_LB = 1.3  # ICES-2026-170: 정상 운용 쾌적 상한
HEAT_STORAGE_CDO_BTU_LB = 2.0      # ICES-2026-170: 비상 운용 인지 저하 시작(CDO) 상한
HEAT_STORAGE_CDO_J = HEAT_STORAGE_CDO_BTU_LB * BTU_PER_LB_TO_J_PER_KG * BODY_MASS_KG
# 물이 떨어진 뒤 CDO 한계까지 몸에 쌓을 수 있는 열을 냉각수 질량으로 환산 (75 kg 기준 약 141 g)
HEAT_STORAGE_WATER_EQ_G = HEAT_STORAGE_CDO_J / LATENT_HEAT_J_PER_KG * 1000

LEVEL_MR_W = float(metabolic_rate_w(0.0, 1.0, G_RATIO_MARS))


def water_g_per_s(metabolic_w, q_extra_w=Q_EXTRA_W):
    return np.maximum(0.0, metabolic_w + q_extra_w) / LATENT_HEAT_J_PER_KG * 1000


def water_reserve_g(q_extra_w=Q_EXTRA_W):
    """Apollo 30분 예비분 원칙을 냉각수에 그대로 적용: 평지 보행 30분어치."""
    return float(water_g_per_s(LEVEL_MR_W, q_extra_w)) * 1800


def minutes_to_cdo(metabolic_w, q_extra_w=Q_EXTRA_W):
    """냉각수가 떨어진 순간부터 비상 체온 한계(CDO)까지 남은 분. 대사열 전부가 몸에 쌓인다고 본 최악값."""
    heat_w = np.maximum(1e-6, metabolic_w + q_extra_w)
    return HEAT_STORAGE_CDO_J / heat_w / 60


if __name__ == "__main__":
    lvl = water_g_per_s(LEVEL_MR_W) * 3600
    print(f"화성 평지 보행 {LEVEL_MR_W:.0f} W -> 냉각수 {lvl:.0f} g/h, 만충 {FEEDWATER_FULL_G/1000:.1f} kg = "
          f"{FEEDWATER_FULL_G / lvl:.1f} h, 예비분 {water_reserve_g():.0f} g")
    print(f"물이 떨어진 뒤 CDO까지: 평지 보행 {float(minutes_to_cdo(LEVEL_MR_W)):.0f}분 "
          f"(= 냉각수 {HEAT_STORAGE_WATER_EQ_G:.0f} g어치, {float(HEAT_STORAGE_WATER_EQ_G / lvl * 60):.0f}분 x "
          f"{EVA_WALK_SPEED_M_S} m/s = {float(minutes_to_cdo(LEVEL_MR_W)) * 60 * EVA_WALK_SPEED_M_S / 1000:.2f} km)")
