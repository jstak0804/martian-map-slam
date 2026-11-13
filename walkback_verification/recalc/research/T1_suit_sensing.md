# T1. 우주복·PLSS 센서와 대사량·산소 소모 계산법

작성일 2026-11-09. 증거 표시는 BRIEF.md를 따른다. 원문 사본과 추출 텍스트는 `research/sources/` 에 있다. "논문이 조건 Y에서 X를 보고했다"는 그 논문의 결과일 뿐이며, 우리 시스템의 기대 성능이 아니다.

## 1. 요약

- ISS/셔틀 EMU가 실시간으로 대사량을 계산하는 근거는 **1차 산소 탱크 압력 감소율 하나뿐**이다. 공식은 `MR[Btu/hr] = 581 × (psi/min)`이고 누설은 보정하지 않는다. 냉각수 사용량은 EVA 중에 알 수 없다. LCVG 입출구 온도도 지상에서 볼 수 없다 [Confirmed, JSC-20597 §2.1, §2.7, App. C].
- EMU 탱크 압력 센서의 사양은 0–1100 ±27.5 psia이다. 12비트 변환 중 절반 범위만 써서 1카운트는 약 0.54 psi로 추정된다. 이 경우 1분 창의 양자화 오차는 약 ±90 W, 10분 창은 약 ±9 W이다 [Inference]. Apollo가 "30분 미만 구간은 잡음이 크다"고 한 것과 맞는다.
- 누설과 대사를 구분하는 방법은 운용 중인 우주복에 없다. 원리상 가능한 방법은 "O2 공급량 − VCO2/RQ"와 "냉각수(열) 기반 대사량과 O2 기반 대사량의 비교"이다. RQ 불확실성(±0.1)은 450 W에서 약 13 g O2/h에 해당하고, EMU 누설 사양(약 4 g/h)보다 크다. 따라서 큰 누설만 검출할 수 있다 [Inference].
- 화성 PLSS용으로 개발 중인 센서는 세 가지다. M-PALSS(O2 ±1 %, CO2 ±0.3 mmHg, t90 3 s / 10–12 s, 1 Hz 이상), 연속 환기 유량계(요구 정확도 ±1 % FS = 1.7 L/min), 유연 물주머니 부피 센서(약 2.5–5 % FS)이다. 셋 다 비행 실적은 없다 [Confirmed, 시험 보고].
- 귀환 반경 계산에 쓸 실시간 k 추정의 현실적인 구성은 다음과 같다. 기본은 O2 압력 감소율(긴 창)에 사전 누설 점검값을 빼는 것이다. 여기에 심박(짧은 창, 개인 보정)을 더하고, 차세대 센서가 있으면 VCO2(유량 × CO2)와 냉각수 부피를 함께 넣어 융합한다 [Inference].

## 2. 후보 방법 표

