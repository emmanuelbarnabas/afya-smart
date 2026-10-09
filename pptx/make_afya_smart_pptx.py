#!/usr/bin/env python3
"""Afya Smart — presentation mpya yenye animation + gradient (hakuna blue).

Inajengwa na python-pptx. Animations za XML (entrance effects: fade + wipe +
fly-in) zimeongezwa moja kwa moja kwenye slide XML kwa sababu python-pptx
haina API ya animations.

Rangi: kijani cha afya (#0B7A4B), lime (#7BC96F), amber (#E8A020), Nyekundu
nyeupe/kimu (#C0392B) kwa dharura tu — HAKUNA blue.
"""
import copy
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn

# ---------- Rangi (hakuna blue!) ----------
GREEN = RGBColor(0x0B, 0x7A, 0x4B)
GREEN_DARK = RGBColor(0x08, 0x4F, 0x31)
GREEN_DEEP = RGBColor(0x06, 0x3D, 0x26)
LIME = RGBColor(0x7B, 0xC9, 0x6F)
AMBER = RGBColor(0xE8, 0xA0, 0x20)
RED = RGBColor(0xC0, 0x39, 0x2B)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
OFFWHITE = RGBColor(0xF6, 0xFA, 0xF8)
INK = RGBColor(0x14, 0x2B, 0x22)
MUTED = RGBColor(0x5F, 0x71, 0x6D)
CARD = RGBColor(0xFF, 0xFF, 0xFF)
CARD_EDGE = RGBColor(0xE0, 0xEC, 0xE6)

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)

prs = Presentation()
prs.slide_width = SLIDE_W
prs.slide_height = SLIDE_H
BLANK = prs.slide_layouts[6]


# ---------- helpers ----------
def add_slide():
    return prs.slides.add_slide(BLANK)


def solid_bg(slide, color):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = color


def gradient_bg(slide, c1, c2, angle=5400000):
    """Background ya gradient (angle kwa MSO: 5400000 = 90°)."""
    bg = slide.background
    fill = bg.fill
    fill.gradient()
    stops = fill.gradient_stops
    stops[0].color.rgb = c1
    stops[0].position = 0.0
    stops[1].color.rgb = c2
    stops[1].position = 1.0
    try:
        fill.gradient_angle = angle / 60000  # degrees
    except Exception:
        pass


def add_rect(slide, x, y, w, h, fill=None, line=None, radius=None, shadow=False):
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if radius is not None else MSO_SHAPE.RECTANGLE
    sp = slide.shapes.add_shape(shape_type, x, y, w, h)
    if radius is not None:
        try:
            sp.adjustments[0] = radius
        except Exception:
            pass
    if fill is None:
        sp.fill.background()
    else:
        sp.fill.solid()
        sp.fill.fore_color.rgb = fill
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line
        sp.line.width = Pt(1)
    sp.shadow.inherit = False
    if shadow:
        el = sp._element.spPr
        existing = el.find(qn("a:effectLst"))
        if existing is None:
            from lxml import etree
            effect = etree.SubElement(el, qn("a:effectLst"))
            outer = etree.SubElement(effect, qn("a:outerShdw"))
            outer.set("blurRad", "90000")
            outer.set("dist", "38100")
            outer.set("dir", "5400000")
            outer.set("rotWithShape", "0")
            clr = etree.SubElement(outer, qn("a:srgbClr"))
            clr.set("val", "0A3D27")
            alpha = etree.SubElement(clr, qn("a:alpha"))
            alpha.set("val", "20000")
    return sp


def add_circle(slide, x, y, size, fill, line=None):
    sp = slide.shapes.add_shape(MSO_SHAPE.OVAL, x, y, size, size)
    sp.fill.solid()
    sp.fill.fore_color.rgb = fill
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line
        sp.line.width = Pt(1.5)
    sp.shadow.inherit = False
    return sp


