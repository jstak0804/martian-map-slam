import fs from 'node:fs/promises';
import {createReadStream} from 'node:fs';
import {createInterface} from 'node:readline';
import crypto from 'node:crypto';
import path from 'node:path';
import zlib from 'node:zlib';
import {loadSeed} from './packed_seed.mjs';

const tag=(xml,name)=>xml.match(new RegExp('<(?:\\w+:)?'+name+'(?:\\s[^>]*)?>([^<]*)</'))?.[1]?.trim()??null;
export function parseLabel(xml) {
  const counters={};
  for(const m of xml.matchAll(/<geom:Motion_Counter_Index>([\s\S]*?)<\/geom:Motion_Counter_Index>/g))counters[tag(m[1],'index_id')]=Number(tag(m[1],'index_value_number'));
  const reference=xml.match(/<img_surface:Derived_Product_Parameters>([\s\S]*?)<\/img_surface:Derived_Product_Parameters>/)?.[1]??'';
  return {id:tag(xml,'logical_identifier'),utc:tag(xml,'start_date_time'),camera_model:tag(xml,'model_type'),site_drive:[counters.site??null,counters.drive??null],pose:counters.pose??null,frame_id:tag(reference,'coordinate_space_frame_type'),frame_index:tag(reference,'index_value_number'),source_ids:[...xml.matchAll(/<lidvid_reference>([^<]+)<\/lidvid_reference>/g)].map(m=>m[1]),grid_registration:null};
}
export function validateRegistration(m,cellM=10) {
  if(m.status!=='registered')return m.blocked_cells?.length?['Unregistered geometry cannot block map cells']:[];
  const r=m.grid_registration,errors=[];
  if(m.units!=='m')errors.push('Units must be meters');
  if(!r||r.control_count<3||r.holdout_count<2||!Number.isFinite(r.holdout_rmse_m)||r.holdout_rmse_m>cellM/2||!Number.isFinite(r.holdout_max_m)||r.holdout_max_m>cellM)errors.push('Independent registration evidence missing or outside tolerance');
  if(!r?.transform||!r?.method)errors.push('Explicit coordinate transform required');
  return errors;
}
async function hash(file){const h=crypto.createHash('sha256');for await(const b of createReadStream(file))h.update(b);return h.digest('hex');}
// Explicit source selection (H0). IDs are PDS4 LIDs (logical_identifier, no ::version). The
// downloaded set holds one version per LID; if a second version ever appears, buildEvidence fails
// instead of silently choosing one, and the selection rule must be recorded here.
export const COMMON_FRAME_MESH_IDS=[
  'urn:nasa:pds:mars2020_navcam_ops_mesh:data:nlf_0443_0706278524m049ras_n0250214ncam00708_0a0085j.obj',
  'urn:nasa:pds:mars2020_navcam_ops_mesh:data:nlf_0443_0706278950m149ras_n0250214ncam03443_0a0195j.obj',
];
// A manifest that carries registration evidence is never replaced by this local-only builder.
export async function assertReplaceable(manifestPath){
  let m;try{m=JSON.parse(await fs.readFile(manifestPath,'utf8'));}catch(e){if(e.code==='ENOENT')return;throw e;}
  if(m.status!=='local_only'||m.grid_registration!==null||m.observed_cells?.length||m.blocked_cells?.length)
    throw Error('Refusing to overwrite '+manifestPath+': it holds registration/mask results ('+m.status+'). Write registration to a separate registration.json.');
}
export async function buildEvidence(root,{outDir=path.join(root,'outputs/local_terrain/jezero'),catalogPath=path.join(root,'data/jezero_observations/catalog.json')}={}) {
  const started=performance.now(),base=path.join(root,'data/downloaded'),out=outDir;
  await assertReplaceable(path.join(out,'manifest.json'));
  await fs.mkdir(out,{recursive:true});await fs.mkdir(path.dirname(catalogPath),{recursive:true});
  const sourceMap=new Map();
  for(const file of await fs.readdir(path.resolve(root,'../research'))){if(!/manifest\.json$/.test(file))continue;try{const a=JSON.parse((await fs.readFile(path.resolve(root,'../research',file),'utf8')).replace(/^\uFEFF/,''));if(Array.isArray(a))for(const e of a)if(e.path&&e.url)sourceMap.set(e.path.replaceAll('\\','/'),e.url);}catch{}}
  const products=[];
  for(const kind of ['raw','mesh']){
    const folder=path.join(base,'navcam/sol00443',kind);
    for(const name of await fs.readdir(folder)){if(!name.endsWith('.xml'))continue;const xml=await fs.readFile(path.join(folder,name),'utf8'),record=parseLabel(xml);const filename=tag(xml,'file_name');
      if(!record.id||!filename)continue;
      const rel='navcam/sol00443/'+kind+'/'+filename;
      products.push({...record,sol:443,waypoint_sol:null,product_kind:kind,filename,path:rel,url:sourceMap.get(rel)??null,label_url:sourceMap.get('navcam/sol00443/'+kind+'/'+name)??null,credit:'NASA/JPL-Caltech',sha256:await hash(path.join(base,rel)),image_registration:'unverified'});
    }
  }
  const byId=new Map();for(const p of products){if(byId.has(p.id)&&byId.get(p.id).sha256!==p.sha256)throw Error('Two different files share LID '+p.id+'; define a version rule');byId.set(p.id,p);}
  const unique=[...byId.values()];
  const rows=(await fs.readFile(path.join(base,'places/best_interp.csv'),'utf8')).trim().split(/\r?\n/);const header=rows.shift().trim().split(',');
  const places=rows.map(r=>Object.fromEntries(r.split(',').map((v,i)=>[header[i],v]))).filter(r=>r.frame==='ROVER'&&r.site==='25'&&['94','214'].includes(r.drive));
  const meshes=unique.filter(p=>p.product_kind==='mesh'&&p.frame_id==='SITE_FRAME'&&p.frame_index==='25');
  // Preserve the source coordinate frame; decimate vertices, never invent a map registration.
  const chosen=COMMON_FRAME_MESH_IDS.map(id=>meshes.find(p=>p.id===id));
  if(chosen.some(p=>!p))throw Error('Selected common-frame mesh missing or not SITE_FRAME 25: '+COMMON_FRAME_MESH_IDS.filter((id,i)=>!chosen[i]).join(', '));
  const clouds=[];let vertices=0;
  for(const p of chosen){const points=[];let count=0;const lines=createInterface({input:createReadStream(path.join(base,p.path)),crlfDelay:Infinity});for await(const line of lines){if(!line.startsWith('v ' )&&!line.startsWith('v\t'))continue;const xyz=line.trim().split(/\s+/).slice(1,4).map(Number);if(xyz.length===3&&xyz.every(Number.isFinite)){if(count++%30===0)points.push(xyz);}}vertices+=count;clouds.push({id:p.id,vertex_count:count,points});}
  const all=clouds.flatMap(c=>c.points),bounds=[0,1,2].map(axis=>[Math.min(...all.map(p=>p[axis])),Math.max(...all.map(p=>p[axis]))]);
  const common=new Map();clouds.forEach((c,k)=>{for(const p of c.points){const key=Math.floor(p[0])+','+Math.floor(p[1]);const a=common.get(key)||[[],[]];a[k].push(p[2]);common.set(key,a);}});
  const median=a=>{a.sort((x,y)=>x-y);return a[Math.floor(a.length/2)];};
  const residuals=[...common.values()].filter(a=>a.every(v=>v.length)).map(a=>Math.abs(median(a[0])-median(a[1])));
  const span=Math.max(bounds[0][1]-bounds[0][0],bounds[1][1]-bounds[1][0],1),scale=900/span;
  const circles=clouds.map((c,k)=>'<g fill="'+['#70c9ee','#f4b576'][k]+'" fill-opacity=".5">'+c.points.map(p=>'<circle cx="'+(50+(p[1]-bounds[1][0])*scale).toFixed(2)+'" cy="'+(950-(p[0]-bounds[0][0])*scale).toFixed(2)+'" r="1.2"/>').join('')+'</g>').join('');
  const svg='<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024"><rect width="1024" height="1024" fill="#10202c"/>'+circles+'<text x="20" y="28" fill="white" font-size="17">PDS mesh vertices · SITE_FRAME 25 · two observations</text><text x="20" y="1008" fill="white" font-size="15">Local coordinates only · no orbital registration · colors identify source products</text></svg>';
  await fs.writeFile(path.join(out,'common-frame-preview.svg'),svg);await fs.writeFile(path.join(out,'common-frame-points.json'),JSON.stringify({frame_id:'SITE_FRAME:25',clouds,bounds}));
  const manifest={schema_version:1,site_id:'jezero',status:'local_only',source_products:chosen,station_ids:[...new Set(chosen.map(p=>p.site_drive.join(':')))],frame_id:'SITE_FRAME:25',units:'m',grid_registration:null,quality:{input_image_count:new Set(unique.filter(p=>p.product_kind==='raw').map(p=>p.filename.match(/^([A-Z]{3}_\d{4}_\d{10})[_M](\d{3})/)?.slice(1).join('_'))).size,input_product_count:unique.filter(p=>p.product_kind==='raw').length,used_image_count:0,stereo_pair_count:0,source_mesh_count:2,source_vertex_count:vertices,preview_vertex_count:all.length,shared_1m_xy_bins:residuals.length,median_bin_height_difference_m:residuals.length?median(residuals):null,registration_rmse_m:null,reprojection_median_px:null,runtime_s:(performance.now()-started)/1000,processing_device:'CPU / Node streaming parser',peak_rss_mb:null,peak_vram_mb:null},assets:{preview:'common-frame-preview.svg',mesh:'common-frame-points.json',panorama:null,coverage_preview:null},observed_cells:[],blocked_cells:[],unknown_reason:'No independent orbital registration control/holdout points. Height-bin differences are not registration accuracy.',localization_candidates:places};
  const catalog={schema_version:1,products:unique,stations:places,registration_status:'unverified',source:'Downloaded PDS4 labels and PLACES best_interp; site-drive join, not image registration'};
  await fs.writeFile(path.join(out,'manifest.json'),JSON.stringify(manifest,null,2));await fs.writeFile(catalogPath,JSON.stringify(catalog,null,2));
  return {products:unique.length,meshes:meshes.length,used:chosen.length,vertices,preview:all.length,sharedBins:residuals.length,runtime_s:manifest.quality.runtime_s};
}

