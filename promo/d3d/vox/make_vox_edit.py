#!/usr/bin/env python3
"""D3D B2B FAQ, re-edited in a Vox-style explainer look.

Source: src/raw.mp4 (480x854, 32 s, voiceover + music already mixed).
The voiceover timing is untouched; everything is layered on top:

  * grade      filmic S-curve, warm highlights / teal shadows, vignette, grain
  * montage    whip-pan transitions with motion blur on every source cut
  * design     paper cards, highlighter swipes, hand-drawn red circles, mono
               "typewriter" chapter tags, progress bar, data graphics
               (10 -> 1000 counter, 50 % pie), chat card, rubber stamps
  * sound      synthesized SFX for every animation, mixed under the voice
  * outro      3 s CTA end card

Usage:
  python3 promo/d3d/vox/make_vox_edit.py              # full 1080x1920 render
  python3 promo/d3d/vox/make_vox_edit.py --stills 3,9.8,14  # PNG checks
"""
import math
import os
import subprocess
import sys
import wave
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src", "raw.mp4")
GRADED = os.path.join(HERE, "_graded.mp4")
OUT = os.path.join(HERE, "d3d_faq_vox.mp4")
W, H, FPS = 1080, 1920, 30
SRC_DUR = 32.08
OUTRO = 3.0
DUR = SRC_DUR + OUTRO
SR = 48000

# Source cuts (ffmpeg scdet) — transitions are placed exactly on these.
CUTS = [1.97, 3.98, 5.07, 6.47, 7.98, 9.57, 11.07, 12.57, 13.70, 15.67,
        17.60, 19.00, 21.53, 27.17, 29.98]

FD = "/usr/share/fonts/opentype/inter"
F_BLACK = f"{FD}/InterDisplay-Black.otf"
F_BOLD = f"{FD}/InterDisplay-Bold.otf"
F_SEMI = f"{FD}/InterDisplay-SemiBold.otf"
F_MONO = "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf"

PAPER = (244, 239, 228)
INK = (20, 20, 20)
YEL = (255, 205, 0)
RED = (226, 54, 44)
GREEN = (37, 211, 102)
WHITE = (255, 255, 255)

CHAPTERS = [  # (start, question)
    (1.97, "À quoi ça sert ?"),
    (7.98, "Quantité minimum ?"),
    (11.07, "Comment commander ?"),
    (21.53, "Paiement & livraison"),
    (28.45, "Matière & emballage"),
]


# ------------------------------------------------------------------ basics
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def prog(t, s, d):
    return clamp((t - s) / d)


def eo3(x):
    return 1 - (1 - x) ** 3


def ei3(x):
    return x ** 3


def eio(x):
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def eexpo(x):
    return 1.0 if x >= 1 else 1 - 2 ** (-10 * x)


def eback(x, s=1.7):
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


def window(t, s, e, fin=0.3, fout=0.2):
    """0..1 in-progress and 0..1 out-progress for an element living [s, e]."""
    return prog(t, s, fin), prog(t, e - fout, fout)


_FONTS = {}


def font(path, size):
    k = (path, size)
    if k not in _FONTS:
        _FONTS[k] = ImageFont.truetype(path, size)
    return _FONTS[k]


def text_img(txt, fnt, color, tracking=0):
    asc, desc = fnt.getmetrics()
    ws = [fnt.getlength(c) for c in txt]
    w = int(sum(ws) + tracking * max(0, len(txt) - 1)) + 6
    im = Image.new("RGBA", (max(1, w), asc + desc + 6), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = 3
    for c, cw in zip(txt, ws):
        d.text((x, 3), c, font=fnt, fill=color + (255,))
        x += cw + tracking
    return im


def over(dst, layer, x, y, alpha=1.0):
    if alpha <= 0.002:
        return
    src = np.asarray(layer, np.float32)
    h, w = src.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(dst.shape[1], x + w), min(dst.shape[0], y + h)
    if x1 <= x0 or y1 <= y0:
        return
    s = src[y0 - y:y1 - y, x0 - x:x1 - x]
    a = s[..., 3:4] / 255.0 * alpha
    reg = dst[y0:y1, x0:x1]
    reg *= 1 - a
    reg += s[..., :3] * a


def place(dst, layer, cx, cy, scale=1.0, rot=0.0, alpha=1.0):
    """Composite a layer centred at (cx, cy) with scale/rotation."""
    if alpha <= 0.002 or scale <= 0.01:
        return
    im = layer
    if scale != 1.0:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BILINEAR)
    if rot:
        im = im.rotate(rot, resample=Image.BICUBIC, expand=True)
    over(dst, im, int(cx - im.width / 2), int(cy - im.height / 2), alpha)


# ------------------------------------------------------------------ design kit
_TEX = {}


def paper_tex(w, h):
    key = "paper"
    if key not in _TEX:
        r = np.random.default_rng(3)
        base = np.ones((1400, 1100, 3), np.float32) * np.array(PAPER, np.float32)
        n = r.standard_normal((1400, 1100)).astype(np.float32)
        fib = np.asarray(Image.fromarray(((n * 20) + 128).clip(0, 255).astype(np.uint8))
                         .filter(ImageFilter.GaussianBlur(1.2)), np.float32) - 128
        base += fib[..., None] * 0.35 + n[..., None] * 3
        _TEX[key] = base
    return _TEX[key][:h, :w]


