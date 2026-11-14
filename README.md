# Mars EVA Walkback & Survival Planner

**NASA Space Apps 2026 · Interplanetary Survival Guide: Martian Map**

> ### If something breaks right now, can the astronaut still walk back to base?

A 10 m map of Mars that shows **where an EVA crew can still get home alive** with the oxygen, coolant
and radiation margin they have left, and **the safest way back** from any point.

**▶ Demo:** [`reports/18-eva-walkback-demo.html`](reports/18-eva-walkback-demo.html) — one HTML file, open it in a desktop browser.

---

### Key features

- **Walk-back zone:** every 10 m cell is checked for O2, coolant, dose and comms on the real return route.
- **Science EVA planner:** visits real rover sampling sites and **turns back automatically** before the margin runs out.
- **Live telemetry simulation:** heart rate or tank pressure drives a minute-by-minute **turn-back alarm**.
- **Rescue planning:** shows where a rescuer can reach a stranded crew member in time, and how much O2 to carry.
- **Helmet HUD:** a popup visor view with O2 and coolant battery gauges, comm signal bars and alarms.

### Why it is credible

- **Measured suit data:** walking cost comes from NASA IST-1/2 reduced-gravity suited walking tests (444 W on level ground).
- **Independently verified:** the model was re-derived in [`walkback_verification/`](walkback_verification/), and the demo matches it (**Gale, 150 g O2 → 9.72 km²**).
- **Model choice matters:** the older Pandolf model gives **2× the area**, so the comparison switch is built into the demo.

### NASA data

HiRISE 1 m DTMs and orthoimages · Curiosity and Perseverance traverses and Navcam images ·
Mars 2020 sample list · JPL Mars Trek THEMIS · Curiosity RAD.
Sites: **Gale**, **Jezero delta**, **Aram Chaos**.

### Limitations

- The suit tests ran at 0.12–0.32 g on Earth, not at Mars gravity.
- Telemetry in the demo is synthetic or loaded from CSV.
- Terrain shielding, fall risk and comm bars are proxies, not measurements.

---

<sub>Rebuild: `cd code && python build_demo_html.py` · SLAM and terrain-AI research from earlier in the project:
[Martian_SLAM](https://github.com/jstak0804/Martian_SLAM) · Built with an AI coding assistant (Claude Code); all imagery is NASA/JPL-Caltech.</sub>
