"""
유인 미션 확장 위험도 공식 — 지형(경사+거칠기)에 시간가변 환경요인(온도, 방사선)을 더한다

기존 risk_total(x,y) = clip(0.4*slope_risk + 0.6*rock_risk, 0, 1) (exploration_slam_sim.true_risk_field,
real_terrain_risk.terrain_risk, anisotropic_risk_exploration)은 전부 '무인 로버가 전복되는가'만
평가한다 — 지형이 바뀌지 않는 한 risk는 시간에 따라 변하지 않는다.

유인 미션에서는 지형이 안전해도 "언제" 그 지형 위에 있는지가 생사를 가를 수 있다 — 화성의 밤은
배터리와 생명유지장비가 저온으로 고장날 수 있는 온도까지 떨어지고, 태양입자사건(SPE)이 터지면
몇 시간 안에 방사선량이 치솟는다. 이 스크립트는 기존 지형 위험도 항을 그대로 두고, 두 개의
시간가변 항을 추가한다.

실측/문헌 기반 수치 (설계 가정과 분리해서 명시):
  - 방사선 배경값: Curiosity RAD 관측, Gale Crater 지표면 평균 은하우주선(GCR) 등가선량률
    0.64 ± 0.12 mSv/day, 흡수선량률 0.210 ± 0.040 mGy/day (Hassler et al. 2014, Science 343,
    1244797, 표 1 — 원문 확인 2026-11-12).
    태양입자사건(SPE): 착륙 후 최대인 2017년 9월 사건에서 선량률이 GCR 배경의 2~3배로 몇 시간 상승
    (Zeitlin et al. 2018, GRL 45:5845, 초록). 2013년 4월 sol 242 사건은 GCR 대비 약 30% 상승
    (Hassler 2014 본문) — 2026-11-12 이전 주석의 "평상시 ~90 uGy/day 대비 2.9배"는 출처에 없는 값이었다.
  - 일교차: JPL 공식 설명 기준 Curiosity 주변 기온은 오후 최고~야간 최저 사이 통상 55°C(100°F)
    이상 떨어지고, 겨울밤 최저는 -100°C 근처까지 기록됨; 여름 지표 온도는 한낮 0~16°C까지 상승
    (JPL REMS 설명, universetoday.com 요약 보도).
  - 공식 우주비행사 피폭 한도(NASA-STD-3001, OCHMO 2021 개정) — D_BUDGET_MSV_DAY와는 단위
    체계가 다른(사건당/30일당/커리어당 누적 한도) 참고용 수치: 커리어 유효선량 한도 600 mSv
    (성별·연령 무관 단일 기준), 조혈장기(BFO) 30일 한도 250 mSv, 단일 SPE 사건 유효선량
    한도 250 mSv/event(1989년 10월 사건을 참조 사건으로 사용). Orion 설계 목표치는 대형 SPE
    발생 시 "storm shelter" 내부 피폭 150 mSv 이하(NASA OCHMO radiation protection technical
    brief, nasa.gov).

설계 가정(측정값이 아님, 명시적으로 분리):
  - 저온 위험 임계값(T_SAFE_LOW=-70°C, T_CRITICAL_LOW=-95°C)은 실제 EVA 슈트/배터리 사양이
    아니라 "이 정도부터 배터리·관절 액추에이터 고장 위험이 급격히 커진다"는 예시적 가정이다.
  - 지형 차폐 proxy(shielding_factor)는 국소 지형이 주변보다 낮을수록(크레이터·협곡 바닥)
    머리 위 암반에 둘러싸여 방사선이 약간 줄어든다는 단순화된 가정 — 실제 차폐는 지붕형 암반이
    있어야 효과적이며 고도차만으로는 근사치에 불과함을 명시한다.
  - "일일 경고 기준선"(D_BUDGET)은 공식 우주비행사 피폭 한도가 아니라, 배경값 대비 상대적으로
    경고를 띄우는 예시적 기준이다.
  - W_TERRAIN/W_HUMAN 가중치(지형 항 대 인체환경 항의 상대적 비중)도 측정값이 아닌 설계 가정.

하위호환성 — 새 공식이 기존 공식을 깨지 않고 엄밀히 일반화함을 코드로 보증한다:
  W_HUMAN=0 (인체환경 항 가중치 0)이면 W_TERRAIN=1로 재정규화되어 risk_total이 기존
  true_risk_field()와 격자점에서 완전히 일치해야 한다 — anisotropic_risk_exploration.py의
  sanity_check_reduces_to_isotropic()와 동일한 검증 패턴.

exploration_slam_sim.generate_terrain()과 anisotropic_risk_exploration.rock_risk_grid()/
slope_grids()는 그대로 재사용하고, 새 항(온도/방사선)과 결합 로직만 이 파일에 새로 작성한다.
"""
from __future__ import annotations

