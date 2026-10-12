"""Tengeneza Afya Smart pitch deck: PPTX (inafunguka PowerPoint/Google Slides) + PDF.

Run:  .venv-tools/bin/python submission/make_deck.py
Matokeo: submission/AfyaSmart_PitchDeck.pptx na submission/AfyaSmart_PitchDeck.pdf
"""
import pathlib
import subprocess

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

HERE = pathlib.Path(__file__).parent
PPTX = HERE / "AfyaSmart_PitchDeck.pptx"
PDF = HERE / "AfyaSmart_PitchDeck.pdf"

# Rangi za chapa (zilezile za USSD/icon: bluu ya gradient)
BLUE_DARK = RGBColor(0x1D, 0x4E, 0xD8)
BLUE = RGBColor(0x3B, 0x82, 0xF6)
INK = RGBColor(0x1E, 0x29, 0x3B)
GREY = RGBColor(0x47, 0x55, 0x69)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT = RGBColor(0xEF, 0xF2, 0xFF)
RED = RGBColor(0xDC, 0x26, 0x26)
AMBER = RGBColor(0xD9, 0x77, 0x06)
GREEN = RGBColor(0x16, 0xA3, 0x4A)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]
SW, SH = prs.slide_width, prs.slide_height


def rect(slide, x, y, w, h, fill, line=None):
    from pptx.enum.shapes import MSO_SHAPE

    shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
    shp.shadow.inherit = False
    return shp


def text(slide, x, y, w, h, runs, align=PP_ALIGN.LEFT, anchor=None):
    """runs: list ya (text, size, bold, color) — kila moja kwa aya tofauti."""
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    if anchor is not None:
        from pptx.enum.text import MSO_ANCHOR

        tf.vertical_anchor = anchor
    for i, (t, size, bold, color) in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run()
        r.text = t
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.color.rgb = color
        r.font.name = "Calibri"
    return tb


def header(slide, title, subtitle=None):
    rect(slide, 0, 0, SW, Inches(1.05), BLUE_DARK)
    text(slide, Inches(0.55), Inches(0.16), Inches(12.2), Inches(0.75),
         [(title, 30, True, WHITE)])
    if subtitle:
        text(slide, Inches(0.58), Inches(0.72), Inches(12.2), Inches(0.32),
             [(subtitle, 14, False, RGBColor(0xDB, 0xEA, 0xFE))])


def bullets(slide, x, y, w, items, size=16, color=INK, gap=Pt(10)):
    tb = slide.shapes.add_textbox(x, y, w, SH - y - Inches(0.5))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        if isinstance(item, tuple):
            head, rest = item
        else:
            head, rest = None, item
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = gap
        r0 = p.add_run()
        r0.text = "•  "
        r0.font.size = Pt(size)
        r0.font.color.rgb = BLUE
        r0.font.bold = True
        if head:
            rh = p.add_run()
            rh.text = head
            rh.font.size = Pt(size)
            rh.font.bold = True
            rh.font.color.rgb = color
        rr = p.add_run()
        rr.text = rest
        rr.font.size = Pt(size)
        rr.font.color.rgb = color
    return tb


def kpi_card(slide, x, y, w, h, value, label, accent=BLUE_DARK):
    rect(slide, x, y, w, h, LIGHT)
    rect(slide, x, y, Inches(0.08), h, accent)
    text(slide, x + Inches(0.25), y + Inches(0.18), w - Inches(0.4), Inches(0.7),
         [(value, 30, True, accent)])
    text(slide, x + Inches(0.25), y + Inches(0.85), w - Inches(0.4), h - Inches(1.0),
         [(label, 13, False, GREY)])


# ── 1. Title ────────────────────────────────────────────────────────────────
s = prs.slides.add_slide(BLANK)
rect(s, 0, 0, SW, SH, BLUE_DARK)
rect(s, 0, Inches(5.9), SW, Inches(1.6), RGBColor(0x17, 0x3C, 0xA8))
text(s, Inches(0.9), Inches(1.9), Inches(11.5), Inches(1.3),
     [("Afya Smart", 60, True, WHITE)])
text(s, Inches(0.95), Inches(3.1), Inches(11.5), Inches(0.9),
     [("AI-powered triage & queue management for fairer, faster public healthcare", 24, False, RGBColor(0xDB, 0xEA, 0xFE))])
text(s, Inches(0.95), Inches(4.1), Inches(11.5), Inches(0.6),
     [("Any phone. No app. No internet. USSD *384#", 18, True, WHITE)])
