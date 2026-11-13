# T3. 우주복 밖(지상) 웨어러블 에너지 소비 추정 기술과 우주복 적용 가능성

작성일: 2026-11-09 · 담당: T3 · 공통 지침: `research/BRIEF.md`

## 1. 요약

- 지상 웨어러블은 **몸 쪽 신호(심박, 호흡량, 다리 IMU)** 로 대사량을 추정한다. 이 신호들은 우주복 누설과 무관하다. 따라서 산소 탱크 감소율(대사 + 누설)과 함께 쓰면 누설을 분리하는 독립 관측이 된다 [Inference].
- 보고된 정확도는 서로 다르다. 개인 보정한 심박+가속도는 집단 보정보다 확실히 낫다(DLW 기준 ICC 0.62 → 0.81). 열 스트레스 아래 원시 심박은 VO2를 평균 30% 과대추정했다. 호흡량(VE)은 심박보다 VO2와 상관이 높았다(r² 0.80~0.87 대 0.50~0.73). 다리 IMU 모델은 새 피험자에서 누적 오차 13%를 보고했다 [Confirmed, 각 논문 조건 한정].
- 우주복 안에서는 다음이 문제다. 열·탈수로 심박이 표류한다. 냉각복이 피부 온도와 열류 신호를 왜곡한다. 순산소 환경에서는 O2 분율 차이로 VO2를 재는 휴대용 열량계(K5 등)가 원리적으로 맞지 않는다. 0.38 g와 우주복 관절 때문에 지상 IMU 보행 모델은 다시 학습해야 한다 [Inference, 일부 Confirmed].
- 비행 실적: Astroskin(Hexoskin 계열)은 Bio-Monitor로 2018년 12월 ISS에 올라가 선내에서 쓰였다. 우주복 안 EVA에서 쓰였다는 기록은 확인하지 못했다. NASA H-3PO의 비가압 우주복 모사(HS3, APACHE)에서는 COSMED K5와 Polar H10, APDM Opal IMU를 함께 썼다 [Confirmed].
- 권장 후보(채택이 아니라 후보): ① 개인 보정 심박(가능하면 열 성분 보정 포함) + 다리/몸통 IMU 보행 모델 융합, ② 호흡 셔츠의 VE(개인 보정 필수), ③ PLSS의 CO2·환기 측정. 이 셋을 칼만 필터로 묶어 k와 누설을 함께 추정하는 구조가 가장 그럴듯하다 [Inference].

## 2. 후보 방법 표

