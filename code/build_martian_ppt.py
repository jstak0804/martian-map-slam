# -*- coding: utf-8 -*-
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# ---------- palette (consistent with earlier CLPS deck) ----------
BG        = RGBColor(0x0B, 0x0E, 0x15)
SURFACE   = RGBColor(0x14, 0x19, 0x26)
SURFACE2  = RGBColor(0x1B, 0x21, 0x30)
INK       = RGBColor(0xE9, 0xEB, 0xF2)
INK_SOFT  = RGBColor(0xA7, 0xAE, 0xC1)
INK_FAINT = RGBColor(0x6D, 0x74, 0x88)
BORDER    = RGBColor(0x28, 0x30, 0x41)
GOLD      = RGBColor(0xE0, 0xAC, 0x53)
TEAL      = RGBColor(0x5C, 0xBC, 0xC3)
TEAL_DIM  = RGBColor(0x1C, 0x3A, 0x3C)
RUST      = RGBColor(0xE0, 0x8A, 0x76)
RUST_DIM  = RGBColor(0x4A, 0x2A, 0x22)
GOLD_DIM  = RGBColor(0x4A, 0x3A, 0x1C)

FONT_KR   = "맑은 고딕"
FONT_MONO = "Consolas"

SW, SH = Inches(13.333), Inches(7.5)

prs = Presentation()
prs.slide_width = SW
prs.slide_height = SH
BLANK = prs.slide_layouts[6]

TOTAL_SLIDES = 18
idx = 0
def next_idx():
    global idx
    idx += 1
    return idx

# ---------- helpers ----------

def add_slide():
    s = prs.slides.add_slide(BLANK)
    bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, SH)
    bg.fill.solid(); bg.fill.fore_color.rgb = BG
    bg.line.fill.background()
    bg.shadow.inherit = False
    s.shapes._spTree.remove(bg._element)
    s.shapes._spTree.insert(2, bg._element)
    return s

def set_font(run, size=18, color=INK, bold=False, font=FONT_KR, italic=False, spacing=None):
    run.font.size = Pt(size)
    run.font.color.rgb = color
    run.font.bold = bold
    run.font.italic = italic
    run.font.name = font
    rPr = run._r.get_or_add_rPr()
    ea = rPr.find('{http://schemas.openxmlformats.org/drawingml/2006/main}ea')
    if ea is None:
        ea = rPr.makeelement('{http://schemas.openxmlformats.org/drawingml/2006/main}ea', {})
        rPr.append(ea)
    ea.set('typeface', font)
    if spacing is not None:
        rPr.set('spc', str(int(spacing * 100)))

def textbox(slide, x, y, w, h, lines, anchor=MSO_ANCHOR.TOP, align=PP_ALIGN.LEFT, wrap=True):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = wrap
    tf.vertical_anchor = anchor
    tf.margin_left = 0; tf.margin_right = 0; tf.margin_top = 0; tf.margin_bottom = 0
    first = True
    for ln in lines:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.alignment = ln.get('align', align)
        p.space_after = Pt(ln.get('space_after', 0))
        p.space_before = Pt(ln.get('space_before', 0))
        runs = ln['runs'] if 'runs' in ln else [ln]
        for r in runs:
            run = p.add_run()
            run.text = r['text']
            set_font(run, size=r.get('size', 18), color=r.get('color', INK),
                     bold=r.get('bold', False), font=r.get('font', FONT_KR),
                     italic=r.get('italic', False), spacing=r.get('spacing'))
    return tb

def rect(slide, x, y, w, h, color, line_color=None, line_w=None, round_=False):
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if round_ else MSO_SHAPE.RECTANGLE
    sp = slide.shapes.add_shape(shape_type, x, y, w, h)
    if round_:
        try: sp.adjustments[0] = 0.06
        except Exception: pass
    if color is None:
        sp.fill.background()
    else:
        sp.fill.solid(); sp.fill.fore_color.rgb = color
    if line_color is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line_color
        sp.line.width = line_w or Pt(0.75)
    sp.shadow.inherit = False
    return sp

def horizon_bar(slide, x, y, w, h=Pt(3)):
    seg = int(w / 3)
    rect(slide, x, y, Emu(seg), h, GOLD)
    rect(slide, x + Emu(seg), y, Emu(seg), h, BORDER)
    rect(slide, x + Emu(seg*2), y, w - Emu(seg*2), h, TEAL)

def eyebrow(slide, x, y, text, color=TEAL, size=12):
    textbox(slide, x, y, Inches(11), Inches(0.3),
            [{'text': text, 'size': size, 'color': color, 'bold': True, 'font': FONT_MONO, 'spacing': 1.5}])

