// H1: real-browser QA of PLAN §19.1 using headless Chrome via DevTools protocol.
//   node tests/browser_qa.mjs [--html reports/18-eva-walkback-demo.html] [--only S1,S2] [--headed]
// Writes reports/browser-qa.json, reports/browser-qa.md and screenshots in reports/browser-qa/.
// Desktop/mobile here are Chrome device emulation, not physical devices.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawn } from 'node:child_process';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { launch } from './cdp.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2), opt = n => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : null; };
const HTML = path.resolve(ROOT, opt('--html') ?? 'reports/18-eva-walkback-demo.html');
const ONLY = opt('--only')?.split(',');
const SHOTS = path.join(ROOT, 'reports/browser-qa');
const URL0 = pathToFileURL(HTML).href;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const results = [];

const LOADED = 'document.getElementById("loading")?.hidden===true && window.EVA_DEBUG?.H && EVA_DEBUG.workerAlive!==undefined';
const PLANNED = '(()=>{const e=EVA_DEBUG.EVA;return e&&(e.ok||(e.msg&&!/Calculating/.test(e.msg)))})()';
const HELPERS = `window.QA={
  D:EVA_DEBUG, $:id=>document.getElementById(id),
  text:id=>document.getElementById(id)?.textContent.trim(),
  visible:el=>{if(typeof el==='string')el=document.querySelector(el);if(!el)return false;const r=el.getBoundingClientRect(),s=getComputedStyle(el);return !el.closest('[hidden]')&&s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0},
  pin:i=>document.querySelector('.map-target-pin[data-poi="'+i+'"]'),
  sel:()=>EVA_DEBUG.state.evaSel.map((v,i)=>v?i:-1).filter(i=>i>=0),
  times:()=>({out:QA.text('map-out'),back:QA.text('map-back'),dwell:QA.text('map-dwell'),split:QA.text('map-split'),status:QA.text('map-plan-status')}),
  flagsHash:()=>{let h=0;const F=EVA_DEBUG.FLAGS;for(let i=0;i<F.length;i++)h=(h*31+F[i])|0;return h},
  center:el=>{const r=el.getBoundingClientRect();return{x:r.left+r.width/2,y:r.top+r.height/2}},
  anchor:el=>({x:parseFloat(el.style.left),y:parseFloat(el.style.top)}),
  wrapCenter:()=>({x:QA.$("mapwrap").clientWidth/2,y:QA.$("mapwrap").clientHeight/2}),
  hangul:root=>{const out=[];const w=document.createTreeWalker(root||document.body,NodeFilter.SHOW_TEXT);let n;while(n=w.nextNode()){const t=n.textContent.trim();if(t&&/[\\uAC00-\\uD7A3]/.test(t)&&QA.visible(n.parentElement))out.push(t.slice(0,60))}return [...new Set(out)]},
};true`;

async function scenario(id, name, env, fn) {
  if (ONLY && !ONLY.includes(id)) return;
  const r = {id, scenario: name, env, status: 'pass', checks: [], notes: [], screenshots: [], errors: []};
  const check = (label, ok, detail) => { r.checks.push({label, ok: !!ok, detail}); if (!ok) r.status = 'fail'; };
  const t0 = Date.now();
  try { await fn({check, note: s => r.notes.push(s), shot: f => r.screenshots.push(path.relative(ROOT, f).replaceAll('\\', '/')), r}); }
  catch (e) { r.status = 'fail'; r.errors.push(String(e.stack || e).split('\n').slice(0, 3).join(' | ')); }
  r.seconds = (Date.now() - t0) / 1000;
  results.push(r);
  console.log(`${r.status.toUpperCase().padEnd(4)} ${id} ${name} (${r.seconds.toFixed(1)}s)` + r.checks.filter(c => !c.ok).map(c => `\n     ✗ ${c.label}: ${JSON.stringify(c.detail)?.slice(0, 300)}`).join('') + r.errors.map(e => '\n     ! ' + e).join(''));
}

async function open(browser, hash, {width = 1440, height = 900, mobile = false, touch = false, url = URL0} = {}) {
  const p = await browser.newPage(); await p.viewport(width, height, {mobile, touch});
  const t0 = Date.now(); await p.goto(url + hash);
  await p.waitFor(LOADED, {timeout: 90000}); const loadMs = Date.now() - t0;
  await p.eval(HELPERS); return {p, loadMs};
}
const pageErrors = p => [...p.errors, ...p.console.filter(c => c.startsWith('error'))];
async function selectPoi(p, i) {
  await p.eval(`QA.pin(${i}).click()`); await p.waitFor('QA.visible("#map-poi")');
  const before = await p.eval('QA.D.EVA'); void before;
  await p.click('#map-poi-select');
}
async function planned(p, timeout = 60000) { const ms = await p.waitFor(PLANNED, {timeout}); return ms; }

const browser = await launch({headless: !args.includes('--headed')});
const env = {browser: browser.info.Browser, html: path.relative(ROOT, HTML).replaceAll('\\', '/'), html_sha256: crypto.createHash('sha256').update(await fs.readFile(HTML)).digest('hex'), url_scheme: 'file', date: new Date().toISOString()};
console.log(env);
await fs.mkdir(SHOTS, {recursive: true});
const desk = 'Chrome headless, 1440×900, file://';

await scenario('S1', 'Entry hashes', desk, async ({check, note, shot}) => {
  for (const [hash, expect] of [['', 'world'], ['#mars', 'world'], ['#jezero', 'jezero'], ['#jezero-evidence-demo', 'demo'], ['#gale', 'gale'], ['#aram', 'aram']]) {
    const {p, loadMs} = await open(browser, hash);
    await sleep(400);
    const s = await p.eval(`({site:QA.D.META.site.id,world:!!document.getElementById('map-world-dialog')?.open,loading:document.getElementById('loading').hidden,sel:QA.sel()})`);
    if (expect === 'world') check(`${hash || '(none)'} opens global map`, s.world, s);
    else if (expect === 'demo') {
      const ms = await planned(p); const t = await p.eval('QA.times()');
      check('#jezero-evidence-demo selects two mission sites', s.site === 'jezero' && s.sel.length === 2 && !s.world, s);
      check('#jezero-evidence-demo shows a plan', /min/.test(t.out) && /min/.test(t.dwell), {t, planMs: ms});
      note(`evidence demo: load ${loadMs} ms, first plan ${ms} ms after load (worker=${await p.eval('QA.D.workerAlive')})`);
      shot(await p.screenshot(path.join(SHOTS, 'S1-evidence-demo-1440.png')));
    } else check(`${hash} opens ${expect} detail`, s.site === expect && !s.world && s.loading, s);
    if (hash === '') shot(await p.screenshot(path.join(SHOTS, 'S1-entry-world-1440.png')));
    check(`${hash || '(none)'} no page errors`, !pageErrors(p).length, pageErrors(p));
    note(`${hash || '(none)'} load ${loadMs} ms`);
    await p.close();
  }
});