import json
import os

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import exploration_slam_sim as sim
from exploration_slam_sim import GRID, CELL_M, RISK_CMAP
from anisotropic_risk_exploration import rock_risk_grid, slope_grids

OUT_DIR = "../outputs/human_mission_risk"
os.makedirs(OUT_DIR, exist_ok=True)

# ============================================================
# 1. 지형 항 가중치 (기존과 동일 — 0.4 slope / 0.6 rock)
# ============================================================

SLOPE_W = 0.4
ROCK_W = 0.6

# 지형 항 대 인체환경 항의 상대적 비중 — 설계 가정
W_TERRAIN = 0.6
W_HUMAN = 0.4
W_THERMAL = 0.5  # W_HUMAN 안에서 온도:방사선 = 1:1
W_RADIATION = 0.5

# ============================================================
# 2. 온도 모델 — 문헌 기반 일교차 + 설계 가정 임계값
# ============================================================

T_MAX_C = 5.0      # 여름 한낮(약 14시) 지표 근처 기온 — JPL REMS 보도 기준 근사치
T_MIN_C = -95.0    # 겨울밤(약 05시) 기온 — JPL REMS 보도 기준 근사치 (최저 -100°C 근접 기록)
T_PEAK_HOUR = 14.0  # 하루 중 최고온 시각(지방시)

T_SAFE_LOW_C = -70.0      # 설계 가정: 이 온도까지는 배터리/액추에이터가 정상 동작한다고 가정
T_CRITICAL_LOW_C = -95.0  # 설계 가정: 이 온도부터 저온 고장 위험이 포화(risk=1)된다고 가정


def diurnal_temperature(hour: np.ndarray | float) -> np.ndarray:
    """1 솔(24.65h을 24h로 근사) 코사인 일교차 모델. hour=0~24, 지방시."""
    t_mean = (T_MAX_C + T_MIN_C) / 2
    t_amp = (T_MAX_C - T_MIN_C) / 2
    phase = 2 * np.pi * (hour - T_PEAK_HOUR) / 24.0
    return t_mean + t_amp * np.cos(phase)


def thermal_risk_from_temp(temp_c: np.ndarray | float) -> np.ndarray:
    span = T_SAFE_LOW_C - T_CRITICAL_LOW_C
    return np.clip((T_SAFE_LOW_C - temp_c) / span, 0, 1)


def thermal_risk(hour: np.ndarray | float) -> np.ndarray:
    return thermal_risk_from_temp(diurnal_temperature(hour))


# ============================================================
# 3. 방사선 모델 — GCR 배경값(문헌) + 지형 차폐 proxy(가정) + SPE 경보(가정)
# ============================================================

D_BACKGROUND_MSV_DAY = 0.655     # Curiosity RAD 관측 평균. 원문 0.64 ± 0.12 mSv/day(Hassler 2014)의 오차 안이라 유지
D_BUDGET_MSV_DAY = 1.0           # 설계 가정: 경보를 띄우는 예시적 "일일 기준선" (공식 한도 아님).
                                  # 참고: NASA 공식 한도는 커리어 600 mSv, SPE 사건당 250 mSv처럼
                                  # 누적치라 "일일 기준선"과 단위가 다름 — 이 값은 그 공식 한도보다
                                  # 훨씬 보수적인 데모용 조기경보 기준일 뿐, 공식 한도의 환산치가 아니다.
