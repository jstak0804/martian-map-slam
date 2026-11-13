# walkback_verification: EVA 귀환 반경 모델 재검증 자료

이 폴더는 Gale EVA 귀환 반경 모델을 다시 검증하면서 만든 코드, 계산 결과, 기록을 모은 것입니다. `CHANGELOG.md`에 적힌 수치를 직접 확인하고 다시 계산할 수 있도록 근거 파일을 함께 넣었습니다.

- **저장소의 기존 파일은 바꾸지 않았습니다.** 저장소 루트의 `code/`, `reports/`, 데모는 그대로입니다. 이 폴더는 따로 돌아가는 사본입니다.
- 이 폴더의 코드를 저장소 기본 모델로 합칠지는 팀이 정할 일입니다(`CHANGELOG.md` 19절 참고).
- 작성: 2026-11-14 기준. 기록 문서는 한국어입니다.

## codeowner 요청 파일
| 파일 | 위치 | 내용 |
|---|---|---|
| `metabolic_model.py` | `code/metabolic_model.py` | 보행 대사 모델(IST 실측 기반), 경사별 속도, 내리막 비용, 예비분 정의 |
| `ist_model_coefs.json` | `code/data/ist_model_coefs.json` | NASA IST-1·IST-2 그림을 PDF 벡터에서 읽어 회귀한 계수. 만든 방법은 `recalc/digitize_ist.py`, 확인 그림은 `recalc/outputs_b/b_digitize_check_*.png`, 원 그림 잘라낸 것은 `recalc/references/IST*.png` |

## 저장소 원본과의 관계
- 저장소 루트 `code/`의 귀환 모델 파일(`metabolic_navigation.py`, `mars_walkback.py`, `spe_walkback.py`, `suit_cooling.py`, `comm_los.py`, `fall_risk_map.py`, `heart_rate_o2.py` 등)이 이 작업의 출발점입니다(재검증 전 원본).
- 이 폴더 `code/`에서 원본과 달라진 파일:
  - 새 파일: `metabolic_model.py`
  - 수정: `metabolic_navigation.py`, `mars_walkback.py`, `spe_walkback.py`, `suit_cooling.py`, `comm_los.py`, `coolant_walkback.py`, `heart_rate_o2.py`, `human_mission_risk.py`, `build_demo_data.py`, `build_demo_html.py`, `demo_template.html`
  - 무엇을 왜 바꿨는지는 `CHANGELOG.md` 10.2절(코드 변경)과 이후 각 절에 있습니다.
- 두 쪽의 모델·변수·가정·알고리즘 차이: `CHANGELOG.md` 19절

## 폴더 구성
```
walkback_verification/
├── CHANGELOG.md            검증·수정 기록 전체 (근거 표시: [확인] [계산] [추론] [미확인])
├── code/                   재검증 후 코드 (기본 모델 = IST 실측, 경보 k × 1.2 등)
│   └── data/               ist_model_coefs.json, sand_zones.json(모래 추정 구역)
├── tests/                  pytest 23개 (빠른 18 + 느린 5)
├── recalc/                 재계산·분석 스크립트, 계획(PLAN_*.md), 조사 노트, 결과(outputs_*)
│   ├── research/           조사 노트 T1~T5, BRIEF
│   └── references/         NASA IST-1·2 보고서에서 잘라낸 그림(수치 읽기 근거)
├── demo/                   재검증 후 데모(HTML 1개), 데모 README, 발표용 한계 한 장(LIMITS.md)
├── outputs/                데모 데이터(demo_meta.json, demo_data.bin.gz), 귀환 통계 JSON
├── data/                   Curiosity 주행 경로(MMGIS), HiRISE 라벨 파일
└── requirements-verification.txt
```

