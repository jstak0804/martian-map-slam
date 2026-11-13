# -*- coding: utf-8 -*-
"""
Phase 2 결과보고회 — Martian_Map_결과보고회.pptx(33슬라이드, Phase 1) 이후 진행한 추가 작업 전용 덱.

Phase 1 내용은 요약만 하고(자세한 내용은 기존 Phase 1 덱 참고), 이후 진행한
ConeQuest 2지역 합산 재학습 + 유인 미션 확장 위험도부터 이어서 작성한다.

팔레트/헬퍼 함수는 code/build_martian_ppt.py(Phase 1 "기술검증 리포트" 덱 생성 스크립트)와
동일하게 맞춰 시각적 일관성을 유지한다 — 원본 파일은 수정하지 않고 필요한 블록만 복제했다.
"""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# ---------- palette (Phase 1 덱과 동일) ----------
BG        = RGBColor(0x0B, 0x0E, 0x15)
SURFACE   = RGBColor(0x14, 0x19, 0x26)
SURFACE2  = RGBColor(0x1B, 0x21, 0x30)
INK       = RGBColor(0xE9, 0xEB, 0xF2)
INK_SOFT  = RGBColor(0xA7, 0xAE, 0xC1)
INK_FAINT = RGBColor(0x6D, 0x74, 0x88)
BORDER    = RGBColor(0x28, 0x30, 0x41)
GOLD      = RGBColor(0xE0, 0xAC, 0x53)
TEAL      = RGBColor(0x5C, 0xBC, 0xC3)
RUST      = RGBColor(0xE0, 0x8A, 0x76)

FONT_KR   = "맑은 고딕"
FONT_MONO = "Consolas"

SW, SH = Inches(13.333), Inches(7.5)

prs = Presentation()
prs.slide_width = SW
prs.slide_height = SH
BLANK = prs.slide_layouts[6]

TOTAL_SLIDES = 16
idx = 0


def next_idx():
    global idx
    idx += 1
    return idx


# ---------- helpers (build_martian_ppt.py와 동일) ----------

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
    rect(slide, x + Emu(seg * 2), y, w - Emu(seg * 2), h, TEAL)


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
            [{'text': value, 'size': 24, 'color': color, 'bold': True, 'font': FONT_MONO}])
    if desc:
        textbox(slide, x + Inches(0.18), y + Inches(1.15), w - Inches(0.36), Inches(0.6),
                [{'text': desc, 'size': 10, 'color': INK_SOFT}])


def section_divider(num, kicker, title, sub):
    s = add_slide()
    rect(s, Inches(0), Inches(0), Inches(0.12), SH, TEAL)
    textbox(s, Inches(0.9), Inches(2.6), Inches(2), Inches(1),
            [{'text': num, 'size': 54, 'color': GOLD, 'bold': True, 'font': FONT_MONO}])
    eyebrow(s, Inches(0.9), Inches(3.55), kicker, color=TEAL, size=13)
    textbox(s, Inches(0.9), Inches(3.9), Inches(11), Inches(1),
            [{'text': title, 'size': 34, 'color': INK, 'bold': True}])
    textbox(s, Inches(0.9), Inches(4.65), Inches(10.5), Inches(0.6),
            [{'text': sub, 'size': 15, 'color': INK_SOFT}])
    page_footer(s, kicker)
    return s


# ============================================================
# 1. TITLE
# ============================================================
s = add_slide()
rect(s, Inches(0), Inches(0), Inches(0.12), SH, GOLD)
eyebrow(s, Inches(0.9), Inches(1.6), "MARTIAN MAP · PHASE 2", color=GOLD, size=13)
textbox(s, Inches(0.9), Inches(2.05), Inches(11.5), Inches(0.6),
        [{'text': "Phase 1 결과보고회(33슬라이드) 이후 추가 작업", 'size': 18, 'color': INK_FAINT, 'font': FONT_MONO}])