| 방법 | 측정하는 물리량 | 필요한 센서 | 시간 분해능·지연 | 보고된 정확도(조건 포함) | 대사와 누설 구분 | 비행 실적·TRL | 근거·출처 |
|---|---|---|---|---|---|---|---|
| 심박 단독, 개인 보정(Flex-HR) | HR → 개인 HR-VO2 곡선 | 가슴 ECG 띠 또는 셔츠 | 수 초 단위로 갱신. 생리적 지연은 수십 초 [Inference] | DLW 대비 개인 TEE 편차 −22.2%~+52.1%, 14명 중 9명이 ±10% 이내(자유생활 15일, Livingstone 1990). EVA 자료에서 R² 전체 0.40, 개인 >0.82(Hoffmann 2021) | 구분함. 몸 신호라 누설과 무관 [Inference] | 심박은 Apollo 이래 EVA에서 늘 측정. 대사 추정의 보조 수단 [Confirmed: BRIEF, Hoffmann 2021] | [Confirmed] PubMed 2193501 초록; NTRS 20210024317 |
| 심박 + 열 성분 보정(Vogt 방식) | HR − ΔHR_thermal | HR + 작업 중 짧은 휴식 구간 | 휴식 구간마다 열 성분을 갱신 | 원시 HR은 작업 VO2를 평균 30%(범위 1~64%) 과대추정. 오차 분산의 74%가 열 성분으로 설명됨. 보정 HR은 측정 VO2와 통계적 차이 없음(임업 노동자 41명, Dubé 2016) | 구분함 | 지상 산업 현장만 | [Confirmed] PubMed 26851474 초록 |
| 심박 + 가속도 결합(Actiheart 계열) | HR + 가속도 활동량 | 가슴 부착 일체형 | 15~60 s 에포크 [Unverified: 기기 설정값] | DLW 기준 AEE: 집단 보정 ICC 0.62, 개인 보정 ICC 0.81, 개인 보정으로 편향·RMSE·LoA가 약 1/3 감소(남성 35명, 10일; Villars 2012). 하지 절단자 실험실 보행에서는 독점 집단 알고리즘 오차가 34~45%, 집단 맞춤 회귀(GT3X+HR)는 15~18%(Ladlow 2019) | 구분함 | 지상만 | [Confirmed] PubMed 23019315, 30703115 초록 |
| 호흡 기반(VE, 호흡수) | 흉곽·복부 움직임 → 일회호흡량·VE·fR | 호흡 인덕턴스·스트레인 셔츠(Hexoskin/Astroskin), 임피던스 호흡측정 | 호흡마다 계산. Astroskin RR은 최근 8회 호흡의 이동평균 | Hexoskin VE: 아최대 자전거에서 불일치 ≤5.3%, 안정 시 ≤15.3%, 최대 운동 ≤11.7%. 성별·체중 보정 후 단일 식 r=0.89(17명, Smith 2019). 최대 운동 typical error 9.5~19.6%(Elliot 2019). 보정 없이는 임의 단위(Villar 2015). 트레드밀 보행 VE 상관 r 0.08~0.15(Montes 2018). VE와 VO2의 r²는 0.80~0.87, HR과 VO2는 0.50~0.73(12명, 10 kg 배낭 보행 포함, Gastinger 2010) | 구분함 | Astroskin/Bio-Monitor: ISS 선내(2018~), HERA 아날로그. 2017년 시점 문서에 "TRL 5 → 6" 목표 | [Confirmed] PubMed 30946696, 28759538, 26360814, 30338022; PMC3737974; NTRS 20190001996 |
| 다중 센서 ML(HR+VE+가속도) | 위 신호들의 결합 | 셔츠 + 손목·허벅지 가속도계 | 15 s 창 | MLP: MAE 1.65 mL/kg/min, R² 0.92. Flex-HR은 MAE 2.83, R² 0.75(11명, 모의 작업, 피험자 1명 제외 교차검증, Lu 2018). 공개 Ingraham 데이터셋에서 단일 신호로는 VE가 가장 예측력이 높음. Transformer RMSE 0.87 W/kg, HR 단독 1.81 W/kg(Babakhani 2025, 프리프린트) | 구분함 | 지상만 | [Confirmed] PMC6164120; arXiv 2511.09276; PubMed 30629472 |
| IMU + 보행 데이터 모델 | 정강이·허벅지 IMU의 보폭별 운동학 | IMU 2개(한쪽 다리) | 보폭마다 갱신. 생리 신호보다 빨리 수렴 | 새 피험자 24명: 정상상태 오차 13%, 시간 변화 구간 23%, 누적 13%. 스마트워치 42%, 심박 모델 39%. 심박을 입력에 더해도 개선 없음(Slade 2021) | 구분함 | 지상만 | [Confirmed] PubMed 34257310; PMC8277831 |
| 보행 부하 예측식(Pandolf, Santee, LCDA) + GPS | 속도·경사·하중·지면 계수 → 대사량 | GPS/관성 항법 + 지형 + 질량 | 1분 단위 + 지수 평활 | 복합 지형, 하중 30~45% BM: Santee 보정이 가장 좋음(편향 −13±87 W, RMSE 99 W). 대부분 식은 과소추정(9명, Looney 2018). GPS 입력 Pandolf-Santee 편향 −2±12 W(12명, Potter 2018). LCDA 보행식 편향±SD 0.01±0.33 W/kg(메타회귀 48편, Looney 2019) | 해당 없음. 이것은 "모델"이므로 k의 분모가 된다 [Inference] | 군 계획 도구(LCDA) | [Confirmed] PubMed 29860513, 29944605, 30649093 |
| 휴대용 간접열량계(COSMED K5) | 마스크 유량 × O2·CO2 분율 | 마스크 + 유량계 + O2·CO2 센서 | 호흡마다(BBB) 또는 혼합 챔버 | Douglas bag 대비 저~중강도 VO2 평균 차 0.61~−2.05%. 고강도 BBB는 −4.63~−7.27%로 과소, DMC는 −0.38~−3.81%(Winkert 2020). VE·VO2가 DB와 2.1 L/min·0.08 L/min 이내, BBB의 VCO2는 ≥150 W에서 과소(Crouter 2019) | 구분함 | NASA H-3PO 비가압 우주복 모사(HS3, APACHE)에서 헬멧 안 마스크로 사용 | [Confirmed] PubMed 31895296, 31841537; NTRS 20230002324, 20220003008 |
| 피부 열류·온도 + 가속도(SenseWear 계열) | 열류, 피부 온도, GSR, 가속도 | 팔뚝 밴드 | 1분 에포크 [Unverified] | 총 EE −18.2% 과소, 강도가 오를수록 오차 증가(26명, Gastin 2017). 33 °C에서 19 °C보다 고강도 EE를 더 높게 추정(Van Hoye 2014) | 구분함 | 지상만 | [Confirmed] PubMed 28797831, 25537112 |
| 심박 → 심부체온 칼만 필터(ECTemp) | HR 시계열 → 심부체온 | HR | 1분 | 편향 −0.03±0.32 °C, 95% LoA ±0.63 °C(검증 N=83; Buller 2013) | 대사가 아니라 열 상태 추정. 심박 표류 보정에 쓸 수 있는 보조 상태 [Inference] | 군 현장(1806명 행군 자료, Buller 2022) | [Confirmed] PubMed 23780514, 35022161 |