| 방법 | 측정하는 물리량 | 필요한 센서 | 시간 분해능·지연 | 보고된 정확도(조건 포함) | 대사·누설 구분 | 비행 실적·TRL | 근거·출처 |
|---|---|---|---|---|---|---|---|
| A. O2 탱크 압력 감소 | 공급된 O2 질량 = 대사 O2 + 누설 | 1차 O2 탱크 압력(+탱크 온도) | EMU CWS: 1분 차분, 6 s마다 갱신, 1/16 지수 필터. 지상 다운링크는 약 2분 주기 | Apollo 12: EVA 전체 평균 953 Btu/h. 오차표: 압력 1 psi당 2, RQ 0.01당 2, 누설 1 cc/min당 1 Btu/h(3.85 h 평균). 짧은 창(30분 미만)은 잡음이 크다 | 구분하지 못한다. 누설은 사전값으로 가정한다 | Apollo·셔틀·ISS에서 운용(TRL 9) | [Confirmed] Carson NTRS 19720019460 표 4.9–4.10; Waligora 1975 p.777–778; JSC-20597 §2.1, §2.3; Cox 2024 p.7 |
| B. LCG/LCVG 열수지 | 냉각수가 가져간 현열 + 환기 잠열 | LCG 입구 온도, ΔT, 유량(펌프 곡선으로 추정), 환기 유량, 이슬점 | 분 단위. 체열 저장 때문에 지연된다 | Apollo 12: 입구 이슬점 가정에 따라 915–1060 Btu/h. 오차표: ΔT 0.1°F당 25, 유량 0.1 lb/min당 6, 이슬점 1°F당 20, 열저장 100 Btu당 25 Btu/h | 구분한다. 누설은 열에 영향을 주지 않는다. 대신 환경 열 누설과 체열 저장이 오차가 된다 | Apollo에서 운용. ISS EMU에는 해당 텔레메트리가 없다 | [Confirmed] Carson 표 4.5–4.6; JSC-20597 §2.7 |
| C. 냉각수(급수) 소비량 | 증발·승화한 물의 질량 → 전체 열부하 | 물탱크 부피(Apollo는 사후 계량, 차세대는 연속 부피 센서) | Apollo·EMU는 EVA 후에만 알 수 있다. 연속 센서는 실시간이지만 정확도 % FS가 창 길이를 제한한다 | Apollo 12: 894 Btu/h. 오차: 계량·잔류수 0–130, 열누설 ±100당 ±75 Btu/h. Creare 센서: 시험 조건에서 약 5 % FS(2019), 약 2.5 % FS(2022) | 구분한다(열만 반영). 대신 환경 열 입력과 섞인다 | Apollo는 사후 확인만 했다. 부피 센서는 지상 시험 단계 | [Confirmed] Carson 표 4.7–4.8; NTRS 20210024203 초록(2.5 %). [Unverified] ICES-2019-401의 5 %는 검색 요약에서만 봄(TTU-IR 403) |
| D. VCO2 = 환기 유량 × CO2 농도(+RQ) | CO2 생산량 → 대사량 | 환기 유량계, 흡수기 전·후 CO2 센서 | 수 초–수십 초. CO2 t90은 10–12 s | NBL·EWT·IST(개루프 탯줄)에서 운용. RER을 0.85로 가정한 뒤 통계식으로 보정한다. 비행 PLSS(폐루프)에서 쓴 사례는 찾지 못했다 | O2 공급량과 결합하면 누설 = 공급 − VCO2/RQ로 구할 수 있다 | 지상 시험 시설 TRL 9. PLSS 탑재형은 개발 중 | [Confirmed] Cox 2024 p.4–5; Norcross TP-2009-214796 p.~9 |
| E. 심박 회귀 | 심박 → 개인별 사전 보정 곡선 | ECG 또는 가슴 띠 | 초 단위(EMU는 EKG 약 100 s 구간 다중화) | Hoffmann 2021: 셔틀·ISS EVA 자료에서 전체 R² 0.40, 개인 회귀 R² > 0.82, RMSE < 200 Btu/h 목표 | 구분한다(누설 영향 없음). 대신 심리·열 요인과 drift가 있다 | 모든 프로그램에서 운용. 단독 사용은 비권장 | [Confirmed] Hoffmann 2021 p.1–4; Waligora 1975; Paul 2012 p.1, p.10 |
| F. 다중 측정 융합 | A·B·C·D·E 가중 결합 | 위 센서들 | 짧은 창은 심박, 긴 창은 O2·물 | Apollo는 "주관적 통합"을 했다. Feiveson 등(2009)은 요인분석 + OLS + LOWESS로 스파이크 민감도가 낮아졌다고 보고했다(초록만 확인) | 구조상 가능하다 | 연구 단계 | [Confirmed 초록] NTRS 20090042588; Paul 2012 p.10 |
| G. 사전 확률 + 실측 적분(PersEIDS) | 누적 대사량, 남은 과업 예측 분포 | A 또는 E가 주는 대사량 입력 | 1 Hz(시연에서는 심박 변환값 사용) | 시연 1건. 성능 일반화는 불가하다고 저자가 명시했다 | 구분하지 않는다(대사량 입력을 그대로 받음) | 연구 도구 | [Confirmed] McGrath ICES-2023-327 Eq.(1), §VI–VII |

