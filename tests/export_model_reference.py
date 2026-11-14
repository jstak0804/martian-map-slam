"""Execute the original Python model; never fit replacement coefficients."""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / 'walkback_verification' / 'code'
sys.path.insert(0, str(MODEL_DIR))
os.environ['GALE_METABOLIC_MODEL'] = 'ist_b'
os.environ['GALE_FLAT_SPEED'] = '0.92'
import numpy as np
import metabolic_model as model

config = json.loads((ROOT / 'tests/fixtures/packaged_model_constants.json').read_text(encoding='utf-8'))
assert model.BODY_MASS_KG == config['body_kg'] == 75
assert model.SUIT_MASS_KG == config['suit_kg'] == 90
rows = []
for grade in [-30, -20, -10, 0, 10, 20, 30]:
    for eta in [1, 1.2, 1.5]:
        for distance in [10, 14.1421356]:
            for heat in [0, 100]:
                speed = float(model.walk_speed(grade))
                watts = float(model.metabolic_rate_w(grade, eta))
                seconds = distance / speed
                oxygen = float(model.o2_g_per_s(watts)) * seconds
                water = max(0, watts + heat) * seconds / config['latent_j_kg'] * 1000
                rows.append(dict(grade=grade, eta=eta, distance=distance, heat=heat,
                                 speed=speed, watts=watts, seconds=seconds,
                                 oxygen_g=oxygen, water_g=water,
                                 known_leak_10g_h_total_o2_g=oxygen + seconds * 10 / 3600))
result = dict(python=sys.version, numpy=np.__version__,
              source='walkback_verification/code/metabolic_model.py',
              source_sha256=hashlib.sha256((MODEL_DIR/'metabolic_model.py').read_bytes()).hexdigest(),
              parameters=dict(body_kg=75, suit_kg=90, model='ist_b', flat_speed=.92), rows=rows)
(ROOT/'tests/fixtures/jezero_model_reference.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(dict(rows=len(rows), numpy=np.__version__, source_sha256=result['source_sha256'])))
