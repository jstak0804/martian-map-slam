"""계획 H1 검증: 데모 EVA 시뮬레이션의 경로 진행(pathTrack/trackAt)이 귀환 트리와 같은 모델인지 검사

실행: cd code && ../recalc/.venv/bin/python ../recalc/h1_sim_check.py
- js_parity.py와 같은 방식으로 code/demo_template.html의 대사 모델·다익스트라 블록과
  시뮬레이션 경로 블록(pathTrack ~ simFeasible 앞)을 잘라 node로 실행한다.
- 귀환 트리에서 칸 200개를 골라 거점까지의 경로를 만든 뒤,
  (1) pathTrack 합계 산소 = 트리 산소, (2) 합계 시간 = 트리 시간 = Σ d / walkSpeed(경사),
  (3) trackAt이 시간에 대해 거리·산소가 단조 증가하고 끝점에서 len·dur과 맞는지 본다.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), "..", "recalc"))
from js_parity import TMP, load_demo  # noqa: E402

OUT = os.path.abspath(os.path.join(os.getcwd(), "..", "recalc", "outputs_h", "h1_sim_check.json"))


def main() -> None:
    meta, h, eta, flags, _ = load_demo()
    cols = meta["cols"]
    base = meta["base"][1] * cols + meta["base"][0]
    h.tofile(f"{TMP}/h.f32"); eta.tofile(f"{TMP}/eta.f32"); flags.tofile(f"{TMP}/flags.u8")
    json.dump(meta, open(f"{TMP}/meta.json", "w"))
    tpl = open("demo_template.html", encoding="utf-8").read()
    model = tpl[tpl.index("  // 2026-11-10: 대사 모델"):tpl.index("  function returnTree(")]
    track = tpl[tpl.index("  function pathTrack("):tpl.index("  function simFeasible(")]
    node_src = f"""
const fs = require('fs');
const META = JSON.parse(fs.readFileSync('{TMP}/meta.json'));
const C = META.const, R = META.rows, W = META.cols, N = R * W, CELL = META.cell_m, OFF = META.offsets;
const H = new Float32Array(fs.readFileSync('{TMP}/h.f32').buffer.slice(0));
const ETA = new Float32Array(fs.readFileSync('{TMP}/eta.f32').buffer.slice(0));
const FLAGS = new Uint8Array(fs.readFileSync('{TMP}/flags.u8'));
const CLS = new Uint8Array(N), RATE1 = new Float32Array(N);
const state = {{ base: {base}, nofall: false }};
{model}
{track}
const r = dijkstra(state.base, true, false);
let seed = 12345; const rnd = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
const cand = []; for (let i = 0; i < N; i++) if (isFinite(r.o2[i]) && r.o2[i] > 5) cand.push(i);
let maxO2 = 0, maxT = 0, maxTw = 0, mono = true, ends = true, n = 0, maxDur = 0;
for (let q = 0; q < 200; q++) {{
  const i = cand[Math.floor(rnd() * cand.length)], path = [i];
  for (let cur = i, k = 0; k < 8000 && r.pred[cur] >= 0; k++) {{ cur = r.pred[cur]; path.push(cur); }}
  const tr = pathTrack(path), last = path.length - 1;
  let tw = 0;
  for (let j = 1; j <= last; j++) {{
    const a = path[j - 1], b = path[j], d = Math.hypot((b % W) - (a % W), ((b / W) | 0) - ((a / W) | 0)) * CELL;
    tw += d / walkSpeed((H[b] - H[a]) / d * 100);
  }}
  maxO2 = Math.max(maxO2, Math.abs(tr.co[last] - r.o2[i]) / r.o2[i]);
  maxT = Math.max(maxT, Math.abs(tr.dur - r.t[i]) / r.t[i]);
  maxTw = Math.max(maxTw, Math.abs(tr.dur - tw) / tw);
  maxDur = Math.max(maxDur, tr.dur);
  let pd = -1, po = -1;
  for (let s = 0; s <= tr.dur + 60; s += 30) {{
    const p = trackAt(tr, s);
    if (p.dist < pd - 1e-9 || p.o2 < po - 1e-9) mono = false;
    pd = p.dist; po = p.o2;
  }}
  const e = trackAt(tr, tr.dur + 1);
  if (Math.abs(e.dist - tr.len) > 1e-6 || Math.abs(e.o2 - tr.co[last]) > 1e-9 || e.cell !== path[last]) ends = false;
  n++;
}}
console.log(JSON.stringify({{ n, max_rel_err_o2_vs_tree: maxO2, max_rel_err_time_vs_tree: maxT,
  max_rel_err_time_vs_walkspeed_sum: maxTw, monotone: mono, endpoints_ok: ends, max_dur_min: maxDur / 60 }}));
"""
    open(f"{TMP}/sim_run.js", "w", encoding="utf-8").write(node_src)
    out = subprocess.run(["node", f"{TMP}/sim_run.js"], capture_output=True, text=True)
    if out.returncode:
        raise RuntimeError(out.stderr)
    res = json.loads(out.stdout.strip().splitlines()[-1])
    # 트리 시간은 Float32로 저장되므로 시간 비교는 1e-5, 나머지는 1e-9 수준
    res["pass"] = (res["max_rel_err_o2_vs_tree"] < 1e-6 and res["max_rel_err_time_vs_tree"] < 1e-5
                   and res["max_rel_err_time_vs_walkspeed_sum"] < 1e-9 and res["monotone"] and res["endpoints_ok"])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=2)
    print(json.dumps(res, indent=1))
    if not res["pass"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
