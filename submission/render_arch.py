"""Render submission/assets/architecture.svg → PNG (hi-dpi) + single-page PDF.

PDF hutengenezwa kutoka PNG kwa Pillow (hakuna kurasa nyingi — picha moja tu).
"""
import pathlib

from PIL import Image
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).parent
SVG = HERE / "assets" / "architecture.svg"
PNG = HERE / "assets" / "architecture.png"
PDF = HERE / "assets" / "architecture.pdf"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1600, "height": 1000}, device_scale_factor=2)
    page.goto(SVG.resolve().as_uri())
    page.wait_for_load_state("networkidle")
    page.screenshot(path=PNG, full_page=True)
    browser.close()

img = Image.open(PNG).convert("RGB")
img.save(PDF, "PDF", resolution=192.0)
print(f"PNG {img.size} + single-page PDF written")
