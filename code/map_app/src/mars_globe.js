// Offline orthographic sphere with equirectangular MOLA texture.
function uiWorld(){
  stopSim();let d=document.getElementById('mars-globe');
  if(d){d.showModal();d.drawGlobe?.();return;}
  d=document.createElement('dialog');d.id='mars-globe';d.style.cssText='width:96vw;max-width:96vw;height:94vh;max-height:94vh;box-sizing:border-box;background:#070e1b;color:#dff6ff;border:1px solid #395064;border-radius:20px;padding:18px';
  d.innerHTML='<header style="display:flex;justify-content:space-between"><b>MARS · 3D EXPLORER</b><button aria-label="Close globe">✕</button></header><p style="color:#91b7ca">Drag to rotate · scroll to zoom · select a region to plan</p><div style="position:relative;height:calc(94vh - 175px);min-height:180px;overflow:hidden;background:radial-gradient(ellipse,#182238,#030813 70%);border-radius:15px"><canvas style="width:100%;height:100%;touch-action:none;cursor:grab" aria-label="Interactive Mars globe" tabindex="0"></canvas><div class="globe-pins"></div></div><nav style="display:flex;gap:12px;flex-wrap:wrap;margin-top:14px"></nav><p class="globe-status" style="font-size:12px">Loading offline MOLA texture…</p>';
  document.body.append(d);d.querySelector('header button').onclick=()=>d.close();
  const world=SITE_LIST[0].meta.world,cv=d.querySelector('canvas'),g=cv.getContext('2d'),pins=d.querySelector('.globe-pins'),status=d.querySelector('.globe-status');
  let lon=77*Math.PI/180,lat=18*Math.PI/180,zoom=1,texture=null,drag=null,frame=0;
  const open=id=>{const i=SITE_LIST.findIndex(s=>s.meta.site.id===id);if(i>=0){d.close();uiClear();loadSite(i);}};
  const markers=world.pins.map(p=>{const b=document.createElement('button');b.textContent='◆ '+p.id[0].toUpperCase()+p.id.slice(1);b.style.cssText='position:absolute;transform:translate(-50%,-50%);border:1px solid #72e5f4;background:#102539e8;color:#d8faff;padding:7px;border-radius:8px;cursor:pointer';b.onclick=()=>open(p.id);pins.append(b);return{...p,b};});
  SITE_LIST.forEach(s=>{const b=document.createElement('button');b.textContent='⚑ '+s.meta.site.short.replace('(가상 거점)','(virtual base)');b.onclick=()=>open(s.meta.site.id);d.querySelector('nav').append(b);});
  const controls=document.createElement('span');controls.innerHTML='<button aria-label="Zoom globe in">＋</button><button aria-label="Zoom globe out">−</button><button>Reset view</button>';d.querySelector('nav').append(controls);
  const basis=()=>{const co=Math.cos(lon),so=Math.sin(lon),cl=Math.cos(lat),sl=Math.sin(lat);return{r:[co,0,-so],u:[-sl*so,cl,-sl*co],f:[cl*so,sl,cl*co]};};
  const dot=(a,b)=>a.reduce((v,x,i)=>v+x*b[i],0);
  function draw(){frame=0;if(!d.open)return;const box=cv.getBoundingClientRect();cv.width=Math.min(720,Math.round(box.width));cv.height=Math.max(1,Math.round(cv.width*box.height/box.width));
    const w=cv.width,h=cv.height,r=Math.min(w,h)*.43*zoom,cx=w/2,cy=h/2,B=basis();g.clearRect(0,0,w,h);
    if(texture){const im=g.createImageData(w,h),out=im.data;
      for(let y=0;y<h;y++)for(let x=0;x<w;x++){const sx=(x-cx)/r,sy=(cy-y)/r,z2=1-sx*sx-sy*sy;if(z2<0)continue;const z=Math.sqrt(z2);
        const nx=B.r[0]*sx+B.u[0]*sy+B.f[0]*z,ny=B.u[1]*sy+B.f[1]*z,nz=B.r[2]*sx+B.u[2]*sy+B.f[2]*z;
        const u=((Math.atan2(nx,nz)/(2*Math.PI)+.5)%1+1)%1,v=.5-Math.asin(Math.max(-1,Math.min(1,ny)))/Math.PI;
        const ti=(Math.min(texture.height-1,Math.floor(v*texture.height))*texture.width+Math.floor(u*texture.width))*4,k=(y*w+x)*4;
        // Remove the elevation rainbow; this is a stylized relief palette,
        // not a reconstruction of the planet's true surface colour.
        const relief=(.2126*texture.data[ti]+.7152*texture.data[ti+1]+.0722*texture.data[ti+2])/255;
        const light=.36+.64*Math.max(0,-.3*sx+.35*sy+.88*z);
        out[k]=(100+105*relief)*light;out[k+1]=(51+83*relief)*light;out[k+2]=(33+65*relief)*light;out[k+3]=255;}
      g.putImageData(im,0,0);g.strokeStyle='#83b9cd66';g.lineWidth=2;g.beginPath();g.arc(cx,cy,r,0,2*Math.PI);g.stroke();}
    for(const p of markers){const a=p.lon*Math.PI/180,b=p.lat*Math.PI/180,V=[Math.cos(b)*Math.sin(a),Math.sin(b),Math.cos(b)*Math.cos(a)],z=dot(V,B.f),x=cx+r*dot(V,B.r),y=cy-r*dot(V,B.u);p.b.hidden=z<.03||x<0||y<0||x>w||y>h;p.b.style.left=x/w*box.width+'px';p.b.style.top=y/h*box.height+'px';}
    if(texture)status.textContent=`${world.source} · Stylized Mars tones (not true-color imagery); relief is not extruded · Centre ${(lat*180/Math.PI).toFixed(1)}° N, ${(((lon*180/Math.PI+180)%360+360)%360-180).toFixed(1)}° E`;}
  const request=()=>{if(!frame)frame=requestAnimationFrame(draw);};d.drawGlobe=request;
  cv.onpointerdown=e=>{drag={x:e.clientX,y:e.clientY,lon,lat};cv.setPointerCapture(e.pointerId);};cv.onpointermove=e=>{if(!drag)return;lon=drag.lon-(e.clientX-drag.x)*.006/zoom;lat=Math.max(-Math.PI/2+.01,Math.min(Math.PI/2-.01,drag.lat+(e.clientY-drag.y)*.006/zoom));request();};cv.onpointerup=cv.onpointercancel=()=>drag=null;
  cv.addEventListener('wheel',e=>{e.preventDefault();zoom=Math.max(.65,Math.min(3,zoom*Math.exp(-e.deltaY*.001)));request();},{passive:false});
  cv.onkeydown=e=>{if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key))return;e.preventDefault();lon+=(e.key==='ArrowLeft'?.1:e.key==='ArrowRight'?-.1:0);lat=Math.max(-1.56,Math.min(1.56,lat+(e.key==='ArrowUp'?.1:e.key==='ArrowDown'?-.1:0)));request();};
  const buttons=controls.querySelectorAll('button');buttons[0].onclick=()=>{zoom=Math.min(3,zoom*1.2);request();};buttons[1].onclick=()=>{zoom=Math.max(.65,zoom/1.2);request();};buttons[2].onclick=()=>{lon=77*Math.PI/180;lat=18*Math.PI/180;zoom=1;request();};
  const image=new Image();image.onload=()=>{const temp=document.createElement('canvas');temp.width=world.width;temp.height=world.height;const c=temp.getContext('2d');c.drawImage(image,0,0,temp.width,temp.height);texture=c.getImageData(0,0,temp.width,temp.height);request();};image.onerror=()=>status.textContent='Unable to load the offline globe texture';image.src=world.image;
  new ResizeObserver(request).observe(cv);d.showModal();request();
}
$('map-world').onclick=uiWorld;
