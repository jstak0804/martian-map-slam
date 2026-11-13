"""
올인원 HTML 데모(reports/18-eva-walkback-demo.html)에 넣을 격자 데이터를 만든다.

브라우저에서 슬라이더를 움직일 때마다 경로 탐색을 다시 돌리지 않도록, 거점으로 돌아오는 경로 트리를
미리 계산해 두고 칸마다 "그 트리를 따라 돌아올 때" 드는 값을 저장한다.
  - o2_g     : 귀환 산소 (g, k = 1)
  - time_s   : 귀환 시간 (s)
  - dose1    : 귀환 선량 (mSv, SPE 배율 1 = 배경)
  - pred     : 귀환 경로의 다음 칸 방향 (OFFSETS 번호, 8 = 거점, 255 = 갈 수 없음)
현재 위치·구조 모드와 거점 옮기기는 임의 지점에서 출발하는 경로(와 새 거점의 통신 가시권)가 필요하므로, 브라우저가 직접 다익스트라를 돌릴 수
있게 간선 비용 재료(고도 h, 지형 계수 eta, 차폐 proxy)도 넣는다. 간선 산소 비용은 mars_walkback.build_o2_graph와
같은 식이다.
경로 트리는 산소 최소 경로 하나다(spe_walkback은 선량·냉각수 몫까지 섞어 경로를 고르지만, 데모에서는
같은 경로 위에서 선량·냉각수를 평가한다). 넘어짐 "높음" 칸 금지 여부에 따라 트리를 두 벌 만든다.

브라우저 쪽 계산 (k = 심박 보정계수, Q = 환경·PLSS 열):
  산소 OK   : k * o2_g <= 남은 산소 - O2 예비분
  선량 OK   : 배율 * dose1 <= 1 mSv
  냉각수 OK : max(0, k * E + Q * time_s) / 증발잠열 <= 남은 냉각수 - 냉각수 예비분(Q),  E = o2_g / (O2 g per J)

실행: python dune_mask.py && python build_demo_data.py   -> outputs/demo/demo_data.bin(gzip), demo_meta.json, hillshade.png
"""
from __future__ import annotations

import gzip
import json
import os

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.sparse.csgraph import dijkstra

from metabolic_navigation import (
    O2_KJ_PER_L, O2_G_PER_L, BODY_MASS_KG, SUIT_MASS_KG, G_RATIO_MARS, ETA_MIN, ETA_MAX, metabolic_rate_w,
)
from human_mission_navigation import EVA_WALK_SPEED_M_S
from human_mission_risk import SPE_DOSE_MULTIPLIER, D_BACKGROUND_MSV_DAY, SHIELDING_MAX_REDUCTION
from mars_walkback import (
    build_o2_graph, hillshade, lonlat_to_cell, _wp_lonlat, load_dtm_crop, load_traverse,
    OFFSETS, CELL_M, O2_RESERVE_G, LEVEL_O2_G_PER_H,
)
from spe_walkback import load_scene, edge_values, dose_rate_msv_h, DOSE_BUDGET_MSV
from comm_los import viewshed, BASE_ANT_M, SUIT_ANT_M, RELAY_ANT_M, STEP as LOS_STEP
from mars_walkback import MARS_RADIUS_M
from fall_risk_map import hazard_fraction, HIGH_FRAC, MED_FRAC
from suit_cooling import (
    LATENT_HEAT_J_PER_KG, FEEDWATER_FULL_G, HEAT_STORAGE_WATER_EQ_G, LEVEL_MR_W,
)

from hackathon.params import load_active

OUT_DIR = "../outputs/demo"
os.makedirs(OUT_DIR, exist_ok=True)
GOAL_SOL = 1282
O2_SCALE = 50      # uint16: 0.02 g 단위 (최대 1310 g)
DOSE_SCALE = 5e5   # uint16: 0.002 uSv 단위 (최대 131 uSv)
NONE16 = 65535


