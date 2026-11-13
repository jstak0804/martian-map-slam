"""
해커톤 데이터를 받으면 이것 하나로: 접수(intake) -> 돌릴 수 있는 단계 전부 -> 보고서.

    cd code
    python -m hackathon.run_all --drop ../data/hackathon_2026 --name hackathon_2026 [--g 1.0 --body-kg 75 --load-kg 0]
    (지형 분할 학습까지 하려면 torch가 있는 가상환경으로: code/.venv/bin/python -m hackathon.run_all ...)

결과: ../outputs/hackathon/<name>/
    intake_report.md      무엇을 받았고 어떻게 읽었는지
    report.md             단계별 결과, 제안 값과 문헌 값 비교, 다음 할 일
    params_proposed.json  보정 제안 (검토 후 python -m hackathon.params --activate 로 반영)
    metabolic/ dose/ dem_walkback/ segmentation/   그림과 근거

데이터 폴더에 SYNTHETIC.txt가 있으면 가짜 데이터로 보고, 정답(truth.json)과 비교한 표를 보고서에 넣는다.
"""
from __future__ import annotations

import argparse
import json
import os
import traceback

from hackathon import intake, calibrate_metabolic, calibrate_dose, dem_walkback
from hackathon.params import DEFAULTS

OUT_ROOT = "../outputs/hackathon"


def run(args):
    synthetic = os.path.exists(os.path.join(args.drop, "SYNTHETIC.txt"))
    args.synthetic = synthetic
    out_dir = os.path.join(OUT_ROOT, args.name)
    prop_path = os.path.join(out_dir, "params_proposed.json")
    if os.path.exists(prop_path):
        os.remove(prop_path)                       # 실행마다 새로 쓴다
    man = intake.main(args.drop, args.name)
    P = man["pipelines"]
    done, errors = {}, {}

    def step(name, fn):
        try:
            done[name] = fn()
        except SystemExit as e:
            errors[name] = str(e)
        except Exception as e:
            errors[name] = f"{type(e).__name__}: {e}"
            traceback.print_exc()

    full = lambda rel: os.path.join(args.drop, rel)
    met_files = sorted({f for k in ("hr_regression", "terrain_factor", "speed_model") for f in P.get(k, [])})
    if met_files:
        step("metabolic", lambda: calibrate_metabolic.main([full(f) for f in met_files], args.name, args))
    if P.get("dose"):
        step("dose", lambda: calibrate_dose.main([full(f) for f in P["dose"]], args.name, args))
    for f in P.get("dem_walkback", []):
        step(f"dem:{f}", lambda f=f: dem_walkback.walkback(full(f), args.name))
    if P.get("segmentation") and not args.skip_seg:
        try:
            from hackathon import finetune_segmentation as fs
            step("segmentation", lambda: fs.main(argparse.Namespace(drop=args.drop, name=args.name, class_map=args.class_map,
                                                                     epochs=args.epochs, batch=8, lr=3e-4, init=fs.DEFAULT_FROM,
                                                                     synthetic=synthetic)))
        except ImportError as e:
            errors["segmentation"] = f"torch가 없는 환경입니다 ({e}). code/.venv/bin/python 으로 다시 실행하세요."
    write_report(out_dir, args, man, done, errors, synthetic)


def _fmt(v):
    return f"{v:.3g}" if isinstance(v, float) else str(v)


