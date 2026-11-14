"""Default entry point for the integrated map-first application."""
from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).with_name('build_map_app.py')), run_name='__main__')
