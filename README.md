# Mars EVA Walkback & Survival Planner

**NASA Space Apps Challenge 2026 · Interplanetary Survival Guide: Martian Map**

> *If something breaks right now, how far can the astronaut still walk back to base?*
> A hyper-local (10 m) map of where a Mars EVA crew can still get home alive with the oxygen,
> coolant and radiation margin they have left, and the safest way back from any point.

- **Demo:** [`reports/18-eva-walkback-demo.html`](reports/18-eva-walkback-demo.html) is one self-contained HTML file
  (≈14 MB: terrain grids, satellite images, rover photos and all code inside). Download it and open it in a
  desktop browser; no install or server is needed. It starts in English unless the browser language is Korean.
- **Sites:** Gale crater (Curiosity), Jezero crater delta (Perseverance), Aram Chaos (virtual base, obstacle-rich).

<!-- 한국어 요약: 화성 선외활동(EVA) 중 문제가 생겼을 때, 남은 산소·냉각수·선량으로 거점까지 걸어서 돌아올 수 있는
곳과 가장 안전한 귀환 경로를 HiRISE 1 m 지형 위 10 m 격자로 계산하는 지도입니다. 데모는 HTML 파일 하나입니다. -->

---

## 1. The problem (Impact)

On the Moon, Apollo crews stayed within a "walk-back limit": the distance from which they could always
walk home if the rover failed. On Mars that limit is not a circle. It depends on:

- **terrain**: slopes, scarps and boulder fields force long detours, and uphill walking costs much more O2;
- **consumables**: O2, and the water the suit evaporates for cooling, run out at rates that change with effort;
- **radiation**: a solar particle event (SPE) can make the shortest way home the most dangerous one;
- **communications**: valleys and craters cut the line of sight to base.

Mission planners and the crew need to see this limit on the map, minute by minute, not as a fixed radius.

## 2. What we built (Relevance)

A browser map console that answers four questions on real Mars terrain:

| Mode | Question it answers |
|---|---|
| ① Route check | From this point, can the crew get back? By which route, with how much O2/coolant/dose left? |
| ② Science EVA plan | Which rover science targets can we visit and still always be able to turn back? Plays back minute by minute. |
| ③ Live simulation | As heart-rate (or tank-pressure) telemetry comes in, when must the crew turn around? |
| ④ Rescue | Where can a rescuer start from, reach an immobilised crew member in time, and bring them home? How much O2/water must they carry? |
| Current position / Move base | How much further can a crew already outside go? How does a different base site change the map? |

Also: a **helmet visor HUD** in a live-synced popup window (battery-style O2/coolant %, time left,
return margin, 0–4 comm signal bars, dose rate, slope, compass to base and target, turn-back alarm);
**rover POV road view** from real Navcam images; zoom/pan; English/Korean.

## 3. How it works (Validity)

**Walking metabolism.** Regression on NASA IST-1/IST-2 reduced-gravity suited walking tests
(NASA/TP-2010-216115, NASA/TP-2010-216125): 444 W on level ground at 0.92 m/s (the Apollo 15 emergency
walk-back pace); uphill speed keeps the level-walking effort (Waligora & Horrigan 1975); downhill cost uses
Looney et al. 2019 scaled to suit grade sensitivity, with Tobler's hiking-function slow-down; floor 222 W
standing with load. O2 via 20.1 kJ/L. The older approach (whole Pandolf equation × Mars gravity, 301 W) is
kept as a **comparison switch**: it doubles the walk-back area, which shows how much the model matters.

**Reserve.** 30 min at the NASA PLSS design average of 1200 BTU/h (352 W) = 45 g O2.

**Routes.** Reverse Dijkstra on a 16-direction grid (knight moves need both crossed cells passable,
20° slope cap per edge) gives the lowest-O2 way home from every cell. Coolant and dose are evaluated along
that route. When an SPE is on, a second **multi-objective** tree minimises
`k·ΔO2/B_O2 + ΔH2O/B_H2O + SPE·ΔDose/B_Dose` (each resource divided by the budget left), so routes bend
into terrain shielding when dose becomes the binding constraint. A cell is safe if either route fits every
budget. Hilltops ringed by steep slopes are reached via the gentlest-descent corridor.

**Turn-back rule.** Every simulated minute: "if I walk one more minute, can I still get home keeping a +20 %
round-trip margin?" If not, turn around (science EVAs skip the remaining targets).

**Coolant, dose, comms.** Evaporative cooling (2.477 MJ/kg, 3.6 kg full, then a 2.0 BTU/lb body-heat
emergency limit). Curiosity RAD background 0.655 mSv/day, observed SPE ×2.9, 1 mSv per return (scenario
budget). Line of sight over terrain and Mars curvature with 3 m base / 2 m suit / 3 m relay antennas.

