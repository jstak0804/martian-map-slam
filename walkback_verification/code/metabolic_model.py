"""보행 대사 모델 (한 곳에서 관리) — 2026-11-10 재검증 반영

두 모델 중 하나를 쓴다. 환경 변수 GALE_METABOLIC_MODEL 로 고른다.
  - "ist_b" (기본): NASA IST-1(NASA/TP-2010-216115, 평지)·IST-2(NASA/TP-2010-216125, 경사) 우주복 보행 실측.
      MKIII 121 kg을 0.12~0.32 g로 시험한 다섯 추세선을 PDF 벡터에서 읽고(recalc/digitize_ist.py),
      각 계수를 총 무게(TGAW = (체중 + 우주복) × 중력)에 대해 선형 회귀했다(data/ist_model_coefs.json).
      화성 무게(75 + 90 kg) × 3.711 = 612 N은 데이터 범위(236~627 N) 안이다.
        VO2 [mL/kg/min] = L(v, W) + ΔG(G, W) · v / 0.77
        M [W] = VO2 · 체중 · 20.1 kJ/L / 60 + (η − 1)(체중 + 우주복)·0.378·1.5·v²   (지형 거칠기 항은 기존 Pandolf와 같은 절대 증가량)
  - "pandolf_legacy": 기존 모델. Pandolf 식 전체에 화성 중력비를 곱함. 이전 결과 재현용.
      재검증에서 실측과 맞지 않는 것으로 확인됨(CHANGELOG.md((프로젝트 루트)) 2.1절).

보행 속도 (ist_b, 2026-11-12 내리막 반영):
  - 평지: GALE_FLAT_SPEED (기본 0.92 m/s = Apollo 15 비상 귀환 계획 3.3 km/h)
  - 경사: "같은 노력" 규칙 — 평지와 같은 대사량이 나오는 속도로 걷는다
    (Apollo 14 승무원이 편한 노력 수준을 유지하고 지형에 따라 속도를 바꿈, Waligora & Horrigan 1975).
    오르막: L(v) + ΔG(G)·v/0.77 = L(v_flat)를 v에 대해 푼다.
    내리막: "같은 노력" 속도와 Tobler 감속 속도 중 작은 쪽(평지 속도 상한). 비용은 Looney 2019 LCDA 비율을
            화성 우주복의 경사 민감도로 줄여 적용(아래 내리막 절).
  - IST 평지 곡선의 속도 범위(0.62 m/s 이상)보다 느린 구간은 외삽이다.

다른 중력(달 등)이 들어오면 IST 모델은 화성 무게 전용이므로 Pandolf 레거시 식을 쓴다.
"""
from __future__ import annotations

import json
import os

import numpy as np

# ---------------- 공통 상수 ----------------
G_RATIO_MARS = 0.378
G_RATIO_MOON = 0.165
G_MARS_M_S2 = 3.711
BODY_MASS_KG = 75.0          # 설계 가정: 우주인 체중
SUIT_MASS_KG = 90.0          # 설계 가정: 우주복+PLSS 질량
ETA_MIN, ETA_MAX = 1.0, 1.5
O2_KJ_PER_L = 20.1           # Weir 식 RER ≈ 0.78에 해당
O2_G_PER_L = 1.429
BTU_H_TO_W = 0.29307

MODEL = os.environ.get("GALE_METABOLIC_MODEL", "ist_b")
V_FLAT_M_S = float(os.environ.get("GALE_FLAT_SPEED", "0.92"))
V_LEGACY_M_S = 0.92          # 기존 고정 속도 (pandolf_legacy)
V_MIN_M_S = 0.2              # 수치 안전용 하한
V_IST2_M_S = 0.77            # IST-2 경사 시험 속도
IST_LEVEL_V_MIN = 0.62       # IST-1 평지 곡선의 최저 측정 속도

