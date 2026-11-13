# 계획: 근거 기반 k로 귀환 가능 면적 다시 계산 (안 A)

상태: **구현 완료 (2026-11-09). 결과: RESULTS.md**

## 1. 목표
보고서 16의 k 방식을 그대로 쓰되, k 범위를 0.8~2.5로 넓히고 RESEARCH.md의 근거 k 지점(1.00 / 1.16 / 1.33 / 1.40 / 1.60 / 1.84 / 2.15)에서 귀환 가능 면적을 낸다. 냉각수는 만충과 0.6 kg 두 경우를 계산한다.

## 2. 이미 확인한 것
- HiRISE DTM 받음: 425,660,300 B. 라벨에서 나온 크기(15040 × 7075 × 4 + 28300)와 정확히 같다.
- 고정 버전 venv(`recalc/.venv`, numpy 2.0.2 / scipy 1.13.1 / matplotlib 3.9.4 / pillow 11.3.0)에서 원본 `heart_rate_o2.py` 실행: k = 1.0 / 1.2 / 1.4 → 18.64 / 13.29 / 10.03 km². 보고서 16 표(18.6 / 13.3 / 10.0)와 일치. 로그: `recalc/baseline_heart_rate_o2.log`
- 원본 실행으로 `outputs/heart_rate_o2/`와 `outputs/mars_walkback/`이 새로 생겼다(원래 패키지에는 없던 폴더).

## 3. 방법
새 파일 하나: `recalc/k_scenarios.py`. 원본 `code/`는 수정하지 않고 import만 한다.

```python
# 실행: cd code && ../recalc/.venv/bin/python ../recalc/k_scenarios.py
import sys, json; sys.path.insert(0, ".")
# heart_rate_o2.main()과 같은 순서로 장면을 만든다: 산소만 쓰는 그래프 → 뒤집은 그래프 다익스트라 1회
from mars_walkback import load_dtm_crop, load_traverse, lonlat_to_cell, build_o2_graph, O2_RESERVE_G, CELL_M
from suit_cooling import FEEDWATER_FULL_G, water_reserve_g, water_g_per_s, LEVEL_MR_W
from metabolic_navigation import o2_g_per_s

K_GRID = np.round(np.arange(0.80, 2.501, 0.05), 2)
K_EVIDENCE = {1.00: "Pandolf 현행", 1.16: "화성 PLSS 평균 350 W", 1.33: "Apollo 14, 누설 제외",
              1.40: "Apollo 보행 계획", 1.60: "Apollo 14 실측(달, 지형·누설 포함)",
              1.84: "EWT 화성 1단계", 2.15: "EWT 화성 최저속도"}
O2_LEFT = [100, 150, 200]
WATER_LEFT_G = [3600, 600]   # 만충, 누수 시나리오(보고서 17과 같은 0.6 kg)
O2_RES, W_RES = O2_RESERVE_G, water_reserve_g(0.0)   # 38.6 g, 219 g (30분 평지 보행)

ret_o2 = ...  # heart_rate_o2.main() 241~259행과 같은 코드로 칸별 귀환 산소(g)
# Q_extra = 0이면 냉각수/산소 비가 상수(약 5.68)라 칸별 귀환 냉각수 = ret_o2 × 비율
WATER_PER_O2 = water_g_per_s(LEVEL_MR_W) / o2_g_per_s(LEVEL_MR_W)
r = {"o2": ret_o2, "water": ret_o2 * WATER_PER_O2}
for o2_left in O2_LEFT:
  for water_left in WATER_LEFT_G:
    for k in sorted(set(K_GRID) | set(K_EVIDENCE)):
        for rdef, rk in (("fixed", 1.0), ("scaled", k)):
            # 정의 1 fixed (주 결과, 보고서 16과 같음): 예비분 g 고정
            # 정의 2 scaled (민감도): 예비분도 k배 = "실제 소비율로 30분"
            ok_o2 = k * r["o2"] <= o2_left - rk * O2_RES
            ok_w = k * r["water"] <= water_left - rk * W_RES
            area = (ok_o2 & ok_w).sum() * (CELL_M/1000)**2
            binding = "water" if (ok_o2 & ~ok_w).any() else "o2"
```

- **경로:** k를 곱해도 최적 경로는 바뀌지 않는다(모든 간선에 같은 배수). 그래서 다익스트라는 한 번만 돌린다. 보고서 16과 같은 방식이다.
- **냉각수:** 대사열이 k배면 냉각수도 k배다. 냉각수 만충(3.6 kg)이면 산소 150 g 조건에서 산소가 먼저 묶이는지 같이 확인해서 표에 표시한다.
- **선량:** 속도를 고정했으므로 귀환 시간이 같아 선량은 k와 무관하다. SPE off만 계산한다.

