"""계획 J7: 몬테카를로 요인 상관 민감도 — 개인차 k와 평지 속도 v의 음의 상관 (분석만)

실행: cd code && ../recalc/.venv/bin/python ../recalc/j7_correlation.py
- 계획 G의 캐시(outputs_g/cache_v{0.7,0.92,1.1}.npz, m = 1, 2, 3)를 쓴다. m은 구간 선형, v는 0.7–0.92–1.1 구간 선형 보간.
- k ~ N(1, 0.15) ±3σ 절단(계획 G와 같음), r ~ U(1.012, 1.037), m ~ U(1, 3) — 독립.
- v ~ N(0.92, 0.10)를 [0.7, 1.1]로 절단한 분포를 가정(계획 G에서는 시나리오였음, 이 분포는 가정).
- k와 v는 가우스 코퓰라로 상관 ρ ∈ {0, −0.3, −0.6} (대사량이 큰 사람이 느리게 걸음, 크기는 근거 없음).
- 누설 0, 산소 150 g. 경로는 각 캐시의 산소 최소 경로로 고정(계획 G와 같음).
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), "..", "recalc")))
import numpy as np  # noqa: E402
from scipy.stats import norm  # noqa: E402

import g_uncertainty as G  # noqa: E402

OUT = os.path.abspath(os.path.join(os.getcwd(), "..", "recalc", "outputs_j"))
RHOS = (0.0, -0.3, -0.6)
V_MU, V_SD, V_LO, V_HI = 0.92, 0.10, 0.7, 1.1
SPEEDS = (0.7, 0.92, 1.1)
N = 2000


def draw(rho: float, n: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    z1 = rng.standard_normal(n * 3); z2 = rng.standard_normal(n * 3)
    zk = z1; zv = rho * z1 + np.sqrt(1 - rho ** 2) * z2
    k = 1 + G.K_SD * zk
    # v: 절단 정규를 역변환으로(코퓰라의 순위 보존)
    a, b = norm.cdf((V_LO - V_MU) / V_SD), norm.cdf((V_HI - V_MU) / V_SD)
    v = V_MU + V_SD * norm.ppf(a + (b - a) * norm.cdf(zv))
    keep = np.abs(k - 1) <= 3 * G.K_SD
    k, v = k[keep][:n], v[keep][:n]
    r = rng.uniform(*G.R_RANGE, n); m = rng.uniform(*G.M_RANGE, n)
    return np.stack([k, r, m, v], axis=1)


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    caches = [dict(np.load(G.cache_path(s))) for s in SPEEDS]
    res0 = float(caches[1]["o2_reserve_g"]); ck = float(caches[1]["cell_km2"])
    budget = 150 - res0
    rets = [[c[f"ret_m{m}"] for m in (1, 2, 3)] for c in caches]
    # 후보 칸: 어떤 표본에서도 안 될 칸은 뺀다(가장 싼 경우 = 최소 k·r × 세 속도 중 최소 비용)
    cheapest = np.minimum.reduce([r[0] for r in rets])
    out = {"assumption": {"v": f"N({V_MU},{V_SD}) truncated [{V_LO},{V_HI}]", "k": "N(1,0.15) ±3σ", "rho": RHOS},
           "cases": {}}
    for rho in RHOS:
        smp = draw(rho, N, G.SEED)
        lo = smp[:, 0].min() * smp[:, 1].min()
        cand = np.nonzero(np.isfinite(cheapest) & (lo * cheapest <= budget))[0]
        rc = [[a[cand] for a in r] for r in rets]
        areas = np.zeros(len(smp))
        for i, (k, r, m, v) in enumerate(smp):
            if v <= 0.92:
                w = (v - 0.7) / 0.22; base = (1 - w) * G.interp_m(rc[0], m) + w * G.interp_m(rc[1], m)
            else:
                w = (v - 0.92) / 0.18; base = (1 - w) * G.interp_m(rc[1], m) + w * G.interp_m(rc[2], m)
            areas[i] = (k * r * base <= budget).sum() * ck
        emp_rho = float(np.corrcoef(smp[:, 0], smp[:, 3])[0, 1])
        out["cases"][str(rho)] = {"empirical_rho_k_v": round(emp_rho, 3), **G.pct(areas),
                                  "p1": round(float(np.percentile(areas, 1)), 2)}
        print(rho, out["cases"][str(rho)], flush=True)
    json.dump(out, open(f"{OUT}/j7_correlation.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