textbox(s, Inches(0.85), Inches(2.55), Inches(11.6), Inches(1.3),
        [{'text': "확장 실험 & 유인 미션 컨셉", 'size': 42, 'color': INK, 'bold': True}])
textbox(s, Inches(0.9), Inches(3.4), Inches(11.4), Inches(0.6),
        [{'text': "ConeQuest 2지역 합산 재학습 · 유인 미션 확장 위험도(온도·방사선) · 다음 단계 컨셉", 'size': 16, 'color': INK_SOFT}])
horizon_bar(s, Inches(0.9), Inches(4.15), Inches(6.2))
textbox(s, Inches(0.9), Inches(4.45), Inches(10.5), Inches(0.4),
        [{'text': "Phase 1 전체 디테일은 Martian_Map_결과보고회.pptx 참고 — 이 덱은 그 이후 내용만 다룬다", 'size': 12.5, 'color': INK_FAINT}])
textbox(s, Inches(0.9), Inches(6.9), Inches(4), Inches(0.3),
        [{'text': "2026-10-18", 'size': 11, 'color': INK_FAINT, 'font': FONT_MONO}])
page_footer(s)

# ============================================================
# 2. AGENDA
# ============================================================
s = add_slide()
y = slide_title(s, "AGENDA", "이 덱에서 다룰 내용", num="◐")
agenda = [
    ("00", "Phase 1 요약 — 핵심 수치 · 셀프 오디트 리캡"),
    ("01", "ConeQuest 2지역 합산 재학습 — 정직한 음의 결과"),
    ("02", "유인 미션 확장 위험도 — 온도 · 방사선 결합 공식"),
    ("03", "유인 미션 컨셉 확장 — 다음 단계 아이디어"),
    ("04", "다음 단계"),
]
rows_y = y + Inches(0.15)
for tag, desc in agenda:
    rect(s, Inches(0.6), rows_y, Inches(1.3), Inches(0.65), SURFACE2, line_color=BORDER, round_=True)
    textbox(s, Inches(0.6), rows_y, Inches(1.3), Inches(0.65),
            [{'text': tag, 'size': 16, 'color': GOLD, 'bold': True, 'font': FONT_MONO}], anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.CENTER)
    textbox(s, Inches(2.1), rows_y, Inches(10.3), Inches(0.65),
            [{'text': desc, 'size': 16, 'color': INK}], anchor=MSO_ANCHOR.MIDDLE)
    rows_y = Emu(rows_y + Inches(0.82))
page_footer(s, "개요")

# ============================================================
# 3. 용어 설명
# ============================================================
s = add_slide()
y = slide_title(s, "GLOSSARY", "이 덱에서 쓰는 용어", sub="처음 보면 낯설 수 있는 약어·전문용어만 추려 정리", num="◑")
glossary = [
    ("SPE", "태양이 고에너지 입자를 방출하는 사건(Solar Particle Event) — 발생 시 방사선량이 급증 (이 프로젝트는 평시 대비 x2.9로 가정)"),
    ("SLAM", "로봇이 자기 위치를 추정하면서 동시에 주변 지도를 만드는 기법(Simultaneous Localization and Mapping)"),
    ("VO / 오도메트리", "카메라 영상만으로 이동거리·방향을 추정하는 방법(Visual Odometry) — 누적 오차(드리프트)가 쌓인다"),
    ("Oracle 맵", "위치추정 오차가 전혀 없다고 가정한 이상적인 비교 기준 지도 — 실제 로버는 이 정보를 가질 수 없다"),
    ("EVA", "우주복을 입고 기지·로버 밖에서 수행하는 선외활동(Extravehicular Activity, 예: 걷기)"),
    ("A* (에이스타)", "목적지까지 최소비용 경로를 찾는 경로탐색 알고리즘 — 직선거리 등 휴리스틱으로 탐색을 가속한다"),
    ("IoU", "예측 영역과 정답 영역이 얼마나 겹치는지 0~1로 나타내는 정확도 지표(Intersection over Union)"),
    ("mSv/day", "방사선 피폭선량 단위(밀리시버트/일) — 하루 동안 사람이 흡수하는 방사선량"),
]
half = len(glossary) // 2
bullet_list(s, Inches(0.6), y + Inches(0.1), Inches(5.9), Inches(4.5), glossary[:half], size=13, gap=16)
bullet_list(s, Inches(6.75), y + Inches(0.1), Inches(5.9), Inches(4.5), glossary[half:], size=13, gap=16)
page_footer(s, "용어 설명")