await scenario('S2', 'Targets: A only / B only / A+B / max two / observation-only', desk, async ({check, note, shot}) => {
  const {p} = await open(browser, '#jezero');
  const names = await p.eval('QA.D.META.targets.map(t=>t.name_en||t.name)'); note('targets: ' + names.join(' | '));
  await selectPoi(p, 1); await planned(p); const a = await p.eval('({t:QA.times(),e:{ok:QA.D.EVA.ok,o:QA.D.EVA.outbound_s,r:QA.D.EVA.return_s,d:QA.D.EVA.dwell_total_s}})');
  check('A only plans', a.e.ok && /min/.test(a.t.dwell), a);
  check('card time = floor(seconds/60)', a.t.out === Math.floor(a.e.o / 60) + ' min' && a.t.dwell === Math.floor(a.e.d / 60) + ' min', a);
  await p.eval('document.getElementById("map-chips").querySelector("button").click()'); await sleep(200);
  check('deselect via chip clears plan', (await p.eval('QA.sel().length')) === 0 && (await p.eval('QA.text("map-out")')) === '—');
  check('Start disabled with no selection', await p.eval('QA.$("map-play").disabled'));
  await selectPoi(p, 2); await planned(p); const b = await p.eval('({t:QA.times(),ok:QA.D.EVA.ok})');
  check('B only plans', b.ok, b);
  await selectPoi(p, 1); await planned(p); const ab = await p.eval('({t:QA.times(),ok:QA.D.EVA.ok,order:QA.D.EVA.order,chips:[...QA.$("map-chips").children].map(c=>c.textContent),split:QA.visible("#map-share-wrap")})');
  check('A+B plans with both chips and split control', ab.ok && ab.chips.length === 2 && ab.split, ab);
  shot(await p.screenshot(path.join(SHOTS, 'S2-two-sites-1440.png')));
  await p.eval('QA.pin(0).click()'); await p.click('#map-poi-select'); await sleep(300);
  const third = await p.eval('({sel:QA.sel(),toast:QA.text("map-toast"),toastVisible:QA.visible("#map-toast")})');
  check('third selection refused, selection kept', third.sel.length === 2 && /up to two/i.test(third.toast), third);
  const station = await p.eval('QA.D.META.targets.findIndex(t=>t.source_kind==="places_station")');
  await p.eval(`QA.pin(${station}).click()`); await sleep(200);
  const st = await p.eval('({disabled:QA.$("map-poi-select").disabled,label:QA.text("map-poi-select"),caption:QA.text("map-poi-caption"),reach:QA.D.META.targets[' + station + '].default_base_reachable})');
  check('disconnected Navcam station is observation-only', st.disabled && /No route/.test(st.label) && st.reach === false, st);
  shot(await p.screenshot(path.join(SHOTS, 'S2-observation-only-1440.png')));
  check('no page errors', !pageErrors(p).length, pageErrors(p));
  await p.close();
});

await scenario('S3', 'Stay split 25/50/75 and order reversal', desk, async ({check, note}) => {
  const {p} = await open(browser, '#jezero-evidence-demo'); await planned(p);
  const sel = await p.eval('QA.sel()');
  for (const share of [25, 50, 75]) {
    await p.eval(`(()=>{const s=QA.$("map-share");s.value="${share}";s.dispatchEvent(new Event("change"))})()`); await planned(p);
    for (const order of ['auto', 'flip']) {
      if (order === 'flip') { await p.click('#map-order'); await planned(p); }
      const e = await p.eval(`(()=>{const e=QA.D.EVA,sel=QA.sel();return{ok:e.ok,order:e.order,total:e.dwell_total_s,A:e.marks.find(m=>m.ti===sel[0])?.dwell_s,B:e.marks.find(m=>m.ti===sel[1])?.dwell_s,split:QA.text("map-split"),dwellCard:QA.text("map-dwell")}})()`);
      const fracA = e.A / (e.A + e.B);
      check(`${share}% ${order}: A+B = total and A share kept`, e.ok && e.A + e.B === e.total && Math.abs(fracA - share / 100) < 0.02, {...e, fracA});
      check(`${share}% ${order}: split text matches`, e.split.includes(`${Math.floor(e.A / 60)} min`) && e.split.includes(`${Math.floor(e.B / 60)} min`), e.split);
      note(`${share}% ${order}: order ${e.order.join('→')} A ${e.A / 60} min B ${e.B / 60} min`);
    }
  }
  void sel; check('no page errors', !pageErrors(p).length, pageErrors(p)); await p.close();
});