text(s, Inches(0.95), Inches(6.1), Inches(11.5), Inches(1.1),
     [("RIDC PT Innovation Hackathon 2026  ·  Software (Web & Mobile)", 16, False, WHITE),
      ("Emmanuel Stephen Barnabas  ·  github.com/emmanuelbarnabas/afya-smart", 13, False, RGBColor(0xBF, 0xDB, 0xFE))])

# ── 2. Problem ──────────────────────────────────────────────────────────────
s = prs.slides.add_slide(BLANK)
header(s, "The problem: public clinics are slow — and unfairly so", "Tanzania · 1 doctor per ~10,000 people; most citizens own a basic phone")
bullets(s, Inches(0.7), Inches(1.5), Inches(12), [
    ("Long, opaque queues. ", "Patients arrive at 5am, wait 4–6 hours, and never know their position or who is being seen before them."),
    ("No triage before arrival. ", "A stroke and a refill prescription wait in the same line; the emergency case is discovered too late."),
    ("Smartphone-only digital health. ", "Apps and QR check-in exclude the majority who use 2G feature phones."),
    ("Hidden bias. ", "Women, rural patients and walk-ins systematically wait longer — nobody measures it, so nobody fixes it."),
])

# ── 3. Solution ─────────────────────────────────────────────────────────────
s = prs.slides.add_slide(BLANK)
header(s, "Solution: triage before you leave home, queue before you arrive")
bullets(s, Inches(0.7), Inches(1.5), Inches(12), [
    ("USSD on any phone. ", "Patient dials *384#, answers a short symptom interview in Kiswahili/English — no smartphone, no internet, no app install."),
    ("AI urgency triage. ", "ML model (gradient boosting) + rule-based red-flag safety net returns RED / YELLOW / GREEN with a reason."),
    ("Smart booking. ", "Nearest facility, first free slot with predicted wait — confirmed by SMS with an appointment ID."),
    ("Fair live queue. ", "One queue per facility on the nurse's dashboard: urgency-banded FIFO, emergency bypass, ageing override."),
    ("Accountability. ", "A fairness report compares average waits by sex, age, facility and urgency — bias becomes visible and fixable."),
])

# ── 4. How it works ─────────────────────────────────────────────────────────
s = prs.slides.add_slide(BLANK)
header(s, "How it works — the patient journey")
steps = [
    ("1. Dial *384#", "USSD session, Kiswahili or English"),
    ("2. Describe symptoms", "Keyword interview → structured features"),
    ("3. Triage result", "RED / YELLOW / GREEN + reason + advice"),
    ("4. Book a slot", "Facility choice, date, time — capacity-aware"),
    ("5. SMS confirmation", "Appointment ID + reminder before the day"),
    ("6. Fair queue on arrival", "Position on nurse dashboard, live updates"),
]
x0, y0 = Inches(0.7), Inches(1.7)
cw, ch = Inches(3.9), Inches(1.5)
for i, (t, d) in enumerate(steps):
    col, row = i % 3, i // 3
    x = x0 + col * (cw + Inches(0.25))
    y = y0 + row * (ch + Inches(0.35))
    rect(s, x, y, cw, ch, LIGHT)
    rect(s, x, y, cw, Inches(0.09), BLUE)
    text(s, x + Inches(0.2), y + Inches(0.22), cw - Inches(0.4), Inches(0.5),
         [(t, 17, True, BLUE_DARK)])
    text(s, x + Inches(0.2), y + Inches(0.75), cw - Inches(0.4), Inches(0.7),
         [(d, 13, False, GREY)])
text(s, Inches(0.7), Inches(5.9), Inches(12), Inches(0.6),
     [("Total time on the phone: under 2 minutes.  Walk-ins and anonymous patients (no SIM) supported.", 15, True, INK)])

# ── 5. Triage engine ────────────────────────────────────────────────────────
s = prs.slides.add_slide(BLANK)
header(s, "AI triage: ML where it helps, rules where it must never fail")
bullets(s, Inches(0.7), Inches(1.45), Inches(7.4), [
    ("Safety net first. ", "Rule-based red-flag detection (chest pain, stroke signs, bleeding…) always overrides the model."),
    ("Gradient-boosting classifier ", "trained on 12,000 synthetic symptom profiles (ml-v2)."),
    ("Clinician feedback loop. ", "Nurse records the real urgency after consultation → measured against prediction → retraining."),
    ("Graceful degradation. ", "Model load failure falls back to rules-only; every prediction carries a version + reason."),
])
kpi_card(s, Inches(8.5), Inches(1.6), Inches(2.1), Inches(1.55), "89.4%", "Overall accuracy (ml-v2)")
kpi_card(s, Inches(10.8), Inches(1.6), Inches(2.1), Inches(1.55), "88.4%", "Recall on EMERGENCY cases")
kpi_card(s, Inches(8.5), Inches(3.35), Inches(2.1), Inches(1.55), "12,000", "Training samples / version")
kpi_card(s, Inches(10.8), Inches(3.35), Inches(2.1), Inches(1.55), "107", "Automated tests passing")

