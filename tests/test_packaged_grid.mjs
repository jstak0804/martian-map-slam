import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import zlib from 'node:zlib';
import assert from 'node:assert/strict';
import {loadSeed, sha256, modelSourceHash} from '../code/packed_seed.mjs';

// Default: write the mission fixture and the connectivity report to a fresh temp directory, so a
// check never replaces the product mission. publish:true is the explicit product-update step that
// writes outputs/local_terrain/jezero/mission.json and reports/packaged-grid-validation.json.
export async function runPackagedGrid(root,{publish=false,outDir=null}={}){
  const out=publish?null:(outDir??await fs.mkdtemp(path.join(os.tmpdir(),'jezero-grid-')));
  const missionPath=publish?root+'/outputs/local_terrain/jezero/mission.json':path.join(out,'mission.json');
  const reportPath=publish?root+'/reports/packaged-grid-validation.json':path.join(out,'packaged-grid-validation.json');
  const seed=await loadSeed(root);
  const template=await fs.readFile(root+'/code/demo_template.html','utf8');
  const stations=JSON.parse(await fs.readFile(root+'/outputs/local_terrain/jezero/stations.json','utf8'));
  const main=seed.meta,site=seed.sites.find(s=>s.meta.site.id==='jezero'),meta=site.meta,C=main.const;
  const targets=meta.targets.filter(t=>t.source_kind!=='places_station').concat(stations.targets);
  const binary=zlib.gunzipSync(Buffer.from(site.data,'base64'));
  const view=name=>{const [off,len,type]=meta.layout[name],b=binary.subarray(off,off+len),a=b.buffer.slice(b.byteOffset,b.byteOffset+b.length);return type==='uint16'?new Uint16Array(a):new Uint8Array(a);};
  const N=meta.rows*meta.cols,W=meta.cols,FLAGS=view('flags'),CLS=view('cls'),hq=view('h'),eq=view('eta'),sq=view('shield');
  const H=Float32Array.from(hq,q=>meta.h_min+q*meta.h_step),ETA=Float32Array.from(eq,q=>meta.eta_min+q/255*(meta.eta_max-meta.eta_min));
  const RATE1=Float32Array.from(sq,q=>C.d_bg_msv_day/24*(1-C.shield_max*q/255));
  const OFF=meta.offsets,CELL=meta.cell_m,STEP_M=OFF.map(([x,y])=>Math.hypot(x,y)*CELL),MID=OFF.map(([dx,dy])=>Math.abs(dx)===1&&Math.abs(dy)===1?[[dx,0],[0,dy]]:Math.abs(dy)===2?[[0,Math.sign(dy)],[dx,Math.sign(dy)]]:Math.abs(dx)===2?[[Math.sign(dx),0],[Math.sign(dx),dy]]:[]);
  const G={C,W,R:meta.rows,N,OFF,CELL,STEP_M,MID,H,ETA,FLAGS,CLS,RATE1,SP:C.cal?.speed_model||{},SAND:C.cal?.eta_sand||{a:1.5,b:1.3,v_floor_m_s:.85},ETA_ADD:.2};
  const model=template.slice(template.indexOf('  function MAKE_MODEL('),template.indexOf('  let MD ='));
  const worker=template.slice(template.indexOf('  function WORKER_MAIN()'),template.indexOf('  let WK ='));
  const ctx={self:{postMessage:r=>ctx.result=r},G};vm.runInNewContext(model+worker+';WORKER_MAIN();model=MAKE_MODEL(G,{});',ctx);
  assert.ok(Math.abs(ctx.model.level()-444.396)<.002,'IST flat model reference');
  const base=meta.base[1]*W+meta.base[0];
  const start=performance.now();ctx.self.onmessage({data:{type:'init',G}});ctx.self.onmessage({data:{id:1,type:'dijkstra',q:{src:base,base,strict:true,M:{},reverse:false}}});
  if(ctx.result.err)throw Error(ctx.result.err);const forward=ctx.result.r;
  assert.equal(forward.o2[base],0,'Real base is traversable');
  const reachable=[];for(const [i,t] of targets.entries()){const cell=Math.floor(t.y)*W+Math.floor(t.x);reachable.push({index:i,id:t.id??'target-'+i,name:t.name_en||t.name,cell,o2:forward.o2[cell],reachable:Number.isFinite(forward.o2[cell])});}
  assert.equal(new Set(reachable.map(r=>r.id)).size,reachable.length,'Stable target IDs are unique');
  assert.ok(reachable.filter(t=>t.reachable).length>=2,'At least two existing targets reachable');
  const goal=reachable.find(t=>t.reachable).cell,path_=[goal];let cur=goal;while(forward.pred[cur]>=0){cur=forward.pred[cur];path_.push(cur);if(path_.length>N)throw Error('Cycle');}path_.reverse();
  let o2=0,time=0;for(let i=1;i<path_.length;i++){const a=path_[i-1],b=path_[i],d=Math.hypot(b%W-a%W,(b/W|0)-(a/W|0))*CELL;assert.ok((FLAGS[b]&8)&&CLS[b]!==2);assert.ok(Math.abs(H[b]-H[a])/d<=Math.tan(Math.PI/9)+1e-8);ctx.model.edge(a,b,d);o2+=ctx.model.out.o2;time+=ctx.model.out.t;}
  assert.ok(Math.abs(o2-forward.o2[goal])<1e-7,'Explicit edge oxygen integral agrees with search');
  assert.ok(Math.abs(time-forward.t[goal])/time<1e-5,'Explicit edge time agrees with search');
  const solve=(src,reverse=false)=>{ctx.self.onmessage({data:{id:2,type:'dijkstra',q:{src,base,strict:true,M:{},reverse,asTree:reverse}}});if(ctx.result.err)throw Error(ctx.result.err);return ctx.result.r;};
  const selected=[1,2],tCell=t=>Math.floor(t.y)*W+Math.floor(t.x),nodes=[base,...selected.map(i=>tCell(targets[i]))];
  const rules=vm.runInNewContext(await fs.readFile(root+'/code/map_ui_policy.js','utf8')+';MapUIRules');
  const ui=await fs.readFile(root+'/code/map_ui.js','utf8');
  const planner=ui.slice(ui.indexOf('function uiPlanEva('),ui.indexOf('function uiPaintZones('));
  const water=(o,t,k,q)=>Math.max(0,k*o/C.o2_g_per_j+q*t)/C.latent_j_kg*1000;
  const pc={MapUIRules:rules,state:{base,k:1,o2:816.466266,q:0},UI:{order:'auto',share:50},META:{...meta,targets},FLAGS,RATE1,C,levelMR:()=>ctx.model.level(),waterOf:water,budgets:()=>({o2:816.466266*.8,water:3600-C.reserve_mr_w*1800/C.latent_j_kg*1000}),multNow:()=>1,uiText:(ko,en)=>en,evaSelected:()=>selected,evaNodes:()=>nodes,legKey:c=>c,LEGS:new Map([[base,forward]]),legPath:(tree,dst)=>{const p=[dst];while(tree.pred[p.at(-1)]>=0)p.push(tree.pred[p.at(-1)]);return p.reverse();}};
  let back=solve(base,true);pc.setNow=()=>back;for(const cell of nodes.slice(1))pc.LEGS.set(cell,solve(cell));vm.runInNewContext(planner,pc);
  const before=pc.uiPlanEva();assert.equal(before.ok,true,'Actual Brac + Amalik trip is feasible');
  assert.ok(816.466266-before.o2>=816.466266*.2-1e-8,'Actual full itinerary keeps 20% oxygen');
  const blocked=before.path.find((c,i)=>i>10&&!nodes.includes(c));const priorFlag=FLAGS[blocked];FLAGS[blocked]&=~8;
  ctx.self.onmessage({data:{type:'init',G}});back=solve(base,true);for(const cell of nodes)pc.LEGS.set(cell,solve(cell));const after=pc.uiPlanEva();
  assert.ok(!after.ok||!after.path.includes(blocked),'Actual recalculated route avoids synthetic blocked cell');FLAGS[blocked]=priorFlag;
  const mission={schema_version:2,site_id:'jezero',model_id:'ist_existing_16dir_strict_eva',base_cell:base,selected_poi_ids:selected.map(i=>'target-'+i),visit_order:before.order,dwell_policy:{mode:'max_feasible',allocation:'weighted',weights:[.5,.5]},oxygen_profile_id:'apollo_j_demo_v1',initial_pressure_psia:1430,initial_o2_g:816.466266,min_return_fraction:.2,water_g:3600,water_reserve_policy:'legacy_30min',k:1,extra_heat_w:0,known_leak_g_s:0,profile_status:'historical_reference_with_assumptions',unknown_policy:'warn',event:{id:'blocked_patch_1',kind:'synthetic',cells:[blocked],label:'Synthetic blocked cell'}};
  await fs.writeFile(missionPath,JSON.stringify(mission,null,2));
  const compact=e=>({ok:e.ok,outbound_s:e.outbound_s,return_s:e.return_s,dwell_s:e.dwell_total_s,o2_g:e.o2,status:e.ok?'needs_observation':'no_candidate'});
  const provenance={grid_payload_sha256:sha256(site.data),model_source_sha256:modelSourceHash(template),seed_manifest_sha256:sha256(JSON.stringify(seed.manifest.files)),stations_sha256:sha256(JSON.stringify(stations.targets.map(t=>[t.id,t.x,t.y]))),base,strict:true,overlay_revision:0};
  const result={provenance,cells:N,directions:OFF.length,flat_metabolic_w:ctx.model.level(),base,reachable_targets:reachable,checked_path_edges:path_.length-1,oxygen_integral_g:o2,time_integral_s:time,synthetic_event:{cell:blocked,before:compact(before),after:compact(after)},elapsed_s:(performance.now()-start)/1000,scope:'Actual packaged Jezero grid and actual worker, executed in Node VM; not browser rendering or device timing'};
  await fs.writeFile(reportPath,JSON.stringify(result,null,2));return {...result,written:{mission:missionPath,report:reportPath,published:publish}};
}
