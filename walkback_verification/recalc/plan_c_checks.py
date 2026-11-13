"""계획 C 검증: 원본 코드(code/)를 모델·격자 설정별로 돌려 기준값과 비교한다.

실행: cd code && ../recalc/.venv/bin/python ../recalc/plan_c_checks.py
각 설정은 환경 변수(GALE_METABOLIC_MODEL, GALE_GRID_NEIGHBORS)를 바꿔 하위 프로세스로 실행한다.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

PROBE = r'''
import json, numpy as np
from scipy.sparse.csgraph import dijkstra
import metabolic_model as mm
from mars_walkback import (load_dtm_crop, load_traverse, lonlat_to_cell, _wp_lonlat, build_o2_graph, trace,
                           slope_deg_grid, eta_from_rock, CELL_M, MAX_WALK_SLOPE_DEG, O2_RESERVE_G, OFFSETS)
from suit_cooling import water_reserve_g, water_g_per_s
h, valid, rough, _ = load_dtm_crop()
slope = slope_deg_grid(h, CELL_M); passable = valid & (slope <= MAX_WALK_SLOPE_DEG); eta = eta_from_rock(rough)
wps, _ = load_traverse(h.shape)
bx, by = (int(round(v)) for v in lonlat_to_cell(wps[0]["lon"], wps[0]["lat"])); base = by * h.shape[1] + bx
gx, gy = (int(round(v)) for v in lonlat_to_cell(*_wp_lonlat(wps, 1282))); goal = gy * h.shape[1] + gx
g, gt = build_o2_graph(h, eta, passable, return_time=True)
ret, rp = dijkstra(g.T.tocsr(), directed=True, indices=base, return_predecessors=True)
out, op = dijkstra(g, directed=True, indices=base, return_predecessors=True)
cell = (CELL_M / 1000) ** 2
def route_stats(route):
    idx = [y * h.shape[1] + x for x, y in route]
    km = sum(np.hypot(x2 - x1, y2 - y1) for (x1, y1), (x2, y2) in zip(route[:-1], route[1:])) * CELL_M / 1000
    o2 = sum(g[a, b] for a, b in zip(idx[:-1], idx[1:])); t = sum(gt[a, b] for a, b in zip(idx[:-1], idx[1:]))
    return round(km, 3), round(float(o2), 1), round(float(t) / 3600, 3)
wr = water_g_per_s(1.0) / mm.o2_g_per_s(1.0)  # 냉각수/산소 비
res = {"model": mm.describe(), "neighbors": len(OFFSETS), "o2_reserve_g": round(O2_RESERVE_G, 2),
       "water_reserve_g": round(water_reserve_g(), 1)}
for o2_left in (100, 150, 200):
    res[f"area_{o2_left}"] = round(float((ret <= o2_left - O2_RESERVE_G).sum() * cell), 3)
res["area_150_water600"] = round(float(((ret <= 150 - O2_RESERVE_G) & (ret * wr <= 600 - water_reserve_g())).sum() * cell), 3)
gc = g.tocoo(); ya, xa = np.divmod(gc.row, h.shape[1]); yb, xb = np.divmod(gc.col, h.shape[1])
eg = np.abs(h[yb, xb] - h[ya, xa]) / (np.hypot(xb - xa, yb - ya) * CELL_M) * 100
res["n_edges"] = int(g.nnz); res["max_edge_grade_pct"] = round(float(eg.max()), 2); res["n_edges_over_36_4pct"] = int((eg > 36.397).sum())
res["route_out"] = route_stats(trace(op, goal, h.shape))
res["route_back"] = route_stats(trace(rp, goal, h.shape)[::-1])
print("JSON" + json.dumps(res))
'''

FLAT = r'''
import json, numpy as np
from scipy.sparse.csgraph import dijkstra
import metabolic_model as mm
from mars_walkback import build_o2_graph, CELL_M, OFFSETS
n = 241; h = np.zeros((n, n)); eta = np.ones((n, n)); p = np.ones((n, n), bool)
g = build_o2_graph(h, eta, p)
c = (n // 2) * n + n // 2
cost = dijkstra(g.T.tocsr(), directed=True, indices=c)
budget = 20.0
area = float((cost <= budget).sum() * (CELL_M / 1000) ** 2)
r = budget / mm.LEVEL_O2_G_PER_H * mm.LEVEL_SPEED_M_S * 3.6
# 벽 검사: 가운데에 한 칸 두께 통행 불가 세로줄(위아래 끝만 열림)
p2 = np.ones((61, 61), bool); p2[1:-1, 30] = False
g2 = build_o2_graph(np.zeros((61, 61)), np.ones((61, 61)), p2)
d2 = dijkstra(g2, directed=True, indices=30 * 61 + 28)
# 벽 너머 바로 옆 칸까지의 비용이 벽을 돌아가는 거리보다 작으면 벽을 뚫은 것
cross = float(d2[30 * 61 + 32]); detour_min = 2 * 29 * CELL_M * mm.LEVEL_O2_G_PER_H / 3600 / mm.LEVEL_SPEED_M_S
print("JSON" + json.dumps({"neighbors": len(OFFSETS), "area_km2": round(area, 4), "circle_km2": round(np.pi * r * r, 4),
      "ratio_to_circle": round(area / (np.pi * r * r), 4), "wall_cross_cost": round(cross, 2),
      "wall_detour_lower_bound": round(detour_min, 2), "wall_ok": bool(cross >= detour_min * 0.99)}))
'''


def run(code: str, env_over: dict) -> dict:
    env = dict(os.environ, **env_over)
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, cwd=os.getcwd())
    line = [ln for ln in r.stdout.splitlines() if ln.startswith("JSON")]
    if not line:
        raise RuntimeError(r.stderr[-3000:])
    return json.loads(line[-1][4:])


def main() -> None:
    configs = {
        # 계획 E 7번 이후: 기존 설정은 간선 경사 상한 끔(이전 결과 재현), ist_16_cap이 현재 기본 설정
        "legacy_pandolf_8": {"GALE_METABOLIC_MODEL": "pandolf_legacy", "GALE_GRID_NEIGHBORS": "8", "GALE_EDGE_SLOPE_CAP": "0"},
        "ist_8": {"GALE_METABOLIC_MODEL": "ist_b", "GALE_GRID_NEIGHBORS": "8", "GALE_EDGE_SLOPE_CAP": "0"},
        "ist_16": {"GALE_METABOLIC_MODEL": "ist_b", "GALE_GRID_NEIGHBORS": "16", "GALE_EDGE_SLOPE_CAP": "0"},
        "legacy_pandolf_16": {"GALE_METABOLIC_MODEL": "pandolf_legacy", "GALE_GRID_NEIGHBORS": "16", "GALE_EDGE_SLOPE_CAP": "0"},
        "ist_16_cap": {"GALE_METABOLIC_MODEL": "ist_b", "GALE_GRID_NEIGHBORS": "16", "GALE_EDGE_SLOPE_CAP": "1"},
    }
    if len(sys.argv) > 1:
        configs = {k: v for k, v in configs.items() if k in sys.argv[1:]}
    results = {}
    for name, env in configs.items():
        results[name] = {"scene": run(PROBE, env), "flat": run(FLAT, env)}
        print(name, json.dumps(results[name], ensure_ascii=False))
    checks = {}
    if "legacy_pandolf_8" in results:
        s = results["legacy_pandolf_8"]["scene"]
        checks["legacy_reproduces_original"] = {
            "area_150": [s["area_150"], 18.643], "route_back_km": [s["route_back"][0], 7.26],
            "o2_out_back": [s["route_out"][1], s["route_back"][1], 196, 184], "water600": [s["area_150_water600"], 7.383],
            "pass": abs(s["area_150"] - 18.643) < 0.002 and abs(s["route_back"][0] - 7.26) < 0.02
            and abs(s["route_out"][1] - 196) < 1 and abs(s["route_back"][1] - 184) < 1
            and abs(s["area_150_water600"] - 7.383) < 0.002,
        }
    for k in ("legacy_pandolf_8", "ist_8", "ist_16", "legacy_pandolf_16", "ist_16_cap"):
        if k in results:
            checks[f"flat_{k}"] = results[k]["flat"]
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs_c")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "plan_c_checks.json"), "w") as f:
        json.dump({"results": results, "checks": checks}, f, ensure_ascii=False, indent=2)
    print(json.dumps(checks, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
