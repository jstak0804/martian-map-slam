"""데모 JS와 Python의 귀환 비용 일치 검사 (계획 C 검증 5)

실행: cd code && ../recalc/.venv/bin/python ../recalc/js_parity.py
- 빌드된 데모 데이터(outputs/demo)의 고도·지형계수·통행 표시를 JS와 같은 방식으로 복원한다.
- code/demo_template.html에서 대사 모델과 다익스트라 코드를 그대로 잘라 node로 실행한다(귀환 방향, 거점 출발).
- 같은 입력으로 Python mars_walkback.build_o2_graph + scipy 다익스트라를 돌려 비교한다.
- 2026-11-12 (계획 H3): 모래 스위치 사례도 비교한다(JS: META.sand_cells에 max(η, sand_eta), Python: mars_walkback.apply_sand).
"""
from __future__ import annotations

import gzip
import json
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.getcwd())
from scipy.sparse.csgraph import dijkstra  # noqa: E402

from mars_walkback import apply_sand, build_o2_graph  # noqa: E402

TMP = os.path.abspath(os.path.join(os.getcwd(), "..", "recalc", "outputs_c", "parity"))
os.makedirs(TMP, exist_ok=True)


def load_demo():
    meta = json.load(open("../outputs/demo/demo_meta.json", encoding="utf-8"))
    raw = gzip.decompress(open("../outputs/demo/demo_data.bin.gz", "rb").read())

    def view(name):
        off, ln, dt = meta["layout"][name]
        return np.frombuffer(raw[off:off + ln], dtype="<u2" if dt == "uint16" else np.uint8)

    h = (meta["h_min"] + view("h").astype(np.float64) * meta["h_step"]).astype(np.float32)
    eta = (meta["eta_min"] + view("eta").astype(np.float64) / 255 * (meta["eta_max"] - meta["eta_min"])).astype(np.float32)
    return meta, h, eta, view("flags"), view("plain_o2")