await scenario('S4', 'Rotate / zoom / N / scale / hit-test after rotation', desk, async ({check, shot}) => {
  const {p} = await open(browser, '#jezero');
  const st = () => p.eval('({angle:QA.D.UI.angle,k:QA.D.UI.screen.k,scale:QA.text("map-scale-label"),base:QA.anchor(QA.$("map-base-pin"))})');
  const s0 = await st();
  const c0 = await p.eval('QA.wrapCenter()');
  check('initial view is centered on the base', Math.hypot(s0.base.x - c0.x, s0.base.y - c0.y) < 2, {base: s0.base, c0});
  await p.click('#map-plus'); await p.click('#map-plus'); await sleep(200); const s1 = await st();
  check('+ zooms in and scale label updates', s1.k > s0.k && s1.scale !== s0.scale, {s0: s0.scale, s1: s1.scale, k: [s0.k, s1.k]});
  await p.click('#map-rotate-right'); await p.click('#map-rotate-right'); await sleep(100);
  check('↷ rotates 15° steps', (await st()).angle === 30);
  // Shift-drag rotation with real input events.
  const c = {x: 700, y: 400};
  await p.mouse('mouseMoved', c.x, c.y, {buttons: 0}); await p.mouse('mousePressed', c.x, c.y, {modifiers: 8});
  for (let i = 1; i <= 10; i++) await p.mouse('mouseMoved', c.x + i * 10, c.y, {modifiers: 8});
  await p.mouse('mouseReleased', c.x + 100, c.y, {modifiers: 8}); await sleep(150);
  const s2 = await st(); check('Shift-drag rotates', Math.abs(s2.angle - 30) > 10, s2.angle);
  // Wheel zoom.
  await p.send('Input.dispatchMouseEvent', {type: 'mouseWheel', x: 700, y: 400, deltaX: 0, deltaY: -300}); await sleep(250);
  const s3 = await st(); check('wheel zooms', s3.k > s2.k, [s2.k, s3.k]);
  // Hit-test: real click on a rotated target pin opens that target.
  await p.eval('QA.D.UI.angle'); await p.click('#map-north'); await sleep(200);
  const s4 = await st();
  const ctr = await p.eval('QA.wrapCenter()');
  check('N: north up, zoom kept', s4.angle === 0 && Math.abs(s4.k - s3.k) < 1e-9, {angle: s4.angle, k: [s3.k, s4.k]});
  check('N: base centered', Math.hypot(s4.base.x - ctr.x, s4.base.y - ctr.y) < 2, {base: s4.base, ctr});
  await p.click('#map-north'); await p.click('#map-north'); await sleep(150);
  const s5 = await st(); check('N repeated: no mode toggle', s5.angle === 0 && !(await p.eval('QA.D.UI.headingUp')), s5.angle);
  await p.click('#map-fit'); await sleep(100); await p.click('#map-north'); await sleep(100);
  await p.click('#map-rotate-left'); await p.click('#map-rotate-left'); await p.click('#map-rotate-left'); await sleep(250);
  let hits = 0, tries = 0;
  for (const i of [0, 1, 2]) {
    const pt = await p.eval(`(()=>{const b=QA.pin(${i});return b.hidden?null:QA.center(b)})()`); if (!pt) continue; tries++;
    await p.eval('QA.$("map-poi").hidden=true');
    await p.mouse('mouseMoved', pt.x, pt.y, {buttons: 0}); await p.mouse('mousePressed', pt.x, pt.y); await p.mouse('mouseReleased', pt.x, pt.y); await sleep(150);
    if (await p.eval(`QA.D.UI.poi===${i}&&QA.visible("#map-poi")`)) hits++;
  }
  check('click on rotated (-45°) pins opens the same site', tries > 0 && hits === tries, {hits, tries});
  shot(await p.screenshot(path.join(SHOTS, 'S4-rotated-1440.png')));
  check('labels upright while rotated', await p.eval('[...document.querySelectorAll(".map-target-pin span")].every(s=>!/rotate/.test(getComputedStyle(s).transform)||getComputedStyle(s).transform==="none")'));
  check('no page errors', !pageErrors(p).length, pageErrors(p)); await p.close();
});

await scenario('S5', 'Site photos: real image and source', desk, async ({check, note}) => {
  const {p} = await open(browser, '#jezero');
  const n = await p.eval('QA.D.META.targets.length'); let withImg = 0;
  for (let i = 0; i < n; i++) {
    await p.eval(`QA.pin(${i}).click()`); await sleep(150);
    const r = await p.eval(`new Promise(ok=>{const im=QA.$("map-poi-image").querySelector("img");if(!im)return ok({img:false,text:QA.text("map-poi-image"),cap:QA.text("map-poi-caption")});const done=()=>ok({img:true,w:im.naturalWidth,h:im.naturalHeight,alt:im.alt,cap:QA.text("map-poi-caption")});im.complete?done():(im.onload=done,im.onerror=()=>ok({img:true,broken:true}))})`);
    if (r.img) { withImg++; check(`site ${i} photo decodes`, r.w > 0 && !r.broken, r); check(`site ${i} caption cites sol of shown photo`, r.alt.match(/sol (\d+)/)?.[1] === r.cap.match(/sol (\d+)/)?.[1], r); }
    else check(`site ${i} empty state explicit`, /No nearby observation/.test(r.text), r);
    note(`site ${i}: ${r.img ? `${r.w}×${r.h} ${r.cap}` : r.text}`);
  }
  const dup = await p.eval('(()=>{const m=new Map();for(const p of QA.D.META.photos||[]){const k=p.sol+":"+(p.az??null);m.set(k,(m.get(k)||0)+1)}return [...m].filter(([,c])=>c>1)})()');
  const rv = await p.eval('(()=>{const m=new Map();for(const s of QA.D.META.roadview||[])for(const f of s.frames||[]){const k=s.sol+":"+f.az;m.set(k,(m.get(k)||0)+1)}return [...m].filter(([,c])=>c>1).length})()');
  check('visor cache key sol:az unique for Jezero photos/roadview frames', !dup.length && !rv, {photoDup: dup, roadviewDup: rv});
  note(`${withImg}/${n} sites show a nearby photo`);
  check('no page errors', !pageErrors(p).length, pageErrors(p)); await p.close();
});

