import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
import {launch} from './cdp.mjs';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
const b=await launch({port:9453});
try{
 const p=await b.newPage();await p.viewport(1440,1000);await p.goto(pathToFileURL(path.join(ROOT,'reports/18-eva-walkback-demo.html')).href);
 await p.waitFor('window.EVA_DEBUG?.setNow() && document.getElementById("radius-outer")');
 assert.equal(await p.eval('!!document.getElementById("travel-mode")'),true,'Planning must offer On foot / Rover');
 await p.eval(`(()=>{const D=EVA_DEBUG,S=D.setNow(),w=D.W;let c=-1;for(let i=0;i<D.N;i++)if((D.FLAGS[i]&8)&&S.o2[i]>0&&S.t[i]>600&&S.t[i]<900){c=i;break;}if(c<0)throw Error('No test location');D.META.targets.push({x:c%w+.5,y:Math.floor(c/w)+.5,name_en:'QA travel target',planned_minutes:2,source_kind:'user_target'});D.state.evaSel=D.META.targets.map((_,i)=>i===D.META.targets.length-1);D.update();})()`);
 await p.waitFor('EVA_DEBUG.EVA?.ok && EVA_DEBUG.SIM?.ok');

 await p.realClick('#map-visor');
 let popup;
 for(let i=0;i<40&&!popup;i++){const {targetInfos}=await b.send('Target.getTargets');popup=targetInfos.find(t=>t.type==='page'&&t.title==='EVA Helmet HUD');if(!popup)await new Promise(r=>setTimeout(r,100));}
 assert(popup,'Visor popup must open');
 const {sessionId}=await b.send('Target.attachToTarget',{targetId:popup.targetId,flatten:true});
 const evaluate=async expression=>{const r=await b.send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true},sessionId);if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description);return r.result.value;};
 const before=await evaluate(`(()=>{const c=document.getElementById('terrain-navigation');return {route:Number(c.dataset.routePoints),heading:Number(c.dataset.heading),time:Number(c.dataset.guideTime)}})()`);assert(before.route>1,'Actual route must populate guidance');
 await evaluate(`(()=>{const c=document.getElementById('terrain-navigation');c.drag={x:0,y:0,look:0,pitch:0};c.onpointermove({clientX:1200,clientY:80});c.onpointerup();})()`);
 const after=await evaluate(`(()=>{const c=document.getElementById('terrain-navigation');return {heading:Number(c.dataset.heading),time:Number(c.dataset.guideTime),pitch:c.pitch}})()`);assert(after.heading>=0&&after.heading<360);assert.notEqual(after.heading,before.heading);assert(after.pitch>0);assert.equal(after.time,before.time);
 await new Promise(r=>setTimeout(r,5100));await evaluate(`document.getElementById('terrain-navigation').ondblclick()`);
 const updated=await evaluate(`Number(document.getElementById('terrain-navigation').dataset.guideTime)`);assert(updated>after.time);
 const {data}=await b.send('Page.captureScreenshot',{format:'png'},sessionId);await fs.writeFile(path.join(ROOT,'reports/map-app-validation/visor-check.png'),Buffer.from(data,'base64'));
 assert.equal(p.errors.length,0);console.log({before,after,updated,errors:p.errors});
 await fs.writeFile(path.join(ROOT,'reports/map-app-validation/visor-check.json'),JSON.stringify({before,after,updated,errors:p.errors},null,2));
}finally{await b.send('Browser.close');b.proc.kill();}
