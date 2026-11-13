# T2. EVA·우주복 맥락의 실시간 대사량 추정 알고리즘과 소모품 예측·의사결정 지원

작성일: 2026-11-09. 공통 브리프: `research/BRIEF.md`. 이번에 받은 원문·추출 텍스트는 `research/sources/`에 있다.
단위 환산: 1 W = 3.412 BTU/hr. 환산값은 모두 [Inference](산술)이다.

---

## 1. 요약

1. NASA 우주복이 실제로 쓴 실시간 대사량 추정은 세 가지다. 산소 탱크 압력 감소, LCG 열수지, 심박이다(Apollo는 셋을 함께 씀). 현행 ISS EMU는 산소 압력 감소 방식이고 누설이 섞인다. 다중 신호를 통계적으로 합친 방법(Feiveson 2009, LEGACI 2008)은 초록 수준에서만 확인했고 오차 수치는 공개되지 않았다. [Confirmed]
2. 심박 → 대사량 회귀는 개인 보정이 필수다. Hoffmann 2021은 132회 무중력 EVA에서 전체 회귀 R² 0.40, 개인별(같은 EVA를 반으로 나눠 학습·시험) R² > 0.82, RMSE 89.7 ± 44.2 BTU/hr(약 26 W)를 보고했다. 그런데 정답 값 자체가 산소 압력 감소를 20분 이동평균한 값이다. [Confirmed]
3. 화성 귀환 반경 문제와 거의 같은 개념이 이미 있다. Mackin 2010(SIM-EVA: TIME LEFT, WALKBACK time, BINGO 타원)과 PersEIDS 2023(과제별 가우시안 사전분포 + 실측 누적 → 종료 시점 소모량 분포와 안전 확률, point of no return)이다. 다만 둘 다 대사량 추정기와 지형 귀환 경로를 함께 검증한 적이 없다. [Confirmed]
4. "k(개인 배율)와 누설을 분리해 실시간 추정"하는 알고리즘을 공개 문헌에서 찾지 못했다. 다만 Apollo가 누설을 사전·사후 시험값으로 따로 넣었다는 점, 그리고 산소 압력 감소만 누설에 오염되고 VCO2·열수지·심박은 그렇지 않다는 점은 확인했다. 이 두 사실로 보아 상태 추정기(칼만 필터 등)로 둘을 분리할 수 있다고 본다. [Inference]
5. 응답 지연은 방법마다 크게 다르다. 산소 압력법은 30분 미만 구간에서 잡음이 크고, 심박·호흡 기반은 수 분 단위로 늦으며, 하지 IMU 기반 모델(지상)은 지연이 거의 없다. 화성 순산소 4.3 psi 우주복에서는 O2 농도 센서로 VO2를 잴 수 없을 가능성이 크다. 따라서 VCO2(유량계 × CO2 센서)가 누설과 무관한 핵심 독립 측정이 된다. [Inference]

---

## 2. 후보 방법 표