def add_text(slide, x, y, w, h, runs, size=18, color=INK, bold=False,
             align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, line_spacing=1.0,
             space_after=0, font="Calibri"):
    """runs: str au list ya paragraphs; kila paragraph inaweza kuwa str au
    list ya (text, overrides) tuples."""
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    if isinstance(runs, str):
        runs = [runs]
    for i, para in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = line_spacing
        if space_after:
            p.space_after = Pt(space_after)
        if isinstance(para, str):
            para = [(para, {})]
        for text, ov in para:
            r = p.add_run()
            r.text = text
            r.font.size = Pt(ov.get("size", size))
            r.font.bold = ov.get("bold", bold)
            r.font.color.rgb = ov.get("color", color)
            r.font.name = ov.get("font", font)
            if ov.get("italic"):
                r.font.italic = True
    return tb


def pill(slide, x, y, w, h, text, fill, color=WHITE, size=11):
    sp = add_rect(slide, x, y, w, h, fill=fill, radius=0.5)
    tf = sp.text_frame
    tf.word_wrap = False
    tf.margin_left = tf.margin_right = Emu(0)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = True
    r.font.color.rgb = color
    r.font.name = "Calibri"
    return sp


def deco_dots(slide, color=LIME, opacity=None):
    """Pambiado: mistari midogo ya dots kona."""
    for i, (x, y) in enumerate([(0.55, 6.9), (0.85, 6.9), (1.15, 6.9)]):
        add_circle(slide, Inches(x), Inches(y), Inches(0.09), color)


# ---------- ANIMATIONS (raw XML) ----------
ANIM_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"


def _make_anim(shape_id, node_name, preset_id, preset_class, preset_subtype,
               delay=0, duration=700, node_type="afterEffect"):
    """Tengeneza par node moja ya entrance animation."""
    return f'''<p:par xmlns:p="{ANIM_NS}" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cTn id="{shape_id * 10 + 5}" presetID="{preset_id}" presetClass="{preset_class}" presetSubtype="{preset_subtype}" fill="hold" grpId="0" nodeType="{node_type}">
    <p:stCondLst><p:cond delay="{delay}"/></p:stCondLst>
    <p:childTnLst>
      <p:set>
        <p:cBhvr>
          <p:cTn id="{shape_id * 10 + 6}" dur="1" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn>
          <p:tgtEl><p:spTgt spid="{shape_id}"/></p:tgtEl>
          <p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst>
        </p:cBhvr>
        <p:to><p:strVal val="visible"/></p:to>
      </p:set>
      <p:animEffect transition="in" filter="fade">
        <p:cBhvr>
          <p:cTn id="{shape_id * 10 + 7}" dur="{duration}"/>
          <p:tgtEl><p:spTgt spid="{shape_id}"/></p:tgtEl>
        </p:cBhvr>
      </p:animEffect>
    </p:childTnLst>
  </p:cTn>
</p:par>'''


