import fs from 'node:fs/promises';
import vm from 'node:vm';
import assert from 'node:assert/strict';
export async function runPythonReference(root){
  const ref=JSON.parse(await fs.readFile(root+'/tests/fixtures/jezero_model_reference.json','utf8'));
  const C=JSON.parse(await fs.readFile(root+'/tests/fixtures/packaged_model_constants.json','utf8'));
  const template=await fs.readFile(root+'/code/demo_template.html','utf8');
  const source=template.slice(template.indexOf('  function MAKE_MODEL('),template.indexOf('  let MD ='));
  const G={C,SP:{},SAND:{a:1.5,b:1.3,v_floor_m_s:.85},ETA_ADD:.2,ETA:[1,1],FLAGS:[9,9],H:[0,0]};
  const context={G};vm.runInNewContext(source+';model=MAKE_MODEL(G,{});',context);
  let worst=0;const match=(a,b)=>{const error=Math.abs(a-b)/Math.max(1e-8,Math.abs(b));worst=Math.max(worst,error);assert.ok(error<=1e-6,`${a} != ${b}, relative error ${error}`);};
  for(const row of ref.rows){G.H[1]=row.grade/100*row.distance;G.ETA.fill(row.eta);const m=context.model;m.edge(0,1,row.distance);match(m.speed(row.grade),row.speed);match(m.out.t,row.seconds);match(m.out.o2,row.oxygen_g);match(m.out.o2/C.o2_g_per_j/m.out.t,row.watts);match((m.out.o2/C.o2_g_per_j+row.heat*m.out.t)/C.latent_j_kg*1000,row.water_g);match(m.out.o2+m.out.t*10/3600,row.known_leak_10g_h_total_o2_g);}
  const result={rows:ref.rows.length,comparisons:ref.rows.length*6,worst_relative_error:worst,source_sha256:ref.source_sha256,python:ref.python,numpy:ref.numpy,status:'pass'};
  await fs.writeFile(root+'/reports/python-js-model-validation.json',JSON.stringify(result,null,2));return result;
}