# ============================================================
# 4. PHASE 1 요약 ① — 핵심 수치
# ============================================================
s = add_slide()
y = slide_title(s, "00 · PHASE 1 요약", "표준 기법을 실데이터로 끝까지 검증했다",
                 sub="세 갈래(SLAM · 위험도 · 학습 모델)로 진행, 전부 실측 데이터 기반", num="①")
cards = [
    ("VO 드리프트 (비디오)", "30.9%", TEAL, "스틸컷 2.3% 대비 — 누적 드리프트가 핵심 원인"),
    ("탐사 SLAM IoU (oracle)", "0.547±0.176", GOLD, "10시드 반복 — 위치오차가 위험지도를 망가뜨림"),
    ("지구→달 평균 위험도", "0.60 → 0.83", RUST, "동일 20m/px · 동일 공식 비교, 9패치 재검증"),
    ("U-Net val mIoU", "0.643", TEAL, "big_rock IoU 0.378 — AI4Mars 학습, 48만 파라미터"),
    ("ConeQuest 단일지역 cone IoU", "0.698", GOLD, "AI4Mars 베이스라인(0.378) 상회 — 외부 데이터 일반화"),
    ("최종 보고서 · 스크립트", "9 / 32", RUST, "결과보고회 33슬라이드, 발표자 노트 22장"),
]
cw, ch, gx, gy = Inches(3.9), Inches(1.7), Inches(0.25), Inches(0.25)
for i, (label, val, color, desc) in enumerate(cards):
    r, c = divmod(i, 3)
    cx = Inches(0.6) + c * (cw + gx)
    cy = y + Inches(0.1) + r * (ch + gy)
    stat_card(s, cx, cy, cw, ch, label, val, color=color, desc=desc)
page_footer(s, "Phase 1 요약")

# ============================================================
# 5. PHASE 1 요약 ② — 셀프 오디트 / 정직한 음의 결과
# ============================================================
s = add_slide()
y = slide_title(s, "00 · PHASE 1 요약", "실패와 과장을 스스로 찾아 공개했다",
                 sub="Validity를 가장 강한 축으로, Creativity를 가장 약한 축으로 스스로 평가", num="②")
bullet_list(s, Inches(0.6), y + Inches(0.1), Inches(11.9), Inches(4.2), [
    ("태양센서 헤딩 보정", "종단오차 94.4m → 146.4m로 악화 — 보정이 개선이 아니었음을 그대로 공개"),
    ("데이터 다양화 가설", "로버 3종 혼합 학습 시 val mIoU 0.643→0.462, big_rock IoU 0.378→0.000으로 반박"),
    ("고해상도 가설", "256→512 재학습해도 big_rock IoU 0.378→0.000 — U-Net 깊이를 안 늘리면 역효과"),
    ("방향성(anisotropic) 위험도", "10시드 전체에서 전복 노출도 차이 거의 없음(0.006 vs 0.006) — 가설 미지지"),
    ("캐스케이드 융합", "그림자 CV(재현율↑오탐↑)와 학습 모델(오탐↓재현율↓)을 결합 — 가장 중요한 역전 사례"),
], size=14, gap=12)
page_footer(s, "Phase 1 요약")

