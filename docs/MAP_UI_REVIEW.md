# Map-first UI review branch

This branch preserves the user's local map-first UI implementation and subsequent H0 build improvements. It starts at `6c6ff58`, the local checkout's base. Upstream `main` has since added a separate exploration/rescue UI, CTX surroundings and estimated zones (`115ec5b` at preparation time). Integrate those changes explicitly before merging; do not resolve overlapping template changes by blindly selecting this branch.

## Run and validate

Open `reports/18-eva-walkback-demo.html#jezero-evidence-demo` in Chrome or Edge. No application server is required. Use `#mars` for the offline global overview.

With Node 22 available, from the repository root:

```sh
node code/build_ui_preview.mjs
node tests/run_validation.mjs --reproduce
node tests/run_validation.mjs --package
```

The hash-verified seed, ten native visor PNGs, MOLA overview tiles, observation catalog and local evidence outputs are included. The multi-gigabyte raw archive and local tooling are excluded. Regenerating observational products from raw data still requires that archive; it is not required for the UI build and automated validation. Packaging uses the recorded original baseline hash, without requiring an adjacent research folder. Generated `dist/` is not committed because the two existing reports HTML files already provide runnable artifacts.

`PLAN.md` and `RESEARCH.md` preserve the research/handoff context. Their absolute paths refer to the original workspace. H0 has since been implemented: use the runner above rather than the older inline recipes. `reports/build-reproducibility.json` describes that change. Browser QA was subsequently attempted; `reports/browser-qa.md` records 7 passing and 9 failing scenarios (115/130 checks) on Chrome emulation. Its artifact hash identifies the version tested; do not treat it as a fresh pass on a rebuilt artifact. Physical-device testing remains open.

## Features and limits

Fresh PR preparation validation: `node tests/run_validation.mjs --reproduce` passed 83 checks, 84 Python reference conditions / 504 comparisons, the actual packaged-grid check and three identical builds. HTML SHA256: `e207c9441d3ba4c4db98ae2c538209ed9236c8a2e76cd8a8dc28fc33d2f51c51`. Packaging also completed (17 generated files; 431 source rows). This does not supersede the outstanding browser QA failures.

- Full-screen map, recognizable current/base/site markers, rotation, zoom, scale and North up / Center on me.
- A/B itinerary selection, outbound/return/stay forecasts, dwell sharing, initial-oxygen 20% reserve, live estimates and manual return.
- Actual rover observations with source metadata, synchronized visor, offline Mars overview and local-only mesh evidence.
- Strict Jezero graph checks, shared worker/model calculations, provenance-aware build inputs and non-destructive grid tests.

This remains a draft: mobile/keyboard/visor issues from browser QA need triage, and upstream UI changes need reconciliation. The local mesh preview is not orbitally registered; Block test is synthetic. Apollo suit quantities are reference assumptions, not validated Mars life-support specifications. Source attribution is recorded, but a full redistribution audit remains outstanding.