def _make_float_anim(shape_id, delay=0, duration=800, direction="up"):
    """Fly-in: content inatoka chini/juu na fade."""
    dx = 0
    dy = "#ppt_h/12" if direction == "up" else "-#ppt_h/12"
    return f'''<p:par xmlns:p="{ANIM_NS}" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cTn id="{shape_id * 10 + 8}" presetID="2" presetClass="entr" presetSubtype="4" fill="hold" grpId="0" nodeType="afterEffect">
    <p:stCondLst><p:cond delay="{delay}"/></p:stCondLst>
    <p:childTnLst>
      <p:set>
        <p:cBhvr>
          <p:cTn id="{shape_id * 10 + 9}" dur="1" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn>
          <p:tgtEl><p:spTgt spid="{shape_id}"/></p:tgtEl>
          <p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst>
        </p:cBhvr>
        <p:to><p:strVal val="visible"/></p:to>
      </p:set>
      <p:anim calcmode="lin" valueType="num">
        <p:cBhvr additive="base">
          <p:cTn id="{shape_id * 10 + 10}" dur="{duration}" fill="hold"/>
          <p:tgtEl><p:spTgt spid="{shape_id}"/></p:tgtEl>
          <p:attrNameLst><p:attrName>ppt_x</p:attrName></p:attrNameLst>
        </p:cBhvr>
        <p:tavLst>
          <p:tav tm="0"><p:val><p:strVal val="#ppt_x"/></p:val></p:tav>
          <p:tav tm="100000"><p:val><p:strVal val="#ppt_x"/></p:val></p:tav>
        </p:tavLst>
      </p:anim>
      <p:anim calcmode="lin" valueType="num">
        <p:cBhvr additive="base">
          <p:cTn id="{shape_id * 10 + 11}" dur="{duration}" fill="hold"/>
          <p:tgtEl><p:spTgt spid="{shape_id}"/></p:tgtEl>
          <p:attrNameLst><p:attrName>ppt_y</p:attrName></p:attrNameLst>
        </p:cBhvr>
        <p:tavLst>
          <p:tav tm="0"><p:val><p:strVal val="{dy}+#ppt_y"/></p:val></p:tav>
          <p:tav tm="100000"><p:val><p:strVal val="#ppt_y"/></p:val></p:tav>
        </p:tavLst>
      </p:anim>
      <p:animEffect transition="in" filter="fade">
        <p:cBhvr>
          <p:cTn id="{shape_id * 10 + 12}" dur="{duration}"/>
          <p:tgtEl><p:spTgt spid="{shape_id}"/></p:tgtEl>
        </p:cBhvr>
      </p:animEffect>
    </p:childTnLst>
  </p:cTn>
</p:par>'''


def animate(slide, specs):
    """Weke animations kwenye slide.

    specs: list ya (shape, kind, delay) ambapo kind ni "fade" au "rise".
    """
    if not specs:
        return
    from lxml import etree
    slide_el = slide._element
    timing = slide_el.find(qn("p:timing"))
    if timing is None:
        timing = etree.SubElement(slide_el, qn("p:timing"))
    tn_tree = etree.SubElement(timing, qn("p:tnLst"))
    par_root = etree.SubElement(tn_tree, qn("p:par"))
    ctn = etree.SubElement(par_root, qn("p:cTn"))
    ctn.set("id", "1")
    ctn.set("dur", "indefinite")
    ctn.set("restart", "never")
    ctn.set("nodeType", "tmRoot")
    child = etree.SubElement(ctn, qn("p:childTnLst"))
    seq = etree.SubElement(child, qn("p:seq"))
    seq.set("concurrent", "1")
    seq.set("nextAc", "seek")
    seq_ctn = etree.SubElement(seq, qn("p:cTn"))
    seq_ctn.set("id", "2")
    seq_ctn.set("dur", "indefinite")
    seq_ctn.set("nodeType", "mainSeq")
    seq_child = etree.SubElement(seq_ctn, qn("p:childTnLst"))

    # kila animation iwe par yake ndani ya mainSeq
    for i, (shape, kind, delay) in enumerate(specs):
        shape_id = shape.shape_id
        if kind == "rise":
            xml = _make_float_anim(shape_id, delay=delay)
        else:
            xml = _make_anim(shape_id, "fade", 10, "entr", 0, delay=delay)
        par_el = etree.fromstring(xml)
        seq_child.append(par_el)

    # prev/next cond kwa seq
    prev = etree.SubElement(seq, qn("p:prevCondLst"))
    cond = etree.SubElement(prev, qn("p:cond"))
    evt = etree.SubElement(cond, qn("p:evt"))
    evt.text = "onPrev"
    delay_el = etree.SubElement(cond, qn("p:delay"))
    delay_el.text = "0"
    tgt = etree.SubElement(cond, qn("p:tgtEl"))
    sld = etree.SubElement(tgt, qn("p:sldTgt"))
    nxt = etree.SubElement(seq, qn("p:nextCondLst"))
    cond2 = etree.SubElement(nxt, qn("p:cond"))
    evt2 = etree.SubElement(cond2, qn("p:evt"))
    evt2.text = "onNext"
    delay_el2 = etree.SubElement(cond2, qn("p:delay"))
    delay_el2.text = "0"
    tgt2 = etree.SubElement(cond2, qn("p:tgtEl"))
    sld2 = etree.SubElement(tgt2, qn("p:sldTgt"))