# ============================================================
# 6. SECTION — ConeQuest 2지역
# ============================================================
section_divider("01", "CONEQUEST · 2지역 합산", "ConeQuest 2지역 합산 재학습",
                 "데이터를 늘리면 항상 좋아지는가 — 정직한 음의 결과")

# ============================================================
# 7. ConeQuest 2지역 결과
# ============================================================
s = add_slide()
y = slide_title(s, "01 · CONEQUEST 2지역", "전체 평균은 떨어졌지만, 원인은 명확하다",
                 sub="Isidis Planitia(144장, 양성 91%) + Acidalia Planitia(288장, 양성 46.9%) 합산 재학습", num="②")
ry = simple_table(s, Inches(0.6), y + Inches(0.1),
                   Inches(8.8),
                   ["지역", "학습 방식", "Cone IoU"],
                   [
                       ["Isidis Planitia", "단일 지역 학습", "0.698"],
                       ["Isidis Planitia", "2지역 합산 학습", "0.682"],
                       ["Acidalia Planitia", "2지역 합산 학습", "0.508"],
                       ["전체(2지역 평균)", "2지역 합산 학습", "0.603"],
                   ],
                   col_w=[Inches(3.6), Inches(3.2), Inches(2.0)], row_h=Inches(0.52))
rect(s, Inches(0.6), ry + Inches(0.25), Inches(12.1), Inches(1.3), SURFACE, line_color=GOLD, line_w=Pt(1), round_=True)
textbox(s, Inches(0.9), ry + Inches(0.45), Inches(11.5), Inches(0.75),
        [{'text': "단순히 데이터양을 늘리는 것이 아니라, 지역별 난이도 차이를 고려한 모델 용량·학습 전략이 필요하다 — "
                  "기존 지역(Isidis) 성능은 거의 유지됐지만, 새로 추가한 지역(Acidalia)이 이 모델 용량으로는 더 어려웠다.",
          'size': 14, 'color': INK}])
textbox(s, Inches(9.7), y + Inches(0.1), Inches(3.0), Inches(2.0),
        [{'runs': [{'text': 'train/val/test\n', 'size': 11, 'color': INK_FAINT, 'font': FONT_MONO}]},
         {'text': "288 / 41 / 85", 'size': 20, 'color': TEAL, 'bold': True, 'font': FONT_MONO, 'space_before': 4},
         {'text': "(100 Isidis + 188 Acidalia)", 'size': 11, 'color': INK_SOFT, 'space_before': 4}])
page_footer(s, "ConeQuest 2지역")

# ============================================================
# 8. SECTION — 유인 미션 확장 위험도
# ============================================================
section_divider("02", "HUMAN MISSION RISK", "유인 미션 확장 위험도",
                 "로버 전복 위험에서, 사람의 생존 위험으로")

# ============================================================
# 9. 공식 구조
# ============================================================
s = add_slide()
y = slide_title(s, "02 · 유인 미션 위험도", "기존 공식은 그대로, 시간가변 항만 더했다",
                 sub="W_HUMAN=0이면 기존 지형 전용 공식과 격자점에서 완전히 일치 (하위호환 검증 완료)", num="①")
rect(s, Inches(0.6), y + Inches(0.1), Inches(12.1), Inches(1.15), SURFACE2, line_color=BORDER, round_=True)
textbox(s, Inches(0.85), y + Inches(0.28), Inches(11.6), Inches(0.85),
        [{'text': "risk_total = clip( 0.6×[0.4·slope_risk + 0.6·rock_risk] + 0.4×[0.5·thermal_risk(t) + 0.5·radiation_risk(x,y,t)], 0, 1 )",
          'size': 14.5, 'color': GOLD, 'font': FONT_MONO}])
