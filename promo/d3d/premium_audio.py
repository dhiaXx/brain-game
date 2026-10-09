"""Premium soundtrack for the D3D ad: deep-house at 120 BPM, A minor.

Stems are synthesized in numpy (supersaw pad, additive pluck lead, sub bass,
layered drums, FM bells, risers/impacts), then mixed with sidechain pumping,
ping-pong delay and convolution reverb. ffmpeg adds the master bus
(glue compression, air, limiter, -14 LUFS).

Arrangement follows the ad's scenes:
  0-2   hook     impact + filtered chords + motif
  2-4   build    filter opens, snare roll, riser, drop gap
  4-8   drop     full groove + lead hook
  8-12  offer    impact, price bell, rising check bells, lighter groove
  12-16 CTA      final chorus, lead doubled, ring-out
"""
import math
import wave

import numpy as np

SR = 48000
BEAT = 0.5
BAR = 4 * BEAT
S16 = BEAT / 4

RNG = np.random.default_rng(2024)


def note(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def xs(length):
    return np.arange(int(length * SR)) / SR


def smooth(x, k):
    return np.convolve(x, np.ones(k) / k, mode="same")


def fftconv(x, ir):
    n = len(x) + len(ir) - 1
    size = 1 << (n - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[:len(x)]
    return y.astype(np.float32)


def stft_lowpass(x, cutoff, n=2048, hop=512, order=4):
    """Time-varying lowpass. cutoff: callable t -> Hz."""
    win = np.hanning(n).astype(np.float32)
    pad = np.concatenate([np.zeros(n), x, np.zeros(n)]).astype(np.float32)
    out = np.zeros_like(pad)
    norm = np.zeros_like(pad)
    freqs = np.fft.rfftfreq(n, 1 / SR)
    for start in range(0, len(pad) - n, hop):
        t = (start - n + n / 2) / SR
        fc = max(20.0, cutoff(t))
        mask = 1 / np.sqrt(1 + (freqs / fc) ** (2 * order))
        seg = np.fft.irfft(np.fft.rfft(pad[start:start + n] * win) * mask, n)
        out[start:start + n] += seg * win
        norm[start:start + n] += win ** 2
    return (out / np.maximum(norm, 1e-6))[n:n + len(x)]


class Bus:
    def __init__(self, dur):
        self.n = int(dur * SR)
        self.x = np.zeros((self.n, 2), np.float32)

    def add(self, sig, t0, gain=1.0, pan=0.0):
        s = int(round(t0 * SR))
        if s >= self.n:
            return
        if sig.ndim == 1:
            l, r = math.cos((pan + 1) * math.pi / 4), math.sin((pan + 1) * math.pi / 4)
            sig = np.stack([sig * l * 1.414, sig * r * 1.414], 1)
        if s < 0:
            sig, s = sig[-s:], 0
        e = min(self.n, s + len(sig))
        self.x[s:e] += sig[:e - s] * gain


# ------------------------------------------------------------------ voices
def kick():
    x = xs(0.5)
    f = 46 + 110 * np.exp(-x * 38)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 6.5)
    nz = RNG.standard_normal(len(x))
    click = (nz - smooth(nz, 3)) * np.exp(-x * 900) * 0.6
    return np.tanh(2.2 * (body + click)) / np.tanh(2.2)


def clap():
    x = xs(0.35)
    nz = RNG.standard_normal(len(x))
    bp = smooth(nz, 2) - smooth(nz, 10)
    env = sum(np.exp(-np.maximum(0, x - d) * 55) * (x >= d) for d in (0, 0.009, 0.019, 0.028))
    tail = np.exp(-np.maximum(0, x - 0.028) * 14) * (x >= 0.028) * 0.5
    return bp * (env + tail) * 2.2


def snare():
    x = xs(0.18)
    nz = RNG.standard_normal(len(x))
    return ((nz - smooth(nz, 4)) * 0.8 + np.sin(2 * np.pi * 190 * x) * 0.5) * np.exp(-x * 30)


def hat(open_=False):
    x = xs(0.35 if open_ else 0.06)
    ph = sum(np.sign(np.sin(2 * np.pi * f * 1.55 * x + RNG.random() * 6))
             for f in (205.3, 304.4, 369.6, 522.7, 540.0, 800.0))
    nz = RNG.standard_normal(len(x))
    s = ph * 0.5 + nz * 0.6
    s = s - smooth(s, 2)
    s = s - smooth(s, 3)
    return s * np.exp(-x * (11 if open_ else 75)) * 0.5


def supersaw(m, length, voices=7, detune=0.20):
    x = xs(length)
    f = note(m)
    out = np.zeros((len(x), 2), np.float32)
    for v in range(voices):
        c = (v - (voices - 1) / 2) / ((voices - 1) / 2)  # -1..1
        fv = f * 2 ** (c * detune / 12)
        saw = 2 * ((fv * x + RNG.random()) % 1.0) - 1
        pan = c * 0.9
        out[:, 0] += saw * math.cos((pan + 1) * math.pi / 4)
        out[:, 1] += saw * math.sin((pan + 1) * math.pi / 4)
    env = np.minimum(1, x / 0.08) * np.clip((length - x) / 0.25, 0, 1)
    return out * env[:, None] / voices


def pluck(m, length=0.45, bright=1.0, decay=0.22):
    """Additive saw pluck: upper harmonics die faster (filter-envelope feel)."""
    x = xs(length)
    f = note(m)
    s = np.zeros_like(x)
    h = 1
    while f * h < 9000 and h <= 24:
        s += np.sin(2 * np.pi * f * h * x) / h * np.exp(-x * (2.5 + h * 3.2 / bright))
        h += 1
    return s * np.minimum(1, x / 0.002) * np.exp(-x / decay)


def sub(m, length):
    x = xs(length)
    s = np.sin(2 * np.pi * note(m) * x)
    s = np.tanh(1.8 * s) * 0.8 + 0.2 * np.sin(4 * np.pi * note(m) * x)
    return s * np.minimum(1, x / 0.004) * np.clip((length - x) / 0.03, 0, 1)


def fm_bell(m, length=2.2, index=5.0, ratio=3.5):
    x = xs(length)
    fc = note(m)
    I = index * np.exp(-x * 3.5)
    s = np.sin(2 * np.pi * fc * x + I * np.sin(2 * np.pi * fc * ratio * x))
    s += 0.35 * np.sin(2 * np.pi * fc * 2.0 * x) * np.exp(-x * 4)
    return s * np.minimum(1, x / 0.001) * np.exp(-x * 1.8)


def impact():
    x = xs(2.0)
    boom = np.sin(2 * np.pi * np.cumsum(32 + 90 * np.exp(-x * 9)) / SR) * np.exp(-x * 1.8)
    nz = RNG.standard_normal(len(x))
    crack = smooth(nz, 3) * np.exp(-x * 18) * 0.7
    return np.tanh(1.5 * (boom + crack))


def sub_drop(length=1.4):
    x = xs(length)
    f = 30 + 60 * np.exp(-x * 2.5)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 1.5)


