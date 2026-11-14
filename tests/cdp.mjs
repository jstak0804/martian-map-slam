// Minimal Chrome DevTools Protocol driver (Node 22 built-in WebSocket; no npm packages).
import { spawn } from 'node:child_process';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

export const CHROME_CANDIDATES = [
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
];
const sleep = ms => new Promise(r => setTimeout(r, ms));

export async function launch({executable, port = 9333, headless = true} = {}) {
  executable ??= (await Promise.all(CHROME_CANDIDATES.map(p => fs.access(p).then(() => p, () => null)))).find(Boolean);
  if (!executable) throw Error('Chrome/Edge not found');
  const profile = await fs.mkdtemp(path.join(os.tmpdir(), 'qa-profile-'));
  const args = [`--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, '--no-first-run', '--no-default-browser-check',
    '--disable-extensions', '--disable-background-networking', '--disable-sync', '--hide-scrollbars', ...(headless ? ['--headless=new'] : []), 'about:blank'];
  const proc = spawn(executable, args, {stdio: 'ignore'});
  let info;
  for (let i = 0; i < 100 && !info; i++) { try { info = await (await fetch(`http://127.0.0.1:${port}/json/version`)).json(); } catch { await sleep(100); } }
  if (!info) { proc.kill(); throw Error('DevTools endpoint did not start'); }
  const ws = new WebSocket(info.webSocketDebuggerUrl);
  await new Promise((ok, fail) => { ws.onopen = ok; ws.onerror = fail; });
  const browser = new Browser(ws, proc, profile, info);
  return browser;
}

class Browser {
  constructor(ws, proc, profile, info) {
    this.ws = ws; this.proc = proc; this.profile = profile; this.info = info; this.seq = 0; this.pending = new Map(); this.listeners = [];
    ws.onmessage = ev => {
      const m = JSON.parse(ev.data);
      if (m.id && this.pending.has(m.id)) { const p = this.pending.get(m.id); this.pending.delete(m.id); m.error ? p.fail(Object.assign(Error(m.error.message), {data: m.error})) : p.ok(m.result); }
      else if (m.method) for (const l of this.listeners) l(m);
    };
  }
  send(method, params = {}, sessionId) {
    const id = ++this.seq;
    return new Promise((ok, fail) => { this.pending.set(id, {ok, fail}); this.ws.send(JSON.stringify({id, method, params, ...(sessionId ? {sessionId} : {})})); });
  }
  async newPage() {
    const {targetId} = await this.send('Target.createTarget', {url: 'about:blank'});
    const {sessionId} = await this.send('Target.attachToTarget', {targetId, flatten: true});
    const page = new Page(this, sessionId, targetId);
    await page.init(); return page;
  }
  async close() {
    try { await this.send('Browser.close'); } catch {}
    await sleep(300); try { this.proc.kill(); } catch {}
    try { await fs.rm(this.profile, {recursive: true, force: true}); } catch {}
  }
}

class Page {
  constructor(browser, sessionId, targetId) {
    this.b = browser; this.sid = sessionId; this.targetId = targetId; this.errors = []; this.console = []; this.requests = []; this.dialogs = []; this.popups = [];
    browser.listeners.push(m => {
      if (m.sessionId !== this.sid) return;
      if (m.method === 'Runtime.exceptionThrown') this.errors.push(m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text);
      if (m.method === 'Runtime.consoleAPICalled' && ['error', 'warning'].includes(m.params.type)) this.console.push(m.params.type + ': ' + m.params.args.map(a => a.value ?? a.description).join(' '));
      if (m.method === 'Network.requestWillBeSent') this.requests.push(m.params.request.url.slice(0, 120));
      if (m.method === 'Page.javascriptDialogOpening') { this.dialogs.push(m.params.message); this.send('Page.handleJavaScriptDialog', {accept: true}); }
      if (m.method === 'Page.windowOpen') this.popups.push(m.params.url);
    });
  }
  send(method, params) { return this.b.send(method, params, this.sid); }
  async init() { await Promise.all(['Page.enable', 'Runtime.enable', 'Network.enable'].map(m => this.send(m))); }
  async viewport(width, height, {mobile = false, touch = false, scale = 1} = {}) {
    await this.send('Emulation.setDeviceMetricsOverride', {width, height, deviceScaleFactor: scale, mobile});
    await this.send('Emulation.setTouchEmulationEnabled', touch ? {enabled: true, maxTouchPoints: 5} : {enabled: false});
  }
  async goto(url, {timeout = 60000} = {}) {
    this.errors.length = 0; this.console.length = 0; this.requests.length = 0;
    await this.send('Page.navigate', {url});
    await this.waitFor('document.readyState==="complete"', {timeout});
  }
  async eval(expression, {await: awaitPromise = true} = {}) {
    const r = await this.send('Runtime.evaluate', {expression, awaitPromise, returnByValue: true});
    if (r.exceptionDetails) throw Error('eval failed: ' + (r.exceptionDetails.exception?.description || r.exceptionDetails.text) + '\n  in: ' + expression.slice(0, 200));
    return r.result.value;
  }
  async waitFor(expression, {timeout = 30000, interval = 100} = {}) {
    const t0 = Date.now(); let last;
    while (Date.now() - t0 < timeout) {
      try { last = await this.eval(`(()=>{try{return !!(${expression})}catch(e){return false}})()`); if (last) return Date.now() - t0; } catch {}
      await sleep(interval);
    }
    throw Error('Timeout waiting for: ' + expression);
  }
  async click(selector) {
    const ok = await this.eval(`(()=>{const el=document.querySelector(${JSON.stringify(selector)});if(!el)return false;el.click();return true})()`);
    if (!ok) throw Error('No element ' + selector);
  }
  // Real input events at element centre (or explicit point) for pointer/gesture paths.
  async mouse(type, x, y, {modifiers = 0, button = 'left', buttons = 1} = {}) {
    await this.send('Input.dispatchMouseEvent', {type, x, y, modifiers, button, buttons, clickCount: 1});
  }
  // A trusted user gesture (needed e.g. for window.open), unlike element.click() from script.
  async realClick(selector) {
    const pt = await this.eval(`(()=>{const el=document.querySelector(${JSON.stringify(selector)});if(!el)return null;const r=el.getBoundingClientRect();return{x:r.left+r.width/2,y:r.top+r.height/2}})()`);
    if (!pt) throw Error('No element ' + selector);
    await this.mouse('mouseMoved', pt.x, pt.y, {buttons: 0}); await this.mouse('mousePressed', pt.x, pt.y); await this.mouse('mouseReleased', pt.x, pt.y, {buttons: 0});
  }
  async key(key, code = key, keyCode = 0) {
    for (const type of ['keyDown', 'keyUp']) await this.send('Input.dispatchKeyEvent', {type, key, code, windowsVirtualKeyCode: keyCode});
  }
  async touch(type, points) { await this.send('Input.dispatchTouchEvent', {type, touchPoints: points}); }
  async screenshot(file) {
    const {data} = await this.send('Page.captureScreenshot', {format: 'png'});
    await fs.mkdir(path.dirname(file), {recursive: true}); await fs.writeFile(file, Buffer.from(data, 'base64')); return file;
  }
  async offline(on) { await this.send('Network.emulateNetworkConditions', {offline: on, latency: 0, downloadThroughput: -1, uploadThroughput: -1}); }
  async metrics() { const {metrics} = await this.send('Performance.getMetrics').catch(async () => { await this.send('Performance.enable'); return this.send('Performance.getMetrics'); }); return Object.fromEntries(metrics.map(m => [m.name, m.value])); }
  async close() { try { await this.b.send('Target.closeTarget', {targetId: this.targetId}); } catch {} }
}
