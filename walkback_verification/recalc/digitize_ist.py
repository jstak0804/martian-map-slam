"""IST-1 그림 22(평지, 속도별)와 IST-2 그림 36(경사별)의 중력별 추세선을 PDF 벡터 좌표에서 읽는다.

두 그림 모두 Excel 차트가 벡터로 들어 있다. 추세선은 계열 색으로 채운 얇은 띠(선 외곽) 조각들이다.
  1. 눈금 숫자(텍스트)의 위치로 축을 보정한다(최소제곱 직선, 잔차를 기록).
  2. 계열 색과 정확히 같은 채움 색이면서 폭이 넓고 높이가 얇은 조각만 추세선으로 본다(기호는 폭이 작다).
  3. 조각 외곽 점을 x 구간별로 모아 위·아래 경계의 가운데를 선의 중심으로 삼는다.
  4. 보고서가 쓴 2차 다항 추세선이므로 중심점에 2차식을 맞추고 잔차를 기록한다.

실행: recalc/.venv/bin/python recalc/digitize_ist.py   (출력: recalc/outputs_b/)
"""
from __future__ import annotations

import csv
import json
import os

import numpy as np
import pymupdf

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, "references")
OUT = os.path.join(HERE, "outputs_b")

# Excel 기본 계열 색(채움 RGB) -> 모사 중력 수준. 그림 범례 순서와 같다.
SERIES = {
    (0.31, 0.51, 0.74): 0.12,
    (0.75, 0.31, 0.30): 0.17,
    (0.61, 0.73, 0.35): 0.22,
    (0.50, 0.39, 0.64): 0.27,
    (0.29, 0.67, 0.78): 0.32,
}
# IST-1 보고서 2.3.6절: 평균 TGAW(80 kg 피험자 가정) 236, 334, 431, 529, 627 N
TGAW_N = {0.12: 236.0, 0.17: 334.0, 0.22: 431.0, 0.27: 529.0, 0.32: 627.0}

FIGS = {
    "ist1_fig22": {
        "pdf": "Norcross_TP-2010-216115.pdf", "page": 38,  # 0부터 셈, 인쇄 27쪽
        "x_labels": ["0.0", "0.5", "1.0", "1.5", "2.0", "2.5", "3.0"], "x_label_y": (545, 565),
        "y_labels": [str(v) for v in range(0, 55, 5)], "y_label_x": (110, 130),
        "xvar": "speed_m_s",
    },
    "ist2_fig36": {
        "pdf": "Norcross_TP-2010-216125_IST2_inclined.pdf", "page": 51,  # 인쇄 37쪽
        "x_labels": [str(v) for v in range(0, 40, 5)], "x_label_y": (385, 400),
        "y_labels": [str(v) for v in range(0, 50, 5)], "y_label_x": (130, 150),
        "xvar": "grade_pct",
    },
}


def _axis_fit(page: pymupdf.Page, labels: list[str], band: tuple[float, float], horizontal: bool) -> dict:
    """눈금 숫자의 중심 좌표로 값 = a·좌표 + b 를 맞춘다."""
    words = page.get_text("words")
    pts = []
    for lab in labels:
        cands = []
        for w in words:
            if w[4] != lab:
                continue
            cy, cx = 0.5 * (w[1] + w[3]), 0.5 * (w[0] + w[2])
            if horizontal and band[0] <= cy <= band[1]:
                cands.append(cx)
            if not horizontal and band[0] <= cx <= band[1]:
                cands.append(cy)
        if len(cands) == 1:
            pts.append((cands[0], float(lab)))
    pos, val = np.array(pts).T
    a, b = np.polyfit(pos, val, 1)
    resid = val - (a * pos + b)
    return {"a": float(a), "b": float(b), "n": len(pts), "max_resid": float(np.abs(resid).max())}


def _series_outline(page: pymupdf.Page) -> dict[float, np.ndarray]:
    out: dict[float, list] = {g: [] for g in SERIES.values()}
    for d in page.get_drawings():
        fill = d.get("fill")
        if not fill:
            continue
        key = tuple(round(c, 2) for c in fill)
        g = SERIES.get(key)
        r = d["rect"]
        if g is None or r.width < 8 or r.height > 0.6 * r.width + 6:  # 기호(작은 정사각형 등) 제외
            continue
        for it in d["items"]:
            for p in it[1:]:
                if isinstance(p, pymupdf.Point):
                    out[g].append((p.x, p.y))
    return {g: np.array(v) for g, v in out.items() if v}


