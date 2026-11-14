// Rebuild the UI against already packaged data, without Python/GIS dependencies.
// Terrain/photo/map payloads come from the read-only seed in data/packed_seed (see packed_seed.mjs);
// the generated reports HTML is output only. Does not regenerate or alter scientific payloads.
import fs from 'node:fs/promises';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';
import { loadSeed, sha256, modelSourceHash } from './packed_seed.mjs';

// Connectivity is only trusted when it was computed on this grid payload, with this model source,
// from this base. Otherwise reachability is unknown (null), never "unreachable".
export function connectivityStatus(report, {gridHash, modelHash, baseCell}) {
  const p = report?.provenance;
  if (!p) return {trusted: false, reason: 'connectivity report has no provenance'};
  if (p.grid_payload_sha256 !== gridHash) return {trusted: false, reason: 'grid payload hash differs'};
  if (p.model_source_sha256 !== modelHash) return {trusted: false, reason: 'model source hash differs'};
  if (p.base !== baseCell) return {trusted: false, reason: 'base cell differs'};
  if (p.strict !== true || p.overlay_revision !== 0) return {trusted: false, reason: 'not the default strict / overlay-0 graph'};
  return {trusted: true, reason: null};
}

export async function buildUI(root, {outDir = path.join(root, 'reports')} = {}) {
  const seed = await loadSeed(root);
  const template = await fs.readFile(path.join(root, 'code/demo_template.html'), 'utf8');
  const inputs = {seed_manifest: seed.manifest.files, template: sha256(template)};
  async function addFullPhotos(meta) {
    for(const p of meta.photos||[]) {
      const filename='sol'+String(p.sol).padStart(4,'0')+'.png';
      try {
        const bytes=await fs.readFile(path.join(root,'data/downloaded/ui_support/visor',meta.site.id,filename));
        if(bytes.subarray(1,4).toString()!=='PNG')throw Error('Invalid visor PNG: '+filename);
        p.full_img='data:image/png;base64,'+bytes.toString('base64');
        p.full_width=bytes.readUInt32BE(16);p.full_height=bytes.readUInt32BE(20);
        p.full_source_url=p.url.replace('_800.jpg','.png');
      } catch(e) {if(e.code!=='ENOENT')throw e;}
    }
    return meta;
  }
  const meta=await addFullPhotos(seed.meta);
  const worldText=await fs.readFile(path.join(root,'code/global_map.json'),'utf8');inputs.global_map=sha256(worldText);
  meta.world=JSON.parse(worldText);
  const sites=seed.sites;let connectivity=null;
  for(const site of sites){await addFullPhotos(site.meta);if(site.meta.site.id==='jezero'){
    const dir=path.join(root,'outputs/local_terrain/jezero');
    const read=async rel=>{const text=await fs.readFile(path.join(root,rel),'utf8');inputs[rel]=sha256(text);return JSON.parse(text);};
    const manifest=await read('outputs/local_terrain/jezero/manifest.json');
    const stationData=await read('outputs/local_terrain/jezero/stations.json');
    const report=await read('reports/packaged-grid-validation.json');
    const baseCell=site.meta.base[1]*site.meta.cols+site.meta.base[0];
    connectivity=connectivityStatus(report,{gridHash:sha256(site.data),modelHash:modelSourceHash(template),baseCell});
    for(const t of stationData.targets){
      const checked=connectivity.trusted?report.reachable_targets.find(r=>r.id===t.id):null;
      t.default_base_reachable=checked?checked.reachable:null;
    }
    site.meta.targets=site.meta.targets.filter(t=>t.source_kind!=='places_station').concat(stationData.targets);
    site.meta.evidenceMission=await read('outputs/local_terrain/jezero/mission.json');
    const preview=await fs.readFile(path.join(dir,manifest.assets.preview));inputs['outputs/local_terrain/jezero/'+manifest.assets.preview]=sha256(preview);
    site.meta.localTerrain={...manifest,preview:'data:image/svg+xml;base64,'+preview.toString('base64')};
  }}
  const json=value=>JSON.stringify(value).replace(/<\//g,'<\\/');
  let html=template;
  const src=async rel=>{const t=await fs.readFile(path.join(root,rel),'utf8');inputs[rel]=sha256(t);return t;};
  const parts={'__META__':json(meta),'__DATA__':seed.blob,'__SITES__':json(sites),'__SHADE__':seed.shade,'__ORTHO__':seed.ortho,
    '/*__I18N__*/':await src('code/i18n_en.js'),
    '/*__MAP_UI_CSS__*/':await src('code/map_ui.css'),
    '/*__MAP_UI__*/':(await src('code/map_ui_policy.js'))+'\n'+(await src('code/map_ui.js'))};
  for(const [key,val] of Object.entries(parts)){if(html.split(key).length!==2)throw Error('Placeholder count '+key);html=html.replace(key,()=>val);}
  if(/\/\*__MAP_UI/.test(html))throw Error('Unresolved UI placeholder');
  const scripts=[...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)];
  for(const m of scripts){if(!/type="application\/(json|octet-stream)"/.test(m[0].slice(0,m[0].indexOf('>'))))new vm.Script(m[1]);}
  await fs.mkdir(outDir,{recursive:true});
  await fs.writeFile(path.join(outDir,'18-eva-walkback-demo.html'),html);await fs.writeFile(path.join(outDir,'18-eva-walkback-demo.standalone.html'),html);
  return {bytes:Buffer.byteLength(html),html_sha256:sha256(html),payloadSource:'data/packed_seed (hash-verified)',
    fullResolutionPhotos:sites.reduce((n,s)=>n+(s.meta.photos||[]).filter(p=>p.full_img).length,0),
    connectivity,scriptSyntax:'pass',inputs};
}
if(typeof process !== 'undefined' && process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))console.log(await buildUI(path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')));
