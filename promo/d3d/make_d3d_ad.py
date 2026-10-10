#!/usr/bin/env python3
"""D3D conversion ad: 1080x1920 (9:16), 16 s, built entirely from product photos.

Structure (120 BPM, cuts on the beat):
  0-2 s    hook      full-bleed product shot + "Votre logo -> en porte-clés"
  2-4 s    process   simulated 3D print, layer by layer
  4-8 s    proof     8 beat-synced cuts of real client orders
  8-12 s   offer     3,5 DT / pièce, min. 20 pcs, emballage + conception offerts
  12-16 s  CTA       "Envoyez votre logo" + phone + @d3d.tn on brand yellow

Usage:  python3 promo/d3d/make_d3d_ad.py [--preview]
"""
import math
import os
import subprocess
import sys
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

import premium_audio
from make_d3d_promo import (F_BLACK, F_BOLD, F_LAB, F_MED, F_SEMI, INK, YELLOW, clamp,
                            ease_in_cubic, ease_in_out, ease_out_back, ease_out_cubic,
                            ease_out_expo, font, over, prog, px, reveal, text_image)

HERE = os.path.dirname(os.path.abspath(__file__))
PREVIEW = "--preview" in sys.argv
W, H = (540, 960) if PREVIEW else (1080, 1920)
FPS = 30
DUR = 16.0
NFRAMES = int(DUR * FPS)
SR = 48000
BEAT = 0.5
WHITE = (255, 255, 255)

T_PRINT, T_PROOF, T_OFFER, T_CTA = 2.0, 4.0, 8.0, 12.0
MONTAGE = ["m1_sks", "m2_atelier", "m3_ego", "m4_peaktime",
           "m5_sceg", "m6_delivery", "m7_9ne", "m8_bluema"]
CHECKS = ["Minimum 20 pièces", "Anneau + chaîne inclus",
          "Emballage offert", "Conception 3D gratuite"]


# ------------------------------------------------------------------ helpers
def load(name):
    return Image.open(os.path.join(HERE, "photos_ad", f"{name}.jpg")).convert("RGB").resize(
        (int(W * 1.15), int(H * 1.15)), Image.LANCZOS)


def kenburns(src, k, punch=0.0, drift=(0, 0)):
    """Crop a zoom window out of an oversized photo. k: 0..1 slow push, punch: extra zoom."""
    z = 1.15 - 0.10 * k - 0.05 * punch
    w, h = W * z, H * z
    ox = clamp((src.width - w) / 2 + drift[0] * px(30) * (k - 0.5), 0, src.width - w)
    oy = clamp((src.height - h) / 2 + drift[1] * px(30) * (k - 0.5), 0, src.height - h)
    return np.asarray(src.resize((W, H), Image.BILINEAR, box=(ox, oy, ox + w, oy + h)), np.float32)


def boxed(txt, fnt, fg, bg, padx=26, pady=10, radius=14):
    """Text on a solid rounded label (highlight-marker look)."""
    t = text_image(txt, fnt, fg, -1)
    w, h = t.width + px(2 * padx), t.height + px(2 * pady) - px(8)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([0, 0, w - 1, h - 1], radius=px(radius), fill=bg + (255,))
    im.alpha_composite(t, (px(padx), px(pady) - px(6)))
    return im


def shadowed(txt, fnt, color=WHITE, tracking=-2):
    """White headline with a soft drop shadow for legibility on photos."""
    t = text_image(txt, fnt, color, tracking)
    pad = px(30)
    sh = Image.new("RGBA", (t.width + 2 * pad, t.height + 2 * pad), (0, 0, 0, 0))
    a = t.getchannel("A").point(lambda v: int(v * 0.55))
    blk = Image.new("RGBA", t.size, (0, 0, 0, 255))
    blk.putalpha(a)
    sh.alpha_composite(blk, (pad, pad + px(6)))
    sh = sh.filter(ImageFilter.GaussianBlur(px(12)))
    sh.alpha_composite(t, (pad, pad))
    return sh