| 방법 | 측정하는 물리량 | 필요한 센서 | 시간 분해능·지연 | 보고된 정확도(조건 포함) | 대사와 누설을 구분하는가 | 비행 실적·TRL | 근거 표시와 출처 |
|---|---|---|---|---|---|---|---|
| A. 산소 탱크 압력 감소 | 공급 O2 질량 유량 = VO2 + 누설 | 고압 O2 탱크 압력·온도 | Apollo: 30분 미만은 잡음 큼. ISS: 2분 간격 값 | Carson 1972: 오차표가 누설 1 cc/min, RQ 0.01, 압력 1 psi당 BTU/hr 오차를 제시함(아래 3.A). 단기 정확도 수치는 없음 | **아니오**. 누설을 사전·사후 시험값으로 빼야 함(Apollo 12 사전 0.0044 → 사후 0.0169 lb/hr) | Apollo, Shuttle, ISS 운용(비행 실적 있음) | [Confirmed] Carson 1972 (NTRS 19720019460) p.62–65; Waligora 1975(브리프); Hoffmann 2021 p.3–4 |
| B. LCG 열수지(직접 열량) | LCG 제거 열 + 환기 잠열 = 대사열 + 열 누입 − 저장열 | LCG 입·출구 온도, 유량, 환기 이슬점 | 체내 열 저장 때문에 늦음(정량 미확인) | Carson 1972: 저장열 100 BTU당 25 BTU/hr, LCG ΔT 0.1°F당 25 BTU/hr 오차(3.85 h EVA 기준) | 산소 누설과 무관. 대신 환경 열 누입이 섞임 | Apollo 운용. Hoffmann 2021은 "단독 사용 시 불안정"이라고 인용 | [Confirmed] Carson 1972 p.56–59; Hoffmann 2021 p.3 |
| C. 급수 소모(승화량) | 승화된 물 질량 × 잠열 | Apollo: EVA 후 계량. 화성 PLSS: 연속 부피 센서 개발 중 | Apollo: EVA 전체 평균 1개 값 | Carson 1972 예시: 894 BTU/hr(Apollo 12 CDR EVA-1). 잔여수 0–0.6 lb면 0–130 BTU/hr 오차 | 산소 누설과 무관. 열 누입이 섞임 | Apollo 사후 계산. 연속 센서는 개발 단계 | [Confirmed] Carson 1972 p.59–61; Ogilvie ICES-2026-126 p.13 §12 |
| D. VCO2 = 환기 유량 × CO2 농도 (+RER) | CO2 생성률 → RER 가정으로 VO2·대사량 | 환기 유량계, CO2 센서 | 센서·환기 혼합 지연(수치 미확인) | NBL: RER 0.85 가정 + 보정식 MR_adj = exp[(ln MR_RER + 1.642327)/1.231614]. NBL→비행 배율 0.84 | **예**. O2 누설과 무관(CO2 누설·세정 효율은 별도 확인 필요) | NBL 지상 운용(엄빌리컬). 화성 PLSS는 유량계·경량 CO2 센서 개발 중 | [Confirmed] Cox 2024 (NTRS 20240009328) 슬라이드 4–5, 7; Ogilvie p.13–14 |
| E. 심박 → 대사량 선형회귀 | 심박(ECG) | ECG 또는 가슴 스트랩 | ISS 자료: HR 20초, MR 2분, 10점 이동평균(약 20분) | 132 EVA: 전체 R² 0.402, MR(BTU/hr) = 284.55 + 5.984·HR. 개인별 R² > 0.82, RMSE 89.66 ± 44.24 BTU/hr | **예**(누설과 무관). 대신 열·심리 스트레스, 피로, 표류가 섞임 | Apollo(사전 보정 곡선)·현재 텔레메트리. 회귀 모델은 연구 단계 | [Confirmed] Hoffmann 2021 (NTRS 20210024317) p.4–9, 12; Carson 1972 p.65 |
| F. 다중 신호 통계 결합 | HR, O2 소모, LCG 온도, VCO2 | A+B+D+E | LOWESS 평활 사용(창 길이 미확인) | "가끔 생기는 급증에 덜 민감, 피험자 안 재현성 양호"(정성적, 예비) | 구조상 가능(누설 항을 따로 모델링했는지는 미확인) | 지상 시뮬레이션 연구 | [Confirmed: 초록만] Feiveson 2009 (NTRS 20090042588); Kuznetz 2008 LEGACI (NTRS 20080014220) |
| G. 지형·속도 예측식 + 지연 보정(CSRM traverse) | 체중, 하중, 속도, 경사, 지형계수 → 대사량 | GPS/속도, DEM | 지수 감쇠 합성곱 + Hilbert 포락선으로 대사 적응 지연을 흉내 냄(D는 조정 변수) | n=4, JSC Rock Yard, K5 대비 회귀계수 0.95. 기존식보다 평균 354 BTU/h 감소, LoA 폭 약 4586 BTU/h | 측정이 아니므로 해당 없음(예측 사전분포로 사용) | APACHE VR 실시간 플러그인 시연 | [Confirmed] Kim 2025 (NTRS 20250001829) p.4–7; Kim 2024 EMBC (NTRS 20240001423) |
| H. 신경망(Kluis 2024) | 속도, 질량, 다리 길이, 하중, 경사, 중력, 우주복 압력 → VO2 | 사전 입력만 사용(생체 신호 없음) | 오프라인 예측 | 시험셋 R² 0.927, MAE 172.54 mL/min, 20% 이내 85.2% | 해당 없음 | 연구. 실시간 생체 피드백 결합은 "향후 과제"로 명시 | [Confirmed] Kluis2024_dissertation.txt PDF p.209–212, p.259–260 |
| I. 하지 IMU + 선형회귀(지상) | 보행 주기별 정강이·허벅지 운동 | IMU 2개 | 보폭 단위로 즉시 수렴. 8초간 보폭이 없으면 정지로 전환 | 신규 피험자 24명, 누적 오차 13%(스마트워치 42%). 심박 모델 정상상태 오차 39% | 해당 없음(누설과 무관) | 지상 연구. 우주복·저중력 검증 없음 | [Confirmed] Slade 2021 Nat Commun (PMC8277831) |
| J. 심박 + 가속도 분기 방정식(지상) | HR, 가속도 | HR + 가속도계 | 일 단위 PAEE | 개인 HR 보정 대신 집단 보정을 쓰면 편향이 약 2배 | 해당 없음 | 지상 역학 연구 | [Confirmed: 초록] Assah 2010 (DOI 10.1093/ije/dyq098) |
| K. 환기량(VE) 기반(지상) | 흉곽·복부 변위 → VE → VO2 | 전자기 코일·RIP | 정상상태·비정상상태 걷기 | VO2=f(VE)의 r²가 VO2=f(HR)보다 유의하게 높음(걷기, 간헐 작업) | 해당 없음 | 지상 연구 | [Confirmed: 초록] Gastinger 2010 (PMC3737974), 2012, 2014 리뷰 |

소모품·귀환 의사결정 도구

