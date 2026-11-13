# 화성 중력 우주복 보행 대사량: 근거 조사

2026-11-09 · 목적: 귀환 반경 재계산에 쓸 보정계수 k(= 실제 대사량 ÷ 프로젝트 Pandolf 예측)의 근거 범위 정하기

근거 표시: [확인] 이번 세션에서 원문(전문 또는 초록)을 직접 읽음 · [추론] 확인된 값으로 계산·해석 · [미확인] 원문을 못 봄

## 1. 결론 요약
- 화성 중력(3/8 g)에서 우주복을 입고 걸은 대사량 **실측은 2006년 MKIII 시험(NASA TP-2009-214796) 하나뿐**이다. 이번 조사에서 이보다 새로운 화성 중력 우주복 보행 실측은 찾지 못했다. [확인: 검색 범위 안에서]
- 더 새로운 자료는 모두 **달 중력**(ARGOS, 2022~2024, MKIII·xEMU)이거나 **설계 가정값**(화성 PLSS 사이징, ICES 2025·2026)이다.
- 근거별 k를 같은 기준(산소/거리, 프로젝트 0.92 m/s·301 W = 328 J/m 대비)으로 맞추면 다음 범위가 나온다. [추론]

| 근거 | 중력 | 성격 | k |
|---|---|---|---|
| 프로젝트 Pandolf (현행) | 화성 | 모델 | 1.00 |
| 화성 PLSS 설계 평균 350 W | 화성 | EVA 전체 평균 가정값 | 1.16 |
| Apollo 보행 계획 1440 BTU/h (예비 20% 포함) | 달 | 계획값 | 1.40 |
| **Apollo 14 실제 월면 보행** 300 kcal/h @ 2.4 km/h | **달 (진짜 중력)** | 실측 | **1.60** |
| EWT 달 중력 우주복 1단계 | 달 | 지상 모사 실측 | 1.64 |
| **EWT 화성 중력 우주복** 1단계 (평균 속도 1.25 m/s) | 화성 | 지상 모사 실측 | **1.84** |
| EWT 화성 중력 우주복 2~3단계 | 화성 | 지상 모사 실측 | 1.96 |
| EWT 화성 1단계, 최저 속도 1.07 m/s로 계산 | 화성 | 실측 + 속도 가정 | 2.15 |

- 해석: 진짜 달 중력에서 Apollo 우주복으로 걸은 비용이 이미 k ≈ 1.6이다. 같은 우주복이면 화성(무게 2.3배)에서 거리당 비용이 달보다 작을 이유는 없다(EWT에서도 같은 MKIII가 화성 중력에서 더 비쌌다). 그래서 Apollo·MKIII급 우주복이라면 화성 k는 1.6 근처 이상일 가능성이 있다. [추론]
- 단, Apollo 1.6에는 프로젝트 기준선(평지, η = 1)에 없는 비용이 섞여 있어 하한으로 쓰기엔 약하다. [추론]
  - 실제 월면 지형·경사 비용. 프로젝트는 이를 η·경사로 따로 더하므로 이중 계산 가능성이 있다.
  - 우주복 산소 누설. Waligora 1975는 "산소 사용률에 누설이 포함되어 있어 추정해야 했다"고 썼고, 사양상 최대 누설을 약 50 kcal/h 상당으로 적었다. 보고된 300 kcal/h에서 누설을 뺐는지는 본문에 분명하지 않다. [확인: 문장 / 미확인: 보정 여부]
  - 300 kcal/h에 최대 누설이 그대로 들어 있다고 가정하면, 사람의 대사량만으로는 291 W, k ≈ 1.33이다. 이미 보정된 값이면 1.60이 대사량 자체다. [추론]
  - k는 사람의 대사량 비율이다. 누설은 탱크에서 시간당 일정량 빠지는 별도 항이다. 최대 50 kcal/h 상당이면 산소 약 15 g/h이고, 프로젝트 모델에는 이 항이 없다. 현대 우주복의 누설 사양은 확인하지 못했다. [추론 / 미확인]
- k = 1.0~1.16은 "미래 화성 우주복이 지금보다 훨씬 가볍고 잘 움직인다"는 낙관 시나리오다. 이를 뒷받침하는 화성 중력 실측은 없다. [추론]

