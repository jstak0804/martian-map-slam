"""
대사량 관련 보정: 표 데이터(CSV)에서 데모의 모델 파라미터를 다시 맞춘다.

    python -m hackathon.calibrate_metabolic --files ../data/hackathon_2026/eva.csv --name hackathon_2026 \
        [--g 1.0 --body-kg 75 --load-kg 0 --window-s 60]

하는 일 (필요한 열이 있을 때만):
  1. 심박 -> 대사량 회귀식  MR[BTU/h] = a + b·HR          (hr + mr 또는 vo2)
     - 기존 Hoffmann 2021 식과 같은 형태라 데모에 그대로 넣을 수 있다.
     - 기존 식의 Bland-Altman(평균 차이·95% 한계)과 새 식의 5겹 교차검증 RMSE를 함께 낸다.
  2. 지면별 지형계수 η                                   (mr/vo2 + speed, grade 있으면 사용)
     - 행마다 η = (측정 대사량 − Pandolf 정지 항) ÷ (η=1일 때 Pandolf 이동 항)  (Richmond 2015 식 11과 같은 방법)
     - 내리막(경사 < −1%)은 Pandolf가 맞지 않아 뺀다.
     - surface 열에 sand/dune/모래가 있으면 η = a + b/V² 를 최소제곱으로 맞춘다(속도가 다양할 때만).
     - 나머지 지면의 중앙값 − 1.0 을 "표토 지형계수 가산값" 제안으로 낸다.
  3. 경사별 자율 보행 속도  V = v0 − c·경사(%)           (speed + grade, 오르막 행)
     - 속도를 정해 놓고 걷게 한 실험이면 의미가 없다: --forced-speed 로 건너뛴다.

주의:
  - 지구에서 잰 자료면 --g 1.0 (기본), 화성 모사 하중 자료면 그 조건에 맞는 g·질량을 넣는다.
    η와 회귀식은 비율·관계식이라 중력에 덜 민감하지만, 정지 항은 질량·중력에 따라 달라진다.
  - 결과는 제안(params_proposed.json)일 뿐이다. 검토 후 python -m hackathon.params --activate 로 반영.
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from hackathon.loaders import read_table, detect_roles, to_si
from hackathon.params import DEFAULTS, write_proposal

BTU_W = 0.29307107
OUT_ROOT = "../outputs/hackathon"
SAND_WORDS = ("sand", "dune", "모래", "사구")


def pandolf_parts(g, body_kg, load_kg, v, grade):
    """정지 항 PA(W), η=1일 때 이동 항(W). 데모 mrOf와 같은 식(질량 항에 중력비)."""
    W, L = body_kg * g, load_kg * g
    pa = 1.5 * W + 2.0 * (W + L) * (L / W) ** 2
    dyn1 = (W + L) * (1.5 * v ** 2 + 0.35 * v * np.maximum(grade, 0))
    return pa, dyn1


def ols(x, y):
    A = np.vstack([np.ones_like(x), x]).T
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    pred = A @ coef
    ss = ((y - y.mean()) ** 2).sum()
    return coef, (1 - ((y - pred) ** 2).sum() / ss) if ss > 0 else np.nan, pred


def kfold_rmse(x, y, k=5, seed=0):
    idx = np.random.default_rng(seed).permutation(len(x))
    errs = []
    for f in range(k):
        te = idx[f::k]
        tr = np.setdiff1d(idx, te)
        if len(tr) < 3 or len(te) == 0:
            continue
        coef, _, _ = ols(x[tr], y[tr])
        errs.append(y[te] - (coef[0] + coef[1] * x[te]))
    e = np.concatenate(errs) if errs else np.array([np.nan])
    return float(np.sqrt(np.nanmean(e ** 2)))


def bland_altman(meas, est):
    d = meas - est
    return {"bias": float(np.mean(d)), "loa_low": float(np.mean(d) - 1.96 * np.std(d)),
            "loa_high": float(np.mean(d) + 1.96 * np.std(d)), "n": int(len(d))}


def load_rows(path, args):
    cols, kinds = read_table(path)
    roles = detect_roles(list(cols), kinds)
    get = lambda r: to_si(cols[roles[r]["column"]], r, roles[r]["unit"], args.body_kg) if r in roles else None
    mr = get("mr") if "mr" in roles else (get("vo2") if "vo2" in roles else None)
    d = {"hr": get("hr"), "mr": mr, "speed": get("speed"), "grade": get("grade"), "t": get("time")}
    d["surface"] = np.array([str(s).strip().lower() for s in cols[roles["surface"]["column"]]]) if "surface" in roles else None
    n = len(next(iter(cols.values())))
    raw = dict(d)
    if args.window_s and d["t"] is not None:     # 시간 창 평균: 잡음과 대사 반응 지연을 줄인다
        b = np.floor((d["t"] - np.nanmin(d["t"])) / args.window_s).astype(int)
        keys = np.unique(b)
        out = {}
        for k_, v in d.items():
            if v is None:
                out[k_] = None
            elif k_ == "surface":
                out[k_] = np.array([max(set(v[b == u]), key=list(v[b == u]).count) for u in keys])
            else:
                out[k_] = np.array([np.nanmean(v[b == u]) for u in keys])
        d, n = out, len(keys)
    return d, roles, n, raw


def main(files, name, args):
    out_dir = os.path.join(OUT_ROOT, name, "metabolic")
    os.makedirs(out_dir, exist_ok=True)
    rows = {"hr": [], "mr": [], "speed": [], "grade": [], "surface": []}
    raw_rows = {"speed": [], "grade": [], "surface": []}
    used = []
    for p in files:
        d, roles, n, raw = load_rows(p, args)
        nr = len(raw["speed"]) if raw["speed"] is not None else 0
        for k_ in raw_rows:                       # 속도식은 시간 평균 전 원자료로 (경사에 바로 반응하므로)
            v = raw.get(k_)
            raw_rows[k_].append(v if v is not None else (np.array(["all"] * nr) if k_ == "surface" else np.full(nr, np.nan)))
        used.append({"file": p, "rows_after_window": n, "roles": {r: v["column"] for r, v in roles.items()}})
        for k_ in rows:
            v = d.get(k_)
            if v is None:
                v = np.full(n, np.nan) if k_ != "surface" else np.array(["all"] * n)
            rows[k_].append(v)
    R = {k_: np.concatenate(v) for k_, v in rows.items()}
    RW = {k_: np.concatenate(v) for k_, v in raw_rows.items()}
    params, ev = {}, {"files": used, "assumptions": {"g": args.g, "body_kg": args.body_kg, "load_kg": args.load_kg,
                                                     "window_s": args.window_s}}
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.4))

    # 1. 심박 -> 대사량
    m = np.isfinite(R["hr"]) & np.isfinite(R["mr"])
    if m.sum() >= 10:
        x, y = R["hr"][m], R["mr"][m] / BTU_W
        (a, b), r2, _ = ols(x, y)
        old = DEFAULTS["hr_to_mr"]
        est_old = (old["a_btu_h"] + old["b_btu_h_per_bpm"] * x) * BTU_W
        cv = kfold_rmse(x, y) * BTU_W
        ev["hr_regression"] = {"n": int(m.sum()), "a_btu_h": float(a), "b_btu_h_per_bpm": float(b), "r2": float(r2),
                               "cv_rmse_w": cv, "old_model_bland_altman_w": bland_altman(R["mr"][m], est_old),
                               "old_model_rmse_w": float(np.sqrt(np.mean((R["mr"][m] - est_old) ** 2)))}
        if np.nanmax(x) > 230 or np.nanmin(x) < 30:
            ev["hr_regression"]["warning"] = (f"심박 범위 {np.nanmin(x):.0f}~{np.nanmax(x):.0f} bpm: 사람 심박으로 보기 어려운 값이 있습니다. "
                                              "열 역할·단위를 확인하세요.")
        if r2 < 0.5:
            ev["hr_regression"]["warning"] = f"R² {r2:.2f}: 심박으로 대사량을 설명하기 어렵습니다. 개인별로 나눠 보거나 쓰지 마세요."
        params["hr_to_mr"] = {"a_btu_h": round(float(a), 2), "b_btu_h_per_bpm": round(float(b), 4),
                              "source": f"해커톤 자료 회귀 ({name}, n={int(m.sum())}, R²={r2:.2f}, CV RMSE {cv:.0f} W)"}
        ax = axes[0]
        ax.scatter(x, R["mr"][m], s=6, alpha=0.4, label="measured")
        xs = np.linspace(x.min(), x.max(), 50)
        ax.plot(xs, (a + b * xs) * BTU_W, "r", label=f"fit {a:.0f} + {b:.2f}*HR")
        ax.plot(xs, (old["a_btu_h"] + old["b_btu_h_per_bpm"] * xs) * BTU_W, "k--", label="Hoffmann 2021")
        ax.set_xlabel("heart rate (bpm)"); ax.set_ylabel("metabolic rate (W)"); ax.legend(fontsize=8); ax.set_title("HR -> metabolic rate")
    else:
        axes[0].set_title("no HR + MR data"); axes[0].axis("off")

    # 2. 지형계수 η
    m = np.isfinite(R["mr"]) & np.isfinite(R["speed"]) & (R["speed"] > 0.2)
    grade = np.where(np.isfinite(R["grade"]), R["grade"], 0.0)
    m &= grade >= -1.0
    if m.sum() >= 10:
        pa, dyn1 = pandolf_parts(args.g, args.body_kg, args.load_kg, R["speed"], grade)
        eta = (R["mr"] - pa) / dyn1
        m &= np.isfinite(eta) & (dyn1 > 5)
        per = {}
        for s in sorted(set(R["surface"][m])):
            e = eta[m & (R["surface"] == s)]
            if len(e) >= 5:
                per[s] = {"n": int(len(e)), "median": float(np.median(e)), "q25": float(np.percentile(e, 25)),
                          "q75": float(np.percentile(e, 75))}
        ev["terrain_factor"] = {"per_surface": per, "note": "η = (측정 − 정지 항) ÷ η=1 이동 항, 경사 ≥ −1% 행만"}
        sand = [s for s in per if any(w in s for w in SAND_WORDS)]
        firm = [s for s in per if s not in sand]
        if firm:
            nf = sum(per[s]["n"] for s in firm)
            med = float(np.median(np.concatenate([eta[m & (R["surface"] == s)] for s in firm])))
            params["eta_surface_add"] = {"value": round(med - 1.0, 3),
                                         "source": f"해커톤 자료 단단한 지면 η 중앙값 {med:.2f} ({', '.join(firm)}, n={nf})"}
        if sand:
            ms = m & np.isin(R["surface"], sand)
            v = R["speed"][ms]
            inv = 1 / v ** 2
            if np.std(inv) > 0.05 and ms.sum() >= 10:
                (sa, sb), sr2, _ = ols(inv, eta[ms])
                params["eta_sand"] = {"a": round(float(sa), 3), "b": round(float(sb), 3),
                                      "v_floor_m_s": round(float(np.percentile(v, 5)), 2),
                                      "source": f"해커톤 자료 모래 η = a + b/V² 회귀 (n={int(ms.sum())}, R²={sr2:.2f})"}
            else:
                a0 = float(np.median(eta[ms])) - DEFAULTS["eta_sand"]["b"] / float(np.median(v)) ** 2
                params["eta_sand"] = {"a": round(a0, 3), "b": DEFAULTS["eta_sand"]["b"],
                                      "source": f"해커톤 자료 모래 η 중앙값으로 a만 조정 (속도가 다양하지 않아 b는 문헌값, n={int(ms.sum())})"}
        ax = axes[1]
        labels = list(per)
        ax.boxplot([eta[m & (R["surface"] == s)] for s in labels], labels=labels, showfliers=False)
        ax.axhline(1.0, color="gray", ls=":"); ax.axhline(1.2, color="orange", ls="--", lw=1)
        ax.set_ylabel("eta"); ax.set_title("terrain factor by surface (orange = gravel 1.2, Richmond 2015)")
    else:
        axes[1].set_title("no MR + speed data"); axes[1].axis("off")

    # 3. 자율 보행 속도
    S = RW                                        # 원자료(시간 평균 전)
    is_sand = np.array([any(w in s for w in SAND_WORDS) for s in S["surface"]])
    m = np.isfinite(S["speed"]) & np.isfinite(S["grade"]) & (S["grade"] >= 0) & ~is_sand   # 모래는 걸음이 달라 뺀다
    if m.sum() >= 10 and not args.forced_speed and np.std(S["grade"][m]) > 1:
        (v0, slope), r2, _ = ols(S["grade"][m], S["speed"][m])
        params["speed_model"] = {"v0_m_s": round(float(v0), 3), "c_m_s_per_pct": round(float(-slope), 4),
                                 "v_min_m_s": round(float(max(0.2, np.percentile(S["speed"][m], 5))), 2),
                                 "source": f"해커톤 자료 자율 보행 속도 회귀 (n={int(m.sum())}, R²={r2:.2f})"}
        ev["speed_model"] = {"n": int(m.sum()), "v0": float(v0), "c": float(-slope), "r2": float(r2),
                             "note": "단단한 지면, 오르막(경사 ≥ 0) 행만, 시간 평균 전 원자료"}
        if v0 > 1.0:
            ev["speed_model"]["warning"] = (f"평지 속도 {v0:.2f} m/s: 지구에서 우주복 없이 걸은 자료로 보입니다. "
                                            "화성 EVA(문헌 0.75 m/s)에 그대로 쓰지 말고 감소율 c만 참고하세요.")
            params["speed_model"]["source"] += " — 주의: 지구·비가압 자료로 보임"
        ax = axes[2]
        ax.scatter(S["grade"][m], S["speed"][m], s=6, alpha=0.4)
        gs = np.linspace(0, S["grade"][m].max(), 20)
        ax.plot(gs, v0 + slope * gs, "r", label=f"fit {v0:.2f} - {-slope:.3f}*G")
        d0 = DEFAULTS["speed_model"]
        ax.plot(gs, np.maximum(d0["v_min_m_s"], d0["v0_m_s"] - d0["c_m_s_per_pct"] * gs), "k--", label="literature (lunar)")
        ax.set_xlabel("uphill grade (%)"); ax.set_ylabel("speed (m/s)"); ax.legend(fontsize=8); ax.set_title("self-paced speed vs grade")
    else:
        axes[2].set_title("no speed + grade data (or forced speed)"); axes[2].axis("off")

    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "metabolic_calibration.png"), dpi=120)
    plt.close(fig)
    with open(os.path.join(out_dir, "metabolic_evidence.json"), "w", encoding="utf-8") as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    prop = write_proposal(os.path.join(OUT_ROOT, name), params, {"metabolic": ev}, args.synthetic)
    print(f"대사량 보정: 제안 {list(params)} -> {prop}")
    return params, ev


def add_args(ap):
    ap.add_argument("--g", type=float, default=1.0, help="자료를 잰 중력비 (지구 1.0)")
    ap.add_argument("--body-kg", type=float, default=75.0)
    ap.add_argument("--load-kg", type=float, default=0.0, help="짐·우주복 질량")
    ap.add_argument("--window-s", type=float, default=60.0, help="시간 창 평균 (0이면 끔)")
    ap.add_argument("--forced-speed", action="store_true", help="속도를 정해 놓고 걸은 실험이면 속도식 건너뜀")
    ap.add_argument("--synthetic", action="store_true", help=argparse.SUPPRESS)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--files", nargs="+", required=True)
    ap.add_argument("--name", default="hackathon_2026")
    add_args(ap)
    a = ap.parse_args()
    main(a.files, a.name, a)