| 도구 | 하는 일 | 대사량 입력 | 검증 | 근거 |
|---|---|---|---|---|
| SIM-EVA Metabolic Advisor (NASA GRC) | TIME LEFT, WALKBACK time(직선 경로), BINGO 타원, 10% 여유 Safety BINGO | 모의 대사량(Apollo 14 자료 기반) | 데스크톱 시뮬레이션. 평균 도달 지점 10 → 11, 종료 시 잔량 11.1 → 13.7% | [Confirmed] Mackin 2010 NASA/TM-2010-216361 p.2–13 |
| PersEIDS (NASA JSC) | 과제별 사전분포 + 실측 누적 → 종료 시점 소모량 분포, 안전 확률, 대안 타임라인, point of no return | 심박을 1 Hz로 변환한 대사량 | VR 3일, EV 1명, 일마다 다른 IV. 정량 지표 없음 | [Confirmed] McGrath 2023 ICES-2023-327 p.3–9 |
| CSRM (NASA JSC) | 대사·PiCO2·체온·피로·traverse·수분·DCS 7개 영역, 개인별 경험 모델 | 분석 자료에서 얻은 개인 모델 | 체온 모델 오차 0.2 ± 0.15 °C (ARGOS) | [Confirmed] Hoffmann 2025 ICES (NTRS 20250002103) |
| SEXTANT / Minerva (BASALT) | 거리·시간·에너지 비용으로 경로 최적화 | 지형 기반 에너지 모델 | BASALT: "traverse 소요시간 추정이 충분히 정확하지 않아 Playbook에 반영하지 않음" | [Confirmed] Marquez 2019 Astrobiology (PMC6442304); Elston 2026 리뷰 부록 |
| ISS EVA 계획(NBL → 비행) | 개인별 과제 범주 10/50/90 백분위 대사율 × 타임라인 | NBL 측정 × 0.84 | EVA 85–88, 8명: 총 비용 상대오차 −33% ~ +14.7%(초록). 슬라이드에는 9.8–47.6%로 적혀 있음 | [Confirmed] Cox 2024 (NTRS 20240009328) |

---

## 3. 방법별 상세

### 3.A 산소 탱크 압력 감소법 [Confirmed: Carson 1972 p.62–65]
- 절차: 탱크 질량 m = P·V/(Z·R·T)(압축계수 Z 보정). m_POS = m_i − m_f. 소비 O2 = m_POS − m_LEAK. Apollo는 RQ(호흡교환율) = 0.85를 가정해 대사량으로 환산했다. 예시: Apollo 12 CDR EVA-1, 0.622 − 0.017 lb → 953 BTU/hr.
- 누설 처리: 누설은 측정하지 않고 시험값을 넣었다. 사전 시험값 0.0044 lb/hr를 쓰다가, 사후 시험에서 0.0169 lb/hr가 나와 EVA-2부터 이 값을 썼다. 누설 추정치가 EVA 사이에 약 4배 바뀐 사례다.
- 오차표(Table 4.10): PGA 누설 1 cc/min, RQ 0.01, 압력 1 psi 변화 각각에 대한 BTU/hr 오차를 제시한다. 추출된 텍스트("1 2 2")로는 수치를 확정할 수 없어 [Unverified]로 둔다. 원본 PDF p.17에서 확인이 필요하다.
- 실패 사례: 30분 미만 구간, 특히 저대사율에서 압력 텔레메트리 잡음 때문에 신뢰할 수 있는 값을 얻기 어려웠다(Waligora 1975, 브리프에서 확인). Hoffmann 2021 p.3–4도 "잡음 + 누설 포함 → 큰 오차"라고 정리했다.
- 우리 조건과의 차이: [Inference] 대사 VO2(걷기 300–600 W에서 대략 0.9–1.8 L/min STPD)에 견줘 누설이 차지하는 비율은 우주복 설계에 달려 있다. 화성 우주복 누설 사양은 이번에 확인하지 못했다. 이 방법만으로는 k와 누설을 분리할 수 없다(3.F 참조).

### 3.B LCG 열수지 [Confirmed: Carson 1972 p.56–59]
- 식: Q_TL + Q_VENT = Q_MET + Q_HL − Q_ST. Q_TL = ṁ·c·ΔT_LCG, Q_VENT = ṁ_O2·Δh(이슬점 기반 잠열).
- 오차원(Table 4.6, 3.85 h EVA 기준): 저장열 100 BTU당 25 BTU/hr, 수송 루프 유량 0.1 lb/min당 6, LCG ΔT 0.1°F당 25, 환기 유량 0.1 lb/hr당 4, 이슬점 1°F당 20 BTU/hr.
- 한계: 입구 이슬점을 가정해야 하고, 체내 열 저장 때문에 늦게 반응하며, 환경 열 누입이 섞인다. Hoffmann 2021 p.3은 LCVG 방식이 단독으로는 신뢰할 수 없다고 정리했다.
- 우리 조건: [Inference] 화성 대기와의 대류·전도 열교환과 일사가 Q_HL을 바꾼다. 냉각수 소모 예측(브리프의 냉각수 식)에도 같은 Q_HL이 들어가므로, 열수지는 대사량 추정기라기보다 냉각수 소모를 직접 관측하는 신호로 쓰는 편이 낫다.

### 3.C 급수 소모 [Confirmed: Carson 1972 p.59–61; Ogilvie p.13 §12]
- Q_MET = {m_FW·[h_c − c(T_FW − 32)] − Q_ELEC}/t − 1.276(LiOH 반응열 항). Apollo는 EVA 뒤 잔여수를 계량해 평균값 하나만 얻었다.
- Mars PLSS: 유연 급수 주머니의 연속 부피 센서를 개발 중이다. 기존 EMU는 2차 주머니의 압력 변화로 "복귀하라"는 비상 경고만 줬다.
- [Inference] 연속 부피 센서가 있으면 이 방법은 실시간 냉각수 소모율 측정이 된다. 대사량으로 환산하려면 열 누입을 알아야 한다.