## 3. 방법별 상세

### 3.1 심박 기반(Flex-HR, 개인 보정)
- **원리.** 개인별 HR-VO2 곡선을 미리 만든다. FLEX HR(안정과 활동을 가르는 심박) 아래는 안정 대사로, 위는 곡선으로 환산한다. Livingstone 1990의 FLEX HR은 97±8 bpm이었다 [Confirmed, PubMed 2193501].
- **절차(재사용 가능).** ① 지상 보정: 우주복을 입은 상태에서 트레드밀이나 ARGOS 보행으로 4~6단계 강도의 HR과 VO2(또는 VCO2)를 잰다. ② 개인별로 선형 또는 2차 회귀 MR = a + b·HR를 맞춘다. ③ EVA 중 MR̂(t)를 계산한다. Hoffmann 2021은 EVA 자료에서 개인 회귀로 R² >0.82를 얻었다 [Confirmed, NTRS 20210024317].
- **실패 원인.**
  - 열 성분: 원시 HR은 VO2를 평균 30% 과대추정했고, 오차 분산의 74%가 열 성분으로 설명됐다 [Confirmed, Dubé 2016 초록].
  - 심혈관 표류: 35 °C에서 60% VO2max로 자전거를 탈 때, 15분에서 45분 사이 HR은 12% 올랐지만 아최대 VO2는 "약간만" 늘었다 [Confirmed, Wingo 2005, PubMed 15692320]. 따라서 장시간 EVA에서 HR→MR 고정 곡선은 시간이 지날수록 과대추정 쪽으로 기운다 [Inference].
  - 정서·각성, 카페인, 자세 [Inference; 카페인 조건 자체는 Silva 2014가 ACC+HR 정확도에 큰 차이가 없다고 보고. PubMed 24690589].
- **Vogt 열 성분 보정.** 작업 중 10분 앉아 쉬는 구간마다 ΔHR_T를 추정해 HR에서 뺀다. 그 결과 측정 VO2와 통계적 차이가 없었다 [Confirmed, 초록]. 식의 세부 형태는 원문을 보지 못했다 [Unverified]. EVA에서는 정지 구간(표본 채취, 휴식)을 같은 용도로 쓸 수 있다 [Inference].
- **우리 조건과의 차이.** 냉각복(LCG)이 열 부하를 상당 부분 없애므로 열 성분은 지상 방호복보다 작을 수 있다. 다만 LCG 설정과 탈수에 따라 달라진다 [Inference]. 4.3 psi 순산소의 흡기 PO2는 (222 − 47) ≈ 175 mmHg로, 해수면 공기(≈150 mmHg)보다 약간 고산소다. 따라서 지상 공기 호흡에서 만든 HR-VO2 곡선은 그대로 옮겨지지 않을 수 있다. 고산소가 아최대 HR을 낮추는 크기는 이번에 확인하지 않았다 [Inference/Unverified]. 그래서 보정은 우주복 압력·기체 조건에서 하는 것이 맞다.

### 3.2 심박 + 가속도(Actiheart 계열)
- **원리.** 분기(branched) 모델이다. 가속도가 낮을 때 높은 HR은 정서나 열 때문이라고 보고 가중치를 낮춘다 [Unverified: 분기 모델 세부식은 원문 미확인].
- **보고 수치.** 집단 보정 ICC 0.62, 개인 보정 ICC 0.81 [Confirmed, Villars 2012]. 독점 집단 알고리즘을 특수 집단(절단자)에 쓰면 34~45%의 큰 오차가 났다 [Confirmed, Ladlow 2019]. 시사점: 집단 보정 알고리즘을 우주비행사에게 그대로 쓰면 안 된다 [Inference].
- **우주복 차이.** 가슴 가속도계는 HUT(단단한 상체 외피) 안에서 몸통 움직임을 직접 잡지만, 우주복 관절 토크 때문에 같은 가속도에 드는 대사가 지상보다 크다. 지상 계수는 그대로 옮길 수 없다 [Inference].