def page_footer(slide, section=""):
    i = next_idx()
    textbox(slide, Inches(0.6), SH - Inches(0.45), Inches(7), Inches(0.3),
            [{'text': section, 'size': 9, 'color': INK_FAINT, 'font': FONT_MONO, 'spacing': 1}])
    textbox(slide, SW - Inches(1.4), SH - Inches(0.45), Inches(0.8), Inches(0.3),
            [{'text': f"{i:02d} / {TOTAL_SLIDES:02d}", 'size': 9, 'color': INK_FAINT, 'font': FONT_MONO, 'align': PP_ALIGN.RIGHT}])

def slide_title(slide, kicker, title, sub=None, num=None, accent=GOLD):
    if num:
        textbox(slide, Inches(0.6), Inches(0.45), Inches(1.2), Inches(0.5),
                [{'text': num, 'size': 20, 'color': accent, 'bold': True, 'font': FONT_MONO}])
    eyebrow(slide, Inches(0.6) if not num else Inches(1.35), Inches(0.55), kicker, color=accent)
    textbox(slide, Inches(0.6), Inches(0.85), Inches(12.1), Inches(0.9),
            [{'text': title, 'size': 28, 'color': INK, 'bold': True}])
    y = Inches(1.5)
    if sub:
        textbox(slide, Inches(0.6), y, Inches(12.1), Inches(0.5),
                [{'text': sub, 'size': 13.5, 'color': INK_SOFT}])
        y = Inches(1.9)
    horizon_bar(slide, Inches(0.6), y, Inches(12.13))
    return y + Inches(0.25)

def code_block(slide, x, y, w, h, filename, lines, font_size=12.5, space_after=3):
    rect(slide, x, y, w, h, SURFACE2, line_color=BORDER, line_w=Pt(0.75), round_=True)
    rect(slide, x, y, w, Inches(0.38), SURFACE, round_=False)
    textbox(slide, x + Inches(0.2), y, w - Inches(0.4), Inches(0.38),
            [{'text': filename, 'size': 10.5, 'color': INK_FAINT, 'font': FONT_MONO}], anchor=MSO_ANCHOR.MIDDLE)
    body = []
    for ln in lines:
        color = INK_FAINT if ln.strip().startswith('#') else INK
        italic = ln.strip().startswith('#')
        body.append({'text': ln if ln else ' ', 'size': font_size, 'color': color, 'font': FONT_MONO,
                      'italic': italic, 'space_after': space_after})
    textbox(slide, x + Inches(0.25), y + Inches(0.5), w - Inches(0.5), h - Inches(0.65), body, wrap=False)
    # rough overflow guard (printed at build time, not rendered)
    avail_pt = (h - Inches(0.65)) / 12700  # EMU -> pt
    used_pt = len(lines) * (font_size * 1.22 + space_after)
    if used_pt > avail_pt:
        print(f"  [WARN] code_block '{filename}' may overflow: used={used_pt:.0f}pt avail={avail_pt:.0f}pt")

def bullet_list(slide, x, y, w, h, items, accent=GOLD, size=13.5, gap=9):
    lines = []
    for it in items:
        if isinstance(it, tuple):
            label, desc = it
            lines.append({'runs': [
                {'text': '›  ', 'size': size, 'color': accent, 'bold': True, 'font': FONT_MONO},
                {'text': label + '  ', 'size': size, 'color': INK, 'bold': True},
                {'text': desc, 'size': size - 1, 'color': INK_SOFT},
            ], 'space_after': gap})
        else:
            lines.append({'runs': [
                {'text': '›  ', 'size': size, 'color': accent, 'bold': True, 'font': FONT_MONO},
                {'text': it, 'size': size, 'color': INK_SOFT},
            ], 'space_after': gap})
    textbox(slide, x, y, w, h, lines)

def simple_table(slide, x, y, w, headers, rows, col_w=None, row_h=Inches(0.55), header_color=GOLD):
    n = len(headers)
    col_w = col_w or [Emu(int(w / n))] * n
    cx = x
    for i, htext in enumerate(headers):
        rect(slide, cx, y, col_w[i], row_h, SURFACE2, line_color=BORDER, line_w=Pt(0.5))
        textbox(slide, cx + Inches(0.12), y, col_w[i] - Inches(0.24), row_h,
                [{'text': htext, 'size': 12, 'color': header_color, 'bold': True}], anchor=MSO_ANCHOR.MIDDLE)
        cx = Emu(cx + col_w[i])
    ry = Emu(y + row_h)
    for r, row in enumerate(rows):
        cx = x
        for i, val in enumerate(row):
            bgc = SURFACE if r % 2 == 0 else BG
            rect(slide, cx, ry, col_w[i], row_h, bgc, line_color=BORDER, line_w=Pt(0.5))
            fcolor = INK if i == 0 else INK_SOFT
            bold = i == 0
            textbox(slide, cx + Inches(0.12), ry, col_w[i] - Inches(0.24), row_h,
                    [{'text': val, 'size': 11.5, 'color': fcolor, 'bold': bold, 'font': FONT_MONO if i > 0 else FONT_KR}],
                    anchor=MSO_ANCHOR.MIDDLE)
            cx = Emu(cx + col_w[i])
        ry = Emu(ry + row_h)
    return ry

