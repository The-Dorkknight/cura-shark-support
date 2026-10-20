# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Draw the project icon (a fin under a tilted slab) at several sizes. Needs Pillow.

python3 tools/make_icons.py
Writes icons/icon-<size>.png, docs/images/icon-512.png, apple-touch-icon.png, favicon-64.png.
PNG only on purpose: an SVG icon attribute once crashed Cura at start-up for another plugin.
"""
import math
import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def draw(size: int) -> Image.Image:
    s = 4 * size                                  # draw big, scale down for smooth edges
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = int(s * 0.2)
    d.rounded_rectangle([0, 0, s - 1, s - 1], r, fill=(17, 24, 39, 255))
    base = s * 0.80
    # slab tilted 35 degrees
    a = math.radians(35)
    x0, y0 = s * 0.14, base
    L = s * 0.78
    x1, y1 = x0 + L * math.cos(a), y0 - L * math.sin(a)
    t = s * 0.10
    nx, ny = -math.sin(a) * t, -math.cos(a) * t
    d.polygon([(x0, y0), (x1, y1), (x1 + nx, y1 + ny), (x0 + nx, y0 + ny)], fill=(156, 163, 175, 255))
    # fin: under the slab, round back edge, small teeth
    pts = [(x0 + s * 0.08, base)]
    n = 7
    for i in range(n + 1):
        q = i / n
        px = x0 + s * 0.08 + q * (L * math.cos(a) * 0.86 - s * 0.08)
        py = y0 - (px - x0) * math.tan(a) + s * (0.035 if i % 2 else 0.012)
        pts.append((px, py))
    tx, ty = pts[-1]
    H = base - ty
    for k in range(1, 13):
        q = k / 12
        pts.append((tx + q * H * 0.42, base - H * math.sqrt(max(0.0, 1 - q * q))))
    d.polygon(pts, fill=(242, 140, 40, 255))
    d.rectangle([s * 0.08, base, s * 0.92, base + s * 0.035], fill=(124, 45, 18, 255))
    return im.resize((size, size), Image.LANCZOS)


def main():
    os.makedirs(os.path.join(ROOT, "icons"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "docs", "images"), exist_ok=True)
    for sz in (16, 32, 48, 64, 128, 256, 512):
        draw(sz).save(os.path.join(ROOT, "icons", "icon-%d.png" % sz))
    draw(512).save(os.path.join(ROOT, "docs", "images", "icon-512.png"))
    draw(180).save(os.path.join(ROOT, "docs", "images", "apple-touch-icon.png"))
    draw(64).save(os.path.join(ROOT, "docs", "images", "favicon-64.png"))
    print("icons written")


if __name__ == "__main__":
    main()