### 1.1 안 B용 추가 근거: 화성과 같은 "총 무게"에서 잰 우주복 보행 (IST-1·IST-2 그림 판독)
- IST-1(2007)과 IST-2(NASA/TP-2010-216125)는 MKIII 121 kg을 0.12~0.32 g로 시험했다. **0.32 g의 총 무게(사람 + 우주복, 592~654 N)는 프로젝트 가정(75 + 90 kg)이 화성에 있을 때의 무게 612 N과 거의 같다.** 다만 질량(관성)은 121 kg이라 프로젝트의 90 kg보다 크다. [확인: 본문 / 추론: 대응]
- 0.32 g 추세선을 눈으로 판독한 값(±1 mL/kg/min 수준, 구현 때 화소 단위로 다시 판독):
  - 평지, 0.92 m/s (IST-1 그림 22): 약 17 mL/kg/min. 평지 k로 환산하면 약 1.42~1.52(체중 75 kg 또는 80.7 kg 기준).
  - 경사, 약 0.77 m/s (IST-2 그림 36, 속도 = 달 PTS − 0.7 m/s): 0% 16.2, 10% 18.4, 20% 23.6, 30% 31.5. 평지 대비 증가 +2.2 / +7.4 / +15.3.
- 비교: 프로젝트 Pandolf는 경사 1%당 같은 양을 더해 10% 경사에서 +201 W(약 +8 mL/kg/min)다. 실측 증가는 10%에서 그 약 1/3, 30%에서 비슷하다. **평지는 모델보다 비싸고, 완만한 오르막은 모델보다 싸다.** k 하나로는 이 차이를 표현할 수 없다. [추론]
- IST-2 그림 36에 맨몸 비교, 내리막 데이터는 없다. [확인]
- 화소 판독용 이미지: references/IST1_fig22_zoom.png, references/IST2_fig36_zoom.png

### 1.2 Kluis 2025 원자료 (github.com/BHP-Lab/POWER_Testing, 라이선스 표기 없음, 2025-08 갱신) [확인: 직접 계산]
맨몸 평균 mL/kg/min(괄호는 1 g 대비): 3 mph 0% → 0.25 g 15.0(80%), 0.5 g 15.1(80%), 0.75 g 15.4(81%), 1 g 18.9. 0.25~0.75 g가 거의 같고 1 g에서만 뛴다. 1 g 값(18.9)은 ACSM 식(11.5)보다 훨씬 높아 장치·측정 차이가 커 보인다. 그래서 절대값은 쓰지 않고 교차 확인에만 쓴다. [추론]

## 2. 근거별 상세

### 2.1 Norcross et al. 2009, NASA/TP-2009-214796 (EVA Walkback Test, 시험 2006) [확인: 전문]
- 남성 우주인 6명(81.4 ± 7.8 kg), MKIII + PLSS 모형 + 짐벌 = POGO 구성 120 kg, 29.6 kPa, 평지 트레드밀, POGO로 1/6 g·3/8 g 모사.
- 표 5 (mL/kg/min), 3/8 g: 맨몸 11.0 / 12.1 / 12.1, 무게 맞춤 12.7 / 13.7 / 14.1, **우주복 27.6 / 32.5 / 35.7**. 속도는 개인별 PTS − 0.49 / 0.36 / 0.22 m/s (평균 PTS 1.74 m/s). 본문은 해당 구간을 1.07~1.53 m/s로 적었다.
- 우주복 증가분의 90~92%가 무게가 아닌 요인(관성 질량, 허리 회전, 관절 제약). "MKIII는 화성에서 수용 불가"라고 결론.
- 맨몸 1.3 m/s 미만에서는 1/6 g, 3/8 g, 1 g 대사량 차이가 거의 없었다(그림 15 설명). → Pandolf 전체에 중력비를 곱하는 가정과 맞지 않는다.
- 한계(보고서 자체): n = 6 남성, POGO가 자유도를 제한, 무게중심 제어 불가, 학습 효과 가능성, 우주복 대사량은 CO₂ 기반 간접 추정.

### 2.2 Norcross et al. 2010, NASA/TP-2010-216115 (IST-1, 시험 2007) [확인: 전문 텍스트, 그림 수치는 텍스트로 안 나옴]
- 같은 MKIII 121 kg, **달 중력만**. 중력 0.12~0.32 g로 무게를 바꿔 시험(질량은 121 kg 고정).
- 0.32 g 조건의 총 무게(592~654 N)는 "75 kg + 우주복 90 kg"이 화성에 있을 때 무게(약 612 N)와 비슷하다. 하지만 수치가 그림에만 있어 읽지 못했다. [확인: 텍스트에 표 없음]
- 1.0 m/s 미만에서는 0.12 g와 0.32 g의 차이가 2.03 mL/kg/min(유의 아님), 1.0~1.5 m/s에서는 약 7 mL/kg/min. 압력(6.9~44.8 kPa)은 보행 대사량에 거의 영향 없음.
- **같은 피험자 3명의 재시험에서 IST-1 우주복 대사량이 EWT보다 일관되게 낮았다**(익숙해짐, 넓은 트레드밀, 정밀한 무게 맞춤). → EWT 화성 값은 과대일 수 있다.
- 회귀 모델(MR = b0 + b1·V·W_total + b2·M_body + b3·W_total·L_leg + b4·P_suit, R² 0.846, RMSE 2.52 mL/kg/min)은 **계수가 본문에 없다**. 이 조건 밖으로 일반화하지 말라고 명시.

