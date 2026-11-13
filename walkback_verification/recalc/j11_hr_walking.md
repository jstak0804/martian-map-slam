# J11. 보행용 심박–대사량 관계 조사 (계획 J, 2026-11-12)

## 질문
현재 데모는 Hoffmann 2021(셔틀·ISS 무중력 EVA 132회) 회귀식 MR(BTU/h) = 284.55 + 5.984 × HR을 쓴다. 우리 보행 대사량(444 W ≈ 1,515 BTU/h)은 그 자료 범위(≤ 1,200 BTU/h)를 넘는다. 우주복 보행, 또는 부분 중력 보행에 맞는 관계식이 있는가?

## 확인한 것
- **Hoffmann 2021** [확인: research/sources/Hoffmann2021_NTRS20210024317.txt, research/T2]
  - 전체 회귀 R² 0.402, 개인별 회귀 R² > 0.82. 개인 보정이 필수다.
  - 무중력 작업 자료라 보행은 없다.
- **Hoffmann 2025 CSRM** [확인: research/sources/Hoffmann2025_CSRM_NTRS20250002103.txt 372행]
  - "real-time heart rate to predict metabolic energy expenditure through pre-established linear regressions"
  - 개인별 사전 회귀 방식이다. 우주복 가압 보행 검증은 진행 중이다(Kim 2025 슬라이드 3).
- **Apollo** [확인: Paul 2012, research/sources/Paul2012_EnergyExpenditureApollo_NTRS20120003917.txt 592–596행]
  - "while the lunar surface EVA metabolic rate was lower than predicted, heart rates were higher than predicted ... heart rate alone should not be a predictor of energy expenditure during EVAs."
  - Waligora 1975도 심박법은 "상대 측정으로만" 썼다고 적었다(I6 원문).
- **지상 보행 모델** [확인: Kluis 2024 학위논문 2장 문헌 정리, references/Kluis2024_dissertation.txt 1070–1095행]
  - Beltrame: HR, 속도, 경사, 성별, BMI 등으로 VO2를 예측하는 신경망, 10명
  - Borror: HR, HR 미분, 속도, 경사, 체중으로 VO2 예측, 26명. 보행이 달리기보다 잘 맞음
  - 모두 지구 맨몸 보행이다.

## 찾지 못한 것 [미확인]
- 우주복을 입고 부분 중력(0.17~0.38 g)에서 걸을 때 심박과 대사량을 함께 잰 회귀식. IST-1·2 보고서에 심박 자료가 있는지는 이번에 확인하지 않았다(다음 확인 후보).
- 검색 결과가 없다고 해서 문헌이 없다는 뜻은 아니다.

## 결론
- 데모의 심박 방식을 보행에 쓰려면 **개인별 사전 보정**이 필요하다. 집단 회귀식 하나로는 부족하다. 이것이 Hoffmann 2021·2025와 Apollo 경험의 공통 결론이다.
- 압력(산소 소모 직접 측정) 방식이 심박 방식보다 근거가 강하다. 계획 I3에서도 심박 방식은 누설을 못 봐서 사망 사례가 나왔다.
- 데모는 지금처럼 "합성값, 회귀 범위 밖"으로 표시하고, 발표에서는 압력 방식을 주 방식으로 소개하는 것을 제안한다(J13).
- 다음 후보: IST-1·2 원문에서 심박 자료 확인 → 우주복 보행 개인 회귀의 기울기 범위 추정.
