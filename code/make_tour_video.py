"""
해커톤 제출용 30초 소개 영상(영어 자막)을 데모 화면으로 자동 제작한다.

    python make_tour_video.py      -> ../outputs/video/eva_walkback_tour.mp4 (1920x1080, 30 fps)

환경: WSL + Windows Chrome(헤드리스 스크린샷), ffmpeg. 장면마다 데모를 열고 버튼 클릭을 스크립트로 흉내 낸 뒤 찍는다.
장면: 제목 → Gale 귀환 반경 → Aram 장애물 지형 → EVA 시뮬레이션 + 헬멧 바이저 HUD → Jezero 과학 EVA 계획 → 로드뷰 → 자료 출처.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFont

CH = "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe"
WTMP = "/mnt/c/Users/user/AppData/Local/Temp/evademo"
WURL = "file:///C:/Users/user/AppData/Local/Temp/evademo"
WWIN = "C:\\Users\\user\\AppData\\Local\\Temp\\evademo"
DEMO = "../reports/18-eva-walkback-demo.html"
OUT = "../outputs/video"
FONT = "../.venv/lib/python3.9/site-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSans.ttf"
FONTB = FONT.replace("DejaVuSans.ttf", "DejaVuSans-Bold.ttf")
FPS = 30
W, H = 1920, 1080
BG = (11, 14, 21)


def page(name, hash_, actions, size=(1480, 1200), budget=90000):
    """데모를 열고 actions[(지연 ms, JS)]를 실행한 뒤 스크린샷."""
    src = open(f"{WTMP}/demo.html", encoding="utf-8").read()
    js = "".join(f"setTimeout(()=>{{try{{{a}}}catch(e){{}}}},{t});" for t, a in actions)
    open(f"{WTMP}/{name}.html", "w", encoding="utf-8").write(src + f"<script>{js}</script>")
    subprocess.run([CH, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={size[0]},{size[1]}",
                    f"--virtual-time-budget={budget}", f"--screenshot={WWIN}\\{name}.png", f"{WURL}/{name}.html{hash_}"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    return Image.open(f"{WTMP}/{name}.png").convert("RGB")


def rects(hash_, actions, size):
    """요소 위치(px) 알아내기: dump-dom으로."""
    src = open(f"{WTMP}/demo.html", encoding="utf-8").read()
    js = "".join(f"setTimeout(()=>{{try{{{a}}}catch(e){{}}}},{t});" for t, a in actions)
    js += ("setTimeout(()=>{const o={};for(const id of ['mapwrap','visor','rv','eva-order','pt-meters','glance','sites-seg']){const e=document.getElementById(id);"
           "if(e){const r=e.getBoundingClientRect();o[id]=[r.left,r.top+scrollY,r.width,r.height];}}const p=document.createElement('pre');p.id='rects';"
           "p.textContent=JSON.stringify(o);document.body.appendChild(p)},60000);")
    open(f"{WTMP}/rects.html", "w", encoding="utf-8").write(src + f"<script>{js}</script>")
    out = subprocess.run([CH, "--headless=new", "--disable-gpu", f"--window-size={size[0]},{size[1]}", "--virtual-time-budget=90000",
                          "--dump-dom", f"{WURL}/rects.html{hash_}"], capture_output=True, text=True, timeout=300).stdout
    return json.loads(re.search(r'<pre id="rects">(.*?)</pre>', out).group(1))


def card(lines, sub=None):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    fb, f = ImageFont.truetype(FONTB, 64), ImageFont.truetype(FONT, 34)
    y = 360
    for ln in lines:
        w = d.textlength(ln, font=fb); d.text(((W - w) / 2, y), ln, font=fb, fill=(231, 234, 240)); y += 86
    if sub:
        for ln in sub:
            w = d.textlength(ln, font=f); d.text(((W - w) / 2, y + 30), ln, font=f, fill=(226, 121, 77)); y += 50
    return im


def frame(img, caption, crop=None):
    """스크린샷(잘라서) + 아래 자막 띠 -> 1920x1080."""
    if crop:
        img = img.crop(crop)
    canvas = Image.new("RGB", (W, H), BG)
    box_h = H - 120
    s = min(W / img.width, box_h / img.height)
    im = img.resize((int(img.width * s), int(img.height * s)), Image.LANCZOS)
    canvas.paste(im, ((W - im.width) // 2, (box_h - im.height) // 2))
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, H - 120, W, H], fill=(21, 26, 35))
    d.rectangle([0, H - 120, 8, H], fill=(226, 121, 77))
    f = ImageFont.truetype(FONT, 38)
    w = d.textlength(caption, font=f)
    d.text(((W - w) / 2, H - 82), caption, font=f, fill=(231, 234, 240))
    return canvas


def side(a, b, caption):
    """두 이미지를 나란히 (지도 + 바이저)."""
    h = 900
    a = a.resize((int(a.width * h / a.height), h), Image.LANCZOS)
    b = b.resize((int(b.width * (W - a.width - 30) / b.width), int(b.height * (W - a.width - 30) / b.width)), Image.LANCZOS)
    c = Image.new("RGB", (a.width + 30 + b.width, max(h, b.height)), BG)
    c.paste(a, (0, 0)); c.paste(b, (a.width + 30, (h - b.height) // 2))
    return frame(c, caption)


def main():
    os.makedirs(OUT, exist_ok=True)
    fdir = f"{OUT}/frames"
    shutil.rmtree(fdir, ignore_errors=True); os.makedirs(fdir)
    shutil.copy(DEMO, f"{WTMP}/demo.html")
    EN = (10000, "document.getElementById('lang-btn').click()")
    seq = []                                   # (이미지, 초)

    seq.append((card(["Mars EVA Walk-Back Map", "Can the crew always get home?"],
                     ["NASA Space Apps 2026 · Interplanetary Survival Guide: Martian Map"]), 3.0))
    print("scene: gale")
    g = page("t_gale", "", [EN], (1480, 1150))
    seq.append((frame(g.crop((330, 230, 1480, 1150)), "Every 10 m cell: can the crew still walk back? O2 · coolant · radiation · comm"), 4.0))
    print("scene: aram")
    a = page("t_aram", "#aram", [EN, (12000, "document.getElementById('showmr').click()")], (1480, 1150))
    seq.append((frame(a.crop((330, 230, 1480, 1150)), "Obstacle-rich sites from the HiRISE 1 m DTM: walk around blocks and scarps"), 3.0))

    print("scene: sim + visor")
    acts = [(9000, "document.querySelector('#presets button[data-id=simhr]').click()"), (12000, "document.getElementById('lang-btn').click()"),
            (13000, "document.getElementById('hud-btn').click()")]
    R = rects("", acts, (1480, 2200))
    mx, my, mw, mh = R["mapwrap"]; vx, vy, vw, vh = R["visor"]
    sims = list(range(0, 241, 16)) + [120, 241]
    for n in sorted(set(sims)):
        p = page(f"t_sim{n:03d}", "", acts + [(16000, f"const t=document.getElementById('sim-t');t.value={n};t.dispatchEvent(new Event('input'))")], (1480, 2200))
        mp = p.crop((int(mx), int(my), int(mx + mw), int(my + mh)))
        vs = p.crop((int(vx) - 4, int(vy) - 4, int(vx + vw) + 4, int(vy + vh) + 4))
        cap = "Helmet HUD: heart-rate-driven O2 use, live return margin, turn-back alert" if n < 120 else "Turn-back alert fires before the return margin runs out — crew gets home"
        seq.append((side(mp, vs, cap), 8.0 / len(set(sims))))
        print("  sim minute", n)

    print("scene: jezero eva")
    e = page("t_eva", "#jezero", [(12000, "document.querySelector('#presets button[data-id=eva]').click()"), (15000, "document.getElementById('lang-btn').click()")], (1480, 1500))
    seq.append((frame(e.crop((330, 230, 1480, 1250)), "Science EVA: visit real rover dwell sites, checked against the walk-back radius at every step"), 4.0))

    print("scene: road view")
    rv = json.load(open("../outputs/demo/roadview/jezero/roadview.json"))
    st = [x for x in rv if len(x["frames"]) > 1][0]
    m = json.load(open("../outputs/demo/sites/jezero/meta.json"))
    click = ("document.getElementById('rv-btn').click();const v=document.getElementById('vec');const r=v.getBoundingClientRect();"
             f"v.dispatchEvent(new MouseEvent('click',{{clientX:r.left+{st['x']}/{m['cols']}*r.width,clientY:r.top+{st['y']}/{m['rows']}*r.height,bubbles:true}}))")
    acts = [(12000, click), (14000, "document.getElementById('lang-btn').click()")]
    R = rects("#jezero", acts, (1480, 1800))
    mx, my, mw, mh = R["mapwrap"]; rx, ry, rw, rh = R["rv"]
    r_ = page("t_rv", "#jezero", acts, (1480, 1800))
    seq.append((frame(r_.crop((int(mx), int(my + mh * 0.35), int(mx + mw), int(ry + rh))), "Road view: rover Navcam photos show what the crew will see there"), 3.0))

    seq.append((card(["Built on NASA data"],
                     ["HiRISE DTM & ortho · MSL / Mars 2020 traverses & raw images",
                      "JPL Mars Trek THEMIS · Curiosity RAD · Pandolf / Santee / Richmond models",
                      "github.com/jstak0804/martian-map-slam"]), 3.0))

    k = 0
    for im, sec in seq:
        for _ in range(max(1, round(sec * FPS))):
            im.save(f"{fdir}/f{k:05d}.png"); k += 1
    out = f"{OUT}/eva_walkback_tour.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(FPS), "-i", f"{fdir}/f%05d.png",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23", out], check=True)
    shutil.rmtree(fdir)
    print(f"saved {out} ({k / FPS:.1f} s, {os.path.getsize(out) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