def main() -> None:
    meta, h, eta, flags, plain_o2 = load_demo()
    rows, cols = meta["rows"], meta["cols"]
    base = meta["base"][1] * cols + meta["base"][0]
    h.tofile(f"{TMP}/h.f32"); eta.tofile(f"{TMP}/eta.f32"); flags.tofile(f"{TMP}/flags.u8")
    json.dump(meta, open(f"{TMP}/meta.json", "w"))

    tpl = open("demo_template.html", encoding="utf-8").read()
    a = tpl.index("  // 2026-11-10: 대사 모델")
    b = tpl.index("  function returnTree(")
    js_block = tpl[a:b]
    node_src = f"""
const fs = require('fs');
const META = JSON.parse(fs.readFileSync('{TMP}/meta.json'));
const C = META.const, R = META.rows, W = META.cols, N = R * W, CELL = META.cell_m, OFF = META.offsets;
const H = new Float32Array(fs.readFileSync('{TMP}/h.f32').buffer.slice(0));
const ETA = new Float32Array(fs.readFileSync('{TMP}/eta.f32').buffer.slice(0));
const FLAGS = new Uint8Array(fs.readFileSync('{TMP}/flags.u8'));
const CLS = new Uint8Array(N), RATE1 = new Float32Array(N);
const state = {{ base: {base}, nofall: false }};
{js_block}
const r = dijkstra(state.base, true, false);
fs.writeFileSync('{TMP}/js_ret.f64', Buffer.from(r.o2.buffer));
fs.writeFileSync('{TMP}/js_t.f32', Buffer.from(r.t.buffer));
for (const i of META.sand_cells) ETA[i] = Math.max(ETA[i], META.sand_eta);   // 데모 모래 스위치와 같은 처리
const rs = dijkstra(state.base, true, false);
fs.writeFileSync('{TMP}/js_ret_sand.f64', Buffer.from(rs.o2.buffer));
console.log('js done');
"""
    open(f"{TMP}/run.js", "w", encoding="utf-8").write(node_src)
    out = subprocess.run(["node", f"{TMP}/run.js"], capture_output=True, text=True)
    if out.returncode:
        raise RuntimeError(out.stderr)
    js = np.fromfile(f"{TMP}/js_ret.f64", dtype=np.float64)
    js_t = np.fromfile(f"{TMP}/js_t.f32", dtype=np.float32)
    js_s = np.fromfile(f"{TMP}/js_ret_sand.f64", dtype=np.float64)

    passable = (flags.reshape(rows, cols) & 8) > 0
    passable.flat[base] = True
    g = build_o2_graph(h.astype(np.float64).reshape(rows, cols), eta.astype(np.float64).reshape(rows, cols), passable)
    py = dijkstra(g.T.tocsr(), directed=True, indices=base)
    eta_s = apply_sand(eta.astype(np.float64).reshape(rows, cols))
    gs = build_o2_graph(h.astype(np.float64).reshape(rows, cols), eta_s, passable)
    py_s = dijkstra(gs.T.tocsr(), directed=True, indices=base)
    fin_s = np.isfinite(py_s) & np.isfinite(js_s)
    rel_s = np.abs(js_s[fin_s] - py_s[fin_s]) / np.maximum(py_s[fin_s], 1e-9)
    sand_cells = np.array(meta["sand_cells"])

    fin = np.isfinite(py) & np.isfinite(js)
    same_reach = bool(np.array_equal(np.isfinite(py), np.isfinite(js)))
    rel = np.abs(js[fin] - py[fin]) / np.maximum(py[fin], 1e-9)
    rng = np.random.default_rng(0)
    sample = rng.choice(np.nonzero(fin & (py > 20))[0], 20, replace=False)
    # 미리 계산해 넣은 귀환 트리(plain_o2, 0.02 g 양자화)와도 비교
    pre = plain_o2.astype(np.float64) / meta["o2_scale"]
    pre_ok = plain_o2 != meta["none16"]
    rel_pre = np.abs(pre[pre_ok & fin] - js[pre_ok & fin]) / np.maximum(js[pre_ok & fin], 1e-9)
    cell_km2 = (meta["cell_m"] / 1000) ** 2
    res = {
        "same_reachable_set": same_reach, "n_reachable": int(fin.sum()),
        "max_rel_err_all": float(rel.max()), "median_rel_err": float(np.median(rel)),
        "sample20": [{"cell": int(i), "py_g": round(float(py[i]), 3), "js_g": round(float(js[i]), 3)} for i in sample],
        "max_rel_err_vs_prebuilt_tree": float(rel_pre[np.isfinite(rel_pre) & (js[pre_ok & fin] > 5)].max()),
        "area_150_js": round(float((js <= 150 - meta["const"]["o2_reserve_g"]).sum() * cell_km2), 3),
        "area_150_py": round(float((py <= 150 - meta["const"]["o2_reserve_g"]).sum() * cell_km2), 3),
        "js_max_time_h": round(float(js_t[np.isfinite(js)].max()) / 3600, 2),
        "sand": {"same_reachable_set": bool(np.array_equal(np.isfinite(py_s), np.isfinite(js_s))),
                 "max_rel_err_all": float(rel_s.max()),
                 "sand_cells_mean_increase_g": round(float(np.nanmean((py_s - py)[sand_cells][np.isfinite(py[sand_cells])])), 3)},
        "pass": same_reach and float(rel.max()) < 1e-3
                and bool(np.array_equal(np.isfinite(py_s), np.isfinite(js_s))) and float(rel_s.max()) < 1e-3,
    }
    json.dump(res, open(f"{TMP}/../js_parity.json", "w"), indent=2)
    print(json.dumps({k: v for k, v in res.items() if k != "sample20"}, indent=1))
    print("sample:", res["sample20"][:5])


if __name__ == "__main__":
    main()