# 30분 예비분 환산 대사율: NASA 설계 평균 1200 BTU/h (Apollo PLSS 설계, EMU 소모품 여유 정의,
# 화성 PLSS 설계 평균 350 W). CHANGELOG.md((프로젝트 루트)) 3.1절.
RESERVE_MR_W = 1200 * BTU_H_TO_W
RESERVE_HOURS = 0.5

_COEF_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "ist_model_coefs.json")
with open(_COEF_PATH) as _f:
    _IST = json.load(_f)
_W_MARS_N = (BODY_MASS_KG + SUIT_MASS_KG) * G_MARS_M_S2
_LA, _LB, _LC = (s * _W_MARS_N + i for s, i in _IST["level_lin"])
_GA, _GB = (s * _W_MARS_N + i for s, i in _IST["grade_lin"])


# ---------------- 내리막 (2026-11-12) ----------------
# 비용: Looney et al. 2019 (Med Sci Sports Exerc 51:1954) LCDA 경사 보행식 — 지구, 맨몸, 11개 연구 95명,
#   경사 −40~+45%. EE[W/kg] = 1.44 + 1.94 S^0.43 + 0.24 S^4 + 0.34·S·G·(1 − 1.05^(1 − 1.1^(G+32)))
#   이 식의 "내리막 ÷ 평지" 비율을, 같은 경사의 오르막에서 잰 "화성 우주복(IST) ÷ 지구 맨몸(LCDA)" 상대 효과
#   비율로 줄여 적용한다(결정 (나)). 화성 중력·우주복 내리막 실측은 없으므로 이 축소는 가정이다.
# 속도: Tobler(1993) 보행 함수 v = 1.6̄·exp(−3.5·|tanθ + 0.05|) m/s (Campbell et al. 2019, Applied Geography
#   106:93, 식 1로 확인)의 "평지 대비 비율"을 평지 속도에 곱한 값과 "같은 노력" 속도 중 작은 쪽.
#   평지보다 빨라지지는 않는다. Campbell 2019는 Tobler 식이 가파른 경사에서 속도를 과소평가한다고 보고했다
#   (가파른 내리막에서 느리게 → 시간이 길어져 산소를 보수적으로 계산).


def lcda_ee_w_kg(speed_m_s, grade_pct):
    s = np.asarray(speed_m_s, dtype=float)
    g = np.asarray(grade_pct, dtype=float)
    return 1.44 + 1.94 * s ** 0.43 + 0.24 * s ** 4 + 0.34 * s * g * (1 - 1.05 ** (1 - 1.1 ** (g + 32)))


def grade_effect_scale(abs_grade_pct):
    """같은 경사(오르막)에서 '화성 우주복의 평지 대비 증가 ÷ 지구 맨몸의 평지 대비 증가'. 0.77 m/s(IST-2 속도) 기준."""
    g = np.maximum(np.asarray(abs_grade_pct, dtype=float), 1.0)
    ist_rel = ist_grade_inc_vo2(g) / ist_level_vo2(V_IST2_M_S)
    lcda_rel = lcda_ee_w_kg(V_IST2_M_S, g) / lcda_ee_w_kg(V_IST2_M_S, 0.0) - 1.0
    return ist_rel / lcda_rel


def downhill_cost_ratio(grade_pct, speed_m_s=None):
    """내리막 대사 비용 ÷ 같은 속도의 평지 비용 (G < 0). 오르막·평지는 1."""
    g = np.asarray(grade_pct, dtype=float)
    v = np.full_like(g, V_FLAT_M_S) if speed_m_s is None else np.asarray(speed_m_s, dtype=float)
    r_earth = lcda_ee_w_kg(v, np.minimum(g, 0.0)) / lcda_ee_w_kg(v, 0.0)
    r = 1.0 + grade_effect_scale(np.abs(g)) * (r_earth - 1.0)
    return np.where(g < 0, r, 1.0)


def tobler_speed_factor(grade_pct):
    """Tobler 보행 함수의 평지 대비 속도 비 (경사 % → tanθ = G/100)."""
    g = np.asarray(grade_pct, dtype=float)
    return np.exp(-3.5 * np.abs(g / 100.0 + 0.05)) / np.exp(-3.5 * 0.05)


