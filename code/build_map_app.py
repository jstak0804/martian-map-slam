"""Build the offline map-first application from explicit source modules and assets.

Standard library only; independent of large raw DTM downloads and machine paths.
"""
from pathlib import Path
import gzip
import json
import re

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'code/map_app'

def build():
    modules = json.loads((APP / 'modules.json').read_text(encoding='utf-8'))
    script = ''.join((APP / 'src' / name).read_text(encoding='utf-8') for name in modules)
    def inline_json(match):
        return gzip.decompress((APP / 'assets' / (match[1]+'.json.gz')).read_bytes()).decode('utf-8')
    script = re.sub(r'@@JSON:([a-z_]+)@@', inline_json, script)
    template = (APP / 'template.html').read_text(encoding='utf-8')
    def inline_asset(match):
        return gzip.decompress((APP / 'assets' / (match[1]+'.txt.gz')).read_bytes()).decode('utf-8')
    html = re.sub(r'@@ASSET:([a-z0-9_-]+)@@', inline_asset, template)
    html = html.replace('@@APP_SCRIPT@@', script)
    output = ROOT / 'reports/18-eva-walkback-demo.html'
    output.write_text(html, encoding='utf-8', newline='\n')
    standalone = ROOT / 'reports/18-eva-walkback-demo.standalone.html'
    standalone.write_text(html, encoding='utf-8', newline='\n')
    print(output)

if __name__ == '__main__':
    build()