# ---------- brand chrome (kila slide) ----------
def chrome(slide, section=None):
    """Dot brand + footer nyepesi."""
    add_circle(slide, Inches(0.55), Inches(6.95), Inches(0.12), GREEN)
    add_circle(slide, Inches(0.75), Inches(6.95), Inches(0.12), LIME)
    add_circle(slide, Inches(0.95), Inches(6.95), Inches(0.12), AMBER)
    add_text(slide, Inches(11.1), Inches(6.88), Inches(1.9), Inches(0.35),
             "AFYA SMART", size=10, color=MUTED, bold=True, align=PP_ALIGN.RIGHT)


def header(slide, kicker, title, title_color=GREEN_DARK):
    """Header ya slide ya kawaida (na animate)."""
    k = add_text(slide, Inches(0.55), Inches(0.42), Inches(9), Inches(0.4),
                 kicker, size=13, color=AMBER, bold=True)
    t = add_text(slide, Inches(0.55), Inches(0.78), Inches(11.5), Inches(0.9),
                 title, size=34, color=title_color, bold=True)
    bar = add_rect(slide, Inches(0.57), Inches(1.62), Inches(1.6), Inches(0.07),
                   fill=AMBER, radius=0.5)
    return [k, t, bar]


# ============================================================
# SLIDE 1 — Title (dark gradient ya kijani)
# ============================================================
s = add_slide()
gradient_bg(s, GREEN_DEEP, GREEN)
# pambiado: circles kubwa zenye transparency (fake glass)
ring = add_circle(s, Inches(9.2), Inches(-1.6), Inches(6.2), GREEN)
ring.fill.fore_color.rgb = RGBColor(0x0A, 0x6B, 0x42)
ring2 = add_circle(s, Inches(-2.2), Inches(4.6), Inches(5.4), GREEN_DARK)
pill(s, Inches(0.85), Inches(1.55), Inches(2.3), Inches(0.42),
     "PUBLIC HEALTH · SOFTWARE", RGBColor(0x0E, 0x54, 0x36), color=LIME, size=11)

t1 = add_text(s, Inches(0.82), Inches(2.05), Inches(9.5), Inches(1.4),
              "AFYA SMART", size=66, color=WHITE, bold=True)
t2 = add_text(s, Inches(0.85), Inches(3.45), Inches(10.5), Inches(1.0),
              "AI-Powered Triage & Queue Management for Fairer, Faster Public Healthcare",
              size=20, color=RGBColor(0xD8, 0xF0, 0xE3))
line = add_rect(s, Inches(0.88), Inches(4.75), Inches(2.2), Inches(0.08),
                fill=AMBER, radius=0.5)
t3 = add_text(s, Inches(0.85), Inches(5.05), Inches(8), Inches(0.9),
              [[("Presented by ", {"color": RGBColor(0xB9, 0xDC, 0xC9), "size": 15}),
                ("Emmanuel Stephen Barnabas", {"color": WHITE, "size": 15, "bold": True})]])
deco_dots(s)
animate(s, [(t1, "rise", 0), (t2, "fade", 500), (line, "fade", 900), (t3, "fade", 1200)])

# ============================================================
# SLIDE 2 — Roadmap
# ============================================================
s = add_slide()
solid_bg(s, OFFWHITE)
chrome(s)
hdr = header(s, "OVERVIEW", "Presentation Roadmap")

