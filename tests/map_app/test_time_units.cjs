const path=require('node:path');const ROOT=path.resolve(__dirname,'../..');
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');const h=fs.readFileSync(path.join(ROOT,'reports/Martian-Map-Final.html'),'utf8');
for(const name of ['hm','hmS']){const line=h.split('\n').find(l=>l.trim().startsWith('const '+name+' ='));const c={};vm.createContext(c);vm.runInContext(line+';globalThis.format='+name,c);assert.equal(c.format(2.5),'150 min',name+' must use minutes');assert.equal(c.format(-1),'–');}console.log('PASS: time formatters use min');
