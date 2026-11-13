"""계획 H 후속(2026-11-12 결정): 계획 G 몬테카를로에 η 바닥값 f ~ U(1.0, 1.2)를 요인으로 추가

실행: cd code && env -u PYTHONPATH ../recalc/.venv/bin/python ../recalc/h5_uncertainty_floor.py
- 근거: Richmond et al. 2015 표 11(포장도로 1.0, 자갈·흙길 1.2). 계획 H4에서 f = 1.2면 150 g 면적 −5.9%.
- η' = 1 + m(η − 1) + (f − 1). 계획 G의 m = 1, 2, 3 캐시(f = 1.0, outputs_g/)에 f = 1.2 캐시를 더해
  m은 구간 선형, f는 선형으로 보간한다.
- 표본: k·r·m은 계획 G와 같은 시드·같은 값을 쓰고, f만 별도 난수(SEED + 1)로 더한다. 그래서 G와 짝지어 비교된다.
- 계획 G 스크립트와 결과(outputs_g/)는 바꾸지 않는다.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), "..", "recalc")))
import numpy as np  # noqa: E402

import g_uncertainty as G  # noqa: E402

OUT = os.path.abspath(os.path.join(os.getcwd(), "..", "recalc", "outputs_h"))
F_RANGE = (1.0, 1.2)


def cache_path(speed: float) -> str:
    return f"{OUT}/cache_floor1.2_v{speed:g}.npz"


def build_cache(speed: float) -> None:
    """GALE_FLAT_SPEED가 설정된 하위 프로세스에서 실행. g_uncertainty.build_cache와 같고 η에 0.2를 더한다."""
    from scipy.sparse.csgraph import dijkstra

    import metabolic_model as mm
    from mars_walkback import (CELL_M, MAX_WALK_SLOPE_DEG, build_o2_graph, eta_from_rock, load_dtm_crop,
                               load_traverse, lonlat_to_cell, slope_deg_grid)
    assert abs(mm.V_FLAT_M_S - speed) < 1e-9
    h, valid, rough, _ = load_dtm_crop()
    passable = valid & (slope_deg_grid(h, CELL_M) <= MAX_WALK_SLOPE_DEG)
    eta = eta_from_rock(rough)
    wps, _ = load_traverse(h.shape)
    bx, by = (int(round(v)) for v in lonlat_to_cell(wps[0]["lon"], wps[0]["lat"]))
    base = by * h.shape[1] + bx
    out = {}
    for m in (1, 2, 3):
        g, gt = build_o2_graph(h, 1 + m * (eta - 1) + (F_RANGE[1] - 1), passable, return_time=True)
        ret, pred = dijkstra(g.T.tocsr(), directed=True, indices=base, return_predecessors=True)
        t = np.full(ret.shape, np.inf)
        t[base] = 0.0
        reach = np.nonzero(np.isfinite(ret) & (np.arange(ret.size) != base))[0]
        et = np.zeros(ret.size); et[reach] = np.asarray(gt[reach, pred[reach]]).ravel()
        for v in reach[np.argsort(ret[reach])]:
            t[v] = t[pred[v]] + et[v]
        out[f"ret_m{m}"] = ret.astype(np.float64)
        out[f"t_h_m{m}"] = t / 3600
        print(f"speed {speed} m {m} floor 1.2: area150 {(ret <= 150 - mm.O2_RESERVE_G).sum() * (CELL_M / 1000) ** 2:.3f}",
              flush=True)
    np.savez_compressed(cache_path(speed), **out)


def areas_for(c0: dict, c2: dict, smp: np.ndarray, leak: float, prob_budget: float | None = None):
    """smp 열: k, r, m, f. 반환: 표본×예산 면적(km²), 후보 칸, (prob_budget이면) 칸별 안전 횟수."""
    res0 = float(c0["o2_reserve_g"])
    r0 = [c0[f"ret_m{m}"] for m in (1, 2, 3)]; t0 = [c0[f"t_h_m{m}"] for m in (1, 2, 3)]
    r2 = [c2[f"ret_m{m}"] for m in (1, 2, 3)]; t2 = [c2[f"t_h_m{m}"] for m in (1, 2, 3)]
    lo = smp[:, 0].min() * smp[:, 1].min()
    cand = np.nonzero(np.isfinite(r0[0]) & (lo * r0[0] <= max(G.BUDGETS) - res0))[0]
    r0 = [a[cand] for a in r0]; t0 = [a[cand] for a in t0]; r2 = [a[cand] for a in r2]; t2 = [a[cand] for a in t2]
    out = np.zeros((len(smp), len(G.BUDGETS)))
    count = np.zeros(cand.size, np.int32) if prob_budget is not None else None
    span = F_RANGE[1] - F_RANGE[0]
    for i, (k, r, m, f) in enumerate(smp):
        w = (f - F_RANGE[0]) / span
        ret = (1 - w) * G.interp_m(r0, m) + w * G.interp_m(r2, m)
        tt = (1 - w) * G.interp_m(t0, m) + w * G.interp_m(t2, m)
        cost = k * r * ret + leak * tt
        for j, b in enumerate(G.BUDGETS):
            ok = cost <= b - (res0 + 0.5 * leak)
            out[i, j] = ok.sum() * float(c0["cell_km2"])
            if prob_budget is not None and b == prob_budget:
                count += ok
    return out, cand, count


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    if len(sys.argv) > 2 and sys.argv[1] == "--cache":
        build_cache(float(sys.argv[2])); return
    for v in G.SPEEDS:
        assert os.path.exists(G.cache_path(v)), f"계획 G 캐시 없음: {G.cache_path(v)} (g_uncertainty.py 먼저)"
        if not os.path.exists(cache_path(v)):
            env = dict(os.environ, GALE_FLAT_SPEED=str(v))
            r = subprocess.run([sys.executable, os.path.abspath(__file__), "--cache", str(v)], env=env, text=True,
                               capture_output=True)
            if r.returncode:
                raise RuntimeError(r.stderr[-3000:])
            print(r.stdout.strip(), flush=True)

    krm = G.samples(G.N_SAMPLES, G.SEED)
    f = np.random.default_rng(G.SEED + 1).uniform(*F_RANGE, len(krm))
    smp = np.column_stack([krm, f])
    c0 = {v: dict(np.load(G.cache_path(v))) for v in G.SPEEDS}
    c2 = {v: dict(np.load(cache_path(v))) for v in G.SPEEDS}
    gres = json.load(open(os.path.join(os.path.dirname(G.OUT), "outputs_g", "g_uncertainty.json")))

    res = {"n_samples": G.N_SAMPLES, "seed_krm": G.SEED, "seed_f": G.SEED + 1,
           "factors": {**gres["factors"], "f": f"U{F_RANGE} (eta floor, added to all cells)"},
           "check": {}, "areas": {}, "areas_planG": {}, "oat": {}, "prob_map_150g": {}, "prob_map_150g_planG": gres["prob_map_150g"]}

    # 검증 1: f = 1 고정이면 계획 G 결과와 같아야 한다 (같은 표본, 같은 캐시)
    s1 = smp.copy(); s1[:, 3] = 1.0
    a1, _, _ = areas_for(c0[0.92], c2[0.92], s1, 0.0)
    res["check"]["f1_reproduces_planG_150"] = {"this": G.pct(a1[:, 1]), "planG": gres["areas"]["v0.92_leak0"]["150"]}
    # 검증 2: 명목값 f = 1.2 → 계획 H4 결정적 계산(9.152 km²)
    n2, _, _ = areas_for(c0[0.92], c2[0.92], np.array([[1.0, 1.0, 1.0, 1.2]]), 0.0)
    res["check"]["nominal_f1.2_area_km2"] = dict(zip(map(str, G.BUDGETS), n2[0].round(3).tolist()))

    for v in G.SPEEDS:
        for leak in G.LEAKS:
            main_case = (v == 0.92 and leak == 0.0)
            a, cand, cnt = areas_for(c0[v], c2[v], smp, leak, 150 if main_case else None)
            key = f"v{v:g}_leak{leak:g}"
            res["areas"][key] = {str(b): G.pct(a[:, j]) for j, b in enumerate(G.BUDGETS)}
            res["areas_planG"][key] = {str(b): gres["areas"][key][str(b)] for b in G.BUDGETS}
            print(key, "150:", res["areas"][key]["150"], "planG:", res["areas_planG"][key]["150"], flush=True)
            if main_case:
                ck = float(c0[v]["cell_km2"]); prob = cnt / len(smp)
                res["prob_map_150g"] = {f"area_P>={q}": round(float((prob >= q).sum() * ck), 2) for q in (0.5, 0.8, 0.9, 0.95)}
                ah, _, _ = areas_for(c0[v], c2[v], smp[:1000], leak)
                res["convergence"] = {"150_first1000": G.pct(ah[:, 1]), "150_all2000": G.pct(a[:, 1])}
                for name, col in (("k", 0), ("r", 1), ("m", 2), ("f", 3)):
                    so = np.ones_like(smp); so[:, col] = smp[:, col]
                    ao, _, _ = areas_for(c0[v], c2[v], so, leak)
                    res["oat"][name] = G.pct(ao[:, 1])
                print("oat", res["oat"], flush=True)
    s20 = smp.copy(); s20[:, 0] *= 1.2
    a20, _, _ = areas_for(c0[0.92], c2[0.92], s20, 0.0)
    res["areas"]["v0.92_leak0_pad20"] = {str(b): G.pct(a20[:, j]) for j, b in enumerate(G.BUDGETS)}
    json.dump(res, open(f"{OUT}/h5_uncertainty_floor.json", "w"), ensure_ascii=False, indent=2)
    print(json.dumps({k: res[k] for k in ("check", "prob_map_150g", "prob_map_150g_planG", "convergence", "oat")},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
