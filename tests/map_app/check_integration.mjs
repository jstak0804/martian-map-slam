import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
import {launch} from './cdp.mjs';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
const b=await launch({port:9454});
try{const p=await b.newPage();await p.viewport(1440,1000);await p.goto(pathToFileURL(path.join(ROOT,'reports/18-eva-walkback-demo.html')).href);await p.waitFor('window.EVA_DEBUG?.setNow() && document.getElementById("radius-status")');
await p.eval(`(()=>{const l=document.getElementById('settings-language');l.value='ko';l.dispatchEvent(new Event('change',{bubbles:true}));})()`);
assert.equal(await p.eval(`document.querySelector('#custom-planning details summary').textContent`),'경로 비교','Compare routes must translate');
assert.equal(await p.eval(`document.querySelector('#radius-status button')?.textContent`),'전체 영역 보기','Fit button must be Korean');
assert.equal(await p.eval(`!!document.querySelector('#map-sites svg')`),true);
const regions=[];for(let i=0;i<3;i++){await p.eval('EVA_DEBUG.loadSite('+i+')');await p.waitFor('EVA_DEBUG.SITE_I==='+i+' && EVA_DEBUG.setNow() && !document.getElementById("radius-outer").hidden');regions.push(await p.eval(`({id:EVA_DEBUG.META.site.id,background:document.getElementById('radius-context-map').dataset.site,pins:document.querySelectorAll('.map-target-pin').length,targets:EVA_DEBUG.META.targets.length,language:document.documentElement.lang})`));}
for(const r of regions){assert.equal(r.id,r.background);assert.equal(r.pins,r.targets);assert.equal(r.language,'ko');}assert.equal(p.errors.length,0);
console.log({regions,errors:p.errors});await fs.writeFile(path.join(ROOT,'reports/map-app-validation/integration-check.json'),JSON.stringify({regions,errors:p.errors},null,2));
}finally{await b.send('Browser.close');b.proc.kill();}
