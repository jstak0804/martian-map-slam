// H0 regression checks: read-only seed, connectivity provenance, overwrite guards, package freshness.
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { loadSeed, SEED_DIR, sha256, modelSourceHash } from '../code/packed_seed.mjs';
import { connectivityStatus } from '../code/build_ui_preview.mjs';
import { assertReplaceable, COMMON_FRAME_MESH_IDS } from '../code/build_observation_evidence.mjs';
import { checkFreshness } from '../code/package_review.mjs';

export async function runH0Tests(root) {
  let passed = 0; const check = async (name, f) => { try { await f(); passed++; } catch (e) { e.message = name + ': ' + e.message; throw e; } };
  const seed = await loadSeed(root);
  const jez = seed.sites.find(s => s.meta.site.id === 'jezero');
  const template = await fs.readFile(path.join(root, 'code/demo_template.html'), 'utf8');

  await check('seed hashes verified on load', () => assert.ok(seed.manifest.files['blob.b64'].sha256.length === 64));
  await check('seed holds no build-derived fields', () => {
    const photos = [seed.meta, ...seed.sites.map(s => s.meta)].flatMap(m => m.photos || []);
    assert.ok(photos.every(p => !('full_img' in p)));
    assert.equal(seed.meta.world ?? null, null);
    assert.ok(seed.sites.every(s => (s.meta.targets || []).every(t => t.source_kind !== 'places_station')));
    assert.ok(seed.sites.every(s => (s.meta.localTerrain ?? null) === null && (s.meta.evidenceMission ?? null) === null));
  });
  await check('seed site IDs and grid sizes recorded', () => {
    for (const s of seed.manifest.sites) { const site = seed.sites.find(x => x.meta.site.id === s.id); assert.ok(site); assert.equal(sha256(site.data), s.data_sha256); assert.equal(site.meta.rows, s.rows); }
  });
  await check('tampered seed is rejected', async () => {
    const tmp = await fs.mkdtemp(path.join(os.tmpdir(), 'seed-')); const dir = path.join(tmp, SEED_DIR);
    await fs.mkdir(dir, {recursive: true});
    for (const f of await fs.readdir(path.join(root, SEED_DIR))) await fs.copyFile(path.join(root, SEED_DIR, f), path.join(dir, f));
    await fs.appendFile(path.join(dir, 'shade.txt'), 'x');
    await assert.rejects(loadSeed(tmp), /hash mismatch/);
    await fs.rm(tmp, {recursive: true});
  });
  await check('missing seed is an explicit error, not an HTML fallback', async () => {
    const tmp = await fs.mkdtemp(path.join(os.tmpdir(), 'noseed-'));
    await assert.rejects(loadSeed(tmp), /Packed seed missing/); await fs.rm(tmp, {recursive: true});
  });

  const ok = {gridHash: sha256(jez.data), modelHash: modelSourceHash(template), baseCell: jez.meta.base[1] * jez.meta.cols + jez.meta.base[0]};
  const prov = {grid_payload_sha256: ok.gridHash, model_source_sha256: ok.modelHash, base: ok.baseCell, strict: true, overlay_revision: 0};
  await check('matching connectivity provenance is trusted', () => assert.equal(connectivityStatus({provenance: prov}, ok).trusted, true));
  for (const [name, mutate] of [['no provenance', r => delete r.provenance], ['other grid', r => r.provenance.grid_payload_sha256 = '0'],
    ['other model', r => r.provenance.model_source_sha256 = '0'], ['other base', r => r.provenance.base = 1], ['overlay applied', r => r.provenance.overlay_revision = 1]]) {
    await check('connectivity rejected: ' + name, () => { const r = {provenance: {...prov}}; mutate(r); assert.equal(connectivityStatus(r, ok).trusted, false); });
  }
  await check('model hash changes when worker source changes', () => assert.notEqual(modelSourceHash(template.replace('function WORKER_MAIN()', 'function WORKER_MAIN() /*changed*/')), ok.modelHash));

  await check('local-only manifest may be regenerated', async () => {
    const tmp = await fs.mkdtemp(path.join(os.tmpdir(), 'man-')), f = path.join(tmp, 'manifest.json');
    await assertReplaceable(f);
    await fs.writeFile(f, JSON.stringify({status: 'local_only', grid_registration: null, observed_cells: [], blocked_cells: []}));
    await assertReplaceable(f);
    await fs.writeFile(f, JSON.stringify({status: 'registered', grid_registration: {control_count: 3}, observed_cells: [1], blocked_cells: []}));
    await assert.rejects(assertReplaceable(f), /Refusing to overwrite/);
    await fs.rm(tmp, {recursive: true});
  });
  await check('mesh selection is the explicit ID list in the manifest', async () => {
    const m = JSON.parse(await fs.readFile(path.join(root, 'outputs/local_terrain/jezero/manifest.json'), 'utf8'));
    assert.deepEqual(m.source_products.map(p => p.id), COMMON_FRAME_MESH_IDS);
    assert.ok(COMMON_FRAME_MESH_IDS.every(id => !id.includes('::')), 'IDs are LIDs without version');
  });

  const v = {status: 'pass', html_sha256: 'a'.repeat(64)};
  await check('package accepts matching validation', () => assert.deepEqual(checkFreshness(v, 'a'.repeat(64), {trusted: true}), []));
  await check('package rejects stale validation', () => assert.ok(checkFreshness(v, 'b'.repeat(64), {trusted: true}).length));
  await check('package rejects legacy validation without hash', () => assert.ok(checkFreshness({status: 'pass'}, 'a'.repeat(64), {trusted: true}).length));
  await check('package rejects untrusted connectivity', () => assert.ok(checkFreshness(v, 'a'.repeat(64), {trusted: false, reason: 'x'}).length));
  return {passed, scope: 'H0 seed integrity, connectivity provenance, overwrite guards, package freshness'};
}
