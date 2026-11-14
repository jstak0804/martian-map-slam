
// Demo assumptions copied from upstream ROVER_V / RIDE_W; not validated Mars vehicle specifications.
const UI_ROVER={speed:2.2,metabolicW:147};
const uiRoverTrees=new WeakMap();
function uiRoverEdge(a,b){
  const distance=Math.hypot(b%W-a%W,Math.floor(b/W)-Math.floor(a/W))*CELL;
  const t=distance/UI_ROVER.speed;
  return {t,o2:UI_ROVER.metabolicW*C.o2_g_per_j*t,dose:.5*(RATE1[a]+RATE1[b])*t/3600,distance};
}
function uiTravelTree(tree){
  if(!tree||state.travelMode!=='rover')return tree;
  let cached=uiRoverTrees.get(tree);if(cached)return cached;
  const o2=new Float64Array(N).fill(Infinity),t=new Float64Array(N).fill(Infinity),dose=new Float64Array(N).fill(Infinity);
  o2[tree.src]=t[tree.src]=dose[tree.src]=0;
  for(let i=0;i<N;i++){
    if(!Number.isFinite(tree.o2[i])||Number.isFinite(t[i]))continue;
    const chain=[];let c=i;
    while(c>=0&&!Number.isFinite(t[c])){chain.push(c);c=tree.pred[c];}
    if(c<0)continue;
    while(chain.length){const child=chain.pop(),edge=uiRoverEdge(c,child);t[child]=t[c]+edge.t;o2[child]=o2[c]+edge.o2;dose[child]=dose[c]+edge.dose;c=child;}
  }
  cached={...tree,o2,t,dose};uiRoverTrees.set(tree,cached);return cached;
}
function uiRoverTrack(cells){
  const cd=new Float64Array(cells.length),cm=new Float64Array(cells.length),co=new Float64Array(cells.length),dose=new Float64Array(cells.length);
  for(let j=1;j<cells.length;j++){const e=uiRoverEdge(cells[j-1],cells[j]);cd[j]=cd[j-1]+e.t;cm[j]=cm[j-1]+e.distance;co[j]=co[j-1]+e.o2;dose[j]=dose[j-1]+e.dose;}
  return {cells,cd,cm,co,dose,len:cd.at(-1),lenM:cm.at(-1)};
}
function uiTravelReturnSeconds(cell){
  if(state.travelMode!=='rover')return retTot(cell)?.t??NaN;
  const path=pathToBase(cell);return path?.length?uiRoverTrack(path).len:NaN;
}
(() => {
  state.travelMode='foot';
  const label=document.createElement('label');label.style.cssText='display:flex;align-items:center;gap:6px;font-size:12px';
  const select=document.createElement('select');select.id='travel-mode';select.setAttribute('aria-label','Travel mode');
  select.innerHTML='<option value="foot">On foot</option><option value="rover">Rover</option>';
  select.style.cssText='background:#263139;color:white;border:1px solid #ffffff30;border-radius:7px;padding:7px';
  const note=document.createElement('small');note.id='travel-mode-note';note.style.cssText='max-width:260px;color:#a7b6bd;font-size:10px';
  note.title='Rover uses existing walking-accessible routes. Vehicle battery, traction and vehicle-specific slope limits are not modeled. Radius remains emergency walking return coverage.';
  const refresh=()=>{const ko=LANG==='ko';select.options[0].textContent=ko?'도보':'On foot';select.options[1].textContent=ko?'로버':'Rover';note.textContent=state.travelMode==='rover'?uiText('가정: 2.2m/s · 147W · 도보 귀환 확보','Assumed: 2.2 m/s · 147 W · walking return required'):uiText('지형 기반 도보 모델','Terrain-based walking model');};
  select.onchange=()=>{state.travelMode=select.value;uiOuterCache=null;uiRadiusLast=null;uiInvalidate();refresh();};
  $('settings-language').addEventListener('change',refresh);label.append(select,note);$('custom-planning').prepend(label);refresh();
})();