### 3.3 호흡 기반(VE, 호흡수, 스마트 셔츠)
- **원리.** 휴식부터 환기 역치 아래까지는 VE와 VO2가 대략 선형이다(VE/VO2 환기당량이 거의 일정). 역치 위에서는 VE가 비선형으로 늘어 과대추정된다. 이것은 일반 운동생리학 지식이며, 이번에 원문으로 확인하지 않았다 [Unverified]. 셔츠는 흉곽·복부 둘레 변화로 일회호흡량을 추정하므로, 개인 보정(스파이로미터 대비 체적 환산)이 필요하다.
- **보고 수치.** 성별·체중을 보정하면 단일 VE 식 r=0.89, 아최대 불일치 ≤5.3% [Confirmed, Smith 2019]. 그러나 보행에서는 VE 상관이 r 0.08~0.15로 나빴다 [Confirmed, Montes 2018]. 최대 운동에서는 typical error가 9.5~19.6%였다 [Confirmed, Elliot 2019]. 같은 기기도 조건과 처리(펌웨어, 보정 여부)에 따라 결과가 크게 갈린다.
- **VE vs HR.** 10 kg 배낭 보행과 간헐 운동을 포함한 조건에서 VE의 r²가 HR보다 일관되게 높았다(개인 단위 0.906 대 0.832) [Confirmed, Gastinger 2010]. 공개 데이터셋(Ingraham 2019)에서도 단일 신호로는 VE가 가장 예측력이 높았다 [Confirmed, arXiv 2511.09276; 해당 프리프린트는 동료심사 여부를 확인하지 못함].
- **우주복 차이.**
  - 셔츠의 VE는 사람의 폐 환기다. PLSS의 "환기 유량"은 우주복 기체 루프 유량이다. 둘은 다른 양이므로 혼동하면 안 된다 [Inference].
  - 가압 우주복(4.3 psi 차압) 안에서도 흉곽 움직임은 셔츠로 잡힌다고 보지만, 실제 측정 사례는 찾지 못했다 [Unverified].
  - 순산소에서는 환기 구동이 공기 호흡과 다를 수 있다(고산소 환기 저하). 개인 보정은 우주복 조건에서 해야 한다 [Inference].
  - 말하기(교신)는 호흡 신호를 오염시킨다 [Inference].

### 3.4 IMU + 보행 모델, 최근 ML
- **Slade 2021.** 정강이와 허벅지 IMU의 보폭별 신호(보폭당 30구간으로 나눠 펼침) + 키·체중·보폭 시간을 입력으로 하는 릿지 선형회귀다. 자이로 입력의 가중치가 컸다. 8 s 동안 보폭이 없으면 기초대사(Mifflin) 값으로 바꾼다. 새 피험자에서 누적 오차 13%였고, 처음 44 s 동안은 모든 방법 중 가장 정확했다 [Confirmed, PMC8277831]. 하중 보행(체중의 10%, 20%)은 학습 자료에만 있었고, 하중 조건의 별도 검증 오차는 보고되지 않았다 [Confirmed].
- **Ingraham 2019.** 신호 16종을 비교했다. 전역 신호(HR, 피부 전기 활동)는 모르는 피험자에 약하고, 국소 신호(가속도)는 모르는 과제에 약했다. 4~5개 신호를 섞으면 성능이 좋았다 [Confirmed, 초록].
- **우리 조건과의 차이.** 0.38 g, 우주복 관절 강성, 부츠 때문에 운동학→대사 사상이 지상과 다르다. 지상 모델을 그대로 쓰면 "모델 대사"의 계통 오차가 k로 섞인다 [Inference]. 반대로 생각하면, IMU 모델은 **k의 분모(모델 예측)** 를 지형 대신 실제 보행에서 계산하는 수단이다. 생리 신호(HR, VE, VCO2)는 분자(실측)다. 둘의 비가 k다 [Inference].

### 3.5 보행 부하 예측식(군)
- **수식.** LCDA 보행식은 초록에 "1.44 + 1.94S + 0.24S" (W/kg, S m/s)로 나온다. PubMed 표시에서 지수가 빠진 것으로 보인다. 원문 지수(S^0.43, S^4로 기억)는 이번에 확인하지 못했다 [Unverified]. 경제 속도는 1.39 m/s다 [Confirmed]. Pandolf 식 M = 1.5W + 2.0(W+L)(L/W)² + η(W+L)(1.5V² + 0.35VG)와 Santee 하강 보정은 기억에 따른 것이며 이번에 원문을 보지 못했다 [Unverified].
- **정확도.** 복합 지형에서 대부분 식은 과소추정했다. Santee 보정은 편향 −13±87 W, RMSE 99 W [Confirmed, Looney 2018]. 지수 평활(계수 0.5)이 비정상 상태 추적을 개선했다 [Confirmed, Potter 2018].
- **우리 조건.** 이 식들은 귀환 반경 계산의 "모델 대사" 쪽에 해당한다. 개인 RMSE ≈ 99 W는 300~600 W 보행에서 16~33%에 해당한다. 이는 BRIEF의 개인차 ±15%와 같은 크기이거나 더 크다 [Inference, 단순 비율 계산]. 따라서 실시간 측정으로 k를 갱신하는 것이 의미가 있다.

