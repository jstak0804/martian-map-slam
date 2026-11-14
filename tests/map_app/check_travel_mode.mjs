import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
import {launch} from './cdp.mjs';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
const b=await launch({port:9452});
try{
 const p=await b.newPage();await p.viewport(1440,1000);await p.goto(pathToFileURL(path.join(ROOT,'reports/18-eva-walkback-demo.html')).href);
 await p.waitFor('window.EVA_DEBUG?.setNow() && document.getElementById("radius-outer")');
 assert.equal(await p.eval('!!document.getElementById("travel-mode")'),true,'Planning must offer On foot / Rover');
 await p.eval(`(()=>{const D=EVA_DEBUG,S=D.setNow(),w=D.W;let c=-1;for(let i=0;i<D.N;i++)if((D.FLAGS[i]&8)&&S.o2[i]>0&&S.t[i]>600&&S.t[i]<900){c=i;break;}if(c<0)throw Error('No test location');D.META.targets.push({x:c%w+.5,y:Math.floor(c/w)+.5,name_en:'QA travel target',planned_minutes:2,source_kind:'user_target'});D.state.evaSel=D.META.targets.map((_,i)=>i===D.META.targets.length-1);D.update();})()`);
 await p.waitFor('EVA_DEBUG.EVA?.ok && EVA_DEBUG.SIM?.ok');
 const read=()=>p.eval(`({out:EVA_DEBUG.EVA.outbound_s,back:EVA_DEBUG.EVA.return_s,oxygen:EVA_DEBUG.EVA.oxygen_g,stay:EVA_DEBUG.EVA.dwell_total_s,simTime:EVA_DEBUG.SIM.frames.at(-1).m,simOxygen:EVA_DEBUG.SIM.frames.at(-1).o2,mode:EVA_DEBUG.state.travelMode})`);
 const walk=await read();
 await p.eval(`(()=>{const el=document.getElementById('travel-mode');el.value='rover';el.dispatchEvent(new Event('change',{bubbles:true}));})()`);
 await p.waitFor('EVA_DEBUG.EVA?.ok && EVA_DEBUG.SIM?.ok && EVA_DEBUG.state.travelMode==="rover"');
 const rover=await read();assert(rover.out<walk.out);assert(rover.back<walk.back);assert(rover.oxygen<walk.oxygen);assert.equal(rover.stay,walk.stay);assert(rover.simTime<walk.simTime);assert(rover.simOxygen>walk.simOxygen);
 await p.eval(`(()=>{const el=document.getElementById('travel-mode');el.value='foot';el.dispatchEvent(new Event('change',{bubbles:true}));})()`);
 await p.waitFor('EVA_DEBUG.EVA?.ok && EVA_DEBUG.SIM?.ok && EVA_DEBUG.state.travelMode==="foot"');
 const restored=await read();assert(Math.abs(restored.out-walk.out)<.001);assert(Math.abs(restored.oxygen-walk.oxygen)<.001);assert.equal(p.errors.length,0);
 await fs.writeFile(path.join(ROOT,'reports/map-app-validation/travel-mode-check.json'),JSON.stringify({walk,rover,restored,errors:p.errors},null,2));console.log({walk,rover,restored});
}finally{await b.send('Browser.close');b.proc.kill();}
