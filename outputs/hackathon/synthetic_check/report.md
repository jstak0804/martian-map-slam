# 해커톤 데이터 학습·보정 보고서: synthetic_check

> **가짜(synthetic) 데이터입니다.** 파이프라인 점검용이며 보정값은 활성화할 수 없습니다.

- 데이터: `../data/hackathon_synthetic` (파일 54개, 접수 보고서: `intake_report.md`)
- 돌린 단계: metabolic, dose, dem:site_dem.tif, segmentation

## 주의

- metabolic.speed_model: 평지 속도 1.30 m/s: 지구에서 우주복 없이 걸은 자료로 보입니다. 화성 EVA(문헌 0.75 m/s)에 그대로 쓰지 말고 감소율 c만 참고하세요.

## 보정 제안 vs 지금 값(문헌)

| 항목 | 값 | 지금(문헌) | 근거 |
|---|---|---|---|
| hr_to_mr.a_btu_h | -304 | 285 | 해커톤 자료 회귀 (synthetic_check, n=300, R²=1.00, CV RMSE 7 W) |
| hr_to_mr.b_btu_h_per_bpm | 16 | 5.98 | 해커톤 자료 회귀 (synthetic_check, n=300, R²=1.00, CV RMSE 7 W) |
| eta_surface_add.value | 0.194 | 0.2 | 해커톤 자료 단단한 지면 η 중앙값 1.19 (regolith, rock field, n=50) |
| eta_sand.a | 1.65 | 1.5 | 해커톤 자료 모래 η = a + b/V² 회귀 (n=120, R²=0.54) |
| eta_sand.b | 1.14 | 1.3 | 해커톤 자료 모래 η = a + b/V² 회귀 (n=120, R²=0.54) |
| eta_sand.v_floor_m_s | 0.9 | 0.85 | 해커톤 자료 모래 η = a + b/V² 회귀 (n=120, R²=0.54) |
| speed_model.v0_m_s | 1.3 | 0.75 | 해커톤 자료 자율 보행 속도 회귀 (n=229, R²=0.23) — 주의: 지구·비가압 자료로 보임 |
| speed_model.c_m_s_per_pct | 0.0195 | 0.01 | 해커톤 자료 자율 보행 속도 회귀 (n=229, R²=0.23) — 주의: 지구·비가압 자료로 보임 |
| speed_model.v_min_m_s | 1.17 | 0.3 | 해커톤 자료 자율 보행 속도 회귀 (n=229, R²=0.23) — 주의: 지구·비가압 자료로 보임 |
| dose.bg_msv_day | 0.664 | 0.655 | 해커톤 선량 자료 중앙값 (synthetic_check, n=240, Q=3.05), SPE 1건 최대 x4.2 |
| dose.spe_observed | 4.24 | 2.9 | 해커톤 선량 자료 중앙값 (synthetic_check, n=240, Q=3.05), SPE 1건 최대 x4.2 |

## 정답 대조 (가짜 데이터)

| 항목 | 정답 | 추정 |
|---|---|---|
| HR 회귀 a (BTU/h) | -300 | -304 |
| HR 회귀 b | 16 | 16 |
| 단단한 지면 η − 1 (regolith·rock 중앙값) | (η 1.15·1.40 섞임) | 0.194 |
| 모래 a | 1.8 | 1.65 |
| 모래 b | 1 | 1.14 |
| 속도 v0 | 1.3 | 1.3 |
| 속도 c | 0.015 | 0.0195 |
| 배경 선량 mSv/day | 0.659 | 0.664 |
| SPE 최대 배율 | 4 | 4.24 |

## 지형 분할 미세조정

- 시작 가중치: small_unet_best.pt, 분할 {'train': 18, 'val': 3, 'test': 3}
- 시험 mIoU: 전 0.179 → 후 0.712
- 클래스별 IoU(후): soil 0.873, bedrock 0.652, sand 0.876, big_rock 0.447

## 새 지형 귀환 반경

- `site_dem.tif`: 600x600 칸 @ 10.0 m, 기복 378 m, 산소 150 g → 33.53 km², 산소 300 g → 35.99 km², 산소 450 g → 35.99 km²

## 다음 할 일

1. `intake_report.md`에서 열 역할 추정이 맞는지 확인. 틀리면 데이터 폴더에 `columns.json`을 두고 다시 실행.
2. 위 표와 각 폴더의 그림(`metabolic/metabolic_calibration.png` 등)을 보고 받아들일 항목만 고르기.
3. `python -m hackathon.params --activate ../outputs/hackathon/synthetic_check/params_proposed.json --only <항목>`
4. `python build_demo_data.py && python build_demo_html.py` → 데모의 왼쪽 "대사량 모델 보정"과 심박 회귀식에 반영됨.
5. 지형 분할 가중치는 `segmentation/small_unet_finetuned.pt`. 새 지형 귀환 반경은 `dem_walkback/`.
