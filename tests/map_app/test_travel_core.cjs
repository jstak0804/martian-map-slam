const path=require('node:path');const ROOT=path.resolve(__dirname,'../..');
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync(path.join(ROOT,'code/map_app/src/travel_mode.js'),'utf8').split('(() => {')[0];
const c={N:4,W:2,CELL:10,C:{o2_g_per_j:.001},RATE1:[1,1,1,1],state:{travelMode:'foot'},retTot:()=>({t:100}),pathToBase:()=>[1,0]};vm.createContext(c);vm.runInContext(source,c);
const tree={src:0,pred:new Int32Array([-1,0,0,-1]),o2:[0,20,20,Infinity],t:[0,30,30,Infinity],dose:[0,1,1,Infinity]};
assert.equal(c.uiTravelTree(tree),tree);c.state.travelMode='rover';let r=c.uiTravelTree(tree);assert(Math.abs(r.t[1]-10/2.2)<1e-9);assert(Math.abs(r.o2[1]-147*.001*10/2.2)<1e-9);assert.equal(r.o2[3],Infinity);assert.equal(r.pred,tree.pred);assert.equal(c.uiTravelTree(tree),r);
let tr=c.uiRoverTrack([0,1]);assert.equal(tr.len,r.t[1]);assert.equal(tr.co[1],r.o2[1]);assert.equal(c.uiTravelReturnSeconds(1),tr.len);c.state.travelMode='foot';assert.equal(c.uiTravelReturnSeconds(1),100);c.state.travelMode='rover';c.pathToBase=()=>null;assert(Number.isNaN(c.uiTravelReturnSeconds(1)));assert.equal(c.uiRoverTrack([0]).len,0);console.log('PASS: walk passthrough, rover costs, unreachable cells, path preservation, caching, simulation agreement, both return modes, missing return, zero distance');
