#!/usr/bin/env python3
"""Tengeneza icons za PWA ya Afya Smart Mobile (192, 512, maskable, apple 180)."""
from PIL import Image, ImageDraw

GREEN = (11, 122, 75)      # --primary #0b7a4b
GREEN_DARK = (8, 92, 57)   # --primary-dark #085c39
WHITE = (255, 255, 255)

OUT = "mobile/public"


def phone_bg(size: int) -> Image.Image:
    img = Image.new("RGB", (size, size), GREEN)
    d = ImageDraw.Draw(img)
    # Gradient rahisi: safu za kijani kilidogo chini
    for y in range(size):
        t = y / size
        r = int(GREEN[0] + (GREEN_DARK[0] - GREEN[0]) * t)
        g = int(GREEN[1] + (GREEN_DARK[1] - GREEN[1]) * t)
        b = int(GREEN[2] + (GREEN_DARK[2] - GREEN[2]) * t)
        d.line([(0, y), (size, y)], fill=(r, g, b))
    return img


def draw_phone(img: Image.Image, scale: float = 1.0) -> Image.Image:
    """Chora simu nyeupe (full-bleed) juu ya background."""
    size = img.width
    d = ImageDraw.Draw(img)
    s = scale
    # Body ya simu (rounded rectangle nyeupe)
    bw, bh = int(260 * s), int(430 * s)
    x0, y0 = (size - bw) // 2, (size - bh) // 2
    d.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], radius=int(38 * s), fill=WHITE)
    # Screen ya kijani kilidogo
    m = int(16 * s)
    sx0, sy0 = x0 + m, y0 + int(52 * s)
    sx1, sy1 = x0 + bw - m, y0 + bh - int(96 * s)
    d.rounded_rectangle([sx0, sy0, sx1, sy1], radius=int(12 * s), fill=GREEN_DARK)
    # Mistari ya "USSD message" kwenye screen
    line_h = int(12 * s)
    pad = int(18 * s)
    for i, w in enumerate([0.78, 0.55, 0.66]):
        ly = sy0 + pad + i * (line_h + int(10 * s))
        d.rounded_rectangle(
            [sx0 + pad, ly, sx0 + pad + int((sx1 - sx0 - 2 * pad) * w), ly + line_h],
            radius=line_h // 2,
            fill=WHITE,
        )
    # Keypad: dots 12 (grid 3x4)
    dot = int(26 * s)
    cols, rows = 3, 4
    gy0 = sy1 + int(14 * s)
    gap_x = (bw - 2 * m - cols * dot) // (cols - 1)
    gap_y = int(10 * s)
    for r_ in range(rows):
        for c in range(cols):
            cx = x0 + m + c * (dot + gap_x)
            cy = gy0 + r_ * (dot + gap_y)
            d.ellipse([cx, cy, cx + dot, cy + dot], fill=GREEN)
    # Call button (ya kijani, ndefu)
    by = gy0 + rows * (dot + gap_y) + int(6 * s)
    d.rounded_rectangle([x0 + m, by, x0 + bw - m, by + int(34 * s)], radius=int(17 * s), fill=GREEN)
    return img


def make(size: int, name: str, maskable: bool = False) -> None:
    img = phone_bg(size)
    if maskable:
        # Safe zone ya maskable: content ≤ 80% ya kati
        draw_phone(img, scale=0.62)
    else:
        draw_phone(img, scale=0.82)
    img.save(f"{OUT}/{name}", "PNG", optimize=True)
    print(f"ok: {OUT}/{name}")


if __name__ == "__main__":
    import os

    os.makedirs(OUT, exist_ok=True)
    make(192, "pwa-192.png")
    make(512, "pwa-512.png")
    make(512, "pwa-maskable-512.png", maskable=True)
    make(180, "apple-touch-icon.png")
