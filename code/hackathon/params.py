"""
보정 가능한 모델 파라미터의 단일 출처.

- DEFAULTS: 지금 데모가 쓰는 문헌값(출처 포함).
- 보정 스크립트(calibrate_*.py)는 outputs/hackathon/<실행이름>/params_proposed.json 에 "제안"만 쓴다.
- 사람이 검토한 뒤에만 활성화한다:
      python -m hackathon.params --activate ../outputs/hackathon/<실행이름>/params_proposed.json
  -> code/hackathon/params_active.json 에 병합 저장. build_demo_data.py가 이 파일을 읽어 데모에 넣는다.
- 되돌리기: python -m hackathon.params --reset   (params_active.json 삭제 = 문헌값으로 복귀)
- 지금 값 보기: python -m hackathon.params --show

가짜(synthetic) 데이터로 만든 제안은 activate를 거부한다(제안 파일의 "synthetic": true).
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ACTIVE_PATH = os.path.join(HERE, "params_active.json")

DEFAULTS = {
    "hr_to_mr": {
        "a_btu_h": 284.55, "b_btu_h_per_bpm": 5.984,
        "source": "Hoffmann et al. 2021 (NASA, Shuttle/ISS EVA 132회) 표 5.1",
    },
    "speed_model": {
        "v0_m_s": 0.75, "c_m_s_per_pct": 0.01, "v_min_m_s": 0.3,
        "source": "Peña-Asensio et al. 2024 달 보행 속도식 (Kim et al. 2025 ICES-2025-129 인용)",
    },
    "eta_surface_add": {
        "value": 0.2,
        "source": "Richmond, Potter & Santee 2015 표 11: 자갈·비포장길 η 1.2 (트레드밀 1.0 대비 +0.2)",
    },
    "eta_sand": {
        "a": 1.5, "b": 1.3, "v_floor_m_s": 0.85,
        "source": "Richmond 2015 식 16: η = a + b/V² (자료 범위 V ≥ 0.85 m/s)",
    },
    "k_prior": {
        "value": 1.0,
        "source": "모델 그대로 (개인 보정 없음)",
    },
    "dose": {
        "bg_msv_day": 0.655, "spe_observed": 2.9,
        "source": "Curiosity RAD 평균 0.64~0.67 mSv/day, RAD sol 242 사건 배율 x2.9",
    },
}


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_active() -> dict:
    """문헌값 위에 활성화된 보정값을 덮어쓴 결과. 각 항목에 source가 남는다."""
    p = copy.deepcopy(DEFAULTS)
    p["_status"] = "문헌값"
    if os.path.exists(ACTIVE_PATH):
        with open(ACTIVE_PATH, encoding="utf-8") as f:
            act = json.load(f)
        p = _merge(p, act.get("params", {}))
        p["_status"] = f"보정값 활성화 ({act.get('activated_at', '?')}, {act.get('from', '?')})"
    return p


def write_proposal(out_dir: str, params: dict, evidence: dict, synthetic: bool):
    """보정 스크립트가 쓰는 제안 파일. 같은 실행의 다른 보정과 합쳐진다."""
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "params_proposed.json")
    cur = {"synthetic": synthetic, "params": {}, "evidence": {}}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            cur = json.load(f)
        cur["synthetic"] = cur.get("synthetic", False) or synthetic
    cur["params"] = _merge(cur["params"], params)
    cur["evidence"] = _merge(cur["evidence"], evidence)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cur, f, ensure_ascii=False, indent=1)
    return path


def activate(proposal_path: str, only: list[str] | None = None):
    with open(proposal_path, encoding="utf-8") as f:
        prop = json.load(f)
    if prop.get("synthetic"):
        raise SystemExit("가짜(synthetic) 데이터로 만든 제안이라 활성화하지 않습니다.")
    params = prop["params"]
    if only:
        params = {k: v for k, v in params.items() if k in only}
    cur = {}
    if os.path.exists(ACTIVE_PATH):
        with open(ACTIVE_PATH, encoding="utf-8") as f:
            cur = json.load(f).get("params", {})
    out = {"activated_at": dt.datetime.now().isoformat(timespec="seconds"),
           "from": "/".join(os.path.abspath(proposal_path).replace("\\", "/").split("/")[-2:]), "params": _merge(cur, params)}
    with open(ACTIVE_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"활성화: {', '.join(params)} -> {ACTIVE_PATH}")
    print("데모에 반영하려면: python build_demo_data.py && python build_demo_html.py")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--activate", metavar="PROPOSAL_JSON")
    ap.add_argument("--only", nargs="*", help="일부 항목만 활성화 (예: hr_to_mr dose)")
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()
    if a.activate:
        activate(a.activate, a.only)
    elif a.reset:
        if os.path.exists(ACTIVE_PATH):
            os.remove(ACTIVE_PATH)
        print("문헌값으로 되돌렸습니다.")
    else:
        print(json.dumps(load_active(), ensure_ascii=False, indent=1))