# ---------------- IST 모델 ----------------
def ist_level_vo2(v):
    v = np.asarray(v, dtype=float)
    return _LA * v ** 2 + _LB * v + _LC


def ist_grade_inc_vo2(grade_pct):
    g = np.maximum(np.asarray(grade_pct, dtype=float), 0.0)
    return _GA * g ** 2 + _GB * g


def _target_vo2():
    return float(ist_level_vo2(V_FLAT_M_S))


def walk_speed(grade_pct):
    """경사별 보행 속도 (m/s). pandolf_legacy는 0.92 고정."""
    g = np.asarray(grade_pct, dtype=float)
    if MODEL == "pandolf_legacy":
        return np.full_like(g, V_LEGACY_M_S)
    t = _target_vo2()
    # 오르막: a v² + (b + k) v + (c − T) = 0, k = ΔG/0.77. 증가 구간의 근을 수치적으로 안정한 형태로 구함.
    k = ist_grade_inc_vo2(g) / V_IST2_M_S
    bq = _LB + k
    cq = _LC - t
    disc = np.maximum(bq ** 2 - 4 * _LA * cq, 0.0)
    v_up = -2 * cq / (bq + np.sqrt(disc))
    # 내리막: (1) 같은 노력 — 비용 비율 r ≤ 1이면 평지 속도, r > 1이면 r·L(v) = T를 푼다(r은 평지 속도에서 평가).
    #         (2) Tobler 감속 — 평지 속도 × min(1, Tobler 비). 둘 중 작은 쪽.
    gd = np.minimum(g, 0.0)
    r = downhill_cost_ratio(gd)
    cq_d = _LC - t / np.maximum(r, 1e-9)
    disc_d = np.maximum(_LB ** 2 - 4 * _LA * cq_d, 0.0)
    v_ce = np.where(r > 1.0, -2 * cq_d / (_LB + np.sqrt(disc_d)), V_FLAT_M_S)
    v_down = np.minimum(v_ce, V_FLAT_M_S * np.minimum(1.0, tobler_speed_factor(gd)))
    v = np.where(g > 0, v_up, v_down)
    return np.clip(v, V_MIN_M_S, V_FLAT_M_S)


def speed_extrapolated(v):
    """IST 평지 곡선의 측정 범위(0.62 m/s)보다 느린지."""
    return np.asarray(v) < IST_LEVEL_V_MIN


# ---------------- Pandolf (레거시·정지·다른 중력) ----------------
def pandolf_metabolic_rate_w(grade_pct, eta=1.0, g_ratio=G_RATIO_MARS, v=V_LEGACY_M_S):
    """기존 식: Pandolf, 질량 항에 중력비를 곱함, 내리막 = 평지."""
    w = BODY_MASS_KG * g_ratio
    l = SUIT_MASS_KG * g_ratio
    g = np.maximum(grade_pct, 0.0)
    return 1.5 * w + 2.0 * (w + l) * (l / w) ** 2 + eta * (w + l) * (1.5 * v ** 2 + 0.35 * v * g)


STANDING_MR_W = float(pandolf_metabolic_rate_w(0.0, 1.0, G_RATIO_MARS, 0.0))   # 짐 진 채 정지 (결정 D3)


