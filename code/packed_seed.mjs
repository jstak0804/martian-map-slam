// H0: read-only packed seed for the UI build.
// The terrain/photo/map payloads used to be read back from the generated reports HTML,
// which made the output also the input. extractSeed() copies the current payload once into
// data/packed_seed/ with build-derived fields removed; loadSeed() verifies the seed hashes
// before every build. Raw-DTM regeneration is still out of scope (code/build_demo_html.py).
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';

export const SEED_DIR = 'data/packed_seed';
const FILES = {meta: 'meta.json', sites: 'sites.json', blob: 'blob.b64', shade: 'shade.txt', ortho: 'ortho.txt'};
const PHOTO_DERIVED = ['full_img', 'full_width', 'full_height', 'full_source_url'];
export const sha256 = b => crypto.createHash('sha256').update(b).digest('hex');

export function packedValue(html, id) {
  const m = html.match(new RegExp('<script[^>]*id="' + id + '"[^>]*>([\\s\\S]*?)<\\/script>'));
  if (!m) throw Error('Missing packaged ' + id);
  return m[1];
}

// Source slices that define the route model and graph search. Shared by the grid check and
// the build so a connectivity report can be matched to the exact model it was computed with.
export function modelSource(template) {
  const slice = (a, b) => {
    const i = template.indexOf(a), j = template.indexOf(b, i);
    if (i < 0 || j < 0) throw Error('Model source marker missing: ' + a);
    return template.slice(i, j);
  };
  return slice('  function MAKE_MODEL(', '  let MD =') + slice('  function WORKER_MAIN()', '  let WK =');
}
export const modelSourceHash = template => sha256(modelSource(template));

function stripPhotos(meta) {
  for (const p of meta.photos || []) for (const k of PHOTO_DERIVED) delete p[k];
}

// Keys are set to null (not deleted) so that buildUI re-fills them at the same JSON position.
function stripDerived(meta, sites) {
  stripPhotos(meta);
  if ('world' in meta) meta.world = null;
  for (const s of sites) {
    stripPhotos(s.meta);
    s.meta.targets = (s.meta.targets || []).filter(t => t.source_kind !== 'places_station');
    if ('localTerrain' in s.meta) s.meta.localTerrain = null;
    if ('evidenceMission' in s.meta) s.meta.evidenceMission = null;
  }
}

export async function extractSeed(root, {fromHtml = 'reports/18-eva-walkback-demo.html', force = false} = {}) {
  const dir = path.join(root, SEED_DIR);
  if (!force) {
    try { await fs.access(path.join(dir, 'seed-manifest.json')); throw Error('Seed already exists; pass force:true to replace it'); }
    catch (e) { if (e.code !== 'ENOENT') throw e; }
  }
  const src = path.join(root, fromHtml), html = await fs.readFile(src, 'utf8');
  const meta = JSON.parse(packedValue(html, 'meta')), sites = JSON.parse(packedValue(html, 'sites'));
  const shade = html.match(/shade: "(data:image\/png;base64,[^"]+)"/), ortho = html.match(/ortho: "(data:image\/jpeg;base64,[^"]+)"/);
  if (!shade || !ortho) throw Error('Missing packaged map images');
  stripDerived(meta, sites);
  const content = {meta: JSON.stringify(meta), sites: JSON.stringify(sites), blob: packedValue(html, 'blob'), shade: shade[1], ortho: ortho[1]};
  await fs.mkdir(dir, {recursive: true});
  const files = {};
  for (const [k, name] of Object.entries(FILES)) {
    await fs.writeFile(path.join(dir, name), content[k]);
    files[name] = {bytes: Buffer.byteLength(content[k]), sha256: sha256(content[k])};
  }
  const manifest = {
    schema_version: 1,
    extracted_from: fromHtml,
    extracted_from_sha256: sha256(await fs.readFile(src)),
    extracted_at: new Date().toISOString(),
    stripped: {photos: PHOTO_DERIVED, meta: ['world'], sites: ['targets[source_kind=places_station]', 'localTerrain', 'evidenceMission']},
    sites: sites.map(s => ({id: s.meta.site.id, rows: s.meta.rows, cols: s.meta.cols, data_sha256: sha256(s.data)})),
    main_site: meta.site?.id ?? null,
    files,
    note: 'Read-only build input. Do not edit by hand; regenerate only with extractSeed({force:true}) and record why.',
  };
  await fs.writeFile(path.join(dir, 'seed-manifest.json'), JSON.stringify(manifest, null, 2));
  return {dir, files, sites: manifest.sites.map(s => s.id)};
}

export async function loadSeed(root) {
  const dir = path.join(root, SEED_DIR);
  let manifest;
  try { manifest = JSON.parse(await fs.readFile(path.join(dir, 'seed-manifest.json'), 'utf8')); }
  catch (e) { if (e.code === 'ENOENT') throw Error('Packed seed missing: run extractSeed(root) once from a known-good HTML'); throw e; }
  const raw = {};
  for (const [k, name] of Object.entries(FILES)) {
    raw[k] = await fs.readFile(path.join(dir, name), 'utf8');
    if (sha256(raw[k]) !== manifest.files[name].sha256) throw Error('Packed seed hash mismatch: ' + name);
  }
  return {manifest, meta: JSON.parse(raw.meta), sites: JSON.parse(raw.sites), blob: raw.blob, shade: raw.shade, ortho: raw.ortho};
}