## 3. 방법별 상세

### 3.1 센서 현황(실제·계획)

**ISS/셔틀 EMU (eCWS, JSC-20597 Rev B CPN-1, 2010)** [Confirmed, 표 1.4-1, 1.4-5, 1.7, 2.1]
- 1차 O2 탱크 압력(item 112): 0–1100 ±27.5 psia. SOP 압력(215): 0–7400 ±259 psia. 수트 압력(114): 0–6 ±0.15 psid. 승화기 급수 압력(138): 0–16 ±0.4 psia. 물주머니 기체/물 압력(132A/B): 0–40 ±1.0 psia. 승화기 출구 온도(139): ±1.5°F.
- CO2(122): 적외선(NDIR) 방식, 0–30 ±2.0 mmHg이며 출력은 비선형이다. 8 psia에서 교정하고 수트 압력으로 보정한다(`보정계수 = 0.2196 × P_abs^0.7221`). 4.3 psia에서 화면에 8.0 mmHg로 표시될 때 실제 값은 6.4–9.6 mmHg이다(약 ±20 %).
- 환기 유량은 연속 측정이 아니다. 3.7–5.4 CFM 사이에서 켜지는 **유량 스위치**뿐이다. 문서 원문: "neither the EMUs nor the vehicles contain flow meters"(§2.2).
- **O2 탱크 온도 센서, LCVG 입출구 온도, 물 잔량 센서는 아날로그 입력 목록에 없다.** 물은 "기체압 − 물압 > 2.1 psi"일 때 30분 카운트다운을 시작하는 방식뿐이다(1000 Btu/h 가정). 원문: "There is no insight into the water usage rate during an EVA"(App. C), "The EMU flight controller has no way of obtaining ... ΔT across the sublimator"(§2.7).
- 샘플링·텔레메트리: 아날로그 신호는 200 ms마다 읽고 9:1 필터를 거친다. 다운링크는 50 baud, COMBO 모드에서 EKG 100.84 s와 EMU 데이터 19.16 s를 번갈아 보내므로 EMU 프레임은 약 2분에 1회 온다. 직렬 포트는 4800 baud이다.
- A/D 변환: 압력 센서는 0–5 V를 출력하지만 변환은 "counts × 10 V/4096"이다. 따라서 실제로 쓰는 카운트는 약 2048개이고, 1차 O2 1카운트는 약 0.54 psi이다 [Inference, 표 1.4-5에서 계산].

**xEMU/xPLSS (DVT, SxEMU 열진공 시험)** [Confirmed]
- O2 탱크(POV) 압력 PT-112와 탱크 온도 TS-110이 있다. SOV는 PT-215이다. 공칭 충전 압력은 3000 psia이고, 탱크와 중간단 센서의 정격은 6000 psia이다(Ogilvie & Campbell ICES-2023-027 §F; Whalen ICES-2024-130 Fig.14).
- 시험 중 PT-112는 감압 중에 지시값이 오르는 이상을 보였고 원인은 센서 오류로 추정되었다. EVA 중에는 정상적으로 감소했다(Whalen §III.3).
- CO2는 NDIR 센서이며 xPLSS 소프트웨어가 압력 보정을 한다. 시험 중 약 8시간 동안 연속 측정했다(Whalen §III.3).
- 사전 누설 점검: POR을 0.9 psid로 내려 압력 감소를 보는 시험을 EVA 전에 두 번 한다(ICES-2023-027 절차 5, 12). POR의 시트 누설 요구는 25 sccm이다.
- **xPLSS 탱크 압력 센서의 정확도, 분해능, POV 부피는 확인하지 못했다** [Unverified].

