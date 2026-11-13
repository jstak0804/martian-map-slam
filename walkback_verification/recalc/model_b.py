"""안 B: IST-1·IST-2 실측(벡터 판독)으로 바꾼 대사 모델로 귀환 가능 면적 계산 (PLAN_B.md)

실행 (원본 코드가 상대 경로를 쓰므로 code/ 안에서, digitize_ist.py를 먼저 실행):
    cd code && ../recalc/.venv/bin/python ../recalc/model_b.py

모델 (속도 v는 경사 속도 방식 ㄱ/ㄴ/ㄷ이 정함):
    VO2(G, W, v) = L(v, W) + ΔG(G, W) · v / V_IST2          [mL/kg/min]
    M [W]        = VO2 · m_body · 20.1 kJ/L / 60 + (η − 1)(m_body + m_suit)·0.378·1.5·v²
  L(v, W)  : IST-1 그림 22 다섯 중력 곡선(2차식)을 TGAW에 대해 선형 회귀
  ΔG(G, W) : IST-2 그림 36 다섯 곡선의 (경사 G − 평지) 증가분을 TGAW에 대해 선형 회귀. G < 0 이면 0
  W        : 화성 무게 = (m_body + m_suit) × 3.711 N/kg
"""
from __future__ import annotations

import csv
import json
import os
import platform
import sys

# 2026-11-12: 이 스크립트는 "원본 모델(Pandolf, 8방향)" 기준으로 쓰였다. 원본 code/의 기본값이 바뀌었으므로
# 원본 모듈을 불러오기 전에 고정한다(PLAN_D 1번).
os.environ["GALE_METABOLIC_MODEL"] = "pandolf_legacy"
os.environ["GALE_GRID_NEIGHBORS"] = "8"
os.environ["GALE_EDGE_SLOPE_CAP"] = "0"   # 계획 E 7번 이전 결과 재현
sys.path.insert(0, os.getcwd())  # code/

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import scipy  # noqa: E402
from scipy.sparse import csr_matrix  # noqa: E402
from scipy.sparse.csgraph import dijkstra  # noqa: E402

from human_mission_navigation import _marker, style_ax  # noqa: E402
from mars_walkback import (  # noqa: E402
    CELL_M, OFFSETS, O2_RESERVE_G, _wp_lonlat, hillshade, km_extent, load_dtm_crop, load_traverse,
    lonlat_to_cell, trace,
)
from metabolic_navigation import (  # noqa: E402
    BODY_MASS_KG, G_RATIO_MARS, MAX_WALK_SLOPE_DEG, O2_G_PER_L, O2_KJ_PER_L, SUIT_MASS_KG, eta_from_rock,
    metabolic_rate_w, o2_g_per_s, slope_deg_grid,
)
from suit_cooling import FEEDWATER_FULL_G, LEVEL_MR_W, water_g_per_s, water_reserve_g  # noqa: E402

HERE = os.path.abspath(os.path.join(os.getcwd(), "..", "recalc"))
OUT = os.path.join(HERE, "outputs_b")
A_TABLE = os.path.join(HERE, "outputs", "k_area_table.csv")

G_MARS = 3.711
V_PANDOLF = 0.92
V_IST2 = 0.77           # IST-2 경사 시험 속도 = IST-1 달 중력 PTS 평균 1.47 − 0.7 m/s
V_LEVEL, V_SLOPE = 0.92, 0.77
TGAW_RANGE = (236.0, 627.0)
GOAL_SOL = 1282
O2_LEFT_G = [100, 150, 200]
WATER_LEFT_G = [FEEDWATER_FULL_G, 600.0]
# Apollo 15 계획 누설률 0.01/0.02/0.03 lb/h (Bellcomm B70 10028, 1970) = 4.5/9.1/13.6 g/h
LEAK_G_PER_H = [0.0, 4.5, 9.1, 13.6]
# Apollo 비상 귀환 대사율 여유: 1200 -> 1440 BTU/h (+20%, 같은 문서)
PAD = [1.0, 1.2]
# 주 결과: fixed444 = 안 B 90 kg·0.92 m/s 평지(444 W) 30분치를 모든 모델·속도 방식에 같은 고정량으로 적용
# 민감도: fixed = Pandolf 301 W 30분치(38.6 g / 219 g), model30 = 모델별 평지 30분치(원문 근거 없음)
RESERVE_DEFS = ("fixed444", "fixed", "model30")
RES444: dict = {}  # main()에서 채움
WATER_PER_O2 = float(water_g_per_s(LEVEL_MR_W) / o2_g_per_s(LEVEL_MR_W))
W_RESERVE_FIXED_G = water_reserve_g(0.0)