### 2.3 Waligora & Horrigan 1975, Metabolic Cost of Extravehicular Activities (NTRS 19750006325) [확인: 전문]
- Apollo 14 월면 보행: 2.9 km를 평균 2.4 km/h, 300 kcal/h(349 W). 진짜 달 중력, A7LB 우주복, 실제 지형.
- 속도와 대사량의 상관은 매우 낮았다. 승무원이 "편한 노력 수준"을 유지하고 속도를 지형에 맞춰 바꿨다.
- Apollo 전체 EVA 평균 234 kcal/h(272 W), 긴 EVA 평균 200~250 kcal/h. 산소 측정에 우주복 누설(최대 약 50 kcal/h 상당)이 섞여 있다.

### 2.4 Schlotman et al. 2023 (NTRS 20220009964), Strock et al. 2024 (NTRS 20230014953) [확인: 초록]
- ARGOS(능동 중력 보상)로 1/6 g. MKIII 남성 2명, xEMU 여성 3명.
- "Apollo 월면 EVA 대사량은 새 우주복으로 지상 모사한 같은 작업보다 최대 50% 낮았다." → 지상 모사 시험이 과대 추정할 수 있다는 근거. 다만 어떤 작업·조건인지는 초록에 없다. [미확인: 본문]
- xEMU 평지 트레드밀 이동은 평균 45~47% VO2pk(최대 69%). 30% 경사 500 m 이동에서 최대 1656~1747 BTU/h(485~512 W, MKIII).
- 화성 중력 시험은 없다.

### 2.5 화성 PLSS 사이징 (ICES-2025-090, ICES 2026 Paper 158) [확인: 발표 자료 전문]
- 주 시스템 평균 350 W, 최대 530 W, 보조 시스템 평균 295 W, 최대 350 W. 4.3 psia, 8시간 EVA, "EVA 내내 고정 대사량" 가정.
- 이 값의 출처는 발표 자료에 없다(참고문헌에 XEMU PLSS 사양서 CTSD-ADV-780, Life Support Baseline Values 문서가 있음). [미확인: 출처]
- 보행 전용 값이 아니라 EVA 전체 평균이다. 그래서 k = 1.16은 하한 참고로만 쓴다. [추론]

### 2.6 맨몸 부분중력 보행 (사용자가 내려받아 준 원문, 2026-11-09) [확인: 전문]
세 자료 모두 **맨몸**이다. 우주복 k 근거 지점은 바꾸지 않는다. 대신 "Pandolf 전체에 중력비를 곱하면 맨몸 보행 비용이 0.378배가 된다"는 프로젝트 가정을 직접 반박한다.

- **Kluis, Wynn, Kennedy, Diaz-Artiles 2025**, J Appl Physiol 139:787–796, doi 10.1152/japplphysiol.00627.2024 (CC-BY 4.0)
  - 12명(남 6, 여 6), 수직 체중 지지 장치(POWER, 탄성 밴드), 0.25 / 0.5 / 0.75 / 1 g × 3·4 mph × 0·10% 경사, COSMED K5.
  - "1.34 m/s(3 mph)에서 0.25 g 대사량은 1 g의 80%", "1.79 m/s(4 mph)에서는 60%". 인용한 선행연구: 1.25 m/s에서 0.25 g가 1 g의 75%(Grabowski 2005).
  - GLMM 계수(log 링크): 절편 3.001, 속도 0.113, 중력 0.104, 경사 0.157, 속도×중력 0.020, 중력×경사 0.055. 독립변수의 부호화 방식(범주 또는 표준화)이 본문에 없어 그대로 재현할 수 없다. [확인 / 미확인: 부호화]
  - 한계: 1 g 안의 체중 지지 장치라 팔다리는 1 g, 탄성 밴드라 지지력이 조금 흔들린다.
  - 데이터 공개: https://github.com/BHP-Lab/POWER_Testing
