(() => {
  const words = {
    'Compare routes':'경로 비교','Fit return area':'전체 영역 보기','Delete destination':'목표 삭제',
    'Stay: blank = auto · fill all stops for a fixed plan':'체류: 빈칸은 자동 · 고정 계획은 모든 지점 입력',
    'Select up to three sites':'최대 3곳을 선택하세요','Travel mode':'이동 방식',
    'Terrain-based walking model':'지형 기반 도보 모델',
    'Auto':'자동','Select':'선택','Stay split':'체류 배분','Methods and limitations':'방법 및 한계',
    '>20%　 / Check terrain':'>20% / 지형 확인','Loading terrain…':'지형 불러오는 중…',
    'Close site':'지점 닫기','Restart trip':'탐사 다시 시작','My location':'현재 위치','Full map':'전체 지도',
    'No nearby observation':'인근 관측 사진 없음','Science target · ground-image registration pending':'탐사 목표 · 지상 영상 위치 정합 미검증',
    'Source:':'출처:','Photo source':'사진 출처','Evidence':'관측 근거',
    'Languages':'언어','Resources and model':'자원 및 모델','Map and analysis':'지도 및 분석',
    'Data and validation':'자료 및 검증','Controls and reference':'조작 및 참고 자료',
    'Settings and analysis':'설정 및 분석','Global map':'전역 지도','Global map: choose a region':'전역 지도: 지역 선택',
    'Sites':'탐사 지점','Rover photos':'로버 사진','Roadview':'로드뷰','Settings':'설정','Visor':'바이저',
    'Observations':'관측 자료','Planning':'탐사 계획','Sources and credits':'출처 및 제작 정보',
    'Select a site':'탐사 지점을 선택하세요','Return now':'지금 복귀','BASE':'기지','YOU':'현재 위치',
    'Move base':'기지 이동','Place base inside the mapped terrain':'지형 자료가 있는 곳에 기지를 놓으세요',
    'Base moved — trip recalculated':'기지를 이동했습니다 — 경로 재계산',
    'Reset view':'시점 초기화','MARS · 3D EXPLORER':'화성 · 3D 탐색',
    'Drag to rotate · scroll to zoom · select a region to plan':'드래그로 회전 · 휠로 확대/축소 · 지역을 선택해 탐사 계획',
    'Close globe':'전역 지도 닫기','Zoom globe in':'전역 지도 확대','Zoom globe out':'전역 지도 축소',
    'Interface language':'화면 언어','Close settings':'설정 닫기','Return oxygen · no stay':'복귀 시 산소 · 체류 제외',
    'Travel left':'남은 이동 시간','Return from site':'지점에서 복귀','Return left':'남은 복귀 시간','Stay left':'남은 체류 시간',
    'On the way':'이동 중','At site':'탐사 지점','Returning':'복귀 중','At base':'기지 도착',
    'Return failed':'복귀 실패','Survey ended':'탐사 종료','Updating trip estimate…':'예상 시간 갱신 중…',
    'Add to route':'경로에 추가','Remove from route':'경로에서 제거','No route from this base':'이 기지에서 연결되는 경로 없음',
    'Calculating route…':'경로 계산 중…','Select up to two sites':'최대 두 지점을 선택하세요',
    'Face next target':'다음 목표 방향으로 정렬','Align next target to top':'다음 목표 방향을 화면 위로 정렬',
    'Zoom in':'확대','Zoom out':'축소','Center on my position':'현재 위치로 이동','Show full map':'전체 지도 보기'
  };
  const reverse=Object.fromEntries(Object.entries(words).map(([en,ko])=>[ko,en]));
  const translate=value=>{
    const trimmed=value.trim(), dictionary=LANG==='ko'?words:reverse;
    if(dictionary[trimmed])return value.replace(trimmed,dictionary[trimmed]);
    const pairs=[[/^SITE (\d+)$/,'지점 $1',/^지점 (\d+)$/,'SITE $1'],[/^Destination (\d+)$/,'목표 $1',/^목표 (\d+)$/,'Destination $1'],[/^(.+) · (\d+) min \/ stay (\d+) min$/,'$1 · $2 min / 체류 $3 min',/^(.+) · (\d+) min \/ 체류 (\d+) min$/,'$1 · $2 min / stay $3 min']];
    for(const [en,ko,kr,english] of pairs){const rule=LANG==='ko'?en:kr;if(rule.test(trimmed))return value.replace(trimmed,trimmed.replace(rule,LANG==='ko'?ko:english));}
    return value;
  };
  const root=document.querySelector('.app'), observer=new MutationObserver(refresh);
  function refresh(){
    observer.disconnect();
    // Existing translation records restore original Korean model controls.
    applyLang();notesLang();
    const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
    for(let node;(node=walker.nextNode());){
      if(node.parentElement.closest('script,style,option'))continue;
      const next=translate(node.nodeValue);if(next!==node.nodeValue)node.nodeValue=next;
    }
    for(const el of document.querySelectorAll('[title],[aria-label],[placeholder]'))for(const attr of ['title','aria-label','placeholder']){
      if(!el.hasAttribute(attr))continue;const old=el.getAttribute(attr),next=translate(old);if(old!==next)el.setAttribute(attr,next);
    }
    document.documentElement.lang=LANG;
    observer.observe(document.body,{childList:true,subtree:true,characterData:true});
  }
  const picker=$('settings-language');
  picker.addEventListener('change',()=>{
    LANG=picker.value;state.hudLang=LANG;
    try{localStorage.setItem('martian-map-language',LANG);}catch{}
    uiPaint();if(UI.poi>=0&&!$('map-poi').hidden)uiOpenPoi(UI.poi);if(!$('map-catalog').hidden)uiCatalog();refresh();
  });
  try{if(localStorage.getItem('martian-map-language')==='ko')LANG='ko';}catch{}
  picker.value=LANG;state.hudLang=LANG;refresh();
})();