items = [
    ("01", "The Problem", "Why queues cost lives and time", AMBER),
    ("02", "Who It Affects", "Patients, families and health workers", RED),
    ("03", "The Solution", "Afya Smart — triage by phone, not queue", GREEN),
    ("04", "Key Features", "Four features, one connected journey", GREEN),
    ("05", "How It Works", "The patient journey, step by step", GREEN),
    ("06", "Success", "We will measure what matters", AMBER),
]
specs = [hdr[0], hdr[1]]
for i, (num, title, sub, tone) in enumerate(items):
    col = i % 2
    row = i // 2
    x = Inches(0.55 + col * 6.25)
    y = Inches(2.15 + row * 1.55)
    card = add_rect(s, x, y, Inches(5.95), Inches(1.32), fill=CARD,
                    line=CARD_EDGE, radius=0.14, shadow=True)
    n = add_circle(s, x + Inches(0.25), y + Inches(0.28), Inches(0.75), tone)
    tf = n.text_frame
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = num
    r.font.size = Pt(16)
    r.font.bold = True
    r.font.color.rgb = WHITE
    add_text(s, x + Inches(1.25), y + Inches(0.18), Inches(4.5), Inches(0.5),
             title, size=17, bold=True, color=INK)
    add_text(s, x + Inches(1.25), y + Inches(0.68), Inches(4.5), Inches(0.5),
             sub, size=12, color=MUTED)
    specs.append(card)
animate(s, [(sp, "rise", 200 + i * 150) for i, sp in enumerate(specs)])

# ============================================================
# SLIDE 3 — The Problem
# ============================================================
s = add_slide()
solid_bg(s, OFFWHITE)
chrome(s)
hdr = header(s, "01 · THE PROBLEM", "Long queues. Lost days. Zero visibility.")

big = add_rect(s, Inches(0.55), Inches(2.2), Inches(6.1), Inches(3.9),
               fill=GREEN_DEEP, radius=0.08, shadow=True)
add_text(s, Inches(1.0), Inches(2.7), Inches(5.3), Inches(0.5),
         "THOSE WHO TRULY NEED CARE WAIT", size=13, color=LIME, bold=True)
big1 = add_text(s, Inches(1.0), Inches(3.25), Inches(5.3), Inches(1.1),
                "3–6 hours", size=54, color=WHITE, bold=True)
big2 = add_text(s, Inches(1.0), Inches(4.45), Inches(5.3), Inches(0.9),
                [[("in line — some arrive as early as ", {"size": 15, "color": RGBColor(0xCF, 0xE9, 0xDB)}),
                  ("5:00 AM", {"size": 17, "color": AMBER, "bold": True}),
                  (" to secure a place.", {"size": 15, "color": RGBColor(0xCF, 0xE9, 0xDB)})]])
quote = add_rect(s, Inches(7.05), Inches(2.2), Inches(5.7), Inches(3.9),
                 fill=CARD, line=CARD_EDGE, radius=0.08, shadow=True)
add_text(s, Inches(7.5), Inches(2.6), Inches(4.9), Inches(0.4),
         "THE CORE INEFFICIENCY", size=12, color=AMBER, bold=True)
q1 = add_text(s, Inches(7.5), Inches(3.15), Inches(4.85), Inches(1.7),
              "“A 10–15 minute consultation can cost a patient an entire day of work.”",
              size=21, color=GREEN_DARK, bold=True, line_spacing=1.15)
q2 = add_text(s, Inches(7.5), Inches(5.0), Inches(4.85), Inches(0.9),
              "Health workers have no digital way to know who needs urgent attention before patients arrive.",
              size=13, color=MUTED, line_spacing=1.15)
deco_dots(s)
animate(s, [(hdr[0], "fade", 0), (hdr[1], "rise", 150),
            (big, "rise", 400), (big1, "fade", 700), (big2, "fade", 900),
            (quote, "rise", 700), (q1, "fade", 1000), (q2, "fade", 1200)])

# ============================================================
# SLIDE 4 — Who it affects
# ============================================================
s = add_slide()
solid_bg(s, OFFWHITE)
chrome(s)
hdr = header(s, "02 · WHO IT AFFECTS", "The wait touches everyone")

