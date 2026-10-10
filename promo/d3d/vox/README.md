# D3D FAQ: Vox-style B2B edit

**Current ad version:** `d3d_faq_ad.mp4` (36 s), built from `src/raw_v2.mp4` (cleaner voice). Its cover is `d3d_faq_cover.jpg` (`python3 promo/d3d/vox/make_cover.py`) and its captions are in `caption.md`.

Changes in the ad version:
- **Voice first:** clarity EQ and light compression on the voiceover, with sound effects ducked under the voice so they stay at least 12 dB below it while it speaks.
- **No doubled sound:** the source mix already accents the cuts, so there are no extra whooshes or booms, and effects never stack.
- **One red circle,** drawn as a single stroke.
- **Sound effects (v3):** stereo whooshes only on the 7 cuts that have no accent in the source mix; typewriter on chapter tags; swipes as cards slide in; highlighter squeaks; pops on chips; counter ticks and a ding; message "send" + read-receipt notification; stamps; a rising tone on the 50 % pie; a check "pling"; clicks on the poll. They duck about 6–8 dB under the voice, and the louder ones peak around 11 dB below it.
- **Interactive end card:** an « Envoyez DEVIS en DM » button plus a « Combien de pièces ? 50 · 100 · 500+ » comment poll.


`d3d_faq_vox.mp4` is a 35-second vertical video (1080×1920, 30 fps) with audio at −14 LUFS.
It's re-edited from `src/raw.mp4`, the raw 480×854 footage with the voiceover. The voiceover timing is unchanged; all the design is layered on top.

```bash
python3 promo/d3d/vox/make_vox_edit.py                    # full render (~6 min)
python3 promo/d3d/vox/make_vox_edit.py --stills 3.6,14.2  # PNG checks of single frames
```

| Time | Chapter | Graphics |
|---|---|---|
| 0–2 s | Intro | Paper card "30 secondes pour répondre à vos questions", typewriter label, highlighter, "Pour entreprises · marques · événements" tag |
| 2–8 s | 01 À quoi ça sert ? | Checkmark chips (Société, Marque, Événement), "Motivez votre équipe", "Fidélisez vos clients", red hand-drawn circle |
| 8–11 s | 02 Quantité minimum ? | Counter 10 → 1000+ pièces on a log-scale bar |
| 11–21.5 s | 03 Comment commander ? | "Simple comme 1, 2, 3"; ① WhatsApp card with the logo message being sent; ② 3D mockup + "VALIDÉ" stamp; ③ quote document |
| 21.5–28.4 s | 04 Paiement & livraison | Two columns: < 100 pièces (payment on delivery) and 100+ pièces (50 % deposit pie chart); "VÉRIFIEZ AVANT DE PAYER" stamp + circle |
| 28.4–32 s | 05 Matière & emballage | PLA+ card, "Emballage individuel ?" → "BIEN SÛR ✓" stamp |
| 32–35 s | Outro | D3D CTA card, +216 25 430 387, @d3d.tn, "Maquette 3D gratuite" stamp |

**Throughout:**
- a five-part chapter progress bar
- a fast whip transition on every one of the 15 source cuts, with motion blur and an exposure bump
- a filmic grade (S-curve, teal shadows, warm highlights), vignette and grain
- sound effects synthesized for each animation (paper, marker, typewriter, stamps, pops, whips, counter ticks, dings), mixed under the voice; the voice is EQ'd and compressed