- **Brown et al. 2018**, JEPonline 21(1):25–35, "The Metabolic Cost of Walking in Simulated Martian Gravity and its Implications" (PUCRS 공동)
  - 12명(58.7 kg, 22.8세), 하체 양압(LBPP), 1.39 m/s, 1 g와 0.38 g 각 8분. VO2 1.00 → 0.68 L/min(**0.38 g가 1 g의 68%**).
  - 신뢰도 낮음: 2주 간격 비무작위, 표준편차가 큼(1.00 ± 0.61), 0.38 g의 RER 1.14는 중강도 보행으로 보기 어렵고, 초록에서 kcal 값의 순서가 본문과 뒤바뀌어 있다.
- **Kluis 2024 박사논문**, Texas A&M, "A Novel Metabolic Model for Ambulation in Hypogravity and Applications to Planetary Extravehicular Activity"
  - 신경망 대사 모델. 학습 데이터 2,897점: IST-1 521점, IST-2 374점, Lankford 1,810점, Kluis 192점. 우주복 데이터는 MKIII만(566점, 0.12~0.37 g). Apollo 데이터는 "우주복 한 종류만 모델링하려고" 제외했다.
  - 결과는 그림으로만 있고, 화성 중력 우주복 예측값은 없다. 모델 공개 여부를 확인하지 못했다.
  - 모델 결과 서술: 맨몸 0.45~1.34 m/s에서는 "모든 중력에서 대사량이 비교적 일정"하다.
- **해석:** 맨몸 0.38 g 보행 비용은 1 g의 약 68~85%로 측정된다(Kluis 0.25 g 80%에서 0.38 g를 직선 보간하면 약 83%). 프로젝트 방식(0.378배)은 맨몸 기준선부터 절반 이하로 낮다. [추론]

### 2.7 접근하지 못한 자료
- Kluis & Diaz-Artiles 2022 초록은 읽었다. 기존 Norcross 회귀가 변수 간 상호작용을 반영하지 못한다고 지적하고, SEXTANT 경로 계획 도구의 대사 모델은 Apollo 외삽 기반이라고 적었다. [확인]
- Wickman & Luna 1996, "Locomotion while load-carrying in reduced gravities" (부분중력에서 짐을 진 보행 회귀식). 원문을 보지 못했다.
- IST-1 그림 22~26의 수치(그래프에만 있음).

## 3. k 근거 계산 방식 [추론]
- 프로젝트 기준: 301.3 W ÷ 0.92 m/s = 328 J/m.
- 실측 값: mL/kg/min × 81.4 kg × 20.1 kJ/L → W, 측정 속도로 나눠 J/m.
- k = (실측 J/m) ÷ 328. 프로젝트의 k는 "같은 경로에서 산소를 k배 쓴다"는 뜻이므로 거리당 비용 비율로 맞춘다.
- 주의: 측정 속도(0.67~1.52 m/s)가 프로젝트 속도(0.92 m/s)와 달라 거리당 비용이 속도에 따라 바뀌는 효과가 섞인다. 측정 피험자는 81 kg으로 프로젝트의 75 kg보다 무겁다(mL/kg 단위라 일부 상쇄).

## 4. 결론을 바꿀 조건
- 최신 우주복(xEMU 후속, 화성용 시제품)으로 3/8 g에서 측정한 보행값이 나오면 그 값이 우선한다.
- 맨몸 기준선은 이제 근거가 있다(2.6절, 1 g의 68~85%). 이것으로 Pandolf 맨몸 항을 고치는 일은 안 B(모델 교체)의 범위다.
- IST-1 0.32 g 그림 수치를 디지털화하면 "가벼운 우주복 무게" 쪽 근거가 하나 더 생긴다.

## 4.1 Apollo 30분 예비분의 원문 (2026-11-09 확인)
**Bellcomm 메모 B70 10028, "Apollo 15 EVA Capability and Constraints Envelopes", P. Benjamin, 1970-10-13** (NASA 문서 번호 19790073512, 로컬: references/NASA_19790073512.pdf) [확인: 전문, 9쪽 중 본문 2쪽]
- 원문: "PLSS feedwater capacity is 9.8 lbs (10,065 BTU) with heat leaks of 0, 100, and 200 BTU/hr for EVA's 1, 2, and 3" / "PLSS oxygen capacity is 1.3 lbs with leak rates of .01, .02, and .03 lbs/hr" / "PLSS battery capacity provides a 7 hr capability" / **"The capacities above are defined after allowance for a 30 minute consumables reserve."**
- 원문: "The metabolic rate for planned walking traverses is 1200 BTU/hr at a speed of 3.3 km/hr. A 20% pad is required for emergency walkback, making the metabolic rate 1440 BTU/hr at a speed of 3.3 km/hr"
- 원문: 걸어서 돌아오는 한계는 "the consumables remaining in the PLSS to support a walking return to the LM at 3.3 km/hr and 1440 BTU/hr"로 정한다.
- 이 메모가 밝히는 MSC "Lunar Surface Mission Guidelines"의 가정이다. Apollo 15 사전 계획용이고, 다른 임무에도 그대로 적용됐는지는 이 문서로 알 수 없다.

