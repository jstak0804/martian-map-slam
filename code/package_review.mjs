import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {loadSeed,modelSourceHash} from './packed_seed.mjs';
import {connectivityStatus} from './build_ui_preview.mjs';
const digest=b=>crypto.createHash('sha256').update(b).digest('hex');
// H0: never package an HTML with a success report produced for a different HTML or grid/model.
export function checkFreshness(validation,htmlSha,connectivity){
  const errors=[];
  if(validation?.status!=='pass')errors.push('automated-validation.json is not a passing run');
  if(validation?.html_sha256!==htmlSha)errors.push('automated-validation.json was produced for a different HTML');
  if(!connectivity?.trusted)errors.push('packaged-grid-validation.json does not match this grid/model/base: '+(connectivity?.reason??'unknown'));
  return errors;
}
export async function packageReview(root){
  const html0=await fs.readFile(path.join(root,'reports/18-eva-walkback-demo.html'));
  const validation=JSON.parse(await fs.readFile(path.join(root,'reports/automated-validation.json'),'utf8'));
  const seed=await loadSeed(root),jez=seed.sites.find(s=>s.meta.site.id==='jezero');
  const grid=JSON.parse(await fs.readFile(path.join(root,'reports/packaged-grid-validation.json'),'utf8'));
  const conn=connectivityStatus(grid,{gridHash:digest(jez.data),modelHash:modelSourceHash(await fs.readFile(path.join(root,'code/demo_template.html'),'utf8')),baseCell:jez.meta.base[1]*jez.meta.cols+jez.meta.base[0]});
  const stale=checkFreshness(validation,digest(html0),conn);if(stale.length)throw Error('Refusing to package: '+stale.join('; '));
  const dest=path.join(root,'dist/jezero-demo');await fs.mkdir(dest,{recursive:true});
  const files=new Map([
    ['reports/18-eva-walkback-demo.html','index.html'],
    ['reports/jezero-validation.md','validation.md'],
    ['reports/jezero-demo-script.md','demo-script.md'],
    ['reports/automated-validation.json','automated-validation.json'],
    ['reports/packaged-grid-validation.json','packaged-grid-validation.json'],
    ['reports/python-js-model-validation.json','python-js-model-validation.json'],
    ['tests/fixtures/jezero_model_reference.json','python-reference.json'],
    ['outputs/global_mars/catalog.json','global-catalog.json'],
    ['data/jezero_observations/catalog.json','observation-catalog.json'],
    ['outputs/local_terrain/jezero/manifest.json','local/manifest.json'],
    ['outputs/local_terrain/jezero/mission.json','local/mission.json'],
    ['outputs/local_terrain/jezero/stations.json','local/stations.json'],
    ['outputs/local_terrain/jezero/common-frame-preview.svg','local/common-frame-preview.svg'],
    ['outputs/local_terrain/jezero/common-frame-points.json','local/common-frame-points.json'],
  ]);
  const records=[];
  for(const [src,out] of files){const bytes=await fs.readFile(path.join(root,src));await fs.mkdir(path.dirname(path.join(dest,out)),{recursive:true});await fs.writeFile(path.join(dest,out),bytes);records.push({path:out,bytes:bytes.length,sha256:digest(bytes)});}
  const catalog=JSON.parse(await fs.readFile(path.join(root,'data/jezero_observations/catalog.json'),'utf8'));
  const local=JSON.parse(await fs.readFile(path.join(root,'outputs/local_terrain/jezero/manifest.json'),'utf8'));const used=new Set(local.source_products.map(p=>p.id));
  const rows=[['product_id','url','sha256','use','credit'],...catalog.products.map(p=>[p.id,p.url??'',p.sha256,used.has(p.id)?'local_vertex_composite':'metadata_catalog','NASA/JPL-Caltech'])];
  const html=await fs.readFile(path.join(root,'reports/18-eva-walkback-demo.html'),'utf8');
  const value=id=>JSON.parse(html.match(new RegExp('<script[^>]*id="'+id+'"[^>]*>([\\s\\S]*?)<\\/script>'))[1]);
  for(const m of [value('meta'),...value('sites').map(s=>s.meta)])for(const p of m.photos||[]){const image=p.full_img||p.img;if(image)rows.push([m.site.id+' photo sol '+p.sol,p.full_source_url||p.url||'',digest(Buffer.from(image.split(',')[1],'base64')),'packaged_rover_photo','NASA/JPL-Caltech']);}
  const layer='Mars_MGS_MOLA_ClrShade_merge_global_463m';for(let r=0;r<4;r++)for(let c=0;c<8;c++){const file=path.join(root,'data/downloaded/maps',layer,'2',r+'_'+c+'.jpg');rows.push([layer+'/2/'+r+'/'+c,'https://trek.nasa.gov/tiles/Mars/EQ/'+layer+'/1.0.0/default/default028mm/2/'+r+'/'+c+'.jpg',digest(await fs.readFile(file)),'global_overview','NASA/JPL Mars Trek']);}
  const csv=rows.map(row=>row.map(s=>'"'+String(s).replaceAll('"','""')+'"').join(',')).join('\n')+'\n';
  await fs.writeFile(path.join(root,'reports/jezero-sources.csv'),csv);await fs.writeFile(path.join(dest,'sources.csv'),csv);records.push({path:'sources.csv',bytes:Buffer.byteLength(csv),sha256:digest(csv)});
  const readme=`# Martian Map — local review package\n\nOpen index.html in Chrome or Edge. Use index.html#mars for global context, or index.html#jezero-evidence-demo for the fixed two-site demonstration. Display data are embedded; source links require internet.\n\nThis is a local review artifact, not a published submission. Read validation.md for executed checks and remaining gates. Browser/device QA, independent orbital registration, a new screen recording and redistribution/license review remain open. No registered ground coverage or measured terrain blockage is claimed.\n\nObservations contains a two-product PDS vertex composite in its original local frame. Navcam stations disconnected from the default base are observation-only. Block test is synthetic.\n\nThe complete research archive remains in data/downloaded and is not duplicated here. sources.csv distinguishes metadata-only products from products actually displayed or combined. hashes.json identifies the packaged files.\n`;
  await fs.writeFile(path.join(dest,'README.md'),readme);records.push({path:'README.md',bytes:Buffer.byteLength(readme),sha256:digest(readme)});
  const baseline=JSON.parse(await fs.readFile(path.join(root,'reports/ui-baseline-provenance.json'),'utf8'));
  if(!/^[0-9a-f]{64}$/.test(baseline.sha256))throw Error('Invalid baseline provenance hash');
  const metadata={generated_at:new Date().toISOString(),purpose:'local review; not published',baseline_sha256:baseline.sha256,files:records};
  await fs.writeFile(path.join(dest,'hashes.json'),JSON.stringify(metadata,null,2));
  return {directory:dest,files:records.length+1,bytes:records.reduce((sum,f)=>sum+f.bytes,0),html_sha256:records.find(r=>r.path==='index.html').sha256,source_rows:rows.length-1};
}