groups = [
    ("Patients & Caregivers", "Lose a full workday for routine care — and rural patients often cannot tell whether travel is even necessary.", GREEN),
    ("Triage Nurses & Clinicians", "Sort true emergencies from routine cases manually, with no prior information about who is arriving.", AMBER),
    ("Facility Administrators", "Manage overcrowding blind — no data on demand, no tools to flatten the peak.", RED),
]
specs = [hdr[0], hdr[1]]
for i, (title, body, tone) in enumerate(groups):
    x = Inches(0.55 + i * 4.28)
    y = Inches(2.3)
    card = add_rect(s, x, y, Inches(3.95), Inches(3.5), fill=CARD,
                    line=CARD_EDGE, radius=0.09, shadow=True)
    strip = add_rect(s, x, y, Inches(3.95), Inches(0.16), fill=tone, radius=0.5)
    n = add_circle(s, x + Inches(0.3), y + Inches(0.5), Inches(0.85), tone)
    tf = n.text_frame
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = f"0{i+1}"
    r.font.size = Pt(18)
    r.font.bold = True
    r.font.color.rgb = WHITE
    t = add_text(s, x + Inches(0.3), y + Inches(1.55), Inches(3.35), Inches(0.6),
                 title, size=17, bold=True, color=INK)
    b = add_text(s, x + Inches(0.3), y + Inches(2.15), Inches(3.35), Inches(1.2),
                 body, size=12.5, color=MUTED, line_spacing=1.2)
    specs += [card, t]
animate(s, [(sp, "rise", 200 + i * 200) for i, sp in enumerate(specs)])

# ============================================================
# SLIDE 5 — The Solution
# ============================================================
s = add_slide()
solid_bg(s, OFFWHITE)
chrome(s)
hdr = header(s, "03 · THE SOLUTION", "Afya Smart — from first symptom to point of care")

intro = add_text(s, Inches(0.55), Inches(2.05), Inches(12.2), Inches(0.95),
                 [[("A USSD/SMS and web platform that guides each patient from the first symptom to the right care — designed to work on ", {"size": 15, "color": INK}),
                   ("any phone", {"size": 15, "color": GREEN, "bold": True}),
                   (", with no smartphone or internet required on the patient's side.", {"size": 15, "color": INK})]],
                 line_spacing=1.2)

cards = [
    ("BETTER", "Right care, right time", "AI triage flags true emergencies immediately and gives every patient clear guidance.", GREEN),
    ("FASTER", "Less time lost waiting", "Priority queues and booked slots mean shorter waits — expected wait is known in advance.", AMBER),
    ("FAIRER", "Care for every phone", "USSD works on feature phones — no smartphone, no internet, no one left behind.", RED),
]
specs = [intro]
for i, (tag, title, body, tone) in enumerate(cards):
    x = Inches(0.55 + i * 4.28)
    y = Inches(3.15)
    card = add_rect(s, x, y, Inches(3.95), Inches(2.9), fill=CARD,
                    line=CARD_EDGE, radius=0.09, shadow=True)
    tagp = pill(s, x + Inches(0.3), y + Inches(0.3), Inches(1.35), Inches(0.4), tag, tone, size=11)
    t = add_text(s, x + Inches(0.3), y + Inches(0.9), Inches(3.35), Inches(0.55),
                 title, size=16, bold=True, color=INK)
    b = add_text(s, x + Inches(0.3), y + Inches(1.5), Inches(3.35), Inches(1.2),
                 body, size=12.5, color=MUTED, line_spacing=1.2)
    specs.append(card)
animate(s, [(sp, "rise", 200 + i * 180) for i, sp in enumerate(specs)])

# ============================================================
# SLIDE 6 — Key Features
# ============================================================
s = add_slide()
gradient_bg(s, GREEN_DEEP, GREEN_DARK)
k = add_text(s, Inches(0.55), Inches(0.42), Inches(9), Inches(0.4),
             "04 · KEY FEATURES", size=13, color=LIME, bold=True)
t = add_text(s, Inches(0.55), Inches(0.78), Inches(11.5), Inches(0.9),
             "Four features, one connected journey", size=34, color=WHITE, bold=True)
bar = add_rect(s, Inches(0.57), Inches(1.62), Inches(1.6), Inches(0.07), fill=AMBER, radius=0.5)