def stat_card(slide, x, y, w, h, label, value, color=TEAL, desc=None):
    rect(slide, x, y, w, h, SURFACE2, line_color=BORDER, line_w=Pt(0.75), round_=True)
    rect(slide, x, y, w, Pt(4), color)
    textbox(slide, x + Inches(0.18), y + Inches(0.2), w - Inches(0.36), Inches(0.35),
            [{'text': label, 'size': 11, 'color': INK_FAINT, 'font': FONT_MONO, 'spacing': 0.5}])
    textbox(slide, x + Inches(0.18), y + Inches(0.55), w - Inches(0.36), Inches(0.6),
            [{'text': value, 'size': 26, 'color': color, 'bold': True, 'font': FONT_MONO}])
    if desc:
        textbox(slide, x + Inches(0.18), y + Inches(1.15), w - Inches(0.36), Inches(0.5),
                [{'text': desc, 'size': 10.5, 'color': INK_SOFT}])

# ============================================================
# 1. TITLE
# ============================================================
s = add_slide()
rect(s, Inches(0), Inches(0), Inches(0.12), SH, TEAL)
eyebrow(s, Inches(0.9), Inches(1.6), "NASA SPACE APPS CHALLENGE 2026 · 챌린지 11", color=GOLD, size=13)
textbox(s, Inches(0.9), Inches(2.05), Inches(11.5), Inches(0.6),
        [{'text': "Interplanetary Survival Guide: Martian Map", 'size': 20, 'color': INK_FAINT, 'font': FONT_MONO}])
textbox(s, Inches(0.85), Inches(2.55), Inches(11.6), Inches(1.6),
        [{'text': "기술 검증 리포트", 'size': 44, 'color': INK, 'bold': True}])
textbox(s, Inches(0.9), Inches(3.45), Inches(11.4), Inches(0.6),
        [{'text': "SLAM 매핑 실험 · 위험도 히트맵 · MMGIS 통합 설계 · 코드 정리", 'size': 18, 'color': INK_SOFT}])
horizon_bar(s, Inches(0.9), Inches(4.25), Inches(6.2))
textbox(s, Inches(0.9), Inches(4.55), Inches(10.5), Inches(0.4),
        [{'text': "Devon Island Rover Navigation Dataset(UTIAS) 실데이터 기반 — 스틸컷 vs 영상 실험, NASA-AMMOS/MMGIS 대응 설계",
          'size': 12.5, 'color': INK_FAINT}])
page_footer(s)

# ============================================================
# 2. AGENDA
# ============================================================
s = add_slide()
y = slide_title(s, "AGENDA", "오늘 다룰 내용", num="◐")
agenda = [
    ("01-02", "챌린지 재확인 · 로봇청소기형 매핑 컨셉"),
    ("03-04", "실제 데이터 — Devon Island 데이터셋 · 실험 설계"),
    ("05-07", "결과 — Stills vs Video, 원인 분석, 다음 단계"),
    ("08-10", "코드 구조 · 핵심 스니펫"),
    ("11-13", "MMGIS 통합 설계 — 대응표 · Sightline · Isochrone"),
    ("14-15", "더스트스톰 · 방사선 레이어 적용안"),
    ("16-17", "로드맵 · 우선순위"),
]
rows_y = y + Inches(0.1)
for tag, desc in agenda:
    rect(s, Inches(0.6), rows_y, Inches(1.6), Inches(0.6), SURFACE2, line_color=BORDER, round_=True)
    textbox(s, Inches(0.6), rows_y, Inches(1.6), Inches(0.6),
            [{'text': tag, 'size': 14, 'color': GOLD, 'bold': True, 'font': FONT_MONO}], anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.CENTER)
    textbox(s, Inches(2.4), rows_y, Inches(10), Inches(0.6),
            [{'text': desc, 'size': 15, 'color': INK}], anchor=MSO_ANCHOR.MIDDLE)
    rows_y = Emu(rows_y + Inches(0.72))
page_footer(s, "개요")