### 3.6 휴대용 간접열량계(COSMED K5)
- **정확도.** 저~중강도에서 Douglas bag와 VO2가 ±2% 안팎으로 맞았다. 고강도 BBB에서는 과소추정했다 [Confirmed, Winkert 2020].
- **우주복 아날로그 사용.** HS3에서는 Dräger 마스크를 헬멧 안에 넣고 K5를 PLSS에 고정했다. 대사량은 Péronnet 식 EE(BTU/hr) = 60 × 3.96 × (4.039·VO2 + 1.157·VCO2)로 계산했다. 마스크 콧등 압박 문제가 보고됐다 [Confirmed, NTRS 20230002324, D.1절·B절].
- **4.3 psi 순산소에서의 한계.**
  - 개방 회로 열량계는 흡기와 호기의 O2 분율 차이와 Haldane 변환(N2 보존 가정)에 기댄다. FiO2가 60%를 넘으면 오차가 커진다는 것이 알려져 있고, 85%에서는 편향과 일치 한계가 커졌다 [Confirmed, Poulsen 2019, PubMed 30714634].
  - FiO2 ≈ 1이면 N2가 없어 Haldane 변환이 정의되지 않는다. O2 분율 차이도 거의 CO2와 수증기의 치환분이다. 그래서 O2 기반 VO2 측정은 원리적으로 맞지 않고, **VCO2 + 가정(또는 개인) RQ** 경로만 남는다 [Inference]. 이것이 EWT·IST가 환기 유량 × CO2 농도 + 개인 VCO2-VO2 회귀를 쓴 이유와도 맞다 [Inference, BRIEF 참조].
  - K5의 대기압 운용 범위는 확인하지 못했다 [Unverified].
- **결론.** K5는 EVA 중 탑재 장비가 아니라 **지상 보정용 기준기**다. 비가압 모사복에서 쓰거나, 가압 우주복이면 PLSS CO2 측정으로 대신해야 한다 [Inference].

### 3.7 피부 열류·체온
- SenseWear 계열은 강도가 오를수록 과소추정했다(총 −18.2%). 주변 온도에 따라 추정치가 달라졌다 [Confirmed, Gastin 2017; Van Hoye 2014].
- **우주복.** LCG가 피부에서 열을 직접 빼므로 피부 열류와 온도는 대사보다 LCG 입구 온도와 유량에 좌우된다 [Inference]. 대신 **LCG 열수지 자체**(유량 × ΔT)가 Apollo 방식의 대사 추정이다(BRIEF: Waligora & Horrigan 1975). 피부 열류 센서는 LCG 열수지의 보조(열 저장 추정) 이상의 역할을 기대하기 어렵다 [Inference].

### 3.8 보호복·짐 상황(우주복과 비슷한 조건)
- 군 보행 부하: 3.5절. 군 현장에서는 HR 기반 심부체온 추정(ECTemp)과 보행 불안정 지표를 결합해, 열사병 6건을 모두 붕괴 최소 3.5분 전에 식별했다. 위양성은 6.1%였다 [Confirmed, Buller 2022 초록]. 대사 추정은 아니지만, 우주복 안 실시간 상태 추정의 선례로 쓸 수 있다.
- 소방(SCBA): SCBA 착용이 HR, 땀 손실, RPE를 올린다는 메타분석이 있다 [Confirmed, PubMed 34983320 초록]. SCBA 공기 소모로 남은 시간을 예측하는 연구(체력-공기 지속시간 회귀 r=0.85, 공기 소모 60~>125 L/min)는 검색 요약에서만 봤고 원문은 읽지 않았다 [Unverified]. 그래도 "탱크 압력으로 남은 시간 예측"이라는 구조는 우리 문제와 같다.
- 임업 열 스트레스(Dubé 2016): 3.1절의 열 성분 보정이 가장 직접 재사용할 만한 결과다.

