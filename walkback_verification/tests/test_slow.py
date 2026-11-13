"""실제 DTM·node를 쓰는 느린 테스트: legacy 원본 재현, 현재 기본 설정 수치, Python–JS 일치, 시뮬레이션 경로 진행"""
import json
import os
import shutil
import subprocess
import sys

import pytest

from conftest import CODE, RECALC

pytestmark = pytest.mark.slow
PY = sys.executable


def _probe(env_over):
    sys.path.insert(0, RECALC)
    import plan_c_checks as pc
    return pc.run(pc.PROBE, env_over)


def test_legacy_reproduces_original():
    s = _probe({"GALE_METABOLIC_MODEL": "pandolf_legacy", "GALE_GRID_NEIGHBORS": "8", "GALE_EDGE_SLOPE_CAP": "0"})
    assert s["area_150"] == pytest.approx(18.643, abs=0.002)
    assert s["route_back"][0] == pytest.approx(7.26, abs=0.02)
    assert s["route_out"][1] == pytest.approx(196, abs=1)
    assert s["route_back"][1] == pytest.approx(184, abs=1)
    assert s["area_150_water600"] == pytest.approx(7.383, abs=0.002)


def test_current_default():
    s = _probe({"GALE_METABOLIC_MODEL": "ist_b", "GALE_GRID_NEIGHBORS": "16", "GALE_EDGE_SLOPE_CAP": "1"})
    assert s["area_150"] == pytest.approx(9.721, abs=0.01)
    assert s["n_edges_over_36_4pct"] == 0


@pytest.mark.skipif(shutil.which("node") is None, reason="node 없음")
def test_js_parity():
    if not os.path.exists(os.path.join(CODE, "..", "outputs", "demo", "demo_meta.json")):
        pytest.skip("데모 데이터 없음 (build_demo_data.py 먼저)")
    r = subprocess.run([PY, os.path.join(RECALC, "js_parity.py")], cwd=CODE, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-2000:]
    res = json.load(open(os.path.join(RECALC, "outputs_c", "js_parity.json")))
    assert res["pass"] and res["same_reachable_set"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node 없음")
def test_js_sim_track():
    """계획 H1: 데모 EVA 시뮬레이션의 경로 진행(시간 단위)이 귀환 트리와 같은 산소·시간을 주는지"""
    if not os.path.exists(os.path.join(CODE, "..", "outputs", "demo", "demo_meta.json")):
        pytest.skip("데모 데이터 없음 (build_demo_data.py 먼저)")
    r = subprocess.run([PY, os.path.join(RECALC, "h1_sim_check.py")], cwd=CODE, capture_output=True, text=True)
    assert r.returncode == 0, (r.stdout + r.stderr)[-2000:]
    res = json.load(open(os.path.join(RECALC, "outputs_h", "h1_sim_check.json")))
    assert res["pass"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node 없음")
def test_demo_examples(tmp_path):
    """계획 I2: demo/README.md 예시 수치를 고정한다. 빌드된 데모를 node 하네스로 그대로 실행한다.
    기준(모델·예시 설정)을 의도적으로 바꾸면 이 테스트가 실패한다. 그때는 demo/README.md와 이 테스트를 함께 고친다."""
    import re
    demo = os.path.join(CODE, "..", "demo", "gale-eva-walkback-demo.html")
    jobs = os.path.join(RECALC, "outputs_h", "h1_readme_jobs.json")
    out = tmp_path / "out.json"
    r = subprocess.run(["node", os.path.join(RECALC, "h1_demo_harness.mjs"), demo, jobs, str(out)],
                       capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, (r.stdout + r.stderr)[-2000:]
    res = {x["name"]: x for x in json.load(open(out))}

    def last(name):
        return res[name]["sim"]["log"][-1]["text"]

    def grams(text):
        return float(re.search(r"산소 (\d+) g", text).group(1))

    base = res["base"]["summary"]
    assert base["safe"] == pytest.approx(9.721, abs=0.002)
    assert base["dark"] / base["safe"] == pytest.approx(0.51, abs=0.01)
    # 2026-11-12 계획 K4: 경보 k × 1.2, 시뮬레이션 예시 목적지 sol 678(5.22 km)
    on = res["simhr_on"]["sim"]
    assert on["turnMin"] == 83 and res["simhr_on"]["sim"]["log"][-1]["m"] == 166
    assert grams(last("simhr_on")) == pytest.approx(86, abs=1)
    assert res["simhr_off"]["sim"]["turnMin"] == -1 and grams(last("simhr_off")) == pytest.approx(22, abs=1)
    assert res["simhr_k1"]["sim"]["turnMin"] == -1 and grams(last("simhr_k1")) == pytest.approx(85, abs=1)
    assert grams(last("simhr_leak10")) == pytest.approx(59, abs=1)
    assert res["simpress"]["sim"]["turnMin"] == 78 and grams(last("simpress")) == pytest.approx(84, abs=1)
    rs = res["rescue"]["text"]
    assert "보급하고 함께 귀환 가능" in rs["pt-verdict"]
    m = re.search(r"구조대원 출발 시 최소량 ([\d,]+) g · ([\d,]+) g", rs["supply"])
    assert float(m.group(1).replace(",", "")) == pytest.approx(633, abs=2)
    assert float(m.group(2).replace(",", "")) == pytest.approx(3446, abs=2)