**계획·개발 중 센서(Mars PLSS 포함)** [Confirmed]
- M-PALSS(Makel, ICES-2023-053, ICES-2025-222): 전기화학식 O2·CO2·CO, NDIR CO2, 정전용량 습도, 압저항 압력 센서를 묶은 장치다. 요구 정확도는 O2 1 %, 상대습도 1 %, CO2 0.3 torr이다. 결론에서 보고한 불확도는 CO2 약 ±0.3 mmHg, O2 약 ±1 %이다(3.5 psia 시험). t90은 O2 약 3 s, 전기화학식 CO2 10–12 s이다. 출력은 1 Hz 이상, 전력 목표는 2.5 W 미만이다. 기존 EMU NDIR 센서는 약 2 W, 2.3×2.2×6.1 in이다. **장기 drift는 아직 시험하지 않았다**(다년 시험을 계획 중). 저자는 용도를 "situational awareness"로 한정했다.
- 환기 유량계: 기존 EMU에는 유량 스위치만 있었다(NTRS 20170005909 p.14; ICES-2026-126 §16). Creare FMHX(ICES-2018-192)의 요구 정확도는 170 L/min 범위에서 ±1 % FS(1.7 L/min)이고, 차압 센서 선형성은 R² 0.9993으로 보고되었다. Mars PLSS는 차압 센서 하나로 "rough flow rate"만 얻을 가능성도 열어 두었다(ICES-2026-126 §16).
- 물주머니 부피 센서(Creare/Ramsey): 음향 방식이다. ICES-2019-401은 EVA 모사 조건에서 약 5 % FS를 보고했다고 검색 요약에 나온다([Unverified], TTU-IR 403으로 원문 못 엶), ICES-2022 Chullen & Ramsey는 약 2.5 % FS를 보고했다(NTRS 20210024203 초록). Mars PLSS 문서는 "continuous volume sensing throughout the entire EVA"를 목표로 한다(ICES-2026-126 §12). 기존 EMU 방식(보조 주머니가 열릴 때 압력 변화로 감지)은 비상 경보 수준이고 신뢰성 문제가 있다고 적혀 있다.
- Vista Photonics 레이저 다이오드 CO2/H2O 센서(ICES-2016): 3–25 psia 전 범위에서 EMU보다 높은 정확도를 목표로 했다. 초록만 확인했다.

### 3.2 A. O2 압력법(현행 ISS 방법)

