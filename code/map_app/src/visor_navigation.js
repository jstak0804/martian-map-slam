// Included inside the planner closure. Synthetic DTM view, not a camera feed.
function uiVisorProject(point,camera){
  const a=camera.heading*Math.PI/180,dx=point.x-camera.x,dy=point.y-camera.y;
  const depth=dx*Math.sin(a)-dy*Math.cos(a);
  if(depth<=1)return null;
  return {x:camera.width/2+(dx*Math.cos(a)+dy*Math.sin(a))*camera.focal/depth,y:camera.horizon-(point.z-camera.z)*camera.focal/depth,depth};
}
function uiVisorRoute(path,pos,target,width){
  if(!path?.length)return [];
  let start=0,best=Infinity;
  path.forEach((cell,i)=>{const d=Math.hypot(cell%width-pos%width,Math.floor(cell/width)-Math.floor(pos/width));if(d<best){best=d;start=i;}});
  const end=path.indexOf(target,start);return end<start?[]:path.slice(start,end+1);
}
function uiVisorGuideDue(guide,now,target,signature){return !guide||now-guide.time>=5000||guide.target!==target||guide.signature!==signature;}
function uiNavigationTarget(pos) {
  const f=simFrame();
  if(f?.phase==='back'||f?.phase==='home')return state.base;
  const order=EVA?.order||evaSelected();
  const index=Math.max(0,(f?.stop_index||0)-(f?.phase==='work'?1:0));
  return order[index]!==undefined?tCell(META.targets[order[index]]):state.base;
}
function uiTerrainVisor(doc,pos,heading){
  const host=doc.getElementById('visor');if(!host)return;
  doc.getElementById('map-visor-photo')?.remove();
  let cv=doc.getElementById('terrain-navigation');
  if(!cv){
    cv=doc.createElement('canvas');cv.id='terrain-navigation';cv.width=720;cv.height=400;
    cv.style.cssText='position:absolute;inset:0;width:100%;height:100%;touch-action:none;cursor:grab';host.prepend(cv);
    cv.look=0;cv.pitch=0;
    cv.onpointerdown=e=>{cv.drag={x:e.clientX,y:e.clientY,look:cv.look,pitch:cv.pitch};cv.setPointerCapture(e.pointerId);};
    cv.onpointermove=e=>{if(!cv.drag)return;cv.look=cv.drag.look+(e.clientX-cv.drag.x)*.35;cv.pitch=Math.max(-35,Math.min(35,cv.drag.pitch+(e.clientY-cv.drag.y)*.15));uiTerrainVisor(doc,simFrame()?.pos??state.base,UI.heading);};
    cv.onpointerup=cv.onpointercancel=()=>{cv.drag=null;};cv.ondblclick=()=>{cv.look=0;cv.pitch=0;uiTerrainVisor(doc,simFrame()?.pos??state.base,UI.heading);};
  }
  const g=cv.getContext('2d'),w=cv.width,h=cv.height,f=simFrame(),target=uiNavigationTarget(pos);
  const bearing=((heading+cv.look)%360+360)%360,rad=bearing*Math.PI/180;
  const walking=playing&&state.travelMode!=='rover'&&f&&['out','back'].includes(f.phase);
  const bob=walking?Math.sin(performance.now()/180)*2:0,horizon=175+cv.pitch*3+bob;
  const sky=g.createLinearGradient(0,0,0,h);sky.addColorStop(0,'#18202b');sky.addColorStop(.5,'#a27b62');sky.addColorStop(1,'#322722');g.fillStyle=sky;g.fillRect(0,0,w,h);
  const continuous=f&&UI.livePose&&UI.livePose.site===SITE_I&&Math.hypot(UI.livePose.x-(pos%W+.5),UI.livePose.y-((pos/W|0)+.5))<3?UI.livePose:null;
  const x0=continuous?.x??pos%W+.5,y0=continuous?.y??(pos/W|0)+.5,z0=H[pos]+1.7;
  const top=new Float32Array(w/3).fill(h);
  // Front-to-back height-field rendering; unknown cells remain unfilled.
  for(let d=2;d<1800;d*=1.045){
    for(let x=0;x<w;x+=3){
      const a=rad+Math.atan((x-w/2)/500),gx=Math.floor(x0+Math.sin(a)*d/CELL),gy=Math.floor(y0-Math.cos(a)*d/CELL);
      if(gx<0||gy<0||gx>=W||gy>=R)continue;const i=gy*W+gx;if(!(FLAGS[i]&1)||!Number.isFinite(H[i]))continue;
      const yy=Math.max(0,Math.min(h,horizon-(H[i]-z0)*500/d)),j=x/3;
      if(yy<top[j]){const light=Math.max(35,Math.min(64,48+(H[i]-H[pos])*.3));g.fillStyle=`hsl(22 28% ${light}%)`;g.fillRect(x,yy,3,top[j]-yy);top[j]=yy;}
    }
  }
  // Guidance is refreshed every five wall-clock seconds, or immediately on target change.
  const now=performance.now();
  const signature=SITE_I+':'+EVASIG+':'+(f?.phase??'plan')+':'+state.base;
  if(uiVisorGuideDue(cv.guide,now,target,signature)){
    const path=f?.phase==='back'?pathToBase(pos):EVA?.ok?EVA.path:[];
    cv.guide={time:now,target,signature,cells:uiVisorRoute(path,pos,target,W)};
  }
  const delta=((bearingTo(pos,target)-bearing+540)%360)-180;
  cv.dataset.guideTime=String(cv.guide.time);cv.dataset.routePoints=String(cv.guide.cells.length);cv.dataset.heading=String(bearing);
  g.strokeStyle='#7de5ee';g.fillStyle='#b7f8ff';g.lineWidth=1;g.globalAlpha=.5;
  for(const q of [1/3,2/3]){g.beginPath();g.moveTo(w*q,40);g.lineTo(w*q,h-40);g.stroke();g.beginPath();g.moveTo(35,h*q);g.lineTo(w-35,h*q);g.stroke();}
  g.beginPath();g.moveTo(w/2-45,h/2);g.lineTo(w/2-12,h/2);g.moveTo(w/2+12,h/2);g.lineTo(w/2+45,h/2);g.stroke();g.globalAlpha=1;
  // Pitch ladder is a virtual camera attitude aid, not measured suit telemetry.
  g.strokeStyle='#7de5ee';g.fillStyle='#b7f8ff';g.font='10px monospace';g.textAlign='left';
  for(let degrees=-30;degrees<=30;degrees+=10){const y=horizon-degrees*3;if(y<70||y>h-110)continue;g.beginPath();g.moveTo(w/2-65,y);g.lineTo(w/2-35,y);g.moveTo(w/2+35,y);g.lineTo(w/2+65,y);g.stroke();g.fillText(degrees+'°',w/2+70,y+3);}
  g.font='18px monospace';g.textAlign='center';g.fillText(`${Math.round(bearing)%360}°`,w/2,32);
  g.font='12px monospace';g.fillText(uiText('DTM 지형 시뮬레이션','SIMULATED DTM'),w/2,h-10);
  g.fillText(`${uiText('목표','WAYPOINT')} · ${Math.round(distKm(pos,target)*1000)} m`,w/2,60);
  const o=Math.max(0,Math.min(100,(f?.o2??state.o2)/state.o2*100)),water=Math.max(0,Math.min(100,(f?.w??state.water*1000)/(state.water*1000)*100));
  const mr=state.travelMode==='rover'&&f&&['out','back'].includes(f.phase)?UI_ROVER.metabolicW:levelMR();
  const rate=mr*C.o2_g_per_j*(f?.k??state.k)+(state.simLeak||0)/3600;
  const wr=waterOf(mr*C.o2_g_per_j,1,f?.k??state.k,state.q);
  const drawBar=(x,y,name,pct,minutes,color)=>{g.fillStyle='#09151ddd';g.fillRect(x,y,180,42);g.strokeStyle=color;g.strokeRect(x,y,100,42);g.fillStyle=color;g.fillRect(x+3,y+31,94*pct/100,7);g.font='14px monospace';g.textAlign='left';g.fillText(`${name} ${Math.round(pct)}%`,x+5,y+21);g.fillText(Number.isFinite(minutes)?`${Math.max(0,Math.floor(minutes))} min`:'—',x+110,y+25);};
  drawBar(20,h-90,'O₂',o,(f?.o2??state.o2)/rate/60,'#79ebba');drawBar(w-200,h-90,'H₂O',water,(f?.w??state.water*1000)/wr/60,'#70cfff');
  const hud=doc.getElementById('hud');if(hud){hud.innerHTML='';hud.style.pointerEvents='none';}
  const liveLabel=doc.querySelector('.live');if(liveLabel)liveLabel.textContent=uiText('시뮬레이션','SIMULATION');
  const cap=doc.getElementById('visor-cap');if(cap)cap.textContent=uiText('가상 지형 · 드래그로 둘러보기 · 더블클릭으로 전방 정렬 · 잔여 시간은 현재 활동량 기준','Simulated terrain · drag to look around · double-click to face forward · resource times assume current work rate');
}
