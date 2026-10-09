#!/usr/bin/env python3
"""Recolor (blue → green) + ongeza animations kwenye presentation ya asili.

Design ya mwanzo inabaka kama ilivyo: mpangilio, nembo, picha, maandishi.
Mabadiliko mawili tu:
  1. Blue zote → kijani (afya) — fills, lines, fonts, gradients, na PNG masks
  2. Entrance animations (fade + rise) kwenye shapes za kila slide
"""
import copy
import io
import re
from PIL import Image
from pptx import Presentation
from pptx.oxml.ns import qn
from lxml import etree

SRC = "/home/karen/afya_pptx_work/Afya Smart Presentation.pptx"
OUT = "/home/karen/Desktop/Afya Smart Presentation (green, animated).pptx"

# ---- ramani ya blue → kijani (afya) ----
# (blue ya awali, kijani mpya)
RGB_MAP = {
    # primary blue → primary green
    "2563EB": "0B7A4B",  # blue-600 → afya primary
    "3B82F6": "189A62",  # blue-500 → green-500
    "60A5FA": "7BC96F",  # blue-400 → lime
    "93C5FD": "A8D9B5",  # blue-300 → light green
    "BFDBFE": "D8EEE0",  # blue-200
    "DBEAFE": "E8F6EF",  # blue-100
    "EFF6FF": "F1F8F4",  # blue-50 → green-50
    # dark blues → deep greens
    "1D4ED8": "085C39",  # blue-700 → primary-dark
    "1E40AF": "084F31",  # blue-800
    "1E3A8A": "063D26",  # blue-900 → deep
    "153E75": "063D26",
    "10305E": "052E1D",
    "0F2A4A": "052E1D",
    # extras
    "172554": "041F14",  # blue-950
    "1E293B": "12281F",  # slate-ish dark
}

def map_rgb(v):
    v = v.upper()
    return RGB_MAP.get(v)

# ---------- 1. XML ya slides: recolor kwa regex ----------
ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}

def recolor_element(root):
    """Badilisha srgbClr zote za blue kwenye element (recursive)."""
    changed = 0
    for clr in root.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}srgbClr"):
        val = clr.get("val")
        new = map_rgb(val) if val else None
        if new:
            clr.set("val", new)
            changed += 1
    # schemeClr: accent1 n.k. — hue-shift za blue themes
    for clr in root.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}schemeClr"):
        val = clr.get("val")
        # schemeClr hue mbaya zinaweza kubaki — hatuna theme ya blue iliyoakisi
        # (LibreOffice conversion ilibadilisha fills kuwa srgbClr nyingi)
    return changed

