#!/usr/bin/env python3
"""Conceptual diagram ya Afya Smart — RAFIUPI: hatua 4 wima + chips za maamuzi.
Picha halisi 2 kutoka deck (stethoscope + muuguzi) zimekatwa duara."""
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

W, H = 1800, 1350
BG = (243, 248, 246)
GREEN = (11, 122, 75)
GREEN_DARK = (8, 92, 57)
GREEN_DEEP = (7, 58, 37)
LIME = (123, 201, 111)
AMBER = (224, 152, 28)
RED = (192, 57, 43)
INK = (20, 43, 34)
MUTED = (95, 113, 109)
WHITE = (255, 255, 255)
CARD = (255, 255, 255)
EDGE = (214, 228, 221)

MEDIA = "/home/karen/afya_pptx_work/odp_pics"
# Picha halisi (originals za ODP — hazijagusa na recolor):
# - A778B530.jpg: mkono wa mgonjwa akihudumia simu (daktari navyo background)
# - C03E9EC47.jpg: mkono wa daktari + stethoskopi + laptop
# - BEED1BD5.jpg: muuguzi akishauri mgonjwa
PH_PATIENT = f"{MEDIA}/100000000000012C0000012CA778B530.jpg"
PH_TRIAGE = f"{MEDIA}/10000000000003200000012C03E9EC47.jpg"
PH_NURSE = f"{MEDIA}/100000000000025800000190BEED1BD5.jpg"

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)


def font(size, bold=False):
    for p in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


F_TITLE = font(46, True)
F_SUB = font(21)
F_HEAD = font(27, True)
F_BODY = font(20)
F_SMALL = font(17)
F_CHIP = font(21, True)
F_CHIP_SUB = font(15)

# ---------- Title ----------
d.text((80, 50), "Afya Smart — How it works", font=F_TITLE, fill=GREEN_DEEP)
d.text((80, 118), "From the first symptom to the right care — on any phone",
       font=F_SUB, fill=MUTED)
d.rectangle([80, 160, 300, 170], fill=AMBER)

CX = W // 2  # 900

# ---------- picha duara (kushoto: stethoscope, kulia: muuguzi) ----------
def circle_photo(path, cx, cy, r):
    ph = Image.open(path).convert("RGB")
    # crop square kutoka kati
    w, h = ph.size
    s = min(w, h)
    ph = ph.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2))
    ph = ph.resize((2 * r, 2 * r), Image.LANCZOS)
    mask = Image.new("L", (2 * r, 2 * r), 0)
    md = ImageDraw.Draw(mask)
    md.ellipse([0, 0, 2 * r, 2 * r], fill=255)
    img.paste(ph, (cx - r, cy - r), mask)
    # ring
    d.ellipse([cx - r - 5, cy - r - 5, cx + r + 5, cy + r + 5],
              outline=GREEN, width=5)


