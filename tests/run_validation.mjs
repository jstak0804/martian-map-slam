// Single validation runner (H0-6).
//   node tests/run_validation.mjs            build + UI/remaining/python checks + grid check in a temp dir
//   node tests/run_validation.mjs --publish-grid   also publish mission.json + connectivity, then rebuild
//   node tests/run_validation.mjs --reproduce      also build twice into temp dirs and compare bytes
//   node tests/run_validation.mjs --package        package dist/jezero-demo after all checks pass
// Writes reports/automated-validation.json (with HTML/input hashes) only when every step passes.
// Exit code 1 on any failure; a failed run never packages.
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildUI } from '../code/build_ui_preview.mjs';
import { sha256 } from '../code/packed_seed.mjs';
import { runTests } from './test_map_ui.mjs';
import { runRemainingTests } from './test_remaining_plan.mjs';
import { runPythonReference } from './test_python_reference.mjs';
import { runPackagedGrid } from './test_packaged_grid.mjs';
import { runH0Tests } from './test_h0_reproducibility.mjs';

export async function runValidation(root, {publishGrid = false, reproduce = false, pack = false} = {}) {
  const steps = [], t0 = performance.now();
  const step = async (name, f) => {
    const s = performance.now();
    try { const result = await f(); steps.push({name, status: 'pass', seconds: (performance.now() - s) / 1000, result}); return result; }
    catch (e) { steps.push({name, status: 'fail', seconds: (performance.now() - s) / 1000, error: String(e?.stack || e)}); throw e; }
  };
  let report;
  try {
    if (publishGrid) {
      await step('grid (publish mission + connectivity)', () => runPackagedGrid(root, {publish: true}));
    }
    const build = await step('build', () => buildUI(root));
    if (build.connectivity && !build.connectivity.trusted) throw Error('Connectivity report is stale: ' + build.connectivity.reason + ' (run with --publish-grid)');
    await step('ui', () => runTests(root));
    await step('remaining', () => runRemainingTests(root));
    await step('h0', () => runH0Tests(root));
    await step('python-reference', () => runPythonReference(root));
    await step('grid (temp dir, product files untouched)', async () => {
      const guarded = ['outputs/local_terrain/jezero/mission.json', 'reports/packaged-grid-validation.json', 'outputs/local_terrain/jezero/manifest.json'];
      const snap = async () => Promise.all(guarded.map(async f => sha256(await fs.readFile(path.join(root, f)))));
      const before = await snap(), r = await runPackagedGrid(root), after = await snap();
      if (before.join() !== after.join()) throw Error('Grid check modified product files');
      const published = JSON.parse(await fs.readFile(path.join(root, 'reports/packaged-grid-validation.json'), 'utf8'));
      const same = JSON.stringify(published.reachable_targets) === JSON.stringify(r.reachable_targets) && JSON.stringify(published.synthetic_event?.before) === JSON.stringify(r.synthetic_event.before);
      if (!same) throw Error('Fresh grid result differs from published connectivity/mission result');
      await fs.rm(path.dirname(r.written.report), {recursive: true});
      return {...r, product_files_unchanged: true, matches_published: true};
    });
    if (reproduce) await step('reproducible build', async () => {
      const a = await fs.mkdtemp(path.join(os.tmpdir(), 'build-a-')), b = await fs.mkdtemp(path.join(os.tmpdir(), 'build-b-'));
      const ra = await buildUI(root, {outDir: a}), rb = await buildUI(root, {outDir: b});
      const same = ra.html_sha256 === rb.html_sha256 && ra.html_sha256 === build.html_sha256;
      if (!same) throw Error('Two builds from the same inputs differ');
      await fs.rm(a, {recursive: true}); await fs.rm(b, {recursive: true});
      return {builds: 3, html_sha256: ra.html_sha256, identical: true};
    });
    const html = await fs.readFile(path.join(root, 'reports/18-eva-walkback-demo.html'));
    const counts = Object.fromEntries(steps.filter(s => typeof s.result?.passed === 'number').map(s => [s.name, s.result.passed]));
    report = {
      schema_version: 2, generated_at: new Date().toISOString(), status: 'pass',
      html_sha256: sha256(html), html_bytes: html.length, inputs: build.inputs,
      node: process.version, platform: `${process.platform} ${os.release()}`,
      check_counts: counts, check_total: Object.values(counts).reduce((a, b) => a + b, 0),
      steps: steps.map(({name, status, seconds, result}) => ({name, status, seconds, result: summarize(result)})),
      scope: 'Automated Node/Python checks only. Not browser/DOM visual QA (see reports/browser-qa.md).',
      elapsed_s: (performance.now() - t0) / 1000,
    };
    await fs.writeFile(path.join(root, 'reports/automated-validation.json'), JSON.stringify(report, null, 2));
    if (pack) {
      const { packageReview } = await import('../code/package_review.mjs');
      report.package = await step('package', () => packageReview(root));
    }
    return report;
  } catch (e) {
    return {status: 'fail', steps: steps.map(({name, status, seconds, error}) => ({name, status, seconds, error})), elapsed_s: (performance.now() - t0) / 1000};
  }
}

function summarize(r) {
  if (!r || typeof r !== 'object') return r;
  const {inputs, reachable_targets, ...rest} = r;
  if (reachable_targets) rest.reachable_targets = reachable_targets.map(t => ({id: t.id, reachable: t.reachable}));
  return rest;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
  const args = new Set(process.argv.slice(2));
  const r = await runValidation(root, {publishGrid: args.has('--publish-grid'), reproduce: args.has('--reproduce'), pack: args.has('--package')});
  console.log(JSON.stringify(r, null, 2));
  process.exit(r.status === 'pass' ? 0 : 1);
}