def write_report(out_dir, args, man, done, errors, synthetic):
    prop = {}
    pp = os.path.join(out_dir, "params_proposed.json")
    if os.path.exists(pp):
        prop = json.load(open(pp, encoding="utf-8"))
    L = [f"# 해커톤 데이터 학습·보정 보고서: {args.name}", ""]
    if synthetic:
        L += ["> **가짜(synthetic) 데이터입니다.** 파이프라인 점검용이며 보정값은 활성화할 수 없습니다.", ""]
    L += [f"- 데이터: `{args.drop}` (파일 {len(man['items'])}개, 접수 보고서: `intake_report.md`)",
          f"- 돌린 단계: {', '.join(done) or '없음'}"]
    if errors:
        L += ["- **실패한 단계:**"] + [f"  - {k}: {v}" for k, v in errors.items()]
    warns = []
    def walk(o, path=""):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "warning":
                    warns.append(f"{path}: {v}")
                else:
                    walk(v, f"{path}.{k}" if path else k)
    walk(prop.get("evidence", {}))
    if warns:
        L += ["", "## 주의", ""] + [f"- {w}" for w in warns]
    L += ["", "## 보정 제안 vs 지금 값(문헌)", "", "| 항목 | 값 | 지금(문헌) | 근거 |", "|---|---|---|---|"]
    for key, val in prop.get("params", {}).items():
        for k2, v2 in val.items():
            if k2 == "source":
                continue
            L.append(f"| {key}.{k2} | {_fmt(v2)} | {_fmt(DEFAULTS.get(key, {}).get(k2, '-'))} | {val.get('source', '')} |")
    if not prop.get("params"):
        L.append("| (제안 없음) | | | |")
    if synthetic and os.path.exists(os.path.join(args.drop, "truth.json")):
        T = json.load(open(os.path.join(args.drop, "truth.json")))
        p = prop.get("params", {})
        chk = [("HR 회귀 a (BTU/h)", T["hr_a_btu_h"], p.get("hr_to_mr", {}).get("a_btu_h")),
               ("HR 회귀 b", T["hr_b_btu_h_per_bpm"], p.get("hr_to_mr", {}).get("b_btu_h_per_bpm")),
               ("단단한 지면 η − 1 (regolith·rock 중앙값)", None, p.get("eta_surface_add", {}).get("value")),
               ("모래 a", T["sand_a"], p.get("eta_sand", {}).get("a")),
               ("모래 b", T["sand_b"], p.get("eta_sand", {}).get("b")),
               ("속도 v0", T["speed_v0"], p.get("speed_model", {}).get("v0_m_s")),
               ("속도 c", T["speed_c"], p.get("speed_model", {}).get("c_m_s_per_pct")),
               ("배경 선량 mSv/day", round(T["dose_bg_ugy_h"] * 24e-3 * 3.05, 4), p.get("dose", {}).get("bg_msv_day")),
               ("SPE 최대 배율", T["spe_peak_multiplier"], p.get("dose", {}).get("spe_observed"))]
        L += ["", "## 정답 대조 (가짜 데이터)", "", "| 항목 | 정답 | 추정 |", "|---|---|---|"]
        L += [f"| {a} | {_fmt(b) if b is not None else '(η 1.15·1.40 섞임)'} | {_fmt(c)} |" for a, b, c in chk]
    seg = done.get("segmentation")
    if seg:
        L += ["", "## 지형 분할 미세조정", "", f"- 시작 가중치: {seg['init']}, 분할 {seg['splits']}",
              f"- 시험 mIoU: 전 {_fmt(seg['test_miou_before'])} → 후 {_fmt(seg['test_miou_after'])}",
              "- 클래스별 IoU(후): " + ", ".join(f"{k} {_fmt(v)}" for k, v in seg["test_iou_after"].items())]
    dems = {k: v for k, v in done.items() if k.startswith("dem:")}
    if dems:
        L += ["", "## 새 지형 귀환 반경", ""]
        for k, s in dems.items():
            L.append(f"- `{k[4:]}`: {s['grid'][0]}x{s['grid'][1]} 칸 @ {s['cell_m']:.1f} m, 기복 {s['relief_m']:.0f} m, "
                     + ", ".join(f"산소 {o} g → {a:.2f} km²" for o, a in s["areas_km2"].items()))
    L += ["", "## 다음 할 일", "",
          "1. `intake_report.md`에서 열 역할 추정이 맞는지 확인. 틀리면 데이터 폴더에 `columns.json`을 두고 다시 실행.",
          "2. 위 표와 각 폴더의 그림(`metabolic/metabolic_calibration.png` 등)을 보고 받아들일 항목만 고르기.",
          f"3. `python -m hackathon.params --activate ../outputs/hackathon/{args.name}/params_proposed.json --only <항목>`",
          "4. `python build_demo_data.py && python build_demo_html.py` → 데모의 왼쪽 \"대사량 모델 보정\"과 심박 회귀식에 반영됨.",
          "5. 지형 분할 가중치는 `segmentation/small_unet_finetuned.pt`. 새 지형 귀환 반경은 `dem_walkback/`."]
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print(f"보고서 -> {out_dir}/report.md")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--drop", default="../data/hackathon_2026")
    ap.add_argument("--name", default="hackathon_2026")
    ap.add_argument("--class-map")
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--skip-seg", action="store_true")
    calibrate_metabolic.add_args(ap)
    ap.add_argument("--q", type=float, default=3.05)
    ap.add_argument("--min-hours", type=float, default=1.0)
    a = ap.parse_args()
    run(a)