### 3.9 ISS·아날로그 사용 사례
- Bio-Monitor는 2018년 12월 ISS에 발사됐다. David Saint-Jacques가 처음 썼다. 측정 항목은 심장 박동·전기 활동, 혈압, 호흡수와 호흡량, 피부 온도, SpO2, 활동량이다 [Confirmed, CSA Bio-Monitor 페이지].
- Astroskin은 HERA 30일 임무에서 24시간 감시에 쓰였다. 승무원은 여성용 의복 지지 문제와 SpO2 머리띠의 불편을 지적했다 [Confirmed, NTRS 20190000238]. 2017 HRP 워크숍 자료는 Astroskin의 센서(3축 가속도, 3유도 ECG, 호흡량·분당환기, SpO2, 혈압 계산값, 피부 온도)를 열거하고, HERA 시험으로 "TRL 5 → 6"을 목표로 했다 [Confirmed, NTRS 20190001996 p.3, p.7].
- NASA ARC 포스터는 Astroskin이 "우주복 아래에 편하게 입을 수 있다"고 적고 EVA 적용을 미래 과제로 언급했다. 15초 평균 HR의 상관은 r=0.989, 호흡수는 r=0.709였다(4명, 안정·회전의자 조건) [Confirmed, NTRS 20150021842].
- Hexoskin/Astroskin이 **가압 우주복 안 EVA** 에서 쓰였다는 1차 자료는 찾지 못했다. 검색 결과가 없다는 것이 사례가 없다는 뜻은 아니다 [Unverified].
- HI-SEAS 2020 모의 달 임무에서 Hexoskin HR로 총 에너지 소비를 계산하고, 우주복을 입은 운동으로 검증할 계획이었다는 IAC 초록이 검색에 나왔다. 원문은 읽지 않았다 [Unverified].

### 3.10 우주복 적용 제약 정리
| 제약 | 영향받는 방법 | 내용 | 근거 |
|---|---|---|---|
| 4.3 psi 순산소 | K5류 O2 분율 열량계, HR·VE 보정 곡선 | Haldane 변환 불능. 경미한 고산소로 HR·VE와 VO2의 관계가 바뀔 가능성 | [Confirmed] FiO2 >60% 오차(Poulsen 2019); 나머지 [Inference] |
| 헬멧 내부 기류 | 마스크형 측정 | 헬멧 안 마스크는 HS3에서만 가능(비가압). 가압복에서는 PLSS 루프 CO2로 대신 | [Confirmed] HS3; [Inference] |
| 냉각복 | 피부 온도·열류 | 신호가 LCG 설정에 지배됨 | [Inference] |
| 심박 표류(열·탈수) | HR 기반 전부 | 45분에 HR +12%, VO2는 약간만 증가. 원시 HR은 평균 30% 과대추정 | [Confirmed] Wingo 2005, Dubé 2016 |
| 착용 위치 | 셔츠, IMU | 셔츠는 LCG 아래(피부 밀착). 다리 IMU는 하체 우주복 안. 배선과 전원은 PLSS 연동 필요 | [Inference]; 여성 의복 지지 문제 [Confirmed, HERA] |
| 0.38 g + 우주복 관절 | IMU 보행 모델, 보행 예측식 | 운동학→대사 사상 재학습 필요 | [Inference] |
| 교신·말하기 | 호흡 신호 | VE·fR 오염 | [Inference] |

### 3.11 k와 누설 분리 구조(제안, 검증 전)
[Inference] 아래는 확인한 문헌들을 조합한 설계 가설이다. 성능은 검증하지 않았다.
- 상태 x = [M(t)(대사, W), L(t)(누설, kg/s), d(t)(HR 표류)].
- 관측:
  - ① 탱크 압력 미분: ṁ_O2 = M/(c_O2) + L. c_O2는 RQ에 따른 O2 1 g당 에너지다.
  - ② PLSS VCO2(Ogilvie 2026이 개발 중인 CO2 센서와 환기 유량계): M에만 의존.
  - ③ HR = a_i + b_i·M + d(t). a_i, b_i는 지상 보정값, d는 랜덤워크로 둔다.
  - ④ 셔츠 VE = e_i·M.
  - ⑤ LCG 열수지 = M − 열 저장 − 외부 열.
- k(t) = M̂(t) / M_model(속도, 경사, 하중)이다. M_model은 IMU 보행 또는 LCDA/Pandolf 식으로 계산한다.
- 누설은 ①에만 나타나고 ②~⑤에는 나타나지 않는다. 그래서 몸 쪽 관측이 많을수록 L의 식별성이 좋아진다. ②가 있으면 HR·VE는 지연과 잡음을 줄이는 보조 관측이 된다. ②가 없거나 고장 나면 HR·VE가 주 관측이 된다.

## 4. 구현·코드·데이터