# ---------- hatua za wima ----------
def step_box(cy, w, h, title, sub, fill, txt=WHITE, sub_txt=None):
    x = CX - w // 2
    # shadow nyepesi
    d.rounded_rectangle([x + 4, cy - h // 2 + 6, x + w + 4, cy + h // 2 + 6],
                        radius=20, fill=(205, 216, 210))
    d.rounded_rectangle([x, cy - h // 2, x + w, cy + h // 2],
                        radius=20, fill=fill)
    center_text_local = lambda t, yy, f, c: d.text(
        (CX - (d.textbbox((0, 0), t, font=f)[2] - d.textbbox((0, 0), t, font=f)[0]) // 2, yy),
        t, font=f, fill=c)
    center_text_local(title, cy - h // 2 + (18 if sub else 0) - (0 if sub else 16), F_HEAD, txt)
    if sub:
        center_text_local(sub, cy + h // 2 - 52, F_SMALL, sub_txt or (205, 235, 218))
    return x, cy - h // 2, w, h


def arrow_down(y1, y2, color=GREEN):
    d.line([(CX, y1), (CX, y2 - 14)], fill=color, width=6)
    d.polygon([(CX - 15, y2 - 16), (CX + 15, y2 - 16), (CX, y2)], fill=color)


# ===== HATUA 1: MGONJWA =====
y = 280
circle_photo(PH_PATIENT, 260, y, 110)   # mkono na simu — picha halisi
step_box(y, 640, 110, "1 · PATIENT DIALS", "Dials *384*37894# on any phone — no internet needed",
         GREEN_DEEP)
# kushoto: mstari kutoka picha kwenda box
d.line([(378, y), (CX - 320, y)], fill=GREEN, width=4)

arrow_down(y + 55, y + 130)

# ===== HATUA 2: USSD GATEWAY =====
y = y + 130
step_box(y, 640, 110, "2 · USSD GATEWAY", "Africa's Talking API calls the Afya Smart backend",
         GREEN)
arrow_down(y + 55, y + 130)

# ===== HATUA 3: ML TRIAGE =====
y = y + 130
step_box(y, 640, 120, "3 · AI TRIAGE", "4–6 questions → ML model (89% accuracy)",
         GREEN_DARK)
circle_photo(PH_TRIAGE, W - 280, y, 130)  # daktari + stethoscope + laptop — picha halisi
d.line([(CX + 320, y), (W - 280 - 130 - 8, y)], fill=GREEN, width=4)
arrow_down(y + 60, y + 130)

# ===== HATUA 4: MAAMUZI (chips 4) =====
y = y + 130
d.text((CX - (d.textbbox((0, 0), "4 · INSTANT GUIDANCE", font=F_HEAD)[2] // 2), y - 46),
       "4 · INSTANT GUIDANCE", font=F_HEAD, fill=INK)

chips = [
    ("EMERGENCY", "Go now / call 112", RED),
    ("URGENT", "Priority queue", AMBER),
    ("ROUTINE", "Book a slot", GREEN),
    ("SELF-CARE", "Home advice", GREEN_DARK),
]
cw, ch, gap = 380, 86, 30
total_w = 4 * cw + 3 * gap
x0 = CX - total_w // 2
cy = y + 10
for i, (name, sub, color) in enumerate(chips):
    x = x0 + i * (cw + gap)
    d.rounded_rectangle([x + 4, cy + 6, x + cw + 4, cy + ch + 6], radius=16,
                        fill=(205, 216, 210))
    d.rounded_rectangle([x, cy, x + cw, cy + ch], radius=16, fill=CARD,
                        outline=color, width=4)
    tb = d.textbbox((0, 0), name, font=F_CHIP)
    d.text((x + (cw - tb[2]) // 2, cy + 14), name, font=F_CHIP, fill=color)
    tb2 = d.textbbox((0, 0), sub, font=F_CHIP_SUB)
    d.text((x + (cw - tb2[2]) // 2, cy + 50), sub, font=F_CHIP_SUB, fill=MUTED)

# arrow chini kwenda facility
arrow_down(cy + ch, cy + ch + 60)

# ===== ROW 5: FACILITY (dashboard + analytics + picha halisi) =====
fy = cy + ch + 130
# picha kubwa ya muuguzi kushoto
circle_photo(PH_NURSE, 280, fy + 20, 150)
d.line([(438, fy + 20), (560, fy + 20)], fill=GREEN, width=4)

# dashboard box
bx, bw, bh = 560, 560, 230
d.rounded_rectangle([bx + 4, fy - bh // 2 + 6, bx + bw + 4, fy + bh // 2 + 6],
                    radius=20, fill=(205, 216, 210))
d.rounded_rectangle([bx, fy - bh // 2, bx + bw, fy + bh // 2], radius=20,
                    fill=GREEN_DEEP)
def ctext(t, yy, f, c):
    tb = d.textbbox((0, 0), t, font=f)
    d.text((bx + (bw - tb[2]) // 2, yy), t, font=f, fill=c)
ctext("FACILITY", fy - bh // 2 + 24, F_HEAD, LIME)
ctext("Live queue + emergency bypass", fy - bh // 2 + 78, F_BODY, (210, 236, 222))
ctext("Call next · clinician feedback", fy - bh // 2 + 112, F_BODY, (210, 236, 222))
ctext("SMS reminders before visit", fy - bh // 2 + 146, F_BODY, (210, 236, 222))

# analytics box
ax = 1160
d.rounded_rectangle([ax + 4, fy - bh // 2 + 6, ax + bw + 4, fy + bh // 2 + 6],
                    radius=20, fill=(205, 216, 210))
d.rounded_rectangle([ax, fy - bh // 2, ax + bw, fy + bh // 2], radius=20,
                    fill=GREEN_DARK)
def ctext2(t, yy, f, c):
    tb = d.textbbox((0, 0), t, font=f)
    d.text((ax + (bw - tb[2]) // 2, yy), t, font=f, fill=c)
ctext2("ANALYTICS", fy - bh // 2 + 24, F_HEAD, LIME)
ctext2("Wait times · demand curve", fy - bh // 2 + 78, F_BODY, (210, 236, 222))
ctext2("Triage accuracy + safety alert", fy - bh // 2 + 112, F_BODY, (210, 236, 222))
ctext2("Model retrains from feedback", fy - bh // 2 + 146, F_BODY, (210, 236, 222))

# link kati ya dashboard na analytics
d.line([(bx + bw + 8, fy), (ax - 8, fy)], fill=AMBER, width=5)
d.polygon([(ax - 26, fy - 13), (ax - 26, fy + 13), (ax - 8, fy)], fill=AMBER)
d.polygon([(bx + bw + 26, fy - 13), (bx + bw + 26, fy + 13), (bx + bw + 8, fy)], fill=AMBER)

# ---------- footer note ----------
d.rounded_rectangle([280, H - 90, W - 280, H - 34], radius=14,
                    fill=(226, 243, 233), outline=(178, 214, 196))
t = "One FastAPI backend serves the patient app, the facility dashboard and the installable USSD PWA"
tb = d.textbbox((0, 0), t, font=F_BODY)
d.text(((W - tb[2]) // 2, H - 78), t, font=F_BODY, fill=GREEN_DARK)

OUT = "/home/karen/Desktop/afya-smart-conceptual-diagram.png"
img.save(OUT, "PNG")
print("saved:", OUT, img.size)