def riser(length):
    nz = RNG.standard_normal(int(length * SR)).astype(np.float32)
    x = np.linspace(0, 1, len(nz))
    swept = stft_lowpass(nz, lambda t: 300 + 11000 * (t / length) ** 2)
    tone = np.sin(2 * np.pi * np.cumsum(220 * 2 ** (3 * x)) / SR) * 0.15
    return (swept + tone) * x ** 2.2


def reverse_cymbal(length=1.0):
    x = xs(length)
    nz = RNG.standard_normal(len(x))
    s = (nz - smooth(nz, 2)) * np.exp(-(length - x) * 5)
    return s * np.clip(x / 0.05, 0, 1)


def whoosh(length=0.25):
    nz = smooth(RNG.standard_normal(int(length * SR)), 10)
    x = np.linspace(0, 1, len(nz))
    return nz * np.sin(np.pi * x) ** 2


def make_ir(length=2.4, decay=0.55, seed=0):
    r = np.random.default_rng(seed)
    x = xs(length)
    pre = int(0.018 * SR)
    ir = np.zeros(len(x) + pre, np.float32)
    tail = r.standard_normal(len(x)) * np.exp(-x / decay)
    # Darken the tail over time (air absorption): blend toward a smoothed copy.
    tail = tail * np.exp(-x * 1.5) + smooth(tail, 6) * (1 - np.exp(-x * 1.5))
    ir[pre:] = tail
    for d, g in ((0.011, 0.5), (0.023, 0.35), (0.037, 0.28), (0.052, 0.2)):
        ir[pre + int(d * SR)] += g * (1 if r.random() > 0.5 else -1)
    return ir / np.sqrt(np.sum(ir ** 2))


# ------------------------------------------------------------------ song
CHORDS = [[57, 60, 64, 67, 71],   # Am9
          [53, 57, 60, 64, 67],   # Fmaj9
          [48, 55, 60, 64, 74],   # Cadd9
          [55, 59, 62, 64, 69]]   # G6/9
ROOTS = [33, 29, 36, 31]
# Lead hook: (16th step within the 2-bar phrase, midi, length in 16ths)
HOOK = [(0, 76, 2), (2, 81, 2), (4, 79, 1), (5, 76, 2), (7, 74, 1), (8, 72, 2), (10, 74, 1),
        (11, 76, 3), (14, 72, 1), (15, 69, 1),
        (16, 76, 2), (18, 81, 2), (20, 83, 1), (21, 81, 2), (23, 79, 1), (24, 76, 2), (26, 74, 1),
        (27, 79, 3), (30, 76, 2)]