# ============================================================
# 3. CHALLENGE RECAP
# ============================================================
s = add_slide()
y = slide_title(s, "RECAP · 01", "왜 이 전환이 말이 되는가", num="①")
rect(s, Inches(0.6), y, Inches(12.13), Inches(1.5), SURFACE, line_color=GOLD, line_w=Pt(1), round_=True)
textbox(s, Inches(0.9), y + Inches(0.2), Inches(11.5), Inches(1.1),
        [{'runs': [{'text': "원문 인용  ", 'size': 11, 'color': GOLD, 'bold': True, 'font': FONT_MONO},
                   {'text': "\"기존 내비게이션 모델은 경로 탐색을 단순 최단거리 문제(유클리드 거리 또는 다익스트라 최단 경로)로 축소시킨다.\"",
                    'size': 15, 'color': INK}]}])
y2 = y + Inches(1.8)
textbox(s, Inches(0.6), y2, Inches(12), Inches(0.4),
        [{'text': "CLPS 작업에서 이미 만든 CV 파이프라인(AI4Mars 위험도 히트맵)이 이 챌린지의 핵심 서브시스템과 동일합니다.", 'size': 14, 'color': INK_SOFT}])
page_footer(s, "챌린지 재확인")

# ============================================================
# 4. CORE CONCEPT — pipeline
# ============================================================
s = add_slide()
y = slide_title(s, "CONCEPT · 02", "로봇청소기형 점진적 매핑", "1인칭 주행 영상 → Visual SLAM → 누적 지도", num="②", accent=TEAL)
pipeline = [
    ("1", "프레임 특징 추출", "연속 영상에서 ORB 특징점 추출, 인접 프레임 대응점 탐색"),
    ("2", "상대 이동(포즈) 추정", "대응점으로 카메라가 얼마나/어느 방향으로 움직였는지 추정"),
    ("3", "지역 지형 재구성", "스테레오 깊이 또는 pseudo-relief로 국소 3D 형상 복원"),
    ("4", "전역 좌표계로 정합", "추정 포즈를 이용해 공유 지도 좌표계에 이어붙임"),
    ("5", "누적 지도 갱신", "겹치는 영역은 평균/최신값으로 병합"),
]
ry = y + Inches(0.1)
for n, title, desc in pipeline:
    rect(s, Inches(0.6), ry, Inches(0.6), Inches(0.85), TEAL_DIM, round_=True)
    textbox(s, Inches(0.6), ry, Inches(0.6), Inches(0.85),
            [{'text': n, 'size': 20, 'color': TEAL, 'bold': True, 'font': FONT_MONO}], anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.CENTER)
    textbox(s, Inches(1.45), ry + Inches(0.05), Inches(10.5), Inches(0.35),
            [{'text': title, 'size': 15.5, 'color': INK, 'bold': True}])
    textbox(s, Inches(1.45), ry + Inches(0.42), Inches(10.8), Inches(0.4),
            [{'text': desc, 'size': 12, 'color': INK_SOFT}])
    ry = Emu(ry + Inches(0.95))
page_footer(s, "핵심 컨셉")

# ============================================================
# 5. DATASET
# ============================================================
s = add_slide()
y = slide_title(s, "DATA · 03", "Devon Island Rover Navigation Dataset", "UTIAS · Mars/Moon 아날로그 지형, Nunavut 75°N", num="③", accent=TEAL)
cards = [
    ("전체 경로", "10.1 km", "루프형(출발=도착 근접)", GOLD),
    ("프레임 수", "49,410장", "스테레오 쌍, ~0.2m 간격", TEAL),
    ("고도 범위", "0 ~ 59 m", "DGPS 실측 고도 프로파일", RUST),
    ("캘리브레이션", "baseline 0.24m", "focal 387.6px (512×384 rectified)", GOLD),
]
cx = Inches(0.6)
cw = Inches(2.93)
for label, val, desc, color in cards:
    stat_card(s, cx, y, cw - Inches(0.15), Inches(1.7), label, val, color, desc)
    cx = Emu(cx + cw)
y2 = y + Inches(2.0)
textbox(s, Inches(0.6), y2, Inches(12), Inches(0.4),
        [{'text': "실제 Mars/Moon 아날로그 현장에서 수집된 스테레오 영상 + DGPS 실측 위치 + 태양센서/경사계 — SLAM 검증에 이상적인 공개 데이터셋", 'size': 13, 'color': INK_SOFT}])
page_footer(s, "데이터셋")

