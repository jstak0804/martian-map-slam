"""원본 code/ 모듈은 상대 경로(../data, ../outputs)를 쓰므로 code/에서 실행한 것처럼 맞춘다.
환경 변수는 모듈 import 시점에 읽히므로, 기본 설정(현재 모델) 테스트는 여기서 기본값을 고정한다.
이전 설정(legacy) 재현은 하위 프로세스로 따로 돌린다(test_slow.py)."""
import os
import sys

CODE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "code"))
RECALC = os.path.abspath(os.path.join(CODE, "..", "recalc"))
for k in ("GALE_METABOLIC_MODEL", "GALE_GRID_NEIGHBORS", "GALE_EDGE_SLOPE_CAP", "GALE_FLAT_SPEED"):
    os.environ.pop(k, None)
os.chdir(CODE)
sys.path.insert(0, CODE)


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: 실제 DTM·node를 쓰는 느린 테스트 (-m 'not slow'로 제외)")
