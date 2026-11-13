# NASA 공개 자료로 설계 가정 재검증

2026-10-31 작성

`reports/11`까지의 유인 미션 위험도·내비게이션 모델에는 "설계 가정(측정값 아님)"으로 표시한 상수가 여럿 있었다. 이번 작업에서는 2025 NASA Space Apps Challenge 데이터 참고자료를 출발점으로 NASA 공식 수치를 찾았고, 각 가정과 비교했다. 그 결과 하나는 실제 값으로 교체했고, 나머지는 단위가 맞지 않아 근거 각주만 붙였다.

## 1. 출발점: 2025 챌린지 데이터 참고자료

`2025 챌린지- Data 예시.pdf`("NASA 공개 데이터 활용 참고자료")에는 2025년 챌린지 17개의 공식 원출처와 글로벌 수상 사례가 정리돼 있다. 이 가운데 이 프로젝트(화성 SLAM, 위험도 기반 내비게이션, 방사선·온도 결합 위험)와 직접 연결되는 것은 4개다.

| 2025 챌린지 | 공식 원출처 | 이 프로젝트와의 연결 | 수상 사례 |
| --- | --- | --- | --- |
| Stellar Stories (우주기상) | NASA Space Weather, Solar Storms and Flares | SPE 방사선 위험 항의 근거 | HerCode Space |
| Your Home in Space (우주 거주지) | NASA-STD-3001 Volume 2, NTRS | EVA 보행속도·피폭 한도 등 인간 시스템 표준 | PureFlow |
| Through the Radar Looking Glass (SAR) | NASA ASF SAR DAAC, Vertex | 시간 경과에 따른 지형 변화 탐지 개념 (방법론 참고만) | — |
| SpaceTrash Hack (화성 재활용) | NASA NTRS | 화성 미션 기술문헌 저장소로서의 NTRS | — |

나머지 13개(식생, 농업, 해양, 외계행성 등)는 주제가 달라 제외했다. 참고자료는 올해 제출 시 **2026년 선택 챌린지의 요구사항과 Resources를 먼저 확인**하라고 명시하고 있다. 이 보고서의 수치는 그 확인을 대신하지 않는다.

## 2. 찾은 공식 수치

