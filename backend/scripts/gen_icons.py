"""Tengeneza icon za mfumo (bluu + msalaba mweupe) bila PIL — PNG halisi.

Hufanya supersampling 3x kwa anti-aliasing laini, kisha inahifadhi kwa
ukubwa: 512, 192, 180 (apple-touch) na 32 (favicon).

Run: backend/.venv/bin/python scripts/gen_icons.py
"""
from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "app" / "static"

# Rangi za theme (same blue family as USSD demo accents)
BLUE_TOP = (59, 130, 246)     # #3b82f6
BLUE_BOTTOM = (29, 78, 216)   # #1d4ed8
WHITE = (255, 255, 255)


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


def _inside_cross(x: float, y: float) -> bool:
    """Msalaba wa kimatibabu katikati (1 = pembeni ya ukanda)."""
    arm_half = 0.085   # upana wa mkono
    arm_len = 0.24     # urefu wa mkono kutoka katikati
    dx, dy = abs(x - 0.5), abs(y - 0.5)
    return (dx <= arm_len and dy <= arm_half) or (dy <= arm_len and dx <= arm_half)


def _ecg_y(x: float) -> float | None:
    """Mstari wa ECG (moyo) chini ya msalaba — urefu wa mstari kwa x.

    Rimba (y=0.80) nje ya eneo la spike; spike ya moyo kati ya x=0.34..0.66.
    Rudisha None pale mstari ulipo nje ya eneo la mstari huu.
    """
    if not (0.14 <= x <= 0.86):
        return None
    if x < 0.34 or x > 0.66:
        return 0.80
    # Spike: kupanda → kupanda zaidi (piko) → kupanda chini → kurudi
    if x < 0.42:
        return 0.80 - (x - 0.34) / 0.08 * 0.06          # 0.80 → 0.74
    if x < 0.48:
        return 0.74 - (x - 0.42) / 0.06 * 0.12          # 0.74 → 0.62 (piko juu)
    if x < 0.54:
        return 0.62 + (x - 0.48) / 0.06 * 0.18          # 0.62 → 0.80 (kushuka)
    if x < 0.60:
        return 0.80 - (x - 0.54) / 0.06 * 0.05          # 0.80 → 0.75
    return 0.75 + (x - 0.60) / 0.06 * 0.05              # 0.75 → 0.80


def _sample(x: float, y: float) -> tuple[int, int, int, int]:
    """Rangi ya pixel moja (x,y kati ya 0..1) — gradient bluu + msalaba mweupe."""
    if not _inside_rounded_square(x, y, 0.22):
        return (0, 0, 0, 0)
    t = (x + y) / 2  # gradient ya diagonali
    color = tuple(
        int(BLUE_TOP[i] + (BLUE_BOTTOM[i] - BLUE_TOP[i]) * t) for i in range(3)
    )
    # Mstari mweupe wa ECG (moyo) chini ya msalaba — detail ya kimatibabu
    ecg = _ecg_y(x)
    if _inside_cross(x, y) or (ecg is not None and abs(y - ecg) < 0.014):
        color = WHITE
    return (*color, 255)


def render(size: int, ss: int = 3) -> list[bytes]:
    rows: list[bytes] = []
    for py in range(size):
        row = bytearray()
        for px in range(size):
            acc = [0, 0, 0, 0]
            for sy in range(ss):
                for sx in range(ss):
                    x = (px + (sx + 0.5) / ss) / size
                    y = (py + (sy + 0.5) / ss) / size
                    s = _sample(x, y)
                    for i in range(4):
                        acc[i] += s[i]
            n = ss * ss
            row += bytes((acc[i] + n // 2) // n for i in range(4))
        rows.append(bytes(row))
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for size, name in [
        (512, "icon-512.png"),
        (192, "icon-192.png"),
        (180, "apple-touch-icon.png"),
        (32, "icon-32.png"),
    ]:
        _write_png(OUT / name, size, size, render(size))
        print(f"OK {name} ({size}x{size})")


if __name__ == "__main__":
    main()
