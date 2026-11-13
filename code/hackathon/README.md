# 해커톤 데이터가 공개되면: 추가 학습·보정 파이프라인

올해 해커톤 데이터는 아직 공개되지 않았습니다. 형식을 모르니 "무엇이 오든 받아서 분류 → 종류별로 학습·보정 → 사람이 검토 → 데모에 반영"하는 흐름을 미리 만들어 두었습니다. 정답을 알고 만든 가짜 데이터로 전체 흐름을 점검해 두었습니다.

## 1. 데이터가 나오면 (3단계)

```bash
cd code
# ① 받은 파일을 그대로 한 폴더에 넣는다 (하위 폴더 그대로 둬도 됨)
#    ../data/hackathon_2026/
# ② 한 번에 돌린다. 지형 분할 학습까지 하려면 torch가 있는 code/.venv 로 실행
.venv/bin/python -m hackathon.run_all --drop ../data/hackathon_2026 --name hackathon_2026
# ③ 보고서를 읽는다
#    ../outputs/hackathon/hackathon_2026/intake_report.md   무엇을 받았고 어떻게 읽었나
#    ../outputs/hackathon/hackathon_2026/report.md          단계별 결과, 제안 값 vs 지금 값, 주의
```

받아들일 항목만 골라 데모에 반영합니다.

```bash
python -m hackathon.params --activate ../outputs/hackathon/hackathon_2026/params_proposed.json --only hr_to_mr dose
python build_demo_data.py && python build_demo_html.py      # 데모에 반영
python -m hackathon.params --show                            # 지금 쓰는 값과 출처
python -m hackathon.params --reset                           # 문헌값으로 되돌리기
```

데모 왼쪽 "대사량 모델 보정"의 설명과 옵션 아래 문구("파라미터: …")에 지금 쓰는 값과 출처가 나옵니다.

## 2. 데이터 종류별로 하는 일

| 받은 데이터 | 자동으로 하는 일 | 데모에 들어가는 값 |
|---|---|---|
| 심박 + 대사량(W, BTU/h, kcal) 또는 VO2 | 심박 → 대사량 회귀식 다시 맞추기, 기존 Hoffmann 식의 오차(Bland-Altman) | `hr_to_mr` (EVA 시뮬레이션의 심박 환산) |
| 대사량 + 속도(+ 경사, 지면 종류) | 지면별 지형계수 η, 모래면 η = a + b/V² | `eta_surface_add`, `eta_sand` |
| 속도 + 경사 (자율 보행) | 경사별 보행 속도식 V = v0 − c·경사 | `speed_model` |
| 선량률 시계열 | 배경 선량률, SPE 구간과 최대 배율 (Gy면 Q 3.05로 Sv 환산) | `dose` |
| 지형 (PDS IMG+LBL, GeoTIFF, npy) | 10 m 칸으로 묶어 산소 귀환 반경 계산, 지도 | (새 지역 데모 입력, 아래 4절) |
| 영상 + 분할 마스크 쌍 (8쌍 이상) | 기존 SmallUNet(AI4Mars)에서 이어서 학습, 전후 시험 IoU 비교 | (지형 분류 모델) |
| 탱크 압력 시계열 | 표시만 (압력 방식 시뮬레이션 검증용) | – |
| 문서, 그 밖의 파일 | 목록만 | – |

### 열 이름이 달라서 못 알아볼 때
데이터 폴더에 `columns.json`을 두면 열 역할을 직접 지정할 수 있습니다.

```json
{"eva_physio.csv": {"hr": "HR", "mr": "Met Rate (BTU/hr)", "speed": "Vel", "grade": "Incline (deg)", "surface": "Terrain"}}
```

단위는 열 이름 괄호에서 읽습니다. 예: `(BTU/hr)`, `(km/h)`, `(deg)`, `(uGy/h)`, `(mGy/day)`, `(psi)`.

### 영상 마스크 값이 우리 클래스와 다를 때
`--class-map class_map.json`을 줍니다. 마스크 값(또는 색 `#rrggbb`)을 우리 클래스 번호로 바꾸고, 무시할 값은 255로 둡니다.

