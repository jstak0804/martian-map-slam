# 화성 전역 탐색 + Jezero 지도 중심 EVA UI — 구현 계획

> **Claude Code 인수인계 기준 — 2026-11-14:** 다음 작업자는 **§15~20을 먼저 읽고 실행**한다. 이 문서는 대화 기록 없이 이어갈 수 있는 실행 지침이다. §1~13은 요구사항과 차수별 이력이며, 오래된 미체크 항목·예정 파일명·일정은 현재 TODO가 아니다. 충돌 시 사용자 요구 → §15~20의 현재 상태/작업 순서 → §14 검증 결과를 우선한다. 최신 제품은 이미 IST·16방향, 영어 UI, 실제 사진, 실시간 남은 일정 예측을 구현했다. 정밀 영상 정합과 실기 QA는 완료하지 않았다. 이번 인수인계 개정은 문서 작업이며 제품 재빌드/추가 실험 결과를 뜻하지 않는다.

**바로가기:** [현재 상태와 요구사항](#15-claude-code-시작점과-현재-기준) · [실행 명령과 재빌드 순서](#16-환경-실행-검증-재현-절차) · [코드와 데이터 구조](#17-구현-구조와-데이터-계약) · [남은 구현·실험](#18-후속-실험과-구현-작업-명세) · [실기 QA](#19-브라우저모바일-검수와-최종-산출물) · [인수인계 체크리스트](#20-다음-작업자의-시작종료-체크리스트)

> **2026-11-14 UI 개정:** 사용자 지침 0~8은 §10의 구현 계약으로 반영했다. 전체 화면 지도·관측 POI·3종 시간·A/B 시나리오·visor 동기화가 필수다. 계획 개정 후 사용자 지시로 UI 구현에 착수했다. 현재 구현/검증 상태는 §14의 재감사 결과를 따른다.

**Goal:** 전체 화면 지도를 중심으로 POI 선택·관측 팝업·가는/복귀/체류 시간·A/B 시나리오·연동 visor를 제공한다. 화성 전역을 탐색하며 지역별 자료·분석 준비 상태를 확인하고, 준비된 세 지역의 기존 분석 화면으로 진입한다. Jezero에서는 기존 `martian-map-slam` 화면에서 다중 영상으로 보완한 국소 지형·관측 공백을 보여주고, 같은 과학 목표에 대해 안전 제약 → 왕복 대사 에너지 → 시간 순으로 경로를 판단하는 Jezero 시연을 완성한다.

**Architecture:** 같은 HTML에 가벼운 2D 전역 탐색 화면을 추가하고, 기존 `loadSite()`로 상세 분석에 연결한다. 전역 화면과 국소 계산의 좌표·데이터를 분리한다. 기존 단일 HTML·Canvas 지도·지역 전환·로드뷰·HUD·귀환 트리를 유지한다. 영상 처리는 Chrome 원격 데스크톱으로 접속하는 RTX 5060 Ti PC에서 사전 계산하고 작은 결과만 HTML에 포함한다. 선택 도구의 GPU 지원을 확인하며 CPU 경로도 유지한다. 수정본 IST 계산을 Jezero에 한정해 연결하며 다른 지역의 기존 계산과 분리한다.

**Tech Stack:** 기존 Python/NumPy/SciPy/Pillow와 브라우저 JavaScript. 추가 영상 도구는 아래 G1 조건을 만족한 한 경로만 사용한다. 전역 화면도 Canvas와 이미지 타일로 구성한다. 새 웹 프레임워크·서버·학습 모델·SLAM 엔진은 도입하지 않는다.

**Spec:** 최신 UI 계약은 §10, 데이터/계산 계약은 §1~6과 [RESEARCH.md](RESEARCH.md)를 따른다. 이전 계획과 검증 폴더의 고정 체류·귀환 비용 20% 가산 규칙은 신규 UI의 기본 정책을 대체하지 않는다.

## 1. 확정 조건과 이번 선택

- 사용자 확정: Jezero 삼각주/Perseverance, 기존 GitHub 산출물 수정·보완, 다수 영상 합성, 3~4명, **30시간**, **RTX 5060 Ti 사용 가능·Chrome 원격 데스크톱 접속 가능**. GPU PC의 VRAM 용량·시스템 RAM·운영체제·드라이버·도구 설치 상태는 미확인이다. 앞서 확인한 RAM 약16GB를 원격 PC 사양으로 자동 적용하지 않는다.
- 시간은 착수 시점을 H0으로 하는 경과시간이다. 기존 3인 54~60인시/30시간 목표는 UI 개정 전 추정이다. 추가 필수 범위를 포함한 66~72인시 재추정과 작업 교환은 §10.8을 따른다.
- 사용자 합의: **전역 탐색 + Gale/Jezero/Aram 상세 분석 + Jezero 다중 영상 시연**. 임의 지역의 자동 자료 수집·정합·정밀 경로 계산은 후속 과제다. 전역 배경 지도가 있다는 이유로 전역 EVA 분석이 가능하다고 표시하지 않는다.
- 안전은 선택한 경사·장애·자원 제약의 충족을 뜻한다. 실제 유인 탐사 안전 인증이나 완전한 다중자원 최적화를 주장하지 않는다.
- 1개 회랑, 탐사자 1명, 고정 가상 거점 1개. 여러 관측 POI 중 최대 2개(A/B)를 선택하며 A만/B만/A+B를 지원한다. 고정 10분 체류는 폐기하고 체류 가능 시간을 역산한다. 작업 대사량은 평지 보행값을 대리값으로 쓰는 가정이다.
- 사진 6~10장 제한은 폐기한다. **후보 100~300장·첫 처리 10~20쌍**은 작업량 목표이며 확보 수/성공률 약속이 아니다. 중복 다운로드를 사용 장수로 세지 않는다.
- 실제 작업 사본은 이미 IST·16방향을 사용한다. 8방향 신규 이식 계획은 이 상태 확인으로 대체한다. 기존16방향을 유지하고 Jezero EVA의 간선 경사·대각선 모서리·위험 셀 제약을 보완한다.
- 고정 Jezero 정책: 신체 75kg·우주복 90kg·IST 속도/대사·기존 정지값 약222W는 모델 가정이다. 산소는 §10.3의 Apollo 참고 프로필과 초기량 대비 20% 하한을 사용한다. 물은 기존 3.6kg와 351.684W×1,800초 환산 예비분을 별도 가정으로 유지한다.
- 20%는 **출발 산소량 대비 복귀 시 잔존량의 하한**이다. 귀환 비용에 1.2를 곱하는 옛 정책을 교체한다. 산소 고정 30분 예비분을 중복 가산하지 않으며 물에 산소 20%를 자동 적용하지 않는다.
- 자료 출처의 위치와 가상 인간 임무의 거점·목표·현장 사건을 분리한다. 기존 로버 이동 성공을 인간 통행 검증으로 사용하지 않는다.

## 2. 기준 버전·재사용 범위

[Confirmed] 앞선 조사 기준 커밋은 `5940cfd051e3267c23e7ee30775b8abf26f63420`다. [GitHub 기준](https://github.com/jstak0804/martian-map-slam/tree/5940cfd051e3267c23e7ee30775b8abf26f63420). 현재 작업 사본은 `C:/nasa/martian-map-slam/`이며 구현 착수 시 실제 상태를 다시 기록한다.

[Confirmed] 이전 `81a158b`와 비교한 메인 `code/` 변경은 `make_visor_video.py`이며, 새 `walkback_verification/`와 영상이 추가됐다. 검증 폴더의 README도 메인 모델에 아직 합치지 않았다고 명시한다. 그러므로 검증 폴더가 존재하는 것과 메인 데모가 IST로 작동하는 것은 별개다.

| 유지 | 이번 보완 | 제외 |
|---|---|---|
| 기존 지도 엔진·한영 전환·로드뷰·HUD·3개 지역 | 지도 전체 화면 재배치, 관측 POI 팝업, Jezero 모델·A/B 시간·visor 동기화 | 새 GIS 엔진·웹 프레임워크 |
| 배포된 `outputs/demo/` 격자·배경 | 별도 `local_terrain` 결과와 출처 | 원본 DTM 전체 재생성 |
| 기존 귀환/방문 탐색 구조 | 캐시 버전, 자원 검사, 제한적 탐색 문구 | 16방향·Pareto 다중자원 탐색·목표 7개 완전 보장 |
| 검증 폴더의 IST 함수·계수 | 필요한 계산만 이식·수치 대조 | 검증 폴더 전체를 메인에 덮어쓰기 |

[Confirmed, 2026-11-14 갱신] `martian-map-slam/data/downloaded/`에 기존 자료 4,712개를 확보했다. Jezero HiRISE DTM/정사영상·CTX·Navcam·메시·PLACES/SPICE가 포함된다. 다운로드 성공은 좌표 정합/제품 적용 완료가 아니다. 추가 Apollo 원문은 §10.7 참조. 원본 빌드의 투영·축·단위를 label과 대조하며 공개 제출 시 코드/자료 라이선스와 출처를 각각 확인한다.

제품 구현 경로는 `C:/nasa/martian-map-slam/` 기준이다. 착수 시 Git 상태 확인 후 필요한 별도 checkout을 만들 수 있다. 과거 Linux 경로를 현재 환경에 가정하지 않는다. 초기 계획 작성 시에는 제품을 변경하지 않았으며, 이후 사용자의 구현 지시에 따라 제품과 HTML을 수정했다.

## 3. 성공 기준과 실패를 감추지 않는 분기

**필수 제품:** 화성 전역 2D 지도가 열리고 위치 선택·이동·확대·자료 상태 확인이 가능하며, 준비된 세 지역의 기존 분석 화면으로 연결된다. 오프라인에서는 포함한 저해상도 전역 지도와 기존 세 지역 상세 자료를 사용한다. Jezero 데모가 오프라인으로 열리고, 실제 여러 영상의 합성 결과·출처·관측 공백을 보여주며, 국소 차단 사건 전후 같은 목표의 왕복 비용/가능 여부가 실제 재계산된다. 기존 화면에 통합해야 하며 별개 슬라이드만으로 대체하지 않는다.

**영상 목표:** 공통 좌표계를 확인한 국소 3D 결과 1개. 지도 좌표 정합이 불충분하면 로버 기준 국소 보기까지만 허용하고 경로 비용에 직접 넣지 않는다. 가상 사건으로 경로 변화 원리를 시연할 수 있으나 실제 복원 결과가 위험을 발견했다고 주장하지 않는다.

| Gate | 시간 | 통과 증거 | 실패 시 결정 |
|---|---:|---|---|
| G0 | H2 | 고정 baseline HTML 열림, 환경/권한/입력 목록 기록 | 실행 가능한 팀 PC로 시연 담당 이전; 데이터/권리 장애는 별도 기록 |
| GW | H6 | 전역 배경·좌표·지역 카드·세 지역 연결, 오프라인 저해상도 지도 | 온라인 타일 확장은 중단하고 포함한 전역 지도 이동/확대와 지역 연결 유지. 전역 배경 자체가 없으면 목표 미달 기록 |
| G1 | H4 | 회랑 1개·실제 영상 ID·공통 frame의 PDS XYZ/mesh 또는 사용 가능한 스테레오 보정 자료 확보 | 회랑 후보를 한 번만 변경; 다운로드/도구 탐색을 무제한 연장하지 않음 |
| G2 | H8 | 최소 2개 겹치는 관측 묶음의 결합 결과, 출처·스케일·잔차·처리시간 기록 | 신규 metric 3D 파이프라인 중단. 기존 파생 제품 검증 또는 파노라마로 축소, **3D 목표 미달** 표시 |
| G3 | H12 | IST Python–JS 대조, 경사/모서리/NoData 테스트 통과 | 모델을 몰래 옛 값으로 되돌리지 않음. 구현 범위를 추가 축소하고 미완료 기능 표시 |
| G4 | H18 목표 | POI 팝업·A/B 선택·3종 시간·지도/visor 동기화·사건 재계산 | 검증된 2개 POI로 제한 가능하나 A/B 기능 삭제 금지. 필수 미완료면 일정 재산정 |
| G5 | H24 | 제품 동결, 오프라인·한영·자원·지역전환 검사 통과 | 새 기능 금지, 치명 오류와 표시 오류만 수정 |
| 제출 | H30 | HTML·영상·출처·검증 기록·한계 패키지 | 완료하지 못한 목표를 제출 설명에 남김 |

**수치와 품질 기준의 성격:** 아래 2px·1셀·10초 등은 프로젝트의 임시 수용 기준이며 논문이 보장한 정확도나 NASA 안전 기준이 아니다. 기준 변경은 `reports/jezero-validation.md`에 이유를 남기며 결과에 맞춰 조용히 완화하지 않는다.

## 3.1 전역 탐색의 의미와 이번 범위

| 화면 | 제공 | 제공하지 않는 것 |
|---|---|---|
| 전역 | 배경 지도, 위경도 선택, 등록된 지역의 데이터 상태, 상세 분석 진입 | 전역 보행 경사/소모품/안전 경로 계산 |
| Gale·Aram | 기존 지역 산출물과 모델/가정 표시 | Jezero용 새 검증이 동일하게 적용됐다는 주장 |
| Jezero | 새 관측·합성 결과·자료 공백·조건부 왕복 재계산 | 전체 Jezero의 지상 관측 완료 또는 실제 EVA 안전 보장 |
| 미등록 위치 | 전역 맥락, 좌표, ‘상세 분석 자료를 아직 확인하지 않음’ | 실제 데이터가 존재하지 않는다는 단정, 정밀 계산 버튼 |

전역에서 지역 마커/카드를 누르면 기존 지역 전체 보기로 이동한다. 임의 클릭 위경도를 국소 격자의 출발점으로 자동 변환하지 않는다. 상세 화면의 ‘화성 전역으로’ 버튼은 이전 전역 중심/확대 상태를 복구한다. 3D 회전 지구본·지명 검색·전역 데이터 인덱스 구축·정밀 분석 지역 자동 추가는 제외한다.

**30시간 범위 교환:** 지도 중심 UI와 A/B 선택을 필수로 승격한다. 온라인 고해상도 타일 확장·신규 직접 스테레오 복원 확장·추가 레이어 선택기를 후순위로 내리고 확보한 PDS 제품/기존 렌더러를 재사용한다. 신규 핵심 버튼/상태는 한영 대응한다. §10.8의 일정 재평가를 적용하며 필수 UI를 조용히 삭제해 종전 일정에 맞추지 않는다.

## 4. 데이터 계약 — 병렬 작업이 만나는 지점

`outputs/global_mars/catalog.json` (신규, 빌드 시 HTML에 포함):

```text
schema_version:1
basemap:{product_id,capabilities_url,resource_url_template,matrix_set,
         crs,axis_order,longitude_domain,tile_matrices,credit,
         retrieved_at,offline_image,offline_bounds}
regions:[{id:"gale"|"jezero"|"aram", name,
          center_lonlat:null|[lon,lat], footprint:null|GeoJSON,
          location_source:null|URL, detail_available:boolean,
          data:{orbital_image,elevation,ground_images,local_reconstruction},
          analysis:{model_id,verification_status,evidence_ref}}]
```

각 `data` 항목은 `{status:"packaged"|"catalog_only"|"not_checked"|"not_applicable", product_ids:[], source_urls:[]}`로 통일한다. 복원 처리 상태는 별도 local manifest를 참조한다. `detail_available`은 해당 지역 HTML 입력이 패키지에 실제 존재함을 뜻하며 안전 검증을 뜻하지 않는다. `verification_status`는 `legacy_demo` / `prototype_checked` / `pending` 중 하나로, 새 테스트를 실행하기 전 `prototype_checked`를 쓰지 않는다.

등록된 3개 지역만 감사한 정적 목록을 만든다. 미등록 위치의 상세 데이터 상태는 `not_checked`로 반환한다. 원제품 투영/footprint를 확인하지 못한 지역은 지도 마커를 추정 좌표에 그리지 않고 이름 카드로 연결한다. 검증된 대표점도 분석 가능한 면적 전체를 나타내는 것으로 표시하지 않는다. 관측 영역 폴리곤이 없는 경우 핀을 반경 원으로 확대하지 않는다.

`outputs/local_terrain/jezero/manifest.json` (신규, `schema_version: 1`):

```json
{
  "schema_version": 1,
  "site_id": "jezero",
  "status": "local_only",
  "source_products": [],
  "station_ids": [],
  "frame_id": null,
  "units": "m",
  "grid_registration": null,
  "quality": {},
  "assets": {},
  "observed_cells": [],
  "blocked_cells": [],
  "unknown_reason": "orbital registration not verified"
}
```

- `status`: `registered` / `local_only` / `panorama_only` / `unavailable`. `registered` 이외에는 셀 단위 자동 지도 갱신 금지.
- `source_products[]`: `{id,url,credit,sha256,sol,utc,camera,site_drive,product_kind,label_url}`. 미확인 값은 `null`; waypoint의 sol을 촬영 sol 대신 넣지 않는다. `product_kind`는 `raw/calibrated/xyz/mesh` 중 하나.
- `station_ids[]`: 실제 촬영 묶음 ID. 같은 sol만으로 같은 위치라고 간주하지 않는다.
- `grid_registration`: `{target_site_id,method,transform,control_count,holdout_count,holdout_rmse_m,holdout_max_m,p95_m}` 또는 `null`. `transform`의 행렬 크기/축/원점을 `method` 설명에 함께 저장한다. 검증점과 정합에 사용한 점은 구분한다.
- `quality`: `{input_image_count,used_image_count,stereo_pair_count,source_mesh_count,valid_fraction,registration_rmse_m,reprojection_median_px,runtime_s,peak_rss_mb,peak_vram_mb,processing_device}`. 해당하지 않는 지표는 `null`; 기존 PDS 제품을 결합했으면 직접 스테레오 복원한 쌍 수를 늘려 세지 않는다.
- `assets`: `{preview,coverage_preview,mesh,panorama}`의 상대 파일 경로, 없는 것은 `null`. 브라우저에는 최대 2,048px 합성 미리보기와 출처만 임베드한다. 전체 원사진·큰 메시 파일은 연구/제출 부속 자료로 둔다.
- `observed_cells[]`, `blocked_cells[]`: 기존 Jezero row-major 셀 ID(`row*cols+col`)의 중복 없는 정수 배열. 관측 범위는 사진 검색 반경과 별개다. 자동 `blocked_cells`는 검증된 metric 형상에서 팀이 검토한 기하학 장애만 허용한다. 모래 지지력 추정은 넣지 않는다.

`outputs/local_terrain/jezero/mission.json` (신규):

```text
schema_version=2, site_id="jezero", model_id="ist_demo_v2",
base_cell:int, selected_poi_ids:string[0..2], visit_order:string[],
dwell_policy={mode:"max_feasible", allocation:"equal", weights:number[]},
oxygen_profile_id="apollo_j_demo_v1", initial_pressure_psia=1430,
initial_o2_g=816.466266, min_return_fraction=0.20,
water_g=3600, water_reserve_policy="legacy_30min",
k=1, extra_heat_w=0, known_leak_g_s=0, fixed_o2_reserve_g=0,
profile_status="historical_reference_with_assumptions",
require_los=false, unknown_policy="warn",
event={id:"blocked_patch_1", kind:"synthetic", cells:int[], label:string}
```

거점/목표/사건 셀은 실자료 확인 후 T2에서 확정해 저장한다. 임의 위경도를 지금 만들어 적지 않는다. 선택 기준은 §6 T2에 고정한다. `require_los=false`이면 가시선은 설명층이며 통신 성공 보장이 아니다. 미관측 경로가 있으면 최종 판정은 반드시 ‘추가 관측 필요’다.

## 5. Review Focus — 반드시 테스트할 다섯 실패 조건

1. 같은 sol 또는 다음 sol의 다른 촬영 위치가 자동으로 같은 좌표가 되는 경우 → T2에서 `null/unverified` 유지.
2. 로컬 3D가 궤도 지도에 잘못 붙거나 단위/축이 바뀌는 경우 → T3에서 등록 금지·셀 마스크 비움.
3. Jezero IST/예비분 또는 지도 갱신이 다른 지역·옛 캐시로 새는 경우 → T4/T5에서 지역 왕복 전환·revision 테스트.
4. 최소 산소 경로 한 개의 실패를 모든 경로 불가능으로 말하는 경우 → T6에서 ‘검사한 경로 기준’ 판정 및 제한 표시.
5. 차단 후 왕복 비용을 다른 경로의 값끼리 섞거나 예비분을 이중 차감하는 경우 → T6에서 명시적 경로 적분·잔량 수지 테스트.

전역 추가 점검: 동서경/축/경도 경계·극점 오류, 타일 요청 실패를 관측 없음으로 오판, 배경만 있는 곳의 정밀 계산 허용을 TW에서 검사한다.

## 6. 작업별 구현 계약

### TW. 전역 탐색 화면과 기존 지역 연결 — C, H0~6 (약5인시)

**Files:** 신규 `code/build_global_mars.py`, `code/mars_overview.js`, `outputs/global_mars/catalog.json`, `outputs/global_mars/overview.jpg`; 수정 `code/build_demo_html.py`, `code/demo_template.html`; 신규 `tests/test_mars_overview.mjs`, `tests/test_global_packaging.py`.

**Interfaces:** `build_global_mars(out_dir:Path)->dict`; `normalizeLon(lon)->number`는 [-180,180); `lonLatToOverview(lon,lat,width,height)->{x,y}`; `overviewToLonLat(x,y,width,height)->{lon,lat}`; `getLocationStatus(lon,lat,catalog)->object`; `openDetail(siteId)->Promise<void>`; `showOverview()->void`. 폭/높이는 전체 등장방형 지도 기준이며 화면 이동/확대 역변환 후 적용한다.

- [ ] H0~2에 Mars Trek WMTS의 **전역 MOLA 색상 음영 지도 1종**을 후보로 확인한다. 제품 ID 후보는 `Mars_MGS_MOLA_ClrShade_merge_global_463m`. [공식 API](https://trek.nasa.gov/tiles/apidoc/trekAPI.html?body=mars)의 GetCapabilities에서 실제 ResourceURL, 확장자, matrix ID/크기, 좌표계, 범위/축을 읽어 catalog에 보존한다. 후보의 현재 요청 성공과 브라우저 표시 여부는 아직 미검증이다.
- [ ] 원시 고도 파일 대신 전역 **표시용 영상**만 사용한다. 2:1 등장방형·경도[-180,180)·위도[-90,90]로 정규화한 2,048×1,024 오프라인 배경을 제작하고 출처/경도 기준을 기록한다. 지도 영상 색을 고도값으로 해석하지 않는다. 지구 Web Mercator/EPSG:3857을 화성 데이터에 그대로 적용하지 않는다.
- [ ] 정상 온라인 모드에서는 viewport에 필요한 타일만 요청하고, 확인된 matrix 중 오프라인 배경보다 최대3단계 높은 해상도까지만 허용한다. 동시 요청4개·메모리 캐시64타일·요청 timeout10초·실패 재시도1회로 제한한다. 요청 실패는 ‘타일 불러오기 실패’이며 데이터 없음으로 확정하지 않는다. 상세 레이어의 공백과 서버/네트워크 오류를 구분한다.
- [ ] CORS/로컬파일 제한·네트워크 단절이면 인라인 전역 배경으로 전환하고 ‘저해상도 오프라인 지도’ 배지를 표시한다. 온라인/오프라인 모두 이동·확대·좌표 선택·지역 카드 진입이 가능해야 한다. 다운로드된 타일을 계속 쌓거나 전행성 고해상도 타일을 선제 수집하지 않는다.
- [ ] 전역 좌표는 행성중심 위도·동경을 기준으로 원제품 정의와 대조한다. 일반식 `x=(normalizeLon(lon)+180)/360*width`, `y=(90-lat)/180*height`; 경도는 wrap, 위도는 clamp한다. 극점은 그림 경계이며 면적·거리 계산에 이 평면 좌표를 사용하지 않는다.
- [ ] 세 지역의 위치/경계를 원제품 label 또는 공식 metadata와 대조한다. 확인된 것은 지도에 표시하고 미확인 것은 지역 카드만 제공한다. Jezero 데이터가 있고 로버 사진이 없는 셀도 ‘지상 관측 있음’으로 일괄 칠하지 않는다.
- [ ] 페이지 최초 진입 또는 `#mars`는 전역 화면, `#gale/#jezero/#aram/#jezero-evidence-demo`는 기존 상세 진입. `openDetail(siteId)`는 이름이 아닌 ID로 `SITE_LIST`를 찾고 기존 `loadSite()`를 호출한다. 타일 비동기 응답이 상세 화면/다른 viewport를 덮지 않게 generation을 검사한다. 전역의 선택 좌표와 `state.base`는 별개로 유지한다.
- [ ] 기존 빌드에 `/*__MARS_OVERVIEW__*/`와 catalog/저해상도 배경 인라인을 추가한다. 입력 누락 시 빌드 검증이 전역 목표 미달을 보고해야 하며 조용히 Gale 기본 화면으로 대체하지 않는다.
- [ ] 시험: 경도0/±180/360 정규화, 북남극·클릭 왕복 좌표, 지구 좌표계 입력 거절, 등록지역 경계 밖 `not_checked`, 상세 미지원 클릭에서 경로함수 호출0회, 타일404/timeout/오프라인에서 배경 유지, 상세→전역 복귀, 빠른 지역 전환의 오래된 응답 폐기. `node --test tests/test_mars_overview.mjs`와 `python -m pytest tests/test_global_packaging.py -q` 실행 후 실제 브라우저 온라인/오프라인 확인.

**완료:** GW. H2까지 온라인 타일/투영 문제가 해결되지 않으면 나머지 시간은 오프라인 전역 배경+지역 연결에 사용한다. 공식 전역 영상 자체도 확보하지 못하면 전역 목표 미달을 남긴다. 더 높은 해상도 타일·새 레이어·폴리곤 확대는 후순위이며 H6 이후 추가하지 않는다.


### T1. 기준 데모·작업 환경 고정 — A, H0~2

**Files:** 신규 `reports/jezero-validation.md`, `reports/jezero-sources.csv`; 기존 `reports/18-eva-walkback-demo.html` 읽기.

- [ ] 기준 커밋 checkout, `git status --short`와 버전·HTML SHA256·빌드 입력 존재 여부 기록.
- [ ] 설치 전에 Python/Node/브라우저 가용성 확인. 사용한 패키지 버전을 기록하고 기존 환경을 임의 업그레이드하지 않는다. B는 원격 PC에서 `nvidia-smi` 결과(GPU명·VRAM·드라이버), 시스템 RAM·디스크 여유·OS, 선택 도구의 버전을 기록한다. CUDA 관련 표시만으로 해당 도구의 실행 호환성을 판정하지 않는다. H2까지 도구 자체의 작은 GPU 실행과 메모리 사용을 확인하고, 실패하면 CPU/기존 PDS 제품 경로로 진행한다. GPU 설정 문제 해결은 최대 1시간으로 제한한다.
- [ ] 기존 자산으로 `cd code` 후 `python build_demo_html.py` 실행. 결과 파일과 `#jezero` 진입을 확인한다. 이 명령은 구현 시 실행할 계획이며 이번 문서 작성 중에는 실행하지 않았다.
- [ ] 공개 제출용 코드 사용 권한·각 자료 출처를 기록한다. 확인되지 않은 항목은 미확인으로 남긴다.

**완료:** 기준 HTML은 유지되며 새 기능 실패 시 비교할 수 있다. 원본 DTM을 요구하는 전체 재빌드는 하지 않는다.

### T2. 실제 회랑·영상 목록·임무 좌표 확정 — B, H0~4

**Files:** 신규 `code/collect_jezero_observations.py`, `data/jezero_observations/catalog.json`; 신규 manifest/mission. 기존 `code/build_rover_photos.py`, `code/build_roadview.py`는 수집 함수 참고.

**Interfaces:** `collect_candidates(sol_start:int, sol_end:int, out_dir:Path)->dict`; `validate_catalog(catalog:dict)->list[str]`. API 응답을 원문 JSON과 함께 보존하며 현재 endpoint 실패 시 PDS 공개 목록으로 전환한다. 접근 차단을 우회하지 않는다.

- [ ] `tests/test_observation_catalog.py`: 중복 product ID 제거, 촬영 sol과 waypoint sol 분리, frame/pose 없는 사진의 `grid_registration is None`, 원해상도 URL과 미리보기 URL 구분을 검사한다.
- [ ] 후보 순서: 기존 목표 군집의 Skinner Ridge/Wildcat Ridge(sol443~535), 다음 Amalik(sol555~593). 이는 탐색 범위이며 정확한 시료 좌표 확정이 아니다. 각 범위에서 동일 site-drive·연속 관측을 우선한다. 초기 sol111/136 로드뷰를 삼각주 관측으로 대체하지 않는다.
- [ ] 다운로드 manifest에서 여러 POI와 인접 촬영 묶음을 선정한다. 후보 100~300장·첫 처리 10~20쌍 목표는 유지하되 받은 파일을 재다운로드하지 않는다. 최소 2개 접근 가능한 POI를 A/B로 지정하고 촬영 위치와 경로 접근 셀을 구분한다.
- [ ] PDS label의 카메라 모델·site-drive·좌표계·valid mask를 검사한다. METADATA 누락 제품은 시각적 자료로만 분류한다.
- [ ] 거점은 유효·경사20° 이하·위험 high가 아닌 연결 성분에서 선정한다. 지상 좌표를 기존 격자에 변환하려면 제품 투영 라벨을 확보해 원점·축·셀 크기를 검증한다. 원본 IMG가 없다는 이유로 화면 좌표를 지리 좌표인 것처럼 사용하지 않는다. 목표는 해당 관측 구역의 접근 가능한 셀로 정하되 원 관측점과 접근점을 별도 기록한다. §10.3의 Apollo 참고 산소/3.6kg 물 예산에 맞지 않으면 같은 관측 구역 내 거점을 가까이 옮긴 **가상 전진 거점**으로 명시하며, 실측 위치를 옮기지 않는다.
- [ ] 시험 명령 `python -m pytest tests/test_observation_catalog.py -q`; 예상은 위 모든 조건 PASS. fixture JSON은 API 실응답의 최소 사례로 만든다.

**완료:** 잠정 좌표가 정해진 `mission.json`, 추적 가능한 catalog, G1 판정. 자원 예산 적합성은 T4 모델 연결 후 T6에서 확정하고, 사건 전후 비교를 시작한 뒤에는 좌표를 바꾸지 않는다. 위치 자료가 없으면 3D/지도 정합을 확정하지 않는다.

### T3. 원격 GPU 다중 영상/지형 합성 — B, H4~12

**근거 경로:** [PDS stereo](https://planetarydata.jpl.nasa.gov/img/data/mars2020/mars2020_navcam_ops_stereo/), [PDS mesh](https://planetarydata.jpl.nasa.gov/img/data/mars2020/mars2020_navcam_ops_mesh/), [공식 입력 안내](https://github.com/NASA-AMMOS/Landform/wiki/Links-to-Publicly-Available-Input-Data). 제품 ID는 다운로드 manifest에 확보되어 있다. 제품 간 공통 frame/지도 정합은 아직 검증해야 한다.

**Files:** 신규 `code/build_local_terrain.py`, `outputs/local_terrain/jezero/`; 테스트 `tests/test_local_terrain.py`.

**Interfaces:** `build_local_terrain(catalog_path:Path, mode:str, out_dir:Path)->dict`; mode는 `pds_mesh`, `calibrated_stereo`, `panorama` 중 G1에서 하나를 기록한다. `validate_registration(manifest:dict, cell_m:float)->list[str]`는 오류가 있으면 `registered` 승격을 금지한다.

- [ ] 1순위는 **공통 frame의 여러 PDS XYZ/mesh와 대응 영상 결합**이다. 이는 공식 파생 제품의 재사용이며 자체 전체 스테레오 복원으로 발표하지 않는다. 서로 다른 frame 제품을 단순 XYZ 이어붙이기하지 않는다.
- [ ] 2순위 직접 스테레오는 보정된 좌우 영상과 투영/변환 모델이 있고, 기존 도구가 그 모델을 지원할 때만 허용한다. 일반 JPEG에 임의 초점거리·baseline을 넣지 않는다. 새 카메라 모델/SLAM 구현은 범위 밖이다.
- [ ] 파노라마는 정지점별 겹치는 영상의 정합·블렌딩을 수행한다. 기존 방위각 띠사진 나열은 합성 성공으로 세지 않는다. 파노라마에서 metric 깊이를 추정하지 않는다.
- [ ] 원격 PC에서 1묶음씩 처리하고 원본은 보존한다. 선택 backend가 해당 GPU에서 실제 실행되는지 확인한다. PDS 메시 결합 등 CPU 작업에는 GPU 효과를 가정하지 않는다. 첫 묶음에서 처리시간·최대 VRAM·시스템 RAM 사용·유효 복원 비율을 기록한 뒤 입력 수 또는 해상도를 한 가지씩 늘린다. 후보 100~300장·첫 10~20쌍은 유지하며 GPU가 있다는 이유로 전량 동시 처리하지 않는다.
- [ ] 첫 처리의 VRAM 목표는 장치 총량의 80% 이내로 두고, 메모리 부족 시 동시 처리량/작업 해상도를 줄인다. 여유 시스템 RAM 4GB 미만 또는 디스크 5GB 미만이면 다음 묶음을 보류한다. 단일 실행 60분 초과 시 해당 해상도 확장을 중단한다. 이는 초기 자원 정책이며 성능 보장이 아니다. 실제 VRAM/RAM 확인 후 G1 기록에 작업 크기를 확정한다.
- [ ] 원격 PC 로컬 디스크에 입력과 중간 결과를 두고 원격 터미널에서 처리한다. Chrome 원격 데스크톱은 화면 조작 수단이며 이 세션의 로컬 명령이 자동으로 그 PC에서 실행되는 것은 아니다. 연결이 끊겨도 작업 상태를 확인할 수 있도록 파일 로그·완료 상태·재시작 가능한 묶음별 출력을 남긴다. 절전/재부팅·세션 종료 시 작업 지속 여부는 작은 작업으로 확인한다.
- [ ] B→C 전달 묶음은 manifest·mission·미리보기·관측 마스크·처리/정합 로그·파일별 SHA256이다. 파일 전달 수단은 H2에 팀이 사용 가능한 방식으로 왕복 시험한다. 원본 영상/대형 메시를 HTML에 넣지 않으며 원격 PC 경로를 최종 패키지에 남기지 않는다. H8에 첫 결과를 전달하고 C가 해시·상대 경로·출처 ID를 검사한다.
- [ ] 직접 복원인 경우 영상 재투영 median≤2px를 초기 기준으로 기록한다. 지도 등록은 최소 3개 비공선 대응점과 별도 검증점 최소 2개, 검증 RMSE≤0.5셀·최대 오차≤1셀을 모두 요구한다. 충분한 점이 없으면 `local_only`. 작은 표본 오차는 전체 정확도 보장이 아님을 표시한다.
- [ ] 테스트: 1,000배 단위 오류/축 바꿈/다른 frame/검증점 없음 → 등록 거절; footprint 밖 셀 → 관측으로 채우지 않음; NaN 깊이 → 미확인 유지; panorama → `blocked_cells=[]`.
- [ ] 계획된 실행 `python code/build_local_terrain.py --catalog data/jezero_observations/catalog.json --mode <G1에서 선택한 모드> --out outputs/local_terrain/jezero`; 세부 backend 명령은 확보한 제품 label에 따라 G1 기록에 고정한다. 현재 특정 제품과 backend의 실행 성공은 미확인이다.

**완료:** G2 결과와 manifest, GPU/CPU 실제 실행 장치·사용량 기록 및 C에게 전달된 해시 확인 결과. H8 실패 시 3D 신규 개발 중단, H12까지 축소 결과를 C에 전달. 실측 형상으로 경로를 바꾸지 못한 경우와 가상 차단 시연을 분리한다.

### T4. Jezero 대사·예비분만 안전하게 연결 — A, H2~8

**Files:** 신규 `code/jezero_model.js`; 수정 `code/build_demo_html.py`, `code/demo_template.html`; 참고 `walkback_verification/code/metabolic_model.py`, `code/data/ist_model_coefs.json`(검증 폴더 내부). 신규 `tests/export_model_reference.py`, `tests/test_jezero_model.mjs`.

**Interfaces:** `createJezeroModel(istConfig)->{id,speed(gradePct),metabolicW(gradePct,eta),edge(gradePct,eta,distanceM),reserveO2G(),reserveWaterG(qW)}`. `edge`는 `{o2G,timeS,energyJ,extrapolated}`를 반환한다. 원 식·계수는 검증 폴더에서 옮기고 새로운 회귀는 하지 않는다.

- [ ] `tests/export_model_reference.py`를 실행해 `tests/fixtures/jezero_model_reference.json`을 만든다. Python reference 생성: 경사 `[-30,-20,-10,0,10,20,30]`%, η `[1,1.2,1.5]`, 거리 `[10,14.1421356]`m, 환경열 `[0,100]`W. metadata의 body75/suit90와 계산 파라미터가 같음을 검사한다.
- [ ] 기존 `C=META0.const`는 Gale 공유 상수이므로 덮어쓰지 않는다. 정책 선택자는 Jezero에 `ist_demo_v2`를 적용하고 나머지는 기존 정책을 유지한다. 신규 O2 하한은 `0.20*initial_o2_g`; 옛 45g를 더하지 않는다. 모델/프로필/잔량 정책을 캐시 키에 포함한다.
- [ ] `speedAt`, `mrOf`, `edgeO2`, `edgeT`, `levelMR`, `levelO2gh`, `waterReserve`, `budgets`에서 선택자를 사용한다. `pathTrack`, `localMR`, 구조 보급·HUD·시뮬레이션의 직접 `C.o2_reserve_g`/평지값 참조도 전수 검색해 같은 정책을 사용한다.
- [ ] Jezero에서는 기존 속도/내리막/η 추가/모래 문헌 옵션을 비활성화한다. 해당 토글은 다른 지역에서 기존 동작을 유지한다. IST와 기존 옵션의 이중 보정을 금지한다.
- [ ] `build_demo_html.py`가 검증 폴더의 계수와 명시적 고정 파라미터를 `jezeroModel`에 넣고 `/*__JEZERO_MODEL__*/` 한 위치에 JS를 인라인한다. 이미지 결과가 아직 없어도 모델 빌드는 가능해야 한다.
- [ ] `node --test tests/test_jezero_model.mjs`: 대사 reference 대비 상대오차≤1e-6(0 근처 절대1e-8), 평지 약444.396W 확인. 옛 예비O₂약45.005g는 legacy 비교 fixture로만 유지한다. 신규 20% 하한은 별도 테스트하며 질량/단위/속도 불일치 시 실패한다.
- [ ] 예비분 설명은 프로젝트 가정, 심박값은 합성/화성 보행 미검증으로 표시한다. 1,200 BTU/h를 원자료 상한이라 부르지 않는다.

**완료:** H8 모델 단위 대조. 전체 그래프를 바꾸지 않고 Jezero 계산과 표시의 모델이 일치한다. 모델 이식 미완료를 ‘검증된 모델 적용’으로 표시하지 않는다.

### T5. 그래프 제약·관측 레이어·캐시 — A, H8~12; C 연결 H12~16

**Files:** `code/demo_template.html`; 신규 `tests/test_jezero_graph.mjs`; 신규 `code/jezero_policy.js`(테스트 가능한 순수 제약·경로 비용 비교 함수만).

**Interfaces:** `grid={width,height,cellM,h,eta,valid,cls,rate1}`는 row-major 배열과 셀 크기(m), `overlay={revision,blockedCells,observedCells}`는 셀 ID 집합이다. `edgeAllowed(a,b,grid,policy,overlay)->boolean`; `compareCost(a,b)->number`, 비용은 `{energyJ,timeS}`; `applyObservationPatch(patch)->void`; `invalidatePlanning(reason)->void`.

- [ ] 기존 8방향 유지. Jezero `passMask`에서 NoData/high/차단 셀을 제외하고 base/src 강제 허용을 하지 않는다. 이 모드의 위험 칸은 경로 없음으로 반환한다. 긴급 탈출 알고리즘 추가는 범위 밖이다.
- [ ] `dijkstra`에서 양 끝점·대각선의 양 옆 칸·간선 `abs(atan2(dh,d))<=20°`를 검사한다. 기존 `descentRoute`가 이 금지를 우회해 안전 경로로 표시하지 못하게 Jezero 고정 시연에서는 비활성화한다.
- [ ] 비용 비교는 먼저 energyJ, 차이가 `1e-9*max(1,abs(Ea),abs(Eb))` 이내일 때 timeS. heap 정렬·완화·오래된 항목 검사 모두 같은 비교를 사용한다. 1차 비용은 k가 고정된 대사 에너지이며 누설/열은 후속 자원 제약으로 검사한다.
- [ ] 출발 셀이 금지이면 Dijkstra 시작 전에 거절한다. source=target도 예외가 아니다. `siteGeneration`을 지역 로드마다 증가시키고 `loadSite`의 decode/Image.decode 및 `ensureTrees`의 지연 실행 전후 generation/revision이 달라지면 오래된 결과를 적용하지 않는다.
- [ ] `overlayRevision`은 site별 정수. `modelKey()`에 site/model/revision을 `:`로 포함해 기존 `treeKey`의 `|` 구분자를 깨지 않는다. `TREES`, `LEGS`, `FWD`, `REV`, `FWDB`, `EVA/EVASIG`, `SIM/SIMSIG`, `LMR/LMR_KEY`를 무효화한다. 시뮬레이션은 정지하고 옛 결과를 숨긴 뒤 다시 계산한다. Gale 사전 계산 트리는 legacy/Gale/overlay0/기본옵션에서만 등록하고, 기존 `0000` 하드코딩과 신규 modelKey가 충돌하지 않게 수정한다. 거점 변경 시 LEGS도 비운다.
- [ ] 실제 patch는 `status=registered`일 때만 셀 반영. `kind=synthetic` 사건은 별도 레이어/라벨로 반영하며 원 manifest를 바꾸지 않는다. 고도 재조립 대신 차단 마스크만 사용해 전체 바이너리 재빌드를 피한다.
- [ ] 테스트: 막힌 대각선2×2 차단; 칸11.31°/간선21.80° 차단; NoData 거점 거절; 비대칭 경로 방향; 에너지 동률이면 시간 최소; patch 바깥 값 불변; 두 번 적용해도 중복 비용 없음; Jezero→Gale→Jezero에서 모델/캐시/patch 분리.
- [ ] 계획된 실행 `node --test tests/test_jezero_graph.mjs`. 브라우저 통합 검사에서는 실제 `dijkstra`가 같은 `edgeAllowed`를 호출하는지 확인하고, 차단 패치 적용 후 실제 반환 경로에 금지 셀/간선이 없음을 재적분한다. 순수 함수 시험만으로 화면 연결을 검증했다고 하지 않는다.

**완료:** G3. ‘16방향’, ‘미터 이하 보행 안전 검증’이라는 문구를 새 화면에 쓰지 않는다.

### T6. 동일 경로 왕복·관측 전후 비교 — A, H12~18

**Files:** `code/demo_template.html`, `code/jezero_policy.js`; 신규 `tests/test_mission_budget.mjs`.

**Interfaces:** `evaluateMission(paths,mission,grid,model,overlay)->MissionResult`; 반환 `{status,reasons,out,work,back,remaining,minReturnMargin,unknownCellCount,revision}`. status=`feasible_in_model/needs_observation/no_candidate/invalid_input`.

- [ ] `planEva()`의 경로 복원/적분을 재사용하되 선택 목표를 누락하는 부분집합 탐색을 금지한다. A만/B만은 각 왕복, A+B는 A→B/B→A 모두 평가한다. 가는 시간=마지막 목표까지의 이동 합계, 복귀 시간=마지막 목표→거점, 체류=작업 시간 합계다.
- [ ] 출발/중간/작업 전후 모든 지점에서 `consumedO2 + immediateReturnO2 <= 0.80*initialO2`를 검사한다. 최종 왕복에도 같은 하한을 적용한다. 물은 `consumedWater + immediateReturnWater + reserveWater <= initialWater`. 옛 `1.2*귀환비용+45g` 규칙을 신규 기본 시나리오에서 제거하며 §10.3의 모든 제약으로 체류 상한을 구한다.
- [ ] 선량을 표시할 때 `elapsedDose+returnDose`를 예산과 비교한다. 원래 귀환 선량만 보는 값을 전체 EVA 누적 보장으로 표시하지 않는다. 알려진 누설·열·작업은 경로/시간에 맞춰 누적한다.
- [ ] 안전 제약을 통과한 후보끼리 왕복 에너지→시간을 비교한다. 산소최소 후보가 다른 자원 제약에 실패하면 `no_candidate`와 ‘검사한 경로에서 조건 미충족’으로 표시한다. 전역 불가능/전역 최적 보장 금지.
- [ ] 관측 공백이 있으면 자원이 충분해도 `needs_observation`. 기하학 복원 성공만으로 `unknown`을 인간 보행 안전으로 승격하지 않는다.
- [ ] 사건 전후 **같은 거점·목표 집합·예산·모델·체류 배분비**를 유지한다. 기본 결과는 가는/복귀/체류 시간만 표시한다. 거리·에너지·산소·물·미관측 길이·출처 ID는 검산 로그/연구 보고서에 보존한다. 경로가 없으면 ‘경로 없음/계획 보류’를 표시한다.
- [ ] 테스트: 왕복 비대칭·산소20% 하한·10% 색 경계·물 제한 체류·A/B 배분 합계·선택 목표 누락 방지·45g 중복 차감 방지·Q100W·누설10g/h·누적 선량·미관측·사건 후 경로 불가. `node --test tests/test_mission_budget.mjs`.

**완료:** G4의 재계산 연결. 기존 다중 목표400후보 한계는 설명에 남긴다. 신규 결과는 수치 실험이며 실제 안전 확률을 표시하지 않는다.

### T7. 기존 화면에 합성 결과·이야기 통합 — C, H6~18

**Files:** `code/build_demo_html.py`, `code/demo_template.html`, `code/i18n_en.js`; 신규 `tests/test_local_packaging.py`.

- [ ] 먼저 manifest fixture로 UI를 연결해 B의 영상 처리와 병렬 진행한다. `build_demo_html.py`에 `local_terrain(site)`를 추가해 `sm["localTerrain"]`에 작은 manifest/미리보기/mission만 넣는다. 기존 `photos()`의 필드 화이트리스트가 새 provenance를 버리지 않도록 필요한 필드를 추가한다.
- [ ] `showPov`, `renderRv`, `paintPoint`를 지도 POI의 1인칭 관측 팝업으로 연결한다. 지도는 전체 화면, 대형 사이드바는 접는 메뉴로 변경한다. 초기 팝업은 짧은 지점명·보기·선택·3종 시간만 표시하고 원영상/합성·출처는 접는다. §10의 방향·확대·축척·시나리오·visor 동기화를 구현한다. 새 자유시점 3D 엔진 대신 기존 지형/HUD 렌더러와 관측 미리보기를 활용한다.
- [ ] 기존 EVA 영역에 `기준 계획 → 관측 확인 → 가상 차단 적용 → 귀환 재평가` 4단계 버튼을 추가한다. 고정 시작 URL `#jezero-evidence-demo`를 `devHash()`에 연결한다. 이후 다른 지역으로 전환하면 사건과 임무를 초기화한다.
- [ ] `siteTexts()`의 Jezero 옛 `baseline_km2`를 새 모델 면적으로 표시하지 않는다. 새 정책으로 계산한 값이 준비되기 전 ‘재계산 중’, 완료 후 모델명과 함께 표시하거나 이 통계를 숨긴다.
- [ ] NightIR는 ‘야간 IR 상대 밝기’, 위험층은 ‘DTM 기복/경사 대리 지표’, RAD는 ‘Gale 참고 시나리오’로 표시한다. ‘사진250m 안=관측 완료’, ‘열관성=단단한 지반’ 문구 제거.
- [ ] 테스트: manifest 없음/사진 없음/파노라마만 있음/등록 실패에서도 지도 동작; `<`가 포함된 출처 문자열 안전한 textContent 렌더; 기존 한국어/영어·HUD·로드뷰 토글 유지, 신규 전역/관측 상태·진입 버튼의 핵심 문구만 한영 대응; 미리보기 누락 시 빈 상태.
- [ ] `python -m pytest tests/test_local_packaging.py -q`, 이후 `cd code && python build_demo_html.py`. 신규 inline placeholder가 정확히 한 번 치환됐는지 검사한다.

**완료:** 기존 산출물의 형태가 유지되며 합성 결과가 최종 HTML에 실제로 포함된다. 원본 100~300장을 HTML에 전부 인라인하지 않는다.

### T8. 통합·오프라인·제출 — 전원, H18~30

**Files:** `reports/18-eva-walkback-demo.html`, `reports/jezero-validation.md`, `reports/jezero-sources.csv`, `reports/jezero-demo-script.md`, 제출용 `dist/jezero-demo/` (신규).

- [ ] 전체 신규 테스트 실행: `python -m pytest tests -q`(신규 checkout의 테스트만), `node --test tests/test_mars_overview.mjs tests/test_jezero_model.mjs tests/test_jezero_graph.mjs tests/test_mission_budget.mjs`. 대용량 검증 폴더의 느린 테스트 전체는 제출 필수 명령에 섞지 않는다.
- [ ] Chrome/Edge에서 로컬 HTML `#mars`, `#gale`, `#jezero-evidence-demo`, `#jezero`, `#aram`을 연다. 온라인 타일과 네트워크 차단 시 저해상도 전역 배경 전환을 먼저 확인한다. 네트워크를 끈 상태로 새 기능·지역 전환·한영·HUD·로드뷰·리셋을 확인한다. 현재 환경의 Windows Chrome 파일 존재와 실제 실행 가능성은 별개다.
- [ ] 최종 HTML 25MB 이하를 내부 목표로 측정한다(대회 공식 제한 아님). 초과 시 원본을 삭제하지 말고 임베드 미리보기 수/해상도를 줄인다. 대상 노트북에서 첫 지도≤10초·고정 재계산≤10초를 목표로 측정한다. 실패하면 영역 갱신 해상도/빈도를 낮추고 비동기 계산으로 재검증한다. 필수 walkback 채움이나 A/B 선택을 삭제하지 않으며 기준 미달을 기록한다.
- [ ] 3분 시연: 0~30초 화성 전역 탐색·자료 상태·Jezero 진입, 30~80초 실제 다중 관측/합성, 80~140초 같은 목표 경로 재평가, 140~180초 관측 공백·한계·귀환 판단. 입력 장수와 직접 처리/공식 파생 제품을 구분한다.
- [ ] 영상은 팀 PC 화면 녹화 우선. 기존 영상 스크립트의 Windows 절대 경로를 자동으로 작동한다고 가정하지 않는다. 기존 GitHub 영상은 새 기능의 증거로 재사용하지 않는다.
- [ ] 출처 CSV, 정책/오차/미완료 항목, 테스트 결과, 처리 지표, HTML SHA256, 실제 사용 제품 ID 목록을 함께 패키징한다. 재배포 허가가 없는 코드/자료는 공개 묶음에 넣지 않는다.

## 7. 기존 30시간 작업 순서 — 최신 인시·담당은 §10.8 적용

| 시간 | A 계산·통합 | B 영상·자료 | C UI·패키징 | D가 있으면 |
|---|---|---|---|---|
| H0~2 | T1 baseline·환경 | 원격 GPU/파일 전달 시험 + T2 제품 탐색 | TW 타일/전역배경·좌표 검증 | 자료 출처/기록 |
| H2~4 | T4 reference·adapter | G1 자료·회랑 확정 | TW 지역목록·상태·상세 연결 | 위치/원제품 교차검증 |
| H4~8 | T4 모델·예비분 대조 | 원격 PC 첫 결합·메모리 측정·G2·결과 전달 | H6 GW 후 T7 단일 패널·출처 | 합성 품질 독립검사 |
| H8~12 | T5 그래프·캐시·G3 | 복원 확장 또는 명시적 축소 | T7 정합/빈 상태·교대 휴식 | 그래프/문구 검사 |
| H12~18 | T6 왕복검사·휴식 교대 | 산출물/manifest 전달·휴식 | T7 실제자료 통합·휴식 교대 | 시나리오/검증 |
| H18~22 | 통합오류·경로 재현 | 자료·정합 검수 | 오프라인/브라우저 | 발표문·사용자 점검 |
| H22~24 | 치명 오류만·G5 | 출처/처리 기록 | 제품 동결·녹화 준비 | 영상 녹화 |
| H24~27 | 검증 기록 | 자료 누락 점검 | 3분 영상·제출 묶음 | QA |
| H27~30 | 제출 전 교차점검·버퍼 | 동일 | 동일 | 동일 |

공유 파일 소유권: `demo_template.html`의 계산·상태·캐시는 A, 패널 HTML/CSS·문구·화면 렌더는 C가 맡는다. H4에 편집 구역을 나누고 H8/H12/H18에 A가 통합한다. B는 catalog/manifest/asset만 전달한다. `build_demo_html.py`는 C가 소유하며 A의 모델 임베드 요구를 반영한다.

종전 A20h/B18h/C20h 추정은 UI 범위 추가로 대체된다. §10.8의 66~72인시와 역할 조정을 적용하고 H2에 30시간 가능 여부를 재평가한다. B의 복원 실패 시 fixture/가상 사건으로 UI를 진행할 수 있지만 모델 실패 시 계산된 것처럼 시간을 표시하지 않는다.

## 8. 변경 파일 목록·검증·승인 상태

신규 제품 파일은 `code/jezero_model.js`, `code/jezero_policy.js`, `code/collect_jezero_observations.py`, `code/build_local_terrain.py`에 전역용 `code/build_global_mars.py`, `code/mars_overview.js`를 더한 6개로 제한한다. UI와 빌드는 기존 `demo_template.html`, `build_demo_html.py`, `i18n_en.js`를 수정한다. 자료·시험·보고서는 위 작업별 경로를 따른다. T3 backend의 필요 모듈은 G1 결과에 따라 계획에 명시한 뒤 구현한다.

**대안 검토:** 기존 계산·Canvas·로드뷰·HUD를 재사용하면서 지도 중심으로 배치를 바꾸는 방식을 선택한다. 검증 폴더 전체 이식·16방향 변경·새 SLAM/NeRF·새 GIS 엔진은 제외한다. GPU 존재를 복원 정확도의 증거로 해석하지 않으며 파노라마 축소는 명시적 실패 분기다.

**이번 문서 작성 중 확인:** 실제 파일/함수/빌드 입력/기준 커밋을 대조했다. 새 영상 파이프라인, 신규 테스트 명령, 성능 수용 기준은 **계획**이며 아직 실행해 통과한 결과가 아니다. 실제 회랑/제품 ID·backend는 G1의 자료 확인 없이는 정직하게 확정할 수 없다. 그 불확실성을 시간 제한·산출물 계약·실패 분기로 관리한다.

**승인 상태:** 사용자는 전역 탐색+세 지역 분석+Jezero 상세 시연의 큰 방향을 승인했고 이번 계획 개정을 요청했다. 이는 제품 구현 승인이 아니다. 제품 코드·의존성·배포는 변경하지 않았다. 구현은 사용자의 계획 검토·명시적 승인과 구현 명령 후 시작한다.

## 9. 조사 근거

- [코드·함수·캐시 통합 계약](research/2026-11-14-plan-code-contract.md): 최종 후보는 11절.
- [영상·PDS·카메라 계약](research/2026-11-14-plan-imagery-contract.md): 제품군 접근과 실제 제품 확보를 구분. 초기 sol111/136은 도구 확인 후보일 뿐 삼각주 본 시연으로 채택하지 않음.
- [환경·빌드·전달 계약](research/2026-11-14-plan-delivery-contract.md): 81a158 당시 입력은 최신 메인 코드 diff와 대조함.
- 환경: 이전 머신의 Python/venv 확인 기록을 현재 Windows의 설치 상태로 간주하지 않는다. 구현 착수 시 실행 파일·패키지·브라우저를 다시 확인한다.

- 전역 자료 범위 근거: [Mars Trek WMTS API](https://trek.nasa.gov/tiles/apidoc/trekAPI.html?body=mars), [HiRISE DTM 설명](https://www.uahirise.org/dtm/about.php). 전역 탐색 가능성과 상세 고도/지상 관측 확보를 구분한다.
- [전역 추가 전 30시간 계획](research/2026-11-14-local-only-30h-plan-superseded.md)은 보존용이다. 현재 계획이 범위·역할표·기본 진입 화면을 대체한다.

## 10. 지도 중심 UI 수정 계획 — 2026-11-14 사용자 지침 반영

### 10.1 전체 화면과 지점 선택

기존 기능을 전제로 지도 Canvas가 뷰포트 전체를 채운다. 전역 지도와 지역 상세 지도는 동일한 화면 구조를 사용하되 정밀 EVA는 데이터가 준비된 지역에서만 제공한다. 큰 상시 사이드바는 접는 메뉴로 옮기고, 지도 위에 작은 조작 요소와 선택 결과만 겹친다.

| 위치 | 표시/조작 |
|---|---|
| 좌상단 | 지역명, 전역/지역 전환, 접는 설정 |
| 우상단 | 북쪽/진행방향 전환, 내 위치, +/−, visor 열기 |
| 좌하단 | 현재 확대에 맞는 m/km 축척 막대, 작은 범례 |
| 지도 | Base, 관측 POI, 선택 A/B, 탐사자·진행방향, 출발/복귀 경로, walkback 채움 |
| 하단 작은 카드 | 선택 지점 칩, 가는 시간·복귀 시간·체류 가능, 출발/정지/복귀 |
| 지점 클릭 팝업 | 실제 1인칭 관측 이미지/파노라마, 짧은 지점명, 선택/해제, 해당 시나리오의 3종 시간 |

- POI는 실제 제품 ID·촬영 시각·위치 근거가 있는 관측 정거장/과학 지점에서 만든다. 지점 수를 채우려고 가짜 좌표를 만들지 않는다. 여러 관측 마커를 표시하고 최소 두 개의 경로 접근 가능한 목표를 제공한다.
- POI를 열어 보는 것과 임무 목표로 선택하는 것을 분리한다. 클릭하면 미리보기, `선택`을 누르면 A/B 칩에 추가한다. 세 번째 선택은 `최대 2곳`을 표시하고 기존 선택을 유지한다. 선택 0개이면 시간을 `—`로 표시하고 출발을 비활성화한다.
- 팝업은 지도 안의 overlay로 구현한다. 실제 이미지가 없으면 `관측 없음`을 표시하고 다른 지점 이미지를 해당 지점 사진처럼 붙이지 않는다. 관측 위치와 접근 셀이 다르면 짧은 배지/출처 상세로 구분한다.
- 기본 화면에 산소 g/psi, 물 g, 에너지, 소모율과 장문의 설명을 노출하지 않는다. 이 값은 계산·검증 데이터로 보존한다. 기존 상세 분석 기능은 접는 고급 메뉴에 유지한다. 시간 카드에는 `가는 길 12분 · 복귀 14분 · 체류 38분`처럼 짧게 표시한다(예시 숫자는 실제 계산값이 아님).
- 처음부터 주 UI는 3종 시간만 표시한다. 거리도 기본 카드에 추가하지 않고 필요 시 지도 측정/상세로 제공한다. 범례의 10%/20%는 색 의미를 설명하는 정책 경계다.
- 긴 이름은 한 줄 말줄임+전체 이름 툴팁, 좁은 화면은 하단 시트 1개, ESC/닫기/키보드 초점 복귀를 지원한다. 선택·경고 상태는 색뿐 아니라 A/B 문자·아이콘으로도 구분한다.

### 10.2 A/B 시나리오와 시간의 의미

| 선택 집합 | 후보 경로 | 기본 표시 |
|---|---|---|
| A | Base→A→Base | 가는/복귀/체류 가능 |
| B | Base→B→Base | 가는/복귀/체류 가능 |
| A+B | Base→A→B→Base 및 Base→B→A→Base | 가는/복귀/총 체류 + A 체류·B 체류 |

- A/B는 선택한 실제 POI의 고정 ID에 붙는 짧은 표시명이다. 방문 순서가 바뀌어도 A와 B의 정체가 바뀌지 않는다. `A→B`/`B→A` 칩에서 순서를 고를 수 있고, 초기 추천은 제약 충족 후보 중 총 체류가 긴 순서, 동률이면 이동 에너지→이동 시간 순이다.
- A+B의 `가는 시간`은 Base에서 마지막 목표까지의 **이동 시간만** 합한다. 중간 체류는 포함하지 않는다. `복귀 시간`은 마지막 목표에서 Base까지다. 총 소요 시간은 세 값의 합이며 상세에서 확인 가능하다. 단일 지점 팝업의 단독 왕복 값과 현재 다중 시나리오 값을 섞지 않는다.
- 총 체류는 단일 공통 자원 예산으로 계산한다. 기본 배분은 A:B=1:1, 접는 조절에서 배분비를 바꿀 수 있다. `A 체류+B 체류=총 체류`를 유지하며 각각의 독립 최대 체류를 합산하지 않는다. 최소 작업 시간이 필요하면 POI별 `min_dwell_s`로 기록하고 못 채우면 해당 시나리오를 `체류 부족`으로 표시한다.
- 경로 후보를 평가한 뒤 정한 방문 순서/경로/체류량을 하나의 결과로 저장한다. 선택 지점을 몰래 빼서 가능한 것처럼 표시하지 않는다. 계산 중에는 출발을 잠그고 이전 결과를 흐리게 하며, 완료 시 revision이 일치할 때만 적용한다.
- 불가능·자료 부족은 시간 0과 구분한다. `경로 없음`, `예산 부족`, `추가 관측`, `계산 중`을 짧게 표시한다. 자원 조건이 충족되어도 미관측 지형은 검증된 안전 경로로 승격하지 않는다.

### 10.3 Apollo 산소 근거와 체류시간 계산

**원자료 확인과 가정 구분:** 기존 `walkback_verification/demo/README.md`의 540g/6.2MPa/21°C 탱크는 ISS 참고 가정이며 Apollo 1,430psi의 검증 자료가 아니다. 이번에 아래 원문을 추가 확보했다.

| 원문 | 확인한 값과 용도 | 적용 제한 |
|---|---|---|
| [Apollo 15 Press Kit](https://assets.science.nasa.gov/content/dam/science/psd/solar/2023/09/a/Apollo_15-1.pdf?emrc=6869761140557), 인쇄 p.110/PDF p.114 | Apollo 15 PLSS 산소 1,430 **psia**, feedwater 11.50lb | psia는 절대압. 압력 자체는 산소 질량이 아님 |
| [Historical PLSS comparison](https://ntrs.nasa.gov/api/citations/20100017516/downloads/20100017516.pdf), Table 1/PDF p.29 | Apollo primary O2 1.8lbm, 압력 1,420psia | 총량 참고값. 1,430psia의 정확한 압력–질량 곡선으로 취급하지 않음 |
| [Apollo 15 EMU assessment](https://ntrs.nasa.gov/api/citations/20160009500/downloads/20160009500.pdf), §4.3/인쇄4-21 | 명목 충전 1,410psia에서 usable O2 1.35lb, 물 10.86lb | 총 충전량과 사용 가능량의 정의가 다름. 1.8lb와 무조건 교체/차감하지 않음 |
| [Bellcomm B70 10028](https://www.apollojournals.org/alsj/19790073512_1979073512.pdf), 본문1~2쪽 | 계획 산소 1.3lb는 30분 소모품 예비분을 이미 제외. 비상 귀환 대사율 가산은 별도 가정 | 사용자 요구의 잔존20% 규칙과 다름. 이미 제외한 예비분을 이중 차감하지 않음 |
| [Apollo 15 Mission Report](https://ntrs.nasa.gov/api/citations/19720021182/downloads/19720021182.pdf) | 실제 임무 소모량/한계값 후속 대조용 원문 확보 | 이번에는 전체 표 수치 전사·검산을 완료한 자료로 표시하지 않음 |

**초기 구현 프로필:** `apollo_j_demo_v1`은 요청한 명목 출발압 **1,430psia**를 유지하고, 질량은 별도 역사적 총량 참고값 **1.8lb=816.466266g**을 채택하는 **명시적 시뮬레이션 가정**이다. 두 수치의 정확한 동일 조건 대응을 입증했다는 의미가 아니다. 원자료의 1,410/1,420/1,430 차이를 임의 평균하거나 압력 비례 보정하지 않는다. 실제 탱크 부피·온도·압축성·운용 불가 잔압 곡선을 확보하기 전 `1430psi → 검증된 정확한 g`라고 표시하지 않는다. 기존 600g 또는 540g를 압력 숫자만 바꿔 Apollo 값으로 쓰지 않는다.

잔존율의 분모는 **출발 총 산소 질량 M0**로 고정한다. 사용 가능량 1.35lb를 분모로 몰래 바꾸지 않는다. 새로운 프로필에서 운용 불가량이 검증되면 별도 하한과 사용자 20% 중 큰 값을 적용하고 버전을 올린다. 현재 결과는 역사적 용량을 참고한 화성 EVA 모델이며 실제 Apollo/Mars 장비 운용 한계 검증은 아니다. OPS 비상 산소는 정상 체류 예산에 합치지 않는다.

계산은 g·s·m·W 단위로 하고 표시할 때 분 단위로 내림한다. `M0=initial_o2_g`, `F=0.20*M0` (기본 약163.293253g)로 둔다. 이동 중 대사와 알려진 누설, 체류 중 작업 대사와 누설을 모두 적분한다.

```text
고정 경로들의 이동 소비량: O_move [g], W_move [g], T_move [s]
목표 i의 체류 배분비: w_i >= 0, sum(w_i)=1
목표 i의 작업 소비율: qO_i [g/s], qW_i [g/s]
체류 총량 D [s], 목표별 d_i = w_i*D

D_O2 = (M0 - F - O_move) / sum(w_i*qO_i)
D_water = (W0 - Wreserve - W_move) / sum(w_i*qW_i)
D = min(D_O2, D_water, 기타 적용 한계, 모든 중간지점 즉시복귀 제약 상한)

최종 O_remaining = M0 - O_move - sum(qO_i*d_i) >= F
매 시점 O_consumed_so_far + O_immediate_return <= M0-F
```

- 음수 가용 예산은 `예산 부족`, 정확히 0초 체류 가능한 경우는 `체류 0분`으로 구분한다. 0소모율은 그 제약만 무한대로 처리하고 NaN/음수 소모율·불명확한 필수 입력은 계산을 거절한다.
- 위 식은 일정한 작업률/배분비의 선형 상한이다. 시간에 따라 냉각·환경열·소모율이 달라지면 같은 경로 시뮬레이터에서 D를 이분 탐색하고, 매 후보마다 작업과 귀환을 재적분한다. 기준 경로를 바꾸면 체류도 다시 계산한다.
- 최종 Base 잔량만 검사하지 않는다. 긴 우회/비대칭 경사 때문에 중간 지점에서 즉시 돌아올 수 없는 계획은 거절한다. A 작업 후·A→B 이동·B 작업 후의 모든 간선 표본에서도 현재 잔량과 비상 귀환 트리를 대조한다.
- 물/배터리 등 추가 자원은 `initial, reserve, move_cost, work_rate, validity, source` 계약으로 확장한다. 확보된 명목 배터리 용량만으로 소비 전력까지 검증됐다고 하지 않는다. 적용한 제약만 시간 상한에 반영한다. 산소가 아닌 물이 먼저 제한하면 산소 잔량은 20%보다 높아질 수 있다.
- 물 3.6kg는 기존 모델 가정으로 유지한다. NASA의 11.5lb는 별도 참고값이며 단위/사용 가능량/열 모델 대조 없이 자동 교체하지 않는다. MEDA 기온·THEMIS 밝기를 우주복 냉각수 소모율로 직접 치환하지 않는다.

### 10.4 Walkback 채움·방향·확대·축척

| 모델상 Base 복귀 잔존 산소 비율 r | 채움 색 |
|---|---|
| r ≤ 0.10 | red |
| 0.10 < r ≤ 0.20 | yellow |
| r > 0.20 | blue |

- 기존 채움/투명도 방식을 유지하되 분류 입력을 새 잔량 정책으로 바꾼다. 정확히 20%는 체류 제약상 허용하면서 사용자 지정 범례상 yellow다. 표시를 반올림하기 전 원값으로 분류한다. 수치 허용오차는 g 단위 검산에만 쓰고 색 임계값을 임의 이동하지 않는다.
- 초기 지역 레이어는 **Base→각 후보 셀→Base, 체류0** 조건의 예상 잔량으로 만든다(`왕복·체류0` 범례). 실제 경로망/경사로 산출하며 원형 거리 버퍼를 안전 영역으로 사용하지 않는다.
- 탐사 중에는 현재까지 소비한 양을 반영한 **현재 위치→후보 셀→Base, 추가 체류0**로 갱신한다. 선택 A/B 전체 일정의 체류 포함 잔량은 별도로 계산해 경로/카드에 연결한다. 배경 영역이 모든 A+B 일정의 체류를 보증한다는 인상을 주지 않는다.
- 경로 없음·NoData는 색 분류 대상에서 제외하고 회색/해칭으로 표시한다. 미관측 셀은 조건부 색 위에 해칭을 더한다. 물 등 다른 제약이 실패한 셀에도 불가 표시를 겹치며 blue를 무조건 안전으로 읽게 하지 않는다.
- N 버튼은 현재 지도 회전각을 0°(북쪽 위)로 재설정하고 탐사자/거점을 화면 중앙에 둔다. 진행방향 모드 전환은 하지 않는다. 지도 회전은 별도 ↶/↷ 버튼, Shift+드래그, 두 손가락 회전으로 제공한다. 탐사자 화살표는 실제 경로 heading을 나타내고 북쪽 화살표는 지도 회전각을 반영한다.
- 지도 회전/확대 시 마커·경로·채움에 같은 변환을 적용하고 클릭 좌표는 역변환한다. HUD의 heading은 지리 좌표 기준이며 화면 회전각과 혼동하지 않는다. 팝업 anchor와 선택 hit-test도 같은 변환을 사용한다.
- +/−, 휠/핀치, 확대 범위 제한을 지원한다. 축척은 1·2·5 계열 m/km로 표시하고 pan/zoom/resize마다 갱신한다. 지역 지도는 검증된 투영·셀 크기를 쓰고 전역 등장방형 지도는 현재 위치의 화성 구면 거리를 사용한다. 경도별 축척/극점 특이점에서는 그릴 수 없는 척도를 숨기고 확대를 제한한다.

### 10.5 Visor와 지도 시뮬레이션 동기화

기존 `openHudPopup()`, `buildSim()`, `SIM.frames`, `renderHud()`, `renderRv()`를 연결한다. 지도 아이콘을 사용자 클릭으로 눌러 별도 visor 창을 연다. 같은 페이지의 단일 시뮬레이션 시계가 지도와 visor를 모두 구동하며 창마다 독립 타이머/위치 적분을 만들지 않는다.

```text
SimulationSnapshot = {
  simulation_id, revision, site_id, plan_id, sequence,
  elapsed_s, phase:out|work|back|home|paused,
  position:{cell,x_m,y_m,z_m}, heading_deg, segment_index,
  active_poi_id, outbound_remaining_s, return_s, dwell_remaining_s,
  view_source:observed|simulated|unavailable
}
```

- `play/pause/seek/reset/return/replan`은 중앙 상태에 한 번 적용한다. 두 창의 위치·방향·단계·시간은 동일 snapshot을 사용한다. 프레임 사이 위치를 보간하되 경로 밖으로 이동시키지 않는다. 귀환 버튼은 현재 위치→Base로 재계산하며 완료하면 Base에서 정지한다.
- 같은 출처의 열린 창 참조로 snapshot을 전달한다. 메인 창이 상태 소유자이며 visor는 읽기/명령 전달 역할이다. message API를 쓴다면 source window와 simulation_id/revision을 검증한다. 로컬 file://의 null origin을 무조건 신뢰하지 않는다.
- 창 닫기/다시 열기, 팝업 차단(지도 안 visor 패널 대체), 탭 숨김/재활성화, 지역 전환/계획 변경을 처리한다. 메인 창 종료 시 visor는 연결 종료를 표시하고 마지막 장면을 진행 중인 것처럼 재생하지 않는다. 늦게 도착한 옛 revision은 폐기한다.
- 지도와 visor의 동기화 허용 오차는 위치 1개 시뮬레이션 샘플 이하, 시간은 같은 snapshot에서 정확히 일치하도록 검사한다. 배경 탭에서는 wall-clock 폭주를 막고 재개 시 중앙 상태로 재동기화한다.
- 사용자 후속 수정에 따라 visor의 기본 화면은 **실제 로버 관측 사진**이다. 저해상도 DTM 가상 지형 렌더를 제거한다. 현재 위치에 가까운 원본 사진을 사용하고 촬영 sol·탐사자와의 거리·방향 확인 상태를 영어로 표시한다. 사진이 없으면 No photo를 표시한다. 이산 관측을 정확한 연속 로드뷰처럼 표시하지 않으며, 원본 카메라/위치 정합과 방향별 고해상도 파노라마는 후속 데이터 단계에서 처리한다.

### 10.6 추가 데이터 계약·테스트

POI catalog는 `id, name, site_id, observation_position, approach_cell, position_source, frame_id, sol, utc, camera_pose, product_ids, panorama_asset, coverage_status, registration_status, min_dwell_s`를 가진다. 미확인은 null이며 등록 실패 지점을 경로 셀에 자동 투입하지 않는다. 관측 위치는 PLACES·카메라 label·필요한 SPICE를 교차 확인한다.

`MissionResult`는 기존 자원 상세를 내부에 유지하고 `plan_id, revision, selected_ids, visit_order, paths[], outbound_s, return_s, dwell_total_s, dwell_by_poi[], end_o2_fraction, limiting_constraint, coverage_status, status`를 추가한다. 모델/프로필/예산/선택 집합/배분비/overlay 변경은 시뮬레이션과 모든 경로·시간·색 캐시를 무효화한다. §4 mission v2가 v1의 target_cell/dwell_s/return_margin을 대체한다.

구현 시 필요한 검증(이번 문서 작업에서 실행한 제품 테스트가 아님):

- [ ] 수지 fixture: M0=100g, 왕복 이동30g, 작업1g/min이면 최대 체류50분·복귀20g. A/B 절반 배분이면 각25분. 이는 공식 데이터가 아닌 단위 테스트 입력이다.
- [ ] 출발비용 증가/누설 증가/냉각수 감소 시 체류가 증가하지 않음; 왕복만으로80% 초과 시 infeasible; 물이 먼저 제한하면 O2가20% 이상 유지됨.
- [ ] r=0.10/red, 0.100001/yellow, 0.20/yellow, 0.200001/blue; 도달 불가/NaN은 blue 금지. 현재 위치가 바뀌면 walkback 출발점도 바뀜.
- [ ] A만/B만/A+B 두 순서, 선택 해제/재선택, 양방향 경사 차이, 선택 누락 금지, 목표별 체류 합계, 분 단위 내림 후 원수지 검산.
- [ ] 출발/일시정지/되감기/복귀/귀환완료/재계산/지역전환의 지도–visor 상태 일치. popup 차단·닫기·다시 열기와 오래된 snapshot 거절.
- [ ] 회전90°/180° 후 동일 POI 선택·북쪽 재설정·축척 배율·화면 resize·키보드 접근성. 1366×768 및390×844에서 주요 버튼/3종 시간이 가려지지 않음.
- [ ] 기본 UI에 자원 숫자 표가 상시 노출되지 않음. 실제/가상 영상 라벨, 자료 부족 상태, 오프라인 이미지/visor 동작을 실제 브라우저로 확인.

추가 테스트 파일은 `tests/test_ui_time_policy.mjs`, `tests/test_visor_sync.mjs`. 기존 T8 명령에 두 파일을 추가하고 사용자 흐름의 실제 브라우저 검사를 수행한다. 계산 실패 시 임의 예시 시간을 대신 표시하지 않는다.

### 10.7 이번 추가 다운로드와 기존 자료 재사용

추가 외부 원문은 **PDF 5개, 35,771,464 bytes(약35.77MB)**다. 위치는 `martian-map-slam/data/downloaded/ui_support/apollo/`. 목록은 `research/download-ui-support-manifest.json`, 실제 크기/URL/SHA256/상태는 `research/download-ui-support-results.json`에 보존한다. Bellcomm의 이전 NASA/NTRS URL은 404여서 Apollo Lunar Surface Journal의 이전 보관 주소를 사용했다. 실패 응답을 다운로드 성공으로 세지 않는다.

| 필요한 기능 | 이미 받은 자료/추가 원문 | 적용 전 남은 작업 |
|---|---|---|
| 전체 화면 지도·축척·방위 | MOLA 32타일, WMTS capabilities, HiRISE DTM/정사영상, CTX | 투영/축/범위 확인, 2,048px 배경·지역 패키징 |
| 여러 POI와 관측 로드뷰 | Navcam/Hazcam/Mastcam-Z, PLACES, SPICE, Camera SIS | 제품 ID–촬영 위치 매칭, 정지점별 합성·coverage |
| 연동 가상 visor | 기존 DEM/renderer, Navcam stereo, 18개 OBJ와 texture/label | 카메라 frame/축 검증, 작은 미리보기, 이동 snapshot 연결 |
| A/B 과학 지점 | PIXL/SHERLOC/SuperCam, 시료 보고서, USGS 지질 GIS | 실측 표적/근접 접근점 구분, 간결한 지점 설명 |
| 시간·산소 예산 | 이번 Apollo 원문5개 + 기존 IST 계수/검증 자료 | 프로필 가정 표시, 동일 경로 수지·JS/Python 대조 |
| 환경 맥락·확장 자원 | MEDA, 정량 열관성 cube, THEMIS NightIR | 범위/품질 검증. 냉각·지반 위험 모델로의 직접 치환 금지 |

확보한 지형·영상·위치 데이터가 UI 구현에 충분한 후보 입력이므로 같은 원본을 다시 받지 않았다. 필요한 좌표 정합/파노라마/시간 계산 결과는 다운로드 가능한 완제품이 아니라 구현 단계의 파생 산출물이다. 모든 확보 자료를 HTML에 넣지 않고 사용한 제품만 provenance로 연결한다. 외부 다운로드 누계는 **4,717개**이며 자체 작성 JSON/설명 파일은 다운로드 수에 포함하지 않는다.

### 10.8 일정·역할·완료 기준 수정

새 필수 UI/계산/검증은 종전 대비 약14~20인시 추가로 추정한다. 온라인 타일 확장과 신규 직접 복원 확장 약6인시를 뒤로 미뤄 총 **66~72인시**로 재추정한다. 3인30시간의 기존 유효54~60인시 상한을 넘으므로 30시간 내 완주를 확정하지 않는다. H2에 담당별 실측 속도를 보고 4번째 인력의 UI 검수/자료 패키징 분담 또는 경과시간 연장을 결정한다. 사용자 요구 0~8은 축소 대상이 아니다.

- A: T4/T5 유지, T6를 체류 최대화·A/B·20% 잔량·색 정책으로 확대(약24~26h).
- B: 확보한 PDS 자료 검증·두 POI/pose·원문 프로필 근거·패키징에 집중(약16~18h). 새 직접 복원 확장은 후순위.
- C: 지도 전체 화면·팝업·3종 시간·회전/축척·visor 동기화·오프라인 QA(약26~28h). §7 표는 기존 순서 참고이며 이 인시와 필수 완료 계약으로 대체한다.
- H4: POI/mission v2/Snapshot 계약 고정. H8: fixture로 지도 팝업·선택·visor 공통 시계. H12: 모델/잔량/경사 테스트. H18: 실제 POI와 A/B·3종 시간 연결. H24 동결은 필수 검증 통과 시에만 가능하다.
- 제품 파일은 기존 6개 모듈 한도 안에서 UI 로직을 `demo_template.html`, 순수 시간/잔량 함수를 `jezero_policy.js`, 프로필 선택을 `jezero_model.js`에 배치한다. 테스트/데이터 계약 파일은 별도다.
- 3분 시연은 전역→Jezero, 지점 팝업→A/B 선택과 시간 비교, 출발→지도/visor 동기화, 북쪽/축척/잔량 영역, 관측 공백·귀환으로 수정한다. 연구용 긴 자원 표를 기본 시연 화면에 올리지 않는다.
- 필수 완료: A만/B만/A+B, 3종 시간·A/B 분할, 20% 복귀 수지, red/yellow/blue, 실제 관측 팝업, 연속 가상 visor, 두 창 동기화, 나침반·zoom·축척, compact UI가 모두 작동하고 §10.6 검증을 통과해야 한다. 미완료 항목을 문서상의 계획으로 완료 처리하지 않는다.


## 11. UI 구현 착수 기록

사용자의 “UI 수정부터 진행하자” 지시로 제품 UI 수정이 승인되어 구현에 착수했다. §8의 구현 전 승인 상태는 이 지시로 대체된다.

- [x] 지도 전체 화면과 접는 고급 설정, 기존 기능 연결
- [x] POI 목록/관측 팝업, A/B 선택, 3종 계획 시간과 균등 체류 배분
- [x] 확대/이동/북쪽·진행방향/화면 축척, 20% EVA 잔량 정책과 영역 분류
- [x] 기존 시뮬레이션 시계와 DTM 기반 가상 visor 연결
- [x] 단독 HTML 빌드,20개 정책/좌표/플래너 테스트,기존 데이터 payload 보존 확인
- [ ] 실제 브라우저 시각/상호작용/반응형/전체 재생 검수: 앱 접근 승인 시간 초과로 미완료
- [ ] 전역 지도, 신규 다운로드 자료 정합/POI 확대, A/B 사용자 배분비, 수동 즉시귀환 및 실시간 체류 재최적화

자세한 변경과 검증 한계: [UI 구현 기록](martian-map-slam/reports/ui-map-first-validation.md). 전체 계획 완료나 실제 장비 안전 검증 완료를 뜻하지 않는다.


## 12. 사용자 UI 피드백 반영 — 2026-11-14

이 절은 이전 언어 전환·N 모드 전환·가상 visor 기본 정책을 대체한다.

- [x] 실제 관측 visor: Jezero Navcam 원본 PNG10장(1280×960)을 확보해 HTML에 포함. 기존400×300 미리보기 대신 사용하며 NASA 출처·sol·촬영 위치 거리 표시. 다른 지역은 보유 관측 사진을 사용한다.
- [x] 자유 지도 회전: ↶/↷15° 버튼, PC Shift+드래그, 터치 두 손가락 회전/확대/이동. 회전 후 마커 선택은 같은 역변환 사용.
- [x] 현재 위치는 파란 방향 화살표와 YOU, 거점은 기지 아이콘과 BASE, 목표는 깃발 핀과 SITE/A/B로 구분. 지도 회전과 무관하게 라벨은 화면에서 읽을 수 있게 유지.
- [x] 제품은 English-only. 새 지도 컨트롤·팝업·로드뷰·단위·설명·접근성 명칭을 영어로 통일하고 언어 전환 버튼 제거. 기존 분석 UI의 영어 사전도 확장.
- [x] N은 North up + Center on me. 반복해서 눌러도 진행방향 모드로 바뀌지 않는다. 사용자가 회전한 각도만 북쪽으로 복원하고 확대 수준은 유지한다.
- [x] JavaScript 문법·순수 정책/좌표/회전/북쪽 초기화/사진 선택 테스트28개 통과. 지형 압축 payload는 유지.
- [ ] 브라우저 화면·모바일 실제 제스처·기존 고급 모드 영문 누락 점검: 브라우저 연결 호스트가 없어 미완료.
- [ ] 다음 데이터 단계: 사진/카메라 pose와 PLACES/SPICE 정합, 방향별 고해상도 파노라마, 탐사 경로상 관측 공백 명시. 정합 전에는 실사진을 탐사자 시점의 정확한 연속 영상이라 표현하지 않음.

추가 확보: 원본 PNG10개 +800px JPEG10개, 총17,628,579bytes. 다운로드 누계4,737개. JPEG는 원본 PNG 확보 전 해상도 확인 자료로 보존한다. 실제 visor에는 원본 PNG를 우선 사용한다.

패키징: 원본 사진을 오프라인 HTML에 포함하면서 파일 크기가 약36.4MB가 됐다. 기존25MB는 내부 목표였으며 이번 실제 이미지 품질 요구를 우선한다. 최종 최적화 단계에서 원본을 보존한 채 배포용 이미지 압축/지연 표시를 검토한다.


## 13. 후속 구현 — 체류 배분·귀환·전역 지도 (2026-11-14)

- [x] A/B 체류 비율 25:75, 50:50, 75:25 선택. 각 지점의 배분을 경로 전체의 산소·냉각수·선량 제약에 반영하고 분 단위로 내림. 방문 순서를 뒤집어도 A/B 비율은 지점에 귀속.
- [x] Return now: 현재 시뮬레이션 분에서 귀환으로 전환. 이미 사용한 자원과 경과 시간을 유지하며 귀환 경로를 지도에 표시. Restart는 원래 일정으로 복원.
- [x] 지도/visor 공통 프레임의 Travel left, Return now, Stay left 갱신. 이동·작업 누적 시간을 실제 시뮬레이션 적분에서 기록. 귀환 이후 체류 시간은 0.
- [x] Mars 전역 화면: 다운로드한 MOLA WMTS level 2 타일 32개(8×4)를 2048×1024 오프라인 배경으로 연결. Gale/Jezero 착륙지 표식 및 Gale/Jezero/Aram 지역 선택. Aram은 정확한 전역 표식 좌표 정합 전까지 지역 버튼으로 접근.
- [x] 정책·계획·시뮬레이션·전역 자산 테스트 34개 및 배포 HTML 스크립트 문법 검사.
- [ ] 실제 브라우저/모바일 화면·제스처 검증: 현재 브라우저 제어 호스트 연결 불가. 데모 실행 요청과 자동화 테스트는 화면 검증을 대체하지 않음.
- [ ] 실시간 다중 지점 재최적화: 현재 Stay left는 남은 예정 작업량을 즉시귀환 산소/냉각수 예산으로 제한한 값. 향후 지점까지의 경로를 재탐색해 최대 체류를 새로 푸는 기능은 아직 아님. 자동 귀환 경보는 기존 시뮬레이터에서 유지.
- [ ] PLACES/SPICE와 사진 pose 정합 → 고해상도 방향별 관측 및 관측 공백 표시 → 과학 POI 확장. 기존 사진의 근사 좌표를 정밀 등록으로 취급하지 않음.
- [ ] 지역 전환 비동기 경합·오프라인 실제 기기 성능·최종 시연 검증.

이번 차수는 추가 외부 다운로드 없이 확보된 MOLA 32개를 새로 사용했다. 전체 외부 다운로드 수는 4,737개로 동일. 단독 HTML은 약 40.0MB이며 전역 지도와 원본 관측 사진을 포함한다. §11의 묶음 미완료 항목은 위 체크리스트로 세분화하며, 미완료 과학 정합/현장 검증까지 완료로 표시하지 않는다.


## 14. 잔여 단계 재감사 및 구현 결과 — 2026-11-14

§6과 §11~13의 미완료 항목을 재검토했다. 이전 체크리스트는 차수별 이력이며 최신 완료/미완료 판정은 아래와 [검증 기록](martian-map-slam/reports/jezero-validation.md)을 따른다. 모든 Gate가 통과했다고 표시하지 않는다.

| 단계 | 이번 결과 | 남은 조건 |
|---|---|---|
| TW 전역 | 오프라인 MOLA32타일, 이동/확대/좌표 선택, 상태 catalog, 지역 진입, 최초/#mars 진입 구현 | 실제 브라우저 검수. 온라인 고해상도 타일은 계획의 오프라인 분기로 축소 |
| T1 환경 | 기준 HTML 보존·해시, 로컬 Windows/32GiB RAM·CPU 실행 확인 | Git CLI 미가용. 프로젝트 전용 Python3.12.10/NumPy2.2.6 환경 준비 완료. 원격 GPU는 사용하지 않고 공식 PDS 파생제품 CPU 분기 선택 |
| T2 입력·POI | PDS366제품/원영상 파생348제품·촬영 식별자36개·메시18개 catalog, SHA256·sol·frame·site-drive 보존. PLACES 정지점2개 추가 | 추가 정지점2개는 기본 거점에서 연결되지 않아 observation-only. 기존 과학 목표3개는 도달 가능 |
| T3 국소 합성 | SITE_FRAME25의 공식 메시2개 결합. 원정점239,349개, 미리보기7,979개, 겹치는1m XYbin11개. manifest/status=local_only | 독립 통제점/검증점 없으므로 orbital registered 승격 금지. 정밀 파노라마·직접 stereo 복원 미실행. G2는 local-only 축소 결과 |
| T4 모델 | 기존 IST 계수 원본 대조, 75/90kg·평지444.3962697W 확인, Jezero 옵션 중복 보정 차단 | 원본 Python84조건/504수치 대조 통과, 최대 상대오차3.61×10⁻¹⁶ |
| T5 그래프/캐시 | NoData/high·20도 간선·모서리 검사, 출발점 강제허용/하산우회 차단, 에너지 동률 시간 비교, 지역/base/revision 캐시 및 늦은 decode 무시 | 실제 브라우저 빠른 전환 QA |
| T6 임무 | 실제466,900셀 그래프에서 왕복 적분·20% 잔량·같은 목표의 차단 후 우회 확인. 현재 O2/물/k/누적선량으로 남은 방문 일정의 체류 상한 재계산 | 후보 경로·기존 방문 순서 안의 추정이며 전체 다중자원 최적 보장 없음. 재생 중 기존 일정을 자동 교체하지 않음. 알려진10g/h 누설 예산·시뮬레이션·부분 분 수지 및 Python 교차검증 추가 완료 |
| T7 UI | Observations 출처/국소 미리보기, 미관측 표시, Block test/Clear block, #jezero-evidence-demo, 전역 복귀 상태 유지 | 실제 터치/visor 창/반응형 및 고급 화면 영어 누락 QA |
| T8 묶음 | 단독 HTML, source CSV, 검증 JSON/Markdown, 3분 시연 대본, 로컬 review package·SHA256 | 브라우저 host unavailable로 녹화/실기 검수/성능 목표 판정 미완료. 공개 재배포 권리 검토 전 게시하지 않음 |

- [x] UI/정책/시뮬레이션39개 + 관측/좌표/실제worker/지연decode26개 = 65개 자동 검사 통과.
- [x] 실제 Jezero 격자에서 추가 통합 검증 실행. 세부 수치와 시간은 reports/packaged-grid-validation.json에 기록. Node VM 실행 시간은 브라우저 성능으로 간주하지 않음.
- [x] 관측 촬영점과 접근점을 분리: 정지점25/94 약9.25m,25/214 약2.49m. 두 접근점의 국소 지형 유효성과 거점 연결성은 별개이며 현재 기본 거점에서 불연결임을 UI에 반영.
- [x] 추가 외부 다운로드 없이 기존 자료 활용. 외부 파일 누계4,737개 유지. 새 catalog/합성/검증 파일은 다운로드 수에 넣지 않음.
- [ ] 브라우저 연결 복구 후 실제 데스크톱/모바일·오프라인·성능·영문 UI QA와 새 시연 영상.
- [x] 프로젝트 전용 Python 실행 환경에서 원본 모델84조건/504수치 대조, 단위 및 알려진 누설 확장 시험.
- [ ] 독립 제어점 최소3개+검증점 최소2개에 의한 orbital registration. 이 증거 없이 observed/blocked mask를 생성하지 않음.
- [ ] 공개 제출 전 코드/자료 재배포 권리 확인. 현재 dist 묶음은 로컬 검토용이며 공개하지 않음.

산출물: [로컬 검토 묶음](martian-map-slam/dist/jezero-demo/README.md), [검증 기록](martian-map-slam/reports/jezero-validation.md), [시연 대본](martian-map-slam/reports/jezero-demo-script.md). 완료되지 않은 항목은 환경/검증 증거가 없는 상태를 숨기기 위해 체크하지 않는다.

최종 화면 검수 시도: 브라우저 host 미가용에 이어 Windows Computer Use도 현재 Chrome URL을 확실히 판별하지 못해 정책 집행상 중단됐다. 추가 앱 입력 없이 화면 검수 미완료 상태를 유지한다. Python 도구 설치 파일은 NASA 관측자료4,737개 집계와 별도다.

## 15. Claude Code 시작점과 현재 기준

### 15.1 범위와 우선순위

현재 구현을 보존하며 **재현 가능한 빌드 → 실제 화면 검수 → 좌표 정합 실험 → 관측 기반 지도 보완 → 최종 패키지** 순으로 진행한다. 정합 증거가 부족하면 local-only 관측 미리보기와 기존 궤도 격자 경로 기능을 유지한다. 관측 사진의 존재를 인간 통행 가능성으로 해석하지 않는다.

과거 30시간·3~4명·원격 RTX5060Ti 계획은 당시의 자원/일정 가정이다. 이번 실행은 로컬 Windows/32GiB RAM/CPU에서 수행했다. 원격 GPU 연결·설치·성능은 미검증이다. 다음 환경에서 사양과 소요시간을 새로 기록한다. 현재 사본에서 Git 저장소/CLI를 확인하지 못했으므로 과거 upstream 커밋을 현재 HEAD라고 쓰지 않는다. 코드 출처 기준은 `5940cfd051e3267c23e7ee30775b8abf26f63420`이며 로컬 변경 식별은 보존본과 파일 해시를 사용한다.

| 항목 | 2026-11-14 기준 | 제한 |
|---|---|---|
| 프로젝트 | `C:/nasa/martian-map-slam` | 이 PLAN은 `C:/nasa/PLAN.md` |
| 실행 HTML | `reports/18-eva-walkback-demo.html` | 정적 자산 내장 |
| 배포본 | `reports/18-eva-walkback-demo.standalone.html`, `dist/jezero-demo/index.html` | 다음 빌드 후 해시 재확인 |
| HTML 크기 | 40,489,064bytes | 25MB는 과거 내부 목표, 공식 제한 아님 |
| HTML SHA256 | `659717e570f7f949e93919180739b68f6b9ce69c9f230cf0b121d807ded5ac19` | 이후 변경 시 갱신 |
| 검토 묶음 | `dist/jezero-demo/`,17파일 | 전체 소스/PLAN/raw 아카이브 미포함 |
| 자동 검사 | UI/계획/시뮬레이션39 + 관측/worker 등26 =65 | 실제 DOM/화면 전체 검사 아님 |
| Python 수치 대조 | 84조건×6=504비교, 최대 상대오차 `3.6128103312332233e-16` | 원본 모델과의 수치 일치, 물리적 인증 아님 |
| 실제 격자 검사 | Jezero667×700=466,900셀 | Node VM worker 실행 |
| 외부 다운로드 | 4,737파일 | 생성물/도구 설치 파일 제외 |
| 출처 CSV | 431행: catalog366+사진33+MOLA32 | 다운로드 수/실사용 촬영 수와 다름 |
| 국소 관측 | 공식 메시2개의 공통 좌표계 정점 결합 | orbital 정합/면 융합/정밀 파노라마 미수행 |
| 미완료 | 실기 QA, 독립 정합, 재배포 검토, 새 영상 | 성공으로 간주하지 않음 |

증거 파일은 `reports/automated-validation.json`, `reports/python-js-model-validation.json`, `reports/packaged-grid-validation.json`, `reports/jezero-validation.md`다. 원본 보존본 `../research/ui-baseline/demo_template.html`, `../research/ui-baseline/18-eva-walkback-demo.html`은 덮어쓰지 않는다.

### 15.2 계속 유지할 사용자 계약

| 요구 | 구현 계약 |
|---|---|
| 지도 중심 | 전체 화면 지도, 작은 컨트롤/접는 설정. 긴 자원 표는 기본 화면에 올리지 않음 |
| 목표 | A만/B만/A+B, 최대2개. 선택 목표를 조용히 버리지 않고 불연결 표시 |
| 시간 | 이동/복귀/체류 3종. A/B 개별 체류와 합계, 25:75·50:50·75:25 배분 |
| 산소 | 초기816.466266g, 복귀 시 초기량의20% 이상. Apollo1430psia/1.8lb 참고 가정이며 압력만으로 질량 환산 불가 |
| 물/선량 | 산소와 별도 제약. 누설은 산소만 소비하며 대사열로 이중 계산하지 않음 |
| 회전/N | 자유 회전. N=North up + Center on me, 확대 수준 유지. 모드 토글 금지 |
| 마커 | YOU/BASE/SITE/A/B 식별, 회전 중 라벨 가독성 및 클릭 좌표 일치 |
| 영역 | 복귀 산소≤10% red,≤20% yellow,그 외 blue. 정확히20%는 yellow. 물/경로 불능·미관측 별도 |
| visor | 실제 원본 사진, 지도와 공통 시계. 정합 전 정확한 현재 시점 영상으로 표현하지 않음 |
| 언어 | 제품 전체 짧고 쉬운 영어. 개발 문서는 한국어 가능 |
| 전역 | 최초 URL/`#mars`는 전역, `#jezero`는 상세. 임의 지점 EVA 분석 가능성 주장 금지 |
| 회귀 | Gale/Aram 유지. Jezero strict EVA를 다른 모드 전체에 무심코 적용하지 않음 |

과거 문구 정정: §13의 단순 Stay left 제한은 남은 방문 일정 재계산으로 대체됐다. 새 예측을 재생 일정으로 자동 적용하지는 않는다. §6/§10의 예정 `jezero_policy.js`, `jezero_model.js` 등은 실제 파일명이 아니다. 현재 일정 비교는 **안전 제약 → 최대 체류 → 산소 비용 → 시간**, 구간 그래프는 **대사 산소 비용 → 동률이면 시간**이다. 서두의 에너지 우선 설명으로 체류 최대화 정책을 되돌리지 않는다.

## 16. 환경 실행 검증 재현 절차

### 16.1 환경과 백업

아래 명령은 프로젝트 루트 PowerShell용이다. 이전 작업은 제공된 Node 실행 도구를 사용했으며 **Node CLI는 PATH에서 확인되지 않았다**. 다음 환경에서 ESM 지원 Node CLI를 준비하고 버전을 기록한다. UI 빌드/검사는 Node 내장 모듈 기반이며 프런트엔드 npm 설치가 필수인 구조가 아니다. Python은 프로젝트 전용3.12.10+NumPy2.2.6만 준비됐다. GIS/Pillow/SciPy 전체 환경이 설치된 것은 아니다.

```powershell
Set-Location C:\nasa\martian-map-slam
Get-Command node -ErrorAction SilentlyContinue
node --version
& C:\nasa\.tools\python-3.12.10\python.exe -c "import sys,numpy; print(sys.version); print(numpy.__version__)"
Get-FileHash reports\18-eva-walkback-demo.html -Algorithm SHA256
```

변경 전 작업공간의 새 날짜별 폴더에 `code/`, `tests/`, 두 reports HTML, `outputs/local_terrain/jezero/`, 검증 보고서, `code/global_map.json`, PLAN을 백업한다. 약25GB 원자료를 매번 복사할 필요는 없지만 manifest/체크섬은 보존한다. Linux/WSL에서는 절대 경로와 research 스크립트의 `C:/nasa`를 수정한다. Git을 새로 사용한다면 raw/HTML/base64 대용량 추적 정책을 먼저 정한다.

### 16.2 빌드 의존성과 부작용

`buildUI()`는 **기존 reports HTML을 입력으로 다시 읽는 UI 교체 빌더**다. meta/blob/sites/shade/ortho를 보존하고 template/UI를 교체한다. raw DTM부터의 clean build가 아니다. 기존 HTML 삭제 후 실행 불가. `terrainPayloadsPreserved:true`도 설계상 보존 표시이며 독립적인 모든 payload 해시 검사 결과는 아니다. `code/build_demo_html.py` 전체 재생성은 새 Python 환경에서 검증하지 않았으므로 기본 명령으로 사용하지 않는다.

```text
기존 reports HTML의 지형 + code template/UI/CSS/i18n/global_map
 + local_terrain의 manifest/stations/mission
 + reports/packaged-grid-validation.json
 -> buildUI -> reports HTML
 -> 실제 격자 검사 -> 연결성 보고서 및 mission.json 변경
 -> buildUI 재실행 -> 최신 연결성/임무 반영
 -> 정책/worker/모델 검사 -> automated-validation.json
 -> packageReview -> dist/jezero-demo
```

- `runPackagedGrid()`는 **mission.json을 고정 fixture로 덮어쓴다**. 실험 임무는 백업하고 검사 전후 diff를 확인한다.
- `buildEvidence()`는 manifest를 `local_only`,빈 observed/blocked,미정합 상태로 다시 만든다. 미래 등록 결과 위에 실행하지 않는다.
- `buildStationCandidates()`는 stations.json을 덮어쓴다. 주변 유효 셀 선택과 base 연결성은 별개다.
- 빌더는 연결성 보고서를 display name으로 연결하며 **격자/모델 버전 일치를 검사하지 않는다**. 데이터 변경 후 과거 보고서를 최종 증거로 사용하지 않는다. H0에서 우선 개선한다.
- `packageReview()`는 기존 성공 보고서의 최신성을 검증하지 않는다. 새 제품에 오래된 성공 JSON을 재사용하지 않는다.

### 16.3 UI 변경 후 빠른 빌드/검사

PowerShell here-string을 Node ESM stdin으로 넘겨 Windows `-e` 따옴표 문제를 피한다. 실패하면 패키징하지 않는다.

```powershell
@'
import { buildUI } from './code/build_ui_preview.mjs';
import { runTests } from './tests/test_map_ui.mjs';
import { runRemainingTests } from './tests/test_remaining_plan.mjs';
const root = process.cwd();
const build = await buildUI(root);
const ui = await runTests(root);
const remaining = await runRemainingTests(root);
console.log(JSON.stringify({build, ui, remaining}, null, 2));
'@ | node --input-type=module
if ($LASTEXITCODE -ne 0) { throw 'Build or tests failed' }
```

`node code/build_ui_preview.mjs`와 `node tests/test_map_ui.mjs`에는 CLI 진입부가 있다. remaining/grid/python-reference/package/evidence는 **export 함수를 호출**해야 한다. `node tests/test_remaining_plan.mjs`의 exit0이나 `node --test` 종료를26개 통과로 해석하지 않는다. 새 검사 추가 시39/26 숫자를 고정하지 말고 실행 목록/범위를 보고한다.

### 16.4 그래프/목표/지형 변경 후 실제 격자 검사

실험 mission을 먼저 백업한다. 이전 전체 실행 약67초는 여러 탐색을 포함한 Node VM 검사 시간이며 브라우저 한 번의 재계산 시간과 다르다.

```powershell
@'
import { runPackagedGrid } from './tests/test_packaged_grid.mjs';
import { buildUI } from './code/build_ui_preview.mjs';
console.log(JSON.stringify(await runPackagedGrid(process.cwd()), null, 2));
console.log(JSON.stringify(await buildUI(process.cwd()), null, 2));
'@ | node --input-type=module
if ($LASTEXITCODE -ne 0) { throw 'Grid validation failed' }
```

생성된 mission/연결성을 확인한다. 다른 임무를 복원했다면 해당 임무의 검증을 별도로 남기고 다시 빌드한다. 고정 fixture 성공을 다른 임무의 성공으로 전용하지 않는다.

### 16.5 원본 Python 수치 대조와 통합 보고서

모델/상수 변경 시 빌드 후 상수 fixture를 갱신하고 원본 Python을 실행한다. 84조건은 경사7×eta3×거리2×외부열2다. 75/90kg 가정 변경 시 exporter assertion을 단순 삭제하지 말고 새 근거와 대조 기준을 정한다.

```powershell
@'
import fs from 'node:fs/promises';
const html = await fs.readFile('reports/18-eva-walkback-demo.html', 'utf8');
const match = html.match(/<script[^>]*id="meta"[^>]*>([\s\S]*?)<\/script>/);
if (!match) throw new Error('Packed metadata missing');
await fs.writeFile('tests/fixtures/packaged_model_constants.json', JSON.stringify(JSON.parse(match[1]).const, null, 2));
'@ | node --input-type=module
if ($LASTEXITCODE -ne 0) { throw 'Constants export failed' }
& C:\nasa\.tools\python-3.12.10\python.exe tests\export_model_reference.py
if ($LASTEXITCODE -ne 0) { throw 'Python reference failed' }
```

아래는 PLAN에서 제공하는 실행 레시피이며 기존 통합 runner 파일이 있다는 뜻은 아니다. Python fixture는 직전에 생성했거나 모델/상수가 동일한 기준임을 확인해야 한다.

```powershell
@'
import fs from 'node:fs/promises';
import { buildUI } from './code/build_ui_preview.mjs';
import { runTests } from './tests/test_map_ui.mjs';
import { runRemainingTests } from './tests/test_remaining_plan.mjs';
import { runPythonReference } from './tests/test_python_reference.mjs';
import { packageReview } from './code/package_review.mjs';
const root = process.cwd();
const build = await buildUI(root);
const ui = await runTests(root);
const remaining = await runRemainingTests(root);
const python = await runPythonReference(root);
const report = {generated_at: new Date().toISOString(), build, ui, remaining, python};
await fs.writeFile('reports/automated-validation.json', JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
console.log(JSON.stringify(await packageReview(root), null, 2));
'@ | node --input-type=module
if ($LASTEXITCODE -ne 0) { throw 'Validation or packaging failed' }
```

### 16.6 관측 재생성과 데모

관측 데이터 변경 시에만 `code/build_observation_evidence.mjs`의 `buildEvidence(root)`, `buildStationCandidates(root)`를 import해 순서대로 호출한 뒤 §16.2 순서를 따른다. 일상 UI 수정 때 실행하지 않는다. 각 함수의 출력 덮어쓰기 위험을 먼저 확인한다.

`dist/jezero-demo/index.html`을 Chrome/Edge에서 연다. `#mars`, `#jezero`, `#jezero-evidence-demo`를 각각 검사한다. 고정 시연 hash는 base/목표/자원/배분을 설정하지만 차단 사건을 자동 적용하거나 mission.visit_order를 강제하지 않는다. HTTP 비교는 별도 터미널에서 아래 서버를 실행하고 종료 후 Ctrl+C한다.

```powershell
& C:\nasa\.tools\python-3.12.10\python.exe -m http.server 8765 --bind 127.0.0.1 --directory C:\nasa\martian-map-slam\dist\jezero-demo
# http://127.0.0.1:8765/index.html#jezero-evidence-demo
```

이전 브라우저 host 부재/Windows URL 판별 불가 중단은 앱 화면 실패가 아니라 **검수 미실행**이다. Claude 환경의 허용된 브라우저 도구로 새로 확인한다. 정책 차단을 우회하거나 보안 설정을 낮추지 않는다.

## 17. 구현 구조와 데이터 계약

### 17.1 실제 수정 지점

| 파일/함수 | 책임과 주의점 |
|---|---|
| `code/demo_template.html` | 모델/그래프/worker/상태/시뮬레이션. UI가 같은 closure에 주입됨 |
| `MAKE_MODEL(G,M)` | 메인과 worker 공통 모델. 함수 문자열로 worker를 만들므로 숨은 외부 closure 의존성 금지 |
| `strictEva`, `MF`, `O2RES` | Jezero EVA 정책/중복 보정 차단/초기20% 예비분 |
| `setGeom`, `passMask`, `dijkstra`, `WORKER_MAIN` | 16방향,대각/knight 중간 셀,NoData/high/20도 제약. 출발점 강제허용 금지 |
| `loadSite`, `decode`, `ensureTrees`, `wkStart` | 지역/이미지/worker 수명. siteGeneration/ETGEN/revision으로 늦은 결과 폐기 |
| `modelKey`, `legKey`, `LEGS`, `TREES` | 지역/base/정책/overlay 변경 시 캐시 무효화 |
| `buildSim(forcedReturnMinute)` | 분 프레임, 이동/작업/누설/열 적분. 수동 귀환 prefix 사용량 보존 |
| `setSimIdx`, `tick`, `placeWalker`, `HUDWIN` | 지도/visor 단일 시계, 별도 창 독립 타이머 금지 |
| `code/map_ui.js`, `uiMount` | 지도 UI와 기존 설정 패널 연결 |
| `uiPlanEva(snapshot)` | 전체 선택 평가,A/B 배분,경로 중 귀환 제약,static 순서 비교/live 남은 순서 고정 |
| `uiRequestLive`, `uiLiveKey`, `uiLiveTimes` | 현재 자원/위치/선량의 남은 방문 예측,pending 구별. 실행 일정 자동 교체 아님 |
| `uiReturnNow` | 현재 분에서 귀환 전환. Start 재개/Restart 원래 임무 |
| `uiPaintZones` | 현재 forward+base return 예산과 영역색/물 불능 |
| `uiPhotoAt`, `uiVisor`, `uiOpenPoi` | 실제 사진/출처/팝업. 근방250m 선택은 정합 증거 아님 |
| `uiEvidence`, `uiBlockTest` | local-only 미리보기,synthetic 차단. 실제 관측 장애와 구별 |
| `uiWorld` | 전역 dialog/좌표/지역 선택. 전역 클릭으로 상세 경로 계산하지 않음 |
| `code/map_ui_policy.js` | 순수 체류·색·회전/좌표 역변환·제스처·경위도 함수 |
| `code/map_ui.css`, `code/i18n_en.js` | 반응형/영문. 동적 legacy 문구는 실기 확인 필요 |
| `code/build_ui_preview.mjs` | 기존 payload+새 UI/관측/전역 결합 및 JS 문법 확인 |
| `code/build_observation_evidence.mjs` | 라벨/catalog/정점 미리보기/PLACES 접근점, 직접 stereo 복원기 아님 |
| `code/package_review.mjs` | HTML/보고서/국소 결과/CSV/해시의 로컬 패키징 |

`EVA_DEBUG`에는 state/update/setNow/md/C/TREES/FLAGS/H/HUDWIN/SIM/setSimIdx/OFF/MO/ALT/N/W/R/META 등이 있다. UI/loadSite/uiPlanEva는 직접 노출하지 않는다. 브라우저 검사에 필요하면 명시적 debug API를 추가하고 제품 흐름과 분리한다. HTML 문자열 추출 테스트는 실제 함수 일부를 실행하지만 전체 DOM 실행과 동등하지 않다.

### 17.2 단위와 상태

- 격자는 row-major `row*W+col`, Jezero CELL 약10.096633268711m. 정확한 packed META 값을 사용한다. 정합 오차 기준을 임의10m로 고정하지 않는다.
- 내부 시간 초, 프레임 `m`은 분, `travel_s/work_s`는 누적 초. 산소/물 g,에너지 J,열 W,알려진 누설 g/h.
- 플래너 `o2`는 누설/k 반영 유효 비용으로 순수 대사 산소가 아니다. 물에는 `metabolic_o2`, 실제 산소에는 `oxygen_g` 또는 대응되는 `k*o2` 의미를 확인한다. 누설을 두 번 더하지 않는다.
- `minM`은 현재 최종 예비분 대비 여유량이며 모든 prefix 최솟값은 아니다. 경로 중 귀환 가능성 검사는 별도다.
- static은 순서 후보 비교, live는 남은 순서 유지. 후보 경로 내 최대 체류이며 완전한 다중자원 최적 경로 보장은 없다.
- 시간 배열 Float64를 Float32로 되돌리지 않는다. 에너지 동률/시간 개선 정밀도로 반복 개선 문제가 있었다. 에너지 동률 tolerance는 상대 `1e-9*max(energy)`.
- Jezero EVA 알려진 `state.simLeak`은 예산/시뮬레이션 모두 반영. 마지막 부분 분은 activeSeconds만 적분. 타 모드의 legacy 센서/미지 누설 의미와 혼합하지 않는다.

### 17.3 고정 실제 격자 기준

| 대상 | 셀 | 기본 base 연결성 / forward 대사 산소 |
|---|---:|---|
| BASE | 405918 (x382,y608) | 고정 데모 출발점 |
| Skinner/Wildcat,target-0 | 352306 | 연결,303.3991580317997g |
| Brac,target-1 | 448559 | 연결,28.559649472496393g |
| Amalik,target-2 | 381627 | 연결,105.32746723671325g |
| Navcam25/94 | 355650 | 불연결,observation-only |
| Navcam25/214 | 355647 | 불연결,observation-only |

첫 목표 실제 경로663간선/9633.262538871817초에서 forward 비용과 재적분이 일치했다. mission은 target-1/2,visit_order `[2,1]`,O2 816.466266g,water3600g,k1,q0,leak0,배분50:50. O2 20%하한163.2932532g,사용 가능653.1730128g.

격자 fixture 차단은398559 한 셀이다. 전 outbound6197.963741s/return905.186400s,후3866.890010s/3243.028603s,체류 둘 다11520s(192분),산소587.891741g→587.893016g. 방문 순서가 바뀔 수 있어 outbound/return 각각만 비교하지 않는다. **UI Block test는 경로1/3 부근3×3 patch**라 fixture와 다르다. 동일 사건 시연이 필요하면 ID/범위를 통일하고 재검증한다.

### 17.4 확보 자료와 사용 범위

원장은 `data/downloaded/download-summary.json`, `download-manifest.json`, `validation-issues.json`이다. 프로젝트 밖 research의 download 계열 manifest7개에도 URL/경로가 있다. 개별 경로를 추측해 재다운로드하기 전에 검색한다. `../research/verify-mars-download.ps1`은 약25GB 전체를 읽고 summary/manifest/issues를 다시 쓰므로 일상 UI 검사로 실행하지 않는다.

| 확보 자료 | 현재/후속 역할 |
|---|---|
| Jezero DTM·ortho·CTX | 기존 궤도 격자/배경,정합 기준. 원본 DTM 약380MB |
| Navcam sol443 raw774파일 | IMG348+XML348+JPG78. 348제품≠348촬영,catalog 촬영 식별36개 |
| stereo918파일 | IMG441+XML459+XMLF18,약16GB. depth/XYZ 등 제품별 label 확인 후 사용 |
| mesh72파일 | OBJ/MTL/PNG/XML 각18,SITE_FRAME25. drive94 2개/214 16개. 현재2개 정점 사용 |
| Hazcam250·MastcamZ818파일 | 관측 확대 후보,모두 지형 계산에 반영된 것은 아님 |
| PLACES83·SPICE52파일 | 촬영점/pose/frame 검증,전체 pose pipeline 미구현 |
| MEDA·thermal inertia·지질 | 환경/과학 설명 후보. 시대/공간 해상도/단위 맞추기 전 EVA 열에 직접 대입 금지 |
| PIXL·SHERLOC·SuperCam·샘플 | 과학 지점 설명 후보,인간 통행 근거 아님 |
| MOLA32JPEG·THEMIS9PNG | MOLA32 전역 사용. 보유와 실제 통합 구별 |
| Apollo PDF5개 | 프로필 근거 확인,Mars suit 검증 아님 |
| visor PNG10+JPEG10 | 원본1280×960 우선,800×600 보존. 총17,628,579bytes |

추가 원본 PNG sols는13,127,136,178,414,464,714,717,719,732다. 전체 HTML 사진33개와 추가 원본10개를 중복 집계하지 않는다. 활용 확대는 파일 수보다 출처/좌표/품질/역할로 평가한다. 기존 자료로 통제점/pose를 확보할 수 없을 때만 추가 조사하고 URL/권리/크기/checksum/용도를 기록한다.

### 17.5 국소 관측과 좌표

`outputs/local_terrain/jezero/manifest.json`은 status=local_only,frame=SITE_FRAME:25,units=m,grid_registration=null,observed_cells=[],blocked_cells=[]다. 정합 전 빈 mask가 정상이며 미관측은 안전/장애 어느 쪽도 아니다.

사용한 메시:

- `NLF_0443_0706278524M049RAS_N0250214NCAM00708_0A0085J03.obj`,SHA256 `f4efb106aebd2973e4b679f7ab90b5e804b7ca03a788073851d8a738ab141fb2`.
- `NLF_0443_0706278950M149RAS_N0250214NCAM03443_0A0195J02.obj`,SHA256 `e3cab738b8f189fffda9da97f120c2a685f9c11403793f246b57b8991996e9ca`.

239,349정점에서7,979미리보기 점과 XY SVG를 만들었다. 1m XYbin11개 높이차 중앙값0.023307m는 **독립 orbital RMSE가 아니다**. 면/텍스처 융합·360°파노라마·직접 stereo 복원 미수행. 제품 URL은 catalog/manifest에 보존됐다.

PLACES25/94는 lon77.408100553/lat18.457588545,grid 약(140.2298,532.9466),접근 중심(139.5,533.5),이격9.2471m. 25/214는77.407469563/18.457527169,grid(136.6530,533.3068),접근 중심(136.5,533.5),이격2.4885m. 두 점 모두 default base 불연결이며 점 투영은 영상 정합이 아니다.

DTM label: radius3394.8398133163km,center_lat15°,center_lon77.44°,scale1.0096633268711m/px,line_offset1088495.5,sample_offset3210.5000000001. 현재 crop(0,0),block10 가정:

```text
Rm = radius_km * 1000
sample = sample_offset + Rm*radians(lon-center_lon)*cos(radians(center_lat))/scale
line = line_offset - Rm*radians(lat)/scale
grid_x = sample/10; grid_y = line/10
cell = floor(grid_y)*667 + floor(grid_x)
```

승격 전 실제 label의 중심/모서리·1-based/0-based·crop 정의를 독립 검증한다. 위 식을 그대로 ground truth로 삼지 않는다.

### 17.6 전역 좌표

`code/global_map.json`은 약3.6MB inline SVG/catalog이며 전용 full builder는 아직 없다. 삭제 후 자동 복구된다고 가정하지 않는다. `outputs/global_mars/catalog.json`도 확인한다. MOLA 레이어 `Mars_MGS_MOLA_ClrShade_merge_global_463m`,level2,256px8×4,2048×1024. CRS `urn:ogc:def:crs:EPSG::104905`,좌상단(-180,90),east longitude[-180,180),equirectangular이며 EPSG3857이 아니다. capabilities는 다운로드 레이어 폴더 `WMTSCapabilities.xml`이다. URL 형식은 `https://trek.nasa.gov/tiles/Mars/EQ/Mars_MGS_MOLA_ClrShade_merge_global_463m/1.0.0/default/default028mm/2/{row}/{col}.jpg`.

Jezero pin(77.4508,18.4447),Gale은 기존 격자 변환,Aram은 좌표 검증 전 버튼만 제공. catalog의 packaged는 registered/verified와 다르다.

## 18. 후속 실험과 구현 작업 명세

아래 H0~H7이 **현재 남은 작업 목록**이다. §6의 옛 파일 수 제한/담당 배분을 그대로 적용하지 않는다. 각 단계는 입력 해시·실행 명령·결과·제한을 기록하고 통과한 부분만 체크한다. 제안된 새 파일/필드는 아직 존재하지 않는 설계안이다. 외부 게시/메시지 전송은 로컬 구현 완료와 별도 작업이다.

### H0 — 재현 가능한 빌드와 테스트 부작용 분리 (가장 먼저)

**목적:** 새 지형에 오래된 연결성 결과를 적용하거나 실험 임무가 테스트로 사라지는 일을 막는다.

1. 현재 HTML, source,manifest,mission,stations,검증 JSON의 SHA256을 별도 run manifest로 저장한다. 현재 성공 결과를 보존한 뒤 수정한다.
2. reports HTML이면서 빌드 입력인 지형 payload를 읽기 전용 seed 또는 명시적 데이터 파일로 분리한다. 처음에는 현재 payload를 그대로 추출하고 전후 해시/배열 길이/지역 ID 일치를 검사한다. 원본 DTM 전체 재생성은 별도 과제다.
3. `runPackagedGrid`에 출력 디렉터리/fixture 입력 인자를 도입한다. 기본 검사는 임시 디렉터리에 결과를 쓰고 제품 mission을 바꾸지 않게 한다. 제품 갱신은 명시적 빌드 단계로 분리한다.
4. 연결성 결과에 grid payload hash,model source/config hash,base,strict mode,overlay revision,station stable ID를 저장한다. display name 조인을 stable ID로 바꾸고 불일치 보고서는 거부하거나 `unknown`으로 표시한다. 불일치를 `unreachable`로 단정하지 않는다.
5. buildEvidence는 원본 산출과 등록 결과를 분리하고 승인된 registration을 덮어쓰지 않게 한다. source 제품 선택을 파일 나열의 첫2개가 아닌 명시적 ID 목록으로 고정한다. LID/LIDVID 구별과 버전 선택 규칙을 기록한다.
6. 단일 검증 runner를 실제 파일로 추가한다면 각 export 호출·실패 exit code·실행 수·입력 해시를 기록한다. packageReview가 새 HTML에 대응하는 성공 보고서인지 확인하도록 한다.

**검증:** 같은 입력 두 번 빌드에서 지형/사진 payload 동일, 다른 grid/base/모델의 보고서 혼입 거부, 검사 전후 제품 mission/registration 불변, 기존65개 및 실제 격자 결과 유지. 생성시각이 있는 보고서는 전체 파일 byte equality 대신 의미 있는 필드를 비교한다.

**증거:** 제안 `reports/build-reproducibility.json`,입출력 dependency 목록,검사 runner 사용법. H0 완료 후 §16 명령을 실제 새 구조로 갱신한다. seed 없이 clean build가 가능해진 범위를 정확히 적는다.

### H1 — 실제 UI와 비동기 상태 검수

**선행:** H0 또는 최소 현재 결과 백업. **절차:** §19 전체 행을 실기 실행하고 재현 가능한 실패부터 수정한다. 기기/브라우저/창 크기/file 또는 HTTP/입력 hash/스크린샷을 기록한다.

코드 검토에서 발견한 아래는 **확정 재현 버그가 아닌 우선 조사 지점**이다:

- `wkStart()`는 worker 종료 후 `WK_CB.clear()`를 하지만 대기 Promise를 settle하지 않는다. 지역 전환/연속 재계산 시 pending이 영구 유지되는지 시험한다. 취소 결과를 명시적으로 resolve/reject하고 UI를 최신 세대로 복구한다.
- `uiPaintZones`의 guard는 SITE_I/modelKey 중심이다. A→B→A 동안 이전 A 결과가 새 A를 덮는지 지연 worker fixture로 확인하고 full siteGeneration/request ID까지 검사한다.
- `uiVisor` 이미지 key는 SITE_I:sol:az다. 같은 sol/az의 다른 제품이 충돌하는지 확인하고 product ID/source URL을 포함한다.
- `uiLocalizeMeta`는 표시 이름/설명을 바꾼다. 출처/원본 ID/과학 설명을 번역용 문자열과 분리한다.
- 현재 전역 지역 자료 상태는 button.title hover에 의존한다. 터치에서 읽을 수 있는 짧은 카드에 `Available / Not checked / Local only` 등 상태를 노출한다.

**통과:** 이전 지역 결과가 새 화면에 쓰이지 않음, pending 종료, worker/창 닫기 후 오류 없음, 지도/visor 같은 frame, 모든 조작 키보드/터치 가능한 범위 명시, 영어 누락 수정. 실패 증거 없이 레이스를 고쳤다고 쓰지 않는다.

### H2 — 모델·경로·임무 회귀 확대

**목적:** 이미 통과한84조건 수치 대조와 분리해 제품의 제약/경계 조건을 검증한다. 생리 모델 자체의 외부 검증은 별도다.

1. A만/B만/A+B 및 각 체류 비율, 방문 순서 역전 시 배분이 지점에 귀속되는지 검사한다. 한 목표 불연결이면 전체 선택을 실패로 보고하며 몰래 제거하지 않는다.
2. O2 잔량10%/20% 경계의 바로 아래·같음·바로 위를 검사한다. 영역색의20% yellow와 체류 허용의≥20%를 구별한다. 산소30분 reserve가 중복 적용되지 않는지 확인한다.
3. 임무 시작/이동/현장 작업/부분 분/복귀/home에서 Return now와 Restart를 실행한다. 경과 시간·누적 산소/물/선량 prefix는 유지되고 복귀 후 체류0인지 확인한다.
4. known leak0/10g/h,외부열0/100W,k 변경,물 부족,선량 제한,목표에서 귀환 불능,출발점NoData/high,20도 경계,대각/knight 모서리를 검사한다. 단위와 허용오차를 fixture에 명시한다.
5. 플래너와 simulation의 동일 경로/체류에 대해 독립 적분한다. 실제 자원 사용량,최종 잔량,모든 prefix 즉시귀환 가능성을 비교한다. 표시용 반올림으로 부적합 임무가 적합해지지 않도록 한다.
6. fixture 한 셀 차단과 UI3×3 차단을 별도 이름으로 기록하거나 하나의 사건 schema로 통일한다. 동일 목표/초기 자원/배분 조건에서 전후 경로와 최종 수지를 비교한다.

**통과:** 기존 원본 Python 상대오차≤1e-6 조건 유지, 경로 재적분과 worker 비용 일치, 제약 위반을 feasible로 표시하지 않음. 새로운 질량/속도/열 정책은 근거·회귀범위를 함께 갱신한다. **증거:** 자동 검사 JSON과 최소 한 실제 격자 임무의 before/after 수지표.

### H3 — live 예측 성능과 일정 적용 정책

현재 기능은 현재 자원으로 남은 방문의 최대 체류를 **예측**하며 실행 중 기존 일정은 유지한다. 이것을 사용자에게 오해 없이 보여주는 것이 먼저다. 실행 일정을 자동 교체하는 기능은 별도 설계 후 구현하며 필수 완료로 간주하지 않는다.

- frame/위치가 자주 변할 때 최신 요청만 적용하고 중간 요청은 취소/합친다. LEGS/liveTree 캐시 크기와 종료 후 해제를 측정한다.
- 계획 중·유효 결과·불능을 구별하고 지난 결과를 최신 추정처럼 표시하지 않는다. map/visor는 같은 결과 버전을 읽는다.
- 일정 적용을 추가한다면 snapshot에 position,consumed resources,dose,completed stops,partial dwell,mission revision을 저장한다. 완료 지점을 다시 방문하거나 소모량을 초기화하지 않는 atomic 적용을 테스트한다. base는 현재 위치가 아니라 원래 귀환지다.
- 실기 측정으로 첫 지도/첫 경로/live 재계산 p50/p95/최대와 peak memory를 기록한다. 10초 이내 재계산 등 과거 목표는 잠정 목표이며 현재 달성했다고 쓰지 않는다. 대형 탐색이 UI를 막으면 worker 작업량/요청 빈도를 먼저 줄인다.

**증거:** 제안 `reports/browser-performance.json`,기기/브라우저/입력 hash/샘플 수,캐시 상한,취소 테스트. 성능 때문에 원본 사진 해상도를 사용자 합의 없이 다시400×300으로 낮추지 않는다.

### H4 — 카메라/메시에서 궤도 격자로의 정합 실험

**선행:** H0의 원본/등록 출력 분리. 가장 불확실한 단계이며 성공을 미리 약속하지 않는다.

1. 두 메시와 관련 XML/MTL/PNG,해당 raw/stereo 제품,PLACES,SPICE label을 읽는다. 각 제품의 LIDVID,sol,time,camera,site/drive,frame,units,pose 출처와 유효기간을 표로 만든다. 동일 sol/site만으로 동일 좌표계라고 가정하지 않는다.
2. frame 변환 체인(camera→rover→site→Mars body/map→DTM grid)을 명시한다. 회전 행렬/quaternion 방향·축 handedness·길이 단위·시간 기준을 확인한다. PLACES 위치 하나만으로 orientation을 추정하지 않는다. SPICE kernel을 다운로드한 것과 올바르게 load/평가한 것을 구별한다.
3. 원본 제품의 유효점/NoData/confidence를 읽고 reprojection/left-right 일치 등 제공되는 품질 정보를 보존한다. XML regex/CSV 단순 split 파서는 현재 제한이므로 복잡한 라벨 지원 시 정식 파서와 fixture를 추가한다.
4. **서로 비공선인 통제점 최소3개 + fitting에 사용하지 않은 검증점 최소2개**를 선정한다. 점 선택 근거/영상 좌표/3D 좌표/궤도 좌표/불확도를 저장한다. 독립 검증점이 없으면 local_only 유지한다.
5. rigid/similarity 등 변환 모델을 선택한 이유를 기록한다. 이미 m 단위인 데이터를 임의 scale로 맞추지 않는다. full transform matrix와 inverse,units,source/destination frame,입력 hashes를 저장한다.
6. fitting residual과 holdout residual을 분리한다. holdout XY RMSE≤0.5×실제CELL,최대오차≤1×CELL을 최소 승격 gate로 사용한다. p95/각 점 오차/고도 오차도 별도 보고한다. 최소 점 수 통과만으로 넓은 영역의 정확성을 보장하지 않는다.
7. 현재 `validateRegistration()`은 개수/단위/오차 임계/transform 존재 정도의 얕은 검사다. 비공선·독립성·matrix shape/finite/invertibility·frame 호환·경계·source hash 검사까지 강화하고 빌드 경로에서 반드시 호출한다. validator를 통과했다는 이유로 과학적 정확성을 자동 주장하지 않는다.

**제안 출력:** 별도 `registration.json`(version,source_products,frames,transform,controls,holdouts,residuals,grid_hash,status),재투영 그림,`reports/registration-experiment.md`. 현재 manifest를 직접 고치는 것으로 검증을 대체하지 않는다.

**실패 분기:** 원인(시간/pose/통제점/해상도 부족)을 기록하고 local_only 관측을 유지한다. 필요한 추가 자료를 구체적으로 식별한 후 공식 출처에서만 조사한다. H5의 실제 관측 mask는 보류하고 나머지 UI/패키징은 진행할 수 있다. 직접 stereo 복원/GPU 도구는 공식 파생제품으로 부족한 이유와 성공 기준이 생긴 후 도입한다.

### H5 — 등록된 관측 범위·장애물·visor 개선

**선행:** H4 통과. 미통과 시 출처/촬영점/거리와 local-only 미리보기 개선만 가능하다.

- 등록된 유효 3D점/카메라 frustum/occlusion/신뢰도에서 observed 범위를 만든다. 사진 중심250m 원이나 경로 주변을 관측 완료로 채우지 않는다.
- `unknown`, `observed`, `blocked`, `traversable under model`을 분리한다. 미관측은 safe도blocked도 아니다. blocked는 경사/높이 단차 등 정의된 근거·threshold·해상도·confidence가 있어야 한다.
- 지도 overlay와 경로용 mask를 분리해 먼저 시각 검수한다. 승인된 실제 mask를 적용할 때 overlayRevision을 올리고 관련 모든 트리/live/zone 캐시를 무효화한다. 해제 시 원본 flag를 정확히 복원한다.
- synthetic Block test는 관측 기반 장애와 별도 레이어/출처/버전으로 남긴다. 시연 때문에 실제 관측 결과처럼 포장하지 않는다.
- visor는 source product ID 기반 cache,방위/거리/촬영 시각 정보를 보존한다. 정확한 위치에 영상이 없으면 `Nearby observation`/`No image here`처럼 짧게 표시한다. 단순 이미지 확대를 신규 고해상도 자료로 세지 않는다.
- 파노라마는 pose/노출/시차 조건이 맞는 영상만 연결한다. 합성 seam/가려짐/빈 영역을 검사하며 이동 전체를 덮는 정확한 연속 roadview라고 과장하지 않는다. 원본1280×960을 보존하고 배포용 변환은 별도 파일/해시로 관리한다.

**통과:** 정합 범위 밖 관측 완료 표시 없음,실제/가상 차단 구별,mask 적용 전후 같은 임무 비교 가능,이미지와 표시 출처 일치. **증거:** overlay 전후 그림,source→cell 매핑/품질 JSON,같은 목표의 경로/수지 변화. 지형이 개선되어도 실제 유인 탐사 안전 인증으로 표현하지 않는다.

### H6 — 전역/과학 자료 활용 확장

H4와 독립적으로 진행 가능한 작은 작업이다. 우선 지역 카드에 확보/등록/계산 가능 상태를 touch-friendly하게 표시한다. Aram pin은 기존 지역 격자의 좌표계·extent·원본 출처에서 검증한 후 추가하며 임의 대표점을 정밀 위치처럼 쓰지 않는다. 경도±180°,극지/지도 경계/확대 후 좌표 역변환을 검사한다.

MEDA/지질/PIXL/SHERLOC 등은 목표의 짧은 과학 설명과 출처 링크에 먼저 사용한다. 관측 sol/위치와 목표의 대응 근거를 기록한다. 자원 모델에 사용하려면 데이터 단위/시공간 정합/결측/불확도/모델 변환식을 별도 검증한다. 모든 다운로드를 계산에 억지로 넣지 않는다. 온라인 고해상도 타일은 선택 확장이고 네트워크 실패 시 현재32타일 오프라인 모드가 유지되어야 한다.

**증거:** 지역 catalog schema/좌표 근거,자료별 `downloaded / metadata-only / displayed / model-input` 활용표. 현재431행 CSV를 모든 확보 자료의 통합 완료로 설명하지 않는다.

### H7 — 최종 검토 패키지와 제출 준비

H1/H2 검수와 사용한 데이터 단계의 gate 결과를 먼저 확정한다. H4가 실패해도 local_only 상태를 명시한 검토 패키지는 만들 수 있으나 registered 지형 시연 완료로 표시하지 않는다.

1. source CSV를 실제 포함된 모든 지형/ortho/사진/전역/코드 자산까지 감사한다. 현재431행에는 모든 역사적 embedded 자산이 완전히 망라된 것이 아니다. 출처 URL,원제품 ID,원본/가공본 hash,처리 방식,credit,권리 근거를 연결한다.
2. 저장 용량 최적화는 원본 보존 아래 별도 배포 파생본으로 한다. 사진 품질/첫 지도 시간/메모리를 전후 측정한다. 현재40.49MB를25MB 이내라고 쓰지 않는다.
3. §19의 실제 file/HTTP/offline/기기 검수 결과와 새3분 화면 영상을 남긴다. 기존 `reports/jezero-demo-script.md`는 대본이며 녹화 완료 증거가 아니다.
4. packageReview 재실행 후 hashes.json과 실제 파일을 대조한다. README에 빌드 hash,실행 방법,완료/미완료,local_only,synthetic 차단,프로필 가정을 기록한다. 전체 raw는 패키지에 복제할 필요 없으며 원장/재현 경로를 제공한다.
5. 공개 재배포 전 코드/원자료/로고/사진 각각의 허용 조건을 확인한다. NASA 관련 자료라는 이유만으로 모든 제3자 자산의 권리를 추정하지 않는다. 로컬 패키지 생성은 공개 게시와 다르다.

**완료 산출물:** 새 HTML/해시,최신 검증 JSON/Markdown,실기 QA/성능,출처·활용표,실험 결과/실패 이유,3분 영상,갱신된 PLAN. 미완료 gate는 그대로 남긴다.

## 19. 브라우저모바일 검수와 최종 산출물

### 19.1 실제 실행 매트릭스

제안 증거 파일 `reports/browser-qa.md`에 각 행의 pass/fail/not-run,환경,재현 순서,스크린샷/영상 위치를 기록한다. 자동 검사 성공을 이 표의 pass로 옮기지 않는다. 모바일 에뮬레이션과 실제 기기 검증을 구별한다.

| 시나리오 | 조작 | 기대 결과 |
|---|---|---|
| 진입 | hash없음/#mars/#jezero/#jezero-evidence-demo | 각각 전역/전역/상세/고정 시연,무한 로딩 없음 |
| 목표 | A만/B만/A+B/선택 해제/불연결 Navcam | 선택과 시간 일치,불능 명시,관측-only에서 계획 추가 차단 |
| 배분 | 25/50/75 및 순서 변경 | A/B 귀속 유지,합계와3종 시간 일치 |
| 회전/줌 | Shift-drag,15°버튼,휠/±,터치 twist/pinch/pan | 표시/클릭 동일 좌표,라벨 정립,축척 갱신 |
| N | 회전/이동/확대 후 여러 번 클릭 | 북쪽0°,현재 위치 중심,zoom 유지,토글 없음 |
| 사진 | 여러POI/방위/같은sol제품 전환 | 실제 사진과source 일치,빈 상태 명확,깨진 이미지 없음 |
| visor | 사용자 클릭으로 창 열기,재생/정지/닫기/다시 열기 | 지도와같은 frame,오류/고아 타이머 없음 |
| 귀환 | 이동 중/작업 중/부분 분 Return now | 소모량·시간 유지,체류0,Start/Restart 의미 일치 |
| 예산 | 알려진 누설/열/물/O2 변화 | pending 구별,새 예측 적용,제약 위반 시 명확한 상태 |
| 차단 | Block test→Clear block 반복 | synthetic 표시,경로 재계산,원본flags 복원 |
| 지역 전환 | Jezero→Gale→Jezero 빠르게,loading 중 전환 | 늦은 데이터 혼입 없음,pending 정리,타지역 회귀 없음 |
| 전역 | 열기/닫기,pan/zoom,경계 클릭,지역 카드 | 상태 유지,경위도 정확,임의 지점 경로 계산 없음 |
| 오프라인 | 다운로드 후 네트워크 끊고 file 열기 | 내장지도/사진/worker 기능,외부source 링크만 네트워크 필요 |
| HTTP 비교 | localhost에서 같은 hash | file와 기능 동일 또는 차이/대응 명시 |
| 화면 크기 | 데스크톱1440×900,소형390×844,가로모드 | 컨트롤 겹침/잘림 없음,터치 가능,대화상자 닫기 가능 |
| 접근/언어 | Tab/Enter/Escape,설정/오류/빈상태 | focus/이름/영문 가독성,한글 legacy 누락 없음 |
| 성능 | cold open/첫계획/live/반복 전환 | 기기와측정법 기록,장시간 main-thread 멈춤/메모리 증가 조사 |

popup이 차단되면 사용자 클릭 흐름에서 정상 허용/안내 또는 같은 창 대체를 구현한다. 보안 설정을 전역 해제하는 것을 해결책으로 삼지 않는다. 기기가 없으면 해당 행은 not-run으로 남기고 desktop emulator 결과만 표시한다.

### 19.2 결과 기록 형식

각 실험은 아래 최소 형식을 사용한다. 성공한 예만 저장하지 말고 실패 조건/관측 공백도 남긴다.

```text
run_id / 날짜 / 담당 도구·환경:
가설 또는 사용자 동작:
입력 파일·SHA256 / 모델·정책 버전 / base·목표·자원:
실행 명령 또는 재현 절차:
비교 기준 / 허용오차 / 사전 통과 조건:
실측 결과 / 실행시간·메모리 / 증거 파일:
판정(pass/fail/not-run/local-only)과 이유:
남은 제한 / 다음 실험 / PLAN에서 갱신한 항목:
```

## 20. 다음 작업자의 시작종료 체크리스트

### 시작할 때

- [ ] §15의 hash/파일/환경을 실제 사본과 비교하고 차이를 기록한다. 현재 사용자 변경을 덮어쓰지 않는다.
- [ ] §16의 부작용을 읽고 source/HTML/mission/registration을 백업한다.
- [ ] Node CLI/Python 가용성을 확인한다. 기존 제공 도구가 Claude 환경에도 있다고 가정하지 않는다.
- [ ] 현재65개 검사를 재현하고,데이터/모델이 달라졌다면 실제 격자/Python 대조를 수행한다.
- [ ] H0부터 개선하고 H1의 실제 UI 검수를 실행한다. 정합은 H4의 증거 gate로 진행한다.

### 작업을 마칠 때

- [ ] 변경한 기능과 해당 테스트/실기 증거를 연결한다. 문서 수정만 했으면 제품 검증을 새로 했다고 쓰지 않는다.
- [ ] 제품/보고서/입력 해시의 일치를 확인하고 패키지 생성 부작용을 점검한다.
- [ ] PLAN의 현재 상태 표,실행 명령,남은 H단계,실패 이유를 갱신한다. 과거 성공 숫자를 최신처럼 복사하지 않는다.
- [ ] 새 파일명/필드가 제안인지 실제 구현인지 구별한다. 정합 미통과 시local_only 유지한다.
- [ ] 다음 사람이 첫 실행 명령과 다음 미완료 작업을 바로 알 수 있도록 남긴다.

**Claude Code에 전달할 시작 지시 예시:** “C:/nasa/PLAN.md의 §15~20을 현재 기준으로 읽고 기존 제품/관측 자료를 보존해 이어서 진행해줘. 먼저 환경과 해시를 확인하고 H0 빌드 재현성 및 테스트 부작용을 해결한 다음 H1 실제 UI 검수를 진행해줘. 좌표 정합은 H4의 독립 검증 gate를 통과할 때만 승격하고, 실행 결과와 다음 단계를 PLAN에 계속 갱신해줘.”