### 3.D VCO2(환기 유량 × CO2) [Confirmed: Cox 2024 슬라이드 4–7]
- NBL: VCO2 = CO2 농도 × 공급 유량(Vaisala GMP252). 대사량(kcal/h) = 60·(4.039·VCO2/RER + 1.157·VCO2)로 계산한다(슬라이드 수식은 일부 깨져 있어 형태만 확인). RER 0.85를 가정한 뒤 MR_adj = exp[(ln MR_RER + 1.642327)/1.231614]로 보정한다.
- 분석 환경 → 비행 배율: NBL 대사율이 비행보다 대략 100–300 BTU/hr 높아, 0.84를 곱한다. 우리 k 문제와 같은 구조다. 분석 환경에서 얻은 개인 값을 실제 환경으로 옮기는 배율 자체가 불확실하고 과제 범주마다 다를 수 있다고 저자들이 적었다.
- 화성 PLSS: 연속 환기 유량계(차압 센서 하나로 대략 추정할 가능성도 언급), 경량 CO2 센서, O2 농도 센서를 개발 중이다(Ogilvie p.13–14).
- [Inference] 우리 조건(순산소 4.3 psi)에서는 루프 기체가 거의 100% O2라 O2 농도 차로 VO2를 재기 어렵다. 반면 CO2는 0에 가까운 배경에서 생성되므로 VCO2 측정은 성립한다. 남는 오차원은 RER(0.7–1.0 범위 → 대사량 환산에서 수 % ~ 10%대 변동, 원 식으로 재계산 필요), CO2 세정 효율, 유량계 정확도다.

### 3.E 심박 → 대사량 [Confirmed: Hoffmann 2021]
- 자료: 2006–2015년 Shuttle·ISS EVA 140건에서 132건 사용(5 h 미만 또는 신호 손실 25% 초과는 제외). 정답 MR은 산소 압력 감소로 2분마다 얻었고, HR은 ECG 20초 값을 2분으로 내렸다. 두 값 모두 10점 이동평균을 했다.
- 재사용 가능한 식(전체 회귀, BTU/hr): MR = 284.55 + 5.984·HR. W로 바꾸면 MR ≈ 83.4 + 1.754·HR [Inference: 환산]. R² 0.402.
- 개인 회귀: **같은 EVA의 앞 50%로 학습하고 나머지 50%로 시험**했다. R² > 0.82, RMSE 89.66 ± 44.24 BTU/hr. [Inference] 이는 "EVA 도중 실측으로 개인 보정을 한 뒤 남은 시간을 예측"하는 상황에 해당하고, 다른 날·다른 과제로 일반화한 성능은 아니다.
- MR/HR 지표: EVA 전체 평균 0.142 ± 0.03 BTU/beat. 시간대별 0.139–0.153 범위로 뚜렷한 표류가 없다고 보고했다.
- 한계: 저자들이 직접 쓴 한계는 과제 정보가 없다는 점, 단순회귀라는 점, 반복 피험자가 필요하다는 점이다. 이에 더해 [Inference] 정답 값이 누설을 포함하는 산소 압력법이라 회귀에 누설이 섞여 있고, 무중력 자료라 0.38 g 걷기와 생리 조건(혈류 분포, 기립 부하)이 다르다. Apollo에서도 심박법은 심리·환경 요인 때문에 짧게 치솟았고 "가장 부정확"해서 평균표에서 뺐다(Carson p.65). 대신 실시간 갱신과 짧은 과제 추정이라는 장점이 있었다.
- 우리 조건: [Inference] 화성 걷기 300–600 W(약 1020–2050 BTU/hr)는 Hoffmann 자료 평균 863 BTU/hr보다 높다. 고대사율 구간으로 외삽하게 된다.

### 3.F 다중 신호 결합과 k·누설 분리
- 확인된 선례
  - Feiveson et al. 2009 [Confirmed: 초록]: HR, O2 소모, LCG 온도, VCO2를 주축 요인분석 + OLS + LOWESS로 묶어 "자료 기반 가중평균"을 만든다. 당시 Constellation 설계는 "충돌하는 자료를 무시하는 휴리스틱 자동 방식"이었다. 정량 결과는 초록에 없다.
  - LEGACI (Kuznetz 2008) [Confirmed: 2쪽 초록]: HR, LCG 입·출구 온도·유량, 출구 가스·이슬점, pCO2, O2 압력, 가속도로 독립 대사량 여러 개를 계산하고, 통계적으로 "best" 값을 고른다. Integrated Walkback Suit Test와 Devon Island HMP에서 통신을 시험했다. 정확도 수치는 없다.
  - PersEIDS [Confirmed]: 과제별 대사율 사전분포(가우시안 근사, 과제 사이는 독립 가정)를 두고, 식 (1) M̂_T ~ M̃_t + R_c(d_c − d̃_c) + Σ_{i>c} R_i·d_i 로 종료 시점 총 소모량 분포를 만든다. 이 분포의 CDF를 한계값에서 평가해 안전 확률로 쓴다. PiCO2는 포아송-이항 분포로 다룬다. **사후 갱신(관측으로 사전분포를 고치는 단계)은 논문에 없다**. 남은 과제의 사전분포는 고정되어 있다.
