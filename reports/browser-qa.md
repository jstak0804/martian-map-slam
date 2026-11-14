# Browser QA (PLAN §19.1)

- Browser: Chrome/157.0.8103.51 (headless, DevTools protocol, `tests/browser_qa.mjs`)
- HTML: `reports/18-eva-walkback-demo.html` SHA256 `9ad2b2e268fc966db6d4c7df91cb0b185bca89858b9811f27c3dcc3875f57667`
- Date: 2026-11-14T11:26:14.328Z
- Result: 7 pass / 9 fail scenarios; 115/130 checks
- Device rows are Chrome emulation, not physical devices.

| ID | Scenario | Env | Result | Failed checks | Evidence |
|---|---|---|---|---|---|
| S1 | Entry hashes | Chrome headless, 1440×900, file:// | **pass** | — | [png](browser-qa/S1-entry-world-1440.png) [png](browser-qa/S1-evidence-demo-1440.png) |
| S2 | Targets: A only / B only / A+B / max two / observation-only | Chrome headless, 1440×900, file:// | **pass** | — | [png](browser-qa/S2-two-sites-1440.png) [png](browser-qa/S2-observation-only-1440.png) |
| S3 | Stay split 25/50/75 and order reversal | Chrome headless, 1440×900, file:// | **pass** | — |  |
| S4 | Rotate / zoom / N / scale / hit-test after rotation | Chrome headless, 1440×900, file:// | **fail** | N: base centered; click on rotated (-45°) pins opens the same site | [png](browser-qa/S4-rotated-1440.png) |
| S5 | Site photos: real image and source | Chrome headless, 1440×900, file:// | **pass** | — |  |
| S6 | Visor window: same frame as map, close / reopen | Chrome headless, 1440×900, file:// | **fail** | Visor opens a window from a user click / error: Error: eval failed: TypeError: Cannot read properties of null (reading 'document') /     at <anonymous>:1:42 /     at <a |  |
| S7 | Return now during travel / at site / partial minute; Restart | Chrome headless, 1440×900, file:// | **pass** | — |  |
| S8 | Block test / Clear block repeated; worker pending settles | Chrome headless, 1440×900, file:// | **pass** | — | [png](browser-qa/S8-block-test-1440.png) |
| S9 | Region switch Jezero→Gale→Jezero fast and during loading/planning | Chrome headless, 1440×900, file:// | **fail** | Gale hides Jezero-only Observations/Block test |  |
| S10 | Global map: open/close, pan/zoom, click coordinates, region entry | Chrome headless, 1440×900, file:// | **fail** | drag pans the global map; region data status readable without hover (touch) | [png](browser-qa/S10-global-1440.png) |
| S11 | Offline (network disabled) file:// open | Chrome headless 1440×900, network emulated offline | **fail** | no external request needed for core features |  |
| S12 | HTTP localhost vs file | Chrome headless 1440×900, http://127.0.0.1 (python http.server) | **fail** | visor window opens over HTTP |  |
| S13 | Screen sizes: key controls visible, not covered, tappable | Chrome headless device emulation | **fail** | phone 390×844 (touch emulation): controls visible, inside viewport, not covered; phone 390×844 (touch emulation): touch targets ≥32px; phone landscape 844×390 (touch emulation): site popup fits and can be closed | [png](browser-qa/S13-desktop-1440x900.png) [png](browser-qa/S13-desktop-1440x900-settings.png) [png](browser-qa/S13-laptop-1366x768.png) [png](browser-qa/S13-laptop-1366x768-settings.png) [png](browser-qa/S13-phone-390x844.png) [png](browser-qa/S13-phone-390x844-settings.png) [png](browser-qa/S13-phone-844x390.png) [png](browser-qa/S13-phone-844x390-settings.png) |
| S14 | Touch: pinch, twist, pan (emulated touch events) | Chrome headless 390×844 touch emulation | **fail** | one-finger pan moves the map |  |
| S15 | Keyboard and English-only text | Chrome headless, 1440×900, file:// | **fail** | Tab reaches map controls; map screen names/titles/alt have no Korean (screen readers, tooltips); settings drawer has no Korean text |  |
| S16 | Performance (emulated desktop, this PC) | Chrome headless 1440×900 on local Windows PC | **pass** | — |  |

## Not run

- Physical phone/tablet (only Chrome device emulation)
- Safari/Firefox
- Popup-blocker enabled browser (headless allows window.open)
- Screen recording (H7)

## Notes

