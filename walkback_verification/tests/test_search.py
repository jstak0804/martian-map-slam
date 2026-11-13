"""A* 최적성, 가시선 이론값"""
import numpy as np
import pytest
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

import metabolic_model as mm
from human_mission_navigation import NEIGHBORS
from metabolic_navigation import astar_o2, step_o2_g


def _terrain(n=31, seed=1):
    rng = np.random.default_rng(seed)
    from scipy.ndimage import gaussian_filter
    h = gaussian_filter(rng.normal(0, 30, (n, n)), 3)
    eta = 1 + 0.5 * rng.random((n, n))
    p = rng.random((n, n)) > 0.1
    return h, eta, p


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_astar_equals_dijkstra(seed):
    h, eta, p = _terrain(seed=seed)
    n = h.shape[0]; cell = 10.0
    s, g = (2, 2), (n - 3, n - 4)
    p[s[1], s[0]] = p[g[1], g[0]] = True
    path = astar_o2(h, eta, p, s, g, cell)
    src, dst, w = [], [], []
    for y in range(n):
        for x in range(n):
            if not p[y, x]:
                continue
            for dx, dy in NEIGHBORS:
                nx, ny = x + dx, y + dy
                if 0 <= nx < n and 0 <= ny < n and p[ny, nx]:
                    src.append(y * n + x); dst.append(ny * n + nx)
                    w.append(step_o2_g(h, eta, cell, x, y, nx, ny, mm.G_RATIO_MARS))
    d = dijkstra(csr_matrix((w, (src, dst)), shape=(n * n, n * n)), indices=s[1] * n + s[0])
    opt = d[g[1] * n + g[0]]
    if not np.isfinite(opt):
        assert path is None; return
    cost = sum(step_o2_g(h, eta, cell, *a, *b, mm.G_RATIO_MARS) for a, b in zip(path[:-1], path[1:]))
    assert cost == pytest.approx(opt, rel=1e-9)


def test_viewshed_horizon_distance():
    from comm_los import BASE_ANT_M, SUIT_ANT_M, viewshed
    from mars_walkback import CELL_M, MARS_RADIUS_M
    h = np.zeros((3, 1001)); valid = np.ones_like(h, bool)
    vis, _ = viewshed(h, valid, (0, 1), BASE_ANT_M, SUIT_ANT_M)
    got = np.nonzero(vis[1])[0].max() * CELL_M
    theory = np.sqrt(2 * MARS_RADIUS_M * BASE_ANT_M) + np.sqrt(2 * MARS_RADIUS_M * SUIT_ANT_M)
    assert abs(got - theory) <= CELL_M