**Independent verification.** [`walkback_verification/`](walkback_verification/) re-derived the model from
the primary sources with its own Python implementation and 23 tests (see its `CHANGELOG.md`). The demo
reproduces its Gale result exactly: **9.72 km² walk-back area at 150 g O2**.

## 4. NASA data used

| Data | Source | Used for |
|---|---|---|
| HiRISE 1 m DTMs and orthoimages (Gale DTEEC_018854_1755_018920_1755_U01, Jezero DTEEC_045994_1985_046060_1985_U01, Aram DTEEC_054753_1825_055452_1825_A01) | NASA PDS / HiRISE (U. Arizona) | slopes, routes, line of sight, micro-relief, base map |
| MSL and Mars 2020 traverses and waypoints | NASA PDS, JPL MMGIS | base sites, science targets, road-view stops |
| Curiosity and Perseverance Navcam raw images | NASA/JPL-Caltech raw image archives | rover POV photos, visor background |
| Mars 2020 sample list | NASA Mars 2020 | Jezero target names (Skinner Ridge · Wildcat Ridge, Brac, Amalik) |
| THEMIS night IR mosaic | JPL Mars Trek | reference layer |
| Curiosity RAD dose rates | Hassler et al. 2014 | radiation budget |

## 5. Results (Gale unless noted)

| Situation | Result |
|---|---|
| O2 150 g, IST model | 9.72 km² walk-back area (previous Pandolf model: 19.95 km²) |
| Default view, O2 250 g | 32.15 km² (75 % of mapped terrain); Jezero 32.34 km², Aram 26.59 km² |
| Heart-rate surge +25 % from minute 60, O2 450 g, target 7.1 km | alarm at minute 83, home at 166 min with 86 g O2 |
| Science EVA, full 540 g tank | Jezero: 3 of 3 sampling sites, 6.65 km, 4 h 19 min · Gale: 1 of 4 · Aram: 2 of 5 |

Performance: all routing runs in an inline Web Worker; first map in ~1 s, a full science-EVA plan in ~4 s.

## 6. Limitations

- IST data come from 0.12–0.32 g tests on Earth, not Mars 0.378 g with a 90 kg suit; downhill costs are scaled
  extrapolations.
- Heart rate and tank pressure are synthetic scenarios or CSV input in this demo; the heart-rate regression
  (Hoffmann 2021) comes from Shuttle/ISS EVAs.
- Terrain shielding and the micro-relief "fall risk" are proxies, not measured values; comm bars are geometric
  steps, not a link budget.
- 540 g O2 capacity is an EMU primary-tank-level design parameter; no Mars suit capacity is public.

## 7. Run and rebuild

```bash
# view: just open reports/18-eva-walkback-demo.html
# rebuild the HTML from the data in outputs/demo:
cd code && python build_demo_html.py
# rebuild terrain data (needs HiRISE DTMs in data/hirise_dtm/, ~460 MB):
python dune_mask.py && python build_demo_data.py && python build_demo_basemap.py
python build_site_data.py jezero && python build_site_data.py aram
python build_rover_photos.py && python build_roadview.py && python build_science_targets.py && python build_trek_layers.py
```

When new challenge data arrive, `code/hackathon/run_all.py` re-fits the heart-rate, terrain-factor, speed and
dose parameters and rebuilds the demo (see `code/hackathon/REMOTE.md`).

## 8. Repository layout

| Path | Contents |
|---|---|
| `code/demo_template.html`, `code/i18n_en.js` | the planner (UI, routing worker, simulation, HUD) |
| `code/build_*.py`, `code/sites.py` | data pipeline: terrain grids, rover photos, road view, targets, Mars Trek layers |
| `code/mars_walkback.py`, `spe_walkback.py`, `coolant_walkback.py`, `comm_los.py`, `fall_risk_map.py`, `heart_rate_o2.py` | Python reference analyses |
| `code/hackathon/` | calibration pipeline for challenge data |
| `walkback_verification/` | independent re-verification of the model (IST, tests, sensitivity, Monte Carlo) |
| `reports/13–18` | write-ups; 15–17 predate the IST model and keep the earlier Pandolf numbers |
| `outputs/`, `data/` | generated grids and small source data |

## 9. Related work

The SLAM and terrain-AI research that started this project (rover map building, AI4Mars segmentation,
ConeQuest, lunar risk maps) has moved to a separate repository:
**[jstak0804/martian-map-slam-research](https://github.com/jstak0804/martian-map-slam-research)**.

## 10. Use of AI tools

Code, data processing and documentation were developed with an AI coding assistant (Claude Code). Model
choices, sources and numbers were checked against the primary literature in `walkback_verification/`.
No AI-generated imagery or NASA branding is used; all images are original NASA/JPL-Caltech data.