| 자원 | 내용 | 라이선스·활동 | 분류 |
|---|---|---|---|
| Slade 2021 코드·데이터, https://simtk.org/projects/energy-est | IMU 보행 대사 추정 코드와 재현 자료(논문 Code/Data availability) | SimTK 라이선스와 마지막 활동은 확인 못 함 [Unverified]. 논문에 언급된 GitHub 미러 URL도 확인 못 함 | **Extend**: 0.38 g와 우주복 보행 자료로 재학습 필요 |
| Sarvibabakhani/deeplearning-biosignals-ee (GitHub) | Babakhani 2025 프리프린트의 DL 모델 | `gh api`: license null(명시 없음), pushed_at 2025-11-21, 별 1개 [Confirmed] | 참고만. 라이선스가 없으므로 코드 재사용 불가. 방법론만 **Build** 참고 |
| Ingraham 2019 데이터셋 | 10명, 6개 활동, 16개 신호 + 간접열량계 | 공개 위치와 라이선스는 이번에 확인 못 함 [Unverified] | 사전 학습·벤치마크용 후보 |
| Pandolf/Santee/LCDA 식 | 공개 식 | 논문 식이라 라이선스 문제 없음 | **Adopt**: 모델 대사의 기준선. 지면 계수 η는 화성 레골리스에 맞게 따로 정해야 함 |
| Vogt 열 성분 보정, Flex-HR | 공개 절차 | 해당 없음 | **Adopt + Extend**: 휴식 구간 기반 보정 |
| ECTemp(Buller 2013) 칼만 필터 | HR → 심부체온 | 공개 코드는 확인 못 함 [Unverified] | 논문 식으로 **Build** |

`gh api "search/repositories?q=metabolic+energy+expenditure+wearable"` 검색에서는 관련성 낮은 저장소 1개만 나왔다. 저장소가 없다는 증거는 아니다.

## 5. 막힌 원문 목록, 추가 확인이 필요한 항목

막혔거나 읽지 못한 원문
- CSA 페이지 첫 접속은 ECONNRESET이었고, 다시 시도해 일부를 읽었다. space.com 기사는 본문이 잘려 읽지 못했다.
- Looney 2019 LCDA 원문(지수 확인 필요), Pandolf 1977, Santee 2003 원문: 이번 세션에서 열지 않음.
- Dubé 2016, Vogt 1970/1973 원문: 열 성분 보정식의 세부 형태 확인 필요.
- HI-SEAS Sensoria M3 IAC 원문(PMC8115028 포함): 우주복 운동 중 Hexoskin 검증 결과.
- SCBA 공기 소모 예측 연구 원문.

추가 확인이 필요한 항목
1. 4.3 psi 순산소(고산소)가 아최대 운동의 HR-VO2, VE-VO2 관계를 얼마나 바꾸는가. 이것으로 지상 공기 호흡 보정을 옮겨 쓸 수 있는지가 정해진다.
2. 가압 우주복 안에서 호흡 셔츠의 일회호흡량 정확도(HUT 접촉, LCG 겹침).
3. Hexoskin/Astroskin의 EVA(가압복) 사용 1차 기록이 있는지.
4. 0.38 g 우주복 보행에서 IMU 모델의 오차. ARGOS 자료가 있다면 NASA H-3PO 문헌을 확인해야 한다.
5. Hoffmann 2021의 HR 표류 결과와 Wingo·Dubé의 지상 결과가 같은 방향·같은 크기인지.

결론을 바꿀 조건
- PLSS CO2·환기 측정의 잡음이 30분 미만 창에서도 충분히 작다면, 웨어러블은 보조 관측(빠른 응답, 고장 대비)으로 역할이 줄어든다.
- 반대로 CO2 센서가 지연되거나 드리프트가 크면, 개인 보정 HR+VE+IMU 융합이 주 관측이 된다.

## 6. 참고문헌 (이번 세션에서 실제로 연 것만)

