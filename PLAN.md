# Map-first demo: implementation handoff

Updated 2026-11-15. This plan describes the integrated map-first application. Earlier SLAM experiments and the legacy wide UI are separate; do not treat this UI work as independent validation of rover-to-orbit alignment.

## Completed scope (steps 1–4)

1. **Localization:** English/Korean interface, dynamic destination/site labels, route comparison, radius actions, popup summaries and Visor captions. Duration formatters use `min`. Scientific product names and source citations retain their original names.
2. **Geographic coordinates:** map clicks show planetocentric latitude, east longitude and offsets from base. HiRISE label projection parameters and crop offsets are embedded; source labels are preserved in `docs/map-app/georeference/`. These are map-cell coordinates, not independent validation of the rover camera position.
3. **Regression checks:** three-region switching; custom destination add/delete; continuous base markers during drag; outbound/return radius shrink; walk/rover costs and simulation consistency; Visor drag and heading; 390×844 touch layout; three-stop 125-minute mission; early return; insufficient-resource rejection. Fixed mobile Visor/planning overlap during testing.
4. **Integration:** editable modules and compressed assets, deterministic offline build, generated main/standalone demos, preserved legacy wide UI, tests and handoff documentation. GitHub delivery is through the feature branch/PR; merging is separate from local verification.

## Where to edit

- `code/map_app/template.html`: HTML shell and shared styles.
- `code/map_app/modules.json`: concatenation order. Modules share a closure; preserve the order and boundary fragments.
- `code/map_app/src/planner-core.js`: core routing, simulation, terrain and resource model.
- `code/map_app/src/bridge-00.js`: map UI controller and integration with the planner.
- Named modules: `language_switch.js`, `map_coordinates.js`, `planning_targets.js`, `target_access.js`, `radius_overlay.js`, `travel_mode.js`, `visor_navigation.js`, `compact_navigation.js`, `base_drag.js`, `base_icon.js`, `mars_globe.js`, `settings_sections.js`, `separate_site_pins.js`.
- `bridge-01.js` through `bridge-12.js`: integration statements and embedded JSON references. They are source fragments, not independently executable modules.
- `code/map_app/assets/`: gzip-compressed JSON/data/image payloads, expanded during build. Changing `docs/map-app/georeference/georeference.json` alone does not update the embedded `assets/georeference.json.gz`.
- `startup.js`: startup and QA debug interface. Tests use the same application state through `EVA_DEBUG`.

Do not edit generated HTML as the source of truth. Run `python code/build_demo_html.py` from the repository root; it delegates to `build_map_app.py` and writes both main and standalone HTML. No raw DTM downloads or npm install are needed. The legacy generator is `code/build_legacy_demo_html.py`; it targets `.wide-ui.html` and still has its original data dependencies.

## Acceptance rules to preserve

- Start with a local map. Open the optional globe to choose Gale, Jezero or Aram.
- Sites stay at their true supplied grid coordinates even when icons overlap.
- Click a traversable map location to add a destination, up to A/B/C; small marker `×` deletes user-created points. Impassable/disconnected/unknown terrain is rejected with feedback. Insufficient oxygen alone must still allow planning and show the deficit.
- Drag the home icon to move base without disappearing markers. N aligns the active target direction upward. Middle-button drag rotates the map.
- All blank dwell fields use automatic allocation; fill all selected fields for fixed dwell. Partial input currently falls back to automatic allocation; the UI states this rule.
- Before departure, radius evaluates round trips. During playback, each candidate cell is assessed for return to base using the current remaining oxygen (not a new trip from the explorer to that candidate). Blue >20%, yellow >10% through 20%, red ≤10%; unknown surroundings use a hatched level-ground estimate. Coolant deficits have a separate overlay.
- Rover uses the existing walking-accessible geometry, 2.2 m/s and 147 W riding assumptions. Emergency return remains on foot. Do not silently replace emergency walking costs with rover costs.
- Visor is a synthetic DTM rendering, not real body-camera video. Preserve 360° drag, heading, attitude grid, resource percentages/minutes and route distance. **Do not restore navigation arrows or curved guidance lines:** the user explicitly removed them.

## Verification

Python 3 and Node 22; browser checks require installed Chrome/Edge on Windows. Run from repository root:

```text
python tests/map_app/test_build.py
node tests/map_app/test_coordinates.cjs
node tests/map_app/test_time_units.cjs
node tests/map_app/test_travel_core.cjs
node tests/map_app/test_visor_navigation.cjs
node tests/map_app/test_visor_no_arrows.cjs
node tests/map_app/check_integration.mjs
node tests/map_app/check_map_interactions.mjs
node tests/map_app/check_radius_live.mjs
node tests/map_app/check_travel_mode.mjs
node tests/map_app/check_visor.mjs
node tests/map_app/check_missions_mobile.mjs
```

Run browser checks sequentially. Evidence outputs go to `reports/map-app-validation/`. See `docs/map-app/VALIDATION.md` for measured results and coverage limits. Add a failing behavioral test before subsequent fixes, then rerun relevant checks and apply the code-reviewer checklist. Do not claim 80% coverage without measuring it.

## Remaining experiments and implementation

1. **Physical-device validation:** Android Chrome and iOS Safari, touch pinch/rotate, narrow-screen keyboard with dwell inputs, popup permissions and 30+ minutes continuous playback. Current mobile checks use desktop Chrome touch emulation, not physical hardware.
2. **DTM coverage (deferred by user):** inventory adjacent HiRISE/HRSC elevation products and their projection, vertical datum, resolution and nodata mask. Register/validate seams against known control points before extending routing. Keep CTX image coverage distinct from elevation coverage; never turn flat extrapolation into measured-terrain claims.
3. **Georeference validation:** compare independent landmark/control points in all three regions, quantify error and record projection conventions. Five displayed decimals are formatting, not accuracy. Current tests verify math and inverse consistency, not independent absolute accuracy.
4. **Model validation:** rover speed/consumption and vehicle traversability need separate evidence; Apollo pressure alone is not oxygen mass without volume/temperature/calibration. Maintain current assumptions explicitly. External radius, comms, fall risk, radiation shielding and synthetic telemetry are demonstrations, not operational safety guarantees.
5. **Maintainability/coverage:** progressively replace closure bridge fragments with explicit interfaces; preserve deterministic build and behavior tests. Add instrumentation and measured branch coverage, especially async region/base changes and resource-boundary cases. Full repository scientific/SLAM tests were not rerun for this UI integration.
6. **H4/H5 research:** prior matching failures are not resolved by coordinates in the UI. Keep observation-derived map corrections disabled until new independent correspondence evidence meets the recorded experiment acceptance criteria.
