"""격자 그래프 테스트 (mars_walkback.build_o2_graph, spe_walkback.build_graph)"""
import numpy as np
import pytest
from scipy.sparse.csgraph import dijkstra

import metabolic_model as mm
import mars_walkback as mw


def test_flat_area_close_to_circle_16_neighbors():
    n = 161
    g = mw.build_o2_graph(np.zeros((n, n)), np.ones((n, n)), np.ones((n, n), bool))
    c = (n // 2) * n + n // 2
    cost = dijkstra(g.T.tocsr(), directed=True, indices=c)
    budget = 12.0
    area = (cost <= budget).sum() * (mw.CELL_M / 1000) ** 2
    r_km = budget / mm.LEVEL_O2_G_PER_H * mm.LEVEL_SPEED_M_S * 3.6
    assert r_km * 1000 / mw.CELL_M < n // 2          # 원이 격자 안에 들어와야 비교가 성립
    ratio = area / (np.pi * r_km ** 2)
    assert len(mw.OFFSETS) == 16
    assert 0.95 < ratio < 1.0                          # 16방향 이론값 약 0.972


def test_knight_move_cannot_cross_one_cell_wall():
    p = np.ones((41, 41), bool); p[1:-1, 20] = False
    g = mw.build_o2_graph(np.zeros((41, 41)), np.ones((41, 41)), p)
    d = dijkstra(g, directed=True, indices=20 * 41 + 18)
    straight = 4 * mw.CELL_M * mm.LEVEL_O2_G_PER_H / 3600 / mm.LEVEL_SPEED_M_S
    assert d[20 * 41 + 22] > 3 * straight             # 벽을 돌아가야 한다


def _two_cell_step(rise_m):
    h = np.zeros((3, 4)); h[:, 2:] = rise_m
    return h, np.ones_like(h), np.ones_like(h, bool)


def test_edge_slope_cap(monkeypatch):
    rise = 0.40 * mw.CELL_M                            # 인접 칸 간선 경사 40% > 36.4%
    h, eta, p = _two_cell_step(rise)
    i, j = 1 * 4 + 1, 1 * 4 + 2
    monkeypatch.setattr(mw, "EDGE_SLOPE_CAP", True)
    assert mw.build_o2_graph(h, eta, p)[i, j] == 0     # 간선 없음
    monkeypatch.setattr(mw, "EDGE_SLOPE_CAP", False)
    assert mw.build_o2_graph(h, eta, p)[i, j] > 0      # 상한을 끄면 이전처럼 간선 있음


def test_edge_slope_cap_keeps_allowed_edges(monkeypatch):
    h, eta, p = _two_cell_step(0.30 * mw.CELL_M)       # 30%는 허용
    monkeypatch.setattr(mw, "EDGE_SLOPE_CAP", True)
    assert mw.build_o2_graph(h, eta, p)[1 * 4 + 1, 1 * 4 + 2] > 0


def test_spe_graph_uses_same_cap(monkeypatch):
    import spe_walkback as sw
    h, eta, p = _two_cell_step(0.40 * mw.CELL_M)
    monkeypatch.setattr(mw, "EDGE_SLOPE_CAP", True)
    g = sw.build_graph(h, eta, np.ones_like(h), p)
    assert g[1 * 4 + 1, 1 * 4 + 2] == 0


def test_graph_is_asymmetric_uphill_costs_more():
    h = np.zeros((3, 3)); h[:, 2] = 0.1 * mw.CELL_M
    g = mw.build_o2_graph(h, np.ones_like(h), np.ones_like(h, bool))
    assert g[1 * 3 + 1, 1 * 3 + 2] > g[1 * 3 + 2, 1 * 3 + 1]