def return_tree(h, eta, rate, passable, base_idx):
    """산소 최소 귀환 트리와 트리를 따라 누적한 (산소, 시간, 선량, 방향 코드)."""
    rows, cols = h.shape
    n = rows * cols
    g = build_o2_graph(h, eta, passable)
    cost, pred = dijkstra(g.T.tocsr(), directed=True, indices=base_idx, return_predecessors=True)
    has = pred >= 0
    v = np.nonzero(has)[0]
    p = pred[v]
    o2_e, dose_e, _ = edge_values(h, eta, rate, v // cols, v % cols, p // cols, p % cols)
    t_e = np.hypot(v % cols - p % cols, v // cols - p // cols) * CELL_M / EVA_WALK_SPEED_M_S
    eo2, edose, et = np.zeros(n), np.zeros(n), np.zeros(n)
    eo2[v], edose[v], et[v] = o2_e, dose_e, t_e
    o2, dose, t = np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan)
    order = np.argsort(cost)
    order = order[np.isfinite(cost[order])]
    o2[order[0]] = dose[order[0]] = t[order[0]] = 0.0
    for node in order[1:]:
        q = pred[node]
        o2[node] = o2[q] + eo2[node]
        dose[node] = dose[q] + edose[node]
        t[node] = t[q] + et[node]
    code = np.full(n, 255, np.uint8)
    dx, dy = p % cols - v % cols, p // cols - v // cols
    lut = {off: i for i, off in enumerate(OFFSETS)}
    code[v] = [lut[(a, b)] for a, b in zip(dx, dy)]
    code[base_idx] = 8
    return o2.reshape(h.shape), t.reshape(h.shape), dose.reshape(h.shape), code.reshape(h.shape)


def q16(a, scale):
    out = np.where(np.isfinite(a), np.clip(np.rint(a * scale), 0, NONE16 - 1), NONE16)
    return out.astype("<u2")


def main():
    # 보정 파라미터: 기본은 문헌값. python -m hackathon.params --activate 로 해커톤 자료 보정값을 켤 수 있다.
    CAL = load_active()
    import spe_walkback as _sw
    _sw.D_BACKGROUND_MSV_DAY = CAL["dose"]["bg_msv_day"]     # 귀환 트리의 선량도 같은 배경값으로
    print(f"모델 파라미터: {CAL['_status']}")
    h, valid, eta, shielding, passable, traverse_xy, base = load_scene()
    rows, cols = h.shape
    bx, by = base
    base_idx = by * cols + bx
    rate1 = dose_rate_msv_h(shielding, 1.0)

    # 넘어짐 위험 등급 (fall_risk_map.py와 같은 정의)
    _, _, _, h1 = load_dtm_crop()
    frac, _, _, _, enough = hazard_fraction(h1)
    del h1
    ok = valid & enough
    cls = np.where(ok, np.where(frac >= HIGH_FRAC, 2, np.where(frac >= MED_FRAC, 1, 0)), 0).astype(np.uint8)
    safe_pass = passable & (cls != 2)
    safe_pass[by, bx] = True

    sets = {}
    for key, pas in (("plain", passable), ("nofall", safe_pass)):
        o2, t, dose, code = return_tree(h, eta, rate1, pas, base_idx)
        sets[key] = (o2, t, dose, code)
        budget = 150 - O2_RESERVE_G
        print(f"[{key}] 산소 150 g 귀환 가능 {(o2 <= budget).sum() * (CELL_M / 1000) ** 2:.2f} km2, "
              f"최대 귀환 산소 {np.nanmax(o2):.0f} g, 최대 시간 {np.nanmax(t) / 3600:.1f} h, "
              f"최대 선량(x1) {np.nanmax(dose) * 1000:.1f} uSv")

    # 통신: 거점 가시권, 보고서 15에서 고른 중계기 위치의 가시권
    with open("../outputs/comm_los/comm_stats.json") as f:
        relay = tuple(json.load(f)["coverage"]["relay_cell"])
    base_vis, _ = viewshed(h, valid, base, BASE_ANT_M, SUIT_ANT_M)
    relay_vis, _ = viewshed(h, valid, relay, RELAY_ANT_M, SUIT_ANT_M)
    flags = (valid.astype(np.uint8) | (base_vis.astype(np.uint8) << 1) | (relay_vis.astype(np.uint8) << 2)
             | (passable.astype(np.uint8) << 3))
    # bit 16: Bagnold 모래언덕 후보 (dune_mask.py, 정사영상 밝기로 만든 추정 영역)
    dune = np.load(f"{OUT_DIR}/dune_mask.npy") if os.path.exists(f"{OUT_DIR}/dune_mask.npy") else np.zeros_like(valid)
    flags |= ((dune & valid).astype(np.uint8) << 4)
    print(f"모래언덕 후보 {(dune & valid).sum() * (CELL_M / 1000) ** 2:.2f} km2")

    blobs, layout, off = [], {}, 0

    def add(name, arr):
        nonlocal off
        b = np.ascontiguousarray(arr).tobytes()
        layout[name] = [off, len(b), str(arr.dtype)]
        blobs.append(b)
        off += len(b)

    for key, (o2, t, dose, code) in sets.items():
        add(f"{key}_o2", q16(o2, O2_SCALE))
        add(f"{key}_time", q16(t, 1.0))
        add(f"{key}_dose", q16(dose, DOSE_SCALE))
        add(f"{key}_pred", code)
    add("cls", cls)
    add("flags", flags)
    h_min = float(np.nanmin(h[valid]))
    h_step = 0.01 if np.nanmax(h[valid]) - h_min < 650 else 0.02
    add("h", np.where(valid, np.clip(np.rint((np.nan_to_num(h, nan=h_min) - h_min) / h_step), 0, NONE16 - 1), 0).astype("<u2"))
    add("eta", np.clip(np.rint((eta - ETA_MIN) / (ETA_MAX - ETA_MIN) * 255), 0, 255).astype(np.uint8))
    add("shield", np.clip(np.rint(np.nan_to_num(shielding) * 255), 0, 255).astype(np.uint8))
    raw = b"".join(blobs)
    gz = gzip.compress(raw, compresslevel=9)
    with open(f"{OUT_DIR}/demo_data.bin.gz", "wb") as f:
        f.write(gz)
    print(f"격자 {rows}x{cols}, 원본 {len(raw) / 1e6:.2f} MB -> gzip {len(gz) / 1e6:.2f} MB")

    shade = np.where(valid, hillshade(h), np.nan)
    plt.imsave(f"{OUT_DIR}/hillshade.png", np.nan_to_num(shade, nan=0.0), cmap="gray", vmin=0, vmax=1)

    wps, _ = load_traverse(h.shape)
    gx, gy = (int(round(v)) for v in lonlat_to_cell(*_wp_lonlat(wps, GOAL_SOL)))
    meta = {
        "rows": rows, "cols": cols, "cell_m": CELL_M, "layout": layout,
        "h_min": h_min, "h_step": h_step, "eta_min": ETA_MIN, "eta_max": ETA_MAX,
        "o2_scale": O2_SCALE, "dose_scale": DOSE_SCALE, "none16": NONE16,
        "offsets": OFFSETS, "base": [bx, by], "relay": list(relay), "goal": [gx, gy], "goal_sol": GOAL_SOL,
        "traverse": [[[round(float(x), 1), round(float(y), 1)] for x, y in zip(xs, ys)][::3]
                     for xs, ys in traverse_xy],
        "const": {
            "o2_reserve_g": O2_RESERVE_G, "level_o2_g_h": LEVEL_O2_G_PER_H, "level_mr_w": LEVEL_MR_W,
            "o2_g_per_j": O2_G_PER_L / (O2_KJ_PER_L * 1000), "latent_j_kg": LATENT_HEAT_J_PER_KG,
            "feedwater_full_g": FEEDWATER_FULL_G, "heat_storage_water_eq_g": HEAT_STORAGE_WATER_EQ_G,
            "dose_budget_msv": DOSE_BUDGET_MSV, "spe_observed": CAL["dose"]["spe_observed"],
            "walk_speed_m_s": EVA_WALK_SPEED_M_S,
            "body_kg": BODY_MASS_KG, "suit_kg": SUIT_MASS_KG, "g_ratio": G_RATIO_MARS,
            "d_bg_msv_day": CAL["dose"]["bg_msv_day"], "shield_max": SHIELDING_MAX_REDUCTION,
            "rest_mr_w": float(metabolic_rate_w(0.0, 1.0, G_RATIO_MARS, v=0.0)),
            "base_ant_m": BASE_ANT_M, "suit_ant_m": SUIT_ANT_M, "relay_ant_m": RELAY_ANT_M,
            "mars_radius_m": MARS_RADIUS_M, "los_step": LOS_STEP,
            "cal": {k: v for k, v in CAL.items() if not k.startswith("_")}, "cal_status": CAL["_status"],
        },
    }
    with open(f"{OUT_DIR}/demo_meta.json", "w") as f:
        json.dump(meta, f, ensure_ascii=False)
    print(f"saved {OUT_DIR}/demo_data.bin.gz, demo_meta.json, hillshade.png")


if __name__ == "__main__":
    main()
