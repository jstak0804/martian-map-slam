# Methods — how the planner turns terrain into minutes of oxygen

Mars EVA Walkback & Survival Planner · NASA Space Apps 2026
Korean version: [METHODS.ko.md](METHODS.ko.md) · Terrain factor η in detail: [TERRAIN.md](TERRAIN.md)

All formulas below are the ones the demo actually runs (`code/demo_template.html`). Numbers in
*italics* are worked examples.

---

## 1. Start-of-EVA consumables

| Quantity | Value | Basis |
|---|---|---|
| O2 at start | **680 g** | Apollo 15–17 PLSS: ≈1.5 lb gaseous O2 stored at 1,380–1,440 psi |
| Cooling water at start | **5.2 kg** | Apollo 15–17 PLSS: 11.5 lb feedwater |
| Astronaut / suit mass | 75 kg / 90 kg | design assumption |
| Mars gravity | 0.378 g (3.711 m/s²) | |

## 2. Metabolic rate → oxygen

Energy released per litre of O2 (Weir equation, RER ≈ 0.8): **20.1 kJ/L**. O2 density: **1.429 g/L**.

$$\dot m_{O_2}\,[\mathrm{g/s}] = \frac{M\,[\mathrm W]}{20\,100\ \mathrm{J/L}} \times 1.429\ \mathrm{g/L} = M \times 7.11\times10^{-5}$$

| Metabolic rate M | O2 use | Where it is used |
|---|---|---|
| 444 W | *114 g/h* | level walking at 0.92 m/s |
| 352 W | *90 g/h* (30 min = **45 g**) | reserve definition (NASA PLSS design average 1200 BTU/h) |
| 222 W | *57 g/h* | standing with load (lower bound) |
| 147 W | *38 g/h* | riding a rover (≈500 BTU/h, assumption) |

If heart rate shows the crew working harder than the model, the multiplier **k** (actual ÷ model)
scales every O2 and water figure: $\dot m_{O_2} = k \cdot M \times 7.11\times10^{-5}$.

## 3. Walking metabolic rate (NASA IST suited-walking data)

Regression of NASA IST-1 (level) and IST-2 (grade) reduced-gravity suited walking tests,
evaluated at the Mars suited weight (75 + 90 kg) × 3.711 m/s² = 612 N:

**Level walking** (VO2 in mL·kg⁻¹·min⁻¹, v in m/s):

$$L(v) = -0.4694\,v^2 + 16.600\,v + 2.813$$

**Uphill increment** (grade G in %, measured at 0.77 m/s):

$$\Delta G(G) = 0.013043\,G^2 + 0.11395\,G \qquad \mathrm{VO_2} = L(v) + \Delta G(G)\,\frac{v}{0.77}$$

**Downhill** (G < 0): Looney et al. 2019 grade-cost ratio, scaled to the suit's grade sensitivity:

$$\mathrm{VO_2} = L(v)\left[1 + s(|G|)\left(\frac{E(v,G)}{E(v,0)} - 1\right)\right],\quad
E(S,G) = 1.44 + 1.94S^{0.43} + 0.24S^4 + 0.34\,S\,G\,(1 - 1.05^{\,1-1.1^{G+32}})$$

where $s(|G|) = \dfrac{\Delta G(|G|)/L(0.77)}{E(0.77,|G|)/E(0.77,0) - 1}$.

**Metabolic rate** (W), with terrain roughness factor η (1.0–1.5 from the 1 m DTM) and a standing floor:

$$M = \max\!\left(\mathrm{VO_2}\cdot 75 \cdot \frac{20.1}{60} + (\eta - 1)\cdot(165 \cdot 0.378)\cdot 1.5\,v^2,\ 222\ \mathrm W\right)$$

*Check: L(0.92) = 17.69 mL·kg⁻¹·min⁻¹ → 17.69 × 75 × 20.1 / 60 = 444 W.*

