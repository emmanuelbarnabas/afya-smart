#!/usr/bin/env python3
"""Recolor ya pili: slide XML zote (pamoja na backgrounds `<p:bg>`),
masters, layouts, theme — kila srgbClr ya blue → kijani."""
import re
import zipfile
import shutil

SRC = "/home/karen/Desktop/Afya Smart Presentation (green, animated).pptx"
TMP = "/home/karen/afya_pptx_work/recolored2.pptx"

RGB_MAP = {
    "2563EB": "0B7A4B", "3B82F6": "189A62", "60A5FA": "7BC96F",
    "93C5FD": "A8D9B5", "BFDBFE": "D8EEE0", "DBEAFE": "E8F6EF",
    "EFF6FF": "F1F8F4",
    "1D4ED8": "085C39", "1E40AF": "084F31", "1E3A8A": "063D26",
    "153E75": "063D26", "10305E": "052E1D", "0F2A4A": "052E1D",
    "172554": "041F14", "1E293B": "12281F",
    # blues za giza zilizoachwa (backgrounds za slides)
    "0B1F3F": "07301E",
    "0F2A5C": "07301E",
    "12315F": "083A24",
    "0A1F44": "06281A",
    "0C224A": "062C1C",
    "0D1F3C": "052418",
}

count = 0

def recolor_xml(xml: str) -> str:
    global count

    def repl(m):
        global count
        hexv = m.group(1).upper()
        new = RGB_MAP.get(hexv)
        if new:
            count += 1
            return f'srgbClr val="{new}"'
        return m.group(0)

    return re.sub(r'srgbClr val="([0-9A-Fa-f]{6})"', repl, xml)


with zipfile.ZipFile(SRC, "r") as zin, zipfile.ZipFile(TMP, "w", zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        if item.filename.endswith(".xml") and (
            item.filename.startswith(("ppt/slides/", "ppt/slideLayouts/", "ppt/slideMasters/", "ppt/theme/"))
        ):
            xml = data.decode("utf-8", "ignore")
            xml = recolor_xml(xml)
            data = xml.encode("utf-8")
        zout.writestr(item, data)

shutil.move(TMP, SRC)
print(f"XML recolors: {count}")
print("saved:", SRC)
