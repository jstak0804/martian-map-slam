"""Malformed build inputs must fail before replacing a working demo."""
import gzip
import json
from pathlib import Path
import runpy
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
BUILD = runpy.run_path(str(ROOT / 'code/build_map_app.py'))['build']


class BuilderValidation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = self.root / 'code/map_app'
        (self.app / 'src').mkdir(parents=True)
        (self.app / 'assets').mkdir()
        (self.root / 'reports').mkdir()
        self.output = self.root / 'reports/Martian-Map-Final.html'
        self.output.write_text('working demo', encoding='utf-8')
        self.write('modules.json', '["main.js"]')
        self.write('src/main.js', 'const ready = true;')
        self.write('template.html', '<script>@@APP_SCRIPT@@</script>')
        previous = {key: BUILD.__globals__[key] for key in ('ROOT', 'APP')}
        BUILD.__globals__.update(ROOT=self.root, APP=self.app)
        self.addCleanup(BUILD.__globals__.update, previous)

    def write(self, name, value):
        (self.app / name).write_text(value, encoding='utf-8')

    def rejected(self):
        with self.assertRaises(ValueError):
            BUILD()
        self.assertEqual(self.output.read_text(encoding='utf-8'), 'working demo')

    def test_duplicate_modules(self):
        self.write('modules.json', '["main.js", "main.js"]')
        self.rejected()

    def test_module_path_escape(self):
        self.write('outside.js', 'const outside = true;')
        self.write('modules.json', '["../outside.js"]')
        self.rejected()

    def test_missing_script_slot(self):
        self.write('template.html', '<script></script>')
        self.rejected()

    def test_unresolved_placeholder(self):
        self.write('template.html', '@@UNKNOWN@@<script>@@APP_SCRIPT@@</script>')
        self.rejected()

    def test_json_cannot_close_script(self):
        value = {'name': '</script><script>alert(1)</script>'}
        self.write('src/main.js', 'const value = @@JSON:example@@;')
        (self.app / 'assets/example.json.gz').write_bytes(gzip.compress(json.dumps(value).encode()))
        BUILD()
        html = self.output.read_text(encoding='utf-8')
        self.assertEqual(html.count('</script>'), 1)
        encoded = html.removeprefix('<script>const value = ').removesuffix(';</script>')
        self.assertEqual(json.loads(encoded), value)


if __name__ == '__main__':
    unittest.main()