- S1: (none) load 1061 ms
- S1: #mars load 827 ms
- S1: #jezero load 522 ms
- S1: evidence demo: load 505 ms, first plan 1086 ms after load (worker=true)
- S1: #jezero-evidence-demo load 505 ms
- S1: #gale load 626 ms
- S1: #aram load 511 ms
- S2: targets: Skinner Ridge · Wildcat Ridge sample site | Brac sample site | Amalik sample site | Navcam station 25/94 | Navcam station 25/214
- S3: 25% auto: order 2→1 A 48 min B 144 min
- S3: 25% flip: order 1→2 A 48 min B 144 min
- S3: 50% auto: order 1→2 A 96 min B 96 min
- S3: 50% flip: order 2→1 A 96 min B 96 min
- S3: 75% auto: order 2→1 A 144 min B 48 min
- S3: 75% flip: order 1→2 A 144 min B 48 min
- S5: site 0: 1280×960 Nearby observation · sol 464 · 32m away
- S5: site 1: 1280×960 Nearby observation · sol 178 · 204m away
- S5: site 2: No nearby observation
- S5: site 3: 1280×960 Nearby observation · sol 464 · 135m away · Observation only
- S5: site 4: 1280×960 Nearby observation · sol 464 · 111m away · Observation only
- S5: 4/5 sites show a nearby photo
- S7: {"frames":312,"phases":["out","work","back","home"]}
- S7: partial-minute frames present: false
- S8: race probe state: {"zonePending":false,"workerPending":0,"livePending":null}
- S9: {"Gale (Curiosity)":0,"Jezero (Perseverance)":1,"Aram Chaos (virtual base)":2}
- S9: after 4 awaited switches: {"site":"jezero","mode":"eva"}
- S10: region buttons: [{"text":"Gale (Curiosity)","title":"Elevation + orbital map · ground photos: packaged · local geometry: not_checked"},{"text":"Jezero (Perseverance)","title":"Elevation + orbital map · ground photos: packaged · local geometry: packaged"},{"text":"Aram Chaos (virtual base)","title":"Elevation + orbital map · ground photos: not_checked · local geometry: not_checked"}]
- S11: external requests attempted: ["https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans+KR:wght@400;500;600;700&display","https://fonts.gstatic.com/s/ibmplexsanskr/v11/vEFK2-VJISZe3O_rc3ZVYh4aTwNOwtW_Wg.woff2","https://fonts.gstatic.com/s/ibmplexsanskr/v11/vEFN2-VJISZe3O_rc3ZVYh4aTwNOygqbf7OEvsHaFtDGbzuTFhzdq3hW5qs5jg.119.woff2","https://fonts.gstatic.com/s/ibmplexmono/v23/-F6qfjptAgt5VM-kVkqdyU8n3twJwlBFgg.woff2","https://fonts.gstatic.com/s/ibmplexsanskr/v11/vEFN2-VJISZe3O_rc3ZVYh4aTwNOyiacf7OEvsHaFtDGbzuTFhzdq3hW5qs5jg.115.woff2","https://fonts.gstatic.com/s/ibmplexsanskr/v11/vEFN2-VJISZe3O_rc3ZVYh4aTwNOym6aT7HmqQ.woff2","https://fonts.gstatic.com/s/ibmplexsanskr/v11/vEFN2-VJISZe3O_rc3ZVYh4aTwNOyiacf7OEvsHaFtDGbzuTFhzdq3hW5qs5jg.119.woff2","https://fonts.gstatic.com/s/ibmplexmono/v23/-F63fjptAgt5VM-kVkqdyU8n1i8q1w.woff2","https://fonts.gstatic.com/s/ibmplexsanskr/v11/vEFN2-VJISZe3O_rc3ZVYh4aTwNOygqbT7HmqQ.woff2","https://fonts.gstatic.com/s/ibmplexsanskr/v11/vEFN2-VJISZe3O_rc3ZVYh4aTwNOygqbf7OEvsHaFtDGbzuTFhzdq3hW5qs5jg.118.woff2","https://fonts.gstatic.com/s/ibmplexsanskr/v11/vEFN2-VJISZe3O_rc3ZVYh4aTwNOygqbf7OEvsHaFtDGbzuTFhzdq3hW5qs5jg.117.woff2","https://fonts.gstatic.com/s/ibmplexsanskr/v11/vEFN2-VJISZe3O_rc3ZVYh4aTwNOygqbf7OEvsHaFtDGbzuTFhzdq3hW5qs5jg.115.woff2","https://fonts.gstatic.com/s/ibmplexsanskr/v11/vEFN2-VJISZe3O_rc3ZVYh4aTwNOyiacT7HmqQ.woff2","https://fonts.gstatic.com/s/ibmplexsanskr/v11/vEFN2-VJISZe3O_rc3ZVYh4aTwNOyiacf7OEvsHaFtDGbzuTFhzdq3hW5qs5jg.118.woff2","https://fonts.gstatic.com/s/ibmplexsanskr/v11/vEFN2-VJISZe3O_rc3ZVYh4aTwNOyiacf7OEvsHaFtDGbzuTFhzdq3hW5qs5jg.117.woff2","https://fonts.gstatic.com/s/ibmplexsanskr/v11/vEFN2-VJISZe3O_rc3ZVYh4aTwNOyiacf7OEvsHaFtDGbzuTFhzdq3hW5qs5jg.116.woff2","https://fonts.gstatic.com/s/ibmplexsanskr/v11/vEFN2-VJISZe3O_rc3ZVYh4aTwNOyiacf7OEvsHaFtDGbzuTFhzdq3hW5qs5jg.114.woff2","https://fonts.gstatic.com/s/ibmplexsanskr/v11/vEFN2-VJISZe3O_rc3ZVYh4aTwNOygqbf7OEvsHaFtDGbzuTFhzdq3hW5qs5jg.116.woff2","https://fonts.gstatic.com/s/ibmplexsanskr/v11/vEFK2-VJISZe3O_rc3ZVYh4aTwNO8tfdTbzIx6SmGN7aVT6YLxnNoW0zig.119.woff2","https://fonts.gstatic.com/s/ibmplexsanskr/v11/vEFK2-VJISZe3O_rc3ZVYh4aTwNO8tfdTbzIx6SmGN7aVT6YLxnNoW0zig.118.woff2","https://fonts.gstatic.com/s/ibmplexsanskr/v11/vEFK2-VJISZe3O_rc3ZVYh4aTwNO8tfdTbzIx6SmGN7aVT6YLxnNoW0zig.117.woff2","https://fonts.gstatic.com/s/ibmplexsanskr/v11/vEFK2-VJISZe3O_rc3ZVYh4aTwNO8tfdTbzIx6SmGN7aVT6YLxnNoW0zig.114.woff2","https://fonts.gstatic.com/s/ibmplexsanskr/v11/vEFK2-VJISZe3O_rc3ZVYh4aTwNO8tfdTbzIx6SmGN7aVT6YLxnNoW0zig.109.woff2","https://fonts.gstatic.com/s/ibmplexsanskr/v11/vEFK2-VJISZe3O_rc3ZVYh4aTwNO8tfdTbzIx6SmGN7aVT6YLxnNoW0zig.32.woff2","https://fonts.gstatic.com/s/ibmplexsanskr/v11/vEFK2-VJISZe3O_rc3ZVYh4aTwNO8tfdTbzIx6SmGN7aVT6YLxnNoW0zig.116.woff2","https://fonts.gstatic.com/s/ibmplexsanskr/v11/vEFN2-VJISZe3O_rc3ZVYh4aTwNOyiacf7OEvsHaFtDGbzuTFhzdq3hW5qs5jg.98.woff2","https://fonts.gstatic.com/s/ibmplexsanskr/v11/vEFK2-VJISZe3O_rc3ZVYh4aTwNO8tfdTbzIx6SmGN7aVT6YLxnNoW0zig.110.woff2","https://fonts.gstatic.com/s/ibmplexsanskr/v11/vEFK2-VJISZe3O_rc3ZVYh4aTwNO8tfdTbzIx6SmGN7aVT6YLxnNoW0zig.98.woff2","https://fonts.gstatic.com/s/ibmplexsanskr/v11/vEFN2-VJISZe3O_rc3ZVYh4aTwNOym6af7OEvsHaFtDGbzuTFhzdq3hW5qs5jg.113.woff2","https://fonts.gstatic.com/s/ibmplexsanskr/v11/vEFN2-VJISZe3O_rc3ZVYh4aTwNOyiacf7OEvsHaFtDGbzuTFhzdq3hW5qs5jg.110.woff2"]
- S12: HTTP load 641 ms; times {"out":"103 min","back":"15 min","dwell":"192 min","split":"B 96 min  ·  A 96 min","status":"Ground coverage unverified"}
- S13: desktop 1440×900: ["map-play","map-out","map-back","map-dwell","map-north","map-plus","map-minus","map-settings","map-world","map-sites","map-return","map-reset"]
- S13: laptop 1366×768: ["map-play","map-out","map-back","map-dwell","map-north","map-plus","map-minus","map-settings","map-world","map-sites","map-return","map-reset"]
- S13: phone 390×844 (touch emulation): ["map-play","map-out","map-back","map-dwell","map-north","map-plus","map-minus","map-settings","map-world","map-sites","map-return","map-reset"]
- S13: phone landscape 844×390 (touch emulation): ["map-play","map-out","map-back","map-dwell","map-north","map-plus","map-minus","map-settings","map-world","map-sites","map-return","map-reset"]
- S15: tab order: map-roadview → map-visor → map-evidence → map-event → map-settings → map-north → map-rotate-left → map-rotate-right → map-plus → map-minus → map-center → map-fit → map-share → BUTTON → BUTTON → map-order → map-reset → map-play → BODY → map-target-pin → map-target-pin selected → map-target-pin → map-target-pin → sim-play → sim-t
- S15: Korean strings in settings drawer: 2
- S16: [{"loadMs":560,"planMs":1572,"liveMs":792,"totalMs":2974,"heapMB":null},{"loadMs":572,"planMs":1764,"liveMs":814,"totalMs":3186,"heapMB":null},{"loadMs":573,"planMs":1741,"liveMs":797,"totalMs":3147,"heapMB":null}]