# ── 6. Fairness ─────────────────────────────────────────────────────────────
s = prs.slides.add_slide(BLANK)
header(s, "Fairness by design — the feature hackathons rarely ship")
bullets(s, Inches(0.7), Inches(1.5), Inches(12), [
    ("Measured, not assumed. ", "Average and 90th-percentile waits grouped by sex × age band × facility × urgency × walk-in vs booked."),
    ("Ageing override. ", "priority = urgency_weight × 60 − minutes_waited — a GREEN patient who waited long overtakes a fresh YELLOW."),
    ("Emergency bypass is audited. ", "Every bypass is flagged and reviewable — speed never erases accountability."),
    ("Clinician overrides kept. ", "Nurses can re-grade urgency; the override is stored with who/when/why."),
    ("Open report. ", "/fairness renders the numbers as charts anyone — including patients — can inspect."),
])

# ── 6b. Tech stack (kutoka pendekezo) ──────────────────────────────────────
s = prs.slides.add_slide(BLANK)
header(s, "Technology stack", "Built exactly as proposed — Python-first, deployable on lightweight hosting")
rows = [
    ("Patient access (no smartphone needed)", "USSD & SMS via Africa's Talking API"),
    ("Backend / API", "Python — FastAPI (SQLAlchemy, Alembic migrations)"),
    ("AI / ML", "Python — gradient-boosting triage classifier + time-series slot-demand forecast"),
    ("Database", "PostgreSQL (production) / SQLite (offline demo) — same models"),
    ("Facility dashboard", "React.js, mobile-first for low-end Android tablets/phones"),
    ("Patient app", "Installable PWA (works on 2G, no app-store dependency)"),
    ("Hosting", "Lightweight cloud (uvicorn) behind Cloudflare tunnel — small payloads on weak links"),
]
x0, y0 = Inches(0.7), Inches(1.5)
rowh = Inches(0.72)
for i, (layer, tech) in enumerate(rows):
    y = y0 + i * rowh
    bg = LIGHT if i % 2 == 0 else WHITE
    rect(s, x0, y, Inches(12), rowh, bg)
    text(s, x0 + Inches(0.2), y + Inches(0.12), Inches(4.3), rowh,
         [(layer, 14, True, BLUE_DARK)])
    text(s, x0 + Inches(4.7), y + Inches(0.12), Inches(7.1), rowh,
         [(tech, 14, False, INK)])