## CHANGELOG 수치 → 근거 파일
| CHANGELOG 절 | 내용 | 스크립트 | 결과 파일 |
|---|---|---|---|
| 1 | 원본 수치 재현(18.64 km² 등) | `recalc/k_scenarios.py`, `tests/test_slow.py::test_legacy_reproduces_original` | `recalc/RESULTS.md` |
| 2.2 | 안 A: Pandolf × k 감도 | `recalc/k_scenarios.py` | `recalc/RESULTS.md` |
| 2.3 | 안 B: IST-1·2 실측 모델, 계수 | `recalc/digitize_ist.py`, `recalc/model_b.py` | `code/data/ist_model_coefs.json`, `recalc/outputs_b/`, `recalc/RESULTS_B.md` |
| 3 | 예비분·누설·비상 여유(Apollo·ISS 원문) | — | `recalc/RESEARCH.md` |
| 5 | 심박·냉각수 민감도 | `recalc/sensitivity_hr_water.py` | `recalc/RESULTS_B.md` 8절 |
| 8 | 실시간 대사량 측정 조사 | — | `recalc/RESEARCH_SENSING.md`, `recalc/research/T1~T3` |
| 10.3~10.5 | 계획 C 반영 검증, 내리막 | `recalc/plan_c_checks.py`, `recalc/js_parity.py` | `recalc/outputs_c/plan_c_checks.json`, `recalc/outputs_c/js_parity.json` |
| 10.4 | 현재 모델 면적 9.72 km² | `code/mars_walkback.py`, `tests/test_slow.py::test_current_default` | `outputs/mars_walkback/walkback_stats.json` |
| 11.1 | 추가 점검(계획 D) | `recalc/e_quick_checks.py` 등 | `recalc/outputs_c/`, `recalc/outputs_e/` |
| 13 | 추가 검증 1~10(해상도, 개인차, 냉각수, A* 등) | `recalc/e1_resolution.py`, `e2_individual.py`, `e3_feedwater.py`, `e_quick_checks.py`, `e10_shift_impact.py` | `recalc/outputs_e/*.json` |
| 13.4 | η 민감도 | `recalc/f_eta_sensitivity.py` | `recalc/outputs_f/f_eta_sensitivity.json` |
| 14 | 몬테카를로 불확실성 결합 | `recalc/g_uncertainty.py` | `recalc/outputs_g/g_uncertainty.json`, `g_safe_probability.png` |
| 15.5 | 경사 상한·η 바닥값·모래 민감도 | `recalc/h_sensitivity.py` | `recalc/outputs_h/h_sensitivity*.json` |
| 15.6 | 모래 시나리오 | `code/mars_walkback.py`(`sand_mask`), `code/data/sand_zones.json` | `recalc/outputs_c/js_parity.json`(모래 사례) |
| 15.7 | 데모 병합, 시뮬레이션 시간 단위 | `recalc/h1_sim_check.py`, `recalc/h1_demo_harness.mjs` | `recalc/outputs_h/h1_sim_check.json`, `h1_readme_numbers.json` |
| 15.9 | η 바닥값을 몬테카를로에 추가 | `recalc/h5_uncertainty_floor.py` | `recalc/outputs_h/h5_uncertainty_floor.json` |
| 16.3 | 경보 규칙 스윕(1,200회) | `recalc/i3_alarm_sweep.py` | `recalc/outputs_i/i3_alarm_sweep.json` |
| 16.4 | 냉각수 추가 열 | `recalc/i4_extra_heat.py` | `recalc/outputs_i/i4_extra_heat.json` |
| 16.5 / 17.5~17.7 | 모래 반경, 질량, 상관, 남은 가정 | `recalc/h_sensitivity.py --sand-radius`, `j6_mass.py`, `j7_correlation.py`, `j8_assumptions.py` | `recalc/outputs_i/i5_*`, `recalc/outputs_j/j6~j8_*.json` |
| 16.6 | Apollo 14 한 점 점검 | `recalc/i6_apollo14.py` | `recalc/outputs_i/i6_apollo14.json` |
| 17.4 | 예비분 정의(비행 규칙)·추가 열 원문 | — | `recalc/j5_reserve_heat.md` |
| 17.9 | 보행용 심박–대사량 조사 | — | `recalc/j11_hr_walking.md` |
| 17.11 | 산소 최소 단일 경로 가정 | `recalc/j14_single_path.py` | `recalc/outputs_j/j14_single_path.json` |
| 17.12 | 경보 규칙 비교(4,000회) | `recalc/j9_alarm.py` | `recalc/outputs_j/j9_alarm.json` |
| 18.2 | 지형·내리막(Kim 2023, Richmond, Minetti) | `recalc/k2_terrain.py` | `recalc/outputs_k/k2_terrain.json` |
| 18.3 | 생리 지연·k 추정기(6,800회) | `recalc/k3_estimator.py` | `recalc/outputs_k/k3_estimator.json` |
| 18.5 | 현재 데모 예시 수치(경보 k × 1.2) | `recalc/h1_demo_harness.mjs` + `recalc/outputs_h/h1_readme_jobs.json` | `recalc/outputs_k/k4_readme_numbers.json`, `tests/test_slow.py::test_demo_examples` |

- 각 계획의 설계와 결정은 `recalc/PLAN.md`, `PLAN_B.md` ~ `PLAN_K.md`에 있습니다.
- 경로 탐색 알고리즘 선택 근거(다익스트라 vs A* 등)는 `recalc/research/T5_path_planning.md`에 있습니다.