- 칼만 필터: 이번 조사에서 EVA 대사량용 칼만 필터는 찾지 못했다. CSRM 논문은 심박 → 심부체온 칼만 필터(군 현장 자료, Buller 등)를 비교군으로만 다뤘고, 우주복 LCG 조건에서 0.95 ± 0.44 °C로 과대 예측했다고 보고했다(Hoffmann 2025 p.9–10). Hoffmann 2021은 Welles 2018(피부온·열유속·HR → 심부체온 칼만 필터)을 인용만 했다. 검색 결과가 없다고 문헌이 없다는 뜻은 아니다.
- k·누설 분리 설계안 [Inference, 검증 안 됨]
  - 상태 x = [k, L(누설, kg/s), (선택) RER]. k는 랜덤워크(빠르게 변함), L은 매우 느린 랜덤워크.
  - 관측식:
    - 산소 압력: ṁ_O2,tank = k·VO2_model(v, slope, g, m) + L + 잡음(큰 잡음, 긴 창)
    - VCO2: VCO2_meas = RER·k·VO2_model + 잡음(누설 무관)
    - 심박(개인 보정 a, b): HR = a + b·k·MR_model + 표류 + 잡음(누설 무관, 지연 있음)
    - 급수 부피: ṁ_w·h_fg = k·MR_model·(1 − η) + Q_env + 잡음(누설 무관, Q_env 별도)
  - 관측 가능성: 산소 압력만 있으면 k와 L은 활동 변화를 통해서만 구분된다(정지 구간에서는 휴식 대사와 L이 겹친다). VCO2나 HR처럼 누설과 무관한 관측이 하나라도 있으면 L은 "산소 압력 잔차의 느린 평균"으로 식별된다. RER 불확실성은 VCO2 → VO2 환산에서 L 추정 오차로 그대로 넘어간다.
  - 지연 처리: HR·VCO2 관측에는 1차 지연(시정수 τ)을 모델에 넣는다. Kim 2025는 예측식 쪽에 지수 감쇠 합성곱을 넣었는데, 같은 구조를 관측 모델에 쓸 수 있다.

### 3.G CSRM traverse 모델 [Confirmed: Kim 2025 p.4–7, Kim 2024]
- 식(BTU/h):
  - MF = |Hilbert[(MP − CF) * DF]|
  - MP = 3.41·[1.5W + 2.0(W+L)(L/W)² + η(W+L)(1.5V² + 0.35·V·S)]
  - CF = 3.41·η·[S(W+L)V/3.5 − (W+L)(S+6)²/W + (25 − V²)]
  - DF = (1/D)·e^(−1/D)
  - 속도: Tobler V = 0.28·6·e^(−3.5|S+0.05|), Apollo V = −0.01θ + 0.75.
- 기울기: GPS 고도 오차 때문에 DEM(NED)으로 보정했다. 경사 ±20° 초과는 통행 불가로 처리했다. 경로는 hybrid A*(고도, 경사, 롤오버 휴리스틱)로 찾는다.
- 검증: n=4, 최대 20분, 자기 속도. 회귀계수 0.95(기존 0.50). 기존식보다 평균 354 BTU/h 감소, LoA 폭 약 4586 BTU/h. 전이(걷기↔휴식)와 반복 오르내림에서 기존식이 특히 나빴다고 보고했다.
- APACHE Mars VR 시연: 비상 상황 지점에서 거주지까지 경로에 대사율을 색으로 입히고, 예상 시간·거리를 실시간으로 표시했다. 이것이 walkback 실시간 갱신 개념에 가장 가까운 NASA 시연이다. 정량 결과는 없다.
- 우리 조건: 지구 1 g, 비우주복 자료다. 달·화성 우주복 모델은 "개발 중"이라고 적혀 있다.

### 3.H Kluis 2024 신경망 [Confirmed: Kluis2024_dissertation.txt]
- 구조: 입력(속도, 질량, 다리 길이, 하중, 경사, 중력, 우주복 압력. 성별은 성능 향상 때문에 제거) → tanh 10노드 은닉층 2개 → 선형 출력. Adam, 학습률 0.01, 15 epoch, 배치 32 (PDF p.207).
- 자료: 2897점(IST-1 521, IST-2 374, Lankford 1810, Kluis 192). 우주복 566점, 부분 중력 1026점. 범위는 0.30–2.77 m/s, 0.12–1 g, 0–44.8 kPa, 경사 −18% ~ +40% (p.198–200).
- 성능: 시험셋 R² 0.927, MAE 172.54 mL/min(대략 58 W, 1 L O2 ≈ 20.1 kJ 가정 [Inference]), 5/10/20% 이내 비율 32.6/59.5/85.2% (p.209).
- 실시간 사용: 모델은 사전 입력만 쓴다. "EVA 중 HR, HRV, 대사율을 피드백 루프로 넣어 개인화"는 향후 과제로 명시되어 있다(p.259–260). 실시간 운용 실적은 없다.
- 주의 [Inference]: 80/20 분할이 "무작위 분할"(PDF p.203)이라 같은 피험자의 점이 학습셋과 시험셋에 함께 들어갔을 가능성이 있다. 그렇다면 신규 피험자에 대한 성능은 이보다 나쁠 수 있다. 0.38 g·29.6 kPa(4.3 psi) 조건은 학습 범위 안에 있지만, 그 조건의 우주복 자료는 IST-1/2(Mark III)뿐이다.
- 쓸모 [Inference]: k = 1 기준선 모델 VO2_model(v, slope, g, m)로 쓸 수 있다. 측정값과 비교해 k를 추정하는 역할이다.