SPEED_MODES = {
    "A_all092": "ㄱ 모두 0.92 m/s (오르막 증가분 × 0.92/0.77)",
    "B_all077": "ㄴ 모두 0.77 m/s (실측 그대로)",
    "C_slope": "ㄷ 평지·내리막 0.92, 10% 이상 0.77, 사이 직선",
}
SUITS = {"suit90": 90.0, "suit121": 121.0}


# ============================================================
# 1. 판독 곡선 -> L(v, W), ΔG(G, W)
# ============================================================

def load_curves() -> dict:
    with open(os.path.join(OUT, "b_digitized.json")) as f:
        d = json.load(f)
    tg = {float(k): v for k, v in d["tgaw_n"].items()}

    def lin_coefs(fig: str) -> tuple[np.ndarray, np.ndarray, list[float]]:
        ser = {float(g): s["poly2"] for g, s in d[fig]["series"].items()}
        gs = sorted(ser)
        w = np.array([tg[g] for g in gs])
        c = np.array([ser[g] for g in gs])  # 행: 중력, 열: 2차식 계수
        slope = np.array([np.polyfit(w, c[:, j], 1) for j in range(3)])  # (계수 j) -> [기울기, 절편]
        return w, c, slope

    w1, c1, s1 = lin_coefs("ist1_fig22")
    w2, c2, s2 = lin_coefs("ist2_fig36")
    return {"w": w1, "level_poly": c1, "level_lin": s1, "grade_poly": c2, "grade_lin": s2,
            "level_xmin": max(s["x_min"] for s in d["ist1_fig22"]["series"].values()),
            "grade_xmax": min(s["x_max"] for s in d["ist2_fig36"]["series"].values())}


def level_vo2(cur: dict, v: np.ndarray | float, w_n: float) -> np.ndarray:
    a, b, c = (cur["level_lin"][j, 0] * w_n + cur["level_lin"][j, 1] for j in range(3))
    v = np.asarray(v, dtype=float)
    return a * v ** 2 + b * v + c


def grade_inc_vo2(cur: dict, grade_pct: np.ndarray | float, w_n: float) -> np.ndarray:
    a, b = (cur["grade_lin"][j, 0] * w_n + cur["grade_lin"][j, 1] for j in range(2))
    g = np.maximum(np.asarray(grade_pct, dtype=float), 0.0)
    return a * g ** 2 + b * g


def regression_quality(cur: dict) -> dict:
    """속도·경사별로 다섯 곡선 값이 TGAW에 대해 얼마나 직선인지(R²)."""
    out = {}
    for v in (0.77, 0.92, 1.25):
        y = np.array([np.polyval(p, v) for p in cur["level_poly"]])
        fit = np.polyval(np.polyfit(cur["w"], y, 1), cur["w"])
        out[f"level_v{v}"] = {"vo2_by_g": np.round(y, 2).tolist(),
                              "r2": float(1 - np.sum((y - fit) ** 2) / np.sum((y - y.mean()) ** 2))}
    for g in (10, 20, 30):
        y = np.array([np.polyval(p, g) - np.polyval(p, 0) for p in cur["grade_poly"]])
        fit = np.polyval(np.polyfit(cur["w"], y, 1), cur["w"])
        out[f"grade_inc_{g}pct"] = {"inc_by_g": np.round(y, 2).tolist(),
                                    "r2": float(1 - np.sum((y - fit) ** 2) / np.sum((y - y.mean()) ** 2))}
    return out


# ============================================================
# 2. 모델 정의
# ============================================================

