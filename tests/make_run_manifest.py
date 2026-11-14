"""H0-1: record SHA256 of build inputs/outputs/evidence before changing anything.

Usage: python tests/make_run_manifest.py <out.json> [label]
Read-only over the project; writes only the given output file.
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

GROUPS = {
    "html": ["reports/18-eva-walkback-demo.html", "reports/18-eva-walkback-demo.standalone.html"],
    "source": ["code/demo_template.html", "code/map_ui.js", "code/map_ui.css", "code/map_ui_policy.js",
               "code/i18n_en.js", "code/global_map.json", "code/build_ui_preview.mjs",
               "code/build_observation_evidence.mjs", "code/package_review.mjs", "code/build_demo_html.py"],
    "local_terrain": "outputs/local_terrain/jezero",
    "tests": "tests",
    "evidence": ["reports/automated-validation.json", "reports/python-js-model-validation.json",
                 "reports/packaged-grid-validation.json", "reports/jezero-validation.md",
                 "reports/jezero-sources.csv", "reports/jezero-demo-script.md"],
    "global": ["outputs/global_mars/catalog.json"],
    "dist": "dist/jezero-demo",
}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def entries(spec):
    paths = []
    if isinstance(spec, str):
        base = ROOT / spec
        paths = sorted(q for q in base.rglob("*") if q.is_file()) if base.exists() else []
        missing = [] if base.exists() else [spec]
    else:
        missing = [s for s in spec if not (ROOT / s).is_file()]
        paths = [ROOT / s for s in spec if (ROOT / s).is_file()]
    out = {q.relative_to(ROOT).as_posix(): {"bytes": q.stat().st_size, "sha256": sha256(q)} for q in paths}
    return out, missing


def main():
    out_path = Path(sys.argv[1])
    label = sys.argv[2] if len(sys.argv) > 2 else ""
    files, missing = {}, []
    for name, spec in GROUPS.items():
        got, miss = entries(spec)
        files[name] = got
        missing += miss
    report = {"schema_version": 1, "label": label,
              "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "root": ".", "files": files, "missing": missing}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"written": str(out_path), "groups": {k: len(v) for k, v in files.items()},
                      "missing": missing}, indent=2))


if __name__ == "__main__":
    main()