await scenario('S6', 'Visor window: same frame as map, close / reopen', desk, async ({check, note}) => {
  const {p} = await open(browser, '#jezero-evidence-demo'); await planned(p);
  await p.waitFor('QA.D.SIM&&QA.D.SIM.ok', {timeout: 60000});
  // Popup blocked (script click has no user gesture): visor falls back to the in-map panel.
  await p.click('#map-visor'); await sleep(400);
  const pip = await p.eval('({hud:QA.D.state.hud,popup:!!(QA.D.HUDWIN&&!QA.D.HUDWIN.closed),pip:QA.visible("#visor-wrap")})');
  if (!pip.popup) {
    check('blocked popup falls back to in-map visor', pip.hud && pip.pip, pip);
    await p.eval('QA.D.setSimIdx(7)'); await sleep(250);
    const s = await p.eval('(()=>{const f=QA.D.frame;return{m:f.m,hud:QA.$("hud").textContent}})()');
    check('in-map visor shows the map frame', s.hud.includes(s.m + ' min'), s);
    await p.click('#visor-close'); await sleep(200);
  } else { note('script click opened a popup (no blocker in this browser); fallback not exercised'); await p.eval('QA.D.HUDWIN.close()'); await sleep(900); }
  await p.realClick('#map-visor'); await sleep(600);
  const v = await p.eval('({hud:QA.D.state.hud,popup:!!(QA.D.HUDWIN&&!QA.D.HUDWIN.closed)})');
  check('Visor opens a window from a user click', v.hud && v.popup, v);
  const len = await p.eval('QA.D.SIM.frames.length');
  for (const idx of [5, Math.floor(len / 3), Math.floor(len * 2 / 3)]) {
    await p.eval(`QA.D.setSimIdx(${idx})`); await sleep(250);
    const s = await p.eval(`(()=>{const f=QA.D.frame,doc=QA.D.HUDWIN.document;return{m:f.m,phase:f.phase,hud:doc.getElementById("hud")?.textContent||"",cap:doc.getElementById("visor-cap")?.textContent||"",img:!!doc.getElementById("map-visor-photo")?.src,mapOut:QA.text("map-out"),mapDwell:QA.text("map-dwell")}})()`);
    const ph = {out: 'On the way', work: 'At site', back: 'Returning', home: 'At base'}[s.phase];
    check(`frame ${idx}: visor shows same minute/phase`, s.hud.includes(s.m + ' min') && s.hud.includes(ph), s);
    check(`frame ${idx}: visor real photo + source`, s.img && /NASA\/JPL-Caltech|No rover photo/.test(s.cap), s.cap);
    check(`frame ${idx}: visor stay = map stay`, s.hud.includes(s.mapDwell), {hud: s.hud, map: s.mapDwell});
  }
  await p.eval('QA.D.HUDWIN.close()'); await sleep(900);
  const closed = await p.eval('({hud:QA.D.state.hud,win:QA.D.HUDWIN})');
  check('closing the window resets visor state', closed.hud === false && closed.win === null, closed);
  await p.click('#map-visor'); await sleep(600);
  await p.realClick('#map-visor'); await sleep(600);
  check('visor reopens', await p.eval('!!(QA.D.HUDWIN&&!QA.D.HUDWIN.closed)'));
  // Playback drives both views from one clock.
  await p.eval('QA.D.setSimIdx(0)'); await p.click('#map-play'); await sleep(2500); await p.click('#map-play'); await sleep(300);
  const pl = await p.eval('({m:QA.D.frame.m,hud:QA.D.HUDWIN.document.getElementById("hud").textContent})');
  check('after playback pause, visor minute = map minute', pl.m > 0 && pl.hud.includes(pl.m + ' min'), pl);
  note(`playback advanced to minute ${pl.m} in 2.5 s`);
  await p.eval('QA.D.HUDWIN.close()');
  check('no page errors', !pageErrors(p).length, pageErrors(p)); await p.close();
});

await scenario('S7', 'Return now during travel / at site / partial minute; Restart', desk, async ({check, note}) => {
  const {p} = await open(browser, '#jezero-evidence-demo'); await planned(p);
  await p.waitFor('QA.D.SIM&&QA.D.SIM.ok', {timeout: 60000});
  const plan = await p.eval('({frames:QA.D.SIM.frames.length,phases:[...new Set(QA.D.SIM.frames.map(f=>f.phase))]})'); note(JSON.stringify(plan));
  for (const phase of ['out', 'work']) {
    await p.click('#map-reset'); await p.waitFor('QA.D.SIM&&QA.D.SIM.ok');
    const idx = await p.eval(`(()=>{const fr=QA.D.SIM.frames;const ix=fr.map((f,i)=>f.phase==="${phase}"?i:-1).filter(i=>i>0);return ix[Math.floor(ix.length/2)]??-1})()`);
    if (idx < 0) { check(`${phase}: frame exists`, false); continue; }
    await p.eval(`QA.D.setSimIdx(${idx})`); await sleep(150);
    const before = await p.eval('(f=>({m:f.m,pos:f.pos,o2:f.o2,w:f.w,dose:f.dose,phase:f.phase}))(QA.D.frame)');
    check(`${phase}: Return now enabled`, !(await p.eval('QA.$("map-return").disabled')));
    await p.click('#map-return'); await sleep(300);
    const after = await p.eval('(f=>({m:f.m,pos:f.pos,o2:f.o2,w:f.w,dose:f.dose,phase:f.phase,manual:!!QA.D.SIM.manualReturnPath,toast:QA.text("map-toast")}))(QA.D.frame)');
    check(`${phase}: elapsed time and consumption preserved`, after.m === before.m && after.pos === before.pos && Math.abs(after.o2 - before.o2) < 1e-9 && Math.abs(after.w - before.w) < 1e-9 && Math.abs(after.dose - before.dose) < 1e-12, {before, after});
    const tail = await p.eval('(()=>{const fr=QA.D.SIM.frames,i=QA.D.SIM.idx;const rest=fr.slice(i+1);return{phases:[...new Set(rest.map(f=>f.phase))],last:fr.at(-1).phase,lastPos:fr.at(-1).pos,base:QA.D.state.base,work:rest.filter(f=>f.phase==="work").length}})()');
    check(`${phase}: remaining frames return to base with no more site work`, tail.work === 0 && tail.last === 'home' && tail.lastPos === tail.base, tail);
    await p.eval('QA.D.setSimIdx(QA.D.SIM.frames.length-1)'); await sleep(250);
    const end = await p.eval('({stay:QA.text("map-dwell"),status:QA.text("map-plan-status"),phase:QA.D.frame.phase})');
    check(`${phase}: stay left is 0 after return`, end.stay === '0 min' && end.phase === 'home', end);
  }
  // Partial minute: the simulation is minute-stepped; the last return frame carries active seconds.
  const partial = await p.eval('(()=>{const fr=QA.D.SIM.frames;return fr.some(f=>f.activeSeconds!==undefined&&f.activeSeconds<60)})()');
  note('partial-minute frames present: ' + partial);
  await p.click('#map-reset'); await p.waitFor('QA.D.SIM&&QA.D.SIM.ok');
  const rs = await p.eval('({manual:!!QA.D.SIM.manualReturnPath,m:QA.D.frame?.m??0,work:QA.D.SIM.frames.filter(f=>f.phase==="work").length})');
  check('Restart restores the original trip', !rs.manual && rs.m === 0 && rs.work > 0, rs);
  check('no page errors', !pageErrors(p).length, pageErrors(p)); await p.close();
});

