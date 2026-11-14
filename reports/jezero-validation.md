# Jezero implementation and validation record

Updated 2026-11-14. The working directory is a source copy without an available Git CLI. The historical upstream commit is provenance, not a verified local checkout status.

## Implemented

- Offline global MOLA overview, pan/zoom, coordinate selection, persistent overview position, three region links, and data-status metadata. Unregistered positions do not initiate local route calculations. Online higher-resolution tiles use the PLAN's offline fallback branch.
- Full-screen map, real rover-photo visor, north reset, rotation, location/goal icons, English primary UI, A/B allocation, manual return, and a shared simulation clock.
- Live remaining-itinerary estimates use current oxygen, coolant, metabolic multiplier, accumulated dose, remaining destinations and the original base. They solve the remaining stay budget on candidate paths in the existing visit order. These estimates do not silently replace the running simulation's previously scheduled itinerary or claim global optimality. Calculation-in-progress is explicit; live forward-tree retention is bounded.
- Strict Jezero EVA graph rejects high-risk/invalid endpoints, diagonal corner cutting and edges over 20 degrees; no forced source/base exception or descent bypass. Main thread and worker retain the existing 16 directions. Energy ties are relaxed using travel time. Time arrays use double precision to prevent repeated false improvements from float rounding.
- Region generation guards reject stale decompression and tree responses. Cache identities include region, base, strict mode and overlay revision.
- Synthetic blocked-cell demo recalculates the same selected mission. Synthetic cells are shown separately and never written into the observation manifest.
- Source catalog: 366 PDS products, including 348 raw product variants from 36 camera/time exposure identifiers, plus 18 mesh products. Every catalog product has a SHA256, label-derived identity and capture time. Product variants are not counted as new photographs.
- Two official PDS meshes in SITE_FRAME 25 were combined as a local vertex-cloud preview: 239,349 source vertices, 7,979 decimated preview vertices. Eleven shared 1-meter XY bins have a median height difference of approximately 0.0233 m. This is an overlap diagnostic, **not** an independent registration error or a surface-accuracy claim. No new stereo reconstruction was performed.
- PLACES rover stations 25/94 and 25/214 were projected using the downloaded HiRISE DTM label. Their approach cells are separated from the localized rover/camera positions by approximately 9.25 m and 2.49 m. Both retain `image_registration: null`.

## Executed checks

See `automated-validation.json` for build and test results and `packaged-grid-validation.json` for the actual-grid run. The former includes 39 UI/planner/simulation checks and 26 observation/global/worker checks. The latter runs the actual worker and packaged 466,900-cell Jezero terrain, checks explicit edge oxygen/time integrals, verifies a two-target trip retains at least 20% initial oxygen, and verifies synthetic blockage causes a route that avoids the blocked cell.

The packaged IST regression coefficients match the reference coefficient file at body mass 75 kg and suit mass 90 kg. The evaluated flat metabolic rate is 444.3962696888408 W. A separate Python 3.12.10 / NumPy 2.2.6 environment was subsequently prepared under C:/nasa/.tools. The original Python model generated 84 cases spanning grade, terrain factor, distance and environmental heat. All 504 comparisons passed, with maximum relative error 3.6128103312332233e-16. See python-js-model-validation.json. Known 10 g/h leakage is included in EVA resource budgets, live zones and simulator accounting; final partial minutes do not charge a full minute of leakage.

The Windows local environment reports x64, release 10.0.26200, 32 GiB RAM (approximately 19 GiB free when checked). Processing used the local CPU, not a remote GPU. Initially Python, Node, and Git command-line executables were not resolved. Python 3.12.10 was then downloaded from python.org into the workspace, with the NumPy 2.2.6 wheel from PyPI verified against its SHA256. JavaScript ran through the provided Node REPL runtime. Existing application environments were not upgraded.

## Gates and remaining limitations

| Gate | Result |
|---|---|
| G0 baseline | Baseline preserved; source and generated HTML hashes recorded in the package. Browser launch is available, browser inspection is not. |
| GW global | Offline functionality implemented; online tile expansion deferred under the prescribed fallback. Actual browser gesture/rendering check remains open. |
| G1 input identity | PDS source identities, common SITE_FRAME 25 and PLACES site-drive distinctions verified from local labels. |
| G2 geometry | Local-only composite delivered. No independent orbital control/holdout registration, no registered observed/blocked cells, no calibrated stitched panorama. |
| G3 model/graph | JavaScript, actual Python reference, coefficient provenance and actual-grid checks executed. |
| G4 mission/UI | Map controls, A/B budgets, live estimates, manual return and synthetic event implemented; real browser interaction sign-off pending. |
| G5 device QA | Not passed: browser access host unavailable; mobile touch, offline browser operation, popup synchronization and device timing not visually verified. |
| Submission | Local review package prepared. New screen recording and public redistribution/license review remain pending; no publication performed. |

Browser inventory again returned `The browser access host is unavailable`. The official Windows Computer Use fallback was also attempted; it stopped because the current Chrome URL could not be determined confidently enough for policy enforcement. No further app input was issued. There is no claim that automated numerical checks verify appearance, mobile interaction, or continuous first-person camera registration.

Orbital registration needs independent control and holdout evidence meeting the PLAN's criteria. A shared PDS site frame or PLACES station match cannot replace those checks. The official derived-product CPU branch was used; remote GPU testing is not claimed. The preview is a local projection of mesh vertices, not a new photorealistic panorama or a registered traversability map.

## Reproduction

From a Node-capable environment, import and invoke:

1. `buildEvidence(root)` and `buildStationCandidates(root)` from `code/build_observation_evidence.mjs`.
2. `buildUI(root)` from `code/build_ui_preview.mjs` using the preserved packed terrain input.
3. `runTests(root)`, `runRemainingTests(root)`, and `runPackagedGrid(root)` from the three test modules.

Keep the original data archive. The local review package is not the full 25+ GB research download. `#mars` opens the overview; `#jezero-evidence-demo` selects the reproducible Brac/Amalik mission. The snapshot-based live estimate is at whole-minute simulator resolution.

The final actual-grid run found both new Navcam approach cells disconnected from the default landing base under the strict graph. They are therefore observation-only at that base; the UI does not offer them as reachable destinations. The three pre-existing science targets remain reachable. The approximate approach offsets above are local offsets, not evidence of base connectivity.