# ============================================================
# 6. EXPERIMENT DESIGN
# ============================================================
s = add_slide()
y = slide_title(s, "EXPERIMENT · 04", "실험 설계 — Stills vs Video", num="④", accent=TEAL)
simple_table(
    s, Inches(0.6), y, Inches(12.13),
    ["", "실험 A · Stills", "실험 B · Video"],
    [
        ["소스", "원본 PGM 스테레오 쌍 (무압축)", "sequence-22.mpg (MPEG, 1024x384)"],
        ["프레임 수", "25 (약 7m 구간)", "432 (약 124m, 전체 s22 구간)"],
        ["취득 방식", "zip 아카이브 직접 추출", "cv2.VideoCapture 디코딩"],
        ["검증", "gps-topocentric.txt 대조", "동일 + 프레임 번인 인덱스로 정합 확인"],
    ],
    col_w=[Inches(2.0), Inches(5.06), Inches(5.07)],
)
page_footer(s, "실험 설계")

# ============================================================
# 7. RESULTS
# ============================================================
s = add_slide()
y = slide_title(s, "RESULT · 05", "결과 — 거리 추정 정확도", num="⑤", accent=RUST)
cx = Inches(0.6)
cw = Inches(3.9)
stat_card(s, cx, y, cw - Inches(0.2), Inches(1.8), "실험 A · 25프레임", "2.3%", TEAL, "실측 7.03m vs 추정 6.87m")
stat_card(s, Emu(cx + cw), y, cw - Inches(0.2), Inches(1.8), "실험 B · 432프레임", "30.9%", RUST, "실측 123.55m vs 추정 85.43m")
stat_card(s, Emu(cx + cw*2), y, cw - Inches(0.2), Inches(1.8), "스텝 성공률", "99.3%", GOLD, "431스텝 중 428 성공 (fail_pnp: 3)")
y2 = y + Inches(2.1)
rect(s, Inches(0.6), y2, Inches(12.13), Inches(1.5), RUST_DIM, line_color=RUST, line_w=Pt(1), round_=True)
textbox(s, Inches(0.9), y2 + Inches(0.2), Inches(11.5), Inches(1.1),
        [{'runs': [{'text': "핵심 발견  ", 'size': 12, 'color': RUST, 'bold': True, 'font': FONT_MONO}]},
         {'runs': [{'text': "매칭 실패가 아니라, 거의 모든 스텝(99.3%)이 '성공' 판정을 받으면서도 평균적으로 실제보다 살짝 작은 이동량을 추정 — 그 작은 편향이 428번 누적되어 31%까지 벌어짐.",
                    'size': 14, 'color': INK}], 'space_before': 6}])
page_footer(s, "결과")

# ============================================================
# 8. ROOT CAUSE / NEXT STEP
# ============================================================
s = add_slide()
y = slide_title(s, "ANALYSIS · 06", "원인 분석과 다음 단계", num="⑥", accent=RUST)
textbox(s, Inches(0.6), y, Inches(12), Inches(0.4),
        [{'text': "짧은 구간(25프레임)에서는 거의 안 보이던 문제가, 긴 구간(432프레임)으로 늘리자 선명하게 드러났습니다.", 'size': 14, 'color': INK_SOFT}])
bullet_list(s, Inches(0.6), y + Inches(0.6), Inches(12), Inches(2.2), [
    ("교과서적 VO 한계", "루프 클로저·번들 조정 없는 순수 프레임간 Visual Odometry는 누적 드리프트가 필연적"),
    ("좋은 소식 — 닫힌 루프", "전체 10km 경로가 출발=도착인 루프 — 드리프트 보정에 이상적인 조건"),
    ("다음 단계", "포즈 그래프 최적화(pose graph optimization)로 누적 오차를 경로 전체에 재분배"),
    ("회전 보정", "sun-sensor-sampled.txt + SPICE 태양 위치 계산으로 절대 방위 보정 (CLPS 코드 재사용)"),
], accent=RUST, size=15, gap=14)
page_footer(s, "원인 분석")