feats = [
    ("01", "AI Symptom Triage (USSD)", "4–6 quick questions on any phone; the model sorts emergency, urgent, routine and self-care."),
    ("02", "Smart Queue & Slot Booking", "Urgent cases jump the queue; routine cases get slots with the shortest expected wait."),
    ("03", "Facility Dashboard", "Live queue, emergency bypass, one-tap calling and clinician feedback — built for the front desk."),
    ("04", "Demand Analytics", "Wait-time percentiles, triage accuracy and demand curves that guide staffing and retraining."),
]
specs = [k, t]
for i, (num, title, body) in enumerate(feats):
    col = i % 2
    row = i // 2
    x = Inches(0.55 + col * 6.25)
    y = Inches(2.15 + row * 2.15)
    card = add_rect(s, x, y, Inches(5.95), Inches(1.9),
                    fill=RGBColor(0x0C, 0x63, 0x3E), radius=0.1)
    n = add_text(s, x + Inches(0.3), y + Inches(0.22), Inches(1.2), Inches(0.6),
                 num, size=26, color=LIME, bold=True)
    t2 = add_text(s, x + Inches(1.3), y + Inches(0.25), Inches(4.4), Inches(0.55),
                  title, size=16.5, color=WHITE, bold=True)
    b = add_text(s, x + Inches(0.3), y + Inches(0.85), Inches(5.35), Inches(0.95),
                 body, size=12, color=RGBColor(0xC9, 0xE7, 0xD7), line_spacing=1.18)
    specs.append(card)
animate(s, [(sp, "rise", 200 + i * 170) for i, sp in enumerate(specs)])

# ============================================================
# SLIDE 7 — How it works (journey)
# ============================================================
s = add_slide()
solid_bg(s, OFFWHITE)
chrome(s)
hdr = header(s, "05 · HOW IT WORKS", "The patient journey")

steps = [
    ("1 · DIAL USSD", "From any phone — no smartphone, app or internet needed."),
    ("2 · ANSWER TRIAGE", "Answer 4–6 short questions about the symptoms."),
    ("3 · GET GUIDANCE", "Clear advice: go now, book a slot, or self-care."),
    ("4 · SKIP THE QUEUE", "Arrive at the booked time — expected wait already known."),
]
specs = [hdr[0], hdr[1]]
y = Inches(2.5)
for i, (title, body) in enumerate(steps):
    x = Inches(0.55 + i * 3.22)
    # connector line
    if i < 3:
        conn = add_rect(s, x + Inches(2.35), y + Inches(1.05), Inches(0.85), Inches(0.06),
                        fill=CARD_EDGE, radius=0.5)
    circ = add_circle(s, x + Inches(1.28), y, Inches(1.25), GREEN if i % 2 == 0 else AMBER)
    tf = circ.text_frame
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = str(i + 1)
    r.font.size = Pt(30)
    r.font.bold = True
    r.font.color.rgb = WHITE
    t = add_text(s, x, y + Inches(1.45), Inches(2.9), Inches(0.45),
                 title, size=14.5, bold=True, color=INK, align=PP_ALIGN.CENTER)
    b = add_text(s, x, y + Inches(1.95), Inches(2.9), Inches(1.0),
                 body, size=11.5, color=MUTED, align=PP_ALIGN.CENTER, line_spacing=1.15)
    specs.append(circ)
animate(s, [(sp, "rise", 250 + i * 280) for i, sp in enumerate(specs)])

# ============================================================
# SLIDE 8 — Technology stack
# ============================================================
s = add_slide()
solid_bg(s, OFFWHITE)
chrome(s)
hdr = header(s, "06 · TECHNOLOGY STACK", "Built light, for real conditions")

