# 계획 C: 원본 코드·데모 HTML에 재검증 결과 반영

상태: **구현 완료(2026-11-12). 내리막 보정(C1) 포함.** 검증·수정 기록: `walkback_verification/CHANGELOG.md` · 근거: RESEARCH.md, RESULTS.md, RESULTS_B.md, RESEARCH_SENSING.md

## 1. 범위
사용자가 정한 수정 항목(1·2·4·5)을 원본 `code/`와 데모 HTML에 반영한다. 반영한 내용과 그 근거는 `walkback_verification/CHANGELOG.md`에 자세히 정리한다.

| 번호 | 수정 | 원본에서 바뀌는 곳 |
|---|---|---|
| 1 | Pandolf 중력 배율 모델 → IST-1·IST-2 실측 모델(안 B) | 대사량을 쓰는 모든 스크립트, 데모 JS의 간선 비용 |
| 2 | PLSS 방식(폐루프 / 개루프) | **사용자 지침 대기.** 지침을 받으면 이 계획에 덧붙인다 |
| 4 | 8방향 격자 → 16방향 격자(거리 과대 최대 약 8% → 약 3%) | `mars_walkback.OFFSETS`, 그래프 생성, 데모 JS의 이웃·경로 인코딩 |
| 5 | 내리막 비용 = 평지 → 문헌 기반 내리막 보정 | 대사 모델 함수, 데모 JS |

## 2. 설계

### 2.1 대사 모델을 한 곳에 모은다
- 새 모듈 `code/metabolic_model.py`
  - `MODEL = "ist_b"`(기본) 또는 `"pandolf_legacy"`(이전 결과 재현용)
  - `metabolic_rate_w(grade_pct, eta, v)` 하나로 모든 호출을 받는다. 시그니처는 기존 `metabolic_navigation.metabolic_rate_w`와 호환되게 한다.
  - IST 계수(평지·오르막 2차식의 TGAW 선형 계수)는 `recalc/outputs_b/b_digitized.json`에서 산출해 `code/data/ist_model_coefs.json`으로 고정 저장한다. 원본 패키지가 recalc에 의존하지 않게 하기 위해서다.
- `metabolic_navigation.metabolic_rate_w`는 위 모듈로 위임한다. 기존 호출부(mars_walkback, spe_walkback, suit_cooling, heart_rate_o2, fall_risk_map, comm_los, coolant_walkback, build_demo_data)는 고치지 않거나 최소한만 고친다.
- `LEVEL_MR_W`, `LEVEL_O2_G_PER_H`, `O2_RESERVE_G`(예비분) 같은 파생 상수는 모델에서 계산된 값을 따른다.
  - 예비분: 1200 BTU/h(352 W) 30분치 고정(산소 45.0 g, 냉각수 256 g). 결정 D6.

### 2.2 16방향 격자
- 이웃: 기존 8개 + (±1, ±2), (±2, ±1) 8개
- 16방향 간선은 두 칸을 걸쳐 지나가므로, **걸치는 중간 두 칸이 모두 통행 가능할 때만** 허용한다(벽 뚫기 방지).
- 경사는 간선 양 끝 고도차 ÷ 간선 길이(√5 × 10 m)로 계산한다. 기존 방식과 같다.
- 데모 데이터의 `pred`(다음 칸 방향 번호, uint8)를 0~15로 확장하고 255 = 갈 수 없음, 16 = 거점으로 바꾼다. JS 디코딩도 같이 고친다.

### 2.3 내리막 보정 (구현 전 근거 확인 단계 포함)
- IST·Kluis 실측에는 내리막 데이터가 없다. 그래서 문헌 식을 확인한 뒤 적용해야 한다.
- 후보(원문 확인 전이라 모두 [미확인]):
  - Santee 2001 내리막 보정항(Pandolf 계열, 군 하중 보행)
  - Looney 2019 LCDA 경사 보행식(메타회귀, 내리막 포함)
  - Minetti 2002 경사별 보행 비용 곡선(−45 ~ +45%)
- 적용 방식(후보): 지구 1 g 식에서 "내리막 비용 ÷ 평지 비용" 비율 곡선을 얻어 안 B 평지 비용에 곱한다. 0.38 g·우주복으로 옮기는 것은 가정이며 결과에 [가정]으로 표시한다.
- 원문을 열 수 없으면(유료) 사용자에게 PDF를 요청한다. 근거가 확인되지 않으면 기존 가정(내리막 = 평지)을 유지하고 그 사실을 기록한다.

### 2.4 데모 HTML (`code/demo_template.html` → 빌드 → `demo/gale-eva-walkback-demo.html`)
- JS `edgeO2`: Pandolf 식을 안 B 식으로 바꾼다. 계수는 `META`로 전달한다.
- 이웃 8 → 16, 중간 칸 통행 검사 추가
- 예비분, 냉각수 예비분, 설명 문구(산소 모델, 39 g → 57 g 등) 수정
- 구조 모드의 "서 있는 대사량 222 W(Pandolf)"는 결정 D3
- `build_demo_data.py` → `build_demo_basemap.py` → `build_demo_html.py`를 다시 실행한다. 출력 경로 문제(`../reports/18-...`)는 기존처럼 두고 `demo/`로 복사한다.