## 다시 돌리는 법
환경: Python 3.10, `requirements-verification.txt`(numpy 2.0.2, scipy 1.13.1, matplotlib 3.9.4, pillow 11.3.0, pytest 9.2.0), node 18 이상(데모 검사용)

```bash
cd walkback_verification
python -m venv .venv && .venv/bin/pip install -r requirements-verification.txt

# 1) DTM 없이 바로 되는 것
.venv/bin/python -m pytest tests -m "not slow"                               # 빠른 테스트 18개
.venv/bin/python -m pytest tests -k "demo_examples or js_parity or sim_track"   # 데모 예시·Python–JS 일치·시뮬레이션 경로 (node 필요)

# 2) DTM이 필요한 것: HiRISE DTM(약 425 MB)을 data/hirise_dtm/에 넣은 뒤
#    받을 곳: https://hirise-pds.lpl.arizona.edu/PDS/DTM/ESP/ORB_018800_018899/ESP_018854_1755_ESP_018920_1755/
#    (DTEEC_018854_1755_018920_1755_U01.IMG)
.venv/bin/python -m pytest tests                                              # 전체 23개
cd code && ../.venv/bin/python ../recalc/<스크립트>.py                         # 각 분석 (스크립트 머리말에 실행법)
```

- 스크립트는 `code/`에서 실행하는 것을 기준으로 상대 경로를 씁니다.
- 셸에 ROS 등이 `PYTHONPATH`를 설정해 두었다면 pytest 플러그인이 섞일 수 있습니다. `env -u PYTHONPATH`로 실행하세요.
- 몬테카를로 캐시(`recalc/outputs_g/cache_*.npz`, `outputs_h/cache_*.npz`, 각 약 18 MB)는 올리지 않았습니다. 스크립트가 처음 실행할 때 다시 만듭니다.

## 넣지 않은 것과 이유
- **HiRISE DTM·정사영상**(용량 큼): 위 주소에서 받으세요. 저장소 `.gitignore` 방침과 같습니다.
- **학술지 논문 PDF와 추출 텍스트**(저작권): 아래 출처 목록으로 대신합니다.
- **대량 스윕의 원시 결과·작업 목록**(`*_raw.json`, `*_jobs.json`, 수십 MB): 해당 스크립트가 다시 만듭니다. 요약 결과(JSON)는 들어 있습니다.
- 로컬 경로가 들어 있던 문서·로그는 이 사본에서만 상대 경로로 바꿨습니다.

## 주요 출처
NASA·미국 정부 자료는 공개 자료입니다. 학술지 논문은 서지 정보만 적습니다.
- NASA/TP-2010-216115 (IST-1, 평지), NASA/TP-2010-216125 (IST-2, 경사), NASA/TP-2009-214796 (EVA Walkback Test)
- Apollo 15 Bellcomm 메모 B70 10028 (NTRS 19790073512): 30분 예비분, 누설률, 비상 귀환 대사율 +20%
- ISS EVA Console Handbook EMU Ops, JSC-20597 Vol.4 Rev.B: 비행 규칙상 30분 예비분 보호, 급수 수명
- Waligora & Horrigan 1975, "Metabolic cost of extravehicular activities" (NASA SP-368): Apollo 14 보행 2.4 km/h, 300 kcal/h
- Apollo 14 Mission Report MSC-04112 (1971), 10절
- Hoffmann et al. 2021 (NTRS 20210024317): 심박 → 대사량 회귀식
- Kim et al. 2025, ICES-2025-129 (NTRS 20250001829): CSRM 경로 모델, ±20° 통행 불가
- Kim et al. 2023, Physiol Meas 44:104001, doi:10.1088/1361-6579/acf993: Rock Yard 지형별 대사량
- Richmond, Potter & Santee 2015, J Sport Hum Perf 3(3):1-26, doi:10.12922/jshp.0067.2015: 지형계수 η
- Looney et al. 2019, Med Sci Sports Exerc 51:1954: LCDA 경사 보행식
- Minetti et al. 2002, J Appl Physiol 93:1039: 경사별 보행 비용
- Campbell et al. 2019, Applied Geography 106:93: Tobler 보행 함수 확인
- Hassler et al. 2014, Science: Curiosity RAD 표면 선량
- Paul 2012 (NTRS 20120003917): Apollo 에너지 소비, 심박 단독 예측의 한계
- Ogilvie et al., ICES-2026-126: 화성 PLSS
