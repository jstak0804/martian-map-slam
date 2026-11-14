# Terrain factor η — how the ground raises oxygen use

Mars EVA Walkback & Survival Planner · NASA Space Apps 2026
Korean version: [TERRAIN.ko.md](TERRAIN.ko.md) · All metabolic and O2 formulas: [METHODS.md](METHODS.md)

At the same grade and speed, walking over rocks or sand costs more than walking on firm level ground. This extra
cost is the **terrain factor η**. η = 1 is a treadmill-smooth floor, and higher values mean harder going.
All formulas below are the ones the code actually runs: `MAKE_MODEL` in `code/demo_template.html`, plus
`code/mars_walkback.py`, `code/build_site_data.py` and `code/dune_mask.py`. Numbers in *italics* are worked
examples.

---

## 1. Where η enters

### Main model (NASA IST regression)

The IST tests ran on a treadmill (η = 1), so the measurements contain no ground penalty. Only the **excess η − 1**
is added, using the form of Pandolf's terrain term:

$$M = \max\!\Big(\underbrace{\mathrm{VO_2}(v,G)\cdot 75 \cdot \tfrac{20.1}{60}}_{\text{from IST data}} \;+\; \underbrace{(\eta-1)\cdot(75+90)\cdot 0.378\cdot 1.5\,v^2}_{\text{ground penalty}},\ 222\ \mathrm W\Big)$$

- (75 + 90) kg × 0.378 is body + suit mass scaled to Mars gravity, and 1.5 v² is Pandolf's speed term.
- Constant: (75 + 90) × 0.378 × 1.5 = **93.6 W·s²/m²**.
- η **does not change walking speed.** Speed depends on grade only (METHODS §3), so η only raises the O2 used at
  that speed.

### Comparison model (Pandolf × Mars gravity)

$$M = 1.5W + 2(W+L)\left(\frac{L}{W}\right)^2 + \eta\,(W+L)\,(1.5v^2 + 0.35\,v\,G)$$

Here W and L are body and load mass × 0.378, and η multiplies both the speed term and the grade term.

### Cell to cell

$$\eta_{a\to b} = \tfrac12\,(\eta_a + \eta_b)$$

A move from 10 m cell a to cell b uses the mean η of the two cells in $\Delta O_2 = M \times 7.11\times10^{-5} \times d/v$.

---

## 2. Three sources of η

| Source | η | Basis | Demo default |
|---|---|---|---|
| ① Terrain roughness (rocks, bumps) | **1.0 – 1.5** per cell | local relief in the HiRISE 1 m DTM; design assumption | **on** (always) |
| ② Regolith surface | **+0.2** | Richmond, Potter & Santee 2015, Table 11 (gravel / dirt road 1.2) | off (switch under "Safety ops · literature-based corrections") |
| ③ Sand dunes | **1.5 + 1.3 / V²** | Richmond 2015, Eq. 16 | off (same panel) |

The η of a cell is:

$$\eta_i = \eta^{\text{rough}}_i + 0.2\,[\text{regolith on}] \qquad\text{on dune cells:}\quad \eta_i = \max\!\left(\eta_i,\ 1.5 + \frac{1.3}{\max(V,\,0.85)^2}\right)$$

### ① Roughness → η (1.0–1.5)

For each 10 × 10 m cell of the HiRISE 1 m DTM:

1. High-pass the 1 m heights: $h' = h - G_{\sigma=3\,\mathrm m}(h)$. This removes hill-scale slopes and keeps
   rock- and bump-scale relief.
2. Take the standard deviation of $h'$ inside the 10 × 10 m block: $\sigma_{\text{rough}}$ (m).
3. Normalise with 0.5 m as the maximum: $r = \mathrm{clip}(\sigma_{\text{rough}}/0.5,\ 0,\ 1)$.
4. Set $\eta^{\text{rough}} = 1.0 + 0.5\,r$.

