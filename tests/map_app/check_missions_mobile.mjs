import {launch} from './cdp.mjs';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const b=await launch({port:9457});
try{
  const p=await b.newPage();await p.viewport(390,844,{mobile:true,touch:true});
  await p.goto(pathToFileURL(path.join(ROOT,'reports/18-eva-walkback-demo.html')).href);
  await p.waitFor('window.EVA_DEBUG?.setNow() && document.getElementById("radius-outer")');
  const bounds=await p.eval(`['.map-actions','.map-bottom','#map-visor'].map(s=>{const r=document.querySelector(s).getBoundingClientRect();return {s,left:r.left,right:r.right,top:r.top,bottom:r.bottom}})`);
  for(const r of bounds){assert(r.left>=0&&r.right<=391,JSON.stringify(r));assert(r.top>=0&&r.bottom<=845,JSON.stringify(r));}
  const plan=bounds.find(r=>r.s==='.map-bottom'),visor=bounds.find(r=>r.s==='#map-visor');assert(visor.bottom<=plan.top||visor.top>=plan.bottom,'Visor must not cover mobile planning controls');
  await p.click('#map-settings');assert.equal(await p.eval('document.getElementById("map-drawer").hidden'),false);await p.click('#map-drawer-close');
  const old=await p.eval('EVA_DEBUG.UI.screen.cx');await p.touch('touchStart',[{x:180,y:320}]);await p.touch('touchMove',[{x:210,y:350}]);await p.touch('touchEnd',[]);
  assert.notEqual(await p.eval('EVA_DEBUG.UI.screen.cx'),old,'Touch must pan map');
  await p.viewport(1440,1000);
  await p.eval(`(()=>{const D=EVA_DEBUG,S=D.setNow(),w=D.W,chosen=[];for(const min of [300,600,900]){let c=-1;for(let i=0;i<D.N;i++)if((D.FLAGS[i]&8)&&S.o2[i]>0&&S.t[i]>min&&S.t[i]<min+120&&!chosen.includes(i)){c=i;break;}if(c<0)throw Error('No reachable sample');chosen.push(c);}const offset=D.META.targets.length;for(const c of chosen)D.META.targets.push({x:c%w+.5,y:Math.floor(c/w)+.5,name_en:'Mission QA',source_kind:'user_target',planned_minutes:30});D.state.evaSel=D.META.targets.map((_,i)=>i>=offset);D.update();})()`);
  await p.waitFor('EVA_DEBUG.EVA?.ok && EVA_DEBUG.SIM?.ok');
  const full=await p.eval(`(()=>{const D=EVA_DEBUG;return {stops:D.EVA.order.length,stay:D.EVA.dwell_total_s,last:D.SIM.frames.at(-1).phase,minutes:D.SIM.frames.at(-1).m,oxygen:D.SIM.frames.at(-1).o2,initial:D.state.o2};})()`);
  assert.equal(full.stops,3);assert.equal(full.stay,5400);assert.equal(full.last,'home');assert(full.oxygen>=full.initial*.2);
  await p.eval(`EVA_DEBUG.setSimIdx(EVA_DEBUG.SIM.frames.findIndex(f=>f.phase==='out'&&f.m>=2))`);
  await p.waitFor('!document.getElementById("map-return").disabled');await p.click('#map-return');
  const early=await p.eval(`({manual:!!EVA_DEBUG.SIM.manualReturnPath?.length,last:EVA_DEBUG.SIM.frames.at(-1).phase,minutes:EVA_DEBUG.SIM.frames.at(-1).m})`);
  assert(early.manual);assert.equal(early.last,'home');assert(early.minutes<full.minutes);
  await p.eval(`(()=>{const D=EVA_DEBUG;for(const t of D.META.targets)if(t.source_kind==='user_target')t.planned_minutes=1440;D.state.o2=50;D.update();})()`);
  await p.waitFor('EVA_DEBUG.EVA && !EVA_DEBUG.EVA.ok && !!EVA_DEBUG.EVA.resourceCandidate');
  assert.equal(await p.eval('document.getElementById("map-play").disabled'),true);
  assert.equal(p.errors.length,0);const result={bounds,full,early,errors:p.errors};
  await fs.writeFile(path.join(ROOT,'reports/map-app-validation/missions-mobile.json'),JSON.stringify(result,null,2));console.log(result);
}finally{await b.send('Browser.close');b.proc.kill();}