### 3.I 지상 웨어러블 연구에서 얻는 교훈
- Slade 2021 [Confirmed]: 심박과 호흡 측정은 에너지 소비 변화에 늦게 반응해서, 정상상태 시작과 시간 변동 구간에서 오차가 컸다. 하지 IMU는 빨리 수렴했다. HR을 입력에 추가해도 정확도가 나아지지 않았다. 신규 피험자 기준 누적 오차는 IMU 13%, 스마트워치 42%. 피험자별 학습 자료를 쓰는 방법은 신규 피험자에서 오차가 약 2배라는 선행 결과도 인용했다.
- Assah 2010 [Confirmed: 초록]: HR+가속도 분기 방정식에서 개인 보정 대신 집단 보정을 쓰면 편향이 약 2배가 됐다.
- Gastinger [Confirmed: 초록]: 걷기·간헐 작업에서 VE와 VO2의 관계가 HR보다 강했다.
- 우리 조건 [Inference]: 우주복이 관절 운동을 제약하므로 하지 운동학 → 대사 관계는 우주복 압력·중력마다 다시 학습해야 한다. 우주복 안 환기 루프는 사람의 VE를 직접 재지 않으므로, VE 기반 방법은 흉부 센서가 있어야 쓸 수 있다.

### 3.J 소모품·귀환 의사결정 도구 상세
- SIM-EVA (Mackin 2010) [Confirmed]:
  - 7단계 표시(잔량, 50/25% 경고, TIME LEFT, WALKBACK, 최대 범위 원, BINGO 타원, 10% Safety BINGO)를 둔다.
  - WALKBACK은 직선 귀환을 가정하고 지형을 고려하지 않는다. 사용자들은 TIME LEFT를 거리와 연결하기 어렵다고 해서 잘 쓰지 않았고, 잔량 게이지와 BINGO 범위를 가장 많이 썼다.
  - "경사·장애물 keep-out과 지형 비용을 통합해 달라"는 요청이 나왔다. 피험자 수와 시행 수는 보고되지 않았다.
  - 이 연구는 우리 프로젝트(지형 위 귀환 가능 영역)의 직접 선행 개념이다.
- PersEIDS (McGrath 2023) [Confirmed]:
  - point of no return을 "가용 소모품 안에서 더 이상 거주지로 돌아올 수 없는 시점"으로 정의한다. 현재 시스템은 이를 현재 시점의 귀환 가능 여부(SA level 2)로만 제시하고, 미래 투영은 하지 않는다고 저자들이 한계로 적었다.
  - 대사량은 Polar H10 심박을 "단순 변환"한 1 Hz 값이었다. 변환식은 공개되지 않았다.
  - 시연에는 정량 지표가 없고, 2일차와 3일차의 학습 편향 가능성을 저자들이 인정했다.
- BASALT/SEXTANT [Confirmed]:
  - SEXTANT는 거리·시간·에너지 비용으로 경로를 최적화했다. 그러나 traverse 소요시간 추정이 충분히 정확하지 않아 Playbook 타임라인에 반영되지 않았다(Marquez 2019).
  - Kluis 2024의 SEXTANT 개선 요구 목록(재계획, 실시간 상호작용, 소모품 표시)은 Beaton et al. PSS 2020을 인용한 것인데, 이 원문은 열지 않았다 [Unverified].
- NBL → 비행 예측 (Cox 2024) [Confirmed]: 개인별 과제 범주 대사율을 사전 분포로 쓰는 방식이 ISS에서 이미 운용되고 있다. 9개 범주 중 6개는 예측과 실제의 대사율 차이가 유의하지 않았다. 예측은 대체로 과대(보수적)였다.
- D-RATS, NEEMO: Elston 2026 리뷰는 D-RATS 2011을 자료 품질 확인 맥락에서만 다뤘다. "traverse 계획과 실시간 EV 자료(소모품, 생리 성능)를 통합한 시도는 거의 발표되지 않았다"고 적었다(리뷰 p.7–8). NEEMO에서 소모품 예측을 다룬 원문은 이번에 찾지 못했다.