ty = y + Inches(1.5)
ry2 = simple_table(s, Inches(0.6), ty,
                    Inches(12.1),
                    ["항목", "값", "구분"],
                    [
                        ["방사선 배경값", "0.655 mSv/day", "문헌 (Curiosity RAD, Hassler 2014)"],
                        ["SPE 발생 시 선량 배율", "x2.9", "문헌 (sol 242 관측 근사)"],
                        ["일교차 범위", "-95°C ~ +5°C", "문헌 (JPL REMS 공식 설명 근사)"],
                        ["저온 위험 임계값", "-70°C ~ -95°C", "설계 가정 (배터리/액추에이터 고장 예시)"],
                        ["지형 차폐 최대 감쇠", "50%", "설계 가정 (고도차 proxy, 교육적 근사)"],
                        ["경고 기준선", "mean risk > 0.37", "설계 가정 (단일요인만으론 안 넘도록 설정)"],
                    ],
                    col_w=[Inches(3.0), Inches(2.6), Inches(6.5)], row_h=Inches(0.44))
page_footer(s, "유인 미션 위험도")

# ============================================================
# 10. 1솔 시뮬레이션 결과
# ============================================================
s = add_slide()
y = slide_title(s, "02 · 유인 미션 위험도", "단일 요인은 경고선을 못 넘지만, 겹치면 넘는다",
                 sub="1솔(24h) 시뮬레이션 — 극저온 야간(1~4시)에 SPE가 겹치는 최악의 경우를 시연", num="②")
img_w = Inches(8.0)
img_h = Emu(int(img_w * 1217 / 2066))
img_x = Inches(0.6)
img_y = y + Inches(0.05)
s.shapes.add_picture("../outputs/human_mission_risk/human_mission_risk.png", img_x, img_y, width=img_w, height=img_h)
sx = Inches(8.85)
stat_card(s, sx, img_y, Inches(3.85), Inches(1.8), "경고 임계값 초과", "3개 / 25개", color=RUST, desc="1시~3시 — 야간 극저온 + SPE가 겹치는 구간에서만 발생")
stat_card(s, sx, img_y + Inches(2.05), Inches(3.85), Inches(1.8), "최악 시점 위험도", "0.408", color=GOLD, desc="02:00, 극저온+SPE 중첩 — 지형전용 0.029 대비 급상승 (경고선 0.37)")
page_footer(s, "유인 미션 위험도")

# ============================================================
# 11. 유인 미션 내비게이션 — 임의 목적지 경로탐색 + 안전지대 자동 대피 (완료)
# ============================================================
s = add_slide()
y = slide_title(s, "02 · 유인 미션 위험도", "같은 목적지라도, 시간대가 다르면 내비게이션 판단이 달라진다",
                 sub="임의 목적지 경로탐색(A*) + 안전지대 자동 대피(병목 다익스트라) — reports/11", num="③")

img_h = Inches(3.0)
img_w = Emu(int(img_h * 922 / 857))
gap = Inches(0.25)
ix1 = Inches(0.6)
ix2 = Emu(ix1 + img_w + gap)
iy = y + Inches(0.05)
s.shapes.add_picture("../outputs/human_mission_navigation/destination_calm_terrain_daytime.png", ix1, iy, width=img_w, height=img_h)
s.shapes.add_picture("../outputs/human_mission_navigation/destination_calm_terrain_night_spe.png", ix2, iy, width=img_w, height=img_h)
cap_y = Emu(iy + img_h + Inches(0.06))
textbox(s, ix1, cap_y, img_w, Inches(0.5),
        [{'text': "낮(14시) · DESTINATION_OK", 'size': 11.5, 'color': INK_SOFT, 'bold': True, 'align': PP_ALIGN.CENTER},
         {'text': "max_risk = 0.14", 'size': 11, 'color': TEAL, 'font': FONT_MONO, 'align': PP_ALIGN.CENTER}])
