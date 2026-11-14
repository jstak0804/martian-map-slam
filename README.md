# Mars EVA Walkback & Survival Planner

**NASA Space Apps Challenge 2026 · Interplanetary Survival Guide: Martian Map**

*If something breaks right now, how far can the astronaut still walk back to base?*
A 10 m map of where a Mars EVA crew can still get home with the oxygen, coolant and radiation margin left,
and the safest way back from any point.

**Demo:** [`reports/18-eva-walkback-demo.html`](reports/18-eva-walkback-demo.html): one self-contained HTML file.
Download and open it in a desktop browser.

## What it does

- **Route check:** click anywhere to see whether the crew can return, by which route, and with how much left.
- **Science EVA plan:** visit real rover science targets while always being able to turn back; play it back minute by minute.
- **Live simulation:** heart-rate or tank-pressure telemetry drives a turn-back alarm.
- **Rescue:** where a rescuer can start from, and how much O2 and water they must carry.
- **Helmet HUD:** popup visor view with O2/coolant battery gauges, comm signal bars and alarms; rover POV road view.
- Three sites: Gale (Curiosity), Jezero delta (Perseverance), Aram Chaos.

## How it works

- **Terrain:** HiRISE 1 m DTMs resampled to 10 m cells. Routes are found with reverse Dijkstra on 16 directions and a 20° slope cap.
- **Walking cost:** NASA IST-1/2 suited-walking measurements (444 W on level ground); 30-minute reserve at the NASA PLSS design average (45 g O2).
- **Radiation:** during a solar particle event, a multi-objective route weighs O2, coolant and dose against what is left.
- **Verification:** the model was re-verified independently in [`walkback_verification/`](walkback_verification/). The demo matches its Gale result: 9.72 km² at 150 g O2.

## NASA data

HiRISE DTMs and orthoimages (PDS) · MSL / Mars 2020 traverses and Navcam raw images · Mars 2020 sample list ·
JPL Mars Trek THEMIS · Curiosity RAD.

## Limitations

IST tests ran at 0.12–0.32 g on Earth, not Mars gravity. Telemetry in the demo is synthetic or CSV input.
Terrain shielding, fall risk and comm bars are proxies.

## Rebuild

```bash
cd code && python build_demo_html.py   # rebuild the HTML from outputs/demo
```

Full data pipeline and challenge-data calibration: `code/build_*.py`, `code/hackathon/`.

## Related

SLAM and terrain-AI research from earlier in the project: [jstak0804/Martian_SLAM](https://github.com/jstak0804/Martian_SLAM).
Developed with an AI coding assistant (Claude Code); all imagery is original NASA/JPL-Caltech data.
