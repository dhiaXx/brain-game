# Tic-Tac-Toe promo video

`tictactoe_promo.mp4`: a 16-second, 1920×1080, 30 fps H.264/AAC promo trailer, mastered to −14 LUFS.
Everything in it, including picture, motion and sound, comes from `make_promo.py`. It uses no stock footage or music.

```bash
python3 promo/make_promo.py            # final 1080p render (~3 min on 4 cores)
python3 promo/make_promo.py --preview  # 540p draft for fast iteration
```

Requirements: Python 3 with `numpy` and `Pillow`, plus `ffmpeg`.

## What's in it

| Time | Shot | Premiere / After Effects equivalent |
|---|---|---|
| 0–2 s | Neon grid lines draw on, staggered, with a slow push-in | Trim Paths, ease curves, scale keyframes |
| 2–5.5 s | A full game is played on the beat. The X and O strokes draw on, and each placement sends out a ring burst | Stroke animation, shape layers, beat markers |
| 5.5 s | The winning line strikes through, with a white flash, camera shake and a zoom punch | Flash frame, Wiggle on a camera null |
| 7–7.5 s | Whip zoom with blur into the next scene | Transform + Directional/Gaussian Blur transition |
| 7.5–11.5 s | Kinetic type: three game modes slide in with motion blur, offset parallax and an accent-bar wipe | Text animators, CC Force Motion Blur |
| 11.5–16 s | The title letters pop in with overshoot, then the tagline and a `python main.py` call-to-action appear | Ease-out-back expressions, end card |
| All | Bloom/glow, colour grade, vignette and film grain | Glow, Lumetri, vignette, Add Grain |
| Audio | Synthesised pad, kick, hats, bass, plinks synced to moves, risers, whooshes and impacts. Echo and loudness normalisation are applied | Essential Sound, loudness meter |

## Plugins and skills for pro-level editing with Claude Code

These come from the Anthropic plugin directory:

- **Remotion**: React-based programmatic video, the closest thing to After Effects in code. It covers captions, 3D, audio and rendering.
- **Motion Reel**: showreel-style motion videos with a beat grid, shot list, synthesised score, contact-sheet critique and 16:9 / 9:16 / 1:1 delivery.
- **IT Reelsmaker**: edits talking-head footage into Reels/Shorts/TikTok. It cuts pauses and retakes, adds word-timed subtitles, applies loudness mastering and renders at 1080×1920.
- **ffmpeg-llm**: turns plain-language requests into ffmpeg commands for cutting, transcoding, grading and audio work.
- **DemoDay** (macOS only): turns a codebase into a demo video with voiceover.

The base tools are **ffmpeg** (cutting, grading, encoding, audio), **Python with numpy/Pillow** (frame-level motion graphics like this video) and **Node + Remotion** (React compositions).