### 3.1 누설 항 (추가, 2026-11-09)
k(사람 대사량)와 따로, 탱크에서 시간당 일정하게 빠지는 누설 L(g/h)을 더한다.

```python
LEAK_G_PER_H = [0.0, 14.9]   # 0 = 현행 모델, 14.9 = Apollo 사양 최대 50 kcal/h 상당 (Waligora 1975)
# 50 kcal/h = 58.1 W → 58.1 / 20100 J/L × 1.429 g/L × 3600 s/h = 14.9 g/h

# 칸별 귀환 거리: 귀환 트리(ret_pred)를 비용 순으로 따라가며 간선 길이를 누적
ret_dist_m = tree_distance(ret_pred, ret_o2, shape, CELL_M)   # 새 함수, 대각선 간선은 √2 × CELL_M
ret_time_h = ret_dist_m / EVA_WALK_SPEED_M_S / 3600

tank_o2 = k * ret_o2 + L * ret_time_h                       # 탱크에서 빠지는 총량
# 예비분: 정의 1 = 38.6 g 고정(보고서 16과 같음), 정의 2 = 0.5 h × (k × 77.1 + L)
```

- 냉각수에는 누설 항이 없다. 산소만 빠진다.
- 경로는 누설이 없는 산소 최적 경로를 그대로 쓴다. 누설을 넣은 최적 경로는 거리가 더 짧은 쪽으로 조금 달라질 수 있지만, 고정 경로 쪽 면적이 같거나 약간 작게 나와 보수적이다. [추론]
- 검증:
  - L = 0이면 누설 없는 결과와 완전히 같아야 한다.
  - 거리 누적 검산: sol 1282 귀환 경로의 거리가 보고서 15의 7.26 km와 같아야 한다.
- 한계: 14.9 g/h는 Apollo A7LB의 사양상 최대치다. 실제 누설과 현대 우주복의 사양은 확인하지 못했다. 그래서 상한 시나리오로만 쓴다.

## 4. 출력 (`recalc/outputs/`)
- `k_area_table.csv`: k × 남은 산소 × 예비분 정의별 면적, 그리고 냉각수가 묶는지 여부
- `k_area_vs_k.png`: 면적-k 곡선, 근거 지점을 세로선으로 표시
- `k_boundary_map.png`: 산소 150 g에서 k = 1.0 / 1.6 / 1.84 / 2.15 경계를 지도 위에 표시
- `k_summary.json`: 근거 지점 면적과 실행 환경 버전

## 5. 검증
1. k = 1.0, 1.2, 1.4의 면적이 기준 실행(18.64 / 13.29 / 10.03 km²)과 같은지 assert
2. 면적이 k에 대해 단조 감소하는지 assert
3. 평지 원 반경 검산: 150 g, k = 1.84이면 (150 − 38.6) / (1.84 × 77.1) h × 3.31 km/h = 2.60 km. 실제 면적이 π·2.60² = 21.2 km²보다 작은지 확인

## 6. 가정과 트레이드오프
- k 하나로 평지와 오르막을 같은 비율로 늘린다. 실제로는 우주복 비용이 속도·경사마다 다르다(EWT에서 화성은 속도에 따라 급증). 이 차이를 반영하는 것은 안 B(모델 교체)이고, 이번 범위가 아니다.
- 근거 k들은 측정 속도와 체중이 프로젝트와 다르다(RESEARCH.md 3절).
- EWT는 학습 효과와 POGO 때문에 과대일 수 있다. Apollo 14는 실제 지형과 누설이 섞였다. 그래서 단일 값 대신 범위로 보고한다.

## 7. 확정된 결정 (2026-11-09)
1. 예비분: 정의 1(고정)을 주 결과, 정의 2(k배)를 민감도로 함께 낸다. 냉각수 예비분에도 같은 정의를 적용한다.
2. 근거 지점: 1.00 / 1.16 / 1.33 / 1.40 / 1.60 / 1.84 / 2.15. 그림에서 1.60은 "지형·누설 포함"으로 표시한다.
3. 냉각수: 만충 3.6 kg과 0.6 kg 두 시나리오. 0.6 kg 검증: k = 1.0, 정의 1이면 보고서 17 값 7.4 km²와 맞아야 한다.
4. 누설 항: 0과 14.9 g/h 두 시나리오(3.1절). 결과 표에 leak 열을 추가한다.
