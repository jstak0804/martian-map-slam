"""
헬멧 바이저 HUD 적용 화면만 담은 영상 (EVA 시뮬레이션 재생 중 바이저 변화).

    python make_visor_video.py      -> ../outputs/video/visor_hud_ko.mp4, visor_hud_en.mp4, visor_hud_*_still.png

심박 시뮬레이션 예시(Gale, 산소 450 g, 60분부터 대사량 25% 급증, 왕복 여유 +20%)를 매 STEP분마다 찍어 이어 붙인다.
바이저 배경은 그 위치 근처 로버 사진, HUD 값은 그 시각의 시뮬레이션 값.
"""
from __future__ import annotations

import os
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFont

import make_tour_video as T

STEP = 8
FPS = 30
SEC_PER_FRAME = 0.6


KO_FONT, KO_FONTB = "/mnt/c/Windows/Fonts/malgun.ttf", "/mnt/c/Windows/Fonts/malgunbd.ttf"   # 한글 자막용 (맑은 고딕)


def caption_frame(img, top, bottom, lang="en"):
    canvas = Image.new("RGB", (T.W, T.H), T.BG)
    box = (T.W - 80, T.H - 220)
    s = min(box[0] / img.width, box[1] / img.height)
    im = img.resize((int(img.width * s), int(img.height * s)), Image.LANCZOS)
    canvas.paste(im, ((T.W - im.width) // 2, 110 + (box[1] - im.height) // 2))
    d = ImageDraw.Draw(canvas)
    fb, f = (ImageFont.truetype(KO_FONTB, 40), ImageFont.truetype(KO_FONT, 32)) if lang == "ko" else (ImageFont.truetype(T.FONTB, 40), ImageFont.truetype(T.FONT, 32))
    d.text((50, 36), top, font=fb, fill=(231, 234, 240))
    d.rectangle([0, T.H - 100, T.W, T.H], fill=(21, 26, 35)); d.rectangle([0, T.H - 100, 8, T.H], fill=(226, 121, 77))
    w = d.textlength(bottom, font=f); d.text(((T.W - w) / 2, T.H - 70), bottom, font=f, fill=(231, 234, 240))
    return canvas


def run(lang):
    fdir = f"{T.OUT}/frames_visor_{lang}"
    shutil.rmtree(fdir, ignore_errors=True); os.makedirs(fdir)
    acts = [(9000, "document.querySelector('#presets button[data-id=simhr]').click()"),
            (13000, "document.getElementById('hud-btn').click()")]
    if lang == "en":
        acts.append((12000, "document.getElementById('lang-btn').click()"))
    pin = ("const b=document.createElement('div');b.style.cssText='position:fixed;inset:0;background:#0b0e15;z-index:99998';document.body.appendChild(b);"
           "const v=document.getElementById('visor');const r=v.getBoundingClientRect();"
           "const pw=v.closest('.visor-wrap'); if(pw) pw.style.cssText+=';width:744px';"
           "v.style.cssText+=`;position:fixed;top:10px;left:10px;width:744px;z-index:99999;margin:0`")   # 바이저만 화면 왼쪽 위에 고정 (PIP 창 크기와 무관하게 744 px)
    simjs = lambda n: f"const t=document.getElementById('sim-t');t.value={n};t.dispatchEvent(new Event('input'))"
    top = {"ko": "헬멧 바이저 HUD 적용 화면 — EVA 시뮬레이션 (Gale, 산소 450 g, 60분부터 대사량 25% 급증)",
           "en": "Helmet visor HUD — EVA simulation (Gale, 450 g O2, metabolic surge +25% from minute 60)"}[lang]
    k, last = 0, None
    for n in sorted(set(range(0, 218, STEP)) | {109, 218}):
        if n == last:
            continue
        a2 = acts + [(16000, simjs(n)), (20000, pin)]
        if n == 0:
            vx, vy, vw, vh = T.rects("", a2, (1480, 900))["visor"]
        p = T.page(f"v_{lang}_{n:03d}", "", a2, (1480, 900))
        vis = p.crop((int(vx) - 6, int(vy) - 6, int(vx + vw) + 6, int(vy + vh) + 6))
        if lang == "ko":
            bottom = f"{n}분 · " + ("심박이 오르면 산소 소모가 빨라지고 귀환 여유가 줄어듭니다" if n < 100 else
                                    "귀환 경보: 왕복 여유(+20%)를 지키려 돌아섭니다" if n < 130 else "거점으로 돌아오는 중 · 여유를 남기고 도착")
        else:
            bottom = f"min {n} · " + ("heart rate up → O2 use up → return margin shrinks" if n < 100 else
                                      "Turn-back alert: keeps the +20% round-trip margin" if n < 130 else "Walking home · arrives with margin to spare")
        fr = caption_frame(vis, top, bottom, lang)
        if n == 109:
            fr.save(f"{T.OUT}/visor_hud_{lang}_still.png")
        for _ in range(round(SEC_PER_FRAME * FPS)):
            fr.save(f"{fdir}/f{k:05d}.png"); k += 1
        last = n
        print(f"  {lang} min {n}")
    out = f"{T.OUT}/visor_hud_{lang}.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(FPS), "-i", f"{fdir}/f%05d.png",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "22", out], check=True)
    shutil.rmtree(fdir)
    print(f"saved {out} ({k / FPS:.1f} s)")


if __name__ == "__main__":
    os.makedirs(T.OUT, exist_ok=True)
    shutil.copy(T.DEMO, f"{T.WTMP}/demo.html")
    for lang in ("ko", "en"):
        run(lang)