| 항목 | 수치 | 출처 | 확인 수준 |
| --- | --- | --- | --- |
| 커리어 유효선량 한도 | 600 mSv (성별·연령 무관) | NASA-STD-3001, OCHMO 2021 개정 / [OCHMO radiation protection technical brief](https://www.nasa.gov/wp-content/uploads/2023/03/radiation-protection-technical-brief-ochmo.pdf) | 여러 출처 일치 |
| 단일 SPE 사건 유효선량 한도 | 250 mSv/event (참조 사건: 1989년 10월) | NASA 표준 (검색 요약 기준) | 원문 미확인 |
| 조혈장기(BFO) 30일 한도 | 250 mSv | [windows2universe 선량 한도 표](https://mail.windows2universe.org/spaceweather/astronaut_dose.html) (2차 자료) | 구 체계 수치, 현행 유지 여부 미확인 |
| Orion storm shelter 설계 목표 | 대형 SPE 1회당 150 mSv 이하 | 검색 요약 기준 | 원문 미확인 |
| Apollo 달 EVA 계획 보행속도 | 3.3 km/h (≈0.92 m/s), 대사율 1200 BTU/hr | [NASA 1979 Apollo 달 표면 운용 문서](https://www.nasa.gov/wp-content/uploads/static/history/alsj/19790073512_1979073512.pdf) | 검색 요약 기준 |
| 장기 임무 피폭 한도 | NASA는 장기 임무용 한도를 권고할 만큼 지식이 충분하지 않다고 명시 | [nasa.gov Space Radiation](https://www.nasa.gov/humans-in-space/space-radiation/) | 직접 확인 |

**확인 수준에 대해.** NTRS 검색 페이지는 JavaScript로 렌더링돼 자동 조회가 되지 않았다. 그래서 위 수치 대부분은 웹 검색 결과 요약에서 얻었고, PDF 원문을 직접 펼쳐 확인한 것은 아니다. 특히 NASA-STD-3001 Volume 2 본문(현행 Rev F)에서 EVA 보행속도 요구치는 찾지 못했다. 0.92 m/s는 이 표준의 수치가 아니라 Apollo 시대 운용 계획값이다.

## 3. 적용 결정

| 상수 | 이전 | 결정 | 이유 |
| --- | --- | --- | --- |
| `EVA_WALK_SPEED_M_S` | 0.5 (임의 가정) | **0.92로 교체** | 문헌 근거가 있고, ETA와 영상 HUD 표시에만 쓰여 파급 범위가 작다 |
| `D_BUDGET_MSV_DAY` | 1.0 (일일 경보 기준선) | 유지, 각주 추가 | 공식 한도는 사건당·30일당·커리어당 누적치라 "일일" 기준선과 단위가 다르다 |
| `WARNING_THRESHOLD` | 0.37 (unitless) | 유지, 각주 추가 | 0~1 복합 지표라 mSv로 환산되지 않는다 |
| `D_BACKGROUND_MSV_DAY` | 0.655 | 변경 없음 | 이미 Curiosity RAD 실측(Hassler et al. 2014) 기반 |
| `SPE_DOSE_MULTIPLIER` | 2.9 | 변경 없음 | 이미 RAD sol 242 관측 기반 |

**방사선 예산을 교체하지 않은 이유.** 30일 BFO 한도를 하루 단위로 나누면 250 ÷ 30 ≈ 8.33 mSv/day가 된다. 이 값을 `D_BUDGET_MSV_DAY`에 넣으면 SPE 중 방사선 위험 항은 1.9/8.33 ≈ 0.23에 그친다. 지금은 1.0으로 포화된다. 그러면 `WARNING_THRESHOLD = 0.37`을 기준으로 맞춰 둔 모든 경보 시점이 바뀐다. 02:00 경보, SLAM 이후 LEG 1·LEG 2 대피 트리거가 모두 여기에 해당하고, 영상·PPT·보고서 숫자를 전부 다시 계산해야 한다. 그래서 현재 값을 "공식 누적 한도보다 훨씬 보수적인 데모용 조기경보 기준"으로 명시하는 쪽을 택했다. 공식 한도를 억지로 일일 값으로 환산해 넣으면 근거가 있는 것처럼 보이지만 실제로는 다른 물리량을 비교하게 된다.

## 4. 변경의 영향: 보행속도 0.5 → 0.92 m/s

경로 계산(어느 안전지대로 가는지, 몇 스텝인지, 경로상 최대 위험도)은 이 값과 무관하다. 바뀌는 것은 ETA뿐이다. 02:00(SPE와 극저온이 겹치는 시간) 대피 시나리오를 다시 실행한 결과는 다음과 같다.

| 출발점 → 안전지대 | 거리 | ETA (0.5 m/s) | ETA (0.92 m/s) |
| --- | --- | --- | --- |
| (20, 20) → (95, 29) | 22.6 m | 0.75분 | 0.41분 |
| (190, 180) → (177, 184) | 2.9 m | 0.10분 | 0.05분 |
| (110, 25) → (96, 29) | 4.2 m | 0.14분 | 0.08분 |

이 탐사 패치는 44m×44m 크기라 어느 쪽이든 1분 안에 도착한다. 따라서 결론("대피 경로가 실시간으로 의미 있는 짧은 거리 안에 존재한다")은 바뀌지 않는다. 다만 Apollo 값은 달 중력(1/6 g)과 Apollo 우주복 기준이다. 화성(약 0.38 g)과 차세대 우주복에서는 다를 수 있으므로 이 값도 여전히 근사치다.

## 5. 변경 파일

- `code/human_mission_navigation.py`: `EVA_WALK_SPEED_M_S = 0.92`로 바꾸고, 출처 주석과 `navigation_stats.json`의 note를 갱신했다.
- `code/human_mission_risk.py`: 문헌 수치 섹션에 NASA-STD-3001 공식 피폭 한도를 추가하고, `D_BUDGET_MSV_DAY` 옆에 단위 불일치 각주를 달았다.
- `code/first_person_walk.py`: HUD 라벨을 "design assumption"에서 "Apollo EVA planning rate, NASA 1979"로 바꿨다.
- `reports/11-human-mission-navigation.html`: JS 상수를 교체하고, 다시 만든 1인칭 영상을 임베드했다.
- `reports/11-human-mission-navigation.md`: 설계 가정 섹션을 갱신했다.
- 다시 생성한 파일: `outputs/human_mission_navigation/navigation_stats.json`, 시나리오 PNG 4장, `first_person_evac_walk.mp4`와 포스터.
- PPT(`build_phase2_ppt.py`)에는 보행속도나 ETA 숫자가 들어 있지 않아 고칠 것이 없었다.

## 5-1. Curiosity REMS 실측 기온으로 다시 계산 (추가 작업)

PDS Atmospheres 노드의 MSL REMS ENVRDR(`mslrem_1001`, Gale 분화구)에서 sol 242, 510, 540, 570, 600, 630, 660을 받았다. 위험도 공식의 기온 항만 실측값(Boom1 기온의 지방평균태양시 기준 시간 평균)으로 바꾸고, 지형·방사선·경고선과 SPE 01~04시 조건은 그대로 두었다. 코드는 `code/rems_temperature_scenario.py`, 그림은 `outputs/rems_temperature/rems_vs_cosine.png`에 있다. 인터랙티브 데모는 `reports/14-rems-temperature-demo.html`이다.

| 기온 출처 | 밤 최저 | 최대 온도 위험 | 최고 평균 위험 | 최소 안전지대 | 경보 시각 |
| --- | --- | --- | --- | --- | --- |
| 코사인 가정 | -95.0°C @02h | 1.00 | 0.408 | 5.6% | 01, 02, 03시 |
| REMS sol 242 (RAD SPE 관측일) | -68.2°C @05h | 0.00 | 0.208 | 97.2% | 없음 |
| REMS sol 510 (받은 것 중 가장 추움) | -81.6°C @04h | 0.44 | 0.281 | 94.4% | 없음 |
| REMS sol 540~660 (5개) | -74 ~ -81°C | 0.14 ~ 0.43 | 0.22 ~ 0.28 | 94.5 ~ 96.7% | 없음 |

실측 밤 최저는 가정보다 13~27°C 따뜻하고, 가장 추운 시각도 02시가 아니라 03~05시다. 그래서 받은 어느 sol에서도 SPE가 겹친 시간에 평균 위험이 경고선에 닿지 않았다. 지금까지 데모의 경보는 사실상 가정한 극저온이 만든 것이다. 다만 온도 위험 기준(-70°C에서 시작, -95°C에서 최대)도 가정이라, 이 결과만으로 실제로 안전하다고 결론 낼 수는 없다. 기준을 우주복·배터리 사양으로 다시 잡는 것이 다음 과제다.

- Boom2 기온 센서는 전자부가 -50°C 아래일 때 Boom1보다 50K 이상 낮은 값을 내는 구간이 있어(예: sol 570 02시, 195K 대 139K) Boom1을 썼다.
- 받은 sol은 242와 510~660뿐이라 화성 1년 전체를 덮지 않는다.
- `human_mission_risk()`에 `temperature_c` 인자를 추가했다. 주지 않으면 기존과 동일하며, 기존 경보(01~03시)가 그대로인 것을 다시 실행해 확인했다.

## 6. 추가로 접목할 수 있는 데이터

| 데이터 | 바꿀 수 있는 것 | 난이도 | 비고 |
| --- | --- | --- | --- |
| Curiosity REMS 기온 시계열 (PDS Atmospheres 노드) | `diurnal_temperature()`의 코사인 근사 → 실측 일교차 곡선 | 낮음 | 이 환경에서 PDS Atmospheres 접속 확인. 경보 시점이 바뀔 수 있어 비교 시나리오로 추가 권장 |
| Curiosity RAD 선량률 시계열 (PDS) | `SPE_DOSE_MULTIPLIER`, SPE 지속시간 | 중간 | 화성 표면에서 실제 SPE(예: 2017년 9월)를 측정한 구간을 찾아 배율·지속시간을 실측으로 보정 |
| NASA DONKI SEP 이벤트 목록 | SPE 발생 시각·빈도 (현재 01~04시 고정) | 중간 | Stellar Stories 공식 원출처 계열. 이 환경에선 api.nasa.gov 접속이 안 돼 파일로 받아와야 함 |
| HiRISE DTM (화성 고해상도 지형) | 실제 지형 위험도 데모의 지형 | 중간~높음 | 현재 `real_terrain_risk.py`는 달 LOLA(남극 20m) 지형 사용. 화성 지형으로 바꾸면 "화성 미션" 서사가 일관됨 |

가장 먼저 해볼 만한 것은 REMS 기온이다. 지금 위험도 모델에서 유일하게 "모양"까지 가정으로 만든 곡선이고, 데이터 접근도 확인됐다.

## 7. 남은 일

1. NASA-STD-3001 Volume 2 Rev F 원문(standards.nasa.gov)을 직접 열어 EVA 이동, 대사율, 피폭 관련 조항을 확인한다. 확인되면 2절의 "확인 수준"을 갱신한다.
2. 실제 SPE 선량률과 지속시간(NASA SRAG 자료 등)을 찾으면, `SPE_START_HOUR`/`SPE_END_HOUR`(현재는 시연용으로 3시간)의 근거를 보강할 수 있다.
3. 원하면 2절의 공식 한도를 쓰는 "현실 보정" 시나리오를 기존 데모와 별도로 추가해 비교할 수 있다. 이 경우 기존 산출물은 건드리지 않는다.
4. 2026년 챌린지 요구사항과 Resources를 확인하고, 이 프로젝트와 맞는 챌린지를 다시 매핑한다.