textbox(s, ix2, cap_y, img_w, Inches(0.5),
        [{'text': "야간+SPE(2시) · SAFE_ZONE_REDIRECT", 'size': 11.5, 'color': INK_SOFT, 'bold': True, 'align': PP_ALIGN.CENTER},
         {'text': "max_risk = 0.41 → 0.40", 'size': 11, 'color': RUST, 'font': FONT_MONO, 'align': PP_ALIGN.CENTER}])

sx = Emu(ix2 + img_w + Inches(0.3))
sw = SW - Inches(0.6) - sx
stat_card(s, sx, iy, sw, Inches(1.4), "같은 목적지, 다른 시간대", "0.14 → 0.41", color=GOLD,
          desc="지형은 동일, 시간대만 바뀌어도 경고선(0.37)을 넘어 리다이렉트됨")
stat_card(s, sx, Emu(iy + Inches(1.6)), sw, Inches(1.4), "정직한 버그 수정", "0.51 → 0.40", color=RUST,
          desc="총이동비용 최소화 경로가 직행(0.41)보다 위험(0.51) — 병목(최대위험) 다익스트라로 교체")

box_y = Emu(cap_y + Inches(0.55))
rect(s, Inches(0.6), box_y, Inches(12.1), Inches(0.85), SURFACE, line_color=GOLD, line_w=Pt(1), round_=True)
textbox(s, Inches(0.85), box_y + Inches(0.14), Inches(11.5), Inches(0.6),
        [{'text': "인터랙티브 데모: reports/11-human-mission-navigation.html — 시간대 3종 전환 + 지도 클릭으로 목적지/대피 모드 테스트 가능",
          'size': 12.5, 'color': INK}])
page_footer(s, "유인 미션 내비게이션")

# ============================================================
# 12. 왜 재구성 슬로프가 더 위험하게 나왔는가
# ============================================================
s = add_slide()
y = slide_title(s, "02 · 유인 미션 위험도", "왜 재구성한 슬로프가 실제보다 훨씬 위험하게 나왔는가 — 실측으로 재검증",
                 sub="처음엔 이론적 추정(공식만)으로 '최대 21배'라 썼다 — 실제 데이터로 다시 재보니 과소평가였다", num="④")

cards = [
    ("셀당 평균 관측", "5.2회", TEAL, "중앙값 3회 — '셀당 1번 관측'이라는 가정은 전체의 20%에만 해당"),
    ("재구성 슬로프 중앙값", "3.27", RUST, "포화기준(0.9) 대비 3.6배 — 참값(노이즈 없는) 중앙값은 0.003, 사실상 평지"),
    ("slope_risk 포화(≥1) 비율", "78.3%", GOLD, "관측이 평균 3~5번씩 쌓여 평균화된 뒤에도 포화 — 이론표보다 실측이 더 나쁘다"),
    ("rock_risk(거칠기) 포화 비율", "91.1%", RUST, "슬로프보다 더 심함(중앙값 자체가 1.0) — 5×5창이라 더 많은 노이즈 셀을 끌어들임"),
]
cw, ch, gx, gy = Inches(5.95), Inches(1.55), Inches(0.2), Inches(0.2)
for i, (label, val, color, desc) in enumerate(cards):
    r, c = divmod(i, 2)
    cx = Inches(0.6) + c * (cw + gx)
    cy = y + Inches(0.1) + r * (ch + gy)
    stat_card(s, cx, cy, cw, ch, label, val, color=color, desc=desc)

box_y = y + Inches(0.1) + 2 * (ch + gy) + Inches(0.05)
rect(s, Inches(0.6), box_y, Inches(12.1), Inches(1.15), SURFACE, line_color=GOLD, line_w=Pt(1), round_=True)
textbox(s, Inches(0.85), box_y + Inches(0.12), Inches(11.5), Inches(0.95), [
    {'text': "정정: 처음 표는 '셀당 1번 관측, 거리별 노이즈만' 가정한 이론적 하한이었다 — 방향은 맞았지만 숫자는 "
              "과소평가였고, '슬로프만 문제'라는 지목도 절반만 맞았다. 실측해보니 거칠기(rock_risk, 5×5창)가 슬로프보다 "
              "더 심하게(91% vs 78%) 포화됐다 — 더 많은 이웃 셀의 노이즈를 끌어들이기 때문. reports/12 참고.",
     'size': 11.5, 'color': INK},
])
page_footer(s, "SLAM 통합 — 원인 분석(실측 재검증)")

