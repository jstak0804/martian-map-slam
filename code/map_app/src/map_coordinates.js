
const UI_GEOREFERENCE=@@JSON:georeference@@;

function uiGridToLonLat(x,y,g){
  const line=g.cropLine+(y+.5)*g.block-.5,sample=g.cropSample+(x+.5)*g.block-.5;
  const lat=(g.lineOffset-line)*g.scale/g.radius*180/Math.PI;
  const east=g.centerLon+(sample-g.sampleOffset)*g.scale/(g.radius*Math.cos(g.centerLat*Math.PI/180))*180/Math.PI;
  return {lat,lon:((east+180)%360+360)%360-180};
}
function uiLonLatToGrid(lon,lat,g){
  const delta=((lon-g.centerLon+180)%360+360)%360-180;
  return {x:(g.sampleOffset+delta*Math.PI/180*g.radius*Math.cos(g.centerLat*Math.PI/180)/g.scale-g.cropSample+.5)/g.block-.5,y:(g.lineOffset-lat*Math.PI/180*g.radius/g.scale-g.cropLine+.5)/g.block-.5};
}
(() => {
  const box=document.createElement('div');
  box.id='map-coordinate-readout';box.className='map-shell map-glass';box.hidden=true;
  box.style.cssText='left:16px;top:86px;padding:9px 12px;max-width:calc(100vw - 110px);font:12px monospace;pointer-events:none';
  box.setAttribute('role','status');$('map-ui').append(box);
  const show=(x,y)=>{
    if(x<0||y<0||x>=W||y>=R)return;
    const east=(x+.5-(state.base%W+.5))*CELL;
    const north=((Math.floor(state.base/W)+.5)-(y+.5))*CELL;
    const geo=uiGridToLonLat(x,y,UI_GEOREFERENCE[META.site.id]);
    box.textContent=`${Math.abs(geo.lat).toFixed(5)}° ${geo.lat>=0?'N':'S'}, ${Math.abs(geo.lon).toFixed(5)}° ${geo.lon>=0?'E':'W'} | E ${Math.round(east)} m / N ${Math.round(north)} m`;
    box.title=uiText('지도 격자 중심 좌표 · 행성중심 위도 · 기지 기준 동서/남북 거리','Map cell centre · planetocentric latitude · offsets east/north from base');
    box.hidden=false;
  };
  wrap.addEventListener('click',e=>{
    if(dragMoved)return;
    const pin=e.target.closest?.('[data-poi]');
    if(pin){const t=META.targets[Number(pin.dataset.poi)];show(Math.floor(t.x),Math.floor(t.y));return;}
    if(e.target.closest?.('button'))return;
    const p=uiGridPoint(e);if(p)show(Math.floor(p.x),Math.floor(p.y));
  },true);
  $('map-world').addEventListener('click',()=>box.hidden=true);
  document.addEventListener('pointerdown',e=>{if(e.target.closest?.('#map-base-pin'))box.hidden=true;},true);
})();
