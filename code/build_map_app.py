"""Build the offline map-first application from explicit source modules and assets.

Standard library only; independent of large raw DTM downloads and machine paths.
"""
from pathlib import Path
import gzip
import json
import re

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'code/map_app'


def read_modules(app):
    modules = json.loads((app / 'modules.json').read_text(encoding='utf-8'))
    if not isinstance(modules, list) or not modules:
        raise ValueError('Module manifest must be a nonempty list')
    if any(not isinstance(name, str) or not re.fullmatch(r'[a-z0-9_-]+\.js', name) for name in modules):
        raise ValueError('Modules must be JavaScript filenames inside src')
    if len(set(modules)) != len(modules):
        raise ValueError('Duplicate module in manifest')
    source = (app / 'src').resolve()
    paths = [(source / name).resolve() for name in modules]
    if any(path.parent != source for path in paths):
        raise ValueError('Module resolves outside src')
    return ''.join(path.read_text(encoding='utf-8') for path in paths)


def read_asset(app, name, suffix):
    return gzip.decompress((app / 'assets' / (name + suffix)).read_bytes()).decode('utf-8')


def render(app):
    script = read_modules(app)

    def inline_json(match):
        raw = read_asset(app, match[1], '.json.gz')
        json.loads(raw)  # Validate while preserving formatting of valid assets.
        # JSON is embedded in an HTML script, where a closing tag ends JS parsing.
        return raw.replace('<', r'\u003c')

    script = re.sub(r'@@JSON:([a-z_]+)@@', inline_json, script)
    template = (app / 'template.html').read_text(encoding='utf-8')
    if template.count('@@APP_SCRIPT@@') != 1:
        raise ValueError('Template must contain exactly one application script slot')
    html = re.sub(r'@@ASSET:([a-z0-9_-]+)@@',
                  lambda match: read_asset(app, match[1], '.txt.gz'), template)
    html = html.replace('@@APP_SCRIPT@@', script)
    if re.search(r'@@[A-Z_]+(?::[^@]+)?@@', html):
        raise ValueError('Unresolved build placeholder')
    return html


def build():
    html = render(APP)  # Validate every input before replacing either output.
    for name in ('Martian-Map-Final.html', '18-eva-walkback-demo.standalone.html'):
        (ROOT / 'reports' / name).write_text(html, encoding='utf-8', newline='\n')
    print(ROOT / 'reports/Martian-Map-Final.html')

if __name__ == '__main__':
    build()
