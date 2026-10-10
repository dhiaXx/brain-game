#!/usr/bin/env python3
"""Cover for the D3D FAQ ad (1080x1920), in the same paper/highlighter style.

Key content stays inside the centred 3:4 area (y 240..1680) that the
Instagram profile grid shows.

Usage:  python3 promo/d3d/vox/make_cover.py
"""
import os
import subprocess
import sys

import numpy as np
from PIL import Image

sys.argv = sys.argv[:1]
from make_vox_edit import (F_BLACK, F_MONO, F_SEMI, INK, RED, SRC, W, H, YEL, card, chat_icon,  # noqa: E402
                           font, highlight_text, mono_tag, place, stamp, text_img)

HERE = os.path.dirname(os.path.abspath(__file__))
VF = ("scale=1080:1920:flags=lanczos,unsharp=5:5:0.7:5:5:0.0,"
      "curves=m='0/0.03 0.25/0.21 0.5/0.5 0.78/0.82 1/0.97',"
      "colorbalance=rs=-0.04:gs=-0.01:bs=0.05:rh=0.05:gh=0.01:bh=-0.05,"
      "eq=saturation=0.95:contrast=1.04,vignette=angle=PI/4.5")


def main():
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", "1.0", "-i", SRC, "-frames:v", "1",
                          "-vf", VF, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    f = np.frombuffer(raw, np.uint8).reshape(H, W, 3).astype(np.float32).copy()
    f *= 0.62  # let the paper cards pop

    tag = mono_tag("FAQ · PORTE-CLÉS B2B", 30, INK, YEL)
    place(f, tag, W / 2, 330, 1.0, -1.5)

    t1 = text_img("Porte-clés pour", font(F_BLACK, 92), INK, -3)
    t2 = highlight_text(["votre", "entreprise"], font(F_BLACK, 104), [1], 1.0)
    t3 = text_img("5 questions · 30 secondes", font(F_SEMI, 44), (70, 70, 70))
    cw = max(t1.width, t2.width, t3.width)
    content = Image.new("RGBA", (cw, t1.height + t2.height + t3.height + 10), (0, 0, 0, 0))
    content.alpha_composite(t1, ((cw - t1.width) // 2, 0))
    content.alpha_composite(t2, ((cw - t2.width) // 2, t1.height - 6))
    content.alpha_composite(t3, ((cw - t3.width) // 2, t1.height + t2.height + 4))
    c = card(content, (48, 36))
    place(f, c, W / 2, 610, 1.0, -1.5)

    qs = ["01  À quoi ça sert ?", "02  Quantité minimum ?", "03  Comment commander ?",
          "04  Paiement & livraison", "05  Matière & emballage"]
    rows = [text_img(q, font(F_MONO, 38), INK, 1) for q in qs]
    lw = max(r.width for r in rows)
    lst = Image.new("RGBA", (lw, sum(r.height + 14 for r in rows)), (0, 0, 0, 0))
    y = 0
    for r in rows:
        lst.alpha_composite(r, (0, y))
        y += r.height + 14
    lc = card(lst, (40, 30))
    place(f, lc, W / 2, 1110, 1.0, 1.0)

    place(f, stamp("DEVIS EN DM", RED, 52), W / 2 + 250, 1330, 1.0, -10)

    ic = chat_icon(26)
    num = text_img("+216 25 430 387", font(F_BLACK, 48), INK)
    brand = text_img("D3D", font(F_BLACK, 56), INK, -1)
    row = Image.new("RGBA", (brand.width + 30 + ic.width + 12 + num.width, max(brand.height, num.height)),
                    (0, 0, 0, 0))
    row.alpha_composite(brand, (0, (row.height - brand.height) // 2))
    row.alpha_composite(ic, (brand.width + 30, (row.height - ic.height) // 2))
    row.alpha_composite(num, (brand.width + 30 + ic.width + 12, (row.height - num.height) // 2))
    place(f, card(row, (34, 18)), W / 2, 1520, 1.0, -1.0)

    out = Image.fromarray(np.clip(f, 0, 255).astype(np.uint8))
    out.save(os.path.join(HERE, "d3d_faq_cover.jpg"), quality=93)
    out.crop((0, 240, W, 240 + 1440)).save(os.path.join(HERE, "d3d_faq_cover_grid.jpg"), quality=90)
    print("wrote d3d_faq_cover.jpg and d3d_faq_cover_grid.jpg")


if __name__ == "__main__":
    main()