def _centerline(pts: np.ndarray, bin_pt: float = 0.75) -> np.ndarray:
    xs = np.arange(pts[:, 0].min(), pts[:, 0].max() + bin_pt, bin_pt)
    cl = []
    for x0 in xs:
        sel = pts[(pts[:, 0] >= x0) & (pts[:, 0] < x0 + bin_pt)]
        if len(sel) >= 2 and np.ptp(sel[:, 1]) < 4.0:  # 띠 두께(약 2 pt) 안의 점만
            cl.append((sel[:, 0].mean(), 0.5 * (sel[:, 1].min() + sel[:, 1].max())))
    return np.array(cl)


def digitize(name: str, spec: dict) -> dict:
    page = pymupdf.open(os.path.join(REF, spec["pdf"]))[spec["page"]]
    ax = _axis_fit(page, spec["x_labels"], spec["x_label_y"], horizontal=True)
    ay = _axis_fit(page, spec["y_labels"], spec["y_label_x"], horizontal=False)
    res = {"axis_x": ax, "axis_y": ay, "series": {}}
    for g, pts in sorted(_series_outline(page).items()):
        cl = _centerline(pts)
        x = ax["a"] * cl[:, 0] + ax["b"]
        y = ay["a"] * cl[:, 1] + ay["b"]
        coef = np.polyfit(x, y, 2)
        rms = float(np.sqrt(np.mean((np.polyval(coef, x) - y) ** 2)))
        res["series"][g] = {"poly2": coef.tolist(), "x_min": float(x.min()), "x_max": float(x.max()),
                            "rms_fit": rms, "n_pts": int(len(x)), "x": x.tolist(), "y": y.tolist()}
    return res


def save_check_png(name: str, spec: dict, res: dict) -> None:
    """원본 그림 위에 맞춘 2차식을 다시 그려 겹침을 확인한다."""
    page = pymupdf.open(os.path.join(REF, spec["pdf"]))[spec["page"]]
    ax, ay = res["axis_x"], res["axis_y"]
    shape = page.new_shape()
    for g, s in res["series"].items():
        xv = np.linspace(s["x_min"], s["x_max"], 60)
        yv = np.polyval(s["poly2"], xv)
        px = (xv - ax["b"]) / ax["a"]
        py = (yv - ay["b"]) / ay["a"]
        shape.draw_polyline(list(zip(px, py)))
        shape.finish(color=(0, 0, 0), width=0.6, dashes="[2 2] 0", closePath=False)
    shape.commit()
    xs = [(0 - ax["b"]) / ax["a"], (float(spec["x_labels"][-1]) - ax["b"]) / ax["a"]]
    ys = [(float(spec["y_labels"][-1]) - ay["b"]) / ay["a"], (0 - ay["b"]) / ay["a"]]
    clip = pymupdf.Rect(xs[0] - 40, ys[0] - 15, xs[1] + 15, ys[1] + 25)
    page.get_pixmap(dpi=220, clip=clip).save(os.path.join(OUT, f"b_digitize_check_{name}.png"))


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    allres = {}
    rows = []
    for name, spec in FIGS.items():
        res = digitize(name, spec)
        save_check_png(name, spec, res)
        for g, s in res["series"].items():
            for x, y in zip(s["x"], s["y"]):
                rows.append({"figure": name, "gravity_g": g, "tgaw_n": TGAW_N[g], spec["xvar"]: "", "x": round(x, 4),
                             "vo2_ml_kg_min": round(y, 3)})
            s.pop("x"), s.pop("y")
        allres[name] = res
        print(f"{name}: x축 보정 잔차 {res['axis_x']['max_resid']:.4f}, y축 {res['axis_y']['max_resid']:.4f}")
        for g, s in res["series"].items():
            print(f"  {g:.2f} g ({TGAW_N[g]:.0f} N): x {s['x_min']:.2f}~{s['x_max']:.2f}, 점 {s['n_pts']}, "
                  f"2차식 잔차 RMS {s['rms_fit']:.3f}, 계수 {np.round(s['poly2'], 4).tolist()}")
    with open(os.path.join(OUT, "b_digitized.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["figure", "gravity_g", "tgaw_n", "x", "vo2_ml_kg_min"])
        w.writeheader()
        for r in rows:
            r.pop("speed_m_s", None), r.pop("grade_pct", None)
            w.writerow(r)
    with open(os.path.join(OUT, "b_digitized.json"), "w") as f:
        json.dump({"series_rgb_to_g": {str(k): v for k, v in SERIES.items()}, "tgaw_n": TGAW_N, **allres}, f, indent=2)


if __name__ == "__main__":
    main()