def card(content, pad=(34, 24), shadow=True, color=None, radius=6):
    """Paper card around an RGBA content image, with soft drop shadow."""
    pw, ph = pad
    w, h = content.width + 2 * pw, content.height + 2 * ph
    body = np.zeros((h, w, 4), np.float32)
    if color is None:
        body[..., :3] = paper_tex(w, h)
    else:
        body[..., :3] = color
    body[..., 3] = 255
    im = Image.fromarray(body.clip(0, 255).astype(np.uint8), "RGBA")
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    im.putalpha(mask)
    im.alpha_composite(content, (pw, ph))
    if not shadow:
        return im
    sp = 30
    out = Image.new("RGBA", (w + 2 * sp, h + 2 * sp), (0, 0, 0, 0))
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 120))
    sh.putalpha(mask.point(lambda v: int(v * 0.45)))
    out.alpha_composite(sh, (sp + 6, sp + 12))
    out = out.filter(ImageFilter.GaussianBlur(10))
    out.alpha_composite(im, (sp, sp))
    return out


def highlight_text(words, fnt, hl_idx, p, color=INK, hl=YEL):
    """Words with a highlighter stroke swiping (0..1) behind word hl_idx."""
    space = fnt.getlength(" ")
    imgs = [text_img(w_, fnt, color, -1) for w_ in words]
    tw = int(sum(i.width for i in imgs) + space * (len(imgs) - 1))
    th = imgs[0].height
    im = Image.new("RGBA", (tw + 20, th + 10), (0, 0, 0, 0))
    x = 10
    d = ImageDraw.Draw(im)
    for k, wi in enumerate(imgs):
        if k in (hl_idx if isinstance(hl_idx, (list, tuple)) else [hl_idx]) and p > 0:
            hw = int((wi.width + 12) * eo3(p))
            y0, y1 = int(th * 0.38), int(th * 0.92)
            r = np.random.default_rng(k)
            j = r.integers(-3, 4, 4)
            d.polygon([(x - 6, y0 + j[0]), (x - 6 + hw, y0 + j[1]),
                       (x - 6 + hw, y1 + j[2]), (x - 6, y1 + j[3])], fill=hl + (230,))
        im.alpha_composite(wi, (x, 5))
        x += wi.width + int(space)
    return im


def scribble_circle(w, h, p, color=RED, width=9, seed=0):
    """Hand-drawn ellipse drawn on progressively (p 0..1), slight overshoot."""
    im = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    if p <= 0:
        return im
    d = ImageDraw.Draw(im)
    r = np.random.default_rng(seed)
    n = 90
    a0 = -2.2
    total = 2 * math.pi * 1.12
    pts = []
    for i in range(int(n * p) + 1):
        a = a0 + total * i / n
        wob = 1 + 0.035 * math.sin(a * 3 + seed) + 0.02 * r.standard_normal()
        sp = 1 + 0.05 * (i / n)  # spiral slightly so the ends don't meet
        pts.append((20 + w / 2 + math.cos(a) * w / 2 * wob * sp,
                    20 + h / 2 + math.sin(a) * h / 2 * wob * sp))
    if len(pts) > 1:
        d.line(pts, fill=color + (255,), width=width, joint="curve")
    return im


def mono_tag(txt, size=28, fg=WHITE, bg=INK):
    t = text_img(txt, font(F_MONO, size), fg, 2)
    im = Image.new("RGBA", (t.width + 28, t.height + 10), bg + (255,))
    im.alpha_composite(t, (14, 5))
    return im


def typed(txt, p):
    n = int(len(txt) * clamp(p))
    return txt[:n]


def stamp(txt, color=RED, size=64):
    t = text_img(txt, font(F_BLACK, size), color, 2)
    w, h = t.width + 50, t.height + 30
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([3, 3, w - 4, h - 4], radius=10, fill=PAPER + (235,), outline=color + (255,), width=7)
    im.alpha_composite(t, (25, 12))
    # Ink texture: knock out random speckles.
    a = np.asarray(im.getchannel("A"), np.float32)
    r = np.random.default_rng(len(txt))
    a *= 0.88 + 0.12 * (r.random(a.shape) > 0.25)
    im.putalpha(Image.fromarray(a.clip(0, 255).astype(np.uint8)))
    return im


