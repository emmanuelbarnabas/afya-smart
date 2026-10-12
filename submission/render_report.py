"""Render submission/technical_report.html → technical_report.pdf (A4, print CSS)."""
import pathlib

from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).parent
HTML = HERE / "technical_report.html"
PDF = HERE / "technical_report.pdf"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto(HTML.resolve().as_uri())
    page.wait_for_load_state("networkidle")
    page.pdf(path=str(PDF), format="A4", print_background=True,
             margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
    browser.close()

print("PDF written:", PDF)