해석 [추론]:
- **30분 예비분은 탱크 용량에서 미리 빼 둔 고정량이다.** 산소와 냉각수 모두 해당한다. 어떤 대사율로 30분을 환산했는지는 메모에 없다(설계 대사율 1200 BTU/h = 352 W라면 산소 약 45 g). 귀환 계산 때 보행 속도나 실제 대사율에 맞춰 다시 늘리거나 줄이지 않는다.
  - 따라서 안 A·B의 "예비분 고정" 정의가 원래 취지에 가깝다. 안 B의 "모델별 평지 30분" 정의는 원문 근거가 없는 확장이다.
- **냉각수 30분 예비분도 Apollo 근거가 있다.** 보고서 17은 이를 "가정"으로 적었다.
- **Apollo는 비상 귀환 대사율에 20% 여유를 더했다(1200 → 1440 BTU/h).** 프로젝트 모델과 안 A·B에는 이 여유가 없다. 이 여유를 넣는 것은 k = 1.2를 곱하는 것과 같다.
- **산소 누설률이 계획값으로 있다:** 0.01 / 0.02 / 0.03 lb/h = 4.5 / 9.1 / 13.6 g/h(EVA 1→3, 장비가 닳을수록 증가). 안 A·B의 14.9 g/h(최대 50 kcal/h 상당)는 이 범위의 위 끝과 비슷하다.
- **냉각수 쪽 열 유입 계획값:** 0 / 100 / 200 BTU/h = 0 / 29 / 59 W. 보고서 17의 Q_extra 시나리오(−100 / 0 / +100 W)와 비교할 수 있는 실제 계획값이다.

**Carson, "Apollo Portable Life Support System Performance Report"** (NTRS 19720019460, 로컬: references/NTRS_19720019460.pdf) [확인: 해당 문단]
- PLSS는 "an average crewman metabolic rate of 1200 Btu/hr"로 설계됐다. 실제 임무(Apollo 9, 11, 12, 14)의 대사율은 "consistently lower than the 1200 Btu/hr design point"였다.
- 비상 산소 공급 장치(OPS)는 "sufficient breathing oxygen for a minimum of 0.5 hr"를 제공한다. 소모품 예비분과는 별개의 30분이다.

## 5. 출처
- NASA/TP-2009-214796: https://www.lpi.usra.edu/lunar/artemis/NorcrossEtAl_NASA-TP-2009-214796_EVA%20Walkback%20Test.pdf (로컬: references/Norcross_TP-2009-214796.pdf)
- NASA/TP-2010-216115: https://www.lpi.usra.edu/lunar/artemis/NorcrossEtAl_NASA-TP-2010-216115_PlanetarySuitMetabolicCosts.pdf
- Waligora & Horrigan 1975: https://ntrs.nasa.gov/citations/19750006325
- Schlotman et al. 2023: https://ntrs.nasa.gov/citations/20220009964
- Strock et al. 2024: https://ntrs.nasa.gov/citations/20230014953
- ICES-2025-090: https://ntrs.nasa.gov/api/citations/20250006266/downloads/ICES_Mars_Presentation.pdf
- ICES 2026 Paper 158: https://ntrs.nasa.gov/api/citations/20260005204/downloads/ICES_Mars_PLSS_Presentation_2026_1.pdf
- Kluis & Diaz-Artiles 2022: https://bhp.engr.tamu.edu/wp-content/uploads/sites/212/2022/02/Kluis-et-al.-2022-A-METHODOLOGY-FOR-ANALYZING-AND-IMPROVING-EVA-PERFORMANCE.pdf
- Kluis et al. 2025: https://journals.physiology.org/doi/full/10.1152/japplphysiol.00627.2024 (로컬: references/Kluis2025_JAP.pdf)
- Brown et al. 2018, JEPonline 21(1):25–35 (로컬: references/Brown2018_JEPonline_Mars_walking.pdf)
- Kluis 2024 박사논문, Texas A&M (로컬: references/Kluis2024_dissertation.pdf)