SPE_DOSE_MULTIPLIER = 2.9        # 문헌 기반: 2017년 9월 SPE 최고치 수준(Zeitlin 2018, 2~3배). 최고치는 몇 시간 지속이라 귀환 내내 적용하면 보수적
SHIELDING_MAX_REDUCTION = 0.5    # 설계 가정: 지형 차폐가 방사선 위험을 최대 50%까지 줄인다고 가정
SHIELDING_WINDOW_PX = 25         # 차폐 proxy 계산 창(지형 상대고도 평균 — 약 5m 상당)


def shielding_factor_grid(h: np.ndarray) -> np.ndarray:
    """국소 지형이 주변 평균보다 얼마나 낮은지(크레이터/협곡 proxy) -> [0,1] 차폐 정도.

    주의: 실제 방사선 차폐는 '머리 위' 암반 유무가 핵심이며, 이 proxy는 고도차만으로
    근사한 것이라 실제 차폐 효과를 과대/과소평가할 수 있다 — 교육적 근사치임을 명시."""
    from scipy.ndimage import uniform_filter

    local_mean = uniform_filter(h, SHIELDING_WINDOW_PX)
    relative_depth = local_mean - h  # 양수면 주변보다 낮은(둘러싸인) 지형
    depth_scale = np.std(relative_depth) * 2 + 1e-9
    return np.clip(relative_depth / depth_scale, 0, 1)


def radiation_risk(hour: np.ndarray | float, shielding: np.ndarray | float, spe_active: bool) -> np.ndarray:
    dose = D_BACKGROUND_MSV_DAY * (SPE_DOSE_MULTIPLIER if spe_active else 1.0)
    base_risk = np.clip(dose / D_BUDGET_MSV_DAY, 0, 1)
    return base_risk * (1 - SHIELDING_MAX_REDUCTION * shielding)


# ============================================================
# 4. 결합 공식 — 기존 지형 항 + 인체환경 항
# ============================================================

def human_mission_risk(slope_risk, rock_risk, hour, shielding, spe_active,
                        w_terrain=W_TERRAIN, w_human=W_HUMAN, temperature_c=None):
    """temperature_c를 주면 코사인 일교차 모델 대신 그 기온(예: REMS 실측)으로 온도 항을 계산한다."""
    terrain_term = SLOPE_W * slope_risk + ROCK_W * rock_risk
    thermal_term = thermal_risk(hour) if temperature_c is None else thermal_risk_from_temp(temperature_c)
    rad_term = radiation_risk(hour, shielding, spe_active)
    human_term = W_THERMAL * thermal_term + W_RADIATION * rad_term
    return np.clip(w_terrain * terrain_term + w_human * human_term, 0, 1)


def sanity_check_reduces_to_terrain_only(h):
    """W_HUMAN=0, W_TERRAIN=1이면 기존 true_risk_field()와 격자점에서 완전히 일치해야 한다."""
    gx_grid, gy_grid = slope_grids(h)
    slope = np.hypot(gx_grid, gy_grid)
    slope_risk = np.clip(slope / 0.9, 0, 1)
    rock_r = rock_risk_grid(h)

    combined = human_mission_risk(slope_risk, rock_r, hour=0.0, shielding=0.0,
                                   spe_active=False, w_terrain=1.0, w_human=0.0)
    reference = sim.true_risk_field(h)
    max_diff = float(np.max(np.abs(combined - reference)))
    assert max_diff < 1e-9, f"일반화 검증 실패, max_diff={max_diff}"
    print(f"sanity check 통과: W_HUMAN=0일 때 기존 지형 전용 공식과 격자점에서 완전히 일치 "
          f"(max diff={max_diff:.2e})")
    print("  -> 유인 미션 확장 공식은 기존 공식을 깨는 게 아니라 엄밀히 일반화한 것.")


# ============================================================
# 5. 1 솔(24h) 시뮬레이션 — 시간가변 위험도 + 경고 이벤트
# ============================================================

WARNING_THRESHOLD = 0.37   # 설계 가정: 극저온만(0.34) 또는 SPE만(0.21)으로는 넘지 않고,
                            # 두 위험이 겹칠 때만 넘도록 잡은 예시적 경고선 — "단일 요인 감시로는
                            # 못 잡아내고 결합 위험도여야 잡아내는 상황"을 보여주기 위한 선택.
