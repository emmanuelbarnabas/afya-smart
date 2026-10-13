"""Tengeneza icon za mfumo (moyo + ECG pulse) bila PIL — PNG halisi.

Muundo SAWA na logo.svg / Logo.jsx (viewBox 64):
  * kisanduku cha kijani cha gradient (#16a066 → #085c39), pembe za mviringo
  * moyo mweupe katikati (implicit heart curve)
  * mstari wa ECG unaokatiza moyo — rangi ya background (cut) ili uonekane
    kama mstari unapita ndani ya moyo, na usionekane nje yake

Hufanya supersampling 3x kwa anti-aliasing laini, kisha inahifadhi ukubwa
halisi: backend (512/192/180/32) + mobile PWA (192/512/maskable/180).

Run: python3 backend/scripts/gen_icons.py
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_OUT = Path(__file__).resolve().parents[1] / "app" / "static"
_MOBILE_OUT = _ROOT / "mobile" / "public"

# Rangi za theme (sawa na .brand-mark ya dashibodi: #16a066 → #085c39)
GREEN_TOP = (22, 160, 102)    # #16a066
GREEN_BOTTOM = (8, 92, 57)    # #085c39
WHITE = (255, 255, 255)

# Moyo: (hx² + hy² − 1)³ − hx²·hy³ ≤ 0 (y + juu; hy=0 ni kiwango cha kando)
_HEART_CX = 0.5
_HEART_Y0 = 0.5496   # y ambapo hy = 0 (imeletwa ili moyo ulingane na wa SVG)
_HEART_S = 0.229     # scale — upana ≈ 0.53 ya tile (kama SVG 34/64)

# Pulse (ECG): pointi za mstari kwa coords ya tile (SVG path ÷ 64)
_PULSE_PTS = [
    (0.1094, 0.4844),  # M7 31
    (0.2969, 0.4844),  # H19
    (0.3516, 0.3750),  # L22.5 24 (piko juu)
    (0.4141, 0.6094),  # L26.5 39 (piko chini)
    (0.4844, 0.4141),  # L31 26.5
    (0.5313, 0.4844),  # L34 31
    (0.8906, 0.4844),  # H57
]
_PULSE_HALF_W = 0.03125  # stroke-width 4/64 ÷ 2

_TILE_RADIUS = 0.3125    # rx 20/64 — kama logo.svg
_MASKABLE_ZOOM = 1.25     # artwork ndani ya safe zone ya 80% (maskable icons)


def _write_png(path: Path, w: int, h: int, rgba_rows: list[bytes]) -> None:
    raw = b"".join(b"\x00" + row for row in rgba_rows)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def _inside_rounded_square(x: float, y: float, r: float) -> bool:
    """Ukanda wa mraba wa pembe za mviringo (0..1)."""
    if 0 <= x <= 1 and 0 <= y <= 1:
        cx = min(max(x, r), 1 - r)
        cy = min(max(y, r), 1 - r)
        return (x - cx) ** 2 + (y - cy) ** 2 <= r * r
    return False


def _inside_heart(x: float, y: float) -> bool:
    """Moyo wa implicit curve (kama wa SVG) — coords ya tile (0..1), y + chini."""
    hx = (x - _HEART_CX) / _HEART_S
    hy = (_HEART_Y0 - y) / _HEART_S  # flip: screen y = chini, curve y = juu
    if hx < -1.2 or hx > 1.2 or hy < -1.05 or hy > 1.3:
        return False  # epua hesabu nyingi kwa pixels za nje
    return (hx * hx + hy * hy - 1.0) ** 3 - hx * hx * hy**3 <= 0


def _pulse_y(x: float) -> float | None:
    """y ya mstari wa ECG kwa x (0..1) — None pale uko nje ya mstari."""
    if x < _PULSE_PTS[0][0] or x > _PULSE_PTS[-1][0]:
        return None
    for (x0, y0), (x1, y1) in zip(_PULSE_PTS, _PULSE_PTS[1:]):
        if x <= x1:
            t = (x - x0) / (x1 - x0) if x1 > x0 else 0.0
            return y0 + (y1 - y0) * t
    return _PULSE_PTS[-1][1]


def _tile_color(x: float, y: float) -> tuple[int, int, int]:
    """Gradient ya diagonali ya kijani (coords ya screen — background nzima)."""
    t = (x + y) / 2
    return tuple(
        int(GREEN_TOP[i] + (GREEN_BOTTOM[i] - GREEN_TOP[i]) * t) for i in range(3)
    )


def _sample(x: float, y: float, radius: float, zoom: float) -> tuple[int, int, int, int]:
    """Rangi ya pixel moja (x,y kati ya 0..1)."""
    if radius > 0 and not _inside_rounded_square(x, y, radius):
        return (0, 0, 0, 0)
    # Artwork coords (maskable: artwork ndani ya 80% ya safe zone)
    ax = 0.5 + (x - 0.5) * zoom
    ay = 0.5 + (y - 0.5) * zoom
    color = _tile_color(x, y)  # gradient ya background inashika screen zima
    if _inside_heart(ax, ay):
        color = WHITE
        ecg = _pulse_y(ax)
        if ecg is not None and abs(ay - ecg) < _PULSE_HALF_W:
            color = _tile_color(x, y)  # cut: mstari wa ECG = rangi ya background
    return (*color, 255)


def render(size: int, radius: float, zoom: float, ss: int = 3) -> list[bytes]:
    rows: list[bytes] = []
    for py in range(size):
        row = bytearray()
        for px in range(size):
            acc = [0, 0, 0, 0]
            for sy in range(ss):
                for sx in range(ss):
                    x = (px + (sx + 0.5) / ss) / size
                    y = (py + (sy + 0.5) / ss) / size
                    s = _sample(x, y, radius, zoom)
                    for i in range(4):
                        acc[i] += s[i]
            n = ss * ss
            row += bytes((acc[i] + n // 2) // n for i in range(4))
        rows.append(bytes(row))
    return rows


# (out_dir, jina, size, radius, zoom)
_TARGETS = [
    # Backend — favicon/brand (radius kama logo.svg; apple-touch full-bleed kwa iOS)
    (_BACKEND_OUT, "icon-512.png", 512, _TILE_RADIUS, 1.0),
    (_BACKEND_OUT, "icon-192.png", 192, _TILE_RADIUS, 1.0),
    (_BACKEND_OUT, "apple-touch-icon.png", 180, 0.0, 1.0),
    (_BACKEND_OUT, "icon-32.png", 32, _TILE_RADIUS, 1.0),
    # Mobile PWA — maskable lazima iwe full-bleed + artwork kwenye safe zone
    (_MOBILE_OUT, "pwa-192.png", 192, _TILE_RADIUS, 1.0),
    (_MOBILE_OUT, "pwa-512.png", 512, _TILE_RADIUS, 1.0),
    (_MOBILE_OUT, "pwa-maskable-512.png", 512, 0.0, _MASKABLE_ZOOM),
    (_MOBILE_OUT, "apple-touch-icon.png", 180, 0.0, 1.0),
]


def main() -> None:
    for out_dir, name, size, radius, zoom in _TARGETS:
        out_dir.mkdir(parents=True, exist_ok=True)
        _write_png(out_dir / name, size, size, render(size, radius, zoom))
        print(f"OK {out_dir}/{name} ({size}x{size})")


if __name__ == "__main__":
    main()
