
function uiVisor(doc,pos,heading){uiTerrainVisor(doc,pos,heading);}
let middleRotation=null;
wrap.addEventListener('pointerdown',e=>{if(e.button!==1)return;e.preventDefault();middleRotation={x:e.clientX,a:UI.angle};wrap.setPointerCapture(e.pointerId);});
wrap.addEventListener('pointermove',e=>{if(!middleRotation)return;UI.angle=middleRotation.a+(e.clientX-middleRotation.x)*.008;uiApplyZoom();});
wrap.addEventListener('pointerup',()=>{middleRotation=null;});
wrap.addEventListener('pointercancel',()=>{middleRotation=null;});
wrap.addEventListener('auxclick',e=>{if(e.button===1)e.preventDefault();});
$('map-north').title='Face next target';$('map-north').setAttribute('aria-label','Align next target to top');