공식 [Confirmed, JSC-20597 App. C-11–C-12]:
```
m_O2[lb]   = ΔP[psi] × 144 × (480/1728) × 32 / (1546 × (T_F + 460))   # T=60°F → 0.001592198 lb/psi
lb O2/Btu  = 1.708e-4 − (RQ − 0.707) × 1.231e-5 / 0.293                # Hamilton ANL 88-333, RQ=0.87 → 1.6396e-4
MR[Btu/hr] = 582.66 × (O2 use rate, psi/min)                             # 작업표에서는 581 사용
```
- CWS 알고리즘 [Confirmed, §2.1]: `R1` = 지난 1분 동안의 탱크 압력 변화(6 s마다 갱신, 10 psi/min 초과 시 1 s마다). `R2_new = 15/16·R2_old + 1/16·R1filt`. 남은 시간 `= (PO2 − 75)/R2`. 사용률이 0.3 psi/min 미만이면 0.3으로 둔다. EVA 첫 10분 등에는 1.5 psi/min을 가정한다.
- 이 공식에는 누설 항이 없다. 핸드북의 원문은 "directly proportional (assuming no suit pressure integrity failures)"이다(§2.3-6). 누설 사양은 50 sccm = 0.0087 lb/h(§2.3, §2.4)이고, 1000 Btu/h에서 대사 O2는 0.1625 lb/h이다. 즉 사양 상한의 누설은 약 53 Btu/h(약 16 W)를 대사로 잘못 세게 만든다 [Inference, 계산]. 탱크 크기는 30 scc/min 누설을 가정해 정했다(§2.3).
- Apollo [Confirmed, Carson 표 4.9–4.10]: Beattie형 압축계수(Z 0.974/0.987)를 쓰고 사전 누설 0.0044 lb/h를 뺐다. 그런데 비행 후 측정한 누설은 0.0169 lb/h였다. 차이 0.0125 lb/h는 약 77 Btu/h(약 23 W)에 해당한다 [Inference, 계산]. Waligora(1975)는 Apollo 사양의 최대 누설을 대사량 약 50 kcal/h(약 58 W)에 해당한다고 썼다.
- 분해능 오차 예산 [Inference, EMU 수치로 계산]: 300/450/600 W는 각각 1.76/2.64/3.52 psi/min이다. 1카운트(0.54 psi) 차분 오차는 창 길이에 따라 1분 약 92 W, 2분 46 W, 5분 18 W, 10분 9 W, 30분 3 W이다. 탱크 온도가 10°F 변하면 압력이 약 1.9 % 변한다(500 psi에서 약 9 psi, 450 W 기준 약 3.6분 분량). EMU에는 탱크 온도 센서가 없어 60°F로 고정 가정한다. 화성의 낮밤 열환경에서는 온도 보정이 필요하다(xEMU는 TS-110 보유).
- 화성 조건과의 차이: 이 방법은 순산소 4.3 psia 수트에서도 원리가 같다. 다만 xEMU 탱크는 3000 psia로 고압이라 같은 상대 정확도에서 psi당 질량이 다르다. 센서 % FS가 같다면 분해능의 질량 환산값은 탱크 부피와 FS에 따라 달라지므로 다시 계산해야 한다 [Inference]. RQ 영향은 작다. RQ 0.7–1.0 범위에서 Btu당 O2 차이는 약 8 %이다 [Inference, 위 공식으로 계산].

### 3.3 B. 열수지법

```
Q_TL + Q_VENT = Q_MET + Q_HL − Q_ST
Q_TL = ṁ_TL · c · ΔT_LCG ;  Q_VENT = ṁ_O2 · Δh   (현열은 무시)
```
[Confirmed, Carson Fig.4.10, 표 4.5–4.6] 유량은 펌프 압력상승–유량 곡선과 LCG 압력강하 곡선에서 추정했다. 입구 이슬점은 가정값이다. 오차표는 2절 표와 같다.
- 화성 조건: 대기가 있어 대류·전도 열누설(Q_HL)이 진공보다 크고 시간에 따라 변한다. 0.38 g 걷기에서는 체열 저장(Q_ST)이 과도기에 크다. LCVG ΔT와 유량을 연속 측정하는 센서는 Mars PLSS 문서의 개발 목록에 명시되어 있지 않다(유량계는 환기 루프용) [Confirmed: ICES-2026-126 §12–16 확인. 해당 항목 없음].

### 3.4 C. 냉각수 소비법

```
Q_MET = [m_FW (h_c − c(T_FW − 32)) − Q_ELEC] / (1.276 t)     # Apollo, Btu/hr, h_c = 1075.8 Btu/lb
```
[Confirmed, Carson 표 4.7] 1.276은 LiOH 반응열 등을 묶은 계수이다(유도는 원문에 있음). EMU는 0.8 lb/h(LiOH) 또는 1.0 lb/h(METOX)를 가정하고, STS-61 실측 평균은 0.72 lb/h였다(JSC-20597 §2.7, App. C).
- 연속 부피 센서의 열량 분해능 [Inference]: `오차_W ≈ (정확도 % FS × 주머니 용량[kg] × 2.4 MJ/kg) / 창 길이[s]`. 예를 들어 용량이 4 kg이고 2.5 % FS라면 0.1 kg(약 0.24 MJ)이므로 1시간 창에서 약 67 W, 4시간 창에서 약 17 W이다. **xEMU FSA 용량은 확인하지 못해 4 kg은 가정이다.** 오프셋형 오차라면 차분에서 상쇄되므로 실제 기울기 오차는 더 작을 수 있다. 이것은 확인이 필요하다.
- 이 방법이 우리 문제에 특히 유용한 이유는 냉각수 잔량이 그 자체로 귀환 반경의 두 번째 제약이라는 점이다. 측정값을 모델에 넣지 않고 잔량에 바로 쓸 수 있다.

