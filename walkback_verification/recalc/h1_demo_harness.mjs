// 계획 H1: 빌드된 데모 HTML의 화면 스크립트를 node에서 그대로 돌려 프리셋 결과(시뮬레이션 로그, 구조 계산 등)를 읽는다.
// 브라우저 대신 가짜 DOM을 쓴다. 요소마다 textContent·innerHTML을 기록하므로 화면에 쓰인 글자를 그대로 확인할 수 있다.
// 실행: node recalc/h1_demo_harness.mjs demo/gale-eva-walkback-demo.html <작업 JSON> <결과 JSON>
//   작업 JSON: [{ "name": "...", "preset": "simhr", "set": { ...state 덮어쓰기 }, "read": ["pt-facts", ...] }, ...]
import fs from "node:fs";

const [, , htmlPath, jobsPath, outPath] = process.argv;
const html = fs.readFileSync(htmlPath, "utf8");
const grab = (re) => { const m = html.match(re); if (!m) throw new Error("not found: " + re); return m[1]; };
const metaText = grab(/<script type="application\/json" id="meta">([\s\S]*?)<\/script>/);
const blobText = grab(/<script type="application\/octet-stream" id="blob">([\s\S]*?)<\/script>/);
let main = grab(/<script>\s*(\(\(\) => \{[\s\S]*?\}\)\(\);)\s*<\/script>/);
// 닫는 줄 앞에 내부 상태를 내보내는 한 줄을 끼운다 (원본 파일은 바꾸지 않음)
const tail = main.lastIndexOf("})();");
main = main.slice(0, tail) +
  "globalThis.__DEMO = { state, PRESETS, DEFAULTS, update, syncInputs, get SIM() { return SIM; }, get summary() { return summary; }, setNow, W, GOAL, BASE0, META };\n" +
  main.slice(tail);

// ---------- 가짜 DOM ----------
const els = new Map();
const noop = () => {};
const imageData = (w, h) => ({ width: w, height: h, data: new Uint8ClampedArray(Math.max(1, w * h * 4)) });
const ctx2d = new Proxy({
  createImageData: (w, h) => (typeof w === "object" ? imageData(w.width, w.height) : imageData(w, h)),
  getImageData: (x, y, w, h) => imageData(w, h),
  measureText: () => ({ width: 10 }),
}, { get: (t, k) => (k in t ? t[k] : noop), set: (t, k, v) => { t[k] = v; return true; } });
function makeEl(id) {
  const el = {
    id, textContent: id === "meta" ? metaText : id === "blob" ? blobText : "", innerHTML: "", value: "", checked: false,
    hidden: false, disabled: false, max: 0, min: 0, src: "", width: 0, height: 0, clientWidth: 800, clientHeight: 900,
    dataset: {}, style: { setProperty: noop, removeProperty: noop }, children: [],
    classList: { add: noop, remove: noop, toggle: noop, contains: () => false },
    addEventListener: noop, removeEventListener: noop, setAttribute: noop, getAttribute: () => null,
    appendChild: noop, querySelector: () => makeEl("_q"), querySelectorAll: () => [], closest: () => null,
    getContext: () => ctx2d, getBoundingClientRect: () => ({ left: 0, top: 0, width: 800, height: 900 }),
    focus: noop, blur: noop, scrollIntoView: noop,
  };
  return el;
}
const $el = (id) => { if (!els.has(id)) els.set(id, makeEl(id)); return els.get(id); };
globalThis.document = {
  getElementById: $el, querySelector: () => makeEl("_q"), querySelectorAll: () => [], createElement: () => makeEl("_c"),
  addEventListener: noop, documentElement: makeEl("_doc"), body: makeEl("_body"),
};
globalThis.window = globalThis;
globalThis.location = { hash: "" };
globalThis.devicePixelRatio = 1;
globalThis.ResizeObserver = class { observe() {} disconnect() {} };
globalThis.matchMedia = () => ({ matches: false, addEventListener: noop });
// 비동기 그리기는 바로 실행하지 않고 모았다가 flush()에서 돈다
let queue = [];
globalThis.requestAnimationFrame = (f) => { queue.push(f); return queue.length; };
globalThis.cancelAnimationFrame = noop;
const realSetTimeout = setTimeout;
globalThis.setTimeout = (f, ms) => { queue.push(f); return queue.length; };
async function flush() {
  for (let round = 0; round < 50 && queue.length; round++) {
    const q = queue; queue = [];
    for (const f of q) f(performance.now());
    await new Promise((r) => realSetTimeout(r, 0));
  }
}

// ---------- 실행 ----------
(0, eval)(main);
const D = globalThis.__DEMO;
for (let i = 0; i < 400 && !D.summary; i++) { await flush(); await new Promise((r) => realSetTimeout(r, 5)); }
if (!D.summary) throw new Error("demo did not finish loading");

const jobs = JSON.parse(fs.readFileSync(jobsPath, "utf8"));
const out = [];
const strip = (s) => String(s).replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
for (const job of jobs) {
  const p = job.preset ? D.PRESETS.find((q) => q.id === job.preset) : null;
  Object.assign(D.state, D.DEFAULTS, p ? p.s : {}, job.set || {});
  if (job.mode === "sim" || D.state.mode === "sim") D.state.mode = "sim";
  D.syncInputs(); D.update(); await flush();
  const rec = { name: job.name, state: { ...D.state }, summary: D.summary };
  if (D.SIM) {
    rec.sim = D.SIM.ok ? {
      ok: true, outLen_km: D.SIM.outLen / 1000, turnMin: D.SIM.turnMin, minutes: D.SIM.frames.length - 1,
      last: D.SIM.frames[D.SIM.frames.length - 1], log: D.SIM.log,
    } : { ok: false, msg: D.SIM.msg };
  }
  rec.text = Object.fromEntries((job.read || []).map((id) => [id, strip($el(id).innerHTML || $el(id).textContent)]));
  out.push(rec);
}
fs.writeFileSync(outPath, JSON.stringify(out, null, 1));
console.log(`jobs ${out.length} done`);
process.exit(0);