```json
{"classes": ["soil", "bedrock", "sand", "big_rock"], "map": {"0": 0, "1": 1, "2": 2, "3": 3, "255": 255}}
```

클래스 수가 바뀌면 출력층(head)만 새로 만들고 나머지 가중치는 이어 받습니다.

### 자료 조건 옵션
- **중력·질량:** 지구에서 잰 자료면 기본값(`--g 1.0`)을 씁니다. 짐이나 우주복 무게가 있으면 `--load-kg`를 넣습니다.
- **속도를 정해 놓고 걸은 실험:** `--forced-speed`를 주면 속도식을 건너뜁니다.

## 3. 안전장치
- **보정 결과는 "제안"입니다.** `params_proposed.json`에 쓸 뿐, `--activate` 전에는 데모가 바뀌지 않습니다.
- **가짜 데이터는 반영되지 않습니다.** 가짜 데이터 폴더(`SYNTHETIC.txt`가 있음)에서 나온 제안은 활성화가 거부됩니다.
- **지구 자료 경고:** 지구에서 우주복 없이 걸은 속도처럼 화성 EVA에 그대로 쓰면 안 되는 값은 보고서 "주의"에 표시합니다. 예: 평지 속도가 1.0 m/s를 넘는 경우.
- **출처 기록:** 모든 값에 출처(`source`: 자료 이름, n, R²)가 남고, 데모에도 표시됩니다.

## 4. 새 지역으로 데모 만들기 (다음 단계)
지금은 `dem_walkback`이 새 지형의 귀환 반경 지도와 격자(`return_o2_g.npy`, `elevation_cell.npy`)까지 만듭니다. 올인원 데모를 새 지역으로 만들려면 `build_demo_data.py`의 `load_scene()`을 지역 설정 파일로 바꿔야 합니다. 바꿀 것은 지형 경로, 자를 범위, 거점 위치, 정사영상입니다. 해커톤 지형 형식을 본 뒤 하는 게 효율적이라 남겨 두었습니다.

## 5. 가짜 데이터 점검 결과 (`outputs/hackathon/synthetic_check/report.md`)

```bash
python -m hackathon.make_synthetic          # ../data/hackathon_synthetic
.venv/bin/python -m hackathon.run_all --drop ../data/hackathon_synthetic --name synthetic_check --load-kg 20 --epochs 8
```

| 항목 | 정답 | 추정 |
|---|---|---|
| 심박 회귀 a / b (BTU/h) | −300 / 16 | −304 / 16.0 |
| 모래 η a / b | 1.8 / 1.0 | 1.65 / 1.14 |
| 속도 v0 / c | 1.30 / 0.015 | 1.30 / 0.0195 (지구 자료 경고 표시됨) |
| 배경 선량 (mSv/day) | 0.659 | 0.664 |
| SPE 최대 배율 | 4 | 4.24 |
| 지형 분할 시험 mIoU | – | 0.18 → 0.71 (가짜 영상 18장 학습) |

- **모래 η:** 6% 측정 잡음과 좁은 속도 범위(0.8~1.1 m/s) 때문에 a와 b가 서로 맞바뀌듯 조금씩 벗어납니다.
- **속도 c:** 가짜 자료에서 단단한 지면 오르막이 연속된 두 세션뿐이라 생긴 표본 오차입니다. 같은 방식으로 표본을 늘리면 0.0147~0.0151로 수렴합니다.
- **실제 자료에서는** R²와 n을 보고 판단하세요.
- **심박 범위 경고:** 심박이 230을 넘거나 30 미만이면 경고합니다. 처음 만든 가짜 자료에서 실제로 걸려 자료를 고쳤습니다.
- **알려진 한계:**
  - 열 이름 추정은 영어·일반 표기 기준입니다.
  - 엑셀(.xlsx)은 CSV로 저장해서 넣어야 합니다.
  - GeoTIFF 좌표계는 rasterio가 있을 때만 읽습니다. 없으면 화소 크기만 읽습니다.