# ============================================================
# 9. CODE ARCHITECTURE
# ============================================================
s = add_slide()
y = slide_title(s, "CODE · 07", "devon_pipeline.py — 구조", "stills/video 공용 파이프라인, 273줄", num="⑦", accent=TEAL)
sections = [
    ("1. 프레임 로딩", "load_frames_from_zip() / load_frames_from_video()", "두 입력 소스를 동일한 (lefts, rights) 형태로 반환"),
    ("2. 스테레오 깊이", "compute_disparity() / disparity_to_depth()", "StereoSGBM + 실제 캘리브레이션으로 미터 단위 깊이"),
    ("3. Visual Odometry", "visual_odometry()", "ORB 매칭 + solvePnPRansac, 스텝별 성공/실패 집계"),
    ("4. Ground Truth", "load_gt_segment()", "gps-topocentric.txt에서 해당 구간 실측 위치 로드"),
    ("5. 실행/시각화", "run_experiment() / plot_comparison()", "실험 실행, 통계 산출, 비교 플롯 생성"),
]
ry = y + Inches(0.1)
for title, func, desc in sections:
    rect(s, Inches(0.6), ry, Inches(12.13), Inches(0.78), SURFACE, line_color=BORDER, round_=True)
    textbox(s, Inches(0.8), ry + Inches(0.08), Inches(2.6), Inches(0.3),
            [{'text': title, 'size': 12.5, 'color': GOLD, 'bold': True}])
    textbox(s, Inches(0.8), ry + Inches(0.4), Inches(4.3), Inches(0.32),
            [{'text': func, 'size': 11.5, 'color': TEAL, 'font': FONT_MONO}])
    textbox(s, Inches(5.3), ry, Inches(7.2), Inches(0.78),
            [{'text': desc, 'size': 12, 'color': INK_SOFT}], anchor=MSO_ANCHOR.MIDDLE)
    ry = Emu(ry + Inches(0.88))
page_footer(s, "코드 구조")

# ============================================================
# 10. CODE SNIPPET — video loader
# ============================================================
s = add_slide()
y = slide_title(s, "CODE · 08", "핵심 스니펫 — 비디오 프레임 로더", num="⑧", accent=TEAL)
code_block(s, Inches(0.6), y + Inches(0.1), Inches(12.13), Inches(5.1), "load_frames_from_video()", [
    "# 압축 비디오(좌우 1024x384 합성) -> zip 로더와 동일한 형태로 반환",
    "def load_frames_from_video(start_idx, n_frames,",
    "        video_name='sequence-22.mpg', video_start_idx=48978):",
    "    cap = cv2.VideoCapture(f'{SCRATCH}/{video_name}')",
    "    cap.set(cv2.CAP_PROP_POS_FRAMES, start_idx - video_start_idx)",
    "    lefts, rights = [], []",
    "    for _ in range(n_frames):",
    "        ok, frame = cap.read()",
    "        if not ok:",
    "            break",
    "        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)",
    "        half = gray.shape[1] // 2",
    "        lefts.append(gray[:, :half])",
    "        rights.append(gray[:, half:])",
    "    cap.release()",
    "    return lefts, rights",
    "# 검증: 프레임 번인 인덱스가 start_idx+frame_number와 일치 확인",
], font_size=12.5, space_after=2)
page_footer(s, "코드")

# ============================================================
# 11. CODE SNIPPET — VO diagnostics
# ============================================================
s = add_slide()
y = slide_title(s, "CODE · 09", "핵심 스니펫 — VO 진단 계측", num="⑨", accent=TEAL)
code_block(s, Inches(0.6), y + Inches(0.1), Inches(12.13), Inches(5.1), "visual_odometry() — stats 집계", [
    "def visual_odometry(lefts, depths, verbose=False):",
    "    stats = {'total': len(lefts)-1, 'ok': 0,",
    "             'fail_features': 0, 'fail_depth_pts': 0, 'fail_pnp': 0}",
    "    for t in range(len(lefts) - 1):",
    "        # ORB 매칭 -> 3D 역투영 -> solvePnPRansac 실스케일 포즈 추정",
    "        ...",
    "        if not ok or inliers is None or len(inliers) < 6:",
    "            poses.append(poses[-1])",
    "            stats['fail_pnp'] += 1",
    "            continue",
    "        ...",
    "        stats['ok'] += 1",
    "    return np.array(poses), stats",
    "# 실측(432프레임 비디오): total=431, ok=428, fail_pnp=3",
    "# -> 실패가 아니라 누적 편향이 원인임을 직접 증명",
], font_size=12.5, space_after=2)
page_footer(s, "코드")

# ============================================================
# 12. MMGIS discovery
# ============================================================
s = add_slide()
y = slide_title(s, "MMGIS · 10", "우리는 MMGIS를 절반쯤 재발명하고 있었다", "NASA-AMMOS/MMGIS — MSL·M2020·Lunar VIPER가 실사용하는 오픈소스 GIS", num="⑩", accent=GOLD)
simple_table(
    s, Inches(0.6), y, Inches(12.13),
    ["우리가 만든 것", "MMGIS 대응 기능", "재사용 여부"],
    [
        ["azimuth_elevation() (SPICE)", "Sightline Tool", "그대로 재사용"],
        ["extract_skyline() (지평선)", "Sightmap 알고리즘", "그대로 재사용"],
        ["DTE 통신 가능/단절 구간", "Visibility Timeline", "그대로 재사용"],
        ["\"최단거리 넘어서\" 비용함수", "Isochrone Tool (Dijkstra)", "데이터만 공급"],
        ["AI4Mars 위험도 히트맵", "Data Layer (colorize)", "데이터만 공급"],
        ["풍향·풍속 레이어", "Velocity Layer", "그대로 재사용"],
    ],
    col_w=[Inches(4.2), Inches(4.2), Inches(3.73)],
    row_h=Inches(0.48),
)
page_footer(s, "MMGIS 통합")

