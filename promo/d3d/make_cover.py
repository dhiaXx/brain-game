#!/usr/bin/env python3
"""Reel cover for the D3D ad (1080x1920).

Everything important sits inside the centred 1080x1440 (3:4) area that the
Instagram profile grid shows, so the cover reads both full-screen and in the grid.

Usage:  python3 promo/d3d/make_cover.py
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from make_d3d_promo import F_BLACK, F_LAB, F_SEMI, INK, YELLOW, font, over, px, text_image

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1080, 1920
WHITE = (255, 255, 255)


def shadowed(txt, fnt, color=WHITE, tracking=-2, strength=0.6):
    t = text_image(txt, fnt, color, tracking)
    pad = 40
    im = Image.new("RGBA", (t.width + 2 * pad, t.height + 2 * pad), (0, 0, 0, 0))
    blk = Image.new("RGBA", t.size, (0, 0, 0, 255))
    blk.putalpha(t.getchannel("A").point(lambda v: int(v * strength)))
    im.alpha_composite(blk, (pad, pad + 8))
    im = im.filter(ImageFilter.GaussianBlur(14))
    im.alpha_composite(t, (pad, pad))
    return im


def boxed(txt, fnt, fg, bg, padx=34, pady=14, radius=18):
    t = text_image(txt, fnt, fg, -1)
    w, h = t.width + 2 * padx, t.height + 2 * pady - 10
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=bg + (255,))
    im.alpha_composite(t, (padx, pady - 8))
    return im


def badge():
    """Round yellow price sticker, slightly rotated."""
    d = 330
    s = 3  # supersample
    im = Image.new("RGBA", (d * s, d * s), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.ellipse([0, 0, d * s - 1, d * s - 1], fill=YELLOW + (255,))
    dr.ellipse([14 * s, 14 * s, (d - 14) * s - 1, (d - 14) * s - 1], outline=INK + (255,), width=4 * s)
    im = im.resize((d, d), Image.LANCZOS)
    top = text_image("SEULEMENT", font(F_LAB, 24), INK, 6)
    price = text_image("3,5", font(F_BLACK, 132), INK, -4)
    unit = text_image("DT / pièce", font(F_BLACK, 40), INK, 0)
    im.alpha_composite(top, (d // 2 - top.width // 2, 62))
    im.alpha_composite(price, (d // 2 - price.width // 2, 88))
    im.alpha_composite(unit, (d // 2 - unit.width // 2, 232))
    return im.rotate(10, resample=Image.BICUBIC, expand=True)


def main():
    src = Image.open(os.path.join(HERE, "photos_ad", "hook_sodip.jpg")).convert("RGB")
    bg = src.resize((W, H), Image.LANCZOS, box=(81, 60, 81 + 1080, 60 + 1920))
    f = np.asarray(bg, np.float32).copy()
    # Readability ramps: darken top and the lower text zone.
    y = np.linspace(0, 1, H, dtype=np.float32)
    ramp = np.maximum(np.clip((0.28 - y) / 0.28, 0, 1) * 0.55,
                      np.clip((y - 0.50) / 0.50, 0, 1) ** 1.2 * 0.80)
    f *= (1 - ramp)[:, None, None]

    # Grid-safe zone: y 240..1680 (3:4 centre crop).
    kicker = boxed("PORTE-CLÉS 3D PERSONNALISÉS", font(F_LAB, 32), INK, YELLOW, 26, 14, 12)
    over(f, kicker, W // 2 - kicker.width // 2, 290)

    b = badge()
    over(f, b, W - b.width - 40, 430)

    h1 = shadowed("Votre logo", font(F_BLACK, 150))
    over(f, h1, W // 2 - h1.width // 2, 1010)
    h2 = boxed("en porte-clés", font(F_BLACK, 140), INK, YELLOW, 38, 18, 22)
    over(f, h2, W // 2 - h2.width // 2, 1010 + h1.height - 40)

    info = shadowed("Dès 20 pcs  ·  Emballage & maquette 3D offerts",
                    font(F_SEMI, 40), WHITE, 0, 0.8)
    iy = 1010 + h1.height - 40 + h2.height + 10
    over(f, info, W // 2 - info.width // 2, iy)

    brand = text_image("D3D", font(F_BLACK, 60), WHITE, 1)
    handle = text_image("@d3d.tn", font(F_SEMI, 40), YELLOW)
    gap = 26
    tw = brand.width + gap + handle.width
    by = 1560
    over(f, brand, W // 2 - tw // 2, by)
    over(f, handle, W // 2 - tw // 2 + brand.width + gap, by + (brand.height - handle.height) // 2 + 4)

    out = Image.fromarray(np.clip(f, 0, 255).astype(np.uint8))
    out.save(os.path.join(HERE, "d3d_cover.jpg"), quality=93)
    # Profile-grid preview (3:4 centre crop).
    out.crop((0, 240, W, 240 + 1440)).save(os.path.join(HERE, "d3d_cover_grid_preview.jpg"), quality=90)
    print("wrote d3d_cover.jpg and d3d_cover_grid_preview.jpg")


if __name__ == "__main__":
    main()