**Walking speed:** 0.92 m/s on the level (Apollo 15 emergency walk-back pace). Uphill: the speed at which
VO2 equals the level-walking VO2 ("equal effort", solve $L(v) + \Delta G\,v/0.77 = L(0.92)$).
Downhill: the smaller of equal effort and $0.92 \times$ Tobler's ratio
$e^{-3.5|G/100 + 0.05|}/e^{-3.5\cdot0.05}$. Never faster than 0.92 m/s.

## 4. Cooling water

The PLSS rejects metabolic heat (plus environment heat q) by evaporating water (latent heat 2.477 MJ/kg):

$$\dot m_{w}\,[\mathrm{g/s}] = \frac{k\,M + q}{2\,477\ \mathrm{J/g}}$$

*444 W → 645 g/h.* Reserve: 352 W × 30 min → 256 g. After the water is gone the body can store about
141 g-equivalent of heat (2.0 BTU/lb emergency limit).

## 5. Routes and the walk-back zone

- Terrain: HiRISE 1 m DTM resampled to 10 m cells; 16 move directions; a move is blocked if its own slope
  exceeds 20° (36.4 %) or, for knight moves, if either crossed cell is blocked.
- Cost of one move of length d between cells a → b (grade G = Δh/d):

$$\Delta O_2 = M(G,\eta,v)\times 7.11\times10^{-5}\times \frac{d}{v},\qquad \Delta t = \frac{d}{v}$$

- **Return tree** S: reverse Dijkstra from base gives, for every cell i, the minimum O2 $S_i$ to walk home
  (and the time and dose along that route). **Outbound tree** F: forward Dijkstra from base gives $F_i$.
- **Map colours** (exploration mode): O2 left after base → i → base, as a fraction of the start O2 $O_s$:

$$r_i = \frac{O_s - k\,(F_i + S_i)}{O_s}\quad\Rightarrow\quad r_i > 20\%\ \text{blue},\ 10\text{–}20\%\ \text{yellow},\ 0\text{–}10\%\ \text{red}$$

- **Radiation** on the way: Curiosity RAD background 0.655 mSv/day × (1 − 0.5 × terrain-shielding proxy) ×
  SPE multiplier; budget 1 mSv per return (scenario).
- **Multi-objective routes** during an SPE: each move costs
  $k\,\Delta O_2/B_{O_2} + \Delta W/B_W + \mathrm{SPE}\cdot\Delta \mathrm{Dose}/B_{\mathrm{Dose}}$ (B = budget left);
  a cell is safe if either the lowest-O2 route or this route fits every budget.

## 6. Exploration scenarios (go / return / stay)

For a visit order base → A (→ B …) → base, the legs come from forward Dijkstra trees started at the base
and at each site. With travel O2 $U = k\sum \Delta O_2$, travel water $U_w$, and the stay rates at
level-walking metabolism ($\dot m_{O_2}^{stay}$, $\dot m_w^{stay}$):

$$T_{stay} = \min\!\left(\frac{0.8\,O_s - U}{\dot m^{stay}_{O_2}},\ \frac{0.8\,W_s - U_w}{\dot m^{stay}_w},\ \frac{1\,\mathrm{mSv} - \mathrm{Dose}_{travel}}{\dot D_{site}}\right)$$

i.e. **the crew must reach base with at least the return reserve R (20 % by default, adjustable) of the
starting O2 and water**; 0.8 above is $1-R$ and 0.2 is $R$. Map colours follow R: blue > R, yellow R/2–R, red 0–R/2.
Sites left on auto share $T_{stay}$ equally ($T_{stay}/n$); if minutes are typed for some sites, the remaining time
is split among the auto sites. Reported times: go = base → first site, return = last site → base, stay = $T_{stay}$.

