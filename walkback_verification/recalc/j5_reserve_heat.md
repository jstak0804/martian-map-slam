# J5. 30분 예비분의 정의와 냉각수 추가 열 (계획 J, 2026-11-12)

## (a)·(b) 예비분은 무엇을 위해 남기나, 귀환 중 써도 되나
- **ISS EMU** [확인: JSC-20597 Rev.B Vol.4, 부록 C-8 "EMU Consumables Application User's Guide"]
  - "The Oxygen, Battery, and LiOH ending points are based on a REDLINE with respect to when EVA Sortie Clean-up would need to start in order to protect (by Flight Rule) having a 30 minute reserve of each consumable when SCU connection is made after airlock ingress."
  - 배터리도 같다: "16.4 volts = 30 minutes until 16.0 volts (This is actually the reserve margin required per Flight Rules, therefore this level should be reached only when the SCU is being connected)".
  - 산소 남은 시간 계산: "an average of the last 10 use rates is used to determine the O2 TIME LF". 우리 데모의 최근 10분 창과 같은 방식이다.
  - 주 산소 시스템 설계: "6-hour EVA, 15-minute egress, 15-minute ingress, and 30-minute reserve for a total of 7 hours" (2.x절).
- **Apollo** [확인: Bellcomm B70 10028, references/NASA_19790073512.txt]
  - "The capacities above are defined after allowance for a 30 minute consumables reserve." 계획 단계에서 예비분을 빼고 능력을 정의했다.
  - 고장 시 비상용은 별도 장치였다. OPS가 30분 산소 흐름을 공급하고, 냉각은 BSLSS로 동료와 연결했다 [확인: ICES-2026-126].
- **결론** [추론]
  - 30분 예비분은 귀환 중 쓰라고 남기는 양이 아니라, **귀환(에어록 진입) 시점에도 남아 있어야 하는 양**이다. 비행 규칙상 보호 대상이다.
  - 고장 대응은 별도 비상 장치(SOP, OPS, BSLSS)가 맡는다.
  - 따라서 계획 I3의 "예비분 침범"(경보 규칙 1분에서 29%)은 비행 규칙 기준으로 위반에 해당하는 실제 문제다. 우리 모델은 화성 PLSS의 비상 장치를 따로 두지 않는다.
  - 경보 재설계(J9)를 미룰 근거가 약해졌다. 기본값 변경은 J9 결과를 보고 결정을 받는다.

## (c) 냉각수 추가 열 계획값
- **ISS EMU** [확인: JSC-20597 2.9절 Feedwater]
  - "The heat flow into the EMU is a large portion of the total heat load of the feedwater system at low metabolic rates. As metabolic rates increase, the heat flow into the EMU remains practically constant"
  - 고온 사례: "95 percentile male, hot case at 2569 Btu/hr = 2000 Btu/hr equivalent metabolic rate" → 바깥에서 약 569 BTU/h(167 W) 유입 [계산]. 저온 사례는 반대로 열이 빠진다.
  - 계획 E 3번에서 중립 사례 그림으로 역산한 값은 22~77 W였다.
- **Apollo** [확인: Bellcomm] 냉각수 쪽 환경 열 계획값 0 / 100 / 200 BTU/h = 0 / 29 / 59 W(EVA별).
- **화성** [미확인]
  - 지표 대기 대류와 낮은 기온(평균 약 −60 °C, 일반 지식) 때문에 ISS 궤도의 고온 사례와 다르다. 열이 빠져나갈 수도 있다 [추론].
  - ICES-2026-126은 화성 대기에서 팬 소비 전력이 크게 줄어든다고 적었다(100 W → 5 W). PLSS 내부 발열이 작아질 수 있다는 정황이지만, 우리 q에 바로 쓸 수 있는 값은 아니다.
- **결론**
  - 추가 열 0 W(결정 E-a)는 화성에서 틀렸다고 할 근거도, 맞다고 할 근거도 없다.
  - 문헌 범위는 Apollo 계획 0~59 W, ISS 중립 역산 22~77 W, ISS 고온 약 167 W다. 계획 I4에 따르면 25 W에서 구조 예시가 깨진다.
  - 기본값은 그대로 두고, 발표 한계에 "냉각수 쪽 추가 열은 화성 값이 없어 0으로 둠. 25 W부터 구조 예시가 깨짐"을 명시한다(J13).
