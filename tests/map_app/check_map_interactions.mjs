import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
import {launch} from './cdp.mjs';
import assert from 'node:assert/strict';
const b=await launch({port:9455});try{const p=await b.newPage();await p.viewport(1440,1000);await p.goto(pathToFileURL(path.join(ROOT,'reports/18-eva-walkback-demo.html')).href);await p.waitFor('EVA_DEBUG?.setNow() && document.getElementById("radius-outer")');
const before=await p.eval('EVA_DEBUG.META.targets.length');
const target=await p.eval(`(()=>{const D=EVA_DEBUG,S=D.setNow(),r=document.getElementById('stage').getBoundingClientRect();for(let i=0;i<D.N;i++)if((D.FLAGS[i]&8)&&S.o2[i]>0&&S.t[i]>300&&S.t[i]<600){const x=r.left+(i%D.W+.5)/D.W*r.width,y=r.top+(Math.floor(i/D.W)+.5)/D.R*r.height;if(x>50&&x<1300&&y>200&&y<650)return {x,y,cell:i};}throw Error('No point');})()`);
await p.eval(`document.getElementById('vec').dispatchEvent(new MouseEvent('click',{bubbles:true,clientX:${target.x},clientY:${target.y}}))`);await p.waitFor('EVA_DEBUG.META.targets.length==='+ (before+1));await p.click('[data-delete-destination="'+before+'"]');await p.waitFor('EVA_DEBUG.META.targets.length==='+before);assert.equal(await p.eval('document.querySelectorAll(".map-target-pin").length'),before);
const base=await p.eval(`(()=>{const r=document.getElementById('map-base-pin').getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2}})()`);
await p.mouse('mouseMoved',base.x,base.y,{buttons:0});await p.mouse('mousePressed',base.x,base.y);await p.mouse('mouseMoved',target.x,target.y);await p.mouse('mouseReleased',target.x,target.y,{buttons:0});
await p.waitFor('EVA_DEBUG.state.base==='+target.cell);assert.equal(await p.eval('document.getElementById("map-markers").hidden'),false);await p.waitFor('EVA_DEBUG.setNow() && !document.getElementById("radius-outer").hidden');assert.equal(p.errors.length,0);console.log('PASS: destination add/delete, marker count, real base drag, markers persist, radius recalculates, no runtime errors');
}finally{await b.send('Browser.close');b.proc.kill();}