### 3.K 우리 조건(화성, 0.38 g, 4.3 psi 순산소, 300–600 W)과의 차이 종합 [Inference]
- 무중력 EVA 자료(Hoffmann)와 NBL 자료(Cox)는 상체 위주 작업이다. 걷기 위주인 화성 traverse의 HR–MR 관계와 다를 가능성이 크다.
- 순산소 루프에서는 O2 농도 기반 VO2 측정이 무의미하다. VCO2(+RER)와 O2 질량 수지가 주 경로다.
- 300–600 W에서는 HR 신호대잡음이 저대사보다 좋지만, 열 스트레스에 따른 HR 상승(심박 표류)이 길게 걸으면 커질 수 있다. Hoffmann의 ISS 자료에서는 표류가 관찰되지 않았다.
- k 정밀도 요구: 브리프에 따르면 k ±15%가 면적 −20 ~ +31%로 이어진다. 보고된 오차를 "평균 대비 %"로 거칠게 보면 이렇다.
  - Hoffmann 개인 회귀: 89.7 / 863 ≈ 10%
  - Kluis 신경망: 20% 이내 85%
  - NBL → 비행 총 비용: −33% ~ +14.7%
  - 이 값들은 조건이 서로 달라 직접 비교할 수 없다. 우리 시스템의 기대 성능으로 옮기면 안 된다.

---

## 4. 구현·코드·데이터

| 대상 | 저장소 | 라이선스 | 마지막 push | 분류 | 비고 |
|---|---|---|---|---|---|
| Slade 2021 IMU 에너지 추정 | `pslade2/EnergyExpenditure` | 없음(라이선스 파일 없음) | 2022-06-06 | 참고만(Build 시 아이디어) | 실시간 마이크로컨트롤러 스크립트(`real_time_est.py`)와 선형회귀 가중치. 라이선스가 없어 코드 재사용 불가 [Confirmed: gh api, README] |
| Slade 스마트폰 모니터 | `Harvard-Slade-Lab/A-smartphone-activity-monitor-that-accurately-estimates-energy-expenditure` | MIT | 2026-01-12 | Extend 후보(지상 전용) | 내용은 열지 않음 [Confirmed: gh api 메타데이터만] |
| pampro (가속도 처리) | `Thomite/pampro` | 없음 | 2021-05-24 | 해당 없음 | 분기 방정식 구현 여부는 미확인 |
| GPS 트랙 traverse 시간 | `ag00dwin/EVA_traversetime` | AGPL-3.0 | 2024-09-09 | 해당 낮음 | Avenza GPS 처리. 내용 미확인 |
| SEXTANT, PersEIDS, CSRM, SIM-EVA, LEGACI | 공개 저장소 찾지 못함 | — | — | **Build** | GitHub 검색("SEXTANT", "spacesuit metabolic", "EVA traverse" 등)으로 나오지 않음. 없다는 증거는 아님 |

권고 [Inference]:
- k·누설 추정기는 **Build**한다. 기준 모델은 Kluis식 또는 기존 프로젝트의 대사 모델, 관측식은 3.F, 필터는 확장 칼만이나 입자 필터.
- 소모품 투영은 PersEIDS 식 (1)을 **Adopt**(식 수준)한다. 단, 관측으로 사전분포를 고치는 사후 갱신 단계를 덧붙인다.
- 표시 계층은 SIM-EVA의 BINGO와 Safety BINGO 개념을 지형 등시간선(isochrone)으로 바꿔 쓴다.

---

## 5. 막힌 원문·추가 확인 항목

열지 못했거나 초록만 본 문헌. 유료 벽을 우회한 시도는 없다.
- Feiveson et al. 2009 ENAR, "Combining Disparate Measures of Metabolic Rate": NTRS에 PDF가 없다(초록만). 가중치와 재현성 수치가 필요하다.
- Horrigan 1975, "Metabolic rate control during EVA simulations…" (NTRS 19760004083): NTRS에 PDF가 없다. 산소법 단기 문제와 심박법 저강도 문제의 정량값이 있을 것으로 보인다.
- Dietrich 2009, ETDP-EVA-PCAI-0024 "Determination of Metabolic Rate for EVA Suits": 내부 문서로 보이며 공개본을 찾지 못했다.
- Kuznetz 2008 SAE 2008-01-1952 "Designing a smart suit for the moon and mars": 열지 않음.
- Johnson et al. 2009 SAE 2009-01-2562, 2010 AIAA (통합 traverse planner, 귀환 경로): 열지 않음. Mackin 2010과 Kim 2024의 기술로만 앎 [Unverified].
- Norheim et al. 2018 IEEE Aerospace (SEXTANT 구조), Beaton et al. 2020 PSS (BASALT 개선 요구), Marquez 2005/2007: 열지 않음.
- Greenlund, Miller, Feigh 2017 AIAA (Apollo 대사율 운용 평가), Paul 2012 ICES (Apollo까지의 에너지 소비, NTRS 20120003917): 열지 않음.
- Beltrame 2017, Borror, Zignoli (심박 + 속도 → VO2 신경망·LSTM): Kluis 학위논문 문헌 검토로만 앎. PubMed 검색으로 찾지 못함 [Unverified].
- Buller 등 심박 → 심부체온 칼만 필터: 원문 미확인.