PubMed 초록(메타데이터)
- Livingstone MB et al. 1990, Am J Clin Nutr 52:59. https://doi.org/10.1093/ajcn/52.1.59 (PMID 2193501)
- Leonard WR 2003, Am J Hum Biol 15:479. https://doi.org/10.1002/ajhb.10187
- Villars C et al. 2012, J Appl Physiol 113:1763. https://doi.org/10.1152/japplphysiol.01413.2011
- Silva AM et al. 2014, Eur J Clin Nutr 69:20. https://doi.org/10.1038/ejcn.2014.51
- Ladlow P et al. 2019, PLoS One 14:e0209249. https://doi.org/10.1371/journal.pone.0209249
- Chowdhury EA et al. 2017, PLoS One 12:e0171720. https://doi.org/10.1371/journal.pone.0171720
- Dubé PA et al. 2016, Appl Ergon 54:148. https://doi.org/10.1016/j.apergo.2015.12.005
- Hebestreit H, Bar-Or O 1998, Eur J Appl Physiol 78:7. https://doi.org/10.1007/s004210050380
- Wingo JE et al. 2005, Med Sci Sports Exerc 37:248. https://doi.org/10.1249/01.mss.0000152731.33450.95
- Smith CM et al. 2019, J Occup Environ Med 61:e104. https://doi.org/10.1097/JOM.0000000000001537
- Elliot CA et al. 2019, J Strength Cond Res 33:1437. https://doi.org/10.1519/JSC.0000000000002005
- Villar R et al. 2015, Appl Physiol Nutr Metab 40:1019. https://doi.org/10.1139/apnm-2015-0140
- Montes J et al. 2018, Int J Exerc Sci 11:806. https://doi.org/10.70252/YPHF4748
- Beltrame T et al. 2016, J Appl Physiol 121:1226. https://doi.org/10.1152/japplphysiol.00600.2016
- Beltrame T et al. 2017, J Appl Physiol 124:473. https://doi.org/10.1152/japplphysiol.00299.2017
- Ingraham KA et al. 2019, J Appl Physiol 126:717. https://doi.org/10.1152/japplphysiol.00714.2018
- Slade P et al. 2021, Nat Commun 12:4312. https://doi.org/10.1038/s41467-021-24173-x (본문 PMC8277831도 읽음)
- Winkert K et al. 2020, Med Sci Sports Exerc 52:1153. https://doi.org/10.1249/MSS.0000000000002241
- Crouter SE et al. 2019, PLoS One 14:e0226290. https://doi.org/10.1371/journal.pone.0226290
- Poulsen MK et al. 2019, Nutr Clin Pract 34:767. https://doi.org/10.1002/ncp.10250
- Looney DP et al. 2018, Mil Med 183:e357. https://doi.org/10.1093/milmed/usx099
- Potter AW et al. 2018, Med Sci Sports Exerc 50:2145. https://doi.org/10.1249/MSS.0000000000001669
- Looney DP et al. 2019, Med Sci Sports Exerc 51:346. https://doi.org/10.1249/MSS.0000000000001779
- Richmond PW et al. 2019, Appl Ergon 74:48. https://doi.org/10.1016/j.apergo.2018.08.017
- Sol JA et al. 2018, Wilderness Environ Med 29:304. https://doi.org/10.1016/j.wem.2018.03.006
- Li J et al. 2022 (SCBA 메타분석), Int J Occup Saf Ergon 29:77. https://doi.org/10.1080/10803548.2021.2024020
- Gastin PB et al. 2018, J Sci Med Sport 21:291. https://doi.org/10.1016/j.jsams.2017.07.022
- Van Hoye K et al. 2015, J Sports Sci 33:1007. https://doi.org/10.1080/02640414.2014.981846
- Buller MJ et al. 2013, Physiol Meas 34:781. https://doi.org/10.1088/0967-3334/34/7/781
- Buller M et al. 2022, Br J Sports Med 56:446. https://doi.org/10.1136/bjsports-2021-104081
- Hadid A et al. 2025, Lancet Digit Health 7:100886. https://doi.org/10.1016/j.landig.2025.100886 (Astroskin 착용 사례)

본문을 직접 읽은 웹 문서
- Gastinger S et al. 2010, J Sports Sci Med 9:110. https://pmc.ncbi.nlm.nih.gov/articles/PMC3737974
- Lu K et al. 2018, Sensors 18:3092. https://pmc.ncbi.nlm.nih.gov/articles/PMC6164120
- Babakhani S et al. 2025, arXiv:2511.09276 (프리프린트). https://arxiv.org/html/2511.09276v1
- CSA Bio-Monitor. https://www.asc-csa.gc.ca/eng/sciences/bio-monitor.asp

NASA NTRS(원문 PDF와 추출 텍스트는 `research/sources/`에 저장)
- Kumar A et al. 2015, Evaluation of the Accuracy of Astroskin…, NTRS 20150021842 → `Astroskin_accuracy_NTRS20150021842.{pdf,txt}`
- Toscano W et al. 2017 HRP IWS, Wearable Biosensor Monitor…, NTRS 20190001996 → `Astroskin_HERA_NTRS20190001996.{pdf,txt}`
- DeLeon R et al., Wearable Biosensor Monitor… (HERA), NTRS 20190000238 → `Astroskin_HERA_NTRS20190000238.{pdf,txt}`
- HS3, ICES 2023, NTRS 20230002324 → `HS3_ICES2023_NTRS20230002324.{pdf,txt}`
- APACHE Physical Workload Approximation, ICES 2022, NTRS 20220003008 → `APACHE_ICES2022_NTRS20220003008.{pdf,txt}`
- Considerations for Health and Performance During Surface EVA, NTRS 20230015332 / 20240005165 (초록만)
- Hoffmann 2021, NTRS 20210024317 (기존 파일 `Hoffmann2021_NTRS20210024317.txt`에서 R² 문장 확인)

GitHub
- `gh api repos/Sarvibabakhani/deeplearning-biosignals-ee` (license null, pushed 2025-11-21)