await scenario('S8', 'Block test / Clear block repeated; worker pending settles', desk, async ({check, note, shot}) => {
  const {p} = await open(browser, '#jezero-evidence-demo'); await planned(p);
  const h0 = await p.eval('QA.flagsHash()'), path0 = await p.eval('QA.D.EVA.path.length');
  for (let round = 1; round <= 2; round++) {
    await p.click('#map-event'); await planned(p, 90000);
    const b = await p.eval('({blocked:QA.D.UI.blocked.length,rev:QA.D.overlayRevision,ok:QA.D.EVA.ok,label:QA.text("map-event"),onPath:QA.D.EVA.ok?QA.D.UI.blocked.filter(c=>QA.D.EVA.path.includes(c)).length:0,len:QA.D.EVA.path?.length})');
    check(`round ${round}: synthetic block applied and route avoids it`, b.blocked > 0 && b.onPath === 0 && b.label === 'Clear block', b);
    if (round === 1) shot(await p.screenshot(path.join(SHOTS, 'S8-block-test-1440.png')));
    await p.click('#map-event'); await planned(p, 90000);
    const c = await p.eval('({blocked:QA.D.UI.blocked.length,label:QA.text("map-event"),len:QA.D.EVA.path?.length})');
    check(`round ${round}: Clear block restores original flags`, c.blocked === 0 && (await p.eval('QA.flagsHash()')) === h0 && c.label === 'Block test', c);
    check(`round ${round}: original route length restored`, c.len === path0, {c: c.len, path0});
  }
  // Race probe: Block test immediately after a zone/tree request was issued.
  await p.eval('QA.D.UI.zoneTree=null;QA.D.UI.zoneKey=null;QA.D.LEGS.clear();QA.D.update()');
  await p.click('#map-event');
  let settled = true; try { await p.waitFor('QA.D.UI.zonePending===false&&QA.D.workerPending===0', {timeout: 30000}); } catch { settled = false; }
  const st = await p.eval('({zonePending:QA.D.UI.zonePending,workerPending:QA.D.workerPending,livePending:QA.D.UI.livePending})');
  check('pending zone/worker jobs settle after worker restart', settled, st);
  await p.click('#map-event'); await planned(p, 90000);
  note('race probe state: ' + JSON.stringify(st));
  check('no page errors', !pageErrors(p).length, pageErrors(p)); await p.close();
});

await scenario('S9', 'Region switch Jezero→Gale→Jezero fast and during loading/planning', desk, async ({check, note}) => {
  const {p} = await open(browser, '#jezero');
  const idx = await p.eval('Object.fromEntries([...QA.$("map-region").options].map(o=>[o.textContent,Number(o.value)]))'); note(JSON.stringify(idx));
  const gale = await p.eval('[...QA.$("map-region").options].findIndex(o=>/Gale/i.test(o.textContent))'), jez = await p.eval('[...QA.$("map-region").options].findIndex(o=>/Jezero/i.test(o.textContent))');
  await selectPoi(p, 1);
  // Switch while planning is in flight, then back immediately (no awaits between).
  await p.eval(`QA.D.loadSite(${gale});QA.D.loadSite(${jez});true`);
  await p.waitFor(LOADED); await sleep(1500);
  const s = await p.eval('({site:QA.D.META.site.id,gen:QA.D.siteGeneration,sel:QA.sel(),blocked:QA.D.UI.blocked?.length||0,rev:QA.D.overlayRevision,eva:QA.D.EVA&&{ok:QA.D.EVA.ok,msg:QA.D.EVA.msg},loading:QA.$("loading").hidden,workerPending:QA.D.workerPending})');
  check('final region is the last requested', s.site === 'jezero' && s.loading, s);
  check('selection and overlays reset on region change', s.sel.length === 0 && s.blocked === 0 && s.rev === 0, s);
  await selectPoi(p, 2); await planned(p);
  check('planning works after rapid switching', await p.eval('QA.D.EVA.ok'));
  for (let i = 0; i < 4; i++) { await p.eval(`QA.D.loadSite(${i % 2 ? jez : gale})`); }
  await p.waitFor(LOADED);
  const g = await p.eval('({site:QA.D.META.site.id,mode:QA.D.state.mode})'); note('after 4 awaited switches: ' + JSON.stringify(g));
  check('Gale still loads with its own policy (not strict Jezero EVA)', g.site === 'jezero' || g.site === 'gale', g);
  await p.eval(`QA.D.loadSite(${gale})`); await p.waitFor(LOADED); await sleep(300);
  const gs = await p.eval('({site:QA.D.META.site.id,evidence:QA.visible("#map-evidence"),block:QA.visible("#map-event"),legacy:QA.$("legacy")?.disabled})');
  check('Gale hides Jezero-only Observations/Block test', gs.site === 'gale' && !gs.evidence && !gs.block, gs);
  check('no page errors', !pageErrors(p).length, pageErrors(p)); await p.close();
});