- The 0.5 m scale and the 1.0–1.5 range are **design assumptions**, not fitted to measurements.
- Per-cell η is stored in the demo as 0–255 steps (`eta_min` = 1.0, `eta_max` = 1.5).

### ② Regolith (+0.2)

Richmond, Potter & Santee 2015 (J Sport Hum Perf 3(3)), Table 11, gives η = 1.2 for gravel and dirt roads. Mars
regolith is assumed to be about that much harder than a treadmill, so +0.2 is added to every cell and to the
level-walking reference.

### ③ Sand dunes: η = 1.5 + 1.3 / V²

- This is Eq. 16 of the same paper: on sand, η rises as you walk more slowly.
- The data cover V ≥ 0.85 m/s, so slower speeds use the 0.85 m/s value (η = 3.30).
- Dune cells are **candidates** found by `dune_mask.py` from HiRISE orthoimage brightness:
  - The orthoimage is box-averaged onto the 10 m grid.
  - A 3 × 3 mean is applied, then Otsu thresholding twice to isolate the darkest basaltic sand.
  - Blobs under 30 cells are dropped.
  - In Gale this gives **≈ 8.6 km²** around the Bagnold dunes.
- This applies Earth sand data unchanged to Mars gravity, so treat it as a **scenario**.

---

## 3. How much it matters (main model, level ground)

The reference for level walking at 0.92 m/s is **444 W** (114 g O2/h).

| Ground | η | Extra | Total | O2 |
|---|---|---|---|---|
| Smooth floor | 1.0 | 0 W | 444 W | 114 g/h |
| Regolith only | 1.2 | *+15.8 W* | 460 W | 118 g/h (+3.6%) |
| Roughest cell | 1.5 | *+39.6 W* | 484 W | 124 g/h (+8.9%) |
| Roughest + regolith | 1.7 | *+55.4 W* | 499 W | 128 g/h (+12.5%) |
| Sand dune | 3.04 | *+161 W* | 605 W | 155 g/h (+36%) |

Extra = (η − 1) × 93.6 × 0.92² = (η − 1) × 79.2 W.

Slower walking (for example uphill) shrinks the extra by v². *At 0.5 m/s with η = 1.5: +11.7 W.* Sand uses
η = 3.30 below 0.85 m/s, so *at 0.5 m/s: +53.8 W.*

---

## 4. In the demo

- **"Local metabolic-rate map" layer** (More layers): the metabolic rate when climbing the steepest way out of each
  cell. Rough, high-η ground shows brighter.
- **"Dune candidates" layer**: the cells where ③ applies.
- **"Safety ops · literature-based corrections"**: switches for regolith +0.2 and sand η. Turning either on
  recomputes the walk-back zone, stay times and rescue plan.

## 5. Limits

- A 1 m DTM cannot see stones smaller than 1 m. Roughness **stands in for** rock load; it is not a rock count.
- The mapping from 0.5 m relief to η = 1.5 is a design assumption and has not been validated with suited walking.
- Pandolf and Richmond η values were measured on Earth without a suit. Using them at Mars gravity with a 90 kg suit
  is an extrapolation.
- Dune cells are brightness-based candidates: shaded steep slopes or dark bedrock can slip in, and thin sand
  sheets are missed.
- η is assumed not to change speed. In reality crews slow down on rough ground, which adds time.

## References

- Pandolf K. B., Givoni B., Goldman R. F. 1977, J Appl Physiol 43:577 (load-carriage metabolism and terrain factor η).
- Richmond P. W., Potter A. W., Santee W. R. 2015, J Sport Hum Perf 3(3) (η by surface; sand η = 1.5 + 1.3/V²).
- Santee W. R. et al. 2003 (downhill correction, comparison model).
- NASA/TP-2010-216115, NASA/TP-2010-216125 (IST-1/2 reduced-gravity suited walking).
- HiRISE DTMs and orthoimages (NASA PDS, University of Arizona).