def pop(frame, img, cx, cy, p, alpha=1.0):
    """Scale-pop an image centred at (cx, cy) with overshoot."""
    if p <= 0:
        return
    sc = max(0.01, ease_out_back(p, 2.2))
    im = img.resize((max(1, int(img.width * sc)), max(1, int(img.height * sc))), Image.BILINEAR)
    over(frame, im, int(cx - im.width / 2), int(cy - im.height / 2), min(1, p * 3) * alpha)


def grad(top, bottom, strength):
    """Vertical darkening ramp (top/bottom fractions of the frame)."""
    y = np.linspace(0, 1, H, dtype=np.float32)
    g = np.maximum(np.clip((top - y) / top, 0, 1) if top else 0,
                   np.clip((y - (1 - bottom)) / bottom, 0, 1) if bottom else 0)
    return (1 - strength * g ** 1.5)[:, None, None]


_A = {}


def assets():
    if _A:
        return _A
    _A["hook"] = load("hook_sodip")
    _A["print"] = load("print_gomycode")
    _A["montage"] = [load(n) for n in MONTAGE]
    ob = load("offer_bg").filter(ImageFilter.GaussianBlur(px(18)))
    ob = ImageEnhance.Brightness(ImageEnhance.Color(ob).enhance(0.4)).enhance(0.32)
    _A["offer_bg"] = np.asarray(ob.crop((0, 0, W, H)), np.float32)
    # Ghost "blueprint" version of the print photo (above the print line).
    pg = _A["print"].convert("L").filter(ImageFilter.FIND_EDGES).point(lambda v: min(255, v * 3))
    _A["print_ghost"] = pg
    _A["g_bottom"] = grad(0, 0.45, 0.75)
    _A["g_both"] = grad(0.30, 0.40, 0.70)

    big = font(F_BLACK, 118)
    _A["h1"] = shadowed("Votre logo", big)
    _A["h2"] = boxed("en porte-clés", font(F_BLACK, 112), INK, YELLOW)
    _A["h3"] = shadowed("pour vos clients & événements", font(F_SEMI, 46), WHITE, 0)
    _A["p1"] = boxed("IMPRESSION 3D", font(F_LAB, 34), INK, YELLOW, 20, 10, 10)
    _A["p2"] = shadowed("couche par couche", font(F_BLACK, 84))
    _A["pr1"] = boxed("ILS NOUS ONT FAIT CONFIANCE", font(F_LAB, 34), INK, YELLOW, 22, 12, 10)
    _A["pr2"] = shadowed("Qualité premium", font(F_BLACK, 92))
    _A["o_lab"] = text_image("SEULEMENT", font(F_LAB, 36), YELLOW, 10)
    _A["o_unit"] = text_image("par pièce", font(F_SEMI, 52), WHITE)
    _A["o_digits"] = {c: text_image(c, font(F_BLACK, 250), WHITE, 0) for c in "0123456789,"}
    _A["o_dt"] = text_image("DT", font(F_BLACK, 120), YELLOW)
    _A["checks"] = [text_image(c, font(F_SEMI, 58), WHITE, -1) for c in CHECKS]
    _A["c1"] = text_image("Envoyez-nous", font(F_BLACK, 104), INK, -2)
    _A["c2"] = text_image("votre logo", font(F_BLACK, 104), INK, -2)
    _A["c3"] = text_image("On vous envoie la maquette 3D gratuite", font(F_MED, 40), INK)
    _A["c_dm"] = text_image("DM  @d3d.tn", font(F_BLACK, 64), YELLOW, 1)
    _A["c_tel"] = text_image("+216 25 430 387", font(F_BLACK, 64), INK, 1)
    _A["c_tlab"] = text_image("OU APPELEZ", font(F_LAB, 30), INK, 8)
    _A["c_brand"] = text_image("D3D", font(F_BLACK, 70), INK, 1)
    _A["c_min"] = text_image("3,5 DT / pièce · dès 20 pcs", font(F_SEMI, 40), INK)
    return _A


