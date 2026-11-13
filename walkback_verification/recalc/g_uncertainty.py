"""계획 G: 불확실성 결합 — 개인차 k, 해상도 r, 지형 항 배수 m(몬테카를로) × 누설·평지 속도(시나리오)

실행: cd code && ../recalc/.venv/bin/python ../recalc/g_uncertainty.py
  1단계: 평지 속도마다 하위 프로세스(GALE_FLAT_SPEED)로 m = 1, 2, 3의 귀환 산소·귀환 시간을 계산해 캐시에 저장.
  2단계: 칸별 조건  k·r·귀환산소_m + 누설·귀환시간_m ≤ 남은 산소 − (45.0 g + 0.5 h × 누설)  로 표본마다 면적을 센다.
경로는 산소 최소 경로(각 m)로 고정한다. 누설이 있을 때 시간까지 고려한 최적 경로보다 약간 보수적이다.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

sys.path.insert(0, os.getcwd())
import numpy as np  # noqa: E402

OUT = os.path.abspath(os.path.join(os.getcwd(), "..", "recalc", "outputs_g"))
SPEEDS = [0.92, 0.7, 1.1]
LEAKS = [0.0, 4.5, 9.1, 13.6]
BUDGETS = [100, 150, 200]
N_SAMPLES = 2000
SEED = 20261112
K_SD = 0.15
R_RANGE = (1.012, 1.037)
M_RANGE = (1.0, 3.0)


def cache_path(speed: float) -> str:
    return f"{OUT}/cache_v{speed:g}.npz"


def build_cache(speed: float) -> None:
    """GALE_FLAT_SPEED가 이미 설정된 하위 프로세스에서 실행된다."""
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
    out = {"shape": np.array(h.shape), "base": np.array([bx, by]), "o2_reserve_g": np.array(mm.O2_RESERVE_G)}
    for m in (1, 2, 3):
        g, gt = build_o2_graph(h, 1 + m * (eta - 1), passable, return_time=True)
        ret, pred = dijkstra(g.T.tocsr(), directed=True, indices=base, return_predecessors=True)
        # 귀환 트리 시간: v에서 다음 칸 pred[v]로 걷는 간선(원 그래프 v -> pred[v])의 시간을 누적
        t = np.full(ret.shape, np.inf)
        t[base] = 0.0
        reach = np.nonzero(np.isfinite(ret) & (np.arange(ret.size) != base))[0]
        edge_t = np.asarray(gt[reach, pred[reach]]).ravel()
        et = np.zeros(ret.size); et[reach] = edge_t
        for v in reach[np.argsort(ret[reach])]:
            t[v] = t[pred[v]] + et[v]
        out[f"ret_m{m}"] = ret.astype(np.float64)
        out[f"t_h_m{m}"] = t / 3600
        print(f"speed {speed} m {m}: area150 {(ret <= 150 - mm.O2_RESERVE_G).sum() * (CELL_M / 1000) ** 2:.3f}", flush=True)
    out["cell_km2"] = np.array((CELL_M / 1000) ** 2)
    np.savez_compressed(cache_path(speed), **out)


def interp_m(arrs: list, m: float):
    """m ∈ [1, 3]에서 m = 1, 2, 3 결과를 선형 보간."""
    if m <= 2:
        return arrs[0] + (m - 1) * (arrs[1] - arrs[0])
    return arrs[1] + (m - 2) * (arrs[2] - arrs[1])


def samples(n: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    k = rng.normal(1.0, K_SD, n * 2)
    k = k[np.abs(k - 1) <= 3 * K_SD][:n]
    r = rng.uniform(*R_RANGE, n)
    m = rng.uniform(*M_RANGE, n)
    return np.stack([k, r, m], axis=1)


def areas_for(c: dict, smp: np.ndarray, leak: float, prob_budget: float | None = None):
    """표본마다 BUDGETS별 면적(km²). prob_budget이면 그 예산의 칸별 안전 횟수도 돌려준다."""
    res0 = float(c["o2_reserve_g"])
    rets = [c[f"ret_m{m}"] for m in (1, 2, 3)]
    ts = [c[f"t_h_m{m}"] for m in (1, 2, 3)]
    # 어떤 표본에서도 안전할 수 없는 칸은 미리 뺀다(비용 하한 = 최소 k·r × ret_m1)
    lo = smp[:, 0].min() * smp[:, 1].min()
    cand = np.nonzero(np.isfinite(rets[0]) & (lo * rets[0] <= max(BUDGETS) - res0))[0]
    rets = [a[cand] for a in rets]; ts = [a[cand] for a in ts]
    out = np.zeros((len(smp), len(BUDGETS)))
    count = np.zeros(cand.size, np.int32) if prob_budget is not None else None
    for i, (k, r, m) in enumerate(smp):
        cost = k * r * interp_m(rets, m) + leak * interp_m(ts, m)
        for j, b in enumerate(BUDGETS):
            ok = cost <= b - (res0 + 0.5 * leak)
            out[i, j] = ok.sum() * float(c["cell_km2"])
            if prob_budget is not None and b == prob_budget:
                count += ok
    return out, cand, count


def pct(a: np.ndarray) -> dict:
    return {f"p{q}": round(float(np.percentile(a, q)), 2) for q in (5, 10, 50, 90)}


def plot_prob(prob_full: np.ndarray, det_safe: np.ndarray, base, path: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from mars_walkback import hillshade, km_extent, load_dtm_crop
    h, valid, _, _ = load_dtm_crop()
    ext = km_extent(h.shape)
    bx, by = base
    from mars_walkback import CELL_M
    half = int(5000 / CELL_M)
    ys, xs = slice(max(0, by - half), by + half), slice(max(0, bx - half), bx + half)
    fig, ax = plt.subplots(figsize=(8, 8))
    sub_ext = [xs.start * CELL_M / 1000, xs.stop * CELL_M / 1000, ys.stop * CELL_M / 1000, ys.start * CELL_M / 1000]
    ax.imshow(hillshade(h)[ys, xs], cmap="gray", extent=sub_ext)
    p = np.where(valid, prob_full, np.nan)[ys, xs]
    im = ax.imshow(np.where(p > 0, p, np.nan), cmap="viridis", vmin=0, vmax=1, alpha=0.75, extent=sub_ext)
    yy = np.linspace(sub_ext[3], sub_ext[2], p.shape[0]); xx = np.linspace(sub_ext[0], sub_ext[1], p.shape[1])
    cs = ax.contour(xx, yy, np.nan_to_num(p), levels=[0.5, 0.9], colors=["white", "red"], linewidths=1.2)
    ax.clabel(cs, fmt={0.5: "50%", 0.9: "90%"}, fontsize=8)
    ax.contour(xx, yy, det_safe[ys, xs].astype(float), levels=[0.5], colors=["orange"], linewidths=1.0, linestyles="--")
    ax.plot(bx * CELL_M / 1000, by * CELL_M / 1000, "w*", ms=12)
    ax.set_xlabel("km"); ax.set_ylabel("km")
    ax.set_title("Probability of safe walk-back, O2 150 g, no leak, 0.92 m/s\n"
                 "k~N(1,0.15), resolution x U(1.012,1.037), terrain term x U(1,3); dashed = nominal boundary", fontsize=9)
    fig.colorbar(im, ax=ax, fraction=0.04, label="P(safe)")
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    if len(sys.argv) > 2 and sys.argv[1] == "--cache":
        build_cache(float(sys.argv[2])); return
    for v in SPEEDS:
        if not os.path.exists(cache_path(v)):
            env = dict(os.environ, GALE_FLAT_SPEED=str(v))
            r = subprocess.run([sys.executable, os.path.abspath(__file__), "--cache", str(v)], env=env, text=True,
                               capture_output=True)
            if r.returncode:
                raise RuntimeError(r.stderr[-3000:])
            print(r.stdout.strip(), flush=True)

    smp = samples(N_SAMPLES, SEED)
    res = {"n_samples": N_SAMPLES, "seed": SEED, "factors": {"k": f"N(1, {K_SD}) truncated ±3σ", "r": f"U{R_RANGE}",
                                                              "m": f"U{M_RANGE}"},
           "leak_g_per_h": LEAKS, "speeds_m_s": SPEEDS, "budgets_g": BUDGETS, "check": {}, "areas": {}, "oat": {},
           "prob_map_150g": {}, "convergence": {}}
    caches = {v: dict(np.load(cache_path(v))) for v in SPEEDS}

    # 검증: 명목값(k = r = m = 1, 누설 0, 0.92 m/s)
    nom, _, _ = areas_for(caches[0.92], np.array([[1.0, 1.0, 1.0]]), 0.0)
    res["check"]["nominal_area_km2"] = dict(zip(map(str, BUDGETS), nom[0].round(3).tolist()))
    res["check"]["nominal_matches_9.721"] = bool(abs(nom[0][1] - 9.721) < 0.002)

    for v in SPEEDS:
        for leak in LEAKS:
            main_case = (v == 0.92 and leak == 0.0)
            a, cand, cnt = areas_for(caches[v], smp, leak, 150 if main_case else None)
            key = f"v{v:g}_leak{leak:g}"
            res["areas"][key] = {str(b): pct(a[:, j]) for j, b in enumerate(BUDGETS)}
            nom_v, _, _ = areas_for(caches[v], np.array([[1.0, 1.0, 1.0]]), leak)
            res["areas"][key]["nominal"] = dict(zip(map(str, BUDGETS), nom_v[0].round(2).tolist()))
            print(key, res["areas"][key]["150"], "nominal", res["areas"][key]["nominal"]["150"], flush=True)
            if main_case:
                ck = float(caches[v]["cell_km2"])
                prob = cnt / len(smp)
                res["prob_map_150g"] = {f"area_P>={q}": round(float((prob >= q).sum() * ck), 2) for q in (0.5, 0.8, 0.9, 0.95)}
                prob_full = np.zeros(int(np.prod(caches[v]["shape"]))); prob_full[cand] = prob
                ret1 = caches[v]["ret_m1"]
                det = (ret1 <= 150 - float(caches[v]["o2_reserve_g"])).reshape(tuple(caches[v]["shape"]))
                plot_prob(prob_full.reshape(tuple(caches[v]["shape"])), det, tuple(caches[v]["base"]),
                          f"{OUT}/g_safe_probability.png")
                # 수렴: 앞 1,000개 대 전체
                a1, _, _ = areas_for(caches[v], smp[:1000], leak)
                res["convergence"] = {"150_first1000": pct(a1[:, 1]), "150_all2000": pct(a[:, 1])}
                # 요인별 기여(한 요인만 움직임)
                for name, col in (("k", 0), ("r", 1), ("m", 2)):
                    s1 = np.ones_like(smp); s1[:, col] = smp[:, col]
                    ao, _, _ = areas_for(caches[v], s1, leak)
                    res["oat"][name] = pct(ao[:, 1])
                print("oat", res["oat"], flush=True)

    # 20% 비상 여유(설계 여유, 별도 한 줄): k에 1.2를 곱한 것과 같다
    smp20 = smp.copy(); smp20[:, 0] *= 1.2
    a20, _, _ = areas_for(caches[0.92], smp20, 0.0)
    res["areas"]["v0.92_leak0_pad20"] = {str(b): pct(a20[:, j]) for j, b in enumerate(BUDGETS)}
    json.dump(res, open(f"{OUT}/g_uncertainty.json", "w"), ensure_ascii=False, indent=2)
    print(json.dumps({k: res[k] for k in ("check", "prob_map_150g", "convergence", "oat")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