# ============================================================
# 13. SLAM 지도 구축 + 내비게이션 통합
# ============================================================
s = add_slide()
y = slide_title(s, "02 · 유인 미션 위험도", "SLAM이 만든 지도 위에서도 내비게이션이 똑같이 작동한다",
                 sub="탐사(SLAM) → 위험도 계산 → 내비게이션을 하나로 이었다 — reports/12", num="⑤")

iw1 = Inches(5.9); ih1 = Emu(int(iw1 * 715 / 1754))
iw2 = Inches(5.6); ih2 = Emu(int(iw2 * 897 / 1542))
jx1 = Inches(0.6)
jx2 = Emu(jx1 + iw1 + Inches(0.3))
jy = y + Inches(0.05)
s.shapes.add_picture("../outputs/slam_navigation/slam_navigation_three_way.png", jx1, jy, width=iw1, height=ih1)
s.shapes.add_picture("../outputs/slam_navigation/slam_navigation_timeofday.png", jx2, jy, width=iw2, height=ih2)
textbox(s, jx1, Emu(jy + ih1 + Inches(0.05)), iw1, Inches(0.4),
        [{'text': "참지형 vs oracle SLAM맵 vs VO SLAM맵 — max_risk 0.40 / 0.44 / 0.45",
          'size': 11, 'color': INK_SOFT, 'align': PP_ALIGN.CENTER}])
textbox(s, jx2, Emu(jy + ih2 + Inches(0.05)), iw2, Inches(0.4),
        [{'text': "같은 oracle SLAM 지도, 낮 0.15(OK) vs 야간+SPE 0.43→0.41(redirect)",
          'size': 11, 'color': INK_SOFT, 'align': PP_ALIGN.CENTER}])

box_y2 = Emu(jy + max(ih1, ih2) + Inches(0.35))
rect(s, Inches(0.6), box_y2, Inches(12.1), Inches(0.95), SURFACE, line_color=GOLD, line_w=Pt(1), round_=True)
textbox(s, Inches(0.85), box_y2 + Inches(0.12), Inches(11.5), Inches(0.75),
        [{'text': "정직한 중간 결과(원인은 앞 슬라이드): 재구성 고도맵에서 슬로프를 직접 다시 계산했더니 탐사 영역의 "
                  "100%가 risk=1.0로 포화됐다 — exploration_slam_sim.py가 이미 가진 저노이즈 지형위험 채널"
                  "(oracle_r/vo_r)을 재사용해 해결.",
          'size': 12, 'color': INK}])
page_footer(s, "SLAM 통합")

# ============================================================
# 14. 영상 시연
# ============================================================
s = add_slide()
y = slide_title(s, "02 · 유인 미션 위험도", "전체 과정 영상 — 탐사부터 시간대별 리다이렉트까지",
                 sub="프런티어 탐사로 지도가 채워지는 과정 → 같은 지도 위에서 시간대가 바뀌며 경로가 재조정되는 과정", num="⑥")