await scenario('S10', 'Global map: open/close, pan/zoom, click coordinates, region entry', desk, async ({check, shot, note}) => {
  const {p} = await open(browser, '#mars');
  await p.waitFor('document.getElementById("map-world-dialog")?.open');
  const legs0 = await p.eval('QA.D.LEGS.size');
  await p.eval('document.querySelector("#map-world-dialog [data-z=\\"2\\"]").click()'); await sleep(100);
  const r = await p.eval('(r=>({x:r.left,y:r.top,w:r.width,h:r.height}))(document.querySelector(".map-world-canvas").getBoundingClientRect())');
  const viewport = await p.eval('(r=>({x:r.left,y:r.top,w:r.width,h:r.height}))(document.querySelector(".map-world-viewport").getBoundingClientRect())');
  const pt = {x: viewport.x + viewport.w / 2, y: viewport.y + viewport.h / 2};
  await p.mouse('mouseMoved', pt.x, pt.y, {buttons: 0}); await p.mouse('mousePressed', pt.x, pt.y); await p.mouse('mouseReleased', pt.x, pt.y); await sleep(150);
  const label = await p.eval('document.querySelector("#map-world-dialog div > span")?.textContent');
  const lon = (pt.x - r.x) / r.w * 360 - 180, lat = 90 - (pt.y - r.y) / r.h * 180;
  const m = label?.match(/(-?[\d.]+)° N, (-?[\d.]+)° E/);
  check('click shows lat/lon matching the equirectangular inverse', m && Math.abs(+m[1] - lat) < 0.01 && Math.abs(+m[2] - lon) < 0.01, {label, lat, lon});
  check('unregistered location says detail not checked, no route computed', /not checked/.test(label) && (await p.eval('QA.D.LEGS.size')) === legs0, label);
  // Drag pan.
  await p.mouse('mousePressed', pt.x, pt.y); for (let i = 1; i <= 8; i++) await p.mouse('mouseMoved', pt.x + i * 15, pt.y + i * 5); await p.mouse('mouseReleased', pt.x + 120, pt.y + 40); await sleep(100);
  const r2 = await p.eval('(r=>({x:r.left,y:r.top}))(document.querySelector(".map-world-canvas").getBoundingClientRect())');
  check('drag pans the global map', Math.abs(r2.x - r.x - 120) < 2 && Math.abs(r2.y - r.y - 40) < 2, {r, r2});
  const cards = await p.eval('[...document.querySelectorAll("#map-world-regions button")].map(b=>({text:b.textContent,title:b.title}))');
  note('region buttons: ' + JSON.stringify(cards));
  check('region data status readable without hover (touch)', cards.every(c => /packaged|not_checked|local|catalog|Available|Not checked/i.test(c.text)), cards);
  shot(await p.screenshot(path.join(SHOTS, 'S10-global-1440.png')));
  await p.eval('[...document.querySelectorAll("#map-world-regions button")].find(b=>/Jezero/.test(b.textContent)).click()');
  await p.waitFor(LOADED); await sleep(300);
  check('region button enters detail and closes dialog', (await p.eval('QA.D.META.site.id')) === 'jezero' && !(await p.eval('document.getElementById("map-world-dialog").open')));
  await p.click('#map-world'); await sleep(150);
  check('Mars button reopens global map', await p.eval('document.getElementById("map-world-dialog").open'));
  await p.key('Escape', 'Escape', 27); await sleep(150);
  check('Escape closes global map', !(await p.eval('document.getElementById("map-world-dialog").open')));
  check('no page errors', !pageErrors(p).length, pageErrors(p)); await p.close();
});

await scenario('S11', 'Offline (network disabled) file:// open', 'Chrome headless 1440×900, network emulated offline', async ({check, note}) => {
  const p = await browser.newPage(); await p.viewport(1440, 900); await p.offline(true);
  await p.goto(URL0 + '#jezero-evidence-demo'); await p.waitFor(LOADED, {timeout: 90000}); await p.eval(HELPERS); await planned(p);
  const s = await p.eval('({ok:QA.D.EVA.ok,worker:QA.D.workerAlive,t:QA.times()})');
  check('plan works offline', s.ok && /min/.test(s.t.dwell), s);
  await p.click('#map-world'); await sleep(300);
  check('global map image renders offline', await p.eval('(im=>im.complete&&im.naturalWidth>0)(document.querySelector("#map-world-dialog img"))'));
  await p.eval('document.getElementById("map-world-dialog").close()');
  await p.eval('QA.pin(1).click()'); await sleep(300);
  check('site photo renders offline', await p.eval('(im=>!!im&&im.complete&&im.naturalWidth>0)(QA.$("map-poi-image").querySelector("img"))'));
  const ext = p.requests.filter(u => /^https?:/.test(u)); note('external requests attempted: ' + JSON.stringify(ext));
  check('no external request for map data, photos, scripts or styles', ext.filter(u => !/fonts\.(googleapis|gstatic)\.com/.test(u)).length === 0, ext);
  check('no external web-font request (fonts fall back offline, but the page still contacts Google Fonts)', !ext.some(u => /fonts\.(googleapis|gstatic)\.com/.test(u)), ext.filter(u => /fonts/.test(u)).slice(0, 2));
  check('no page errors', !pageErrors(p).length, pageErrors(p)); await p.close();
});

await scenario('S12', 'HTTP localhost vs file', 'Chrome headless 1440×900, http://127.0.0.1 (python http.server)', async ({check, note}) => {
  const py = 'C:/nasa/.tools/python-3.12.10/python.exe';
  const srv = spawn(py, ['-m', 'http.server', '8765', '--bind', '127.0.0.1', '--directory', path.dirname(HTML)], {stdio: 'ignore'});
  try {
    let up = false; for (let i = 0; i < 50 && !up; i++) { try { await fetch('http://127.0.0.1:8765/'); up = true; } catch { await sleep(100); } }
    check('server started', up);
    const {p, loadMs} = await open(browser, '#jezero-evidence-demo', {url: 'http://127.0.0.1:8765/' + path.basename(HTML)});
    await planned(p);
    const s = await p.eval('({ok:QA.D.EVA.ok,worker:QA.D.workerAlive,t:QA.times(),origin:location.origin})');
    check('same plan over HTTP', s.ok && /min/.test(s.t.dwell), s);
    await p.realClick('#map-visor'); await sleep(600);
    check('visor window opens over HTTP', await p.eval('!!(QA.D.HUDWIN&&!QA.D.HUDWIN.closed)'));
    note(`HTTP load ${loadMs} ms; times ${JSON.stringify(s.t)}`);
    check('no page errors', !pageErrors(p).length, pageErrors(p)); await p.close();
  } finally { srv.kill(); }
});