**Rescue playback supply:** at least the minimum (the stranded crew member's walk home + 30 min reserve), and the
rescuer's surplus is split in half so **both arrive with the same amount**. During playback the map shows, in the same
three colours, what the stranded crew member (after hand-over: the lower of the two) would have left walking home
from each cell, so the zone grows again at the moment of resupply.

*Example (Jezero, on foot, site A only): (0.8 × 680 − 191) g ÷ 114 g/h = 3.1 h → "can stay 3 h 06 min".*

**Rover:** travel time = distance / 2.2 m/s (≈8 km/h), travel metabolism 147 W. Apollo walk-back rule: at
every site j the crew must still be able to **walk** home if the rover fails, arriving with ≥ R:

$$O_s - U_{\le j} - T_{stay}\tfrac{j}{n}\,\dot m^{stay}_{O_2} - k\,S_{site_j} \ \ge\ 0.2\,O_s \quad\text{(same for water)}$$

## 7. Live turn-back alarm

Every simulated minute: if walking (or working) one more minute would leave less than the required margin
for the return from the next position, the crew turns around:

$$O_2^{left} - k\,S_{pos} \ \ge\ 0.2\,O_s\ \text{(exploration)} \qquad\text{or}\qquad 1.2\,k\,S_{pos} \le O_2^{left} - 45\ \mathrm g\ \text{(other modes)}$$

Heart rate → metabolic rate (Hoffmann 2021, Shuttle/ISS EVAs): $M\,[\mathrm{BTU/h}] = 284.55 + 5.984\,\mathrm{HR}$;
k = heart-rate metabolic rate ÷ model over the last 10 minutes.

## 8. Communications signal bars

Line of sight over terrain and Mars curvature (3 m base, 2 m suit, 3 m relay antennas). Bars: strong
(line of sight, ≤ 2 km), good (≤ 5 km), weak (> 5 km or via relay), "link within 50 m", no link.
A geometric indicator, not a link budget.

## 9. Validation and limits

- The demo reproduces an independent Python implementation (`walkback_verification/`): Gale, 150 g O2,
  walk-back area **9.72 km²**. The older Pandolf × gravity model gives 19.95 km² (comparison switch).
- Outside the HiRISE DTM strip the exploration colours are a **level-ground estimate** (hatched): the round-trip O2 of the
  nearest strip cell plus level walking at η = 1.2 outward (16-direction distance on a 40 m grid). Rough or steep ground
  (e.g. Mt. Sharp) makes the real cost higher, so treat it as optimistic until a surrounding DEM is added.
- IST tests ran at 0.12–0.32 g on Earth, not Mars 0.378 g with a 90 kg suit; downhill costs are scaled
  extrapolations; rover speed and riding metabolism are assumptions; terrain shielding and fall risk are proxies.


### Observed data vs. models

| Observed / published data (NASA) | Models and scenarios (computed or chosen by us) |
|---|---|
| HiRISE 1 m DTMs and orthoimages | Walking metabolism (regression on NASA IST tests, extrapolated to Mars gravity) |
| Curiosity / Perseverance traverses, stops, Navcam raw images | Return routes, walk-back areas, stay times (Dijkstra results) |
| Mars 2020 sample list | Heart-rate and tank-pressure telemetry (synthetic scenarios or CSV input) |
| Curiosity RAD background dose, observed SPE ×2.9 | 1 mSv dose budget, terrain shielding proxy, large SPE multipliers |
| Apollo 15–17 PLSS consumables (680 g O2, 5.2 kg water) | Rover speed and riding metabolism; fall-risk and comm-bar proxies |
| JPL Mars Trek THEMIS night IR | First-person visor rendered from the 10 m terrain (not a photograph) |

## References

- NASA/TP-2010-216115 (IST-1) and NASA/TP-2010-216125 (IST-2), reduced-gravity suited walking.
- Looney D. P. et al. 2019, Med Sci Sports Exerc 51:1954 (graded walking energy expenditure).
- Tobler W. 1993 hiking function; Waligora J. M. & Horrigan D. J. 1975 (Apollo metabolic rates).
- Hoffmann et al. 2021, NASA (heart rate → metabolic rate, Shuttle/ISS EVAs).
- Hassler D. M. et al. 2014, Science 343 (Curiosity RAD surface dose).
- [Apollo 15 LM Portable Life Support System](https://apollojournals.org/alsj//LM15_Portable_Life_Support_System_ppP1-5.pdf);
  [Primary life support system](https://en.wikipedia.org/wiki/Primary_life_support_system).
- HiRISE DTMs (NASA PDS, University of Arizona).
