import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_build():
    builder = ROOT / 'code' / 'build_map_app.py'
    assert builder.exists(), 'Integrated reproducible builder is missing'
    subprocess.run([sys.executable, str(builder)], check=True)
    output = ROOT / 'reports/Martian-Map-Final.html'
    first = hashlib.sha256(output.read_bytes()).hexdigest()
    subprocess.run([sys.executable, str(builder)], check=True)
    assert hashlib.sha256(output.read_bytes()).hexdigest() == first
    html = output.read_text(encoding='utf-8')
    assert '@@APP_SCRIPT@@' not in html and '@@ASSET:' not in html and '@@JSON:' not in html
    assert 'uiGridToLonLat' in html and 'travel-mode' in html
    assert 'TURN RIGHT' not in html
    print('PASS: reproducible offline build, coordinates, travel modes, no visor arrows')

if __name__ == '__main__':
    test_build()