추가 확인이 필요한 항목:
1. Carson 1972 Table 4.10 수치(누설 1 cc/min, RQ 0.01, 압력 1 psi당 BTU/hr): 추출 텍스트가 깨져 있어 PDF 원본 p.17로 확인해야 한다.
2. Cox 2024 대사량 식의 계수(4.039, 1.157)와 변수 배치: 슬라이드 글꼴이 깨져 있어 원문 확인이 필요하다.
3. Cox 2024 오차 범위 불일치: 초록 −33% ~ +14.7%, 슬라이드 9.8–47.6%.
4. PersEIDS의 HR → MR "단순 변환"식: 공개되지 않았다.
5. 화성 우주복 누설 사양(scc/min)과 순산소 루프 O2 센서의 용도: Ogilvie 문서에는 O2 센서가 prebreathe·대기 감시 용도로 적혀 있다.
6. 심박·VCO2 관측의 실제 지연 시정수(우주복 환기 루프 혼합 포함): 수치 출처가 없다.
7. Kluis 2024 분할이 피험자 단위였는지 여부.

---

## 6. 참고문헌 (이번에 실제로 연 것)

- Hoffmann B. (2021) Ch.5 "EVA Metabolic Rate Model: Metabolic Rate Estimated from Heart Rate", UND 학위논문 일부. NTRS 20210024317. https://ntrs.nasa.gov/citations/20210024317 (전문, `sources/Hoffmann2021_NTRS20210024317.txt`)
- Carson M.A. (1972) "Apollo Portable Life Support System Performance Report". NTRS 19720019460 (전문, `references/NTRS_19720019460.txt`)
- Waligora & Horrigan (1975) `references/Waligora1975_metabolic_cost_EVA.pdf` (브리프 확인 사항 재확인용으로 일부 구절만)
- Mackin M.A., Gonia P., Lombay-Gonzalez J. (2010) NASA/TM-2010-216361 "Effective Presentation of Metabolic Rate Information for Lunar EVA". https://ntrs.nasa.gov/citations/20100039148 (전문)
- McGrath T. et al. (2023) ICES-2023-327 "A Decision Support System for Extravehicular Operations Under Significant Communication Latency" (PersEIDS). https://ntrs.nasa.gov/citations/20230007488 (전문)
- Hoffmann B.T. et al. (2025) ICES "Development of the Crew State and Risk Model…". https://ntrs.nasa.gov/citations/20250002103 (전문)
- Hoffmann B. et al. (2024) ICES "Core Body Temperature Predictions Using Metabolic Energy Expenditure and Heart Rate…". https://ntrs.nasa.gov/citations/20230016649 (초록·1쪽)
- Kim K.J. et al. (2025) ICES "A Consolidated Tool for Planning and Analyzing Simulated Exploration Traverses and Associated Metabolic Workload". https://ntrs.nasa.gov/citations/20250001829 (전문)
- Kim K.J. et al. (2024) IEEE EMBC "Improving Metabolic Workload Estimation Accuracy…". https://ntrs.nasa.gov/citations/20240001423 (1쪽 전문)
- Cox L. et al. (2024) ISS R&D "EVA Planning: Using NBL Training to Predict in-Flight Energy Expenditure". https://ntrs.nasa.gov/citations/20240009328 (초록 + 슬라이드)
- Kuznetz L. et al. (2008) "Integrated Software Systems for Crew Management During EVA…" (LEGACI/VIOLET). https://ntrs.nasa.gov/citations/20080014220 (2쪽)
- Feiveson A.H. et al. (2009) "Combining Disparate Measures of Metabolic Rate During Simulated Spacewalks". https://ntrs.nasa.gov/citations/20090042588 (초록만)
- Elston J.T. et al. (2026) IEEE Aerospace "Review of Advanced Informatics and Display Systems for EVA Operations". https://ntrs.nasa.gov/citations/20250011652 (전문 일부 검색)
- Marquez J.J. et al. (2019) "Future Needs for Science-Driven Geospatial and Temporal EVA Planning and Execution", Astrobiology 19(3):440–461. https://doi.org/10.1089/ast.2018.1838 (PMC6442304 전문, PubMed 경유)
- Kluis L. (2024) 박사학위논문, `references/Kluis2024_dissertation.txt` (PDF p.31–36, 80–82, 198–216, 259–260)
- Ogilvie et al. ICES-2026-126 "Mars PLSS Status and Plan", `references/ICES-2026-126_Ogilvie_MarsPLSS.txt` p.13–14
- Norcross et al. NASA/TP-2010-216115 (IST-1), `references/Norcross_TP-2010-216115.md` (bioadvisory 언급 구절, 원문 p.54)
- Slade P. et al. (2021) "Sensing leg movement enhances wearable monitoring of energy expenditure", Nat Commun 12:4312. https://doi.org/10.1038/s41467-021-24173-x (PMC8277831 전문, PubMed 경유)
- Assah F.K. et al. (2010) Int J Epidemiol 40(1):112–120. https://doi.org/10.1093/ije/dyq098 (초록, PubMed)
- Gastinger S. et al. (2010) J Sports Sci Med 9(1):110–118, PMC3737974; (2012) https://doi.org/10.1123/ijsnem.22.2.117; (2014) https://doi.org/10.1177/0148607114530432 (초록, PubMed)
- GitHub 메타데이터: `gh api repos/pslade2/EnergyExpenditure`, `repos/Harvard-Slade-Lab/A-smartphone-activity-monitor-that-accurately-estimates-energy-expenditure`, `repos/Thomite/pampro`, `repos/ag00dwin/EVA_traversetime`