def check_icon(r, fill=GREEN):
    s = 4
    im = Image.new("RGBA", (2 * r * s, 2 * r * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([0, 0, 2 * r * s - 1, 2 * r * s - 1], fill=fill + (255,))
    d.line([(r * s * 0.55, r * s * 1.05), (r * s * 0.88, r * s * 1.38), (r * s * 1.48, r * s * 0.68)],
           fill=WHITE + (255,), width=int(r * s * 0.22), joint="curve")
    return im.resize((2 * r, 2 * r), Image.LANCZOS)


def chat_icon(r):
    s = 4
    im = Image.new("RGBA", (2 * r * s, 2 * r * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([0, 0, 2 * r * s - 1, 2 * r * s - 1], fill=GREEN + (255,))
    c = r * s
    d.ellipse([c * 0.45, c * 0.45, c * 1.55, c * 1.45], outline=WHITE + (255,), width=int(c * 0.12))
    d.polygon([(c * 0.55, c * 1.25), (c * 0.42, c * 1.62), (c * 0.85, c * 1.42)], fill=WHITE + (255,))
    return im.resize((2 * r, 2 * r), Image.LANCZOS)


def box_icon(sz, color=INK):
    s = 4
    S = sz * s
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    lw = int(S * 0.07)
    top = [(S * 0.5, S * 0.12), (S * 0.92, S * 0.3), (S * 0.5, S * 0.48), (S * 0.08, S * 0.3)]
    d.polygon(top, outline=color + (255,), width=lw)
    d.line([(S * 0.08, S * 0.3), (S * 0.08, S * 0.72), (S * 0.5, S * 0.9), (S * 0.92, S * 0.72),
            (S * 0.92, S * 0.3)], fill=color + (255,), width=lw, joint="curve")
    d.line([(S * 0.5, S * 0.48), (S * 0.5, S * 0.9)], fill=color + (255,), width=lw)
    return im.resize((sz, sz), Image.LANCZOS)


def pie(sz, p, frac=0.5, color=YEL, bg=(220, 214, 200)):
    s = 4
    S = sz * s
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([0, 0, S - 1, S - 1], fill=bg + (255,))
    if p > 0:
        d.pieslice([0, 0, S - 1, S - 1], -90, -90 + 360 * frac * p, fill=color + (255,))
    d.ellipse([0, 0, S - 1, S - 1], outline=INK + (255,), width=int(S * 0.03))
    return im.resize((sz, sz), Image.LANCZOS)


def doc_icon(w, h):
    s = 3
    im = Image.new("RGBA", (w * s, h * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w * s - 1, h * s - 1], fill=WHITE + (255,), outline=INK + (255,), width=3 * s)
    for k in range(5):
        y = int(h * s * (0.22 + k * 0.13))
        d.line([(w * s * 0.15, y), (w * s * (0.85 if k % 2 == 0 else 0.6), y)], fill=(150, 150, 150, 255), width=3 * s)
    d.rectangle([w * s * 0.15, h * s * 0.85, w * s * 0.5, h * s * 0.9], fill=YEL + (255,))
    return im.resize((w, h), Image.LANCZOS)


# ------------------------------------------------------------------ transitions
def box_blur_x(a, k):
    if k < 2:
        return a
    c = np.cumsum(np.pad(a, ((0, 0), (k, k), (0, 0)), mode="edge"), axis=1, dtype=np.float32)
    return (c[:, 2 * k:] - c[:, :-2 * k])[:, :a.shape[1]] / (2 * k)


def box_blur_y(a, k):
    if k < 2:
        return a
    c = np.cumsum(np.pad(a, ((k, k), (0, 0), (0, 0)), mode="edge"), axis=0, dtype=np.float32)
    return (c[2 * k:] - c[:-2 * k])[:a.shape[0]] / (2 * k)


def transition(f, t):
    """Whip-pan on every cut: outgoing shot slides+blurs out, incoming slides in."""
    TD = 0.12
    for n, c in enumerate(CUTS):
        dt = t - c
        if -TD <= dt < TD:
            vertical = n % 3 == 2
            sign = 1 if n % 2 == 0 else -1
            amt = ei3(prog(dt, -TD, TD)) if dt < 0 else 1 - eo3(prog(dt, 0, TD))
            shift = int(sign * amt * (H if vertical else W) * 0.45) * (-1 if dt < 0 else 1)
            k = int(amt * 140)
            if vertical:
                f = np.roll(f, shift, axis=0)
                f = box_blur_y(f, k)
            else:
                f = np.roll(f, shift, axis=1)
                f = box_blur_x(f, k)
            f = f * (1 + 0.15 * amt)  # exposure bump hides the seam
            return f
    return f


# ------------------------------------------------------------------ overlays
def progress_bar(f, t):
    if t < 1.97 or t > SRC_DUR - 0.05:
        return
    x0, x1, y = 60, 1020, 238
    gap = 10
    seg = (x1 - x0 - gap * 4) / 5
    for k, (s, _) in enumerate(CHAPTERS):
        e = CHAPTERS[k + 1][0] if k + 1 < len(CHAPTERS) else SRC_DUR
        sx = int(x0 + k * (seg + gap))
        f[y:y + 8, sx:int(sx + seg)] = f[y:y + 8, sx:int(sx + seg)] * 0.4 + np.array(WHITE) * 0.35
        p = prog(t, s, e - s)
        if p > 0:
            f[y:y + 8, sx:int(sx + seg * p)] = YEL


def chapter_header(f, t):
    """Big centred chapter card that shrinks into a persistent top header."""
    idx = None
    for k, (s, _) in enumerate(CHAPTERS):
        if t >= s:
            idx = k
    if idx is None or t > SRC_DUR - 0.05:
        return
    s, q = CHAPTERS[idx]
    e = CHAPTERS[idx + 1][0] if idx + 1 < len(CHAPTERS) else SRC_DUR
    num = text_img(f"{idx + 1:02d}", font(F_BLACK, 150), YEL, -4)
    tag = text_img(typed(f"QUESTION {idx + 1:02d}/05", prog(t, s, 0.35)) or " ", font(F_MONO, 30), INK, 3)
    qt = highlight_text(q.split(" "), font(F_BLACK, 74), [], 0)
    content = Image.new("RGBA", (max(qt.width, 600), tag.height + qt.height + 10), (0, 0, 0, 0))
    content.alpha_composite(tag, (10, 0))
    content.alpha_composite(qt, (0, tag.height + 6))
    c = card(content, (30, 22))
    pin, pout = prog(t, s, 0.35), prog(t, e - 0.15, 0.15)
    shrink = eio(prog(t, s + 0.6, 0.3))
    big_cx, big_cy, big_sc = W / 2, H * 0.47, 1.0
    hd_sc = 0.80
    hd_cx, hd_cy = 60 + c.width * hd_sc / 2 - 18, 270 + c.height * hd_sc / 2
    cx = big_cx + (hd_cx - big_cx) * shrink
    cy = big_cy + (hd_cy - big_cy) * shrink
    sc = (big_sc + (hd_sc - big_sc) * shrink) * (0.85 + 0.15 * eback(pin))
    rot = (-2.0 + 4 * (1 - eo3(pin))) * (1 - shrink) - 0.8 * shrink
    alpha = eo3(pin) * (1 - pout)
    # Darken the footage while the big card is up (focus).
    dim = 0.45 * eo3(pin) * (1 - shrink)
    if dim > 0:
        f *= 1 - dim
    if shrink < 0.95:
        place(f, num, W / 2, big_cy - c.height / 2 - 70, 1.0, -3, alpha * (1 - shrink))
    place(f, c, cx, cy, sc, rot, alpha)


def caption(f, t, s, e, words, hl, cy=1420, size=66, rot=-1.2):
    pin, pout = window(t, s, e, 0.25, 0.18)
    if pin <= 0 or pout >= 1:
        return
    im = highlight_text(words, font(F_BLACK, size), hl, prog(t, s + 0.15, 0.35))
    c = card(im, (26, 14))
    dy = (1 - eo3(pin)) * 60 + ei3(pout) * 40
    place(f, c, 480, cy + dy, 0.9 + 0.1 * eback(pin), rot, eo3(pin) * (1 - pout))


def chips(f, t, items, cx=300, cy0=1180, step=110):
    for k, (s, e, txt) in enumerate(items):
        pin, pout = window(t, s, e, 0.25, 0.2)
        if pin <= 0 or pout >= 1:
            continue
        ic = check_icon(26, INK)
        tx = text_img(txt, font(F_BLACK, 58), INK, -1)
        row = Image.new("RGBA", (ic.width + 18 + tx.width, max(ic.height, tx.height)), (0, 0, 0, 0))
        row.alpha_composite(ic, (0, (row.height - ic.height) // 2))
        row.alpha_composite(tx, (ic.width + 18, (row.height - tx.height) // 2))
        c = card(row, (24, 14))
        x = cx - 200 * (1 - eo3(pin)) - 300 * ei3(pout)
        place(f, c, x, cy0 + k * step, 1.0, [-1.5, 1.0, -0.6][k % 3], eo3(pin) * (1 - pout))


def counter_card(f, t, s, e):
    pin, pout = window(t, s, e, 0.3, 0.2)
    if pin <= 0 or pout >= 1:
        return
    p = eio(prog(t, s + 0.2, 1.0))
    val = int(round(10 ** (1 + 2 * p)))  # log scale 10 -> 1000
    lab = text_img("QUANTITÉ", font(F_MONO, 28), INK, 3)
    big = text_img(f"{val}{'+' if p >= 1 else ''}", font(F_BLACK, 150), INK, -4)
    unit = text_img("pièces", font(F_BLACK, 56), INK)
    bw, bh = 640, 26
    bar = Image.new("RGBA", (bw, bh + 70), (0, 0, 0, 0))
    d = ImageDraw.Draw(bar)
    d.rectangle([0, 20, bw - 1, 20 + bh], fill=(220, 214, 200, 255))
    d.rectangle([0, 20, int(bw * p), 20 + bh], fill=YEL + (255,))
    d.rectangle([0, 20, bw - 1, 20 + bh], outline=INK + (255,), width=3)
    for k, (lv, lt) in enumerate([(0, "10"), (0.5, "100"), (1.0, "1000")]):
        x = int(lv * (bw - 4)) + 2
        d.line([(x, 10), (x, 20 + bh + 8)], fill=INK + (255,), width=3)
        tl = text_img(lt, font(F_MONO, 24), INK)
        bar.alpha_composite(tl, (min(bw - tl.width, max(0, x - tl.width // 2)), 20 + bh + 12))
    row = Image.new("RGBA", (big.width + 20 + unit.width, big.height), (0, 0, 0, 0))
    row.alpha_composite(big, (0, 0))
    row.alpha_composite(unit, (big.width + 20, big.height - unit.height - 22))
    content = Image.new("RGBA", (max(bw, row.width), lab.height + row.height + bar.height + 10), (0, 0, 0, 0))
    content.alpha_composite(lab, (0, 0))
    content.alpha_composite(row, (0, lab.height))
    content.alpha_composite(bar, (0, lab.height + row.height + 10))
    c = card(content, (40, 30))
    place(f, c, 490, 1300 + 80 * (1 - eo3(pin)), 0.92 + 0.08 * eback(pin), -1.0, eo3(pin) * (1 - pout))


def chat_card(f, t, s, e):
    pin, pout = window(t, s, e, 0.3, 0.2)
    if pin <= 0 or pout >= 1:
        return
    title = text_img("① Envoyez votre logo", font(F_BLACK, 54), INK, -1)
    ic = chat_icon(34)
    num = text_img("+216 25 430 387", font(F_BLACK, 62), INK, 0)
    sub = text_img("WhatsApp · DM", font(F_MONO, 26), (90, 90, 90), 2)
    # Message bubble that "sends" at s+0.6.
    bp = eback(prog(t, s + 0.6, 0.35))
    bubble = Image.new("RGBA", (420, 120), (0, 0, 0, 0))
    if bp > 0:
        bb = Image.new("RGBA", (420, 110), (0, 0, 0, 0))
        d = ImageDraw.Draw(bb)
        d.rounded_rectangle([0, 0, 419, 109], radius=26, fill=(217, 253, 211, 255))
        d.rounded_rectangle([20, 18, 92, 90], radius=10, fill=YEL + (255,))
        bb.alpha_composite(text_img("LOGO", font(F_BLACK, 22), INK), (26, 40))
        bb.alpha_composite(text_img("votre-logo.png", font(F_SEMI, 32), INK), (110, 22))
        ticks_blue = prog(t, s + 1.4, 0.2) > 0
        tk = text_img("✓✓", font(F_BOLD, 28), (52, 183, 241) if ticks_blue else (140, 140, 140))
        bb.alpha_composite(tk, (330, 62))
        bb = bb.resize((max(1, int(420 * bp)), max(1, int(110 * bp))), Image.BILINEAR)
        bubble.alpha_composite(bb, (420 - bb.width, 0))
    row = Image.new("RGBA", (ic.width + 20 + num.width, max(ic.height, num.height)), (0, 0, 0, 0))
    row.alpha_composite(ic, (0, (row.height - ic.height) // 2))
    row.alpha_composite(num, (ic.width + 20, (row.height - num.height) // 2))
    cw = max(title.width, row.width, 420)
    content = Image.new("RGBA", (cw, title.height + 20 + bubble.height + 10 + row.height + sub.height + 8), (0, 0, 0, 0))
    y = 0
    content.alpha_composite(title, (0, y)); y += title.height + 20
    content.alpha_composite(bubble, (cw - 420, y)); y += bubble.height + 10
    content.alpha_composite(row, (0, y)); y += row.height + 4
    content.alpha_composite(sub, (ic.width + 22, y))
    c = card(content, (36, 28))
    place(f, c, 490, 1290 + 90 * (1 - eo3(pin)), 0.92 + 0.08 * eback(pin), 1.0, eo3(pin) * (1 - pout))


def step_card(f, t, s, e, title, sub, icon=None, rot=-1.0, cy=1400):
    pin, pout = window(t, s, e, 0.3, 0.2)
    if pin <= 0 or pout >= 1:
        return
    tt = text_img(title, font(F_BLACK, 58), INK, -1)
    st = text_img(sub, font(F_SEMI, 38), (70, 70, 70)) if sub else None
    iw = icon.width + 24 if icon is not None else 0
    h = tt.height + (st.height + 4 if st else 0)
    content = Image.new("RGBA", (iw + max(tt.width, st.width if st else 0), max(h, icon.height if icon else 0)), (0, 0, 0, 0))
    if icon is not None:
        content.alpha_composite(icon, (0, (content.height - icon.height) // 2))
    content.alpha_composite(tt, (iw, (content.height - h) // 2))
    if st:
        content.alpha_composite(st, (iw, (content.height - h) // 2 + tt.height + 4))
    c = card(content, (32, 22))
    place(f, c, 480, cy + 80 * (1 - eo3(pin)), 0.92 + 0.08 * eback(pin), rot, eo3(pin) * (1 - pout))


def stamp_slam(f, t, s, e, txt, cx, cy, rot=-12, color=RED, size=64):
    pin, pout = window(t, s, e, 0.18, 0.2)
    if pin <= 0 or pout >= 1:
        return
    sc = 1.0 + 1.2 * (1 - eo3(pin))
    place(f, stamp(txt, color, size), cx, cy, sc, rot, min(1, pin * 2) * (1 - pout))


def circle(f, t, s, e, cx, cy, w, h, seed=0):
    p = eio(prog(t, s, 0.5))
    pout = prog(t, e - 0.2, 0.2)
    if p <= 0 or pout >= 1:
        return
    over(f, scribble_circle(w, h, p, seed=seed), int(cx - w / 2 - 20), int(cy - h / 2 - 20), 1 - pout)


def payment_panel(f, t):
    s, e = 21.6, 27.1
    if not (s <= t < e):
        return
    pout = prog(t, e - 0.2, 0.2)
    cols = []
    for k, (ts, head, line1, line2, kind) in enumerate([
            (21.65, "< 100 pièces", "Paiement", "à la livraison", "box"),
            (23.0, "100+ pièces", "Acompte 50 %", "le reste à la livraison", "pie")]):
        pin = prog(t, ts, 0.3)
        if pin <= 0:
            continue
        hd = mono_tag(head, 30, INK, YEL)
        l1 = text_img(line1, font(F_BLACK, 50), INK, -1)
        l2 = text_img(line2, font(F_SEMI, 32), (70, 70, 70))
        ic = box_icon(120) if kind == "box" else pie(120, eo3(prog(t, ts + 0.3, 0.6)))
        cw = max(hd.width, l1.width, l2.width, ic.width)
        content = Image.new("RGBA", (cw, hd.height + 16 + ic.height + 14 + l1.height + l2.height), (0, 0, 0, 0))
        y = 0
        content.alpha_composite(hd, (0, y)); y += hd.height + 16
        content.alpha_composite(ic, (0, y)); y += ic.height + 14
        content.alpha_composite(l1, (0, y)); y += l1.height
        content.alpha_composite(l2, (0, y))
        cols.append((card(content, (30, 26)), pin, k))
    for c, pin, k in cols:
        cx = 270 + k * 420
        place(f, c, cx, 1330 + 120 * (1 - eo3(pin)), 0.95 + 0.05 * eback(pin), [-1.5, 1.2][k],
              eo3(pin) * (1 - pout))


def intro(f, t):
    if t >= 2.1:
        return
    pin, pout = prog(t, 0.05, 0.4), prog(t, 1.82, 0.15)
    kick = text_img(typed("FAQ · PORTE-CLÉS PERSONNALISÉS", prog(t, 0.2, 0.7)) or " ", font(F_MONO, 28), INK, 2)
    big = text_img("30 secondes", font(F_BLACK, 132), INK, -4)
    line = highlight_text(["pour", "répondre", "à", "vos", "questions"], font(F_BLACK, 58), [3, 4],
                          prog(t, 0.75, 0.45))
    cw = max(kick.width, big.width, line.width)
    content = Image.new("RGBA", (cw, kick.height + big.height + line.height + 6), (0, 0, 0, 0))
    content.alpha_composite(kick, (6, 0))
    content.alpha_composite(big, (0, kick.height))
    content.alpha_composite(line, (-4, kick.height + big.height))
    c = card(content, (40, 30))
    f *= 1 - 0.35 * eo3(pin) * (1 - pout)
    place(f, c, W / 2, H * 0.47 + 120 * (1 - eo3(pin)), 0.9 + 0.1 * eback(pin), -2 + 3 * (1 - eo3(pin)),
          eo3(pin) * (1 - pout))
    b2b = mono_tag("POUR ENTREPRISES · MARQUES · ÉVÉNEMENTS", 24, INK, YEL)
    place(f, b2b, W / 2, H * 0.47 + c.height / 2 + 30, 1.0, 1.5, prog(t, 1.0, 0.25) * (1 - pout))


def outro(f, t):
    lt = t - SRC_DUR
    if lt < 0:
        return
    logo = text_img("D3D", font(F_BLACK, 200), INK, -2)
    l1 = highlight_text(["Porte-clés", "personnalisés"], font(F_BLACK, 62), [1], prog(lt, 0.5, 0.4))
    l2 = text_img("pour entreprises, marques & événements", font(F_SEMI, 36), (70, 70, 70))
    ic = chat_icon(30)
    num = text_img("+216 25 430 387", font(F_BLACK, 58), INK)
    ig = text_img("@d3d.tn", font(F_MONO, 34), INK, 2)
    row = Image.new("RGBA", (ic.width + 16 + num.width, max(ic.height, num.height)), (0, 0, 0, 0))
    row.alpha_composite(ic, (0, (row.height - ic.height) // 2))
    row.alpha_composite(num, (ic.width + 16, (row.height - num.height) // 2))
    cw = max(logo.width, l1.width, l2.width, row.width)
    content = Image.new("RGBA", (cw, logo.height + l1.height + l2.height + 30 + row.height + ig.height + 10),
                        (0, 0, 0, 0))
    y = 0
    for im, gap in ((logo, -10), (l1, 0), (l2, 30), (row, 10), (ig, 0)):
        content.alpha_composite(im, ((cw - im.width) // 2, y))
        y += im.height + gap
    c = card(content, (60, 50))
    pin = prog(lt, 0.0, 0.45)
    place(f, c, W / 2, H * 0.48 + 150 * (1 - eo3(pin)), 0.9 + 0.1 * eback(pin), -1.5, eo3(pin))
    stamp_slam(f, lt, 1.0, 99.0, "MAQUETTE 3D GRATUITE", W / 2 + 170, H * 0.48 - c.height / 2 + 10, -10, RED, 44)


def overlays(f, t):
    intro(f, t)
    if 1.97 <= t < SRC_DUR:
        # Chapter 1: what is it for?
        chips(f, t, [(3.0, 5.0, "Société"), (3.45, 5.0, "Marque"), (4.0, 5.0, "Événement")])
        caption(f, t, 5.12, 6.45, ["Motivez", "votre", "équipe"], [2])
        caption(f, t, 6.55, 7.92, ["Fidélisez", "vos", "clients"], [2])
        circle(f, t, 6.7, 7.92, 640, 870, 520, 520, seed=2)
        # Chapter 2: MOQ
        caption(f, t, 8.9, 9.6, ["À", "partir", "de…"], [], cy=1380)
        counter_card(f, t, 9.6, 11.02)
        # Chapter 3: how to order
        caption(f, t, 11.5, 12.52, ["Simple", "comme", "1,", "2,", "3"], [2, 3, 4], cy=1420)
        chat_card(f, t, 12.6, 17.55)
        step_card(f, t, 17.62, 18.95, "② Maquette 3D", "validée avec vous avant production")
        stamp_slam(f, t, 18.0, 18.95, "VALIDÉ", 760, 1160, -12, GREEN)
        step_card(f, t, 19.05, 21.48, "③ Vous recevez le devis", "et on lance la production", doc_icon(70, 90))
        # Chapter 4: payment & delivery
        payment_panel(f, t)
        stamp_slam(f, t, 27.35, 28.4, "VÉRIFIEZ AVANT DE PAYER", 500, 1500, -6, RED, 50)
        circle(f, t, 27.3, 28.4, 600, 1060, 820, 420, seed=5)
        # Chapter 5: material & packaging
        step_card(f, t, 28.9, 29.95, "Matière : PLA+", "impression 3D multicolore", None, -1.2)
        caption(f, t, 30.1, 31.0, ["Emballage", "individuel", "?"], [0, 1])
        stamp_slam(f, t, 31.0, SRC_DUR - 0.02, "BIEN SÛR ✓", 540, 1420, -8, GREEN, 70)
        chapter_header(f, t)
        progress_bar(f, t)
    outro(f, t)


# ------------------------------------------------------------------ rendering
_LAST = {}


def render(args):
    i, raw = args
    t = i / FPS
    if raw is None:  # outro: blurred, darkened last frame
        f = _outro_bg().copy()
    else:
        f = np.frombuffer(raw, np.uint8).reshape(H, W, 3).astype(np.float32)
        f = transition(f, t)
    overlays(f, t)
    return np.clip(f, 0, 255).astype(np.uint8).tobytes()


def _outro_bg():
    if "bg" not in _LAST:
        last = np.load(os.path.join(HERE, "_last.npy"))
        im = Image.fromarray(last).filter(ImageFilter.GaussianBlur(18))
        a = np.asarray(im, np.float32) * 0.45
        _LAST["bg"] = a
    return _LAST["bg"]


def grade():
    vf = ("fps=30,scale=1080:1920:flags=lanczos,"
          "unsharp=5:5:0.7:5:5:0.0,"
          "curves=m='0/0.03 0.25/0.21 0.5/0.5 0.78/0.82 1/0.97',"
          "colorbalance=rs=-0.04:gs=-0.01:bs=0.05:rh=0.05:gh=0.01:bh=-0.05,"
          "eq=saturation=0.92:contrast=1.04,"
          "vignette=angle=PI/4.5")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", SRC, "-vf", vf, "-an",
                    "-c:v", "libx264", "-crf", "12", "-preset", "fast", GRADED], check=True)


def frames():
    p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-i", GRADED, "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    n = 0
    last = None
    while True:
        b = p.stdout.read(W * H * 3)
        if len(b) < W * H * 3:
            break
        last = b
        yield n, b
        n += 1
    np.save(os.path.join(HERE, "_last.npy"), np.frombuffer(last, np.uint8).reshape(H, W, 3))
    for k in range(int(OUTRO * FPS)):
        yield n + k, None


# ------------------------------------------------------------------ sound design
def sfx_bank():
    r = np.random.default_rng(9)

    def xs(L):
        return np.arange(int(L * SR)) / SR

    def sm(x, k):
        return np.convolve(x, np.ones(k) / k, mode="same")

    def whip(L=0.28):
        nz = r.standard_normal(int(L * SR))
        x = np.linspace(0, 1, len(nz))
        lo, hi = sm(nz, 30), nz - sm(nz, 3)
        mix = lo * (1 - x) + hi * x * 0.5
        return mix * np.sin(np.pi * x) ** 1.5 * 2.2

    def paper(L=0.35):
        nz = r.standard_normal(int(L * SR))
        x = np.linspace(0, 1, len(nz))
        crinkle = (r.random(len(nz)) > 0.985) * r.standard_normal(len(nz)) * 3
        s = (nz - sm(nz, 2)) * 0.5 + sm(crinkle, 3)
        return s * np.sin(np.pi * x) ** 0.8 * np.exp(-x * 1.5)

    def pop(f0=900):
        x = xs(0.12)
        return np.sin(2 * np.pi * (f0 + 900 * np.exp(-x * 60)) * x) * np.exp(-x * 40)

    def tick():
        x = xs(0.03)
        nz = r.standard_normal(len(x))
        return ((nz - sm(nz, 2)) * 0.6 + np.sin(2 * np.pi * 2400 * x) * 0.4) * np.exp(-x * 220)

    def marker(L=0.35):
        nz = r.standard_normal(int(L * SR))
        x = np.linspace(0, 1, len(nz))
        bp = sm(nz, 3) - sm(nz, 12)
        squeak = np.sin(2 * np.pi * np.cumsum(1800 + 300 * np.sin(x * 20)) / SR) * 0.08
        return (bp + squeak) * np.sin(np.pi * x) ** 0.5

    def scribble(L=0.5):
        nz = r.standard_normal(int(L * SR))
        x = np.linspace(0, 1, len(nz))
        bp = sm(nz, 2) - sm(nz, 8)
        return bp * (0.6 + 0.4 * np.abs(np.sin(x * 2 * np.pi * 6))) * np.sin(np.pi * x) ** 0.4

    def stamp_():
        x = xs(0.5)
        thud = np.sin(2 * np.pi * (70 + 120 * np.exp(-x * 40)) * x) * np.exp(-x * 14)
        nz = r.standard_normal(len(x))
        return thud * 1.2 + sm(nz, 3) * np.exp(-x * 35) * 0.6

    def boom():
        x = xs(1.2)
        return np.sin(2 * np.pi * (40 + 60 * np.exp(-x * 9)) * x) * np.exp(-x * 3) + \
            sm(r.standard_normal(len(x)), 6) * np.exp(-x * 14) * 0.4

    def riser(L=0.6):
        nz = r.standard_normal(int(L * SR))
        x = np.linspace(0, 1, len(nz))
        return (nz - sm(nz, 3)) * x ** 3 * 0.7 + np.sin(2 * np.pi * np.cumsum(300 + 1500 * x ** 2) / SR) * x ** 2 * 0.2

    def ding(f0=1760):
        x = xs(1.0)
        I = 2.5 * np.exp(-x * 5)
        return np.sin(2 * np.pi * f0 * x + I * np.sin(2 * np.pi * f0 * 2 * x)) * np.exp(-x * 4)

    def bubble():
        x = xs(0.18)
        return np.sin(2 * np.pi * np.cumsum(500 + 700 * x / 0.18) / SR) * np.exp(-x * 18)

    def count(L):
        out = np.zeros(int(L * SR))
        t = 0.0
        k = 0
        while t < L - 0.03:
            tk = tick() * (0.5 + 0.5 * t / L)
            s = int(t * SR)
            out[s:s + len(tk)] += tk[:len(out) - s]
            t += 0.09 * (1 - 0.6 * t / L)
            k += 1
        return out

    return dict(whip=whip, paper=paper, pop=pop, tick=tick, marker=marker, scribble=scribble,
                stamp=stamp_, boom=boom, riser=riser, ding=ding, bubble=bubble, count=count)


def build_sfx(path):
    n = int(DUR * SR)
    out = np.zeros((n, 2), np.float32)
    B = sfx_bank()

    def add(sig, t0, g=1.0, pan=0.0):
        s = int(t0 * SR)
        if s >= n or s < 0:
            return
        e = min(n, s + len(sig))
        l, r_ = math.cos((pan + 1) * math.pi / 4), math.sin((pan + 1) * math.pi / 4)
        out[s:e, 0] += sig[:e - s] * g * l * 1.414
        out[s:e, 1] += sig[:e - s] * g * r_ * 1.414

    for k, c in enumerate(CUTS):
        add(B["whip"](), c - 0.14, 0.22, 0.6 if k % 2 == 0 else -0.6)
    # Intro.
    add(B["boom"](), 0.02, 0.35)
    add(B["paper"](), 0.05, 0.35)
    for k in range(22):
        add(B["tick"](), 0.2 + k * 0.032, 0.12)
    add(B["marker"](), 0.75, 0.25)
    add(B["pop"](700), 1.0, 0.15)
    # Chapters.
    for s, _ in CHAPTERS:
        add(B["riser"](0.4), s - 0.4, 0.12)
        add(B["boom"](), s, 0.28)
        add(B["paper"](), s, 0.3)
        for k in range(14):
            add(B["tick"](), s + k * 0.025, 0.10)
        add(B["paper"](0.25), s + 0.6, 0.18, -0.4)
    # Chapter 1 chips + captions + circle.
    for k, t0 in enumerate([3.0, 3.45, 4.0]):
        add(B["pop"](800 + 150 * k), t0, 0.22, -0.4)
    for t0 in (5.12, 6.55):
        add(B["paper"](0.3), t0, 0.22)
        add(B["marker"](), t0 + 0.15, 0.2)
    add(B["scribble"](), 6.7, 0.18, 0.2)
    # Chapter 2.
    add(B["paper"](0.3), 8.9, 0.2)
    add(B["paper"](0.3), 9.6, 0.25)
    add(B["count"](1.0), 9.8, 0.35)
    add(B["ding"](1568), 10.8, 0.16)
    # Chapter 3.
    add(B["paper"](0.3), 11.5, 0.2)
    add(B["marker"](), 11.65, 0.2)
    add(B["paper"](0.3), 12.6, 0.25)
    add(B["bubble"](), 13.2, 0.3)
    add(B["pop"](1400), 14.0, 0.15)
    add(B["paper"](0.3), 17.62, 0.22)
    add(B["stamp"](), 18.0, 0.45)
    add(B["paper"](0.3), 19.05, 0.22)
    # Chapter 4.
    add(B["paper"](0.3), 21.65, 0.22, -0.4)
    add(B["paper"](0.3), 23.0, 0.22, 0.4)
    add(B["tick"](), 23.3, 0.2)
    add(B["ding"](2093), 23.9, 0.12)
    add(B["stamp"](), 27.35, 0.45)
    add(B["scribble"](), 27.3, 0.16)
    # Chapter 5.
    add(B["paper"](0.3), 28.9, 0.22)
    add(B["paper"](0.3), 30.1, 0.2)
    add(B["marker"](), 30.25, 0.2)
    add(B["stamp"](), 31.0, 0.45)
    add(B["ding"](1760), 31.05, 0.12)
    # Outro.
    add(B["whip"](0.4), SRC_DUR - 0.2, 0.25)
    add(B["boom"](), SRC_DUR, 0.35)
    add(B["paper"](), SRC_DUR, 0.3)
    add(B["marker"](), SRC_DUR + 0.5, 0.2)
    add(B["stamp"](), SRC_DUR + 1.0, 0.35)
    # Soft outro pad so the end card isn't silent.
    x = np.arange(int(OUTRO * SR)) / SR
    pad = sum(np.sin(2 * np.pi * f * x) for f in (220, 277.2, 329.6, 440)) / 4
    pad *= np.minimum(1, x / 0.3) * np.clip((OUTRO - x) / 1.2, 0, 1) * 0.18
    add(pad, SRC_DUR, 1.0)
    pcm = (np.clip(out, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


AUDIO_MIX = (
    # input 1 = source voice+music, input 2 = sfx
    "[1:a]aresample=48000,highpass=f=70,equalizer=f=250:t=q:w=1:g=-2,"
    "equalizer=f=3500:t=q:w=1:g=2.5,acompressor=threshold=-20dB:ratio=3:attack=8:release=120:makeup=3,"
    f"apad=whole_dur={DUR}[v];"
    "[2:a]aresample=48000[s];"
    "[v][s]amix=inputs=2:normalize=0:duration=longest,"
    "alimiter=limit=0.9,loudnorm=I=-14:TP=-1.0:LRA=8[a]"
)


def main():
    if "--stills" in sys.argv:
        ts = [float(v) for v in sys.argv[sys.argv.index("--stills") + 1].split(",")]
        if not os.path.exists(GRADED):
            grade()
        outdir = os.path.join(HERE, "_stills")
        os.makedirs(outdir, exist_ok=True)
        for t in ts:
            if t < SRC_DUR:
                raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", GRADED,
                                      "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                     capture_output=True).stdout
            else:
                if not os.path.exists(os.path.join(HERE, "_last.npy")):
                    raw0 = subprocess.run(["ffmpeg", "-loglevel", "error", "-sseof", "-0.1", "-i", GRADED,
                                           "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                          capture_output=True).stdout
                    np.save(os.path.join(HERE, "_last.npy"), np.frombuffer(raw0, np.uint8).reshape(H, W, 3))
                raw = None
            buf = render((int(round(t * FPS)), raw))
            Image.frombytes("RGB", (W, H), buf).save(os.path.join(outdir, f"t{t:05.2f}.png"))
        print("stills in", outdir)
        return

    print("grading...")
    grade()
    sfx = os.path.join(HERE, "_sfx.wav")
    print("sound design...")
    build_sfx(sfx)
    print("rendering...")
    enc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-i", SRC, "-i", sfx,
         "-filter_complex", "[0:v]noise=alls=3:allf=t,format=yuv420p[vv];" + AUDIO_MIX,
         "-map", "[vv]", "-map", "[a]",
         "-c:v", "libx264", "-preset", "slow", "-crf", "22", "-profile:v", "high",
         "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", "-t", f"{DUR}", OUT],
        stdin=subprocess.PIPE)
    with Pool(os.cpu_count()) as pool:
        for k, buf in enumerate(pool.imap(render, frames(), chunksize=2)):
            enc.stdin.write(buf)
            if k % 150 == 0:
                print(f"  frame {k}/{int(DUR * FPS)}")
    enc.stdin.close()
    if enc.wait() != 0:
        sys.exit("ffmpeg failed")
    for p in (sfx, GRADED, os.path.join(HERE, "_last.npy")):
        if os.path.exists(p):
            os.remove(p)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
