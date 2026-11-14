function uiDeleteDestination(i){
  if(META.targets[i]?.source_kind!=='user_target')return;
  META.targets.splice(i,1);state.evaSel.splice(i,1);
  UI.poi=-1;$('map-poi').hidden=true;$('map-catalog').hidden=true;
  if($('map-markers'))$('map-markers').dataset.site='';
  if($('custom-planning'))$('custom-planning').dataset.key='';
  uiInvalidate();uiMarkers();uiPlanningControls();
}
function uiDestinationDeletePins(layer){
  const wanted=new Set();
  layer.querySelectorAll('.map-target-pin').forEach(pin=>{
    const i=Number(pin.dataset.poi);
    if(META.targets[i]?.source_kind!=='user_target')return;
    wanted.add(String(i));
    let button=layer.querySelector(`[data-delete-destination="${i}"]`);
    if(!button){
      button=document.createElement('button');button.dataset.deleteDestination=String(i);button.className='destination-delete-pin';button.textContent='×';
      button.onpointerdown=e=>e.stopPropagation();
      button.onclick=e=>{e.preventDefault();e.stopPropagation();uiDeleteDestination(i);};layer.append(button);
    }
    button.title=uiText('목표 삭제','Delete destination');button.setAttribute('aria-label',button.title+' '+uiName(META.targets[i]));
    button.style.left=pin.style.left;button.style.top=pin.style.top;
    button.hidden=pin.hidden;
  });
  layer.querySelectorAll('[data-delete-destination]').forEach(b=>{if(!wanted.has(b.dataset.deleteDestination))b.remove();});
}
function uiPlanningControls(){
  const panel=$('custom-planning');if(!panel)return;
  uiResourceShortfall(panel);
  const selected=evaSelected(),key=SITE_I+':'+selected.join(',');
  if(panel.dataset.key===key)return;panel.dataset.key=key;
  const rows=panel.querySelector('.target-rows');rows.replaceChildren();
  selected.forEach((i,n)=>{
    const t=META.targets[i],row=document.createElement('label');
    row.textContent=String.fromCharCode(65+n)+' ';
    const input=document.createElement('input');input.type='number';input.min='0';input.max='1440';input.step='1';input.placeholder='Auto';input.value=t.planned_minutes??'';
    input.setAttribute('aria-label',uiName(t)+' stay (min)');
    input.onchange=()=>{if(!input.checkValidity()){input.reportValidity();return;}t.planned_minutes=input.value===''?null:Number(input.value);uiInvalidate();};
    row.append(input,document.createTextNode(' min'));
    const remove=document.createElement('button');remove.textContent='×';remove.title=t.source_kind==='user_target'?uiText('목표 삭제','Delete destination'):uiText('경로에서 제외','Remove from route');remove.setAttribute('aria-label',remove.title);remove.onclick=()=>{if(t.source_kind==='user_target')uiDeleteDestination(i);else{state.evaSel[i]=false;uiInvalidate();}};row.append(remove);rows.append(row);
  });
}
function uiResourceShortfall(panel){
  let box=$('route-resources');if(!box){box=document.createElement('div');box.id='route-resources';box.style.cssText='width:100%;font-size:12px;color:#ffc897';panel.append(box);}
  const r=EVA?.resourceCandidate;box.hidden=!r;if(!r)return;
  box.textContent=uiText('현재','Current')+`: O₂ ${Math.round(state.o2)} g / H₂O ${Math.round(state.water*1000)} g · `+
    uiText('추가 필요','Extra needed')+`: O₂ +${Math.ceil(r.extraOxygen)} g / H₂O +${Math.ceil(r.extraWater)} g · `+
    uiText('이동','Travel')+` ${Math.ceil(r.travel/60)} min · `+uiText('체류','Stay')+` ${Math.round(r.stay/60)} min`+
    (r.doseExcess>0?' · '+uiText('방사선 한도 초과 — 자원 추가만으로 해결 불가','Radiation limit exceeded — extra supplies alone are insufficient'):'');
  box.title=uiText('산소 20% 귀환 예비량과 기존 냉각수 예비량 포함. 자동 체류 계획은 체류 0분 기준 최소 추가량.','Includes 20% return oxygen and existing coolant reserve. Auto stay uses zero dwell for the minimum extra supply estimate.');
}
(() => {
  const panel=document.createElement('div');panel.id='custom-planning';panel.innerHTML='<span class="target-rows"></span><small>Stay: blank = auto · fill all stops for a fixed plan</small>';
  panel.style.cssText='display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:8px 0';
  document.querySelector('.map-bottom').append(panel);
  const deleteStyle=document.createElement('style');deleteStyle.textContent='.destination-delete-pin{position:absolute;transform:translate(14px,-54px);width:22px;height:22px;padding:0;line-height:18px;border:1px solid #ffb7a4;border-radius:50%;background:#442a28;color:white;font-size:18px;pointer-events:auto;cursor:pointer;z-index:9}.destination-delete-pin[hidden]{display:none}.destination-delete-pin:focus-visible{outline:2px solid white;outline-offset:2px}';document.head.append(deleteStyle);
  const compare=document.createElement('details');compare.innerHTML='<summary>Compare routes</summary><div></div>';panel.append(compare);
  compare.addEventListener('toggle',()=>{
    if(!compare.open)return;
    const out=compare.querySelector('div');out.replaceChildren();
    const selected=evaSelected(),saved=state.evaSel.slice();
    for(let mask=1;mask<(1<<selected.length);mask++){
      const subset=selected.filter((_,j)=>mask&(1<<j));let result;
      try{state.evaSel=saved.map((_,i)=>subset.includes(i));result=uiPlanEva();}finally{state.evaSel=saved;}
      const b=document.createElement('button');
      b.textContent=selected.map((i,j)=>subset.includes(i)?String.fromCharCode(65+j):'').join('+')+' · '+(result.ok?Math.floor(result.t/60)+' min / stay '+Math.floor(result.dwell_total_s/60)+' min':result.msg);
      b.onclick=()=>{state.evaSel=saved.map((_,i)=>subset.includes(i));compare.open=false;uiInvalidate();};out.append(b);
    }
  });
  const style=document.createElement('style');style.textContent='#custom-planning input{width:55px;background:#263139;color:white;border:1px solid #ffffff30;border-radius:5px;padding:4px}.target-rows{display:flex;gap:8px;flex-wrap:wrap}#custom-planning small{font-size:10px;color:#a7b6bd}#custom-planning button{background:#263139;color:white;border:1px solid #ffffff30;border-radius:6px;padding:5px}';document.head.append(style);
  wrap.addEventListener('click',async e=>{
    if(state.mode!=='eva'||state.rvMode||dragMoved||e.target.closest?.('button,.map-location'))return;
    e.preventDefault();e.stopImmediatePropagation();
    if(evaSelected().length>=3){uiToast('Select up to three sites');return;}
    const cell=cellAt(e);if(!await uiCanSelectTarget(cell))return;
    if(evaSelected().length>=3){uiToast(uiText('최대 3곳을 선택하세요','Select up to three sites'));return;}
    const existing=META.targets.findIndex(t=>tCell(t)===cell);
    if(existing>=0){state.evaSel[existing]=true;}else{
      const number=META.targets.filter(t=>t.source_kind==='user_target').length+1;
      META.targets.push({x:cell%W+.5,y:Math.floor(cell/W)+.5,name_en:'Destination '+number,source_kind:'user_target',sols:[],ui:{name:'Destination '+number,summary:'User-selected location on the terrain grid. No rover observation is implied.'}});
      state.evaSel.push(true);
    }
    uiInvalidate();uiMarkers();uiPlanningControls();
  },true);
  uiPlanningControls();
})();