def render(path, dur, t_print, t_proof, t_offer, t_cta, n_cuts, n_checks):
    drums, bass, pad, lead, fx = (Bus(dur) for _ in range(5))
    rev_send = Bus(dur)

    bars = int(math.ceil(dur / BAR))
    kicks = []

    # --- pad: supersaw chords every bar, filter opens through the build.
    for b in range(bars):
        t0 = b * BAR
        ch = CHORDS[b % 4]
        for m in ch:
            pad.add(supersaw(m, BAR + 0.3), t0, 0.07)

    def pad_cut(t):
        if t < t_print:
            return 1300 + 600 * (t / t_print)
        if t < t_proof:
            return 1900 + 6500 * ((t - t_print) / (t_proof - t_print)) ** 2
        if t_offer <= t < t_cta:
            return 2600
        return 7000
    pad.x[:, 0] = stft_lowpass(pad.x[:, 0], pad_cut)
    pad.x[:, 1] = stft_lowpass(pad.x[:, 1], pad_cut)

    # --- drums.
    t = 0.0
    k = 0
    while t < dur - 1.0:
        sec_hook = t < t_print
        sec_build = t_print <= t < t_proof
        gap = t_proof - 0.25 <= t < t_proof  # breath before the drop
        if not gap:
            if (sec_hook and k % 2 == 0) or (not sec_hook and not sec_build) or (sec_build and t < t_proof - 0.5):
                drums.add(kick(), t, 0.72)
                kicks.append(t)
        if not (sec_hook or sec_build) and k % 2 == 1:
            drums.add(clap(), t, 0.42, 0.05)
            rev_send.add(clap(), t, 0.25)
        if not (sec_hook or sec_build):
            drums.add(hat(True), t + BEAT / 2, 0.20, 0.25)
            for q in (1, 3):
                vel = 0.13 if q == 1 else 0.10
                drums.add(hat(), t + q * S16 + 0.006 * (q == 3), vel, -0.3)
        t += BEAT
        k += 1

    # Snare roll in the build (8ths -> 16ths, rising) and before the offer/CTA.
    def roll(t_start, t_end, g0, g1):
        tt = t_start
        while tt < t_end - 1e-6:
            p = (tt - t_start) / (t_end - t_start)
            step = S16 * 2 if p < 0.5 else S16
            drums.add(snare(), tt, g0 + (g1 - g0) * p, 0.1)
            rev_send.add(snare(), tt, 0.12 * p)
            tt += step
    roll(t_print + 0.5, t_proof - 0.25, 0.06, 0.38)
    roll(t_offer - BEAT, t_offer, 0.12, 0.30)
    roll(t_cta - BEAT, t_cta, 0.12, 0.30)

    # --- bass: offbeat 8ths in the groove sections; held root in the hook.
    for b in range(bars):
        t0 = b * BAR
        rt = ROOTS[b % 4]
        if t0 < t_print:
            bass.add(sub(rt + 12, BAR - 0.05), t0, 0.12)
        elif t0 >= t_proof and t0 < dur - 1.0:
            for s in range(8):
                if (s % 2 == 1 or s == 0) and t0 + s * BEAT / 2 < dur - 1.0:
                    bass.add(sub(rt + 12, BEAT / 2 - 0.03), t0 + s * BEAT / 2, 0.27)

    # --- lead hook (2-bar phrase).
    def phrase(t0, gain, octave=0, bright=1.0, double=False):
        for st, m, ln in HOOK:
            sig = pluck(m + octave, ln * S16 + 0.35, bright)
            pan = 0.15 if st % 2 else -0.15
            lead.add(sig, t0 + st * S16, gain, pan)
            if double:
                lead.add(pluck(m + octave + 12, ln * S16 + 0.3, bright * 0.8), t0 + st * S16, gain * 0.35, -pan)
    phrase(0.0, 0.16, -12, 0.6)           # hook: dark, low
    phrase(t_proof, 0.27)                 # drop
    phrase(t_proof + 2 * BAR, 0.27) if t_proof + 2 * BAR < t_offer else None
    phrase(t_cta, 0.30, 0, 1.2, double=True)
    # Offer: soft arpeggio leaves room for the bells.
    for b in range(int(t_offer / BAR), int(t_cta / BAR)):
        ch = CHORDS[b % 4]
        for s in range(8):
            m = ch[[0, 2, 4, 3, 1, 3, 2, 4][s]] + 12
            lead.add(pluck(m, 0.3, 0.6, 0.12), b * BAR + s * BEAT / 2, 0.07, 0.4 if s % 2 else -0.4)

    # --- FX.
    fx.add(impact(), 0.0, 0.45)
    fx.add(sub_drop(), 0.0, 0.28)
    rev_send.add(impact(), 0.0, 0.25)
    fx.add(riser(t_proof - t_print - 0.25), t_print, 0.22)
    fx.add(reverse_cymbal(1.0), t_proof - 1.0, 0.12)
    bell = fm_bell(88, 1.8, 3.0, 3.5)
    fx.add(bell, t_print + 1.6, 0.10, 0.2)            # print complete
    rev_send.add(bell, t_print + 1.6, 0.10)
    fx.add(impact(), t_proof, 0.30)
    for i in range(1, n_cuts):
        fx.add(whoosh(0.2), t_proof + i * BEAT - 0.1, 0.05, 0.5 if i % 2 else -0.5)
    fx.add(riser(1.5), t_offer - 1.5, 0.18)
    fx.add(impact(), t_offer, 0.38)
    fx.add(sub_drop(), t_offer, 0.22)
    for m, d in ((81, 0.0), (88, 0.012), (93, 0.024)):  # price: shimmering A-E-A bell chord
        b_ = fm_bell(m, 2.4, 4.0, 3.5)
        fx.add(b_, t_offer + 0.75 + d, 0.09, (m - 88) / 10)
        rev_send.add(b_, t_offer + 0.75 + d, 0.12)
    for n_, m in enumerate([81, 84, 88, 93][:n_checks]):  # checklist ticks
        b_ = fm_bell(m, 1.2, 2.5, 2.0)
        fx.add(b_, t_offer + 1.25 + n_ * BEAT, 0.07, -0.3 + 0.2 * n_)
        rev_send.add(b_, t_offer + 1.25 + n_ * BEAT, 0.08)
    fx.add(reverse_cymbal(1.0), t_cta - 1.0, 0.12)
    fx.add(impact(), t_cta, 0.42)
    rev_send.add(impact(), t_cta, 0.2)
    # Final ring-out chord.
    for m in CHORDS[0]:
        b_ = fm_bell(m + 12, 3.0, 2.0, 2.0)
        fx.add(b_, dur - 1.6, 0.05)
        rev_send.add(b_, dur - 1.6, 0.08)

    # --- sidechain pumping (keyed from the kick).
    tt = np.arange(drums.n) / SR
    duck = np.zeros(drums.n, np.float32)
    for tk in kicks:
        s = int(tk * SR)
        e = min(drums.n, s + int(0.45 * SR))
        dt = tt[s:e] - tk
        curve = np.exp(-dt / 0.11) * np.minimum(1, dt / 0.004)
        duck[s:e] = np.maximum(duck[s:e], curve)
    pad.x *= (1 - 0.65 * duck)[:, None]
    bass.x *= (1 - 0.80 * duck)[:, None]
    lead.x *= (1 - 0.30 * duck)[:, None]

    # --- ping-pong delay on the lead (dotted 8th).
    d = int(0.375 * SR)
    dl = np.zeros_like(lead.x)
    for n_ in range(1, 5):
        sh = lead.x[:-d * n_ or None].mean(1) * (0.38 ** n_)
        ch = n_ % 2
        dl[d * n_:, ch] += sh[:len(dl) - d * n_]
    dl[:, 0] = smooth(dl[:, 0], 5)
    dl[:, 1] = smooth(dl[:, 1], 5)

    # --- reverb.
    send = rev_send.x + pad.x * 0.35 + lead.x * 0.45 + dl * 0.3 + fx.x * 0.15
    irl, irr = make_ir(seed=1), make_ir(seed=2)
    wet = np.stack([fftconv(send[:, 0], irl), fftconv(send[:, 1], irr)], 1)
    wet[:, 0] -= smooth(wet[:, 0], 40)  # keep the low end dry
    wet[:, 1] -= smooth(wet[:, 1], 40)

    mix = (drums.x * 1.0 + bass.x * 1.0 + pad.x * 0.9 + lead.x * 1.0 + dl * 0.45
           + fx.x * 1.0 + wet * 0.55)
    # Mid/side widening above the bass.
    mid, side = (mix[:, 0] + mix[:, 1]) / 2, (mix[:, 0] - mix[:, 1]) / 2
    side = (side - smooth(side, 60)) * 1.7 + smooth(side, 60) * 0.2
    mix = np.stack([mid + side, mid - side], 1)

    env = np.clip((dur - tt) / 0.9, 0, 1)
    mix *= env[:, None]
    mix /= max(1e-6, np.abs(mix).max()) / 0.9
    pcm = (np.clip(mix, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


MASTER = ("highpass=f=30,equalizer=f=280:t=q:w=1.2:g=-2.5,equalizer=f=3200:t=q:w=1:g=1.5,"
          "acompressor=threshold=-16dB:ratio=2.5:attack=15:release=150:makeup=2,"
          "treble=g=2:f=10000,"
          "alimiter=limit=0.84:attack=3:release=60,"
          "loudnorm=I=-14:TP=-1.0:LRA=7")