# ---------------- 공개 함수 ----------------
def metabolic_rate_w(grade_pct, eta=1.0, g_ratio=G_RATIO_MARS, v=None):
    """대사량 (W). v=None이면 경사별 보행 속도(walk_speed)로 계산한다.
    v=0은 '짐 진 채 정지'로, 실측 대체 근거가 없어 Pandolf 정지 값(222 W)을 유지한다(결정 D3)."""
    if v is not None and np.all(np.asarray(v) == 0):
        return pandolf_metabolic_rate_w(grade_pct, eta, g_ratio, 0.0)
    if MODEL == "pandolf_legacy" or abs(g_ratio - G_RATIO_MARS) > 1e-9:
        return pandolf_metabolic_rate_w(grade_pct, eta, g_ratio, V_LEGACY_M_S if v is None else v)
    g = np.asarray(grade_pct, dtype=float)
    vv = walk_speed(g) if v is None else np.asarray(v, dtype=float)
    up = ist_grade_inc_vo2(g) * vv / V_IST2_M_S
    down = ist_level_vo2(vv) * (downhill_cost_ratio(np.minimum(g, 0.0), vv) - 1.0)
    vo2 = ist_level_vo2(vv) + np.where(g > 0, up, down)
    terrain = (np.asarray(eta, dtype=float) - 1.0) * (BODY_MASS_KG + SUIT_MASS_KG) * G_RATIO_MARS * 1.5 * vv ** 2
    mr = vo2 * BODY_MASS_KG * O2_KJ_PER_L / 60.0 + terrain
    # 2026-11-12 (PLAN_D 2번): 걷는 비용은 서 있는 비용보다 작을 수 없다(Looney 2019 식 1 = 서 있는 상수 + 0 이상의
    # 보행 항). IST 평지 곡선을 측정 범위(0.62 m/s) 아래로 외삽할 때만 걸린다. 서 있는 값은 결정 D3대로 Pandolf 222 W.
    return np.maximum(mr, STANDING_MR_W)


def o2_g_per_s(metabolic_w):
    return np.asarray(metabolic_w) / (O2_KJ_PER_L * 1000) * O2_G_PER_L


def edge_rate(grade_pct, eta=1.0, g_ratio=G_RATIO_MARS):
    """칸 이동 한 번의 (대사량 W, 속도 m/s)."""
    if MODEL == "pandolf_legacy" or abs(g_ratio - G_RATIO_MARS) > 1e-9:
        v = np.full_like(np.asarray(grade_pct, dtype=float), V_LEGACY_M_S)
    else:
        v = walk_speed(grade_pct)
    return metabolic_rate_w(grade_pct, eta, g_ratio, v), v


LEVEL_SPEED_M_S = float(walk_speed(0.0))
LEVEL_MR_W = float(metabolic_rate_w(0.0, 1.0, G_RATIO_MARS))
LEVEL_O2_G_PER_H = float(o2_g_per_s(LEVEL_MR_W)) * 3600
# 예비분: ist_b는 NASA 설계 평균(352 W) 30분 고정량, legacy는 기존 정의(평지 보행 30분)를 그대로 재현
O2_RESERVE_G = (float(o2_g_per_s(RESERVE_MR_W)) if MODEL != "pandolf_legacy"
                else LEVEL_O2_G_PER_H / 3600) * 3600 * RESERVE_HOURS
RESERVE_MR_FOR_WATER_W = RESERVE_MR_W if MODEL != "pandolf_legacy" else LEVEL_MR_W


def describe() -> dict:
    return {"model": MODEL, "flat_speed_m_s": LEVEL_SPEED_M_S, "level_mr_w": round(LEVEL_MR_W, 1),
            "level_o2_g_per_h": round(LEVEL_O2_G_PER_H, 2), "o2_reserve_g": round(O2_RESERVE_G, 2),
            "reserve_mr_w": round(RESERVE_MR_FOR_WATER_W, 1)}


if __name__ == "__main__":
    print(describe())
    for gr in (-35, -30, -20, -10, -5, 0, 5, 10, 15, 20, 30):
        mr, v = edge_rate(np.array(float(gr)))
        o2m = float(o2_g_per_s(mr)) / float(v)
        print(f"경사 {gr:>4}%: 속도 {float(v):.2f} m/s{' [외삽]' if speed_extrapolated(v) else ''}, 대사량 {float(mr):.0f} W, "
              f"1 m당 산소 {o2m * 1000:.1f} mg, 내리막 비용비 {float(downhill_cost_ratio(gr, v)):.3f}")
