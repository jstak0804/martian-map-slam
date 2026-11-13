# 17. 냉각수 잔량과 귀환 반경

2026-11-05 · 지형: HiRISE DTM (Gale, 10 m) · 냉각: NASA ICES 2007·2026, UMD ENAE 697
웹 버전: `reports/17-coolant-walkback.html` (원격 열람용 `17-coolant-walkback.standalone.html`)

## 요약
- 화성 평지 보행(301 W)의 냉각수 소모는 438 g/h로, 산소 77 g/h의 약 5.7배다. 만충 3.6 kg이면 8.2시간을 쓴다.
- 산소 150 g이 남았을 때 냉각수가 약 0.85 kg보다 적으면 귀환 반경이 냉각수로 정해진다. 이 선은 환경·PLSS 열(Q_extra)이 −100 W면 0.57 kg, +100 W면 1.13 kg이다.
- 냉각수 0.6 kg이 남으면 귀환 가능 면적이 18.6 → 7.4 km²(−60%)로 준다. Q_extra가 +100 W면 3.2 km²다.
- 물이 떨어진 뒤 비상 체온 한계(2.0 BTU/lb)까지는 평지 보행 약 19분(1.1 km)을 버틴다. 냉각수 141 g어치다.
- 보고서 15의 SPE 수치는 그대로다. 냉각수가 만충이면 경로 선택이 바뀌지 않는다. 다시 돌려 확인했다.

## 1. 왜 냉각수인가
- **화성에서 쓸 수 있는 냉각 방식**
  - 승화기는 물의 삼중점(611 Pa) 아래에서만 작동해 화성에서는 쓸 수 없다.
  - 대신 막 증발기(SWME)를 쓴다. 10 Torr까지 시험했다(ICES-2026-126 p.4, p.10).
  - 첫 화성 EVA 후보지는 7~8 Torr 이하로 가정한다(p.7).
- **잔량 측정:** 기존 EMU는 냉각수 잔량을 연속으로 재지 못했다. 연속 센서는 개발 중이다(p.13).
- **버디 냉각:** 고장 시 동료의 냉각 회로에 연결하는 Apollo BSLSS 방식을 검토 중이다(p.4, p.12).

## 2. 모델 (`code/suit_cooling.py`)
`냉각수(g/s) = max(0, 대사량 + Q_extra) / 2.477 MJ/kg × 1000`

귀환 가능 = 산소 OK AND 선량 OK AND 귀환 냉각수 ≤ 남은 냉각수 − 30분 예비분

| 값 | 근거 | 수준 |
|---|---|---|
| 증발잠열 2.477 MJ/kg | 10 °C 증기표. SWME 작동 온도 | 문헌 |
| 만충 3.6 kg | Nabity et al. 2007, 8 h EVA. EMU는 3.9 kg, 7 h × 1000 BTU/h | 문헌 |
| 비상 체온 한계 2.0 BTU/lb (4.65 kJ/kg) | ICES-2026-170 slide 5. 정상 운용은 1.3 BTU/lb | 문헌 |
| 대사열 전부를 증발로 버림 | 보수적 | 가정 |
| 예비분 30분 (Q=0이면 219 g) | 산소와 같은 원칙 | 가정 |
| Q_extra −100 / 0 / +100 W | 화성 기압에서 MLI 성능 저하(진공 <1 W/m² → 화성 >100 W/m²) | 가정 |

## 3. 남은 냉각수별 귀환 가능 면적 (km², 산소 150 g, SPE off)
| 냉각수 kg | 0.3 | 0.4 | 0.5 | 0.6 | 0.7 | 0.8 | 0.9 | 1.0 | 1.1 | 1.2 |
|---|---|---|---|---|---|---|---|---|---|---|
| −100 W | 2.9 | 6.9 | 12.7 | 18.6 | 18.6 | 18.6 | 18.6 | 18.6 | 18.6 | 18.6 |
| 0 W | 0.5 | 2.1 | 4.4 | 7.4 | 11.2 | 15.9 | 18.6 | 18.6 | 18.6 | 18.6 |
| +100 W | 0.0 | 0.5 | 1.7 | 3.2 | 5.2 | 7.6 | 10.5 | 13.9 | 17.8 | 18.6 |

경계 모양은 산소 경계와 같은 동심원 띠다. 귀환 경로마다 냉각수와 산소의 비율을 보면, 평지 보행 비율과의 차이가 2% 안이다(+100 W일 때 중앙값 0.985).

## 4. 실행
```
python spe_walkback.py --spe off --water-left 0.6
python spe_walkback.py --spe on --water-left 0.6 --heat-extra 100
python coolant_walkback.py
```

## 5. 한계와 다음 단계
- **Q_extra는 측정치가 없다.** REMS 기온(보고서 14)과 태양 고도로 시간대별 값을 추정할 수 있다.
- **추울 때의 위험은 넣지 않았다:** 히터 전력, 저체온.
- **심박 보정(보고서 16)의 k는 냉각수에도 곱해야 한다.** 연속 잔량 센서가 없다면 심박으로 쓴 열을 적분해 잔량을 추정할 수 있다.
- **화성 SWME의 실제 효율은 모른다:** 먼지 필터 배압, 7~8 Torr에서의 성능 저하.
- **경계 모양:** 오르막 감속을 넣으면 냉각수 경계가 산소 경계와 다른 모양이 된다.

## 출처
- Ogilvie et al., Mars PLSS Status and Plan (ICES-2026-126): https://ntrs.nasa.gov/citations/20260003024
- Nabity et al., Space Suit Radiator Performance in Lunar and Mars Environments (07ICES-221): https://ntrs.nasa.gov/citations/20070013698
- Mah & Machak, IVA Spacesuit without LCG (ICES-2026-170): https://ntrs.nasa.gov/citations/20260005313
- Akin, UMD ENAE 697 Thermal Analysis: https://spacecraft.ssl.umd.edu/academics/697S23/697S23L25.thermalx.pdf
