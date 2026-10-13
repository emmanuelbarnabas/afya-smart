"""Tests za nembo (logo.svg) na icon routes — hazihitaji database."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_logo_svg_served():
    """/logo.svg inarudisha SVG ya nembo (herufi 'A' + ECG pulse) kwa status 200."""
    response = client.get("/logo.svg")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    # Umbo halisi wa logo: mguu wa 'A' (path) + mstari wa ECG (pulse)
    assert "M30.1 13.4" in response.text   # herufi 'A'
    assert "M8.3 47.4" in response.text    # pulse (ECG)


def test_favicon_served_as_png():
    """/favicon.ico inarudisha PNG ya icon (route ya mfumo)."""
    response = client.get("/favicon.ico")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
