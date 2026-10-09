#!/usr/bin/env python3
"""Render a 16-second motion-graphics promo for the Tic-Tac-Toe game.

Everything is generated from code: animated background, neon board with
stroke-on marks, kinetic typography, camera shake, a synthesized score and
sound effects. ffmpeg handles the grade, film grain, loudness mastering
and the H.264 delivery encode.

Usage:  python3 promo/make_promo.py [--preview]
Needs:  python3 with numpy + Pillow, and ffmpeg on PATH.
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
W, H = (960, 540) if PREVIEW else (1920, 1080)
S = W / 1920  # layout is authored at 1080p and scaled
FPS = 30
DUR = 16.0
NFRAMES = int(DUR * FPS)
SR = 48000
BEAT = 0.5  # 120 BPM

FONT_DIR = "/usr/share/fonts/opentype/inter"
F_BLACK = os.path.join(FONT_DIR, "InterDisplay-Black.otf")
F_SEMI = os.path.join(FONT_DIR, "Inter-SemiBold.otf")
F_MED = os.path.join(FONT_DIR, "Inter-Medium.otf")
F_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

BG_A = np.array([16, 22, 44], np.float32)
BG_B = np.array([4, 6, 14], np.float32)
CYAN = (34, 211, 238)
PINK = (244, 114, 182)
AMBER = (251, 191, 36)
WHITE = (241, 245, 249)
GREY = (148, 163, 184)

# Game: X takes the centre, sets up a fork on move 5 and wins on the 2-4-6 diagonal.
MOVES = [(4, "X"), (1, "O"), (0, "X"), (8, "O"), (6, "X"), (3, "O"), (2, "X")]
MOVE_T0 = 2.0
WIN_T = MOVE_T0 + len(MOVES) * BEAT  # 5.5
WIN_CELLS = (2, 4, 6)
TRANS_T = 7.0
CARDS = [("VS  AI", "MODE 01", "Outsmart the machine", CYAN),
         ("1 v 1", "MODE 02", "Same screen. Same couch.", PINK),
         ("ONLINE", "MODE 03", "Host a server. Invite a rival.", AMBER)]
CARD_T0, CARD_LEN = 7.5, 4.0 / 3
END_T = 11.5


# ---------------------------------------------------------------- easing
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def prog(t, start, dur):
    return clamp((t - start) / dur)


def ease_out_cubic(x):
    return 1 - (1 - x) ** 3


def ease_in_cubic(x):
    return x ** 3


def ease_in_out(x):
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def ease_out_expo(x):
    return 1.0 if x >= 1 else 1 - 2 ** (-10 * x)


def ease_out_back(x, s=1.9):
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


def font(path, size):
    return ImageFont.truetype(path, max(1, int(size * S)))


# ---------------------------------------------------------------- background
_yy, _xx = np.mgrid[0:H // 4, 0:W // 4].astype(np.float32)
_xx /= (W // 4)
_yy /= (H // 4)
_rng = np.random.default_rng(7)
PARTICLES = _rng.random((70, 4))  # x, y, speed, size


def background(t):
    cx = 0.5 + 0.12 * math.sin(t * 0.35)
    cy = 0.45 + 0.08 * math.cos(t * 0.27)
    d = np.sqrt(((_xx - cx) * 1.7) ** 2 + (_yy - cy) ** 2)
    k = np.clip(d / 0.9, 0, 1)[..., None]
    small = BG_A * (1 - k) + BG_B * k
    # Accent bloom that follows the current scene colour.
    if t < TRANS_T:
        tint = np.array(CYAN, np.float32)
    elif t < END_T:
        i = min(2, int((t - CARD_T0) / CARD_LEN)) if t >= CARD_T0 else 0
        tint = np.array(CARDS[i][3], np.float32)
    else:
        tint = np.array(PINK, np.float32)
    d2 = np.sqrt(((_xx - (1 - cx)) * 1.7) ** 2 + (_yy - (1 - cy * 0.8)) ** 2)
    small += tint * (0.07 * np.clip(1 - d2 / 0.6, 0, 1) ** 2)[..., None]
    img = Image.fromarray(small.astype(np.uint8)).resize((W, H), Image.BICUBIC)
    arr = np.asarray(img, np.float32).copy()
    # Drifting dust particles.
    for px, py, sp, sz in PARTICLES:
        x = int(px * W)
        y = int(((py - t * (0.01 + 0.025 * sp)) % 1.0) * H)
        r = max(1, int((1 + 2 * sz) * S))
        a = 0.10 + 0.25 * sz
        arr[max(0, y - r):y + r, max(0, x - r):x + r] += 255 * a * 0.5
    return arr


# ---------------------------------------------------------------- board
BOARD = 600          # board side in 1080p px
MARGIN = 60          # room for glow / strokes outside the grid
SS = 2               # supersampling for crisp antialiased strokes
BL = int((BOARD + 2 * MARGIN) * S)  # board layer size at output res


def _cell_center(i):
    c = BOARD / 3
    return MARGIN + (i % 3 + 0.5) * c, MARGIN + (i // 3 + 0.5) * c


def _line(d, p0, p1, frac, width, color):
    if frac <= 0:
        return
    k = SS * S
    x0, y0 = p0
    x1, y1 = x0 + (p1[0] - x0) * frac, y0 + (p1[1] - y0) * frac
    w = width * k
    d.line([(x0 * k, y0 * k), (x1 * k, y1 * k)], fill=color, width=int(w))
    for x, y in ((x0, y0), (x1, y1)):  # round caps
        d.ellipse([x * k - w / 2, y * k - w / 2, x * k + w / 2, y * k + w / 2], fill=color)


def board_layer(t):
    """Board grid, marks and win line, drawn at SS x then downsampled."""
    size = BL * SS
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = BOARD / 3
    gcol = (200, 214, 240, 150)
    # Grid lines draw on, staggered, from 0.3s.
    lines = [((MARGIN + c, MARGIN), (MARGIN + c, MARGIN + BOARD)),
             ((MARGIN + 2 * c, MARGIN + BOARD), (MARGIN + 2 * c, MARGIN)),
             ((MARGIN, MARGIN + c), (MARGIN + BOARD, MARGIN + c)),
             ((MARGIN + BOARD, MARGIN + 2 * c), (MARGIN, MARGIN + 2 * c))]
    for n, (a, b) in enumerate(lines):
        _line(d, a, b, ease_in_out(prog(t, 0.3 + n * 0.25, 0.7)), 7, gcol)

    k = SS * S
    for n, (cell, who) in enumerate(MOVES):
        p = ease_out_cubic(prog(t, MOVE_T0 + n * BEAT, 0.3))
        if p <= 0:
            continue
        cx, cy = _cell_center(cell)
        r = c * 0.28
        if who == "X":
            _line(d, (cx - r, cy - r), (cx + r, cy + r), clamp(p * 2), 20, CYAN + (255,))
            _line(d, (cx + r, cy - r), (cx - r, cy + r), clamp(p * 2 - 1), 20, CYAN + (255,))
        else:
            w = 18 * k
            box = [(cx - r) * k, (cy - r) * k, (cx + r) * k, (cy + r) * k]
            d.arc(box, -90, -90 + 360 * p, fill=PINK + (255,), width=int(w))
        # Ring burst on placement.
        rb = prog(t, MOVE_T0 + n * BEAT, 0.45)
        if 0 < rb < 1:
            rr = r * (0.8 + 1.1 * ease_out_cubic(rb))
            col = (CYAN if who == "X" else PINK) + (int(170 * (1 - rb)),)
            d.ellipse([(cx - rr) * k, (cy - rr) * k, (cx + rr) * k, (cy + rr) * k],
                      outline=col, width=int(4 * k))

    # Win strike-through.
    wp = ease_out_expo(prog(t, WIN_T, 0.35))
    if wp > 0:
        a, b = _cell_center(WIN_CELLS[0]), _cell_center(WIN_CELLS[-1])
        ext = 0.42 * c / math.sqrt(2) * 2
        ux, uy = (b[0] - a[0]), (b[1] - a[1])
        ln = math.hypot(ux, uy)
        ux, uy = ux / ln, uy / ln
        p0 = (a[0] - ux * ext, a[1] - uy * ext)
        p1 = (b[0] + ux * ext, b[1] + uy * ext)
        _line(d, p0, p1, wp, 14, (255, 255, 255, 255))
    return img.resize((BL, BL), Image.LANCZOS)


# ---------------------------------------------------------------- compositing
def over(dst, layer, x, y, alpha=1.0):
    """Alpha-composite an RGBA PIL layer onto a float RGB array at (x, y)."""
    src = np.asarray(layer, np.float32)
    h, w = src.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    s = src[y0 - y:y1 - y, x0 - x:x1 - x]
    a = s[..., 3:4] / 255.0 * alpha
    reg = dst[y0:y1, x0:x1]
    reg *= 1 - a
    reg += s[..., :3] * a


def add_glow(dst, layer, x, y, strength, radius=10):
    """Additive bloom from a layer (blurred at quarter res for speed)."""
    w, h = layer.size
    small = layer.resize((max(1, w // 4), max(1, h // 4)), Image.BILINEAR)
    small = small.filter(ImageFilter.GaussianBlur(radius * S))
    big = np.asarray(small.resize((w, h), Image.BILINEAR), np.float32)
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    g = big[y0 - y:y1 - y, x0 - x:x1 - x]
    dst[y0:y1, x0:x1] += g[..., :3] * (g[..., 3:4] / 255.0) * strength


def text_image(txt, fnt, color, tracking=0):
    """Render text (with letter spacing) to a tight RGBA image."""
    chars = list(txt)
    widths = [fnt.getlength(ch) for ch in chars]
    asc, desc = fnt.getmetrics()
    tw = int(sum(widths) + tracking * S * (len(chars) - 1)) + 4
    img = Image.new("RGBA", (max(1, tw), asc + desc + 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = 2
    for ch, w in zip(chars, widths):
        d.text((x, 2), ch, font=fnt, fill=color + (255,))
        x += w + tracking * S
    return img


# Pre-rendered type (built lazily per worker process).
_CACHE = {}


def assets():
    if _CACHE:
        return _CACHE
    big = font(F_BLACK, 230)
    lab = font(F_SEMI, 30)
    sub = font(F_MED, 46)
    _CACHE["cards"] = [(text_image(w, big, WHITE, 4),
                        text_image(l, lab, col, 10),
                        text_image(s_, sub, GREY), col)
                       for w, l, s_, col in CARDS]
    tf = font(F_BLACK, 190)
    title = [("TIC", CYAN), ("·", GREY), ("TAC", WHITE), ("·", GREY), ("TOE", PINK)]
    glyphs = []
    for word, col in title:
        for ch in word:
            glyphs.append((text_image(ch, tf, col), tf.getlength(ch) + 6 * S))
    _CACHE["title"] = glyphs
    _CACHE["tag"] = text_image("Three in a row. Endless rematches.", font(F_MED, 46), GREY)
    _CACHE["cmd"] = text_image("$ python main.py", font(F_MONO, 38), WHITE)
    _CACHE["kicker"] = text_image("NOW PLAYABLE", font(F_SEMI, 28), AMBER, 12)
    return _CACHE


# ---------------------------------------------------------------- scenes
def scene_board(frame, t):
    if t >= TRANS_T + 0.6:
        return
    layer = board_layer(t)
    # Intro push-in, then whip zoom out of the scene.
    scale = 0.9 + 0.1 * ease_out_cubic(prog(t, 0, 2.0))
    tp = ease_in_cubic(prog(t, TRANS_T, 0.5))
    scale *= 1 + 2.2 * tp
    alpha = 1 - tp
    # Punch-in on the win.
    wp = prog(t, WIN_T, 0.6)
    if 0 < wp < 1:
        scale *= 1 + 0.06 * math.sin(math.pi * wp) * (1 - wp)
    if tp > 0:  # directional blur while whipping
        layer = layer.filter(ImageFilter.GaussianBlur(12 * tp * S))
    sz = max(1, int(BL * scale))
    layer = layer.resize((sz, sz), Image.BILINEAR)
    x, y = W // 2 - sz // 2, H // 2 - sz // 2
    add_glow(frame, layer, x, y, 1.2 * alpha)
    over(frame, layer, x, y, alpha)

    # Small "WINNER" caption after the strike.
    cp = ease_out_cubic(prog(t, WIN_T + 0.35, 0.4))
    if cp > 0 and alpha > 0:
        cap = assets()["kicker"]
        if "win" not in _CACHE:
            _CACHE["win"] = text_image("X WINS", font(F_BLACK, 64), CYAN, 6)
        im = _CACHE["win"]
        yy = int(H / 2 + (BOARD / 2 + 70) * S * scale + 20 * S * (1 - cp))
        over(frame, im, W // 2 - im.width // 2, yy, cp * alpha)
        add_glow(frame, im, W // 2 - im.width // 2, yy, 0.8 * cp * alpha)
        del cap


def scene_cards(frame, t):
    if not (CARD_T0 <= t < END_T + 0.3):
        return
    for i, (word, lab, sub, col) in enumerate(assets()["cards"]):
        s0 = CARD_T0 + i * CARD_LEN
        s1 = s0 + CARD_LEN
        if not (s0 <= t < s1 + 0.01):
            continue

        def xoff(tt):
            pin = ease_out_expo(prog(tt, s0, 0.45))
            pout = ease_in_cubic(prog(tt, s1 - 0.25, 0.25))
            return (1 - pin) * 1300 * S - pout * 1500 * S

        # Motion blur: average sub-frame samples of the moving headline.
        samples = 7
        acc = np.zeros_like(frame)
        acc_a = 0.0
        for n in range(samples):
            tt = t - (n / samples) * (1 / FPS) * 0.9
            tmp = frame.copy()
            x = int(W / 2 - word.width / 2 + xoff(tt))
            y = int(H / 2 - word.height / 2 - 10 * S)
            over(tmp, word, x, y)
            acc += tmp
            acc_a += 1
        frame[:] = acc / acc_a
        x = int(W / 2 - word.width / 2 + xoff(t))
        y = int(H / 2 - word.height / 2 - 10 * S)
        add_glow(frame, word, x, y, 0.35)

        # Label, accent bar and subline with offset timing (parallax).
        fade = ease_out_cubic(prog(t, s0 + 0.15, 0.3)) * (1 - prog(t, s1 - 0.2, 0.2))
        lx = int(W / 2 - lab.width / 2 + xoff(t) * 0.5)
        over(frame, lab, lx, int(y - 30 * S), fade)
        bw = int(420 * S * ease_out_expo(prog(t, s0 + 0.25, 0.5)) * (1 - prog(t, s1 - 0.2, 0.2)))
        if bw > 0:
            by = int(y + word.height + 10 * S)
            frame[by:by + max(2, int(8 * S)), W // 2 - bw // 2:W // 2 + bw // 2] = col
        sx = int(W / 2 - sub.width / 2 + xoff(t) * 0.3)
        over(frame, sub, sx, int(y + word.height + 45 * S), fade)


def scene_end(frame, t):
    if t < END_T:
        return
    a = assets()
    glyphs = a["title"]
    total = sum(w for _, w in glyphs)
    x = W / 2 - total / 2
    base_y = H / 2 - 150 * S
    for n, (g, adv) in enumerate(glyphs):
        p = prog(t, END_T + n * 0.045, 0.5)
        if p > 0:
            sc = max(0.01, ease_out_back(p))
            gw, gh = max(1, int(g.width * sc)), max(1, int(g.height * sc))
            gi = g.resize((gw, gh), Image.BILINEAR)
            cx = x + g.width / 2
            cy = base_y + g.height / 2 + (1 - ease_out_cubic(p)) * 60 * S
            px, py = int(cx - gw / 2), int(cy - gh / 2)
            add_glow(frame, gi, px, py, 0.6 * min(1, p * 2))
            over(frame, gi, px, py, min(1, p * 3))
        x += adv

    tp = ease_out_cubic(prog(t, END_T + 1.0, 0.6))
    tag = a["tag"]
    over(frame, tag, W // 2 - tag.width // 2, int(base_y + 250 * S + 25 * S * (1 - tp)), tp)

    cp = ease_out_back(prog(t, END_T + 1.6, 0.5), 1.4)
    if cp > 0:
        cmd = a["cmd"]
        pw, ph = cmd.width + int(70 * S), cmd.height + int(36 * S)
        pill = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
        ImageDraw.Draw(pill).rounded_rectangle(
            [0, 0, pw - 1, ph - 1], radius=ph // 2, fill=(15, 23, 42, 230),
            outline=AMBER + (255,), width=max(1, int(3 * S)))
        pill.alpha_composite(cmd, (int(35 * S), int(16 * S)))
        sc = max(0.01, cp)
        pi = pill.resize((max(1, int(pw * sc)), max(1, int(ph * sc))), Image.BILINEAR)
        py = int(base_y + 360 * S)
        add_glow(frame, pi, W // 2 - pi.width // 2, py, 0.35 * min(1, cp))
        over(frame, pi, W // 2 - pi.width // 2, py, min(1, cp))

    kp = ease_out_cubic(prog(t, END_T + 2.0, 0.5))
    k = a["kicker"]
    over(frame, k, W // 2 - k.width // 2, int(base_y - 70 * S), kp)


def camera(img, t):
    """Shake on impacts (win strike, title slam)."""
    amp = 0.0
    for t0, strength in ((WIN_T, 14), (END_T, 9)):
        p = prog(t, t0, 0.5)
        if 0 < p < 1:
            amp += strength * (1 - p) ** 2
    if amp <= 0.01:
        return img
    dx = amp * S * math.sin(t * 91.0)
    dy = amp * S * math.cos(t * 73.0)
    z = 1.015
    return img.transform(img.size, Image.AFFINE,
                         (1 / z, 0, dx + W * (1 - 1 / z) / 2, 0, 1 / z, dy + H * (1 - 1 / z) / 2),
                         Image.BICUBIC)


def render_frame(i):
    t = i / FPS
    frame = background(t)
    scene_board(frame, t)
    scene_cards(frame, t)
    scene_end(frame, t)
    # White flash on the win and the title slam.
    for t0, k in ((WIN_T, 0.35), (END_T, 0.25)):
        p = prog(t, t0, 0.35)
        if 0 < p < 1:
            frame += 255 * k * (1 - p) ** 2
    fade = min(prog(t, 0, 0.4), 1 - prog(t, DUR - 0.6, 0.6))
    frame *= fade
    img = Image.fromarray(np.clip(frame, 0, 255).astype(np.uint8))
    return camera(img, t).tobytes()


# ---------------------------------------------------------------- audio
def synth_audio(path):
    n = int(DUR * SR)
    out = np.zeros((n, 2), np.float32)
    rng = np.random.default_rng(3)
    tt = np.arange(n) / SR

    def place(sig, t0, gain=1.0, pan=0.0):
        s = int(t0 * SR)
        e = min(n, s + len(sig))
        if s >= n or e <= s:
            return
        l, r = math.cos((pan + 1) * math.pi / 4), math.sin((pan + 1) * math.pi / 4)
        out[s:e, 0] += sig[:e - s] * gain * l * 1.414
        out[s:e, 1] += sig[:e - s] * gain * r * 1.414

    def env(length, attack, decay):
        x = np.arange(int(length * SR)) / SR
        return np.minimum(1, x / max(attack, 1e-4)) * np.exp(-x / decay)

    def smooth(x, k):
        return np.convolve(x, np.ones(k) / k, mode="same")

    def note(m):
        return 440.0 * 2 ** ((m - 69) / 12)

    def kick():
        x = np.arange(int(0.45 * SR)) / SR
        f = 45 + 110 * np.exp(-x * 30)
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 7)

    def hat():
        nz = rng.standard_normal(int(0.06 * SR))
        return (nz - smooth(nz, 6)) * env(0.06, 0.001, 0.015)

    def pluck(freq, length=0.6):
        x = np.arange(int(length * SR)) / SR
        s = np.sin(2 * np.pi * freq * x) + 0.35 * np.sin(4 * np.pi * freq * x) + 0.12 * np.sin(6 * np.pi * freq * x)
        return s * env(length, 0.002, 0.16)

    def whoosh(length, rise=True):
        nz = rng.standard_normal(int(length * SR))
        lp = smooth(nz, 18)
        x = np.linspace(0, 1, len(nz))
        e = x ** 2 if rise else (1 - x) ** 2
        return lp * e * np.sin(np.pi * x) ** 0.3 * 3

    def impact():
        x = np.arange(int(1.4 * SR)) / SR
        boom = np.sin(2 * np.pi * (40 + 60 * np.exp(-x * 12)) * x) * np.exp(-x * 3.0)
        nz = smooth(rng.standard_normal(len(x)), 4) * np.exp(-x * 9)
        return boom + 0.6 * nz

    # Pad: Am - F - C - G, two seconds per chord, detuned stacked sines.
    chords = [[57, 60, 64, 69], [53, 57, 60, 65], [48, 55, 60, 64], [55, 59, 62, 67]]
    pad = np.zeros(n, np.float32)
    for ci in range(int(DUR / 2)):
        ch = chords[ci % 4]
        seg = (tt >= ci * 2) & (tt < ci * 2 + 2.2)
        x = tt[seg] - ci * 2
        e = np.minimum(1, x / 0.4) * np.minimum(1, np.maximum(0, 2.2 - x) / 0.4)
        for m in ch:
            for det in (-0.12, 0.12):
                f = note(m + det)
                pad[seg] += (np.sin(2 * np.pi * f * x) + 0.25 * np.sin(4 * np.pi * f * x)) * e * 0.05
    pad *= np.minimum(1, tt / 1.5) * np.clip((DUR - tt) / 1.2, 0, 1)
    out[:, 0] += pad
    out[:, 1] += np.roll(pad, int(0.012 * SR))  # Haas widening

    # Grid draw ticks.
    for k in range(4):
        place(pluck(note(81), 0.25), 0.3 + k * 0.25, 0.25, -0.5 + k / 3)
    place(whoosh(1.6), 0.4, 0.25)

    # Drums + bass from the first move until the end card, with a drop at the transition.
    bass_line = [45, 45, 41, 41, 48, 48, 43, 43]
    t = MOVE_T0
    while t < DUR - 1.0:
        if not (TRANS_T - 0.01 < t < CARD_T0):
            place(kick(), t, 0.9)
            place(hat(), t + BEAT / 2, 0.35, 0.3)
            if t >= CARD_T0:
                place(hat(), t + BEAT / 4, 0.18, -0.3)
            m = bass_line[int((t // 2) % 4) * 2]
            x = np.arange(int(0.45 * SR)) / SR
            f = note(m - 12)
            bass = np.tanh(2.5 * np.sin(2 * np.pi * f * x)) * env(0.45, 0.005, 0.25)
            place(bass, t, 0.30)
            place(bass, t + BEAT / 2, 0.18)
        t += BEAT

    # Move plinks: X high, O lower; panned by column.
    for n_, (cell, who) in enumerate(MOVES):
        f = note(76 + 2 * (n_ % 3)) if who == "X" else note(69 + 2 * (n_ % 2))
        place(pluck(f), MOVE_T0 + n_ * BEAT, 0.45, (cell % 3 - 1) * 0.5)

    # Riser into the win, impact, sparkle.
    place(whoosh(1.0), WIN_T - 1.0, 0.35)
    place(impact(), WIN_T, 0.9)
    for k, m in enumerate([81, 84, 88, 93]):
        place(pluck(note(m), 0.8), WIN_T + 0.06 * k, 0.25, -0.6 + 0.4 * k)

    # Transition whip + card whooshes and hits.
    place(whoosh(0.6), TRANS_T, 0.6)
    for i in range(3):
        s0 = CARD_T0 + i * CARD_LEN
        place(whoosh(0.35, rise=False), s0, 0.45, 0.5)
        place(pluck(note(57 + 5 * i), 0.5), s0 + 0.05, 0.4)
    place(whoosh(0.6), END_T - 0.6, 0.45)

    # Title slam and final ring-out chord.
    place(impact(), END_T, 1.0)
    for k, m in enumerate([57, 64, 69, 72, 76]):
        place(pluck(note(m), 3.5) * 0.6, END_T + 0.02 * k, 0.35, -0.5 + 0.25 * k)

    out = np.tanh(out * 0.9)  # soft-clip bus
    pcm = (np.clip(out, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


# ---------------------------------------------------------------- main
def main():
    out_dir = HERE
    wav = os.path.join(out_dir, "_score.wav")
    mp4 = os.path.join(out_dir, "tictactoe_promo_preview.mp4" if PREVIEW else "tictactoe_promo.mp4")
    print("synthesizing score...")
    synth_audio(wav)

    vf = ("eq=contrast=1.06:saturation=1.12:gamma=0.98,"
          "vignette=angle=PI/5,"
          "noise=alls=3:allf=t,"
          "format=yuv420p")
    af = ("aecho=0.8:0.5:55|89:0.18|0.12,"
          "loudnorm=I=-14:TP=-1.0:LRA=9")
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", wav,
           "-vf", vf, "-af", af,
           "-c:v", "libx264", "-preset", "slow", "-crf", "21", "-profile:v", "high",
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-movflags", "+faststart", "-shortest", mp4]
    enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    print(f"rendering {NFRAMES} frames at {W}x{H}...")
    with Pool(os.cpu_count()) as pool:
        for k, buf in enumerate(pool.imap(render_frame, range(NFRAMES), chunksize=4)):
            enc.stdin.write(buf)
            if k % 60 == 0:
                print(f"  frame {k}/{NFRAMES}")
    enc.stdin.close()
    if enc.wait() != 0:
        sys.exit("ffmpeg failed")
    os.remove(wav)
    print("wrote", mp4)


if __name__ == "__main__":
    main()
