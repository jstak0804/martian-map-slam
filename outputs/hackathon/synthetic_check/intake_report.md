# 데이터 접수 보고서

- 폴더: `../data/hackathon_synthetic`
- 파일 54개

## 종류별

| 종류 | 개수 | 예시 |
|---|---|---|
| dem | 1 | `site_dem.tif` |
| document | 1 | `notes.md` |
| json | 1 | `truth.json` |
| seg_pair | 48 | `seg/images/scene_000.png` |
| table | 3 | `SYNTHETIC.txt` |

## 돌릴 수 있는 단계

- **hr_regression**: 심박 → 대사량 회귀식 다시 맞추기 (calibrate_metabolic) ← `eva_physio.csv`
- **terrain_factor**: 지면별 지형계수 η, 개인 보정 k (calibrate_metabolic) ← `eva_physio.csv`
- **speed_model**: 경사별 자율 보행 속도식 (calibrate_metabolic) ← `eva_physio.csv`
- **dose**: 배경 선량률, SPE 배율 (calibrate_dose) ← `rad_dose.csv`
- **dem_walkback**: 새 지형에서 귀환 반경 계산 (dem_walkback) ← `site_dem.tif`
- **segmentation**: 지형 분할 U-Net 미세조정 (finetune_segmentation) ← `.`

## 표 데이터: 열 역할 추정

열 이름으로 추정했습니다. 틀리면 데이터 폴더에 `columns.json`을 두고 다시 실행하세요.

- `SYNTHETIC.txt` (0행): (추정된 역할 없음)
- `eva_physio.csv` (1800행): time=`Elapsed (s)`(s), hr=`Heart Rate (bpm)`(bpm), mr=`Metabolic Rate (W)`(W), speed=`Walking Speed (m/s)`(m/s), grade=`Grade (%)`(%), surface=`Surface`()
- `rad_dose.csv` (240행): time=`hour`(h), dose=`dose_rate (uGy/h)`(ugy/h)

## 영상·마스크

- 쌍 24개, 마스크 없는 영상 1개, 영상 없는 마스크 0개