# ============================================================
# 13. MMGIS — Sightline detail
# ============================================================
s = add_slide()
y = slide_title(s, "MMGIS · 11", "Sightline — 사실상 CLPS 챌린지 그 자체", num="⑪", accent=GOLD)
code_block(s, Inches(0.6), y + Inches(0.1), Inches(12.13), Inches(2.3), "MMGIS 공식 설정 예시", [
    '"sources": [',
    '  { "name": "The Sun", "value": "SUN" }   # CLPS가 계산하던 그 태양',
    '],',
    '"observers": [ { "name": "MSL", "value": "MSL" } ]',
    '# obsRefFrame 기본값: IAU_MOON (달 임무가 기본 가정)',
], font_size=14)
bullet_list(s, Inches(0.6), y + Inches(2.65), Inches(12), Inches(1.8), [
    "\"Include Sun + Earth\" 옵션 하나로 CLPS의 \"태양·지구 동시 가시성\" 요구사항 충족",
    "Horizon Profile = 우리 extract_skyline()과 동일 원리, bilinear 보간+곡률보정까지 완비",
    "Composite 모드 = 우리 DTE 통신창 계산과 동일한 누적 가시성 히트맵",
], accent=GOLD, size=14, gap=10)
page_footer(s, "MMGIS 통합")

# ============================================================
# 14. MMGIS — Isochrone detail
# ============================================================
s = add_slide()
y = slide_title(s, "MMGIS · 12", "Isochrone — 경로탐색을 이미 풀어놓은 엔진", num="⑫", accent=GOLD)
code_block(s, Inches(0.6), y + Inches(0.1), Inches(12.13), Inches(2.3), "Isochrone 설정 예시", [
    '"data": {',
    '  "DEM":  [ { "name": "지형고도", "tileurl": "..." } ],',
    '  "cost": [ { "name": "우리CV위험도", "tileurl": "..." } ]',
    '},',
    '"models": ["Traverse Time", "Isodistance"]',
], font_size=14)
bullet_list(s, Inches(0.6), y + Inches(2.65), Inches(12), Inches(1.8), [
    "타일 기반 Dijkstra가 브라우저 안에서 이미 동작 (8방향+나이트무브 16개 이웃)",
    "우리 risk_score를 \"cost\" 데이터 소스 하나로 공급하면 바로 연결됨",
    "science_value(제제로 크레이터 등)는 음수 비용으로 — \"가치 있는 곳으로 끌어당기는\" 경로 탐색",
], accent=GOLD, size=14, gap=10)
page_footer(s, "MMGIS 통합")

# ============================================================
# 15. Dust storm layer
# ============================================================
s = add_slide()
y = slide_title(s, "LAYER · 13", "더스트스톰 레이어 적용 방법", num="⑬", accent=RUST)
bullet_list(s, Inches(0.6), y + Inches(0.1), Inches(12), Inches(2.0), [
    ("계절 기준선", "Mars Climate Database의 더스트 광학두께(τ)를 태양경도(Ls)별로 조회"),
    ("실시간 보정", "Navcam 하늘 밝기 감쇠로 τ 직접 역산 (2018 MY34 폭풍 때 실제 사용된 기법)"),
    ("배수 반영", "발전량 = P0×illumination×(1-τ), CV 신뢰도·이동성 위험에도 가중"),
], accent=RUST, size=14.5, gap=12)
y2 = y + Inches(2.3)
rows = [
    ("2018-05-30", "MY34 전지구 모래폭풍 시작"),
    ("2018-06-10", "Opportunity 마지막 교신"),
    ("2019-02-13", "임무 공식 종료 선언"),
]
ry = y2
for date, desc in rows:
    rect(s, Inches(0.6), ry, Inches(1.8), Inches(0.55), SURFACE2, line_color=RUST, line_w=Pt(0.75), round_=True)
    textbox(s, Inches(0.6), ry, Inches(1.8), Inches(0.55),
            [{'text': date, 'size': 12.5, 'color': RUST, 'bold': True, 'font': FONT_MONO}], anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.CENTER)
    textbox(s, Inches(2.6), ry, Inches(9.8), Inches(0.55),
            [{'text': desc, 'size': 13.5, 'color': INK}], anchor=MSO_ANCHOR.MIDDLE)
    ry = Emu(ry + Inches(0.63))