### 2.5 재생성
- `outputs/`(그림·JSON) 재생성: spe_walkback, comm_los, heart_rate_o2, fall_risk_map, coolant_walkback, mars_walkback
- `figures/` 10장 갱신
- `README.md`의 "주요 결과" 표 갱신

## 3. 파일
- 새로 만듦: `code/metabolic_model.py`, `code/data/ist_model_coefs.json`, `recalc/plan_c_checks.py`(검증 스크립트), `walkback_verification/CHANGELOG.md`
- 수정: `code/metabolic_navigation.py`, `code/mars_walkback.py`(OFFSETS, build_o2_graph), `code/spe_walkback.py`(build_graph/edge_values의 이웃), 16방향 영향을 받는 나머지 그래프 생성 코드, `code/build_demo_data.py`, `code/demo_template.html`, `README.md`
- 재생성: `outputs/`, `figures/`, `demo/gale-eva-walkback-demo.html`
- 수정 전에 원본 전체를 `recalc/backup_original/`에 복사해 둔다(되돌리기용).

## 4. 검증
1. **이전 결과 재현:** `MODEL="pandolf_legacy"` + 8방향이면 기존 수치(18.643 km², 7.26 km, 196 / 184 g, 냉각수 0.6 kg 7.383 km²)가 그대로 나온다.
2. **안 B 재현:** `MODEL="ist_b"` + 8방향 + 내리막 = 평지이면 `recalc/model_b.py`의 90 kg ㄱ 결과(7.32 km², 444 W 예비분)와 같다.
3. **16방향 평지 검산:** 합성 평지에서 면적이 원 넓이에 얼마나 가까운지 확인한다(8방향 90% → 16방향 약 95% 이상 기대). 벽 뚫기가 없는지 확인한다(얇은 통행 불가 선을 넘지 않음).
4. **내리막 보정:** 경사 0에서 평지 비용과 같고, 연속이다.
5. **Python–JS 일치:** node(v12 설치 확인)로 데모 JS의 다익스트라를 Python 결과와 표본 지점 20곳에서 비교한다(상대 오차 < 0.1%).
6. **데모 동작:** 빌드한 HTML을 node로 문법 검사하고, 주요 수치(기준 면적, 예비분 표시)가 Python과 맞는지 확인한다.

## 5. 가정과 트레이드오프
- 16방향도 완전한 연속 거리는 아니다(약 3% 과대 남음). fast marching은 더 정확하지만 JS 구현이 크고 비대칭 비용(오르막·내리막)을 다루기 복잡하다.
- 안 B는 MKIII 121 kg, 0.32 g 지상 모사 자료다(RESULTS_B 9절의 한계 그대로).
- 보고서 15~17 본문 수치는 이전 모델 결과다. 처리 방식은 결정 D4.

## 6. 결정 (2026-11-10)
- **D1 PLSS 방식: 폐루프 유지.** 이유: ISS EMU(LiOH/METOX)와 xEMU/xPLSS(RCA)가 폐루프이거나 폐루프에 가깝다. 개루프·반개루프(화성 PLSS 후보)와 RCA 베드 배기 손실은 CHANGES_VALIDATION.md의 한계 항목에 기록한다.
- **D2 내리막:** 근거 확인 단계(2.3절)부터 진행한다.
- **D3 구조 모드 정지 대사량:** Pandolf 222 W를 유지하고 한계로 표시한다.
- **D4 보고서 15~17:** 본문은 그대로 두고 맨 위에 안내 문구를 넣는다. 새 수치는 CHANGES_VALIDATION.md와 README에 정리한다.
- **D5 속도 (확정):**
  - 평지: 주 결과 0.92 m/s(Apollo 15 비상 귀환 계획 3.3 km/h, 444 W). 민감도 0.7 / 1.1 m/s.
  - 경사: **"같은 노력" 규칙.** 평지와 같은 대사량이 나오는 속도로 걷는다(근거: Apollo 14 승무원이 편한 노력 수준을 유지하고 지형에 따라 속도를 바꿈, Waligora 1975). 오르막 10% 0.77, 20% 0.57 m/s.
  - 내리막: 문헌 비용 곡선에 같은 규칙을 적용하되 속도 상한은 평지 속도.
  - 속도가 IST 평지 곡선 범위(0.62 m/s) 아래로 내려가는 구간은 외삽으로 표시한다.
  - 영향: 칸 이동 시간이 경사마다 달라진다. Python의 시간·선량 누적과 JS 다익스트라를 경사별 속도로 바꾼다.
- **D6 예비분 환산 대사율: NASA 관행인 1200 BTU/h(352 W)로 확정 (2026-11-10).**
  - 산소 45.0 g, 냉각수 256 g. 모든 모델·속도 방식에 같은 고정량을 적용한다.
  - 근거는 CHANGES_VALIDATION.md에 정리한다(Apollo PLSS 설계 평균 대사율, EMU 소모품 여유 정의, 화성 PLSS 설계 평균 350 W).