vid_h = Inches(4.2)
vid_w = Emu(int(vid_h * 629 / 662))
vid_x = Emu(int((SW - vid_w) / 2))
vid_y = y + Inches(0.1)
s.shapes.add_movie(
    "../outputs/slam_navigation/slam_navigation_demo.mp4",
    vid_x, vid_y, vid_w, vid_h,
    poster_frame_image="../outputs/slam_navigation/slam_navigation_demo_poster.png",
    mime_type="video/mp4",
)
textbox(s, Inches(0.6), Emu(vid_y + vid_h + Inches(0.08)), Inches(12.1), Inches(0.3),
        [{'text': "15초 · 1장 탐사 진행(47스텝) → 2장 같은 oracle SLAM 지도에서 14시→2시로 이동하며 재계산 "
                  "(재생은 PowerPoint 데스크톱 앱에서만 지원 — 원본 파일: outputs/slam_navigation/slam_navigation_demo.mp4)",
          'size': 10.5, 'color': INK_FAINT, 'align': PP_ALIGN.CENTER}])
page_footer(s, "SLAM 통합 — 영상")

# ============================================================
# 15. 유인 미션 컨셉 확장 — 다음 단계 아이디어
# ============================================================
s = add_slide()
y = slide_title(s, "03 · 컨셉 확장", "다음 단계로 고려 중인 유인 미션 요소",
                 sub="대피소·차폐 경로는 구현 완료(앞 2개 슬라이드) — 아래는 아직 코드로 구현되지 않은 아이디어", num="①")
bullet_list(s, Inches(0.6), y + Inches(0.1), Inches(11.9), Inches(4.2), [
    ("생명유지 자원 소모", "산소·전력 잔량 기준 '복귀 가능 반경' 계산 — 거리뿐 아니라 자원 예산으로 경로를 제한"),
    ("통신 음영구역", "MMGIS Sightline(가시선) 개념을 확장해 지구와 통신이 끊기는 지형 음영구역을 지도에 표시"),
    ("EVA 슈트 피로도", "경사·거칠기가 로버 전복이 아니라 '걷는 사람의 피로도'에 미치는 영향을 별도 항으로 설계"),
    ("SLAM 폐루프 재위치추정", "실주행 중 드리프트가 누적되는 동안의 실시간 재위치추정까지는 아직 시뮬레이션하지 않음"),
], size=14.5, gap=13)
page_footer(s, "컨셉 확장")

# ============================================================
# 16. CLOSING / 다음 단계
# ============================================================
s = add_slide()
eyebrow(s, Inches(0.9), Inches(1.0), "NEXT STEPS", color=TEAL)
textbox(s, Inches(0.85), Inches(1.35), Inches(11), Inches(0.9),
        [{'text': "다음 단계", 'size': 38, 'color': INK, 'bold': True}])
horizon_bar(s, Inches(0.9), Inches(2.15), Inches(6.2))
steps = [
    ("1", "컨셉 확장 아이디어(생명유지 자원·통신 음영구역·SLAM 폐루프 재위치추정) 중 우선순위 결정"),
    ("2", "유인 미션 위험도의 설계 가정값(임계값·가중치)을 실제 EVA/우주복 사양 문헌으로 교체"),
    ("3", "Phase 2 신규 섹션을 Phase 1 결과보고회 덱에 통합할지, 별도 덱으로 유지할지 결정"),
    ("4", "ConeQuest 2지역 결과를 반영해 모델 용량·학습 전략 재설계"),
]
ry3 = Inches(2.6)
for num, desc in steps:
    rect(s, Inches(0.9), ry3, Inches(0.55), Inches(0.55), SURFACE2, line_color=GOLD, round_=True)
    textbox(s, Inches(0.9), ry3, Inches(0.55), Inches(0.55),
            [{'text': num, 'size': 16, 'color': GOLD, 'bold': True, 'font': FONT_MONO}], anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.CENTER)
    textbox(s, Inches(1.65), ry3, Inches(10.5), Inches(0.55),
            [{'text': desc, 'size': 15, 'color': INK}], anchor=MSO_ANCHOR.MIDDLE)
    ry3 = Emu(ry3 + Inches(0.72))
page_footer(s)

prs.save('../exports/Phase2/Martian_Map_Phase2.pptx')
print("SAVED", len(prs.slides._sldIdLst), "slides")