### 3.5 D. VCO2 법과 누설 분리

- NBL 지상 운용 [Confirmed, Cox 2024 p.4–5]: 탯줄 배기의 CO2 농도(Vaisala GMP252)와 공급 유량을 곱해 VCO2를 구한다. RER을 0.85로 가정하고 `MR_adj = exp[(ln MR_RER + 1.642327)/1.231614]`로 보정한다. Weir형 에너지식을 쓰지만 포스터 텍스트 추출이 일부 깨져 계수 확인이 필요하다. NBL 대사량은 비행보다 100–300 Btu/h 높아 0.84 배율을 쓴다.
- EWT/IST [Confirmed, Norcross TP-2009-214796]: 환기 유량 × 배기 CO2(AEI CD-3A)에 개인별 VCO2–VO2 회귀를 더해 구했다. 저자는 "O2 분석기를 넣으면 정확도가 오르고, 출구 유량 센서를 넣으면 누설을 정량할 수 있다"고 권고했다.
- PLSS(폐루프) 적용 [Inference]: `VCO2 = Q_vent × (x_CO2,흡수기 입구 − x_CO2,흡수기 출구) + V_suit · d(x_CO2)/dt`. 따라서 흡수기 앞뒤 CO2와 유량이 필요하다. EMU CO2 센서는 흡수기 돌파(breakthrough) 경보 용도로 쓰였다. 위치가 흡수기 하류라면 VCO2를 직접 줄 수 없다. 센서 위치는 문서에서 직접 확인하지 못했다 [Unverified].
- 누설 분리 [Inference]: `ṁ_leak = ṁ_O2,supply − VCO2/RQ`. 450 W에서 VO2는 약 114 g/h이고, RQ ±0.1은 ±13 g/h이다. 여기에 유량 ±1 % FS(170 L/min 기준 1.7 L/min)와 CO2 ±0.3 mmHg가 더해진다. 0.3 mmHg는 4.3 psia(222 mmHg)에서 몰분율 약 0.14 %p이고, 출구 CO2가 5–8 mmHg일 때 상대 오차 4–6 %이다. 결과적으로 수 g/h 수준의 사양 누설은 분리할 수 없고, 수십 g/h 이상의 이상 누설은 검출할 수 있다. 개인별 RQ 사전 보정(운동 부하 시험)을 하면 RQ 항을 줄일 수 있다.
- 다른 분리 수단 [Confirmed 절차 / Inference 해석]: (1) EVA 전 수트 누설 점검(POR 0.9 psid 압력 감소)에서 누설 사전값을 얻는다. (2) 열 기반 추정(B, C)은 누설에 영향받지 않으므로, O2 기반 추정과의 차이를 누설 + RQ 오차로 볼 수 있다. 이를 위한 추정 모형(예: 상태 [k, leak] 칼만 필터)은 문헌에서 찾지 못했다. 검색이 비었다고 해서 문헌이 없다는 뜻은 아니다.

### 3.6 E·F·G. 심박, 융합, PersEIDS

