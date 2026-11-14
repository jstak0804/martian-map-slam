
const UI_CONTEXT_MAPS=@@JSON:context_maps@@;

// Derived from upstream paintOuter: terrain-edge costs extended over assumed flat ground.
// This display never changes the terrain graph or destination eligibility.
let uiOuterCache=null,uiContextFitted=null,uiRadiusLast=null;
let uiZeroForward=null;
function uiRadiusLive(){return (simFrame()?.m??0)>0;}
function uiRadiusZeroForward(){
  if(!uiZeroForward||uiZeroForward.o2.length!==N)uiZeroForward={o2:new Float32Array(N),t:new Float32Array(N)};
  return uiZeroForward;
}
function uiRadiusScope(){return [SITE_I,state.base,modelKey(),overlayRevision].join(':');}
function uiRadiusCanRetain(){return uiRadiusLast===uiRadiusScope();}
function uiRadiusOverlay(F,S){
  uiRadiusLast=uiRadiusScope();
  const context=UI_CONTEXT_MAPS[META.site.id];
  let background=$('radius-context-map');
  if(context){
    if(!background){background=document.createElement('img');background.id='radius-context-map';background.alt='CTX regional orbital map';background.style.cssText='pointer-events:none;z-index:-1;max-width:none';stage.prepend(background);}
    background.hidden=false;
    if(background.dataset.site!==META.site.id){
      background.src=context.img;background.dataset.site=META.site.id;
      const mask=document.createElement('canvas');mask.width=W;mask.height=R;
      const mc=mask.getContext('2d'),mi=mc.createImageData(W,R);
      for(let i=0;i<N;i++)if(FLAGS[i]&1)mi.data[i*4+3]=255;
      mc.putImageData(mi,0,0);const url='url('+mask.toDataURL()+')';
      for(const id of ['ortho','shade']){const el=$(id);el.style.maskImage=url;el.style.maskSize='100% 100%';}
    }
    Object.assign(background.style,{inset:'auto',left:`${context.x/W*100}%`,top:`${context.y/R*100}%`,width:`${context.w/W*100}%`,height:`${context.h/R*100}%`});
  }
  const threshold=i=>{
    const cost=F.o2[i]+S.o2[i],time=F.t[i]+S.t[i];
    if(!(FLAGS[i]&1)||S.o2[i]<0||!Number.isFinite(cost))return -1;
    const r=(EO2()-EK()*cost-(state.simLeak||0)*time/3600)/state.o2;
    return r>.2?3:r>.1?2:r>=0?1:0;
  };
  const zones=new Int8Array(N);for(let i=0;i<N;i++)zones[i]=threshold(i);
  for(let y=0;y<R;y++)for(let x=0;x<W;x++){
    const i=y*W+x,z=zones[i];if(z<1)continue;
    if((x&&zones[i-1]>=0&&zones[i-1]<z)||(x+1<W&&zones[i+1]>=0&&zones[i+1]<z)||(y&&zones[i-W]>=0&&zones[i-W]<z)||(y+1<R&&zones[i+W]>=0&&zones[i+W]<z))px[i]=rgba(z===3?'#d2efff':z===2?'#ffe9a6':'#ffb7a4',.95);
  }
  let cv=$('radius-outer'),label=$('radius-status');
  if(!cv){cv=document.createElement('canvas');cv.id='radius-outer';cv.style.cssText='pointer-events:none;image-rendering:pixelated;z-index:1';stage.append(cv);}
  if(!label){label=document.createElement('div');label.id='radius-status';label.className='map-shell map-glass';label.style.cssText='left:16px;top:122px;padding:7px 10px;font-size:11px;max-width:300px';$('map-ui').append(label);}
  cv.hidden=false;label.hidden=false;
  const speed=md().speed(0),gpm=md().mr(0,1.2,speed)*C.o2_g_per_j/speed;
  const extent=Math.ceil(state.o2/(2*Math.max(.001,EK()*gpm)*CELL))+8;
  const padX=context?-context.x:Math.max(Math.ceil(W/2),extent),padY=context?-context.y:Math.max(Math.ceil(R/2),extent);
  const extentW=context?.w??W+2*padX,extentH=context?.h??R+2*padY;
  const step=Math.max(8,Math.ceil(Math.max(extentW,extentH)/420)),cw=Math.ceil(extentW/step),ch=Math.ceil(extentH/step);
  const live=uiRadiusLive(),legs=live?1:2;
  const key=[SITE_I,legKey(state.base),live,state.base,overlayRevision,padX,padY].join(':');
  if(!uiOuterCache||uiOuterCache.key!==key||uiOuterCache.F!==F||uiOuterCache.S!==S){
    const cost=new Float64Array(cw*ch).fill(Infinity),time=new Float64Array(cw*ch).fill(Infinity),has=new Uint8Array(cw*ch);
    for(let i=0;i<N;i++){
      if(!(FLAGS[i]&1))continue;
      const p=Math.floor((Math.floor(i/W)+padY)/step)*cw+Math.floor((i%W+padX)/step);has[p]=1;
      const o=F.o2[i]+S.o2[i];if(S.o2[i]>=0&&Number.isFinite(o)&&o<cost[p]){cost[p]=o;time[p]=F.t[i]+S.t[i];}
    }
    const neighbors=[[1,0],[0,1],[1,1],[-1,1],[2,1],[-2,1],[1,2],[-1,2]];
    for(let iteration=0;iteration<2;iteration++)for(const dir of [1,-1])for(let yy=0;yy<ch;yy++)for(let xx=0;xx<cw;xx++){
      const x=dir>0?xx:cw-1-xx,y=dir>0?yy:ch-1-yy,p=y*cw+x;if(has[p])continue;
      for(const [dx,dy]of neighbors){const nx=x-dir*dx,ny=y-dir*dy;if(nx<0||ny<0||nx>=cw||ny>=ch)continue;
        const q=ny*cw+nx,d=step*CELL*Math.hypot(dx,dy),o=cost[q]+legs*d*gpm;
        if(o<cost[p]){cost[p]=o;time[p]=time[q]+legs*d/speed;}
      }
    }
    uiOuterCache={key,F,S,cost,time,has};
  }
  cv.width=cw;cv.height=ch;Object.assign(cv.style,{inset:'auto',left:`${-padX/W*100}%`,top:`${-padY/R*100}%`,width:`${cw*step/W*100}%`,height:`${ch*step/R*100}%`});
  const ctx=cv.getContext('2d'),im=ctx.createImageData(cw,ch),data=new Uint32Array(im.data.buffer),{cost,time,has}=uiOuterCache;
  let clipped=false;
  for(let y=0;y<ch;y++)for(let x=0;x<cw;x++){
    const p=y*cw+x;if(has[p]||!Number.isFinite(cost[p]))continue;
    const rem=(EO2()-EK()*cost[p]-(state.simLeak||0)*time[p]/3600)/state.o2;if(rem<0)continue;
    const color=rem>.2?'#238fff':rem>.1?'#e6bd5b':'#dc725e';
    const waterLimited=waterOf(cost[p],time[p],EK(),state.q)>budgets().water;
    data[p]=(waterLimited&&(x+y)%6===0)?rgba('#c0c4c8',.65):rgba(color,(x+y)%6===0?.64:.44);
    if(x===0||y===0||x===cw-1||y===ch-1)clipped=true;
  }
  ctx.putImageData(im,0,0);
  cv.dataset.oxygen=String(EO2());cv.dataset.mode=live?'return-only':'round-trip';
  label.textContent=uiText('사선: DTM 밖 평지 추정 · 회색: 냉각수 부족','Hatching: flat-ground estimate outside DTM · gray: coolant limit')+(clipped?uiText(' · 영역이 화면 범위 밖으로 이어짐',' · extends beyond displayed area'):'');
  label.prepend(document.createTextNode(live?uiText('현재 산소로 귀환 가능 · ','Return with current oxygen · '):uiText('출발 전 왕복 가능 · ','Pre-trip round-trip range · ')));
  const fit=document.createElement('button');fit.textContent=uiText('전체 영역 보기','Fit return area');fit.style.cssText='display:block;margin-top:6px;pointer-events:auto';fit.onclick=()=>{const v=uiView();ZK=Math.max(.08,Math.min(1,.85*Math.min(wrap.clientWidth/(v.w*cw*step/W),wrap.clientHeight/(v.h*ch*step/R))));ZX=(W/2-(-padX+extentW/2))/W*v.w*ZK;ZY=(R/2-(-padY+extentH/2))/R*v.h*ZK-70;UI.angle=0;uiApplyZoom();};label.append(fit);
  if(uiContextFitted!==SITE_I){uiContextFitted=SITE_I;fit.click();}
  if(context)label.title=context.source+' ? Context imagery only; outside-DTM terrain is assumed flat.';
}
function uiHideOuterRadius(pending=false){
  const retain=pending&&uiRadiusCanRetain();
  if($('radius-outer'))$('radius-outer').hidden=!retain;
  const label=$('radius-status');if(label){label.hidden=!pending;if(pending)label.textContent=retain?uiText('귀환 영역 갱신 중 · 직전 계산 결과 표시','Updating return area · showing previous calculation'):uiText('현재 위치의 귀환 영역 계산 중…','Updating return area for current position…');}
}
