"""
선량 보정: 시간별 선량률 자료에서 배경 선량률과 SPE(태양입자사건) 배율을 다시 잡는다.

    python -m hackathon.calibrate_dose --files ../data/hackathon_2026/rad.csv --name hackathon_2026 [--q 3.05]

- 단위는 열 이름의 괄호에서 추정한다: uGy/h, mGy/day, uSv/h, mSv/day, mGy/h, Gy/s.
- 흡수선량(Gy)이면 선량당량(Sv)으로 바꾸려고 평균 품질계수 Q를 곱한다.
  기본 Q = 3.05: Curiosity RAD 표면 평균 0.21 mGy/day ↔ 0.64 mSv/day (Hassler et al. 2014, Science 343).
  SPE 때는 양성자가 많아 Q가 더 낮다(약 1.5~2). 가정이다.
- 배경 = 선량률 중앙값. SPE 구간 = 배경의 2배를 넘는 연속 구간(최소 --min-hours).
- 제안: dose.bg_msv_day, dose.spe_observed(관측 최대 배율).
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

OUT_ROOT = "../outputs/hackathon"
TO_PER_DAY = {"ugy/h": 24e-3, "mgy/day": 1.0, "ugy/day": 1e-3, "usv/h": 24e-3, "msv/day": 1.0, "mgy/h": 24.0,
              "gy/s": 86400e3}


def main(files, name, args):
    out_dir = os.path.join(OUT_ROOT, name, "dose")
    os.makedirs(out_dir, exist_ok=True)
    series, ev = [], {"files": [], "q_factor": args.q}
    for p in files:
        cols, kinds = read_table(p)
        roles = detect_roles(list(cols), kinds)
        if "dose" not in roles:
            continue
        unit = roles["dose"]["unit"]
        rate = np.asarray(cols[roles["dose"]["column"]], float) * TO_PER_DAY.get(unit, 24e-3)
        absorbed = "gy" in unit
        msv_day = rate * (args.q if absorbed else 1.0)
        t = to_si(cols[roles["time"]["column"]], "time", roles["time"]["unit"]) if "time" in roles else np.arange(len(rate)) * 3600.0
        ok = np.isfinite(msv_day) & np.isfinite(t)
        series.append((t[ok] - t[ok].min(), msv_day[ok]))
        ev["files"].append({"file": p, "column": roles["dose"]["column"], "unit": unit, "absorbed_gy": absorbed, "n": int(ok.sum())})
    if not series:
        print("선량 열을 찾지 못했습니다."); return {}, ev
    t = np.concatenate([s[0] for s in series]); d = np.concatenate([s[1] for s in series])
    order = np.argsort(t); t, d = t[order], d[order]
    bg = float(np.median(d))
    hot = d > 2 * bg
    events, i = [], 0
    while i < len(d):
        if hot[i]:
            j = i
            while j + 1 < len(d) and hot[j + 1]:
                j += 1
            if (t[j] - t[i]) / 3600 >= args.min_hours:
                seg = d[i:j + 1]
                events.append({"start_h": float(t[i] / 3600), "hours": float((t[j] - t[i]) / 3600),
                               "peak_multiplier": float(seg.max() / bg),
                               "event_dose_msv": float(getattr(np, "trapezoid", getattr(np, "trapz", None))(seg, t[i:j + 1]) / 86400)})
            i = j + 1
        else:
            i += 1
    peak = max((e["peak_multiplier"] for e in events), default=None)
    ev.update(background_msv_day=bg, events=events, n=int(len(d)),
              literature_background_msv_day=DEFAULTS["dose"]["bg_msv_day"])
    params = {"dose": {"bg_msv_day": round(bg, 4),
                       "source": f"해커톤 선량 자료 중앙값 ({name}, n={len(d)}{', Q=' + str(args.q) if any(f['absorbed_gy'] for f in ev['files']) else ''})"}}
    if peak:
        params["dose"]["spe_observed"] = round(peak, 2)
        params["dose"]["source"] += f", SPE {len(events)}건 최대 x{peak:.1f}"
    fig, ax = plt.subplots(figsize=(10, 3.6))
    ax.plot(t / 3600, d, lw=0.8)
    ax.axhline(bg, color="k", ls="--", lw=1, label=f"background {bg:.3f} mSv/day")
    ax.axhline(DEFAULTS["dose"]["bg_msv_day"], color="gray", ls=":", lw=1, label="RAD literature 0.655")
    for e in events:
        ax.axvspan(e["start_h"], e["start_h"] + e["hours"], color="orange", alpha=0.25)
    ax.set_xlabel("hours"); ax.set_ylabel("dose-equivalent rate (mSv/day)"); ax.legend(fontsize=8)
    ax.set_title("dose rate, SPE windows (orange) = > 2x background")
    fig.tight_layout(); fig.savefig(os.path.join(out_dir, "dose_calibration.png"), dpi=120); plt.close(fig)
    with open(os.path.join(out_dir, "dose_evidence.json"), "w", encoding="utf-8") as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    prop = write_proposal(os.path.join(OUT_ROOT, name), params, {"dose": ev}, args.synthetic)
    print(f"선량 보정: 배경 {bg:.3f} mSv/day, SPE {len(events)}건 -> {prop}")
    return params, ev


def add_args(ap):
    ap.add_argument("--q", type=float, default=3.05, help="흡수선량 -> 선량당량 품질계수")
    ap.add_argument("--min-hours", type=float, default=1.0)
    ap.add_argument("--synthetic", action="store_true", help=argparse.SUPPRESS)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--files", nargs="+", required=True)
    ap.add_argument("--name", default="hackathon_2026")
    add_args(ap)
    a = ap.parse_args()
    main(a.files, a.name, a)
