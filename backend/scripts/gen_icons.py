"""Tengeneza icon za mfumo (herufi 'A' + pulse) bila PIL — PNG halisi.

Muundo SAWA na logo.svg / Logo.jsx (viewBox 64), unatokana na jina "Afya Smart":
  * kisanduku cha kijani cha gradient (#16a066 → #085c39), pembe za mviringo
  * herufi NYEWEPE 'A' (stencil: migu miwili + crossbar) — herufi ya kwanza ya "Afya"
  * mstari wa pulse (ECG) chini ya 'A' — alama ya afya / maisha

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

# Herufi 'A' — quad3 za kila umbo (nukta4 kila moja; ndani ya YOYOTE = ndani)
# Pembe: (topL, topR, botR, botL) kwa coords ya tile (0..1, y + chini)
_A_QUADS = (
    # Mguu wa kushoto (slope −0.5)
    ((0.47, 0.21), (0.53, 0.21), (0.31, 0.65), (0.25, 0.65)),
    # Mguu wa kulia (slope +0.5)
    ((0.47, 0.21), (0.53, 0.21), (0.75, 0.65), (0.69, 0.65)),
    # Crossbar (mraba)
    ((0.35, 0.50), (0.65, 0.50), (0.65, 0.555), (0.35, 0.555)),
)

# Pulse (ECG) chini ya 'A': pointi za mstari kwa coords ya tile (SVG path ÷ 64)
_PULSE_PTS = [
    (0.13, 0.74),    # M8.3 47.4
    (0.42, 0.74),    # H26.9
    (0.465, 0.695),  # L29.8 44.5 (piko juu)
    (0.525, 0.795),  # L33.6 50.9 (piko chini)
    (0.575, 0.74),   # L36.8 47.4
    (0.87, 0.74),    # H55.7
]
_PULSE_HALF_W = 0.026  # stroke-width 3.3/64 ÷ 2

_TILE_RADIUS = 0.3125  # rx 20/64 — kama logo.svg
_MASKABLE_ZOOM = 1.25   # artwork ndani ya safe zone ya 80% (maskable icons)


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


def _in_quad(x: float, y: float, quad) -> bool:
    """Ndani ya polygon ya nukta4 (convex) — ray/orientation ya kulia/zote."""
    sign = 0
    for i in range(4):
        x0, y0 = quad[i]
        x1, y1 = quad[(i + 1) % 4]
        cross = (x1 - x0) * (y - y0) - (y1 - y0) * (x - x0)
        if cross == 0:
            continue
        s = 1 if cross > 0 else -1
        if sign == 0:
            sign = s
        elif s != sign:
            return False
    return True


def _inside_letter_a(x: float, y: float) -> bool:
    """Herufi 'A' — union ya quad3 (migu2 + crossbar)."""
    if x < 0.23 or x > 0.77 or y < 0.19 or y > 0.67:
        return False  # epua hesabu nyingi kwa pixels za nje
    return any(_in_quad(x, y, q) for q in _A_QUADS)


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
    white = False
    if _inside_letter_a(ax, ay):
        white = True
    else:
        ecg = _pulse_y(ax)
        white = ecg is not None and abs(ay - ecg) < _PULSE_HALF_W
    color = WHITE if white else _tile_color(x, y)  # gradient ya background
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