- 심박: Hoffmann 2021은 셔틀·ISS EVA(2006–2015)에서 2분 간격 O2 압력 기반 대사량과 20 s 간격 심박을 썼다. 전체 회귀 R²는 0.402, 개인 회귀 R²는 0.82 이상이었다 [Confirmed]. Apollo 15–17 사령선 EVA에서는 심박이 심리적 요인으로 올라간 것으로 보였다(Waligora 1975 [Confirmed]).
- 융합: Feiveson 등은 Constellation 설계가 "heuristic하게 4개 측정을 결합하고, 충돌하는 자료는 버린다"고 기술했다 [Confirmed 초록, NTRS 20090042588]. 본문은 확인하지 못했다.
- PersEIDS: `M̂_T ~ M̃_t + R_c(d_c − d̃_c) + Σ_{i>c} R_i d_i`. 각 과업의 대사율 사전분포는 가우시안이고 서로 독립으로 둔다. CDF를 소모 한도에서 평가한다 [Confirmed, ICES-2023-327 Eq.1]. 우리 "귀환 반경"의 확률적 버전과 구조가 같다. 다만 누설과 k를 따로 다루지는 않는다.

### 3.7 우리 조건(화성, 0.38 g, 4.3 psi 순산소, 300–600 W)과의 차이 정리 [Inference]

- 화성 대기 0.15 psia CO2: 탱크 압력법과 수트 내부 센서에는 영향이 거의 없다. 열수지와 물 소비에는 환경 열이 섞인다.
- 통신 지연: 지상 관제가 2분 주기 텔레메트리로 계산하는 현행 구조는 쓸 수 없다. 수트나 IV 승무원 쪽에서 계산해야 한다(PersEIDS의 동기와 같음).
- 걷기 300–600 W에서 O2 압력법은 5–10분 창이면 분해능 오차가 수 %로 내려간다. k를 ±15 % 수준으로 구분하려면 몇 분 이상의 창이 필요하다(정확한 값은 xPLSS 센서 사양이 정해진 뒤 다시 계산).

## 4. 구현·코드·데이터

| 대상 | 내용 | 라이선스·활동 | 분류 |
|---|---|---|---|
| JSC-20597 공식(581 × psi/min, CWS 필터, 탱크 질량식) | 문서 공식이다. 코드가 아니다 | NASA 문서(ibiblio 사본) | **Build**: 공식을 그대로 옮겨 구현 |
| Carson/Apollo 3방법 공식 | 문서 공식 | NTRS 공개 | **Build** |
| PersEIDS 모형 | 공개 코드를 찾지 못함 | — | **Build**: Eq.(1)만 참고 |
| SUITS-Techteam/TSS2026 | NASA SUITS 대회용 텔레메트리 시뮬레이터(C). `oxy_consumption`(psi/min) 등 합성 텔레메트리 필드가 있다 | `gh api`: license null, pushed 2026-09-01 | 코드 채택 불가(라이선스 없음). 필드 이름만 참고 |
| 공개 우주복 대사량 추정 코드 | `gh search`에서 찾지 못함 | — | — |

## 5. 막힌 원문과 추가 확인 항목

**막힌 원문(우회하지 않음)**
- TTU-IR(ttu-ir.tdl.org)은 403 봇 차단이다. ICES-2019-401 Ramsey(물주머니 부피 센서) 본문과 ICES-2020 "High-Accuracy Oxygen Flow Meter for the xPLSS" 본문이 여기에 있다. 초록 수치는 검색 결과 요약으로만 확인했으므로 본문 확인을 권한다.
- NTRS 20210024203(Chullen & Ramsey 2022): PDF가 없다(초록만 있음).
- NTRS 20090042588(Feiveson 2009), 20080046927(Dietrich 2009, Cx CO2 센서 평가): PDF가 없다.
- SAE 972502(EVA metabolic profile, Apollo–Shuttle): 유료.

**추가 확인 필요**
- xPLSS POV 부피, PT-112 정확도·분해능, 텔레메트리 주기 [Unverified]
- EMU·xPLSS CO2 센서의 위치(흡수기 상류인지 하류인지) [Unverified]
- xEMU FSA 용량과 부피 센서 오차의 성격(오프셋형인지 이득형인지) [Unverified]
- EMU CWS 자동 누설 점검의 판정 기준: 메시지(LEAKAGE HI)가 있다는 것은 확인했지만 임계값은 찾지 못했다
- Cox 2024 포스터의 Weir형 식 계수: PDF 추출 텍스트가 깨졌으므로 원본 그림으로 확인할 것

