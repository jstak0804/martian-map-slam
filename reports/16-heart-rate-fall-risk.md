# 16. 심박으로 보정하는 귀환 반경과 넘어짐 위험지도

2026-11-03 · 지형: HiRISE DTM (Gale, 1 m) · 심박-대사량: NASA 셔틀·ISS EVA 132회 (Hoffmann 2021)
웹 버전: `reports/16-heart-rate-fall-risk.html` (원격 열람용 `16-heart-rate-fall-risk.standalone.html`)

## 요약
- 모델보다 산소를 20% 더 쓰는 사람(k = 1.2)은 같은 산소 150 g으로도 귀환 가능 면적이 18.6 → 13.3 km²(−29%)로 줄어든다. 관측된 크기의 SPE보다 훨씬 큰 변수다.
- 심박으로 k를 추정하는 시연에서는 대사량이 25% 뛴 뒤 약 6분 만에 ±0.1 안으로 들어왔다(10분 이동창). 이 시연의 심박은 합성값이다.
- 넘어짐 위험 "높음" 칸 5.0 km² 중 94%는 10 m 평균 경사 검사를 통과한다. 10 m 계획만으로는 이 위험을 못 본다.
- 높음·중간 칸을 모두 피해도 산소는 +3 g(+1.5%), 거리는 +0.2 km밖에 늘지 않는다.

## 1. 심박 → 대사량 → 산소 (`code/heart_rate_o2.py`)
`대사량(BTU/h) = 284.55 + 5.984 × 심박(bpm)`. 출처는 Hoffmann 2021 표 5.1(8쪽)이다.
- 설명력: 전체 R² 0.402, 개인별 R² > 0.82
- 개인별 예측 오차: 대사량 RMSE 89.66 ± 44.24 BTU/h, 심박 RMSE < 10 bpm
- 측정 방법: 대사량은 PLSS 산소탱크 압력이 줄어드는 속도로 2분마다, 심박은 심전도로 20초마다 쟀다.

환산 결과: 화성 평지 보행(301 W, 77 g/h)은 심박 124 bpm에 해당한다. 셔틀·ISS EVA 평균 103 bpm은 264 W, 68 g/h다.

**주의**
- 무중력 EVA 자료를 화성 0.38 g 보행에 그대로 썼다. 검증되지 않은 가정이다.
- 개인별 보정 없이 전체 회귀만 쓰면 오차가 크다.

## 2. 경로 예상 심박과 보정계수 k
- 계산식: `k = 지난 10분 심박으로 구한 대사량 ÷ 같은 구간의 Pandolf 예측값`
- 판정: `k × 귀환 산소 ≤ 남은 산소 − 예비분`이면 귀환 가능
- 착륙지 → sol 1282 경로의 1분 평균 예상 심박은 갈 때 152 bpm, 올 때 140 bpm이다.
- 원 자료 범위(~1400 BTU/h)를 넘는 외삽 구간은 갈 때 15분, 올 때 5분이다. 속도를 고정했기 때문에 생긴 봉우리다.

## 3. k별 귀환 가능 면적 (남은 산소 150 g)
| k | 0.8 | 0.9 | 1.0 | 1.1 | 1.2 | 1.3 | 1.4 | 1.5 |
|---|---|---|---|---|---|---|---|---|
| km² | 28.3 | 22.8 | 18.6 | 15.6 | 13.3 | 11.5 | 10.0 | 8.9 |

## 4. 넘어짐·장애물 위험지도 (`code/fall_risk_map.py`)
- 위험 화소(1 m): 3 m 안 높이차 ≥ 0.5 m, 또는 1 m 경사 ≥ 20°
- 칸(10 m) 등급: 위험 화소 비율 ≥ 25%면 높음(통행 금지), ≥ 5%면 중간
- 기준값은 모두 가정이다. 0.5 m는 DTM 수직 정밀도(약 0.2~0.25 m)의 2배이고, 노인 낙상 연구의 15.2 cm보다 3배 크다.
- 결과(지도 42.7 km²): 높음 5.0 km², 중간 3.8 km². 위험 화소 중 턱은 8.5%, 1 m 급사면은 1.5%다.

## 5. 경로와 귀환 반경에 반영
| 착륙지 → sol 1282 | 거리 | 산소 | 중간 칸 통과 | 높음 칸 통과 |
|---|---|---|---|---|
| 산소만 고려 | 7.26 km | 196 g | 610 m | 353 m |
| 높음 칸 금지 | 7.43 km | 197 g | 477 m | 0 |
| 높음 금지 + 중간 회피 (비용 ×2) | 7.47 km | 199 g | 0 | 0 |

높음 칸을 금지하면 귀환 가능 면적은 18.6 → 17.3 km²가 된다. 잃은 면적은 대부분 높음 칸 자체이고, 막혀서 새로 못 돌아오게 된 곳은 0.15 km²다.

## 6. 지형 데이터로 볼 수 없는 것
- **2~15 cm 걸림:** DTM 오차보다 작아서 안 보인다. 헬멧·로버 카메라와 AI4Mars 분할 모델이 필요하다.
- **푹 꺼지는 땅(Spirit, Troy 2009):** 표면 높이로는 구분할 수 없다. 열관성 같은 물성 자료가 필요하다.
- **바이저 시야:** 반영하지 않았다.
- **xEMU 계단 높이 시험(ICES 2025):** 최종값을 확인해야 한다.

## 출처
- Hoffmann 2021, EVA Metabolic Rate Estimated from Heart Rate: https://ntrs.nasa.gov/citations/20210024317
- Waligora et al., Apollo Assessment of Metabolic Expenditures (TN D-7883): https://www.nasa.gov/wp-content/uploads/static/history/alsj/tnD7883Metabolic.pdf
- Apollo 15 시간·동작 분석: https://ntrs.nasa.gov/citations/19730008096
- Apollo 16 시간·동작 분석: https://ntrs.nasa.gov/api/citations/19730008098/downloads/19730008098.pdf
- NASA ICES 2025 xEMU 계단 높이: https://ntrs.nasa.gov/citations/20250004496
- 노인 장애물 넘기: https://pmc.ncbi.nlm.nih.gov/articles/PMC4905923
- CDC/NIOSH 걸림 확률: https://stacks.cdc.gov/view/cdc/216641
- HiRISE DTM 정밀도: https://www.uahirise.org/dtm/about.php
- Spirit, Troy (JPL): https://www.jpl.nasa.gov/news/mars-rover-yielding-new-clues-while-lodged-in-martian-soil/