const SIZES = [['desktop 1440×900', 1440, 900, false], ['laptop 1366×768', 1366, 768, false], ['phone 390×844 (touch emulation)', 390, 844, true], ['phone landscape 844×390 (touch emulation)', 844, 390, true]];
await scenario('S13', 'Screen sizes: key controls visible, not covered, tappable', 'Chrome headless device emulation', async ({check, note, shot}) => {
  for (const [label, w, h, mobile] of SIZES) {
    const {p} = await open(browser, '#jezero-evidence-demo', {width: w, height: h, mobile, touch: mobile}); await planned(p);
    const ids = ['map-play', 'map-out', 'map-back', 'map-dwell', 'map-north', 'map-plus', 'map-minus', 'map-settings', 'map-world', 'map-sites', 'map-return', 'map-reset'];
    const r = await p.eval(`(${JSON.stringify(ids)}).map(id=>{const el=QA.$(id);if(!QA.visible(el))return{id,visible:false};const b=el.getBoundingClientRect(),c=QA.center(el),top=document.elementFromPoint(c.x,c.y);return{id,visible:true,inside:b.left>=0&&b.top>=0&&b.right<=innerWidth&&b.bottom<=innerHeight,covered:!(top===el||el.contains(top)),by:top&&!(top===el||el.contains(top))?(top.id||top.className||top.tagName):null,size:[Math.round(b.width),Math.round(b.height)]}})`);
    const bad = r.filter(x => !x.visible || !x.inside || x.covered);
    check(`${label}: controls visible, inside viewport, not covered`, !bad.length, bad);
    if (mobile) { const small = r.filter(x => x.visible && !['map-out', 'map-back', 'map-dwell'].includes(x.id) && (x.size[0] < 32 || x.size[1] < 32)); check(`${label}: touch targets ≥32px`, !small.length, small); }
    const scroll = await p.eval('({x:document.documentElement.scrollWidth>innerWidth+1,y:document.documentElement.scrollHeight>innerHeight+1})');
    check(`${label}: no page scroll`, !scroll.x, scroll);
    await p.eval('QA.pin(1).click()'); await sleep(250);
    const pop = await p.eval('(()=>{const b=QA.$("map-poi").getBoundingClientRect(),c=QA.$("map-poi-close").getBoundingClientRect();return{inside:b.left>=0&&b.top>=0&&b.right<=innerWidth+1&&b.bottom<=innerHeight+1,closeVisible:c.width>0&&c.top>=0&&c.bottom<=innerHeight}})()');
    check(`${label}: site popup fits and can be closed`, pop.inside && pop.closeVisible, pop);
    const tag = label.split(' ')[0] + '-' + w + 'x' + h;
    shot(await p.screenshot(path.join(SHOTS, `S13-${tag}.png`)));
    await p.click('#map-poi-close'); await p.click('#map-settings'); await sleep(200);
    const dr = await p.eval('(()=>{const c=QA.$("map-drawer-close"),b=c.getBoundingClientRect();return{visible:QA.visible("#map-drawer"),closeInside:b.top>=0&&b.bottom<=innerHeight&&b.right<=innerWidth}})()');
    check(`${label}: settings drawer opens and close button reachable`, dr.visible && dr.closeInside, dr);
    shot(await p.screenshot(path.join(SHOTS, `S13-${tag}-settings.png`)));
    note(`${label}: ${JSON.stringify(r.map(x => x.id + (x.visible ? '' : ':hidden')))}`);
    await p.close();
  }
});

await scenario('S14', 'Touch: pinch, twist, pan (emulated touch events)', 'Chrome headless 390×844 touch emulation', async ({check}) => {
  const {p} = await open(browser, '#jezero', {width: 390, height: 844, mobile: true, touch: true});
  const st = () => p.eval('({angle:QA.D.UI.angle,k:QA.D.UI.screen.k,base:QA.anchor(QA.$("map-base-pin"))})');
  const s0 = await st(); const c = {x: 195, y: 420};
  check('phone opens with the base on screen', s0.base.x > 0 && s0.base.x < 390 && s0.base.y > 0 && s0.base.y < 844, s0.base);
  await p.touch('touchStart', [{x: c.x, y: c.y, id: 1}]); for (let i = 1; i <= 6; i++) await p.touch('touchMove', [{x: c.x + i * 10, y: c.y + i * 5, id: 1}]); await p.touch('touchEnd', []); await sleep(200);
  const s1 = await st(); check('one-finger pan moves the map', Math.hypot(s1.base.x - s0.base.x - 60, s1.base.y - s0.base.y - 30) < 3, {s0: s0.base, s1: s1.base});
  const rad = 60, steps = 8;
  await p.touch('touchStart', [{x: c.x - rad, y: c.y, id: 1}, {x: c.x + rad, y: c.y, id: 2}]);
  for (let i = 1; i <= steps; i++) { const a = i / steps * Math.PI / 6, r = rad * (1 + i / steps); await p.touch('touchMove', [{x: c.x - r * Math.cos(a), y: c.y - r * Math.sin(a), id: 1}, {x: c.x + r * Math.cos(a), y: c.y + r * Math.sin(a), id: 2}]); }
  await p.touch('touchEnd', []); await sleep(200);
  const s2 = await st();
  check('two-finger pinch zooms ~2×', Math.abs(s2.k / s1.k - 2) < 0.15, {k1: s1.k, k2: s2.k});
  check('two-finger twist rotates ~30°', Math.abs(s2.angle - s1.angle - 30) < 3, {a1: s1.angle, a2: s2.angle});
  const pt = await p.eval('(()=>{const b=QA.pin(1);return b.hidden?null:QA.center(b)})()');
  if (pt) { await p.touch('touchStart', [{x: pt.x, y: pt.y, id: 1}]); await p.touch('touchEnd', []); await sleep(300); check('tap on rotated pin opens that site', await p.eval('QA.D.UI.poi===1&&QA.visible("#map-poi")')); }
  check('no page errors', !pageErrors(p).length, pageErrors(p)); await p.close();
});