**결론을 바꿀 조건**
- xPLSS 탱크 센서 분해능이 EMU보다 훨씬 좋으면(예: 24비트 디지털), 짧은 창 O2 방법의 잡음 결론이 바뀐다.
- Mars PLSS가 흡수기 앞뒤 CO2와 연속 유량을 실제로 탑재하면 D 방법이 주력 후보가 된다.

## 6. 참고문헌 (이번에 실제로 연 것)

- Carson, M. A., Apollo PLSS Performance Report, NTRS 19720019460 — `references/NTRS_19720019460.txt`
- Waligora & Horrigan, Metabolic Cost of Extravehicular Activities (Skylab SP-377 계열, N75-14397) — `references/Waligora1975_metabolic_cost_EVA.pdf`
- Ogilvie et al., Mars PLSS Status and Plan, ICES-2026-126 — `references/ICES-2026-126_Ogilvie_MarsPLSS.txt`
- JSC-20597 Vol.4 Rev B CPN-1, EVA Console Handbook – EMU Operations (2010) — https://ibiblio.org/apollo/Shuttle/MCC/EVA%20Console%20Handbook%20-%20EMU%20Operations.pdf
- Makel et al., ICES-2023-053 — https://ntrs.nasa.gov/api/citations/20230005393/downloads/Makel_M-PALSS_2023_v2.pdf
- Makel et al., ICES-2025-222 — https://ntrs.nasa.gov/api/citations/20250003986/downloads/Final_Makel_M-PALSS_2025_Strives_1.pdf
- Whalen et al., SxEMU Testing Setup, ICES-2024-130 — https://ntrs.nasa.gov/citations/20240004887
- Ogilvie & Campbell, PLSS Oxygen Regulator History, ICES-2023-027 — https://ntrs.nasa.gov/api/citations/20230007781/downloads/Regulators_ICES2023_Final.pdf
- Izenson et al., Integrated O2 Flow Meter/Heat Exchanger, ICES-2018-192 — https://ntrs.nasa.gov/citations/20200002310
- Chullen, Sensors and Systems for Spacesuits (SBIR 2017) — https://ntrs.nasa.gov/citations/20170005909
- McGrath et al., PersEIDS, ICES-2023-327 — https://ntrs.nasa.gov/citations/20230007488
- McGrath et al., Novel Approaches to Metabolic Consumption Modeling (ISS RDC 2024 poster) — https://ntrs.nasa.gov/citations/20240009179
- Cox, EVA Planning: NBL training to predict in-flight energy expenditure (ISS RDC 2024) — https://ntrs.nasa.gov/citations/20240009328
- Hoffmann, EVA Metabolic Rate Model: Metabolic Rate Estimated from Heart Rate (2021) — https://ntrs.nasa.gov/citations/20210024317
- Paul, Energy Expenditure During EVA Through Apollo (2012) — https://ntrs.nasa.gov/citations/20120003917
- Horrigan, Waligora et al., Shuttle 61-B EASE/ACCESS energy expenditure (1986) — https://ntrs.nasa.gov/citations/19880001500
- Norcross et al., EVA Walkback Test, NASA/TP-2009-214796 — `references/Norcross_TP-2009-214796.md`
- Mah & Machak, ICES-2026-170 (슬라이드) — `references/ICES-2026-170_Mah_Machak.pdf`
- Wood et al., Optical Breath Gas EVA Sensor (ICES-2016, 초록 쪽) — https://ntrs.nasa.gov/citations/20150021031
- NTRS 초록만 확인: 20090042588 (Feiveson), 20210024203 (Chullen & Ramsey), 20080046927 (Dietrich)
- GitHub: https://github.com/SUITS-Techteam/TSS2026
