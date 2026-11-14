# Map-first integration validation — 2026-11-15

## TDD evidence

The reproducible-build test was executed before the integrated builder existed and failed on the missing implementation. RED checkpoint: `cb89413`. The same test now passes and compares two build hashes, expected UI features and absence of the removed Visor arrows. Mobile testing additionally reproduced a Visor button/planning-card overlap; the layout now tracks card height and the overlap assertion passes.

The imported preview predates this integration checkpoint. Do not interpret that checkpoint as a fresh RED/GREEN history for every imported feature. Existing focused regression tests were retained and rerun.

## Results

- Deterministic offline Python build: PASS, identical main and standalone output.
- Five Node unit/regression scripts: PASS (coordinates/inverse, minute formatting, walking/rover travel and return modes, navigation helper math, arrows absent).
- Six headless Chrome workflow scripts: PASS; no runtime exceptions recorded in tested workflows.
- Three-region switch with Korean retained: Gale 4, Jezero 5, Aram 5 markers; background IDs and marker/target counts agree.
- Actual mouse base drag and destination add/delete: PASS; markers remain visible.
- Live radius blue pixel count: outbound 67,490 → 66,980; return 66,926 → 65,996. Displayed oxygen matches the simulation frame. Both phases remain visible.
- Three stops with 90 minutes total dwell: 125-minute simulation ends at home; 581.389 g of initial 816.466 g oxygen remains. Early return ends at home in 5 simulated minutes. A 1,440-minute dwell request with 50 g oxygen is rejected and start disabled.
- Mobile touch emulation at 390×844: pan/settings checks pass. Planning top 569.94 px and Visor bottom 557.94 px do not overlap.
- Walk/rover round-trip simulation agrees with corresponding planner costs; restoring walking mode restores previous costs.
- Visor drag changes heading and pitch, preserves distance/resources and contains no drawn guidance arrows.

Machine-readable evidence and screenshots: `reports/map-app-validation/`.

## Review and limits

Self-review used the installed `agents/code-reviewer.md` checklist, focusing on build inputs, state changes, coordinate conversion, mode-dependent return costs, HTML labels and regression evidence. Fixed custom-target localization being overwritten on region revisits and refreshed open POI/catalog content when switching language. No independent reviewer agent was used.

No unresolved critical/high finding was identified in this scoped review. This does not establish complete correctness: whole-application coverage is not measured and the skill's 80% target is not claimed. Physical phones, Firefox/Safari, prolonged real-time playback and the separate scientific/SLAM suite were not validated. Coordinates derive from labels/crop metadata and are not an independent ground-control check. See PLAN.md for retained modeling limits.