rows = [
    ("PATIENT ACCESS", "USSD & SMS — Africa's Talking API", "Works on any phone; no smartphone or internet needed", GREEN),
    ("BACKEND / API", "Python · FastAPI + PostgreSQL", "Lightweight services for triage, booking and queues", AMBER),
    ("AI / ML", "Gradient boosting triage model + demand forecasting", "Trained on 12,000 triage samples · 89% accuracy, retrained from clinician feedback", RED),
    ("WEB PLATFORMS", "React admin dashboard · patient app · installable PWA", "Pages for queue, analytics, reminders and USSD simulation", GREEN),
]
specs = [hdr[0], hdr[1]]
y = Inches(2.15)
for i, (tag, tech, note, tone) in enumerate(rows):
    yy = y + Inches(i * 1.12)
    card = add_rect(s, Inches(0.55), yy, Inches(12.2), Inches(0.95),
                    fill=CARD, line=CARD_EDGE, radius=0.12, shadow=True)
    tagp = add_rect(s, Inches(0.75), yy + Inches(0.24), Inches(2.35), Inches(0.46),
                    fill=tone, radius=0.5)
    tf = tagp.text_frame
    tf.margin_left = Emu(0)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = tag
    r.font.size = Pt(11)
    r.font.bold = True
    r.font.color.rgb = WHITE
    t = add_text(s, Inches(3.35), yy + Inches(0.12), Inches(9.2), Inches(0.45),
                 tech, size=15, bold=True, color=INK)
    b = add_text(s, Inches(3.35), yy + Inches(0.52), Inches(9.2), Inches(0.4),
                 note, size=11.5, color=MUTED)
    specs.append(card)
animate(s, [(sp, "rise", 200 + i * 200) for i, sp in enumerate(specs)])

# ============================================================
# SLIDE 9 — Success metrics
# ============================================================
s = add_slide()
solid_bg(s, OFFWHITE)
chrome(s)
hdr = header(s, "07 · WHAT SUCCESS LOOKS LIKE", "We will measure what matters")

metrics = [
    ("Shorter waits", "Average physical wait time per patient, baseline vs post-pilot, measured in minutes.", AMBER),
    ("Accurate triage", "% of USSD sessions correctly deferring non-urgent cases, validated by clinician review.", GREEN),
    ("Flatter demand", "Smaller gap between peak (6–9 AM) and off-peak patient volume across the day.", RED),
    ("Zero missed emergencies", "No true emergency delayed by the triage/queue flow — the metric that matters most.", GREEN_DARK),
]
specs = [hdr[0], hdr[1]]
for i, (title, body, tone) in enumerate(metrics):
    col = i % 2
    row = i // 2
    x = Inches(0.55 + col * 6.25)
    y = Inches(2.2 + row * 2.05)
    card = add_rect(s, x, y, Inches(5.95), Inches(1.8), fill=CARD,
                    line=CARD_EDGE, radius=0.1, shadow=True)
    strip = add_rect(s, x, y, Inches(0.14), Inches(1.8), fill=tone, radius=0.5)
    t = add_text(s, x + Inches(0.45), y + Inches(0.22), Inches(5.2), Inches(0.5),
                 title, size=17, bold=True, color=INK)
    b = add_text(s, x + Inches(0.45), y + Inches(0.8), Inches(5.2), Inches(0.9),
                 body, size=12.5, color=MUTED, line_spacing=1.2)
    specs.append(card)
animate(s, [(sp, "rise", 200 + i * 180) for i, sp in enumerate(specs)])

# ============================================================
# SLIDE 10 — Thank you
# ============================================================
s = add_slide()
gradient_bg(s, GREEN_DEEP, GREEN)
ring = add_circle(s, Inches(9.6), Inches(3.9), Inches(5.8), GREEN_DARK)
ty = add_text(s, Inches(0.85), Inches(2.3), Inches(10), Inches(1.3),
              "Thank You", size=60, color=WHITE, bold=True)
sub = add_text(s, Inches(0.88), Inches(3.7), Inches(10), Inches(0.6),
               "Afya Smart — fairer, faster healthcare for every Tanzanian.",
               size=19, color=RGBColor(0xD8, 0xF0, 0xE3))
who = add_text(s, Inches(0.88), Inches(4.75), Inches(10), Inches(0.5),
               "Emmanuel Stephen Barnabas  ·  Public Health  ·  Software (Web & Mobile)",
               size=14, color=LIME, bold=True)
deco_dots(s)
animate(s, [(ty, "rise", 0), (sub, "fade", 500), (who, "fade", 900)])

OUT = "/home/karen/Desktop/Afya Smart Presentation v2.pptx"
prs.save(OUT)
print("saved:", OUT)
