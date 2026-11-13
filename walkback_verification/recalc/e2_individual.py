"""계획 E 2번: IST-1 그림 22의 개별 측정점으로 우주복 보행 대사량의 개인차(추세선 대비 퍼짐) 추정

실행: recalc/.venv/bin/python recalc/e2_individual.py
- 측정점 기호는 계열별로 두 가지 채움 색(기호 내부와 테두리)의 벡터 경로로 들어 있다. 0.27 g·0.32 g는
  여러 기호가 한 경로로 합쳐져 있어, 경로를 연속성으로 하위 경로로 나눠 기호 하나씩 본다.
- 축 보정과 추세선(2차식)은 digitize_ist.py와 같은 방법을 쓴다.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pymupdf

import digitize_ist as dg

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "outputs_e")
MARKER_FILLS = {
    0.12: [(0.27, 0.45, 0.65), (0.25, 0.44, 0.65)],
    0.17: [(0.67, 0.27, 0.26), (0.66, 0.26, 0.25)],
    0.22: [(0.54, 0.65, 0.31), (0.53, 0.64, 0.29)],
    0.27: [(0.44, 0.35, 0.56), (0.43, 0.33, 0.55)],
    0.32: [(0.25, 0.60, 0.69), (0.24, 0.59, 0.68)],
}


def _subpath_boxes(items):
    """경로 항목을 연속성(앞 항목의 끝점 = 다음 항목의 시작점)으로 하위 경로로 나눠 각 경계 상자를 돌려준다."""
    boxes, cur, last = [], [], None
    for it in items:
        if it[0] == "re":
            boxes.append(it[1]); continue
        p0, p1 = it[1], it[-1]
        if last is not None and (abs(p0.x - last.x) > 0.01 or abs(p0.y - last.y) > 0.01):
            boxes.append(pymupdf.Rect(min(q.x for q in cur), min(q.y for q in cur), max(q.x for q in cur), max(q.y for q in cur)))
            cur = []
        cur += [q for q in it[1:] if isinstance(q, pymupdf.Point)]
        last = p1
    if cur:
        boxes.append(pymupdf.Rect(min(q.x for q in cur), min(q.y for q in cur), max(q.x for q in cur), max(q.y for q in cur)))
    return boxes


def marker_centers(page, fills, plot_rect):
    """기호 중심 목록. 따로 그린 기호는 그 경로의 경계 상자 중심, 합쳐진 경로는 하위 경로별 중심.
    채움과 테두리처럼 같은 자리에 겹친 것(1 pt 이내)은 하나로 합친다."""
    cents = []
    for d in page.get_drawings():
        f = d.get("fill")
        if not f or tuple(round(c, 2) for c in f) not in fills:
            continue
        r = d["rect"]
        boxes = [r] if (r.width < 9 and r.height < 9) else _subpath_boxes(d["items"])
        for bx in boxes:
            if 2.0 < max(bx.width, bx.height) < 9.0:
                c = ((bx.x0 + bx.x1) / 2, (bx.y0 + bx.y1) / 2)
                if plot_rect.contains(pymupdf.Point(*c)):
                    cents.append(c)
    cents = np.array(cents)
    keep = []
    for c in cents:
        if not any(np.hypot(*(c - k)) < 1.0 for k in keep):
            keep.append(c)
    return np.array(keep)


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    spec = dg.FIGS["ist1_fig22"]
    page = pymupdf.open(os.path.join(dg.REF, spec["pdf"]))[spec["page"]]
    res = dg.digitize("ist1_fig22", spec)
    ax, ay = res["axis_x"], res["axis_y"]
    x_lo, x_hi = (0 - ax["b"]) / ax["a"], (3.0 - ax["b"]) / ax["a"]
    y_top, y_bot = (50 - ay["b"]) / ay["a"], (0 - ay["b"]) / ay["a"]
    plot_rect = pymupdf.Rect(x_lo - 2, y_top - 2, x_hi + 2, y_bot + 2)
    out = {"by_gravity": {}, "method": __doc__.strip().splitlines()[0]}
    allrel = []
    for g, fills in MARKER_FILLS.items():
        c = marker_centers(page, fills, plot_rect)
        v = ax["a"] * c[:, 0] + ax["b"]
        vo2 = ay["a"] * c[:, 1] + ay["b"]
        trend = np.polyval(res["series"][g]["poly2"], v)
        rel = vo2 / trend - 1
        sel = (v >= 0.6) & (v <= 1.3)
        out["by_gravity"][str(g)] = {
            "n_markers": int(len(c)), "n_in_0.6_1.3": int(sel.sum()),
            "rel_sd_0.6_1.3": round(float(np.std(rel[sel], ddof=1)), 4) if sel.sum() > 2 else None,
            "rel_sd_all": round(float(np.std(rel, ddof=1)), 4),
            "rel_p10_p90_0.6_1.3": [round(float(np.percentile(rel[sel], 10)), 3), round(float(np.percentile(rel[sel], 90)), 3)] if sel.sum() > 2 else None,
            "points": [[round(float(a), 3), round(float(b), 2)] for a, b in zip(v, vo2)],
        }
        allrel.append(rel[sel])
    pooled = np.concatenate(allrel)
    out["pooled_0.6_1.3"] = {"n": int(len(pooled)), "rel_sd": round(float(np.std(pooled, ddof=1)), 4),
                             "p10_p90": [round(float(np.percentile(pooled, 10)), 3), round(float(np.percentile(pooled, 90)), 3)]}
    out["assumption_compared"] = "개인차 k ±15% (1σ) — RESULTS_B 8.3, CHANGELOG 5절"
    json.dump(out, open(os.path.join(OUT, "e2_individual.json"), "w"), ensure_ascii=False, indent=2)
    for g, r in out["by_gravity"].items():
        print(g, {k: r[k] for k in r if k != "points"})
    print("pooled", out["pooled_0.6_1.3"])


if __name__ == "__main__":
    main()