SPE_START_HOUR = 1.0        # 시연용: 가장 위험한 경우(극저온 야간 + SPE 중첩)를 보여주기 위해
SPE_END_HOUR = 4.0          # 일부러 야간 최저온 구간과 겹치게 설정 — SPE는 실제로 지방시와
                            # 무관하게 언제든 발생할 수 있으므로 이는 "최악의 경우" 시연이다.


def run_sol_simulation(h, slope_risk, rock_r, shielding):
    hours = np.arange(0, 24.1, 1.0)
    rows = []
    risk_snapshots = {}
    for hour in hours:
        spe_active = SPE_START_HOUR <= hour < SPE_END_HOUR
        risk_grid = human_mission_risk(slope_risk, rock_r, hour, shielding, spe_active)
        mean_risk = float(risk_grid.mean())
        rows.append({
            "hour": float(hour),
            "temperature_c": float(diurnal_temperature(hour)),
            "thermal_risk": float(thermal_risk(hour)),
            "radiation_risk_mean": float(np.mean(radiation_risk(hour, shielding, spe_active))),
            "spe_active": bool(spe_active),
            "mean_total_risk": mean_risk,
            "warning": bool(mean_risk > WARNING_THRESHOLD),
        })
        if hour in (2.0, 8.0, 14.0):
            risk_snapshots[str(int(hour))] = risk_grid

    warnings = [r for r in rows if r["warning"]]
    return rows, warnings, risk_snapshots


# ============================================================
# 6. 시각화
# ============================================================

def style_ax(ax):
    ax.set_facecolor("#0b0e15")
    for s in ax.spines.values():
        s.set_color("#262d3d")
    ax.tick_params(colors="#a7aec1", labelsize=7)


def plot_results(terrain_only_risk, risk_snapshots, rows):
    fig = plt.figure(figsize=(16, 9.5), facecolor="#0b0e15")
    gs = fig.add_gridspec(2, 3, height_ratios=[1.1, 0.9])

    ax = fig.add_subplot(gs[0, 0]); style_ax(ax)
    im = ax.imshow(terrain_only_risk, cmap=RISK_CMAP, vmin=0, vmax=1, origin="upper")
    ax.set_title(f"Terrain-only risk (time-invariant)\nmean={terrain_only_risk.mean():.3f}",
                 color="#e9ebf2", fontsize=9.5)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)

    labels = {"2": "02:00 (extreme cold + SPE overlap -- WARNING)",
              "8": "08:00 (SPE ended, still cold)",
              "14": "14:00 (midday, no SPE)"}
    for i, key in enumerate(["2", "8", "14"]):
        ax = fig.add_subplot(gs[0, 1] if i == 0 else gs[0, 2] if i == 1 else gs[1, 0])
        style_ax(ax)
        grid = risk_snapshots[key]
        im = ax.imshow(grid, cmap=RISK_CMAP, vmin=0, vmax=1, origin="upper")
        ax.set_title(f"{labels[key]}\nmean={grid.mean():.3f}", color="#e9ebf2", fontsize=9)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)

    ax = fig.add_subplot(gs[1, 1:]); style_ax(ax)
    hours = [r["hour"] for r in rows]
    ax.plot(hours, [r["thermal_risk"] for r in rows], color="#5cbcc3", label="thermal_risk(t)", linewidth=1.6)
    ax.plot(hours, [r["radiation_risk_mean"] for r in rows], color="#e08a76", label="radiation_risk(t)", linewidth=1.6)
    ax.plot(hours, [r["mean_total_risk"] for r in rows], color="#e0ac53", label="mean_total_risk(t)", linewidth=2.2)
    ax.axhline(WARNING_THRESHOLD, color="#ffffff", linestyle="--", linewidth=1, alpha=0.6, label=f"warning threshold={WARNING_THRESHOLD}")
    ax.axvspan(SPE_START_HOUR, SPE_END_HOUR, color="#e08a76", alpha=0.12, label="SPE window")
    for r in rows:
        if r["warning"]:
            ax.scatter([r["hour"]], [r["mean_total_risk"]], color="#ffffff", s=22, zorder=5)
    ax.set_xlabel("local hour", color="#a7aec1", fontsize=8)
    ax.set_ylabel("risk", color="#a7aec1", fontsize=8)
    ax.set_title("1-sol (24h) time-varying risk -- temperature, radiation, warning events", color="#e9ebf2", fontsize=10)
    ax.legend(facecolor="#141926", edgecolor="#262d3d", labelcolor="#e9ebf2", fontsize=7.5, loc="upper right")
    ax.set_ylim(-0.05, 1.05)

    fig.suptitle("Human-mission extended risk -- terrain (slope+roughness) + temperature + radiation (background GCR + SPE alert)",
                 color="#a7aec1", fontsize=11)
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/human_mission_risk.png", dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"saved {OUT_DIR}/human_mission_risk.png")