def speed_of(mode: str, grade_pct: np.ndarray) -> np.ndarray:
    g = np.asarray(grade_pct, dtype=float)
    if mode == "A_all092":
        return np.full_like(g, V_LEVEL)
    if mode == "B_all077":
        return np.full_like(g, V_SLOPE)
    frac = np.clip(g / 10.0, 0.0, 1.0)
    return V_LEVEL - (V_LEVEL - V_SLOPE) * frac


def make_model(name: str, cur: dict | None, mode: str | None, suit_kg: float) -> dict:
    w_n = (BODY_MASS_KG + suit_kg) * G_MARS

    def rate(grade_pct: np.ndarray, eta: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """(대사량 W, 속도 m/s)"""
        if cur is None:  # 기존 Pandolf
            return metabolic_rate_w(grade_pct, eta, G_RATIO_MARS), np.full_like(np.asarray(grade_pct, float), V_PANDOLF)
        v = speed_of(mode, grade_pct)
        vo2 = level_vo2(cur, v, w_n) + grade_inc_vo2(cur, grade_pct, w_n) * v / V_IST2
        terrain = (eta - 1.0) * (BODY_MASS_KG + suit_kg) * G_RATIO_MARS * 1.5 * v ** 2
        return vo2 * BODY_MASS_KG * O2_KJ_PER_L / 60.0 + terrain, v

    lvl_w, lvl_v = rate(np.array(0.0), np.array(1.0))
    lvl_o2_g_h = float(lvl_w) / (O2_KJ_PER_L * 1000) * O2_G_PER_L * 3600
    return {"name": name, "mode": mode, "suit_kg": suit_kg, "w_n": w_n, "rate": rate,
            "level_w": float(lvl_w), "level_v": float(lvl_v), "level_o2_g_h": lvl_o2_g_h,
            "extrapolated": bool(cur is not None and not (TGAW_RANGE[0] <= w_n <= TGAW_RANGE[1]))}


# ============================================================
# 3. 그래프·트리
# ============================================================

def edge_arrays(h, eta, passable, model):
    rows, cols = h.shape
    idx = np.arange(rows * cols).reshape(rows, cols)
    src, dst, o2c, tc = [], [], [], []
    for dx, dy in OFFSETS:
        ys, ye = max(0, -dy), rows - max(0, dy)
        xs, xe = max(0, -dx), cols - max(0, dx)
        a = (slice(ys, ye), slice(xs, xe))
        b = (slice(ys + dy, ye + dy), slice(xs + dx, xe + dx))
        ok = passable[a] & passable[b]
        dist_m = float(np.hypot(dx, dy)) * CELL_M
        grade = (h[b] - h[a]) / dist_m * 100
        e = 0.5 * (eta[a] + eta[b])
        mr, v = model["rate"](grade, e)
        t_s = dist_m / v
        src.append(idx[a][ok]); dst.append(idx[b][ok])
        o2c.append((mr / (O2_KJ_PER_L * 1000) * O2_G_PER_L * t_s)[ok]); tc.append(t_s[ok])
    n = rows * cols
    s, d = np.concatenate(src), np.concatenate(dst)
    g_o2 = csr_matrix((np.concatenate(o2c), (s, d)), shape=(n, n))
    g_t = csr_matrix((np.concatenate(tc), (s, d)), shape=(n, n))
    return g_o2, g_t


def tree_sum(cost: np.ndarray, pred: np.ndarray, edge_graph: csr_matrix, child_to_parent: bool) -> np.ndarray:
    """최단경로 트리를 비용 순으로 따라가며 edge_graph 값을 누적.
    child_to_parent=True(귀환): 간선은 칸 -> 부모(거점 쪽). False(나가기): 부모 -> 칸."""
    n = cost.size
    acc = np.full(n, np.nan)
    order = np.argsort(cost)
    order = order[np.isfinite(cost[order])]
    acc[order[0]] = 0.0
    v = order[1:]
    p = pred[v]
    e = np.asarray(edge_graph[v, p] if child_to_parent else edge_graph[p, v]).ravel()
    step = np.zeros(n)
    step[v] = e
    for node in v:
        acc[node] = acc[pred[node]] + step[node]
    return acc


def path_metrics(route, h, slope, g_o2, g_t):
    idx = [y * h.shape[1] + x for x, y in route]
    dist = sum(np.hypot(x2 - x1, y2 - y1) * CELL_M for (x1, y1), (x2, y2) in zip(route[:-1], route[1:]))
    asc = sum(max(0.0, h[y2, x2] - h[y1, x1]) for (x1, y1), (x2, y2) in zip(route[:-1], route[1:]))
    o2 = sum(g_o2[a, b] for a, b in zip(idx[:-1], idx[1:]))
    t = sum(g_t[a, b] for a, b in zip(idx[:-1], idx[1:]))
    return {"km": round(dist / 1000, 3), "o2_g": round(float(o2), 1), "ascent_m": round(float(asc), 1),
            "max_slope_deg": round(float(max(slope[y, x] for x, y in route)), 1), "hours": round(float(t) / 3600, 3)}


# ============================================================
# 4. 시나리오 판정
# ============================================================

def reserves(model: dict, rdef: str, leak: float) -> tuple[float, float]:
    if rdef == "fixed":
        return O2_RESERVE_G, W_RESERVE_FIXED_G
    if rdef == "fixed444":
        return RES444["o2_g"], RES444["water_g"]
    o2 = 0.5 * (model["level_o2_g_h"] + leak)
    return o2, 0.5 * model["level_o2_g_h"] * WATER_PER_O2


def areas(model: dict, ret_o2: np.ndarray, ret_t_h: np.ndarray) -> list[dict]:
    cell_km2 = (CELL_M / 1000) ** 2
    rows = []
    for pad in PAD:
      water = pad * ret_o2 * WATER_PER_O2
      for o2_left in O2_LEFT_G:
        for wl in WATER_LEFT_G:
            for leak in LEAK_G_PER_H:
                for rdef in RESERVE_DEFS:
                    o2_res, w_res = reserves(model, rdef, leak)
                    with np.errstate(invalid="ignore"):
                        ok_o2 = pad * ret_o2 + leak * ret_t_h <= o2_left - o2_res
                        ok_w = water <= wl - w_res
                    rows.append({
                        "model": model["name"], "suit_kg": model["suit_kg"], "speed_mode": model["mode"] or "pandolf",
                        "extrapolated": model["extrapolated"], "pad": pad, "o2_left_g": o2_left, "water_left_g": wl,
                        "leak_g_per_h": leak, "reserve_def": rdef, "o2_reserve_g": round(o2_res, 1),
                        "area_km2": round(float((ok_o2 & ok_w).sum() * cell_km2), 3),
                        "binding": "water" if (ok_o2 & ~ok_w).any() else "o2",
                    })
    return rows


# ============================================================
# 5. 검증
# ============================================================

def flat_grid_check(model: dict) -> dict:
    """평지·η=1 합성 격자에서 8방향 거리 영역과 비교. 대각 비용 √2인 8방향 거리의 R-구는
    반경 R 원에 내접하는 정팔각형(꼭짓점 (R,0), (R/√2,R/√2))이고 넓이는 2√2·R²."""
    n = 241
    h = np.zeros((n, n)); eta = np.ones((n, n)); passable = np.ones((n, n), bool)
    g_o2, _ = edge_arrays(h, eta, passable, model)
    c = (n // 2) * n + n // 2
    cost = dijkstra(g_o2.T.tocsr(), directed=True, indices=c)
    budget = 20.0  # 반경이 격자(반폭 1.2 km) 안에 들도록 작은 예산 사용
    area = float((cost <= budget).sum() * (CELL_M / 1000) ** 2)
    r_km = budget / model["level_o2_g_h"] * model["level_v"] * 3.6
    octagon = 2 * np.sqrt(2) * r_km ** 2
    return {"area_km2": round(area, 3), "octagon_km2": round(octagon, 3), "rel_err": round(area / octagon - 1, 4)}


def effective_k(area: float) -> float | None:
    """안 A 표(예비분 고정, 만충, 누설 0, 산소 150 g)에서 같은 면적이 되는 k (선형 보간)."""
    with open(A_TABLE) as f:
        a = [r for r in csv.DictReader(f) if r["o2_left_g"] == "150" and r["water_left_g"] == "3600.0"
             and r["leak_g_per_h"] == "0.0" and r["reserve_def"] == "fixed"]
    ks = np.array([float(r["k"]) for r in a]); ar = np.array([float(r["area_km2"]) for r in a])
    o = np.argsort(ks); ks, ar = ks[o], ar[o]
    if not (ar.min() <= area <= ar.max()):
        return None
    return round(float(np.interp(area, ar[::-1], ks[::-1])), 3)


# ============================================================
# 6. 그림
# ============================================================

COLORS = {"pandolf": "#e6e9ef", "A_all092": "#5cbcc3", "B_all077": "#e3a857", "C_slope": "#ff6b8a"}


def plot_boundaries(scene, results, path):
    fig, axes = plt.subplots(1, 2, figsize=(13, 8), facecolor="#0b0f17")
    shape = scene["h"].shape
    xs = np.arange(shape[1]) * CELL_M / 1000; ys = np.arange(shape[0]) * CELL_M / 1000
    for ax, suit in zip(axes, SUITS):
        style_ax(ax)
        ax.imshow(np.where(scene["valid"], hillshade(scene["h"]), np.nan), cmap="gray", extent=km_extent(shape))
        handles = []
        for key, r in results.items():
            m = r["model"]
            if not (m["name"] == "pandolf" or m["name"].startswith(suit)):
                continue
            o2_res, _ = reserves(m, "fixed444", 0.0)
            ok = (r["ret_o2"] <= 150 - o2_res).astype(float)
            col = COLORS[m["mode"] or "pandolf"]
            ls = {"A_all092": "-", "B_all077": "-", "C_slope": "--"}.get(m["mode"], "-")
            ax.contour(xs, ys, ok, levels=[0.5], colors=col, linewidths=1.5, linestyles=ls)
            a = ok.sum() * (CELL_M / 1000) ** 2
            lab = "Pandolf (current)" if m["mode"] is None else m["mode"].split("_")[1]
            handles.append(plt.Line2D([], [], color=col, lw=1.8, ls=ls, label=f"{lab}: {a:.1f} km2"))
        for tx, ty in scene["traverse_xy"]:
            ax.plot(tx * CELL_M / 1000, ty * CELL_M / 1000, color="white", lw=0.4, alpha=0.5)
        bx, by = scene["base"]
        _marker(ax, (bx * CELL_M / 1000, by * CELL_M / 1000), "#ffd166", marker="*", size=150)
        ext = " (EXTRAPOLATED weight)" if suit == "suit121" else ""
        ax.set_title(f"{SUITS[suit]:.0f} kg suit{ext}: 150 g O2, water full, no leak, reserve fixed 56.9 g (30 min at 444 W)",
                     color="#e6e9ef", fontsize=8.5)
        ax.legend(handles=handles, fontsize=7, loc="lower left", facecolor="#141a26", labelcolor="#e6e9ef",
                  edgecolor="#2a3142")
    fig.tight_layout(); fig.savefig(path, dpi=140, facecolor=fig.get_facecolor()); plt.close(fig)


def plot_routes(scene, results, path):
    fig, ax = plt.subplots(figsize=(7, 8), facecolor="#0b0f17")
    style_ax(ax)
    shape = scene["h"].shape
    ax.imshow(np.where(scene["valid"], hillshade(scene["h"]), np.nan), cmap="gray", extent=km_extent(shape))
    handles = []
    for key, r in results.items():
        m = r["model"]
        if not (m["name"] == "pandolf" or m["name"].startswith("suit90")):
            continue
        col = COLORS[m["mode"] or "pandolf"]
        for route, ls in ((r["route_out"], "-"), (r["route_back"], "--")):
            px, py = zip(*route)
            ax.plot(np.array(px) * CELL_M / 1000, np.array(py) * CELL_M / 1000, ls, color=col, lw=1.3)
        lab = "Pandolf" if m["mode"] is None else m["mode"]
        handles.append(plt.Line2D([], [], color=col, lw=1.8, label=f"{lab} (solid out, dashed back)"))
    bx, by = scene["base"]
    _marker(ax, (bx * CELL_M / 1000, by * CELL_M / 1000), "#ffd166", marker="*", size=150)
    ax.legend(handles=handles, fontsize=7, loc="lower left", facecolor="#141a26", labelcolor="#e6e9ef",
              edgecolor="#2a3142")
    ax.set_title(f"Landing -> sol {GOAL_SOL}, 90 kg suit models", color="#e6e9ef", fontsize=9)
    fig.tight_layout(); fig.savefig(path, dpi=140, facecolor=fig.get_facecolor()); plt.close(fig)


def plot_asymmetry(scene, results, path):
    keys = ["pandolf", "suit90_A_all092", "suit90_B_all077", "suit90_C_slope"]
    fig, axes = plt.subplots(1, 4, figsize=(16, 5.4), facecolor="#0b0f17")
    shape = scene["h"].shape
    for ax, k in zip(axes, keys):
        style_ax(ax)
        r = results[k]
        with np.errstate(invalid="ignore", divide="ignore"):
            ratio = r["ret_o2"] / r["out_o2"]
        o2_res, _ = reserves(r["model"], "fixed444", 0.0)
        mask = r["ret_o2"] <= 150 - o2_res
        im = ax.imshow(np.where(mask, ratio, np.nan), cmap="coolwarm", vmin=0.7, vmax=1.3, extent=km_extent(shape))
        med = float(np.nanmedian(ratio[mask]))
        ax.set_title(f"{k}\nreturn/out O2, median {med:.2f}", color="#e6e9ef", fontsize=8)
    fig.colorbar(im, ax=axes, fraction=0.015)
    fig.savefig(path, dpi=130, facecolor=fig.get_facecolor()); plt.close(fig)


# ============================================================
# 7. 실행
# ============================================================

def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    cur = load_curves()

    h, valid, rough_r, _ = load_dtm_crop()
    slope = slope_deg_grid(h, CELL_M)
    passable = valid & (slope <= MAX_WALK_SLOPE_DEG)
    eta = eta_from_rock(rough_r)
    wps, traverse_xy = load_traverse(h.shape)
    bx, by = (int(round(v)) for v in lonlat_to_cell(wps[0]["lon"], wps[0]["lat"]))
    base_idx = by * h.shape[1] + bx
    gx, gy = (int(round(v)) for v in lonlat_to_cell(*_wp_lonlat(wps, GOAL_SOL)))
    goal = gy * h.shape[1] + gx
    scene = {"h": h, "valid": valid, "traverse_xy": traverse_xy, "base": (bx, by)}

    models = {"pandolf": make_model("pandolf", None, None, SUIT_MASS_KG)}
    for s, kg in SUITS.items():
        for mode in SPEED_MODES:
            models[f"{s}_{mode}"] = make_model(f"{s}_{mode}", cur, mode, kg)

    # 경사 분포: 데이터 범위(30%)를 넘는 칸 이동 비율
    gr = np.abs(np.tan(np.radians(slope[passable]))) * 100
    grade_beyond = float((gr > cur["grade_xmax"]).mean())

    ref = models["suit90_A_all092"]
    RES444.update({"level_w": ref["level_w"], "o2_g": 0.5 * ref["level_o2_g_h"],
                   "water_g": 0.5 * ref["level_o2_g_h"] * WATER_PER_O2})
    print(f"고정 예비분(444 W 기준): 산소 {RES444['o2_g']:.1f} g, 냉각수 {RES444['water_g']:.0f} g")

    results, rows, route_rows = {}, [], []
    for key, m in models.items():
        g_o2, g_t = edge_arrays(h, eta, passable, m)
        ret, ret_pred = dijkstra(g_o2.T.tocsr(), directed=True, indices=base_idx, return_predecessors=True)
        out, out_pred = dijkstra(g_o2, directed=True, indices=base_idx, return_predecessors=True)
        ret_t_h = tree_sum(ret, ret_pred, g_t, child_to_parent=True) / 3600
        route_out = trace(out_pred, goal, h.shape)
        route_back = trace(ret_pred, goal, h.shape)[::-1]
        results[key] = {"model": m, "ret_o2": ret.reshape(h.shape), "out_o2": out.reshape(h.shape),
                        "route_out": route_out, "route_back": route_back}
        rows += areas(m, ret.reshape(h.shape), ret_t_h.reshape(h.shape))
        np.savez_compressed(os.path.join(OUT, f"b_return_{key}.npz"), ret_o2=ret.reshape(h.shape).astype(np.float32),
                            ret_t_h=ret_t_h.reshape(h.shape).astype(np.float32))
        for direction, rt in (("out", route_out), ("back", route_back)):
            route_rows.append({"model": key, "direction": direction, **path_metrics(rt, h, slope, g_o2, g_t)})
        print(f"{key:<22} 평지 {m['level_w']:.0f} W @ {m['level_v']:.2f} m/s, 산소 {m['level_o2_g_h']:.1f} g/h"
              f"{'  [외삽]' if m['extrapolated'] else ''}")

    # 경로 공유 비율 (Pandolf 경로와 같은 칸)
    base_cells = set(results["pandolf"]["route_out"])
    for rr in route_rows:
        r = results[rr["model"]]
        rt = r["route_out"] if rr["direction"] == "out" else r["route_back"]
        ref = results["pandolf"]["route_out" if rr["direction"] == "out" else "route_back"]
        rr["shared_with_pandolf"] = round(len(set(rt) & set(ref)) / len(set(rt)), 3)

    # ---------- 검증 ----------
    pick = lambda **kw: [r for r in rows if all(r[a] == b for a, b in kw.items())]  # noqa: E731
    checks = {}
    p0 = pick(model="pandolf", pad=1.0, o2_left_g=150, water_left_g=FEEDWATER_FULL_G, leak_g_per_h=0.0, reserve_def="fixed")[0]
    checks["pandolf_area_150"] = {"got": p0["area_km2"], "want": 18.643}
    assert abs(p0["area_km2"] - 18.643) < 0.002, p0
    p_back = [r for r in route_rows if r["model"] == "pandolf" and r["direction"] == "back"][0]
    p_out = [r for r in route_rows if r["model"] == "pandolf" and r["direction"] == "out"][0]
    checks["pandolf_route"] = {"out": p_out, "back": p_back, "report15": "7.26 km, 갈 때 196 g, 올 때 184 g"}
    assert abs(p_back["km"] - 7.26) < 0.02 and abs(p_out["o2_g"] - 196) < 1 and abs(p_back["o2_g"] - 184) < 1
    w06 = pick(model="pandolf", pad=1.0, o2_left_g=150, water_left_g=600.0, leak_g_per_h=0.0, reserve_def="fixed")[0]
    checks["pandolf_water_0p6"] = {"got": w06["area_km2"], "k_scenarios": 7.383}
    assert abs(w06["area_km2"] - 7.383) < 0.002
    for s, kg in SUITS.items():
        w_n = (BODY_MASS_KG + kg) * G_MARS
        g = np.linspace(0, 40, 401)
        inc = grade_inc_vo2(cur, g, w_n)
        assert inc[0] == 0 and np.all(np.diff(inc) >= -1e-9), (s, "ΔG 단조")
        checks[f"grade_inc_monotonic_{s}"] = True
    checks["flat_grid"] = {k: flat_grid_check(models[k]) for k in ("pandolf", "suit90_A_all092", "suit90_B_all077")}
    for k, v in checks["flat_grid"].items():
        assert abs(v["rel_err"]) < 0.02, (k, v)
    l092 = float(level_vo2(cur, 0.92, models["suit90_A_all092"]["w_n"]))
    checks["level_vo2_092_suit90"] = {"vo2": round(l092, 2), "scatter_range_ist1": [13, 19]}
    assert 13 <= l092 <= 19
    checks["eyeball_vs_vector"] = {
        "level_0.92_0.32g": {"vector": round(float(np.polyval(cur["level_poly"][4], 0.92)), 2), "eyeball": 17.0},
        "grade_0.32g": {g: {"vector": round(float(np.polyval(cur["grade_poly"][4], g)), 2), "eyeball": e}
                        for g, e in ((0, 16.2), (10, 18.4), (20, 23.6), (30, 31.5))},
    }
    for v in checks["eyeball_vs_vector"]["grade_0.32g"].values():
        assert abs(v["vector"] - v["eyeball"]) <= 1.0
    # 교차 확인 (판정 아님)
    ist1_077 = float(np.polyval(cur["level_poly"][4], 0.77)); ist2_0 = float(np.polyval(cur["grade_poly"][4], 0))
    ewt_w = (81.4 + 120) * 3.68
    cross = {
        "ist1_level_0.77_vs_ist2_0pct_0.32g": [round(ist1_077, 2), round(ist2_0, 2)],
        "ewt_3_8g_vs_model": {f"v{v}": {"ewt": e, "model_at_ewt_weight_extrap": round(float(level_vo2(cur, v, ewt_w)), 2)}
                              for v, e in ((1.25, 27.6), (1.38, 32.5), (1.52, 35.7))},
        "ewt_weight_n": round(ewt_w, 1),
        "grade_edges_beyond_30pct_fraction": round(grade_beyond, 4),
    }

    # ---------- 유효 k, 저장 ----------
    eff = {}
    for key in models:
        a = pick(model=key, pad=1.0, o2_left_g=150, water_left_g=FEEDWATER_FULL_G, leak_g_per_h=0.0, reserve_def="fixed")[0]
        eff[key] = {"area_km2_fixed_reserve": a["area_km2"], "effective_k_vs_plan_A": effective_k(a["area_km2"]),
                    "level_o2_ratio_vs_pandolf": round(models[key]["level_o2_g_h"] / models["pandolf"]["level_o2_g_h"]
                                                       * models["pandolf"]["level_v"] / models[key]["level_v"], 3)}
    with open(os.path.join(OUT, "b_area_table.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    with open(os.path.join(OUT, "b_routes.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(route_rows[0])); w.writeheader(); w.writerows(route_rows)
    with open(os.path.join(OUT, "b_effective_k.json"), "w") as f:
        json.dump(eff, f, ensure_ascii=False, indent=2)
    summary = {
        "models": {k: {kk: vv for kk, vv in m.items() if kk != "rate"} for k, m in models.items()},
        "speed_modes": SPEED_MODES, "regression_quality": regression_quality(cur), "checks": checks, "cross": cross,
        "reserve_fixed444": dict(RES444),
        "level_lin_coefs(per TGAW N: [slope, intercept] for a,b,c)": cur["level_lin"].tolist(),
        "grade_lin_coefs(per TGAW N: [slope, intercept] for a,b)": cur["grade_lin"][:2].tolist(),
        "env": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
                "matplotlib": matplotlib.__version__},
    }
    with open(os.path.join(OUT, "b_summary.json"), "w") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=float)

    plot_boundaries(scene, results, os.path.join(OUT, "b_boundary_map.png"))
    plot_routes(scene, results, os.path.join(OUT, "b_route_sol1282.png"))
    plot_asymmetry(scene, results, os.path.join(OUT, "b_asymmetry.png"))

    print("\n검증 통과:", ", ".join(checks))
    print("교차 확인:", json.dumps(cross, ensure_ascii=False))
    print("\n산소 150 g, 냉각수 만충, 누설 0 (km2)")
    print(f"{'model':<22} {'444W고정':>9} {'모델30분':>9} {'38.6고정':>9} {'유효 k':>8}")
    for key in models:
        a30 = pick(model=key, pad=1.0, o2_left_g=150, water_left_g=FEEDWATER_FULL_G, leak_g_per_h=0.0, reserve_def="model30")[0]
        a444 = pick(model=key, pad=1.0, o2_left_g=150, water_left_g=FEEDWATER_FULL_G, leak_g_per_h=0.0, reserve_def="fixed444")[0]
        print(f"{key:<22} {a444['area_km2']:9.2f} {a30['area_km2']:9.2f} {eff[key]['area_km2_fixed_reserve']:9.2f} "
              f"{str(eff[key]['effective_k_vs_plan_A']):>8}{'  [외삽]' if models[key]['extrapolated'] else ''}")
    print("\n경로 (착륙지 <-> sol 1282)")
    for rr in route_rows:
        print(f"  {rr['model']:<22} {rr['direction']:<4} {rr['km']:.2f} km, O2 {rr['o2_g']:.0f} g, 오르막 {rr['ascent_m']:.0f} m, "
              f"최대 {rr['max_slope_deg']}°, {rr['hours']:.2f} h, Pandolf 경로 공유 {rr['shared_with_pandolf']:.0%}")


if __name__ == "__main__":
    main()