def check_icon(r):
    im = Image.new("RGBA", (4 * r, 4 * r), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([0, 0, 4 * r - 1, 4 * r - 1], fill=YELLOW + (255,))
    d.line([(r * 1.1, r * 2.1), (r * 1.75, r * 2.75), (r * 2.95, r * 1.35)],
           fill=INK + (255,), width=max(2, int(r * 0.42)), joint="curve")
    return im.resize((2 * r, 2 * r), Image.LANCZOS)


# ------------------------------------------------------------------ scenes
def scene_hook(t):
    a = assets()
    f = kenburns(a["hook"], prog(t, 0, T_PRINT), punch=1 - ease_out_expo(prog(t, 0, 0.5)), drift=(1, -1))
    f *= a["g_bottom"]
    h1, h2, h3 = a["h1"], a["h2"], a["h3"]
    y = px(1150)
    reveal(f, h1, W // 2 - h1.width // 2, y, prog(t, 0.05, 0.5))
    h2y = y + h1.height + px(10)
    pop(f, h2, W // 2, h2y + h2.height // 2, prog(t, 0.45, 0.45))
    p3 = ease_out_cubic(prog(t, 0.9, 0.4))
    over(f, h3, W // 2 - h3.width // 2, h2y + h2.height + px(5) + int(px(16) * (1 - p3)), p3)
    return f


def scene_print(t):
    a = assets()
    lt = t - T_PRINT
    k = prog(lt, 0, 2.0)
    sharp = kenburns(a["print"], k, drift=(0, 1))
    ghost = a["print_ghost"].resize((W, H), Image.BILINEAR, box=(
        (a["print"].width - W * (1.15 - 0.1 * k)) / 2, (a["print"].height - H * (1.15 - 0.1 * k)) / 2,
        (a["print"].width + W * (1.15 - 0.1 * k)) / 2, (a["print"].height + H * (1.15 - 0.1 * k)) / 2))
    g = np.asarray(ghost, np.float32)[..., None] / 255.0
    blueprint = np.empty_like(sharp)
    blueprint[:] = (14, 16, 22)
    blueprint += g * np.array([90, 150, 255], np.float32) * 0.55
    # Faint build-plate grid.
    step = px(60)
    blueprint[::step, :] += 10
    blueprint[:, ::step] += 10
    # Print line climbs bottom -> top in discrete layers.
    pp = ease_in_out(prog(lt, 0.1, 1.5))
    layer = max(2, px(14))
    line_y = int(H - (H + layer) * pp) // layer * layer
    f = blueprint
    if line_y < H:
        f[max(0, line_y):] = sharp[max(0, line_y):]
    if 0 < line_y < H:
        band = slice(max(0, line_y - px(5)), min(H, line_y + px(5)))
        f[band] = f[band] * 0.2 + np.array(YELLOW, np.float32) * 0.8 + 40
        glow = slice(max(0, line_y - px(60)), line_y)
        ramp = np.linspace(0, 1, glow.stop - glow.start, dtype=np.float32)[:, None, None]
        f[glow] += ramp * np.array(YELLOW, np.float32) * 0.35
        # Nozzle sweeping across the current layer.
        nx = int((0.5 + 0.45 * math.sin(lt * 9)) * W)
        f[max(0, line_y - px(14)):line_y + px(6), max(0, nx - px(10)):nx + px(10)] = 255
    f *= a["g_both"]
    p1, p2 = a["p1"], a["p2"]
    y = px(300)
    pop(f, p1, W // 2, y + p1.height // 2, prog(lt, 0.05, 0.4))
    reveal(f, p2, W // 2 - p2.width // 2, y + px(70), prog(lt, 0.25, 0.5))
    # Flash as the print completes.
    fl = prog(lt, 1.6, 0.3)
    if 0 < fl < 1:
        f += 120 * (1 - fl) ** 2
    return f


def scene_proof(t):
    a = assets()
    lt = t - T_PROOF
    i = min(len(MONTAGE) - 1, int(lt / BEAT))
    k = (lt - i * BEAT) / BEAT
    f = kenburns(a["montage"][i], k, punch=1 - ease_out_expo(clamp(k * 2.5)),
                 drift=((-1) ** i, (-1) ** (i // 2)))
    f *= a["g_both"]
    pr1, pr2 = a["pr1"], a["pr2"]
    y = px(290)
    pop(f, pr1, W // 2, y + pr1.height // 2, prog(lt, 0.0, 0.4))
    # Second line appears halfway through the montage.
    reveal(f, pr2, W // 2 - pr2.width // 2, px(1380), prog(lt, 2.0, 0.5))
    return f


def scene_offer(t):
    a = assets()
    lt = t - T_OFFER
    f = a["offer_bg"].copy()
    # Dot pattern in brand yellow, very subtle.
    lab = a["o_lab"]
    y0 = px(330)
    reveal(f, lab, W // 2 - lab.width // 2, y0, prog(lt, 0.05, 0.4))
    # Price count-up 0,0 -> 3,5 then pop.
    cp = ease_out_cubic(prog(lt, 0.15, 0.6))
    val = 3.5 * cp
    s = f"{val:.1f}".replace(".", ",")
    digits = [a["o_digits"][c] for c in s]
    dt = a["o_dt"]
    total = sum(d.width for d in digits) + px(20) + dt.width
    sc = 1 + 0.12 * math.sin(math.pi * prog(lt, 0.75, 0.3))
    x = W / 2 - total * sc / 2
    py = px(420)
    for d in digits:
        im = d.resize((int(d.width * sc), int(d.height * sc)), Image.BILINEAR) if sc != 1 else d
        over(f, im, int(x), int(py - (im.height - d.height) / 2), min(1, lt * 5))
        x += im.width
    x += px(20)
    dtp = prog(lt, 0.7, 0.35)
    if dtp > 0:
        pop(f, dt, x + dt.width / 2, py + digits[0].height * 0.62, dtp)
    unit = a["o_unit"]
    up = ease_out_cubic(prog(lt, 0.9, 0.4))
    over(f, unit, W // 2 - unit.width // 2, py + px(280) + int(px(12) * (1 - up)), up)
    # Divider.
    dp = ease_out_expo(prog(lt, 1.0, 0.5))
    if dp > 0:
        dw = int(px(700) * dp)
        dy = py + px(380)
        f[dy:dy + max(1, px(3)), W // 2 - dw // 2:W // 2 + dw // 2] = (90, 90, 90)
    # Checklist on the beat.
    r = px(32)
    icon = check_icon(r)
    left = W // 2 - px(340)
    for n, im in enumerate(a["checks"]):
        t0 = 1.25 + n * BEAT
        ry = py + px(450) + n * px(120)
        pop(f, icon, left + r, ry + im.height // 2, prog(lt, t0, 0.35))
        reveal(f, im, left + 2 * r + px(28), ry, prog(lt, t0 + 0.05, 0.45))
    out = prog(lt, 3.85, 0.15)
    if out > 0:
        f = f * (1 - out) + np.array(YELLOW, np.float32) * out
    return f


def scene_cta(t):
    a = assets()
    lt = t - T_CTA
    f = np.empty((H, W, 3), np.float32)
    f[:] = YELLOW
    # Subtle diagonal stripe texture.
    yy, xx = np.ogrid[0:H, 0:W]
    f -= (((xx + yy + int(lt * 40 * (W / 1080))) // px(36)) % 2 == 0)[..., None] * 6.0
    br = a["c_brand"]
    over(f, br, W // 2 - br.width // 2, px(250), ease_out_cubic(prog(lt, 0.0, 0.4)))
    c1, c2, c3 = a["c1"], a["c2"], a["c3"]
    y = px(600)
    reveal(f, c1, W // 2 - c1.width // 2, y, prog(lt, 0.05, 0.5))
    reveal(f, c2, W // 2 - c2.width // 2, y + px(120), prog(lt, 0.2, 0.5))
    p3 = ease_out_cubic(prog(lt, 0.5, 0.4))
    over(f, c3, W // 2 - c3.width // 2, y + px(275) + int(px(12) * (1 - p3)), p3)

    # Primary CTA: black pill "DM @d3d.tn", breathing pulse.
    dm = a["c_dm"]
    pw, phh = dm.width + px(120), dm.height + px(60)
    pill = Image.new("RGBA", (pw, phh), (0, 0, 0, 0))
    ImageDraw.Draw(pill).rounded_rectangle([0, 0, pw - 1, phh - 1], radius=phh // 2, fill=INK + (255,))
    pill.alpha_composite(dm, (px(60), px(30) - px(5)))
    pp = prog(lt, 0.7, 0.45)
    pulse = 1 + 0.035 * math.sin(max(0, lt - 1.2) * 2 * math.pi / (2 * BEAT)) * (lt > 1.2)
    if pp > 0:
        sc = max(0.01, ease_out_back(pp, 2.0)) * pulse
        im = pill.resize((max(1, int(pw * sc)), max(1, int(phh * sc))), Image.LANCZOS)
        over(f, im, W // 2 - im.width // 2, y + px(400) + (phh - im.height) // 2, min(1, pp * 3))
    # Secondary: phone.
    tp = ease_out_cubic(prog(lt, 1.0, 0.4))
    tl, tel = a["c_tlab"], a["c_tel"]
    ty = y + px(400) + phh + px(60)
    over(f, tl, W // 2 - tl.width // 2, ty + int(px(12) * (1 - tp)), tp)
    over(f, tel, W // 2 - tel.width // 2, ty + px(50) + int(px(12) * (1 - tp)), tp)
    mn = a["c_min"]
    mp = ease_out_cubic(prog(lt, 1.3, 0.4))
    over(f, mn, W // 2 - mn.width // 2, ty + px(170), mp)
    return f


def render_frame(i):
    t = i / FPS
    if t < T_PRINT:
        f = scene_hook(t)
    elif t < T_PROOF:
        f = scene_print(t)
    elif t < T_OFFER:
        f = scene_proof(t)
    elif t < T_CTA:
        f = scene_offer(t)
    else:
        f = scene_cta(t)
    return np.clip(f, 0, 255).astype(np.uint8).tobytes()


def make_score(wav):
    premium_audio.render(wav, DUR, T_PRINT, T_PROOF, T_OFFER, T_CTA, len(MONTAGE), len(CHECKS))


def main():
    wav = os.path.join(HERE, "_ad_score.wav")
    mp4 = os.path.join(HERE, "d3d_ad_preview.mp4" if PREVIEW else "d3d_ad.mp4")
    print("synthesizing score...")
    make_score(wav)
    if "--remux" in sys.argv:  # keep the rendered picture, replace only the soundtrack
        tmp = mp4 + ".tmp.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp4, "-i", wav,
                        "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", premium_audio.MASTER,
                        "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
                        "-movflags", "+faststart", "-shortest", tmp], check=True)
        os.replace(tmp, mp4)
        os.remove(wav)
        print("remuxed", mp4)
        return
    vf = "eq=contrast=1.05:saturation=1.12,noise=alls=2:allf=t,format=yuv420p"
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", wav, "-vf", vf, "-af", premium_audio.MASTER,
           "-c:v", "libx264", "-preset", "slow", "-crf", "19", "-profile:v", "high",
           "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
           "-movflags", "+faststart", "-shortest", mp4]
    enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    print(f"rendering {NFRAMES} frames at {W}x{H}...")
    with Pool(os.cpu_count()) as pool:
        for k, buf in enumerate(pool.imap(render_frame, range(NFRAMES), chunksize=4)):
            enc.stdin.write(buf)
    enc.stdin.close()
    if enc.wait() != 0:
        sys.exit("ffmpeg failed")
    os.remove(wav)
    print("wrote", mp4)


if __name__ == "__main__":
    main()