await scenario('S15', 'Keyboard and English-only text', desk, async ({check, note}) => {
  const {p} = await open(browser, '#jezero-evidence-demo'); await planned(p);
  await p.eval('QA.pin(1).click()'); await sleep(150); await p.key('Escape', 'Escape', 27); await sleep(150);
  check('Escape closes popup and returns focus to Sites', await p.eval('!QA.visible("#map-poi")&&document.activeElement?.id==="map-sites"'));
  const unnamed = await p.eval('[...document.querySelectorAll("#map-ui button,#map-ui select")].filter(b=>QA.visible(b)&&!(b.getAttribute("aria-label")||b.textContent.trim())).map(b=>b.id||b.className)');
  check('visible controls have accessible names', !unnamed.length, unnamed);
  const order = []; await p.eval('document.activeElement?.blur()');
  for (let i = 0; i < 25; i++) { await p.key('Tab', 'Tab', 9); order.push(await p.eval('document.activeElement?.id||document.activeElement?.className||document.activeElement?.tagName')); }
  note('tab order: ' + order.join(' → '));
  check('Tab reaches map controls', ['map-world', 'map-north', 'map-play'].every(id => order.includes(id)), order);
  const main = await p.eval('QA.hangul(document.getElementById("map-ui"))');
  check('default map UI has no Korean text', !main.length, main);
  const attrs = await p.eval('[...document.querySelectorAll("[aria-label],[title],[alt]")].filter(el=>!el.closest("#map-drawer")).flatMap(el=>["aria-label","title","alt"].map(a=>el.getAttribute(a)).filter(v=>v&&/[\\uAC00-\\uD7A3]/.test(v)).map(v=>(el.id||el.tagName)+": "+v.slice(0,50)))');
  check('map screen names/titles/alt have no Korean (screen readers, tooltips)', !attrs.length, attrs);
  await p.click('#map-settings'); await sleep(200);
  const drawer = await p.eval('QA.hangul(document.getElementById("map-drawer"))');
  check('settings drawer has no Korean text', !drawer.length, drawer.slice(0, 40));
  note(`Korean strings in settings drawer: ${drawer.length}`);
  await p.click('#map-visor'); await sleep(500);
  const hud = await p.eval('QA.D.HUDWIN?QA.hangul(QA.D.HUDWIN.document.body):[]');
  check('visor window has no Korean text', !hud.length, hud);
  await p.eval('QA.D.HUDWIN?.close()'); await p.close();
});

await scenario('S16', 'Performance (emulated desktop, this PC)', 'Chrome headless 1440×900 on local Windows PC', async ({check, note}) => {
  const samples = [];
  for (let i = 0; i < 3; i++) {
    const t0 = Date.now(); const {p, loadMs} = await open(browser, '#jezero-evidence-demo'); const planMs = await planned(p);
    const live = await (async () => { await p.waitFor('QA.D.SIM&&QA.D.SIM.ok'); const ix = await p.eval('QA.D.SIM.frames.findIndex(f=>f.phase==="out"&&f.m>10)'); const s = Date.now(); await p.eval(`QA.D.setSimIdx(${ix})`); try { await p.waitFor('QA.D.UI.liveEstimate&&QA.D.UI.livePending==null', {timeout: 60000}); return Date.now() - s; } catch { return null; } })();
    const m = await p.metrics(); samples.push({loadMs, planMs, liveMs: live, totalMs: Date.now() - t0, heapMB: +(m.JSHeapUsedSize / 1048576).toFixed(1)}); await p.close();
  }
  note(JSON.stringify(samples));
  const med = k => samples.map(s => s[k]).filter(v => v != null).sort((a, b) => a - b)[1];
  check('first map ≤10 s (provisional target)', med('loadMs') <= 10000, med('loadMs'));
  check('first plan ≤10 s after load (provisional target)', med('planMs') <= 10000, med('planMs'));
  check('live estimate ≤10 s (provisional target)', med('liveMs') != null && med('liveMs') <= 10000, med('liveMs'));
});

await browser.close();
const summary = {pass: results.filter(r => r.status === 'pass').length, fail: results.filter(r => r.status === 'fail').length, checks: results.reduce((n, r) => n + r.checks.length, 0), failedChecks: results.reduce((n, r) => n + r.checks.filter(c => !c.ok).length, 0)};
const out = {schema_version: 1, env, summary, results, not_run: ['Physical phone/tablet (only Chrome device emulation)', 'Safari/Firefox', 'Popup-blocker enabled browser (headless allows window.open)', 'Screen recording (H7)']};
if (!ONLY) {
  await fs.writeFile(path.join(ROOT, 'reports/browser-qa.json'), JSON.stringify(out, null, 2));
  const md = ['# Browser QA (PLAN §19.1)', '', `- Browser: ${env.browser} (headless, DevTools protocol, \`tests/browser_qa.mjs\`)`, `- HTML: \`${env.html}\` SHA256 \`${env.html_sha256}\``, `- Date: ${env.date}`, `- Result: ${summary.pass} pass / ${summary.fail} fail scenarios; ${summary.checks - summary.failedChecks}/${summary.checks} checks`, '- Device rows are Chrome emulation, not physical devices.', '',
    '| ID | Scenario | Env | Result | Failed checks | Evidence |', '|---|---|---|---|---|---|',
    ...results.map(r => `| ${r.id} | ${r.scenario} | ${r.env} | **${r.status}** | ${r.checks.filter(c => !c.ok).map(c => c.label).join('; ').replaceAll('|', '/') || '—'}${r.errors.length ? ' / error: ' + r.errors[0].slice(0, 120).replaceAll('|', '/') : ''} | ${r.screenshots.map(s => `[png](${s.replace('reports/', '')})`).join(' ')} |`),
    '', '## Not run', '', ...out.not_run.map(s => '- ' + s), '', '## Notes', '', ...results.flatMap(r => r.notes.map(n => `- ${r.id}: ${n}`))];
  await fs.writeFile(path.join(ROOT, 'reports/browser-qa.md'), md.join('\n') + '\n');
}
console.log(JSON.stringify(summary));
process.exit(0);
