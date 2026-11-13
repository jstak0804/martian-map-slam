"""대사 모델 단위 테스트 (metabolic_model)"""
import numpy as np
import pytest

import metabolic_model as mm


def test_defaults():
    assert mm.MODEL == "ist_b"
    assert mm.V_FLAT_M_S == pytest.approx(0.92)


def test_reserve_and_level_constants():
    assert mm.RESERVE_MR_W == pytest.approx(1200 * 0.29307, rel=1e-6)       # 352 W (결정 D6)
    assert mm.O2_RESERVE_G == pytest.approx(45.01, abs=0.01)
    assert mm.LEVEL_MR_W == pytest.approx(444.4, abs=0.1)
    assert mm.LEVEL_O2_G_PER_H == pytest.approx(113.74, abs=0.01)


def test_grade_zero_continuous():
    mr = lambda g: float(mm.edge_rate(np.array(g), np.array(1.0))[0])
    assert mr(-1e-6) == pytest.approx(mr(0.0), rel=1e-4)
    assert mr(1e-6) == pytest.approx(mr(0.0), rel=1e-4)


def test_uphill_cost_per_m_increases():
    g = np.linspace(0, 36.4, 200)
    mr, v = mm.edge_rate(g, np.ones_like(g))
    per_m = mm.o2_g_per_s(mr) / v
    assert np.all(np.diff(per_m) > 0)


def test_floor_is_standing_rate():
    g = np.linspace(-80, 80, 1601)
    mr, _ = mm.edge_rate(g, np.ones_like(g))
    assert mr.min() >= mm.STANDING_MR_W - 1e-9


def test_downhill_not_free_and_cheaper_than_uphill():
    for g in (5, 10, 20, 30):
        up = float(mm.o2_g_per_s(mm.edge_rate(np.array(g), np.array(1.0))[0]))
        dn = float(mm.o2_g_per_s(mm.edge_rate(np.array(-g), np.array(1.0))[0]))
        assert 0 < dn < up


def test_eta_increases_cost():
    a = mm.edge_rate(np.array(0.0), np.array(1.0))[0]
    b = mm.edge_rate(np.array(0.0), np.array(1.5))[0]
    assert b > a


def test_heuristic_floor_is_lower_bound():
    from metabolic_navigation import o2_per_m_floor
    g = np.linspace(-100, 100, 4001)
    mr, v = mm.edge_rate(g, np.ones_like(g))
    assert o2_per_m_floor() <= float(np.min(mm.o2_g_per_s(mr) / v)) + 1e-12