page_footer(s, "환경 레이어")

# ============================================================
# 16. Radiation layer
# ============================================================
s = add_slide()
y = slide_title(s, "LAYER · 14", "방사선 레이어 적용 방법", num="⑭", accent=RUST)
rect(s, Inches(0.6), y, Inches(12.13), Inches(1.1), SURFACE, line_color=RUST, line_w=Pt(1), round_=True)
textbox(s, Inches(0.9), y + Inches(0.2), Inches(11.5), Inches(0.7),
        [{'runs': [{'text': "실측 기준  ", 'size': 11, 'color': RUST, 'bold': True, 'font': FONT_MONO},
                   {'text': "MSL/RAD, 표면 GCR 흡수선량 약 0.21 mGy/day (PDS 공개)", 'size': 14.5, 'color': INK}]}])
bullet_list(s, Inches(0.6), y + Inches(1.4), Inches(12), Inches(2.2), [
    ("핵심 설계 — 누적 예산", "\"칸당 위험\"이 아니라 dose_rate × 체류시간 → 자연히 빠른 경로를 우대"),
    ("돌발 이벤트", "SEP(태양고에너지입자) 스파이크 — 실시간 우주기상 경보와 연동해 임시 고위험 플래그"),
    ("지형 차폐 보너스", "CV 지형분류(절벽/그늘)로 방사선 비용 할인 — CV·방사선 레이어 교차점"),
    ("건강 모니터링 연동", "2026 챌린지 전체 가이드 \"06\" 건강 모니터링 챌린지로 누적 노출값 전달"),
], accent=RUST, size=14, gap=11)
page_footer(s, "환경 레이어")

# ============================================================
# 17. ROADMAP
# ============================================================
s = add_slide()
y = slide_title(s, "ROADMAP · 15", "우선순위", num="⑮", accent=TEAL)
simple_table(
    s, Inches(0.6), y, Inches(12.13),
    ["단계", "내용", "재사용도"],
    [
        ["1순위", "AI4Mars 위험도 파이프라인 — 단일 프레임에서 경로 전체로 확장", "매우 높음"],
        ["2순위", "포즈 그래프 최적화로 VO 드리프트 보정 (루프 클로저 활용)", "신규"],
        ["3순위", "MMGIS 로컬 배포 — Sightline/Isochrone 교차검증", "데이터만 공급"],
        ["4순위", "REMS JSON API로 기온·풍향 레이어 연결", "중간"],
        ["여유 시", "더스트스톰·방사선 레이어, Isochrone 커스텀 비용 모델", "신규"],
    ],
    col_w=[Inches(1.8), Inches(7.83), Inches(2.5)],
)
page_footer(s, "로드맵")

# ============================================================
# 18. CLOSING
# ============================================================
s = add_slide()
rect(s, Inches(0), Inches(0), Inches(0.12), SH, GOLD)
eyebrow(s, Inches(0.9), Inches(1.0), "CLOSING", color=TEAL)
textbox(s, Inches(0.85), Inches(1.35), Inches(11), Inches(0.9),
        [{'text': "Thank you", 'size': 38, 'color': INK, 'bold': True}])
textbox(s, Inches(0.9), Inches(2.15), Inches(10.8), Inches(0.5),
        [{'text': "Interplanetary Survival Guide: Martian Map — 기술 검증 리포트", 'size': 14, 'color': INK_SOFT}])
horizon_bar(s, Inches(0.9), Inches(2.75), Inches(6.2))
textbox(s, Inches(0.9), Inches(3.15), Inches(11), Inches(0.35),
        [{'text': "참고 자료", 'size': 13, 'color': INK, 'bold': True}])
srcs = [
    "asrl.utias.utoronto.ca/datasets/devon-island-rover-navigation",
    "github.com/NASA-AMMOS/MMGIS",
    "pds-ppi.igpp.ucla.edu — MSL/RAD",
    "www-mars.lmd.jussieu.fr — Mars Climate Database",
]
lines = [{'runs':[{'text':'· ', 'size':11.5, 'color':TEAL},{'text': t, 'size':11.5, 'color':INK_FAINT, 'font': FONT_MONO}], 'space_after':6} for t in srcs]
textbox(s, Inches(0.9), Inches(3.55), Inches(11.2), Inches(1.8), lines)
page_footer(s)

prs.save('../exports/Martian_Map_기술검증_리포트.pptx')
print("SAVED", len(prs.slides._sldIdLst), "slides")
