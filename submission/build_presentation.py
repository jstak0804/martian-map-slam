"""
제출용 발표 HTML(presentation_base.html, 팀 React 빌드)에 플래너 데모를 'trial'로 넣는다.
  - Stage 2 Mapping 칸의 "Map coming soon" 자리에 미리보기 그림 + ▶ 버튼
  - 버튼을 누르면 전체 화면 창에서 플래너(reports/18-eva-walkback-demo.html, base64로 내장)가 열림
    python build_presentation.py [poster.png]  ->  ../exports/Martian-Map-NASAJOIM.html
"""
import base64, io, sys
from PIL import Image

BASE = "presentation_base.html"
DEMO = "../reports/18-eva-walkback-demo.html"
OUT = "../exports/Martian-Map-NASAJOIM.html"
poster_png = sys.argv[1] if len(sys.argv) > 1 else "poster.png"

s = open(BASE, encoding="utf-8-sig").read()

def rep(old, new):
    global s
    assert s.count(old) == 1, (s.count(old), old[:80])
    s = s.replace(old, new)

# 미리보기 그림 (4:3)
im = Image.open(poster_png).convert("RGB")
W, H = im.size
im = im.crop((int(W * 0.21), int(H * 0.035), int(W * 0.21) + int(H * 0.70 * 4 / 3), int(H * 0.035) + int(H * 0.70))).resize((960, 720), Image.LANCZOS)
buf = io.BytesIO(); im.save(buf, "JPEG", quality=82, optimize=True)
poster = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

# 1) Mapping 데이터: 설명과 버튼 글
rep("T={heading:`Martian Map`,description:`Spatial and temporal hazards combined into a single map of where crews can safely go, and for how long.`,mapImage:``,placeholder:`Map coming soon`}",
    "T={heading:`Martian Map`,description:`Spatial and temporal hazards combined into a single map of where crews can safely go, and for how long.`,mapImage:``,"
    "placeholder:`▶ Try the planner`,trialNote:`Interactive trial · runs offline in your browser · best on a desktop screen`,poster:`" + poster + "`}")
# 2) 자리 표시 대신 버튼
rep("(0,P.jsx)(`span`,{children:T.placeholder})",
    "(0,P.jsxs)(`button`,{type:`button`,className:`trial-launch`,onClick:()=>window.__openTrial&&window.__openTrial(),"
    "children:[(0,P.jsx)(`img`,{src:T.poster,alt:`Planner preview: walk-back zone around a Jezero exploration site`}),"
    "(0,P.jsx)(`span`,{className:`trial-launch__label`,children:T.placeholder})]})")
rep("(0,P.jsx)(`div`,{className:`map-frame reveal`,children:",
    "(0,P.jsx)(`p`,{className:`trial-note reveal`,children:T.trialNote}),(0,P.jsx)(`div`,{className:`map-frame reveal`,children:")
# 3) 파비콘 주소 앞의 잘못된 점 제거
s = s.replace('href=".data:image/png;base64,', 'href="data:image/png;base64,', 1)

css = """
.map-frame{border-style:solid}
.trial-launch{all:unset;cursor:pointer;position:relative;display:block;width:100%;height:100%}
.trial-launch img{object-fit:cover;width:100%;height:100%;transition:transform .4s,filter .4s;filter:saturate(.95)}
.trial-launch:hover img,.trial-launch:focus-visible img{transform:scale(1.03);filter:saturate(1.1)}
.trial-launch__label{position:absolute;left:50%;bottom:8%;translate:-50% 0;background:var(--accent);color:#111;font-weight:700;
  padding:.55em 1.3em;border-radius:999px;font-size:clamp(.95rem,1.4vw,1.15rem);box-shadow:0 6px 24px #0006;white-space:nowrap}
.trial-launch:focus-visible{outline:3px solid var(--accent);outline-offset:3px}
.trial-note{color:var(--muted);font-size:.85em;margin:.2rem 0 .8rem}
.trial-overlay{position:fixed;inset:0;z-index:1000;background:#05070a;display:flex;flex-direction:column}
.trial-overlay[hidden]{display:none}
.trial-bar{display:flex;align-items:center;gap:.8rem;height:44px;padding:0 12px;background:#0d1016;color:#e7eaf0;font:600 14px var(--font)}
.trial-bar b{color:var(--accent)} .trial-bar span{flex:1;color:#9aa3b2;font-weight:400}
.trial-bar button{font:inherit;cursor:pointer;background:#1b2130;color:#e7eaf0;border:1px solid #2c3445;border-radius:8px;padding:5px 12px}
.trial-bar button:hover{border-color:var(--accent)}
.trial-overlay iframe{flex:1;width:100%;border:0;background:#05070a}
.trial-loading{position:absolute;inset:44px 0 0;display:grid;place-items:center;color:#9aa3b2;font:15px var(--font);pointer-events:none}
"""
rep("/*$vite$:1*/</style>", css + "/*$vite$:1*/</style>")

demo_b64 = base64.b64encode(open(DEMO, "rb").read()).decode()
tail = """
    <div class="trial-overlay" id="trial" hidden role="dialog" aria-modal="true" aria-label="Mars EVA Walkback &amp; Survival Planner (trial)">
      <div class="trial-bar"><b>Mars EVA Walkback &amp; Survival Planner</b><span>Trial · NASA HiRISE, CTX, THEMIS, rover data</span>
        <button type="button" id="trial-tab">Open in new tab ↗</button><button type="button" id="trial-close">Close ✕</button></div>
      <div class="trial-loading" id="trial-loading">Loading terrain…</div>
    </div>
    <script type="text/plain" id="planner-b64">""" + demo_b64 + """</script>
    <script>
    (function () {
      var url = null, box = document.getElementById("trial"), frame = null, lastFocus = null;
      function plannerUrl() {
        if (url) return url;
        var b = atob(document.getElementById("planner-b64").textContent.trim()), a = new Uint8Array(b.length);
        for (var i = 0; i < b.length; i++) a[i] = b.charCodeAt(i);
        url = URL.createObjectURL(new Blob([a], { type: "text/html;charset=utf-8" }));
        return url;
      }
      window.__openTrial = function () {
        lastFocus = document.activeElement;
        box.hidden = false; document.documentElement.style.overflow = "hidden";
        if (!frame) {
          document.getElementById("trial-loading").hidden = false;
          setTimeout(function () {
            frame = document.createElement("iframe");
            frame.title = "Mars EVA Walkback & Survival Planner";
            frame.allow = "fullscreen";
            frame.onload = function () { document.getElementById("trial-loading").hidden = true; };
            frame.src = plannerUrl() + "#en";
            box.appendChild(frame);
          }, 30);
        }
        document.getElementById("trial-close").focus();
      };
      function close() { box.hidden = true; document.documentElement.style.overflow = ""; if (lastFocus) lastFocus.focus(); }
      document.getElementById("trial-close").onclick = close;
      document.getElementById("trial-tab").onclick = function () { window.open(plannerUrl() + "#en", "_blank"); };
      document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !box.hidden) close(); });
    })();
    </script>
  </body>"""
rep("\n  </body>", tail)
open(OUT, "w", encoding="utf-8").write(s)
print("saved", OUT, f"{len(s.encode()) / 1e6:.1f} MB")
