// Included inside the existing planner closure: one state and one simulation clock.
const UI = { poi: -1, heading: 0, headingUp: false, angle: 0, order: 'auto', share: 50, toastTimer: 0, screen: null };
const uiText = (ko, en) => LANG === "ko" ? ko : en;
const uiEscape = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const uiTime = s => Number.isFinite(s) && s >= 0 ? `${Math.floor(s / 60)} min` : '—';
const uiName = t => (t.ui?.name || t.name_en || trText(t.name || '') || t.name || 'Survey site').replace(/ sample site| drill sites?/g, '').trim();
function uiToast(message) { const el=$('map-toast'); el.textContent=message; el.hidden=false; clearTimeout(UI.toastTimer); UI.toastTimer=setTimeout(()=>el.hidden=true,2600); }
function uiMount() {
  const shell=document.createElement('div'); shell.id='map-ui';
  shell.innerHTML=`
    <header class="map-shell map-top"><div class="map-glass map-brand"><span class="map-logo">◈</span><div><b>MARTIAN MAP</b><small>EXPLORATION / EVA PLANNER</small></div></div><nav class="map-glass map-actions" aria-label="Map menu"><button id="map-world" aria-label="Global map: choose a region">Global map</button><select id="map-region" aria-label="Region" hidden style="display:none"></select><button id="map-sites">Sites</button><button id="map-roadview">Rover photos</button><button id="map-visor">Visor ↗</button><button id="map-evidence">Observations</button><button id="map-event" title="Synthetic blocked patch">Block test</button><button id="map-settings" aria-expanded="false">Settings</button></nav></header>
    <div class="map-shell map-tools"><button class="map-button" id="map-north" aria-label="Reset north and center on me" title="North up · center on me"><span id="map-north-arrow">↑</span><small>N</small></button><button class="map-button" id="map-rotate-left" aria-label="Rotate map left" title="Rotate left · or Shift-drag">↶</button><button class="map-button" id="map-rotate-right" aria-label="Rotate map right" title="Rotate right · or twist with two fingers">↷</button><button class="map-button" id="map-plus" aria-label="Zoom in">+</button><button class="map-button" id="map-minus" aria-label="Zoom out">−</button><button class="map-button" id="map-center" aria-label="Center on my position" title="My location">⌖</button><button class="map-button" id="map-fit" aria-label="Show full map" title="Full map">⤢</button></div>
    <div class="map-shell map-scale"><span id="map-scale-label">—</span><b id="map-scale-line"></b></div>
    <div class="map-shell map-glass map-legend" id="map-legend"><span>Return oxygen · no stay</span><span><i style="background:#ed7663"></i>≤10%　<i style="background:#ecc76a"></i>≤20%</span><span><i style="background:#669fc8"></i>&gt;20%　 / Check terrain</span></div>
    <section class="map-shell map-glass map-bottom" aria-label="Trip times"><div class="map-mission-head"><b id="map-plan-title">Planning</b><span class="map-status" id="map-plan-status" role="status">Select a site</span></div><div class="map-time-grid"><div><small id="map-out-label">Travel time</small><strong id="map-out">—</strong></div><div><small id="map-back-label">Return time</small><strong id="map-back">—</strong></div><div><small id="map-dwell-label">Time at site</small><strong id="map-dwell">—</strong></div></div><div class="map-split" id="map-split"></div><label id="map-share-wrap" hidden>Stay split <select id="map-share" aria-label="Time at A versus B"><option value="25">A 25% / B 75%</option><option value="50" selected>A 50% / B 50%</option><option value="75">A 75% / B 25%</option></select></label><div class="map-mission-foot"><div class="map-chips" id="map-chips"></div><button class="map-button" id="map-order" hidden> A→B </button><button class="map-button" id="map-return" disabled>Return now</button><button class="map-button" id="map-reset" aria-label="Restart trip" title="Restart trip">↺</button><button class="map-button primary" id="map-play" disabled>▶ Start</button></div></section>
    <section class="map-shell map-glass map-popup" id="map-poi" hidden role="dialog" aria-label="Site observation"><div class="map-popup-head"><b id="map-poi-name"></b><button class="map-close" id="map-poi-close" aria-label="Close site">×</button></div><div class="map-popup-image" id="map-poi-image"></div><div class="map-popup-body"><p id="map-poi-caption"></p><button class="map-button primary" id="map-poi-select">Select</button><details><summary id="map-evidence-label">Photo source</summary><p id="map-poi-evidence"></p></details></div></section>
    <section class="map-shell map-glass map-catalog" id="map-catalog" hidden aria-label="Survey sites"></section>
    <div class="map-drawer" id="map-drawer" hidden><div class="map-drawer-head"><b>Settings and analysis</b><button class="map-close" id="map-drawer-close" aria-label="Close settings">×</button></div></div>
    <div class="map-shell map-glass map-toast" id="map-toast" role="status" hidden></div>`;
  document.querySelector('.app').appendChild(shell);
  const drawer=$('map-drawer');
  for(const el of [document.querySelector('.grid>.panel'),document.querySelector('.modebar'),document.querySelector('.grid>div[style]'),$('notes-ko'),$('notes-en')]) if(el)drawer.appendChild(el);
  $('eva-dwell').closest('.ctl').hidden=true;
  const credits=document.createElement('button');credits.id='map-credits';credits.className='map-button';credits.textContent='Sources and credits';credits.onclick=uiCredits;
  const attribution=document.createElement('button');attribution.id='map-attribution';attribution.className='map-shell map-attribution';attribution.textContent='NASA/JPL-Caltech · UArizona · ASU · Credits';attribution.setAttribute('aria-label','Sources and credits');attribution.onclick=uiCredits;shell.append(attribution);
  const help=document.createElement('p');help.className='hint';help.textContent='Drag to move. Shift-drag or use ↶ / ↷ to rotate. On touch screens, pinch and twist with two fingers. N resets north and centers on you.';drawer.prepend(help);
  const profile=document.createElement('p');profile.className='hint';profile.textContent='Apollo reference: 1,430 psia / 1.8 lb. Assumed capacity, not a verified Mars suit profile. The trip keeps 20% of starting oxygen for return.';drawer.prepend(profile);drawer.prepend(credits);
  $('map-region').innerHTML=SITE_LIST.map((s,i)=>`<option value="${i}">${uiEscape(s.meta.site.short.replace("(가상 거점)","(virtual base)"))}</option>`).join('');
  $('map-world').onclick=uiWorld;
  $('map-evidence').onclick=uiEvidence;$('map-event').onclick=uiBlockTest;
  $('map-region').onchange=e=>{uiClear();loadSite(Number(e.target.value));};
  $('map-sites').onclick=()=>{ $('map-catalog').hidden=!$('map-catalog').hidden; $('map-poi').hidden=true; uiCatalog(); };
  $('map-roadview').onclick=()=>{ $('map-poi').hidden=true; $('map-catalog').hidden=true; $('rv-btn').click(); if(state.rvMode && META.roadview?.length){state.rv=nearestRv(simFrame()?.pos??state.base);renderRv();drawVec();} };
  $('map-visor').onclick=()=>{ if(!state.hud)$('hud-btn').click();else if(hudPopupOpen())HUDWIN.focus();else if(openHudPopup())renderHud(); };
  const drawerToggle=on=>{drawer.hidden=!on;$('map-settings').setAttribute('aria-expanded',String(on));};
  $('map-settings').onclick=()=>drawerToggle(drawer.hidden);$('map-drawer-close').onclick=()=>drawerToggle(false);
  $('map-rotate-left').onclick=()=>uiRotateBy(-15);$('map-rotate-right').onclick=()=>uiRotateBy(15);
  $('map-plus').onclick=()=>$('zin').click();$('map-minus').onclick=()=>$('zout').click();
  $('map-fit').onclick=()=>{UI.headingUp=false;UI.angle=0;resetZoom();};
  $('map-north').onclick=uiNorthUp;
  $('map-center').onclick=()=>uiCenter(simFrame()?.pos ?? state.base);
  $('map-poi-close').onclick=()=>{$('map-poi').hidden=true;$('map-sites').focus();};
  $('map-poi-select').onclick=()=>{if(META.targets[UI.poi]?.source_kind==='user_target')uiDeleteDestination(UI.poi);else uiSelect(UI.poi);};
  $('map-play').onclick=()=>{if(state.mode!=='eva'||!EVA?.ok)return;$('sim-play').click();uiPaint();};
  $('map-reset').onclick=()=>{SIMSIG='';ensureSim();$('sim-restart').click();uiPaint();};
  $('map-return').onclick=uiReturnNow;
  $('map-share').onchange=e=>{UI.share=Number(e.target.value);uiInvalidate();};
  $('map-order').onclick=()=>{UI.order=UI.order==='forward'?'reverse':'forward';uiInvalidate();};
  document.addEventListener('keydown',e=>{if(e.key==='Escape'){drawerToggle(false);$('map-poi').hidden=true;$('map-catalog').hidden=true;$('map-sites').focus();}});
  document.addEventListener('visibilitychange',()=>{if(document.hidden){stopSim();uiPaint();}});
  window.addEventListener('beforeunload',()=>{if(hudPopupOpen())HUDWIN.close();});
  // Capture only real POIs; unrelated clicks retain the existing advanced modes.
  vec.addEventListener('click',e=>{
    if(dragMoved)return; const p=uiGridPoint(e), view=UI.screen;if(!p||!view)return;
    const tol=18*W/(view.w*ZK);let best=-1,dist=tol;
    (META.targets||[]).forEach((t,i)=>{const d=Math.hypot(t.x-p.x,t.y-p.y);if(d<dist){dist=d;best=i;}});
    if(best>=0){e.stopImmediatePropagation();uiOpenPoi(best);}
  },true);
}
// H1 point 4: display strings live in t.ui only. The record fields (name, why, source, samples,
// station, science_*) are never rewritten, so provenance and lookups keep the original catalogue values.
const UI_SOURCE_LABEL={
  rover:'NASA MMGIS M20_waypoints (stay window) + NASA Mars 2020 sample list (matched by sealing sol)',
  aram:'JPL Mars Trek THEMIS night-IR mosaic (automatic selection)',
  places_station:'NASA PDS Mars 2020 PLACES localisation (site/drive)',
};
function uiLocalizeMeta(meta) {
  for(const t of meta.targets||[]) {
    if(t.source_kind==='user_target')continue;
    const station=t.source_kind==='places_station', aram=meta.site.id==='aram';
    const samples=(t.samples||[]).map(s=>s.name+' (sol '+s.sol_sealed+')').join(', ');
    t.ui={
      name:station?(t.name_en||t.name):aram?'Warm night-IR area '+(String(t.name).match(/\d+/)?.[0]||''):(t.name_en||trText(t.name)||t.name),
      summary:station?'PLACES station '+t.station.site+'/'+t.station.drive+' · Sol '+(t.sols?.[0]??'')+'. Planned approach '+t.station.approach_offset_m.toFixed(1)+' m from the rover location. Ground-image registration pending.'
        :aram?'Candidate area based on relative night-IR brightness. Surface material is not verified.'
        :'Rover survey stop'+(t.sols?.length?' · Sol '+t.sols.join('–'):'')+'. '+(samples?'Samples: '+samples+'. ':'')+'Location from rover records; precise image registration is pending.',
      summary_ko:station?'PLACES 관측 지점 '+t.station.site+'/'+t.station.drive+' · Sol '+(t.sols?.[0]??'')+' · 로버 위치와 '+t.station.approach_offset_m.toFixed(1)+' m 차이. 지상 영상 위치 정합은 미검증입니다.':aram?'야간 적외선의 상대 밝기로 선정한 후보지입니다. 표면 물질은 확인되지 않았습니다.':'로버 탐사 지점'+(t.sols?.length?' · Sol '+t.sols.join('–'):'')+'. '+(samples?'시료: '+samples+'. ':'')+'로버 기록에 기반한 위치이며, 정밀 영상 위치 정합은 미검증입니다.',
      source:UI_SOURCE_LABEL[station?'places_station':aram?'aram':'rover'],
      record_id:t.id||(station?'PLACES '+t.station.site+'/'+t.station.drive:null),
    };
  }
  for(const p of meta.photos||[])p.camera=(p.camera||'Navcam').replace('왼쪽','left').replace('오른쪽','right');
}
function uiClear(){stopSim();uiRadiusLast=null;uiHideOuterRadius();if($('radius-context-map'))$('radius-context-map').hidden=true;UI.originalFlags=null;UI.blocked=[];UI.liveTree=null;UI.livePending=null;UI.liveEstimate=null;UI.liveEstimateKey=null;UI.zonePending=false;UI.zoneTree=null;UI.zoneKey=null;if($('map-markers'))$('map-markers').hidden=true;UI.poi=-1;UI.order='auto';UI.share=50;UI.heading=0;UI.livePos=null;UI.angle=0;UI.headingUp=false;if($('map-poi'))$('map-poi').hidden=true;if($('map-catalog'))$('map-catalog').hidden=true;}
function uiInvalidate(){stopSim();UI.livePending=null;UI.liveEstimate=null;UI.liveEstimateKey=null;EVA=null;EVASIG='';SIM=null;SIMSIG='';lastVec={path:null};state.mode='eva';update();uiPaint();}
async function uiSelect(i){
  if(i<0)return;const selected=evaSelected();
  if(!state.evaSel[i]&&selected.length>=3){uiToast(uiText('최대 3곳을 선택할 수 있습니다','Select up to three sites'));return;}
  if(!state.evaSel[i]&&!await uiCanSelectTarget(tCell(META.targets[i])))return;
  if(!state.evaSel[i]&&evaSelected().length>=3)return;
  state.evaSel[i]=!state.evaSel[i];UI.order='auto';uiInvalidate();uiOpenPoi(i);
}
// members: optional subset of target indices (an overlapping-pin group); default lists every site.
function uiCatalog(members){
  const list=members||(META.targets||[]).map((t,i)=>i);
  $('map-catalog').innerHTML=`<b style="font-size:12px">${members?members.length+' sites at this spot':uiText('탐사 지점','Exploration sites')}</b>`+list.map(i=>[META.targets[i],i]).map(([t,i])=>`<button data-poi="${i}"><span>◇ ${String(i+1).padStart(2,'0')}</span><b>${uiEscape(uiName(t))}</b></button>`).join('');
  if(!(META.targets||[]).length)$('map-catalog').append(uiText('등록된 지점 없음','No registered sites'));
  $('map-catalog').querySelectorAll('button').forEach(b=>b.onclick=()=>{uiOpenPoi(Number(b.dataset.poi));uiCenter(tCell(META.targets[Number(b.dataset.poi)]));});
}
function uiOpenPoi(i){
  const t=META.targets?.[i];if(!t)return;UI.poi=i;$('map-catalog').hidden=true;$('map-poi').hidden=false;
  $('map-poi-name').textContent=uiName(t);$('map-poi-evidence').textContent=(LANG==='ko'?t.ui?.summary_ko:t.ui?.summary) || `Rover observation and sample records. Sol ${(t.sols||[]).join('–')}. Target location is approximate; ground-image registration is pending.`;
  $('map-poi-science')?.remove();$('map-poi-source')?.remove();
  if(t.ui?.source){const src=document.createElement('p');src.id='map-poi-source';src.className='map-poi-source';src.textContent='Source: '+t.ui.source+(t.ui.record_id?' · record '+t.ui.record_id:'');$('map-poi-evidence').after(src);}
  if(t.science_en){const box=document.createElement('div');box.id='map-poi-science';const p=document.createElement('p');p.textContent=t.science_en;box.append(p);
    for(const u of t.science_sources||[]){const a=document.createElement('a');a.href=u;a.target='_blank';a.rel='noopener';a.textContent=u.replace(/^https:\/\/pds-geosciences\.wustl\.edu\/m2020\//,'PDS ');a.style.cssText='display:block;color:#8ed8f5;overflow-wrap:anywhere';box.append(a);}
    $('map-poi-evidence').after(box);}
  if(t.source_kind==='places_station')$('map-poi-evidence').textContent+=' Position from PLACES (NASA operations localisation); three independent orbital-registration attempts did not pass, so it is not independently verified.';
  const p=(META.photos||[]).map(p=>({p,d:Math.hypot(t.x-p.x,t.y-p.y)*CELL})).sort((a,b)=>a.d-b.d)[0];
  const box=$('map-poi-image');box.replaceChildren();
  if(p&&p.d<=250){const im=document.createElement('img');im.src=p.p.full_img || p.p.img;im.alt=`${p.p.rover} Navcam sol ${p.p.sol}`;box.append(im);$('map-poi-caption').textContent=uiText(`인근 관측 · sol ${p.p.sol} · ${Math.round(p.d)}m 거리`,`Nearby observation · sol ${p.p.sol} · ${Math.round(p.d)}m away`);}
  else{box.textContent=uiText('이 지점의 근접 관측 없음','No nearby observation');$('map-poi-caption').textContent=uiText('과학 목표 위치 · 지상 사진 정합 확인 필요','Science target · ground-image registration pending');}
  $('map-poi-select').textContent=state.evaSel[i]?uiText('선택 해제','Remove from route'):uiText('경로에 추가','Add to route');
  $('map-poi-select').setAttribute('aria-pressed',String(!!state.evaSel[i]));$('map-poi-select').hidden=t.source_kind==='user_target';
  const disconnected=t.default_base_reachable===false&&state.base===BASE0&&!state.evaSel[i];$('map-poi-select').disabled=disconnected;if(disconnected){$('map-poi-select').textContent='No route from this base';$('map-poi-caption').textContent+=' · Observation only';}
  else if(t.source_kind==='places_station'&&t.default_base_reachable==null)$('map-poi-caption').textContent+=' · Route from base not pre-checked';
  drawVec();
}
function uiView(){const cw=wrap.clientWidth,ch=wrap.clientHeight,s=Math.max(cw/W,ch/R);return{w:W*s,h:R*s,k:ZK,angle:UI.angle,cx:cw/2+ZX,cy:ch/2+ZY};}
function uiApplyZoom(redraw=true){
  ZK=Math.min(10,Math.max(.08,ZK));const v=UI.screen=uiView();
  stage.style.width=`${v.w}px`;stage.style.height=`${v.h}px`;
  stage.style.transform=`translate(${v.cx}px,${v.cy}px) rotate(${v.angle}deg) scale(${ZK}) translate(${-v.w/2}px,${-v.h/2}px)`;
  stage.style.setProperty('--zk',String(ZK));$('zreset').hidden=ZK===1;
  if($('map-north-arrow')){$('map-north-arrow').style.transform=`rotate(${UI.angle}deg)`;$('map-north').title='Reset north · '+Math.round(((UI.angle%360)+360)%360)+'° map rotation';}
  uiScale();uiMarkers();if(redraw){clearTimeout(zTimer);zTimer=setTimeout(()=>drawVec(),60);}
}
function uiGridPoint(ev){if(!UI.screen)return null;const r=wrap.getBoundingClientRect(),p=MapUIRules.unproject(ev.clientX-r.left,ev.clientY-r.top,UI.screen);return{x:p.x/UI.screen.w*W,y:p.y/UI.screen.h*R};}
function uiZoomAt(f,cx,cy){const v=UI.screen||uiView(),p=MapUIRules.unproject(cx,cy,v);ZK=Math.max(.08,Math.min(10,ZK*f));const next={...v,k:ZK},q=MapUIRules.project(p.x,p.y,next);ZX+=cx-q.x;ZY+=cy-q.y;uiApplyZoom();}
function uiCenter(cell){const v=uiView(),p=MapUIRules.project((cell%W+.5)/W*v.w,((cell/W|0)+.5)/R*v.h,v);ZX+=wrap.clientWidth/2-p.x;ZY+=wrap.clientHeight/2-p.y;uiApplyZoom();}
function uiScale(){if(!$('map-scale-line')||!UI.screen)return;const mpx=CELL*W/(UI.screen.w*ZK),raw=100*mpx,p=Math.pow(10,Math.floor(Math.log10(raw))),n=[1,2,5,10].filter(n=>n*p<=raw).pop()||1,m=n*p;$('map-scale-line').style.width=`${m/mpx}px`;$('map-scale-label').textContent=m>=1000?`${m/1000} km`:`${Math.round(m)} m`;}
function uiPaint(){
  if(!$('map-ui'))return;const sel=evaSelected(),e=state.mode==='eva'?EVA:null,f=simFrame();
  $('map-region').value=SITE_I;
  for(const id of ['legacy','m-speed','m-eta','m-down','m-sand']){const el=$(id);if(el){el.disabled=strictEva()||(id==='m-sand'&&!(SITE().stats.dune_km2>.01));if(strictEva())el.checked=false;}}
  $('map-evidence').hidden=SITE().id!=='jezero';$('map-event').hidden=SITE().id!=='jezero';$('map-event').disabled=!EVA?.ok&&!UI.blocked?.length;$('map-event').textContent=UI.blocked?.length?'Clear block':'Block test';
  $('pm').closest('.ctl').hidden=state.mode==='eva';
  if(state.mode==='eva')$('o2-hint').textContent=uiText('출발 총량의 20%를 복귀 잔량으로 확보 · Apollo 참고 가정','Keep 20% of initial oxygen on return · assumed Apollo reference');
  $('map-sites').title=uiText('탐사 지점','Sites');$('map-roadview').title=uiText('로드뷰','Roadview');$('map-settings').title=uiText('설정','Settings');
  $('map-out-label').textContent=uiText('가는 시간','Travel time');$('map-back-label').textContent=uiText('복귀 시간','Return');$('map-dwell-label').textContent=uiText('체류 가능','Time at site');$('map-plan-title').textContent=uiText('탐사 계획','Planning');
  $('map-plan-status').textContent=state.mode!=='eva'?uiText('상세 분석 모드','Advanced mode'):!sel.length?uiText('지점을 선택하세요','Select a site'):!e?uiText('계산 중','Calculating'):e.ok?uiText('모델 예측 · 관측 확인 필요','Ground coverage unverified'):e.msg;
  $('map-out').textContent=e?.ok?uiTime(e.outbound_s):'—';$('map-back').textContent=e?.ok?uiTime(e.return_s):'—';$('map-dwell').textContent=e?.ok?uiTime(e.dwell_total_s):'—';
  $('map-split').textContent=state.mode!=='eva'?uiText('기존 분석 정책 적용','Legacy analysis policy'):e?.ok&&sel.length===2?e.order.map(ti=>`${String.fromCharCode(65+sel.indexOf(ti))} ${uiTime(e.marks.find(m=>m.ti===ti).dwell_s)}`).join('  ·  '):uiText('복귀 후 산소 20% 확보 · 가정 기반','20% oxygen on return · assumed profile');
  $('map-chips').replaceChildren();sel.forEach((ti,j)=>{const b=document.createElement('button');b.textContent=`${String.fromCharCode(65+j)} · ${uiName(META.targets[ti])} ×`;b.title=uiName(META.targets[ti]);b.onclick=()=>uiSelect(ti);$('map-chips').append(b);});
  $('map-share-wrap').hidden=true;$('map-share').value=String(UI.share);$('map-share').disabled=!!f&&f.m>0;
  $('map-return').disabled=!e?.ok||!f||!['out','work'].includes(f.phase)||f.m===0;
  $('map-order').hidden=sel.length<2;$('map-order').textContent=e?.ok?e.order.map(ti=>String.fromCharCode(65+sel.indexOf(ti))).join('→'):'A↔B';
  $('map-play').disabled=!e?.ok||!SIM?.ok;$('map-play').textContent=playing?uiText('Ⅱ 정지','Ⅱ Pause'):uiText('▶ 출발','▶ Start');
  $('map-legend').hidden=state.mode!=='eva';$('map-evidence-label').textContent=uiText('관측 근거','Evidence');
  if(f){const prev=SIM.frames[Math.max(0,SIM.idx-1)];if(prev.pos!==f.pos)UI.heading=bearingTo(prev.pos,f.pos);if(UI.headingUp){UI.angle=-UI.heading;uiApplyZoom(false);}}
  if(e?.ok&&f&&f.m>0){const times=uiLiveTimes(f);$('map-out-label').textContent='Travel left';$('map-back-label').textContent=['out','work'].includes(f.phase)?'Return from site':'Return left';$('map-dwell-label').textContent='Stay left';$('map-out').textContent=uiTime(times.travel);$('map-back').textContent=uiTime(times.back);$('map-dwell').textContent=uiTime(times.stay);if(UI.liveEstimateKey===uiLiveKey(f)&&UI.liveEstimate?.ok&&sel.length===2)$('map-split').textContent=sel.map((ti,i)=>String.fromCharCode(65+i)+' '+uiTime(UI.liveEstimate.marks.find(m=>m.ti===ti)?.dwell_s??0)).join(' · ');if(!['out','work'].includes(f.phase))$('map-split').textContent='Survey ended';$('map-plan-status').textContent=({out:'On the way',work:'At site',back:'Returning',home:'At base',dead:'Return failed'})[f.phase];}
  if(f&&['out','work'].includes(f.phase)&&f.m>0&&UI.liveEstimateKey!==uiLiveKey(f))$('map-plan-status').textContent='Updating trip estimate…';
  uiScale();if(typeof uiPlanningControls==='function')uiPlanningControls();
}
function uiLiveTimes(f){
  if(["out","work"].includes(f.phase)){uiRequestLive(f);if(UI.liveEstimateKey===uiLiveKey(f)){const e=UI.liveEstimate;return e?.ok?{travel:e.outbound_s,back:e.return_s,stay:e.dwell_total_s}:{travel:NaN,back:uiTravelReturnSeconds(f.pos),stay:0};}return{travel:NaN,back:uiTravelReturnSeconds(f.pos),stay:NaN};}
  return{travel:0,back:['home','dead'].includes(f.phase)?0:(uiTravelReturnSeconds(f.pos)),stay:0};
}
function uiReturnNow(){
  const f=simFrame();if(!f||!['out','work'].includes(f.phase)||!pathToBase(f.pos)?.length)return;
  stopSim();const idx=SIM.idx,path=pathToBase(f.pos);SIM=buildSim(f.m);SIM.manualReturnPath=path;SIM.idx=Math.min(idx,SIM.frames.length-1);$('sim-t').max=SIM.frames.length-1;setSimIdx(SIM.idx);uiToast('Return route ready · press Start');uiPaint();
}
// Enumerate complete selections only. Weighted dwell shares one resource budget.
function uiPlanEva(snapshot=null){
  const sel=snapshot?.selected??evaSelected();if(!sel.length)return{msg:uiText('지점을 선택하세요','Select a site')};if(sel.length>3)return{msg:uiText('최대 3곳 선택','Select up to three sites')};
  const nodes=snapshot?[snapshot.pos,...sel.map(i=>tCell(META.targets[i])),state.base]:evaNodes(),home=snapshot?nodes.length-1:0,L=nodes.map(c=>uiTravelTree(LEGS.get(legKey(c)))),S=setNow();if(L.some(x=>!x)||!S)return{msg:'Calculating route…'};
  const indices=sel.map((_,i)=>i+1);
  const permutations=a=>a.length?a.flatMap((v,i)=>permutations(a.filter((_,j)=>i!==j)).map(p=>[v,...p])):[[]];
  const orders=snapshot?[indices]:UI.order==='forward'?[indices]:UI.order==='reverse'?[[...indices].reverse()]:permutations(indices);
  const requested=sel.map(i=>META.targets[i].planned_minutes??null);
  const manual=!snapshot&&requested.every(v=>v!==null);
  const requestedTotal=manual?requested.reduce((a,b)=>a+b,0)*60:0;
  const weights=snapshot?.weights??(manual&&requestedTotal>0?requested.map(v=>v*60/requestedTotal):sel.map(()=>1/sel.length));
  const leak=(state.simLeak||0)/3600;
  const qO=levelMR()*C.o2_g_per_j,k=snapshot?.k??state.k,qW=waterOf(qO,1,k,state.q),b=snapshot?{o2:snapshot.o2-O2RES(),water:snapshot.w-waterReserve(state.q)}:budgets(true),results=[],shortfalls=[];
  for(const order of orders){
    let usedO=0,time=0,dose=0,done=0,valid=true;const path=[],legs=[],marks=[],limits=[];
    const seq=[0,...order,home];
    for(let n=0;n<seq.length-1;n++){
      const src=seq[n],dst=seq[n+1],tree=L[src],target=nodes[dst];
      if(!Number.isFinite(tree.o2[target])){valid=false;break;}
      const P=legPath(tree,target);
      for(const cell of P){
        if(!(FLAGS[cell]&1)||S.o2[cell]<0){valid=false;break;}
        const po=usedO+tree.o2[cell]+S.o2[cell],pt=time+tree.t[cell]+S.t[cell],fraction=done;
        limits.push({resource:'o2',budget:b.o2,used:k*po+leak*pt,rate:(k*qO+leak)*fraction});
        limits.push({resource:'water',budget:b.water,used:waterOf(po,pt,k,state.q),rate:qW*fraction});
        limits.push({resource:'dose',budget:C.dose_budget_msv-(snapshot?.dose??0),used:multNow()*(dose+tree.dose[cell]+S.dose[cell]),rate:multNow()*marks.reduce((v,m)=>v+RATE1[nodes[m.node]]/3600*weights[m.node-1],0)});
      }
      if(!valid)break;
      usedO+=tree.o2[target];time+=tree.t[target];dose+=tree.dose[target];
      path.push(...(path.length?P.slice(1):P));legs.push({path:P,t:tree.t[target],o2:tree.o2[target]});
      if(dst!==home){done+=weights[dst-1];marks.push({ti:sel[dst-1],node:dst,arrive:time,o2:usedO});
        limits.push({resource:'o2',budget:b.o2,used:k*(usedO+S.o2[target])+leak*(time+S.t[target]),rate:(k*qO+leak)*done},{resource:'water',budget:b.water,used:waterOf(usedO+S.o2[target],time+S.t[target],k,state.q),rate:qW*done});
      }
    }
    if(!valid)continue;
    limits.push({resource:'o2',budget:b.o2,used:k*usedO+leak*time,rate:k*qO+leak},{resource:'water',budget:b.water,used:waterOf(usedO,time,k,state.q),rate:qW});
    const dwell=MapUIRules.dwellLimit(limits);
    if(!snapshot){
      const stay=manual?requestedTotal:0;
      const peak=kind=>Math.max(0,...limits.filter(l=>l.resource===kind).map(l=>l.used+l.rate*stay));
      const oxygen=peak('o2')/.8,water=peak('water')+waterReserve(state.q),doseExcess=Math.max(0,peak('dose')-C.dose_budget_msv);
      shortfalls.push({path:[...path],oxygen,water,doseExcess,extraOxygen:Math.max(0,oxygen-state.o2),extraWater:Math.max(0,water-state.water*1000),travel:time,stay});
    }
    if(dwell===null)continue;
    // Whole minutes per stop fit the existing minute-step simulation without rounding up.
    if(manual&&requestedTotal>dwell+1e-6)continue;
    const allocated=manual?requested.map(v=>v*60):weights.map(w=>Math.floor(dwell*w/60)*60),total=allocated.reduce((a,b)=>a+b,0),perStop=total/sel.length;
    let elapsedStay=0;marks.forEach(m=>{m.arrive+=elapsedStay;m.dwell_s=allocated[m.node-1];elapsedStay+=m.dwell_s;m.o2+=elapsedStay*qO;});
    results.push({ok:true,path,marks,order:order.map(j=>sel[j-1]),dropped:[],metabolic_o2:usedO+total*qO,oxygen_g:k*(usedO+total*qO)+leak*(time+total),o2:usedO+total*qO+leak*(time+total)/k,t:time+total,dose:dose+marks.reduce((v,m)=>v+RATE1[nodes[m.node]]*m.dwell_s/3600,0),minM:b.o2-k*(usedO+total*qO)-leak*(time+total),minAt:state.base,cls:3,outbound_s:legs.slice(0,-1).reduce((v,l)=>v+l.t,0),return_s:legs.at(-1).t,dwell_total_s:total,dwell_per_stop_s:perStop});
  }
  results.sort((a,b)=>b.dwell_total_s-a.dwell_total_s||a.o2-b.o2||a.t-b.t);
  shortfalls.sort((a,b)=>a.extraOxygen-b.extraOxygen||a.extraWater-b.extraWater||a.travel-b.travel);
  return results[0]||{ok:false,resourceCandidate:shortfalls[0],msg:uiText('선택 경로 예산 부족','No feasible candidate route')};
}
function uiPaintZones(){
  if(state.mode!=='eva'||state.showmr||state.showtir){uiHideOuterRadius();return false;}const S=setNow(),f=simFrame(),source=f?.pos??state.base;
  // Use only a forward tree from the actual position; never relabel base coverage as live coverage.
  const key=`${SITE_I}:${legKey(source)}`;
  const F=uiRadiusLive()?uiRadiusZeroForward():LEGS.get(legKey(source))||(UI.liveTree?.key===legKey(source)?UI.liveTree.tree:null)||(UI.zoneKey===key?UI.zoneTree:null);
  if(!S){uiHideOuterRadius(true);return false;}
  if(!F){
    uiHideOuterRadius(true);
    // One in-flight job at a time; stale results never paint a newer position/site.
    if(!UI.zonePending){UI.zonePending=true;const generation=siteGeneration,model=modelKey();wkDijkstra(source,false,state.nofall).then(tree=>{
      if(generation===siteGeneration&&model===modelKey()){UI.zoneKey=key;UI.zoneTree=tree;}
    }).catch(()=>{}).finally(()=>{UI.zonePending=false;if(state.mode==='eva')paintCells();});}
    if(uiRadiusCanRetain())return true;
    for(let i=0;i<N;i++)px[i]=(FLAGS[i]&1)&&((i%W+(i/W|0))%6<2)?rgba('#8c969d',.18):0;
    cctx.putImageData(img,0,0);return true;
  }
  const colors={red:rgba('#dc725e',.42),yellow:rgba('#e6bd5b',.40),blue:rgba('#238fff',.58)},unknown=rgba('#8c969d',.18);
  for(let i=0;i<N;i++){
    if(!(FLAGS[i]&1)){px[i]=0;continue;}
    const o=F.o2[i]+S.o2[i],t=F.t[i]+S.t[i];
    if(S.o2[i]<0||!Number.isFinite(o)){px[i]=((i%W+(i/W|0))%6<2)?unknown:0;continue;}
    const r=(EO2()-EK()*o-(state.simLeak||0)/3600*t)/state.o2;let c=colors[MapUIRules.zone(r)]||unknown;
    if(waterOf(o,t,EK(),state.q)>budgets().water&&((i%W+(i/W|0))%6<2))c=unknown;
    px[i]=c;
  }
  uiRadiusOverlay(F,S);cctx.putImageData(img,0,0);return true;
}

function uiRotateBy(degrees) {
  const v=uiView(),cx=wrap.clientWidth/2,cy=wrap.clientHeight/2,p=MapUIRules.unproject(cx,cy,v);
  UI.headingUp=false;UI.angle+=degrees;
  const q=MapUIRules.project(p.x,p.y,{...v,angle:UI.angle});ZX+=cx-q.x;ZY+=cy-q.y;applyZoom();uiMarkers();
}
function uiNorthUp() { const p=simFrame()?.pos??state.base;UI.headingUp=false;UI.angle=-bearingTo(p,uiNavigationTarget(p))*Math.PI/180;uiCenter(p);uiMarkers(); }
function uiGestures() {
  const points=new Map();let start=null;
  const local=e=>{const r=wrap.getBoundingClientRect();return{x:e.clientX-r.left,y:e.clientY-r.top};};
  const restart=rotate=>{start={points:[...points.values()].map(p=>({...p})),view:uiView(),rotate};};
  stage.addEventListener('pointerdown',e=>{
    if(e.button!==0)return;e.preventDefault();points.set(e.pointerId,local(e));
    stage.setPointerCapture(e.pointerId);if(points.size===1)dragMoved=false;
    else dragMoved=true;
    restart(e.shiftKey);
  });
  stage.addEventListener('pointermove',e=>{
    if(!points.has(e.pointerId)||!start)return;points.set(e.pointerId,local(e));const next=[...points.values()];
    if(points.size>=2 && start.points.length>=2){
      const v=MapUIRules.gesture(start.points,next,start.view);ZK=v.k;UI.angle=v.angle;ZX=v.cx-wrap.clientWidth/2;ZY=v.cy-wrap.clientHeight/2;dragMoved=true;
    }else{
      const dx=next[0].x-start.points[0].x,dy=next[0].y-start.points[0].y;
      if(!dragMoved&&Math.hypot(dx,dy)<4)return;dragMoved=true;
      if(start.rotate){
        const cx=wrap.clientWidth/2,cy=wrap.clientHeight/2,anchor=MapUIRules.unproject(cx,cy,start.view);
        UI.angle=start.view.angle+dx*.4;const q=MapUIRules.project(anchor.x,anchor.y,{...start.view,angle:UI.angle});
        ZX=start.view.cx-wrap.clientWidth/2+cx-q.x;ZY=start.view.cy-wrap.clientHeight/2+cy-q.y;
      }else{ZX=start.view.cx-wrap.clientWidth/2+dx;ZY=start.view.cy-wrap.clientHeight/2+dy;}
    }
    UI.headingUp=false;stage.classList.add('grab');uiApplyZoom(false);uiMarkers();
  });
  const end=e=>{points.delete(e.pointerId);if(points.size)restart(false);else{start=null;stage.classList.remove('grab');drawVec();}};
  stage.addEventListener('pointerup',end);stage.addEventListener('pointercancel',end);
  stage.addEventListener('lostpointercapture',e=>{if(points.has(e.pointerId))end(e);});
}
const UI_ICONS={
  user:'<svg viewBox="0 0 40 40" aria-hidden="true"><circle cx="20" cy="20" r="15" fill="#2285ec" stroke="white" stroke-width="3"/><path d="M20 5L28 29L20 24L12 29Z" fill="white" stroke="#124d85" stroke-width="1.5"/></svg>',
  base:'<svg viewBox="0 0 40 40" aria-hidden="true"><path d="M7 21L20 9L33 21V34H7Z" fill="#183d35" stroke="#b2f4d8" stroke-width="2.5"/><path d="M16 34V24H24V34M20 9V3H29L25 7H20" fill="none" stroke="#b2f4d8" stroke-width="2.5"/></svg>',
  target:'<svg viewBox="0 0 40 48" aria-hidden="true"><path d="M20 46C16 38 4 27 4 18A16 16 0 0136 18C36 27 24 38 20 46Z" fill="#df895d" stroke="#fff1df" stroke-width="2"/><path d="M15 29V10H27L24 15L27 20H15" fill="#203039" stroke="#203039" stroke-width="2" stroke-linejoin="round"/></svg>'
};
function uiMarkers(live) { if(live)UI.livePose={...live,site:SITE_I};
  if(!H||!UI.screen)return;
  let layer=$('map-markers');
  if(!layer){layer=document.createElement('div');layer.id='map-markers';layer.className='map-markers';wrap.append(layer);}
  layer.hidden=false;
  const key=String(SITE_I)+':'+(META.targets||[]).length;
  if(layer.dataset.site!==key){
    layer.dataset.site=key;layer.innerHTML='<div id="map-base-pin" class="map-location base">'+UI_ICONS.base+'<span>BASE</span></div><div id="map-user-pin" class="map-location current">'+UI_ICONS.user+'<span>YOU</span></div>';
    (META.targets||[]).forEach((t,i)=>{const b=document.createElement('button');b.className='map-target-pin';b.dataset.poi=i;b.innerHTML=UI_ICONS.target+'<span></span>';b.title='Survey site: '+uiName(t);b.setAttribute('aria-label','Survey site: '+uiName(t));b.onclick=()=>uiOpenPoi(i);layer.append(b);});
  }
  const place=(el,x,y)=>{const v=UI.screen,p=MapUIRules.project(x/W*v.w,y/R*v.h,v);el.style.left=p.x+'px';el.style.top=p.y+'px';el.hidden=p.x < -40 || p.x > wrap.clientWidth+40 || p.y < -60 || p.y > wrap.clientHeight+60;};
  place($('map-base-pin'),state.base%W+.5,(state.base/W|0)+.5);uiBaseIcon();
  const f=simFrame(),pos=f?.pos??state.base;
  const x=live?.x??pos%W+.5,y=live?.y??(pos/W|0)+.5;
  UI.livePos=Math.min(N-1,Math.max(0,Math.floor(y)*W+Math.floor(x)));
  place($('map-user-pin'),x,y);
  $('map-user-pin').querySelector('svg').style.transform='rotate('+(UI.heading+UI.angle)+'deg)';
  layer.querySelectorAll('.map-block-pin').forEach(e=>e.remove());
  for(const c of UI.blocked||[]){const el=document.createElement('div');el.className='map-block-pin';el.textContent='×';el.title='Synthetic blocked cell';layer.append(el);place(el,c%W+.5,(c/W|0)+.5);}
  const sel=evaSelected();
  layer.querySelectorAll('.map-target-pin').forEach(b=>{const i=Number(b.dataset.poi),t=META.targets[i],n=sel.indexOf(i);place(b,t.x,t.y);b.classList.toggle('selected',n>=0);b.querySelector('span').textContent=n>=0?String.fromCharCode(65+n):'SITE '+(i+1);b.classList.remove('clustered');});
  uiClusterPins(layer,sel);uiDestinationDeletePins(layer);
}
// Pins whose tips are closer than one pin width on screen cover each other, so only the top one
// could be clicked. Replace such groups with one button that lists the members (screen space, so
// zooming in splits the group again). Positions and data are unchanged.
const UI_PIN_CLUSTER_PX=40;
function uiClusterPinsLegacy(layer,sel){
  layer.querySelectorAll('.map-pin-cluster').forEach(e=>e.remove());
  const pins=[...layer.querySelectorAll('.map-target-pin')].filter(b=>!b.hidden).map(b=>({b,i:Number(b.dataset.poi),x:parseFloat(b.style.left),y:parseFloat(b.style.top)}));
  const groups=[];
  for(const p of pins){const g=groups.find(g=>g.some(q=>Math.hypot(q.x-p.x,q.y-p.y)<UI_PIN_CLUSTER_PX));if(g)g.push(p);else groups.push([p]);}
  for(let merged=true;merged;){merged=false;for(let a=0;a<groups.length&&!merged;a++)for(let c=a+1;c<groups.length&&!merged;c++)if(groups[a].some(p=>groups[c].some(q=>Math.hypot(q.x-p.x,q.y-p.y)<UI_PIN_CLUSTER_PX))){groups[a].push(...groups.splice(c,1)[0]);merged=true;}}
  for(const g of groups){
    if(g.length<2)continue;
    const ids=g.map(p=>p.i).sort((a,b)=>a-b),names=ids.map(i=>uiName(META.targets[i])),letters=ids.map(i=>sel.indexOf(i)).filter(n=>n>=0).map(n=>String.fromCharCode(65+n));
    g.forEach(p=>p.b.classList.add('clustered'));
    const c=document.createElement('button');c.className='map-pin-cluster'+(letters.length?' selected':'');c.dataset.members=ids.join(',');
    c.innerHTML=UI_ICONS.target+'<span></span>';c.querySelector('span').textContent=uiText('묶음 ','Group ')+ids.map(i=>i+1).join(', ');
    c.title=c.ariaLabel=ids.length+' overlapping sites: '+names.join(', ');c.setAttribute('aria-label',c.title);
    c.style.left=g.reduce((s,p)=>s+p.x,0)/g.length+'px';c.style.top=g.reduce((s,p)=>s+p.y,0)/g.length+'px';
    c.onclick=()=>{$('map-poi').hidden=true;$('map-catalog').hidden=false;uiCatalog(ids);$('map-catalog').querySelector('button')?.focus();};
    layer.append(c);
  }
}
function uiPhotoAt(pos,heading) {
  const x=pos%W+.5,y=(pos/W|0)+.5;
  const photos=(META.photos||[]).filter(p=>p.full_img||p.img).map(p=>({...p,distance:Math.hypot(p.x-x,p.y-y)*CELL}));
  photos.sort((a,b)=>a.distance-b.distance);
  const nearest=photos[0];
  const stations=(META.roadview||[]).map(s=>({...s,distance:Math.hypot(s.x-x,s.y-y)*CELL})).sort((a,b)=>a.distance-b.distance);
  const st=stations[0];
  // Prefer a nearby directional frame only when it is materially closer than the full-size image.
  if(st&&(!nearest||st.distance+100<nearest.distance)){
    const frames=st.frames.filter(f=>f.img&&Number.isFinite(f.az)).sort((a,b)=>Math.abs(MapUIRules.angleDelta(a.az,heading))-Math.abs(MapUIRules.angleDelta(b.az,heading)));
    if(frames[0])return{...st,img:frames[0].img,az:frames[0].az,source:'Directional rover photo'};
  }
  return nearest?{...nearest,img:nearest.full_img||nearest.img,source:'Nearest rover photo',az:null}:null;
}
function uiPhotoVisorLegacy(doc,pos,heading) {
  const el=doc.getElementById('visor'),photo=uiPhotoAt(pos,heading);
  doc.getElementById('map-visor-ground')?.remove();
  let image=doc.getElementById('map-visor-photo');
  if(!image){image=doc.createElement('img');image.id='map-visor-photo';image.className='map-visor-photo';el.prepend(image);}
  el.style.backgroundImage='none';
  if(photo){const key=SITE_I+':'+(photo.full_source_url||photo.url||'')+':'+photo.sol+':'+photo.az;if(image.dataset.photoKey!==key){image.src=photo.img;image.dataset.photoKey=key;}image.alt=(photo.rover||'Rover')+' surface observation, sol '+photo.sol;image.hidden=false;}
  else{image.hidden=true;image.removeAttribute('src');delete image.dataset.photoKey;}
  const hud=doc.getElementById('hud'),e=EVA,f=simFrame(),live=e?.ok&&f&&f.m>0?uiLiveTimes(f):null;
  const phases={out:'On the way',work:'At site',back:'Returning',home:'At base',dead:'Return failed'};
  if(state.mode==='eva')hud.innerHTML='<div class="map-visor-label">'+(photo?'ROVER PHOTO':'NO PHOTO AVAILABLE')+' · '+Math.round(heading)+'°</div><div class="c tl"><span>Travel time</span><span class="v">'+(e?.ok?uiTime(live?live.travel:e.outbound_s):'—')+'</span></div><div class="c tr"><span>Return time</span><span class="v">'+(e?.ok?uiTime(live?live.back:e.return_s):'—')+'</span></div><div class="c bl"><span>Stay left</span><span class="v">'+(e?.ok?uiTime(live?live.stay:e.dwell_total_s):'—')+'</span></div><div class="c br"><span>'+(f?f.m+' min · '+(phases[f.phase]||'Ready'):'Ready')+'</span></div>';
  const cap=doc.getElementById('visor-cap');
  cap.textContent=photo?(photo.rover||'Rover')+' · Sol '+photo.sol+' · '+(photo.distance<1000?Math.round(photo.distance)+' m':(photo.distance/1000).toFixed(2)+' km')+' from your position · '+(photo.az!==null?'Camera '+Math.round(photo.az)+'°':'Camera direction not verified')+' · NASA/JPL-Caltech':'No rover photo is available for this region.';
  cap.title='Real rover observation selected by location. This is not a continuous or precisely registered view from the explorer.';
}
uiMount();
uiGestures();

function uiWorldFlatLegacy(){
  stopSim();let dialog=$('map-world-dialog');
  if(!dialog){dialog=document.createElement('dialog');dialog.id='map-world-dialog';dialog.className='map-world-dialog';document.body.append(dialog);
    const world=SITE_LIST[0].meta.world;
    dialog.innerHTML='<header><b>MARS / EXPLORE A REGION</b><button id="map-world-close" aria-label="Close Mars map">×</button></header><div class="map-world-canvas"><img alt="Mars global MOLA shaded relief"/><div id="map-world-pins"></div></div><nav id="map-world-regions"></nav><small></small>';
    const worldImg=dialog.querySelector('img');worldImg.src=world.image;worldImg.draggable=false;worldImg.addEventListener('dragstart',e=>e.preventDefault());
    const canvas=dialog.querySelector('.map-world-canvas'),viewport=document.createElement('div');viewport.className='map-world-viewport';canvas.before(viewport);viewport.append(canvas);
    const controls=document.createElement('div');controls.innerHTML='<button data-z="2" aria-label="Zoom global map in">+</button> <button data-z="0.5" aria-label="Zoom global map out">−</button> <span>Offline overview · select a location</span>';viewport.after(controls);
    let zoom=1,dx=0,dy=0,drag=null,moved=false;const draw=()=>{canvas.style.transform='translate('+dx+'px,'+dy+'px) scale('+zoom+')';canvas.style.setProperty('--wz',String(zoom));};
    controls.querySelectorAll('button').forEach(b=>b.onclick=()=>{zoom=Math.max(1,Math.min(8,zoom*Number(b.dataset.z)));draw();});
    viewport.onpointerdown=e=>{if(e.target.closest('button'))return;e.preventDefault();drag={x:e.clientX,y:e.clientY,dx,dy};moved=false;viewport.setPointerCapture(e.pointerId);};
    viewport.onpointermove=e=>{if(!drag)return;const x=e.clientX-drag.x,y=e.clientY-drag.y;if(Math.hypot(x,y)>4)moved=true;dx=drag.dx+x;dy=drag.dy+y;draw();};
    viewport.onpointerup=e=>{if(!drag)return;drag=null;if(moved)return;const r=canvas.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)return;const p=MapUIRules.overviewToLonLat(e.clientX-r.left,e.clientY-r.top,r.width,r.height);controls.querySelector('span').textContent=p.lat.toFixed(3)+'° N, '+p.lon.toFixed(3)+'° E · Detail data not checked';};viewport.onpointercancel=()=>drag=null;
dialog.querySelector('small').textContent=world.source+' · Overview only';
    const open=i=>{dialog.close();loadSite(i);};
    const statusWord={packaged:'included',catalog_only:'listed only',not_checked:'not checked',not_applicable:'n/a'};
    SITE_LIST.forEach((s,i)=>{const b=document.createElement('button');b.className='map-world-region';const name=document.createElement('b');name.textContent=s.meta.site.short.replace('(가상 거점)','(virtual base)');b.append(name);b.onclick=()=>open(i);const info=world.catalog?.regions.find(r=>r.id===s.meta.site.id);
      // Readable on touch screens: no hover needed. "included" means packaged in this file, not verified.
      if(info){const st=document.createElement('small');st.textContent='Terrain + map · Photos: '+(statusWord[info.data.ground_images.status]||info.data.ground_images.status)+' · 3D: '+(info.data.local_reconstruction.status==='packaged'?'local only':(statusWord[info.data.local_reconstruction.status]||info.data.local_reconstruction.status));b.append(st);}
      b.title=info?'Elevation + orbital map · ground photos: '+info.data.ground_images.status+' · local geometry: '+info.data.local_reconstruction.status:'';dialog.querySelector('nav').append(b);const pin=world.pins.find(p=>p.id===s.meta.site.id);if(pin){const p=document.createElement('button');p.className='map-world-pin';p.style.left=(pin.lon+180)/360*100+'%';p.style.top=(90-pin.lat)/180*100+'%';p.textContent=({jezero:'Jezero',gale:'Gale',aram:'Aram'})[s.meta.site.id]||s.meta.site.id;p.title=pin.kind==='dtm_grid_centre'?'Centre of the analysed DTM area (HiRISE label)':'Landing site';p.onclick=()=>open(i);$('map-world-pins').append(p);}});
    $('map-world-close').onclick=()=>dialog.close();
  }
  dialog.showModal();
}

function uiEvidence(){
  const m=META.localTerrain;if(!m){uiToast('No local reconstruction available');return;}
  let d=$('map-evidence-dialog');if(!d){d=document.createElement('dialog');d.id='map-evidence-dialog';d.className='map-world-dialog';document.body.append(d);}
  d.replaceChildren();const head=document.createElement('header'),title=document.createElement('b'),close=document.createElement('button');title.textContent='LOCAL OBSERVATIONS / SOL 443';close.textContent='×';close.setAttribute('aria-label','Close observations');close.onclick=()=>d.close();head.append(title,close);d.append(head);
  const img=document.createElement('img');img.src=m.preview;img.alt='Common-frame PDS mesh vertex composite';img.style.cssText='width:min(100%,640px);display:block;margin:auto';d.append(img);
  const note=document.createElement('p');note.textContent=m.quality.source_mesh_count+' PDS meshes · '+m.quality.source_vertex_count.toLocaleString()+' source vertices · '+m.frame_id+' · Local coordinates only';d.append(note);
  const warning=document.createElement('p');warning.textContent='Orbital registration: three independent attempts (terrain shape, image texture, rover tracks) did not pass, so these points stay in local coordinates. No verified ground-coverage cells. This composite does not change route safety.';d.append(warning);
  const details=document.createElement('details'),summary=document.createElement('summary');summary.textContent='Products and provenance';details.append(summary);for(const p of m.source_products){const a=document.createElement('a');a.href=p.url;a.textContent=p.filename;a.target='_blank';a.rel='noopener';a.style.display='block';details.append(a);}d.append(details);d.showModal();
}
// H7: one place listing every data provider, its credit line and the rights basis (code/credits.json).
function uiCreditProducts(){
  const m=/DTEEC_(\d{6}_\d{4})_(\d{6}_\d{4})_(\w\d\d)/.exec(META.site?.source||'');if(!m)return[];
  const dir='https://hirise-pds.lpl.arizona.edu/PDS/DTM/ESP/ORB_'+m[1].slice(0,4)+'00_'+m[1].slice(0,4)+'99/ESP_'+m[1]+'_ESP_'+m[2]+'/';
  const dtm='DTEEC_'+m[1]+'_'+m[2]+'_'+m[3];
  return[{name:dtm+' (terrain model)',url:dir+dtm+'.IMG'},{name:'ESP_'+m[1]+'_RED_C (orthoimage)',url:dir+'ESP_'+m[1]+'_RED_C_01_ORTHO.JP2'}];
}
function uiCredits(){
  const C=typeof UI_CREDITS==='object'?UI_CREDITS:null;if(!C)return;
  let d=$('map-credits-dialog');if(!d){d=document.createElement('dialog');d.id='map-credits-dialog';d.className='map-world-dialog';d.setAttribute('aria-label','Sources and credits');document.body.append(d);}
  d.replaceChildren();
  const el=(tag,text,cls)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;if(cls)e.className=cls;return e;};
  const link=(href,text)=>{const a=el('a',text);a.href=href;a.target='_blank';a.rel='noopener';return a;};
  const head=el('header'),close=el('button','×');close.setAttribute('aria-label','Close credits');close.onclick=()=>d.close();head.append(el('b','SOURCES AND CREDITS'),close);d.append(head);
  d.append(el('p',C.disclaimer,'map-credit-disclaimer'));
  const photos=(META.photos||[]).length,rv=(META.roadview||[]).reduce((n,s)=>n+(s.frames||[]).filter(f=>f.img).length,0);
  const nasa=[photos+' rover photo'+(photos===1?'':'s'),rv?rv+' roadview strips':'',META.localTerrain?'Navcam mesh preview':'',META.traverse?.length?'rover traverse':'',META.targets?.length?'site records':''].filter(Boolean).join(', ');
  const used={hirise:'This region: terrain model, orthoimage and hillshade.',nasa_jpl:'This region: '+nasa+'.',themis:'Night-IR layer resampled to each region.',trek_mola:'Global overview: 32 tiles at zoom 2.',ofl:'Embedded Latin subsets for the interface.',project:'Planner, simulation and interface code.'};
  const list=el('div',null,'map-credit-list');
  for(const [id,r] of Object.entries(C.rights)){
    const box=el('section');box.dataset.rights=id;box.append(el('b',r.label),el('p','Credit: '+r.credit),el('p',used[id]||''),el('p',r.basis,'map-credit-basis'));
    if(r.status==='needs_confirmation')box.append(el('p','Reuse terms not yet confirmed with the provider.','map-credit-flag'));
    if(r.status==='owner_decision')box.append(el('p','Licence not chosen yet.','map-credit-flag'));
    if(r.url)box.append(link(r.url,'Policy: '+r.url.replace(/^https:\/\//,'')));
    if(id==='hirise')for(const p of uiCreditProducts())box.append(link(p.url,p.name));
    list.append(box);
  }
  d.append(list,el('p','Policies checked '+C.checked+'. Full asset list: asset-provenance.csv in the review package.','map-credit-basis'));
  d.showModal();close.focus();
}
function uiBlockTest(){
  if(SITE().id!=='jezero'||(!EVA?.ok&&!UI.blocked?.length))return;
  stopSim();
  if(UI.blocked?.length){FLAGS.set(UI.originalFlags);UI.blocked=[];UI.originalFlags=null;}
  else{const protectedCells=new Set([state.base,...evaSelected().map(i=>tCell(META.targets[i]))]);const candidates=EVA.path.filter(c=>!protectedCells.has(c));if(!candidates.length)return;const center=candidates[Math.floor(candidates.length/3)];UI.originalFlags=FLAGS.slice();UI.blocked=[];for(let y=-1;y<=1;y++)for(let x=-1;x<=1;x++){const xx=center%W+x,yy=(center/W|0)+y,c=yy*W+xx;if(xx>=0&&xx<W&&yy>=0&&yy<R&&!protectedCells.has(c)){FLAGS[c]&=~8;UI.blocked.push(c);}}}
  overlayRevision++;ETGEN++;TREES.clear();LEGS.clear();INFLIGHT.clear();DESC.clear();FWD=REV=FWDB=null;MO=null;MO_KEY='';LMR=null;LMR_KEY='';UI.zoneTree=null;UI.zoneKey=null;wkStart();uiInvalidate();uiToast(UI.blocked.length?'Synthetic block applied · route recalculated':'Original terrain restored');
}

function uiLiveKey(f){return [siteGeneration,modelKey(),EVASIG,f.m,f.pos,f.o2,f.w,f.k,f.dose].join(':');}
function uiRequestLive(f){
  const key=uiLiveKey(f);if(UI.liveEstimateKey===key||UI.livePending===key)return;if(UI.livePending)return;
  const start=Math.max(0,(f.stop_index||0)-(f.phase==='work'?1:0)),selected=EVA.order.slice(start);if(!selected.length)return;
  const original=evaSelected(),ratio=(UI.share??50)/100,raw=selected.map(i=>(EVA.marks.find(m=>m.ti===i)?.dwell_s||1)),sum=raw.reduce((a,b)=>a+b,0);
  const snapshot={...f,selected,weights:raw.map(v=>v/sum)},generation=siteGeneration,model=modelKey(),lk=legKey(f.pos);UI.livePending=key;
  const source=LEGS.get(lk)||(UI.liveTree?.key===lk?UI.liveTree.tree:null);Promise.resolve(source||wkDijkstra(f.pos,false,state.nofall)).then(tree=>{
    if(generation!==siteGeneration||model!==modelKey())return;const existing=LEGS.get(lk);UI.liveTree={key:lk,tree};LEGS.set(lk,tree);
    let result;try{result=uiPlanEva(snapshot);}finally{if(!existing)LEGS.delete(lk);}if(simFrame()&&uiLiveKey(simFrame())===key){UI.liveEstimate=result;UI.liveEstimateKey=key;}
  }).catch(()=>{if(generation===siteGeneration&&simFrame()&&uiLiveKey(simFrame())===key){UI.liveEstimate={ok:false,msg:'Estimate unavailable'};UI.liveEstimateKey=key;}}).finally(()=>{if(UI.livePending===key)UI.livePending=null;if(generation===siteGeneration){uiPaint();if(state.hud)renderHud();}});
}

