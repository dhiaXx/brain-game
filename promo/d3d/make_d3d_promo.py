#!/usr/bin/env python3
"""D3D promo reel: 1080x1920 (9:16), 22 s, clean minimal / premium style.

Uses the real product photos in ./photos, animated type, a synthesized score
and ffmpeg for grade, grain, loudness mastering and the H.264 delivery.

Usage:  python3 promo/d3d/make_d3d_promo.py [--preview]
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
PREVIEW = "--preview" in sys.argv
W, H = (540, 960) if PREVIEW else (1080, 1920)
S = W / 1080
FPS = 30
DUR = 22.0
NFRAMES = int(DUR * FPS)
SR = 48000
BEAT = 0.6  # 100 BPM

FD = "/usr/share/fonts/opentype/inter"
F_BLACK = f"{FD}/InterDisplay-Black.otf"
F_BOLD = f"{FD}/InterDisplay-Bold.otf"
F_SEMI = f"{FD}/InterDisplay-SemiBold.otf"
F_MED = f"{FD}/Inter-Medium.otf"
F_LAB = f"{FD}/Inter-SemiBold.otf"

PAPER = np.array([244, 242, 238], np.float32)
INK = (17, 17, 17)
MUTED = (110, 110, 110)
YELLOW = (255, 200, 0)

# Timeline (seconds)
HOOK_END = 2.4
PHOTOS = [("01_atelier", 0), ("02_sks", 1), ("03_sceg", 1), ("04_gomycode", 2),
          ("05_ego", 2), ("06_lcp", 3), ("07_peaktime", 3)]
CAPTIONS = ["Conçu & imprimé en 3D", "Pour les entreprises", "Pour les marques",
            "Pour les événements"]
PH_T0 = HOOK_END
PH_LEN = 9.6 / len(PHOTOS)
PROPS_T0 = PH_T0 + 9.6  # 12.0
PROPS = ["100% sur-mesure", "Maquette 3D gratuite", "Cadeau d'entreprise idéal"]
END_T0 = 16.8

CW, CH = 820, 1093  # photo card (3:4), authored px
CARD_Y = 330        # card top, inside the Reels safe area
RADIUS = 40


# ------------------------------------------------------------------ easing
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def prog(t, start, dur):
    return clamp((t - start) / dur)


def ease_out_cubic(x):
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def ease_out_expo(x):
    return 1.0 if x >= 1 else 1 - 2 ** (-10 * x)


def ease_in_cubic(x):
    return x ** 3


def ease_out_back(x, s=1.6):
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


def px(v):
    return int(round(v * S))


def font(path, size):
    return ImageFont.truetype(path, max(1, px(size)))


# ------------------------------------------------------------------ drawing
def over(dst, layer, x, y, alpha=1.0, clip=None):
    """Alpha-composite RGBA layer onto float RGB frame. clip=(y0, y1) masks rows."""
    if alpha <= 0:
        return
    src = np.asarray(layer, np.float32)
    h, w = src.shape[:2]
    cy0, cy1 = (0, H) if clip is None else (max(0, clip[0]), min(H, clip[1]))
    x0, y0 = max(0, x), max(cy0, y)
    x1, y1 = min(W, x + w), min(cy1, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    s = src[y0 - y:y1 - y, x0 - x:x1 - x]
    a = s[..., 3:4] / 255.0 * alpha
    reg = dst[y0:y1, x0:x1]
    reg *= 1 - a
    reg += s[..., :3] * a


def text_image(txt, fnt, color, tracking=0):
    asc, desc = fnt.getmetrics()
    widths = [fnt.getlength(c) for c in txt]
    tw = int(sum(widths) + px(tracking) * (len(txt) - 1)) + 4
    img = Image.new("RGBA", (max(1, tw), asc + desc + 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = 2
    for c, w in zip(txt, widths):
        d.text((x, 2), c, font=fnt, fill=color + (255,))
        x += w + px(tracking)
    return img


def reveal(frame, img, x, y, p_in, p_out=0.0, alpha=1.0):
    """Mask reveal: text rises out of an invisible line, exits upward."""
    h = img.height
    shift = int((1 - ease_out_expo(p_in)) * h - ease_in_cubic(p_out) * h)
    if p_in <= 0 or p_out >= 1:
        return
    over(frame, img, x, y + shift, alpha, clip=(y, y + h))


def pill(w, h, fill):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([0, 0, w - 1, h - 1], radius=h // 2, fill=fill + (255,))
    return im


_A = {}


def assets():
    if _A:
        return _A
    # Background: warm paper with a soft radial falloff.
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H * 0.45) / H) ** 2)
    _A["bg"] = PAPER[None, None, :] * (1 - 0.10 * np.clip(d / 0.75, 0, 1) ** 2)[..., None]

    # Photo cards: oversized source for Ken Burns, rounded mask, soft shadow.
    cw, ch = px(CW), px(CH)
    mask = Image.new("L", (cw * 2, ch * 2), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, cw * 2 - 1, ch * 2 - 1], radius=px(RADIUS) * 2, fill=255)
    _A["mask"] = mask.resize((cw, ch), Image.LANCZOS)
    pad = px(80)
    sh = Image.new("L", (cw + 2 * pad, ch + 2 * pad), 0)
    ImageDraw.Draw(sh).rounded_rectangle([pad, pad + px(24), pad + cw, pad + ch + px(24)],
                                         radius=px(RADIUS), fill=70)
    sh = sh.filter(ImageFilter.GaussianBlur(px(34)))
    shadow = Image.new("RGBA", sh.size, (20, 18, 10, 0))
    shadow.putalpha(sh)
    _A["shadow"], _A["pad"] = shadow, pad
    _A["photos"] = [Image.open(os.path.join(HERE, "photos", f"{n}.jpg")).convert("RGB")
                    .resize((int(cw * 1.12), int(ch * 1.12)), Image.LANCZOS) for n, _ in PHOTOS]

    _A["hook"] = [text_image("Votre logo.", font(F_BOLD, 112), INK, -2),
                  text_image("En porte-clés 3D.", font(F_BOLD, 112), INK, -2)]
    _A["hook_sub"] = text_image("Sur-mesure, en série.", font(F_MED, 44), MUTED)
    _A["captions"] = [text_image(c, font(F_SEMI, 54), INK, -1) for c in CAPTIONS]
    _A["brand_s"] = text_image("D3D", font(F_BLACK, 40), INK, 1)
    _A["nums"] = [text_image(f"{i + 1:02d} / {len(PHOTOS):02d}", font(F_LAB, 28), MUTED, 3)
                  for i in range(len(PHOTOS))]
    _A["why"] = text_image("POURQUOI D3D", font(F_LAB, 30), MUTED, 8)
    _A["props"] = [text_image(p, font(F_SEMI, 64), INK, -1) for p in PROPS]
    _A["logo"] = [text_image(c, font(F_BLACK, 300), INK, 0) for c in "D3D"]
    _A["tag"] = text_image("Porte-clés personnalisés", font(F_SEMI, 58), INK, -1)
    _A["tag2"] = text_image("Entreprises · Marques · Événements", font(F_MED, 38), MUTED)
    _A["cta_lab"] = text_image("COMMANDEZ", font(F_LAB, 28), MUTED, 8)
    _A["phone"] = text_image("+216 25 430 387", font(F_BOLD, 58), INK, 1)
    _A["handle"] = text_image("@d3d.tn", font(F_SEMI, 44), INK)
    _A["mock"] = text_image("Maquette 3D offerte", font(F_SEMI, 34), INK)
    return _A


# ------------------------------------------------------------------ scenes
def scene_hook(f, t):
    if t >= HOOK_END + 0.2:
        return
    a = assets()
    l1, l2 = a["hook"]
    y0 = px(760)
    gap = px(132)
    out = prog(t, HOOK_END - 0.45, 0.4)
    reveal(f, l1, W // 2 - l1.width // 2, y0, prog(t, 0.15, 0.7), out)
    reveal(f, l2, W // 2 - l2.width // 2, y0 + gap, prog(t, 0.55, 0.7), out)
    # Yellow highlight wipes behind "3D."-line baseline.
    wp = ease_out_expo(prog(t, 1.0, 0.6)) * (1 - ease_in_cubic(out))
    if wp > 0:
        bw = int(l2.width * 0.98 * wp)
        by = y0 + gap + int(l2.height * 0.80)
        f[by:by + px(14), W // 2 - l2.width // 2:W // 2 - l2.width // 2 + bw] = YELLOW
    sub = a["hook_sub"]
    sp = ease_out_cubic(prog(t, 1.2, 0.5)) * (1 - out)
    over(f, sub, W // 2 - sub.width // 2, y0 + 2 * gap + px(40) + int(px(16) * (1 - sp)), sp)


def card_image(i, t):
    a = assets()
    src = a["photos"][i]
    cw, ch = px(CW), px(CH)
    # Ken Burns: slow push across the shot.
    k = prog(t, PH_T0 + i * PH_LEN - 0.3, PH_LEN + 0.8)
    z = 1.12 - 0.10 * ease_in_out(k)
    w, h = min(cw * z, src.width), min(ch * z, src.height)
    ox = (src.width - w) / 2 + (0.5 - k) * px(18) * (1 if i % 2 else -1)
    ox = clamp(ox, 0, src.width - w)
    oy = (src.height - h) / 2
    im = src.resize((cw, ch), Image.BILINEAR, box=(ox, oy, ox + w, oy + h)).convert("RGBA")
    im.putalpha(a["mask"])
    return im


def scene_photos(f, t):
    if not (PH_T0 - 0.3 <= t < PROPS_T0 + 0.6):
        return
    a = assets()
    cw = px(CW)
    # Caption under the card, changes with each group.
    if t < PROPS_T0 + 0.3:
        idx = min(len(PHOTOS) - 1, max(0, int((t - PH_T0) / PH_LEN)))
        g = PHOTOS[idx][1]
        g_start = PH_T0 + min(k for k, (_, gg) in enumerate(PHOTOS) if gg == g) * PH_LEN
        g_end = PH_T0 + (max(k for k, (_, gg) in enumerate(PHOTOS) if gg == g) + 1) * PH_LEN
        cap = a["captions"][g]
        cy = px(CARD_Y) + px(CH) + px(70)
        reveal(f, cap, W // 2 - cap.width // 2, cy,
               prog(t, g_start - 0.05, 0.6), prog(t, g_end - 0.3, 0.3))

    for i in range(len(PHOTOS)):
        s = PH_T0 + i * PH_LEN
        e = s + PH_LEN
        if not (s - 0.3 <= t < e + 0.5):
            continue
        pin = ease_out_expo(prog(t, s - 0.3, 0.7))
        if i == len(PHOTOS) - 1:  # last card leaves the frame upward
            pout = ease_in_out(prog(t, e - 0.1, 0.55))
            dy = (1 - pin) * px(1500) - pout * px(1800)
            sc, alpha, dim = 1.0, 1.0, 0.0
        else:  # previous cards recede under the next one
            pout = ease_in_out(prog(t, e - 0.3, 0.6))
            dy = (1 - pin) * px(1500) - pout * px(60)
            sc, alpha, dim = 1 - 0.08 * pout, 1 - pout, pout
        if alpha <= 0:
            continue
        card = card_image(i, t)
        if sc != 1.0:
            card = card.resize((max(1, int(card.width * sc)), max(1, int(card.height * sc))), Image.BILINEAR)
        x = W // 2 - card.width // 2
        y = int(px(CARD_Y) + (px(CH) - card.height) / 2 + dy)
        sh = a["shadow"]
        over(f, sh, W // 2 - sh.width // 2, int(px(CARD_Y) - a["pad"] + dy), alpha * (1 - dim))
        over(f, card, x, y, alpha)

    # Header row: counter (left) and brand (right), aligned to the card edges.
    hp = ease_out_cubic(prog(t, PH_T0, 0.5)) * (1 - prog(t, PROPS_T0 - 0.2, 0.4))
    if hp > 0:
        idx = min(len(PHOTOS) - 1, max(0, int((t - PH_T0) / PH_LEN)))
        num = a["nums"][idx]
        hy = px(CARD_Y) - px(70)
        over(f, num, W // 2 - cw // 2, hy + px(6), hp)
        b = a["brand_s"]
        over(f, b, W // 2 + cw // 2 - b.width, hy, hp)


def scene_props(f, t):
    if not (PROPS_T0 <= t < END_T0 + 0.2):
        return
    a = assets()
    out = prog(t, END_T0 - 0.45, 0.45)
    why = a["why"]
    y = px(640)
    reveal(f, why, W // 2 - why.width // 2, y, prog(t, PROPS_T0 - 0.05, 0.6), out)
    r = px(40)
    left = W // 2 - px(400)
    for n, im in enumerate(a["props"]):
        t0 = PROPS_T0 + 0.3 + n * 1.2
        ry = y + px(140) + n * px(170)
        cp = ease_out_back(prog(t, t0, 0.45))
        if cp > 0 and out < 1:
            rr = max(1, int(r * cp * (1 - ease_in_cubic(out))))
            cx, cy = left + r, ry + im.height // 2
            circ = Image.new("RGBA", (2 * rr * 2, 2 * rr * 2), (0, 0, 0, 0))
            d = ImageDraw.Draw(circ)
            d.ellipse([0, 0, 4 * rr - 1, 4 * rr - 1], fill=YELLOW + (255,))
            cw_ = max(2, int(rr * 0.42))  # check mark, drawn at 2x then downsampled
            d.line([(rr * 1.1, rr * 2.1), (rr * 1.75, rr * 2.75), (rr * 2.95, rr * 1.35)],
                   fill=INK + (255,), width=cw_, joint="curve")
            circ = circ.resize((2 * rr, 2 * rr), Image.LANCZOS)
            over(f, circ, cx - rr, cy - rr)
        reveal(f, im, left + 2 * r + px(30), ry, prog(t, t0 + 0.08, 0.6), out)


def scene_end(f, t):
    if t < END_T0:
        return
    a = assets()
    letters = a["logo"]
    total = sum(l.width for l in letters) - px(8) * 2
    x = W // 2 - total // 2
    y = px(560)
    for n, l in enumerate(letters):
        reveal(f, l, x, y, prog(t, END_T0 + 0.15 + n * 0.09, 0.8))
        x += l.width - px(8)
    # Yellow bar under the wordmark (brand accent).
    bp = ease_out_expo(prog(t, END_T0 + 0.7, 0.7))
    if bp > 0:
        bw = int(total * bp)
        by = y + letters[0].height - px(30)
        f[by:by + px(18), W // 2 - total // 2:W // 2 - total // 2 + bw] = YELLOW
    tag, tag2 = a["tag"], a["tag2"]
    ty = y + letters[0].height + px(40)
    reveal(f, tag, W // 2 - tag.width // 2, ty, prog(t, END_T0 + 1.0, 0.7))
    reveal(f, tag2, W // 2 - tag2.width // 2, ty + px(86), prog(t, END_T0 + 1.25, 0.7))

    # CTA block: label, black pill with phone number, handle.
    cp = ease_out_cubic(prog(t, END_T0 + 1.8, 0.6))
    if cp > 0:
        lab = a["cta_lab"]
        cy = ty + px(230)
        over(f, lab, W // 2 - lab.width // 2, cy + int(px(14) * (1 - cp)), cp)
        ph = a["phone"]
        pw, phh = ph.width + px(110), ph.height + px(54)
        pl = pill(pw, phh, YELLOW)
        pl.alpha_composite(ph, (px(55), px(27) - px(4)))
        sc = 0.9 + 0.1 * ease_out_back(prog(t, END_T0 + 1.9, 0.6))
        pl = pl.resize((int(pw * sc), int(phh * sc)), Image.LANCZOS)
        over(f, pl, W // 2 - pl.width // 2, cy + px(60) + (phh - pl.height) // 2, cp)
        hd = a["handle"]
        over(f, hd, W // 2 - hd.width // 2, cy + px(60) + phh + px(40), ease_out_cubic(prog(t, END_T0 + 2.2, 0.5)))
    # Small "free mockup" badge.
    mp = ease_out_cubic(prog(t, END_T0 + 2.6, 0.5))
    if mp > 0:
        m = a["mock"]
        bw, bh = m.width + px(60), m.height + px(28)
        b = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        ImageDraw.Draw(b).rounded_rectangle([0, 0, bw - 1, bh - 1], radius=bh // 2,
                                            outline=INK + (255,), width=max(1, px(3)))
        b.alpha_composite(m, (px(30), px(14) - px(3)))
        over(f, b, W // 2 - bw // 2, px(400) + int(px(12) * (1 - mp)), mp)


def render_frame(i):
    t = i / FPS
    f = assets()["bg"].copy()
    scene_hook(f, t)
    scene_props(f, t)  # under the last card as it leaves
    scene_photos(f, t)
    scene_end(f, t)
    # Fade in from paper / out to paper (loops cleanly on Reels).
    k = min(prog(t, 0, 0.3), 1 - prog(t, DUR - 0.5, 0.5))
    if k < 1:
        f = f * k + assets()["bg"] * (1 - k)
    return np.clip(f, 0, 255).astype(np.uint8).tobytes()


# ------------------------------------------------------------------ audio
def synth_audio(path):
    n = int(DUR * SR)
    out = np.zeros((n, 2), np.float32)
    rng = np.random.default_rng(11)
    tt = np.arange(n) / SR

    def place(sig, t0, gain=1.0, pan=0.0):
        s = int(t0 * SR)
        e = min(n, s + len(sig))
        if s >= n or e <= s:
            return
        l, r = math.cos((pan + 1) * math.pi / 4), math.sin((pan + 1) * math.pi / 4)
        out[s:e, 0] += sig[:e - s] * gain * l * 1.414
        out[s:e, 1] += sig[:e - s] * gain * r * 1.414

    def note(m):
        return 440.0 * 2 ** ((m - 69) / 12)

    def smooth(x, k):
        return np.convolve(x, np.ones(k) / k, mode="same")

    def keys(freq, length, decay=0.9):
        """Soft electric-piano tone: sine + bell partial + gentle tremolo."""
        x = np.arange(int(length * SR)) / SR
        s = np.sin(2 * np.pi * freq * x) + 0.18 * np.sin(2 * np.pi * freq * 2 * x) \
            + 0.06 * np.sin(2 * np.pi * freq * 3.01 * x) * np.exp(-x * 6)
        e = np.minimum(1, x / 0.006) * np.exp(-x / decay)
        return s * e * (1 + 0.08 * np.sin(2 * np.pi * 4.5 * x))

    def kick():
        x = np.arange(int(0.4 * SR)) / SR
        f = 48 + 70 * np.exp(-x * 35)
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 9)

    def rim():
        nz = rng.standard_normal(int(0.08 * SR))
        x = np.arange(len(nz)) / SR
        hp = nz - smooth(nz, 4)
        return (hp * 0.6 + np.sin(2 * np.pi * 1800 * x) * 0.3) * np.exp(-x * 60)

    def shaker():
        nz = rng.standard_normal(int(0.07 * SR))
        x = np.arange(len(nz)) / SR
        return (nz - smooth(nz, 3)) * np.minimum(1, x / 0.01) * np.exp(-x * 45)

    def whoosh(length):
        nz = smooth(rng.standard_normal(int(length * SR)), 24)
        x = np.linspace(0, 1, len(nz))
        return nz * np.sin(np.pi * x) ** 2 * 2.5

    # Chords: Fmaj7 - Am7 - Dm9 - Bbmaj7, one bar (4 beats) each.
    chords = [[53, 57, 60, 64], [57, 60, 64, 67], [50, 57, 60, 64], [46, 53, 57, 62]]
    bar = 4 * BEAT
    nb = int(math.ceil(DUR / bar))
    for b in range(nb):
        ch = chords[b % 4]
        t0 = b * bar
        for k, m in enumerate(ch):  # soft pad stab, slightly strummed
            place(keys(note(m), bar + 0.6, 1.4), t0 + k * 0.012, 0.10, -0.3 + 0.2 * k)
        place(keys(note(ch[0] - 12), bar, 1.2), t0, 0.16)  # bass
        if t0 >= HOOK_END - 0.01:  # arpeggio on eighths from the photo section
            arp = ch[1:] + [ch[0] + 12, ch[2] + 12, ch[1] + 12, ch[3], ch[2]]
            for k in range(8):
                place(keys(note(arp[k % len(arp)] + 12), 0.5, 0.18), t0 + k * BEAT / 2,
                      0.055, 0.5 if k % 2 else -0.5)

    # Drums: kick from the photo section, rim on 2 & 4, shaker on offbeats.
    t = HOOK_END
    k = 0
    while t < DUR - 1.2:
        if not (END_T0 - 0.05 < t < END_T0 + bar - 0.05):  # breathe at the logo
            place(kick(), t, 0.55)
            if k % 2:
                place(rim(), t, 0.16, 0.2)
            place(shaker(), t + BEAT / 2, 0.10, -0.2)
        t += BEAT
        k += 1

    # Hook: two soft hits for the two text lines.
    place(keys(note(77), 1.2, 0.5), 0.15, 0.10)
    place(keys(note(81), 1.2, 0.5), 0.55, 0.10)
    place(whoosh(0.5), HOOK_END - 0.45, 0.10)
    # Photo transitions: soft swish + pluck per card.
    for i in range(len(PHOTOS)):
        s = PH_T0 + i * PH_LEN
        place(whoosh(0.4), s - 0.35, 0.10, 0.3 if i % 2 else -0.3)
    place(whoosh(0.6), PROPS_T0 - 0.2, 0.12)
    # Value props: rising ticks.
    for n_, m in enumerate([72, 76, 79]):
        place(keys(note(m + 12), 0.6, 0.25), PROPS_T0 + 0.3 + n_ * 1.2, 0.14)
    # Logo: low swell + bloom chord.
    x = np.arange(int(2.5 * SR)) / SR
    place(np.sin(2 * np.pi * 43.65 * x) * np.exp(-x * 1.5), END_T0 + 0.1, 0.35)
    for k_, m in enumerate([65, 69, 72, 76, 81]):
        place(keys(note(m), 4.5, 1.6), END_T0 + 0.1 + k_ * 0.05, 0.10, -0.4 + 0.2 * k_)

    env = np.minimum(1, tt / 0.3) * np.clip((DUR - tt) / 1.5, 0, 1)
    out *= env[:, None]
    out = np.tanh(out * 1.1)
    pcm = (np.clip(out, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def main():
    wav = os.path.join(HERE, "_score.wav")
    mp4 = os.path.join(HERE, "d3d_promo_preview.mp4" if PREVIEW else "d3d_promo.mp4")
    print("synthesizing score...")
    synth_audio(wav)
    vf = "eq=contrast=1.03:saturation=1.06,noise=alls=2:allf=t,format=yuv420p"
    af = "aecho=0.8:0.6:70|110:0.20|0.14,loudnorm=I=-14:TP=-1.0:LRA=9"
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", wav, "-vf", vf, "-af", af,
           "-c:v", "libx264", "-preset", "slow", "-crf", "19", "-profile:v", "high",
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-movflags", "+faststart", "-shortest", mp4]
    enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    print(f"rendering {NFRAMES} frames at {W}x{H}...")
    with Pool(os.cpu_count()) as pool:
        for k, buf in enumerate(pool.imap(render_frame, range(NFRAMES), chunksize=4)):
            enc.stdin.write(buf)
            if k % 120 == 0:
                print(f"  frame {k}/{NFRAMES}")
    enc.stdin.close()
    if enc.wait() != 0:
        sys.exit("ffmpeg failed")
    os.remove(wav)
    print("wrote", mp4)


if __name__ == "__main__":
    main()