# ── 7. Architecture ─────────────────────────────────────────────────────────
s = prs.slides.add_slide(BLANK)
header(s, "Technical architecture", "Single FastAPI service · SQLite/PostgreSQL · Africa's Talking · runs offline-first")
arch = HERE / "assets" / "architecture.png"
if arch.exists():
    from PIL import Image as PILImage

    with PILImage.open(arch) as im:
        iw, ih = im.size
    max_w = Inches(12.3)
    max_h = Inches(5.4)
    scale = min(max_w / iw, max_h / ih)
    w, h = Emu(int(iw * scale)), Emu(int(ih * scale))
    s.shapes.add_picture(str(arch), (SW - w) // 2, Inches(1.35), width=w, height=h)

# ── 8. Traction / build state ───────────────────────────────────────────────
s = prs.slides.add_slide(BLANK)
header(s, "Working prototype — end to end, today")
kpi_card(s, Inches(0.7), Inches(1.5), Inches(2.9), Inches(1.6), "6", "USSD menus: triage, book, my appointments, facility search, health guide, opt-out")
kpi_card(s, Inches(3.8), Inches(1.5), Inches(2.9), Inches(1.6), "5", "Seeded facilities across Dodoma, Morogoro & Singida regions")
kpi_card(s, Inches(6.9), Inches(1.5), Inches(2.9), Inches(1.6), "4", "Apps in one: USSD · patient PWA · nurse dashboard · SMS reminders")
kpi_card(s, Inches(10.0), Inches(1.5), Inches(2.9), Inches(1.6), "2", "Channels for USSD: live Africa's Talking callback + built-in simulator")
bullets(s, Inches(0.7), Inches(3.5), Inches(12), [
    ("Full data model: ", "patients (incl. anonymous), facilities + services, slots, appointments, queue entries, triage sessions — all Alembic-migrated."),
    ("Integrations live: ", "Africa's Talking USSD + SMS reminders with dedup, Cloudflare tunnel for a public HTTPS URL on demo day."),
    ("Deployable anywhere: ", "uvicorn + SQLite works on a laptop with no internet — important for rural clinics."),
    ("Honest prototype: ", "clearly labelled not-for-clinical-use; triage rules need medical sign-off before real patients."),
])

# ── 9. Impact ───────────────────────────────────────────────────────────────
s = prs.slides.add_slide(BLANK)
header(s, "Impact — why this matters for Tanzania")
bullets(s, Inches(0.7), Inches(1.5), Inches(12), [
    ("Cuts waiting time. ", "Pre-arrival triage + booked slots mean stable, predictable visits instead of 5am queues."),
    ("Catches emergencies earlier. ", "RED flags surface before the patient joins the line — the nurse sees them first on the dashboard."),
    ("Includes everyone. ", "Feature phones, walk-ins and SIM-less patients use the same fair system."),
    ("Gives clinics evidence. ", "Forecasts demand per slot; the fairness report turns equity from a slogan into a metric."),
    ("Scales by SMS. ", "No app downloads, no data bundles — the channel Tanzania already uses for everything."),
])

# ── 9b. Success metrics (kutoka pendekezo) ─────────────────────────────────
s = prs.slides.add_slide(BLANK)
header(s, "Success looks like", "The exact metrics from our proposal — measured before/after the pilot")
bullets(s, Inches(0.7), Inches(1.5), Inches(12), [
    ("Reduced average physical wait time. ", "Baseline vs post-pilot, measured in minutes at the facility (analytics already records every wait)."),
    ("Correct deferral rate. ", "% of USSD triage sessions that correctly deferred non-urgent cases to self-care or a booked slot — validated against clinician review (feedback loop is live)."),
    ("Flatter demand curve. ", "Smaller gap between peak-hour and off-peak volume after slot adoption — the forecast shows expected wait per slot to steer patients off the 6–9 AM peak."),
    ("Adoption rate. ", "Patients per week using USSD booking vs walk-in, plus repeat usage (tracked per patient)."),
    ("Zero missed emergencies. ", "No case where a true emergency was delayed by triage or queue flow — audited via emergency-bypass flags and facility incident review."),
])

# ── 10. Roadmap ─────────────────────────────────────────────────────────────
s = prs.slides.add_slide(BLANK)
header(s, "Roadmap")
bullets(s, Inches(0.7), Inches(1.5), Inches(12), [
    ("Now (hackathon). ", "USSD triage + booking, nurse dashboard, fairness report, SMS reminders — all working."),
    ("Next 3 months. ", "Pilot with 2–3 public dispensaries; medical board review of triage rules; voice (IVR) menu for low literacy."),
    ("Next 6 months. ", "Retrain triage on real clinician feedback; integrate CHAT/WhatsApp channel; county-level demand dashboards."),
    ("12 months. ", "District health authority deployments; open fairness metrics published per facility."),
])

# ── 11. Ask ─────────────────────────────────────────────────────────────────
s = prs.slides.add_slide(BLANK)
header(s, "The ask")
bullets(s, Inches(0.7), Inches(1.5), Inches(12), [
    ("Pilot partners. ", "Public clinics willing to run a 90-day pilot with the nurse dashboard and USSD line."),
    ("Clinical review. ", "Medical professionals to sign off (and challenge) the triage rules — a stated condition of this prototype."),
    ("Mentorship on compliance. ", "Tanzania Medicines and Medical Devices Authority (TMDA) and data-protection (PDPA) pathways."),
    ("Follow-on support. ", "Compute credits and Africa's Talking credits to keep the demo line alive past the hackathon."),
])
text(s, Inches(0.7), Inches(5.9), Inches(12), Inches(1.0),
     [("Afya Smart — because your place in the queue should never depend on who you are.", 18, True, BLUE_DARK),
      ("github.com/emmanuelbarnabas/afya-smart  ·  demo at /demo on the live server", 13, False, GREY)])

prs.save(PPTX)
print("PPTX:", PPTX)

# ── PDF kupitia LibreOffice (headless) ──────────────────────────────────────
soffice = "/snap/bin/libreoffice"
if pathlib.Path(soffice).exists():
    subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(HERE), str(PPTX)],
        check=True, capture_output=True, timeout=180,
    )
    print("PDF:", PDF if PDF.exists() else "(haikuundwa)")
else:
    print("LibreOffice haipo — PPTX pekee imehifadhiwa")