# ---------- 2. Images: hue-shift blue → green ----------
def recolor_image(img_bytes):
    """Badilisha hue ya piksel za blue kuwa green (images zote za slide)."""
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    px = img.load()
    w, h = img.size
    # kama picha ni ndogo sana au haihusiki (photo), acha
    # heuristics: tintblue kama kuna pixels nyingi za blue-dominant
    blue_count = 0
    sample = min(w * h, 25000)
    step = max(1, (w * h) // sample)
    for idx in range(0, w * h, step):
        x, y = idx % w, idx // w
        r, g, b, a = px[x, y]
        if a > 0 and b > r + 25 and b > g + 15:
            blue_count += 1
    total = len(range(0, w * h, step))
    if total == 0 or blue_count / total < 0.12:
        return img_bytes, False  # si blue-dominant — acha (mf. picha za watu)
    # hue shift: kwa kila pixel ya blue-dominant, zungusha hue kuwa green
    import colorsys
    hsv = img.convert("RGBA").split()
    rgb_img = img.convert("RGB")
    hsv_img = rgb_img.convert("HSV")
    hsv_px = hsv_img.load()
    out = Image.new("RGBA", img.size)
    out_px = out.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                out_px[x, y] = (r, g, b, a)
                continue
            if b > r + 20 and b >= g:  # blue-dominant pixel
                hh, ss, vv = hsv_px[x, y]
                # hue: blue ~170 (0-255 scale) → green ~85
                nh = int(hh * 0.5) % 256
                nr, ng, nb = colorsys.hsv_to_rgb(nh / 255.0, ss / 255.0, vv / 255.0)
                out_px[x, y] = (int(nr), int(ng), int(nb), a)
            else:
                out_px[x, y] = (r, g, b, a)
    buf = io.BytesIO()
    out.save(buf, "PNG")
    return buf.getvalue(), True

# ---------- 3. Animations ----------
ANIM_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"

_id_counter = [100]

def _next_id():
    _id_counter[0] += 1
    return _id_counter[0]

def _fade_par(spid, delay):
    i1, i2, i3 = _next_id(), _next_id(), _next_id()
    return f'''<p:par xmlns:p="{ANIM_NS}" xmlns:a="{A_NS}">
  <p:cTn id="{i1}" presetID="10" presetClass="entr" presetSubtype="0" fill="hold" grpId="0" nodeType="afterEffect">
    <p:stCondLst><p:cond delay="{delay}"/></p:stCondLst>
    <p:childTnLst>
      <p:set>
        <p:cBhvr>
          <p:cTn id="{i2}" dur="1" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn>
          <p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl>
          <p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst>
        </p:cBhvr>
        <p:to><p:strVal val="visible"/></p:to>
      </p:set>
      <p:animEffect transition="in" filter="fade">
        <p:cBhvr>
          <p:cTn id="{i3}" dur="600"/>
          <p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl>
        </p:cBhvr>
      </p:animEffect>
    </p:childTnLst>
  </p:cTn>
</p:par>'''

def _wipe_par(spid, delay, direction="up"):
    i1, i2, i3 = _next_id(), _next_id(), _next_id()
    filt = "wipe(up)" if direction == "up" else "wipe(right)"
    return f'''<p:par xmlns:p="{ANIM_NS}" xmlns:a="{A_NS}">
  <p:cTn id="{i1}" presetID="22" presetClass="entr" presetSubtype="4" fill="hold" grpId="0" nodeType="afterEffect">
    <p:stCondLst><p:cond delay="{delay}"/></p:stCondLst>
    <p:childTnLst>
      <p:set>
        <p:cBhvr>
          <p:cTn id="{i2}" dur="1" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn>
          <p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl>
          <p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst>
        </p:cBhvr>
        <p:to><p:strVal val="visible"/></p:to>
      </p:set>
      <p:animEffect transition="in" filter="{filt}">
        <p:cBhvr>
          <p:cTn id="{i3}" dur="700"/>
          <p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl>
        </p:cBhvr>
      </p:animEffect>
    </p:childTnLst>
  </p:cTn>
</p:par>'''

def animate_slide(slide, index):
    """Ongeza mainSeq ya entrance animations (shapes zinafuatana)."""
    slide_el = slide._element
    # usiongeze mara mbili
    if slide_el.find(qn("p:timing")) is not None:
        existing = slide_el.find(qn("p:timing"))
        slide_el.remove(existing)

    timing = etree.SubElement(slide_el, qn("p:timing"))
    tn_tree = etree.SubElement(timing, qn("p:tnLst"))
    par_root = etree.SubElement(tn_tree, qn("p:par"))
    ctn = etree.SubElement(par_root, qn("p:cTn"))
    ctn.set("id", "1"); ctn.set("dur", "indefinite"); ctn.set("restart", "never")
    ctn.set("nodeType", "tmRoot")
    child = etree.SubElement(ctn, qn("p:childTnLst"))
    seq = etree.SubElement(child, qn("p:seq"))
    seq.set("concurrent", "1"); seq.set("nextAc", "seek")
    seq_ctn = etree.SubElement(seq, qn("p:cTn"))
    seq_ctn.set("id", "2"); seq_ctn.set("dur", "indefinite")
    seq_ctn.set("nodeType", "mainSeq")
    seq_child = etree.SubElement(seq_ctn, qn("p:childTnLst"))

    # shapes za ku-animate: ukipuuza background rectangles kubwa sana
    shapes = []
    for sh in slide.shapes:
        w = sh.width or 0
        h = sh.height or 0
        # background zikubwa (inashika slide nzima) zisifade — zibaki
        if w > 11_500_000 and h > 6_000_000:
            continue
        if sh.has_text_frame and not sh.text_frame.text.strip() and sh.shape_type == 1:
            # empty autoshape (deco) — fade fupi tu
            pass
        shapes.append(sh)

    delay = 0
    for i, sh in enumerate(shapes):
        kind = "wipe" if i == 0 else ("fade" if i % 3 else "wipe")
        xml = _wipe_par(sh.shape_id, delay) if kind == "wipe" else _fade_par(sh.shape_id, delay)
        par_el = etree.fromstring(xml)
        seq_child.append(par_el)
        delay += 250
        if delay > 2500:
            delay = 2500  # isizidi — mwisho wa chain

    # prev/next conds
    for tag, evt in (("p:prevCondLst", "onPrev"), ("p:nextCondLst", "onNext")):
        cl = etree.SubElement(seq, qn(tag))
        cond = etree.SubElement(cl, qn("p:cond"))
        e = etree.SubElement(cond, qn("p:evt")); e.text = evt
        d = etree.SubElement(cond, qn("p:delay")); d.text = "0"
        tg = etree.SubElement(cond, qn("p:tgtEl"))
        etree.SubElement(tg, qn("p:sldTgt"))


# ---------- MAIN ----------
prs = Presentation(SRC)
total_clr = 0
total_img = 0

for idx, slide in enumerate(prs.slides, 1):
    slide_el = slide._element

    # 1. XML recolor (fills, lines, fonts, gradient stops)
    n = recolor_element(slide_el)
    total_clr += n

    # 2. Images recolor (blue→green hue shift)
    for sh in slide.shapes:
        if sh.shape_type == 13:  # PICTURE
            try:
                blob = sh.image.blob
                new_bytes, changed = recolor_image(blob)
                if changed:
                    # badilisha image part yenyewe
                    image_part = sh.image._image_part if hasattr(sh.image, "_image_part") else None
                    from pptx.parts.image import Image as PPTXImage
                    # njia rahisi: replace blob kwenye part
                    part = sh.part.related_part(sh._element.blip_rId)
                    part._blob = new_bytes
                    total_img += 1
            except Exception as e:
                print(f"  slide {idx}: image skip ({e})")

    # 3. Animations
    animate_slide(slide, idx)

prs.save(OUT)
print(f"saved: {OUT}")
print(f"recolors (XML): {total_clr}, images recolored: {total_img}")