# ============================================================
# 7. 실행
# ============================================================

def main():
    print("=== 유인 미션 확장 위험도 공식 — 지형 + 온도 + 방사선 ===\n")

    sim.rng = np.random.default_rng(0)
    h, _ = sim.generate_terrain()

    sanity_check_reduces_to_terrain_only(h)
    print()

    gx_grid, gy_grid = slope_grids(h)
    slope = np.hypot(gx_grid, gy_grid)
    slope_risk = np.clip(slope / 0.9, 0, 1)
    rock_r = rock_risk_grid(h)
    shielding = shielding_factor_grid(h)
    terrain_only = sim.true_risk_field(h)

    rows, warnings, risk_snapshots = run_sol_simulation(h, slope_risk, rock_r, shielding)

    print(f"지형 전용 평균 위험도: {terrain_only.mean():.3f}")
    print(f"{'시각':>6} {'온도(C)':>9} {'thermal':>8} {'radiation':>10} {'SPE':>5} {'total':>7} {'경고':>5}")
    for r in rows:
        print(f"{r['hour']:>6.0f} {r['temperature_c']:>9.1f} {r['thermal_risk']:>8.3f} "
              f"{r['radiation_risk_mean']:>10.3f} {str(r['spe_active']):>5} {r['mean_total_risk']:>7.3f} "
              f"{'WARN' if r['warning'] else '':>5}")

    print(f"\n경고 임계값({WARNING_THRESHOLD}) 초과 시각: {len(warnings)}개 / {len(rows)}개")
    if warnings:
        print("  -> " + ", ".join(f"{w['hour']:.0f}시" for w in warnings))

    stats = {
        "model_params": {
            "literature_based": {
                "radiation_background_mSv_day": D_BACKGROUND_MSV_DAY,
                "spe_dose_multiplier": SPE_DOSE_MULTIPLIER,
                "diurnal_temp_range_c": [T_MIN_C, T_MAX_C],
                "sources": [
                    "Hassler et al. 2014, Science (RAD Mars surface radiation)",
                    "SwRI press release on first Mars surface radiation measurements",
                    "csmonitor.com 2013-12-09 Curiosity radiation report",
                    "JPL REMS diurnal temperature public summaries",
                ],
            },
            "design_assumptions": {
                "T_SAFE_LOW_C": T_SAFE_LOW_C,
                "T_CRITICAL_LOW_C": T_CRITICAL_LOW_C,
                "D_BUDGET_MSV_DAY": D_BUDGET_MSV_DAY,
                "SHIELDING_MAX_REDUCTION": SHIELDING_MAX_REDUCTION,
                "W_TERRAIN": W_TERRAIN, "W_HUMAN": W_HUMAN,
                "W_THERMAL": W_THERMAL, "W_RADIATION": W_RADIATION,
                "WARNING_THRESHOLD": WARNING_THRESHOLD,
            },
        },
        "terrain_only_mean_risk": float(terrain_only.mean()),
        "hourly": rows,
        "n_warnings": len(warnings),
        "warning_hours": [w["hour"] for w in warnings],
    }
    with open(f"{OUT_DIR}/human_mission_risk_stats.json", "w") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    print(f"\nsaved {OUT_DIR}/human_mission_risk_stats.json")

    plot_results(terrain_only, risk_snapshots, rows)


if __name__ == "__main__":
    main()
