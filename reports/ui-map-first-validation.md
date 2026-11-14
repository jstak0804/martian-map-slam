# 지도 중심 UI 구현 기록

2026-11-14. 사용자 요청: PLAN.md의 UI 수정부터 구현.

## 변경

- `demo_template.html`의 기존 Canvas, 자료 디코더, 워커, 경로 탐색, 재생 시계를 재사용했다.
- 지도 전체 화면, 지역 선택, 접는 상세 설정, 지점 목록/팝업, 간결한 3종 시간 카드, 확대/축소/이동/축척, 북쪽/진행방향 전환을 연결했다.
- A/B 최대 두 지점의 완전한 방문 순서를 평가한다. 선택 일부를 제외하던 기존 EVA 부분집합 탐색을 교체했다. 체류는 공통 자원 예산에서 동일 비율로 배분하며 A→B/B→A 선택이 가능하다.
- EVA 모드의 산소 하한은 출발량의20%다. 기본 질량816.466266g은 PLAN의 Apollo 참고 가정이다. 명목1430psia와 질량의 정확한 대응을 검증했다고 주장하지 않는다. 기존 고급 분석 모드는 기존 예비분 정책을 유지한다.
- EVA 영역은 현재 위치→후보→Base 체류0 조건으로 분류한다. 현재 위치의 순방향 트리가 계산 중이면 회색 해칭을 보이고 이전 위치의 영역을 새 영역처럼 표시하지 않는다.
- visor는 동일한 재생 위치/heading으로 DTM 기반 가상 시점을 렌더링한다. 사진 로드뷰는 기존 관측 자료를 사용한다. POI의250m 이내 사진이 없으면 근접 관측 없음으로 표시한다.
- 기본 진입 지역은 Jezero. 기존 지역·모드·사진·설정은 유지했다.

## 빌드

Python 빌드에도 UI CSS/JS 임베드를 추가했다. 현재 환경에서는 Python/Node CLI 대신 Node REPL로 `build_ui_preview.mjs`를 실행했다. 이 빌더는 이미 패키징된 과학 데이터와 영상 payload를 그대로 보존하면서 UI만 재조립한다.

재현 명령(해당 런타임 설치 환경):

```text
node code/build_ui_preview.mjs
node tests/test_map_ui.mjs
```

산출물: `reports/18-eva-walkback-demo.html`, 동일 내용의 `.standalone.html`. 수정 전 템플릿/HTML은 `C:/nasa/research/ui-baseline/`에 보존했다.

## 검증 결과

- 전체 HTML 실행 스크립트의 JavaScript 문법 검사 통과.
- 순수 정책·좌표 변환·실제 UI 플래너 함수 기반 테스트20개 통과: 산소20%, 색10/20% 경계, 물 제한,0체류와불가능 구분, NaN, 회전 클릭 역변환, A만/A+B/역순/도달불가 목표 누락 방지.
- 빌드 전후 `meta`, `blob`, `sites` payload 동일성 확인.
- 로컬 HTTP 미리보기 서버와 Chrome 실행 완료.
- **브라우저 시각/조작 검증 미완료:** 브라우저 연결 호스트가 없었고 네이티브 앱 접근 승인이 시간 초과했다. 실제 화면·팝업·반응형·전체 재생 성공을 확인했다고 보고하지 않는다.

## 남은 범위

- 실제 Chrome/Edge에서 선택·재생·두 창 동기화·회전·모바일 화면을 검수해야 한다. 현재 단위 테스트는 전체 UI 통합 검증을 대체하지 않는다.
- 새로운25GB 원자료의 좌표 정합/POI 확대/파노라마 합성 및 전역 화성 지도는 이번 UI 수정에서 새로 처리하지 않았다. 현재 패키지의 세 지역과 POI/로드뷰를 사용한다.
- A/B 체류 배분은1:1이며 사용자 지정 비율 조절은 후속 작업이다. 시간 카드는 계획 시간, visor는 현재 귀환 시간을 보여준다. 실시간 체류 여유 재최적화와 수동 즉시귀환 버튼은 별도 후속 작업이다.
- 기존 분 단위 시뮬레이션을 재사용한다. 시간/수지의 실제 지형 전 경로 대조와 센서 이상 시나리오 회귀 검증은 추가로 필요하다.

새로운 원자료 정합이나 과학적 안전 검증 완료로 간주하지 않는다.


## UI feedback revision (2026-11-14)

Supersedes the initial synthetic visor and north/heading toggle described above.

- Native1280×960 NASA/JPL Navcam PNG observations for10 Jezero stops are embedded offline;400×300 previews are no longer the primary visor image. Images are shown without invented camera motion. Distance from the explorer and direction availability remain visible.
- Map rotation: two-finger pinch/twist/pan, Shift-drag, and15-degree rotate buttons. N always sets north-up and centers the current explorer position without changing zoom.
- Screen-space markers distinguish YOU (blue direction arrow), BASE (station), and survey sites (flag pin, A/B when selected).
- English-only controls, units, tooltips, accessible labels, target descriptions and photo captions; language toggles removed.
-28 regression checks pass, including simultaneous pinch/rotation anchor preservation, angular wrap, zoom cap, repeated north reset, native photo preference and no synthetic fallback for missing photos. All emitted JavaScript parses. Terrain grid payloads preserved.
- Browser visual/touch verification still pending: browser access host is unavailable.
- Standalone output grows to about36.4MB because the10 original PNGs are embedded. The25MB target is an internal optimization target, not a required limit.
- Accurate continuous, direction-matched real imagery remains dependent on later camera/position registration and panorama work in PLAN §12.


## Mission controls and global overview — 2026-11-14

Implemented weighted A/B stay allocation (25/50/75% for A), deterministic manual return from the current minute, cumulative travel/work counters shared by map and visor, and an offline MOLA global overview with three region links. Return preserves elapsed time and consumed oxygen; restarting restores the original itinerary. The return path replaces the planned route while returning manually.

Validation: 34 tests pass, including whole-trip shared budgets with weighted stops, simulated arrival at home, manual-return resource continuity, itinerary immutability, and 32 embedded global tiles. Generated HTML scripts compile. Both reports rebuilt at 40,032,403 bytes. Terrain payloads unchanged.

MOLA placement uses the downloaded WMTS matrix: top-left −180/90, tile 256×256, 8 columns × 4 rows. Jezero marker uses sites.py landing coordinates; Gale uses the existing mars_walkback.py grid transform and base cell center. Aram remains a region link until its locator coordinate is registered. Global artwork is color-shaded relief, not an RGB surface photograph.

Limits: browser host unavailable; no visual or mobile interaction pass claimed. Live stay is remaining scheduled work capped by immediate-return oxygen/water, not future multi-stop re-optimization. Manual return acts at the simulation's current whole-minute snapshot. Position-aware rover photo selection remains approximate, with camera direction unverified where no calibrated azimuth is available.
