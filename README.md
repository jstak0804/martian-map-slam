# Mars EVA Walkback & Survival Planner

NASA Space Apps 2026 ? Interplanetary Survival Guide: Martian Map

A map-first exploration planning demo for Gale, Jezero and Aram Chaos. Routes, consumables and return areas are model estimates, not an operational EVA safety system.

**Open the [integrated demo](reports/18-eva-walkback-demo.html)** after downloading the repository/file. The HTML is self-contained; double-click to open in a modern browser. GitHub's file viewer displays source rather than running the application. The [standalone copy](reports/18-eva-walkback-demo.standalone.html) has identical content. The previous [wide UI](reports/18-eva-walkback-demo.wide-ui.html) is preserved separately.

## Controls

- Start on a local map; use the globe/location menu to choose a region. Sites, Roadview and Settings use icons; language is under Settings.
- Click a traversable location or site to plan up to three destinations. Delete custom points with the small marker ?. Enter all dwell times for fixed stays, or leave them blank for automatic allocation; compare subsets in Planning.
- Drag the home marker to move base. Wheel zooms; drag pans; middle-button drag rotates. N points the active destination upward.
- Choose On foot or Rover. Play/pause the mission or use Return now. Time values use minutes; resource deficits are shown when a plan exceeds available resources.
- Radius colors show return oxygen: blue >20%, yellow 10?20%, red ?10%. Before departure it evaluates round trips; during playback it evaluates return to base from candidate cells using current oxygen. Hatched areas outside the DTM are level-ground estimates; they do not add selectable measured terrain.
- Open Visor with the goggles button. Drag to look around the synthetic DTM terrain; heading, attitude grid, distance and oxygen/coolant remain visible. Guidance arrows were intentionally removed. Roadview contains actual rover images, which are separate from this simulated view.
- Map clicks show latitude/longitude and offsets from base. These are projected map-cell positions, not independently verified rover-camera coordinates.

## Build and development

Run `python code/build_demo_html.py` from the repository root. Python's standard library expands committed assets and assembles the explicit source modules; raw DTM downloads and npm packages are not required. Edit `code/map_app/`, not generated HTML. The previous builder is retained as `code/build_legacy_demo_html.py` and still requires its original data inputs.

[Implementation plan and handoff](PLAN.md) ? [Validation results and limits](docs/map-app/VALIDATION.md)

### Why it is credible

- **Measured suit data:** walking cost comes from NASA IST-1/2 reduced-gravity suited walking tests (444 W on level ground).
- **All formulas, with worked examples:** [docs/METHODS.md](docs/METHODS.md) · [한국어](docs/METHODS.ko.md); terrain factor η: [docs/TERRAIN.md](docs/TERRAIN.md) · [한국어](docs/TERRAIN.ko.md).
- **Independently verified:** the model was re-derived in [`walkback_verification/`](walkback_verification/), and the demo matches it (**Gale, 150 g O2 → 9.72 km²**).
- **Model choice matters:** the older Pandolf model gives **2× the area**, so the comparison switch is built into the demo.

### NASA data

HiRISE 1 m DTMs and orthoimages · MRO CTX mosaics (surroundings) · Curiosity and Perseverance traverses and Navcam images ·
Mars 2020 sample list · JPL Mars Trek THEMIS · Curiosity RAD.
Sites: **Gale**, **Jezero delta**, **Aram Chaos**.

### Observed data vs. models

| Observed / published data (NASA) | Models and scenarios (computed or chosen by us) |
|---|---|
| HiRISE 1 m DTMs and orthoimages | Walking metabolism (regression on NASA IST tests, extrapolated to Mars gravity) |
| Curiosity / Perseverance traverses, stops, Navcam raw images | Return routes, walk-back areas, stay times (Dijkstra results) |
| Mars 2020 sample list | Heart-rate and tank-pressure telemetry (synthetic scenarios or CSV input) |
| Curiosity RAD background dose, observed SPE ×2.9 | 1 mSv dose budget, terrain shielding proxy, large SPE multipliers |
| Apollo 15–17 PLSS consumables (680 g O2, 5.2 kg water) | Rover speed and riding metabolism; fall-risk and comm-bar proxies |
| JPL Mars Trek THEMIS night IR | First-person visor rendered from the 10 m terrain (not a photograph) |

### Limitations

- The suit tests ran at 0.12–0.32 g on Earth, not at Mars gravity.
- Telemetry in the demo is synthetic or loaded from CSV.
- Terrain shielding, fall risk and comm bars are proxies, not measurements.

---

<sub>Rebuild: `cd code && python build_demo_html.py` · SLAM and terrain-AI research from earlier in the project:
[Martian_SLAM](https://github.com/jstak0804/Martian_SLAM) · Built with an AI coding assistant (Claude Code); all imagery is NASA/JPL-Caltech.</sub>