export async function buildStationCandidates(root,{outDir=path.join(root,'outputs/local_terrain/jezero')}={}){
  const dir=outDir;await fs.mkdir(dir,{recursive:true});
  const catalog=JSON.parse(await fs.readFile(path.join(root,'data/jezero_observations/catalog.json'),'utf8'));
  const f=await fs.open(path.join(root,'data/downloaded/hirise_jezero/DTEEC_045994_1985_046060_1985_U01.IMG'));
  const bytes=Buffer.alloc(30000);try{await f.read(bytes,0,bytes.length,0);}finally{await f.close();}
  const label=bytes.toString('ascii'),value=name=>Number(label.match(new RegExp('^\\s*'+name+'\\s*=\\s*([-+0-9.eE]+)','m'))?.[1]);
  const site=(await loadSeed(root)).sites.find(s=>s.meta.site.id==='jezero');
  const data=zlib.gunzipSync(Buffer.from(site.data,'base64')),meta=site.meta;
  const read=name=>data.subarray(meta.layout[name][0],meta.layout[name][0]+meta.layout[name][1]);const flags=read('flags'),cls=read('cls');
  const targets=catalog.stations.map(r=>{
    const lat=Number(r.planetocentric_latitude),lon=Number(r.longitude),radius=value('A_AXIS_RADIUS')*1000;
    const x=(value('SAMPLE_PROJECTION_OFFSET')+radius*(lon-value('CENTER_LONGITUDE'))*Math.PI/180*Math.cos(value('CENTER_LATITUDE')*Math.PI/180)/value('MAP_SCALE'))/10;
    const y=(value('LINE_PROJECTION_OFFSET')-radius*lat*Math.PI/180/value('MAP_SCALE'))/10;
    if(![x,y].every(Number.isFinite))throw Error('Missing DTM projection metadata');
    let approach=null;
    for(let dy=-3;dy<=3;dy++)for(let dx=-3;dx<=3;dx++){const xx=Math.floor(x)+dx,yy=Math.floor(y)+dy,c=yy*meta.cols+xx,d=Math.hypot(xx+.5-x,yy+.5-y)*meta.cell_m;
      if(xx>=0&&xx<meta.cols&&yy>=0&&yy<meta.rows&&(flags[c]&8)&&cls[c]!==2&&(!approach||d<approach.offset_m))approach={x:xx+.5,y:yy+.5,offset_m:d};}
    if(!approach)throw Error('No terrain-valid approach cell for station '+r.site+'/'+r.drive);
    return {id:'navcam-'+r.site+'-'+r.drive,name:'Navcam station '+r.site+'/'+r.drive,name_en:'Navcam station '+r.site+'/'+r.drive,source_kind:'places_station',x:approach.x,y:approach.y,sols:[Number(r.sol)],samples:[],station:{site:Number(r.site),drive:Number(r.drive),observation_lon:lon,observation_lat:lat,observation_grid:{x,y},approach_offset_m:approach.offset_m,grid_method:'HiRISE DTM label equirectangular inverse; 10-pixel block; crop origin 0,0',image_registration:null},why_en:'PLACES rover localization; approach cell is distinct from camera position. Image-to-orbit registration is unverified.',source:'PDS PLACES best_interp.csv + HiRISE DTEEC_045994_1985_046060_1985_U01 label'};
  });
  await fs.writeFile(path.join(dir,'stations.json'),JSON.stringify({schema_version:1,projection_label:'DTEEC_045994_1985_046060_1985_U01.IMG',source_places:'places/best_interp.csv',targets},null,2));return {targets:targets.length};
}
