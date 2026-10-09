#!/usr/bin/env python3
"""Recolor media zote za pptx (backgrounds + picha): blue → green hue-shift."""
import io
import zipfile
import shutil
from PIL import Image
import colorsys

SRC = "/home/karen/Desktop/Afya Smart Presentation (green, animated).pptx"
TMP = "/home/karen/afya_pptx_work/recolored.pptx"


def hue_shift_image(data):
    """Blue-dominant pixels → green. Picha za watu/mazingira (si blue) zinabaki."""
    try:
        img = Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:
        return data, False
    w, h = img.size
    if w < 8 or h < 8:
        return data, False
    px = img.load()
    # sampili: je picha iko blue-dominant?
    blue = 0
    total = 0
    step = max(1, (w * h) // 30000)
    for idx in range(0, w * h, step):
        x, y = (idx % w), (idx // w)
        r, g, b, a = px[x, y]
        total += 1
        if a > 0 and b > r + 20 and b >= g:
            blue += 1
    if total == 0 or blue / total < 0.10:
        return data, False  # si blue-heavy — acha (picha halisi za watu nk.)

    hsv = img.convert("RGB").convert("HSV")
    hsv_px = hsv.load()
    out = img.copy()
    out_px = out.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            if b > r + 20 and b >= g:  # blue pixel
                hh, ss, vv = hsv_px[x, y]
                nh = int(hh * 0.52) % 256  # zungusha hue kwenda kijani
                nr, ng, nb = colorsys.hsv_to_rgb(nh / 255.0, ss / 255.0, vv / 255.0)
                out_px[x, y] = (int(nr), int(ng), int(nb), a)
    buf = io.BytesIO()
    is_png = data[:8] == b"\x89PNG\r\n\x1a\n"
    if is_png:
        out.save(buf, "PNG")
    else:
        out.convert("RGB").save(buf, "JPEG", quality=92)
    return buf.getvalue(), True


changed = 0
kept = 0
with zipfile.ZipFile(SRC, "r") as zin, zipfile.ZipFile(TMP, "w", zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        if item.filename.startswith("ppt/media/") and item.filename.lower().endswith(
            (".png", ".jpg", ".jpeg")
        ):
            new, did = hue_shift_image(data)
            if did:
                changed += 1
                data = new
            else:
                kept += 1
        zout.writestr(item, data)

shutil.move(TMP, SRC)
print(f"media recolored: {changed}, left as-is: {kept}")
print("saved:", SRC)
