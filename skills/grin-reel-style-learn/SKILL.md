---
name: grin-reel-style-learn
description: Learn the editing style of any reel the person likes, from just that finished video ("сделай в таком стиле", "разбери этот ролик"), or very precisely from the reel plus its source clips, and save it as a reusable GRIN Reels style. Then the person's own videos are edited in that style.
---

<!-- GRIN Reels skill — © 2026 Ernest Grin (GRIN studio). All rights reserved. Licensed to the buyer for personal use; redistribution or resale prohibited. See LICENSE.md in the GRIN Reels folder. -->

# GRIN Reels — learn a style from a reference

## Quick mode — just someone else's finished reel (use this by default)
The engine ships inside this skill under `engine/`.
1. Copy it to the workspace with `cp -r <this skill's folder>/engine ./grin && cd grin`, then run `pip install --break-system-packages numpy Pillow fonttools faster-whisper "av<16" opencv-python-headless resvg-py`.
2. Run `python -m autocut style-from-ref REF.mp4 --name ref_<short_name>`. This measures the editing pace, the share of B&W shots and the music under the voice. It saves colour reference frames, so every new video gets its own LUT toward that colour. It writes `styles/ref_<name>.json`.
3. Open `library/looks/ref_<name>/sheet.png` **once** and set only what eyes can judge, in that style file:
   - `caption_style`: `mode` is `phrase` for short phrases or `words` for 1–3 big words with the spoken word lit up. Also set the font (the closest free one; folders are listed in the auto-edit skill), size, `y`, colour, `uppercase`, `box` (plate) and `pop`.
   - `title`: keep it and set the font, colours and size, or remove it if the reel has no title.
   - `sticker`: keep or remove the end button.
4. Tell the person in two plain lines what you took from the reel, for example: «Темп — смена кадра каждые 0,8 с, цвет тёплый, субтитры крупными словами на плашке».
5. If their own video is attached, build the reel with `python -m autocut reel A.MOV B*.MOV --model cloud --style styles/ref_<name>.json --out jobs/NAME` and send it. Otherwise offer: «Пришли своё видео — соберу в этом стиле».

The style lives only in this chat's workspace. To reuse it in another chat, the person sends the same reference again; that takes a minute.

## Precise mode — the reel plus the source clips it was cut from
Use this only when the person has the original clips and wants an exact copy of a hand edit.

The result is `styles/<name>.json`, plus fitted `.cube` LUTs and any overlays or stickers in `library/`. Verify it by rebuilding the reference and running `python -m autocut.compare ref.mov out.mp4`; the target is a mean difference under 8/255. Measure every value; never eyeball. Work on the user's Mac in the GRIN Reels folder, using small decodes so RAM stays low.

## Steps
1. **Probe** every file with `ffprobe` (size, fps, rotation, audio). A `te_is_reencode` tag means the reference was exported from CapCut.
2. **Contact sheet:** take the reference at fps=3, 216 px wide, tiled 9x6, and look at it **once** to get the structure, the text and the stickers.
3. **A-roll segments:** decode mono 8 kHz audio. For each 0.5 s window of the reference, run a normalised FFT cross-correlation against the A-roll; a score above 0.9 is voice. Refine each offset within ±30 ms, then place cuts with a 0.25 s RMS-envelope correlation. Cuts usually hide under B-roll.
4. **B-roll mapping:** decode at 54x96 gray and 30 fps. Find each reference frame's best match by max normalised correlation, then fit a line per run to get `in` and `speed`; fit speed at the clip's native fps.
5. **Framing:** run SIFT and `estimateAffinePartial2D` on a reference/source frame pair with the caption band masked. Then `x = (tx + (s-1)W/2)/(W/2)` and `y = -(ty + (s-1)H/2)/(H/2)`.
6. **Grade:**
   - Render a version without LUTs and compare it to the reference frame-exact at 270x480.
   - A vertical darkening gradient means a shadow layer; model it as a black PNG gradient in `library/overlays/`.
   - Fit per-channel median curves on the **top half only**, separately for A-roll, colour B-roll and B&W luma, and write them as 33³ `.cube` files.
   - Store `input_luma`, measured with `media.median_luma` on the same source span.
7. **Text:**
   - Threshold white and accent pixels in the caption band to get on/off times, bounding boxes and line pitch.
   - Calibrate libass font sizes by rendering and measuring; libass comes out about 1.6–1.7× the PIL size.
   - Condensed titles may need `scale_y`.
   - Create static instances of variable fonts (`fontTools.varLib.instancer`), because libass renders a variable font as Thin.
   - Use only fonts with a commercial licence (OFL or bought).
8. **Audio bed:** subtract the aligned voice (search ±200 samples, least-squares gain) and look at the residual spectrogram. Get BPM from low-band onset autocorrelation and check whether the B-roll cuts fall every 2 beats.
9. **Sticker and end:** track the sticker's bounding box per frame for pop timing and scale, and read the fade from mean brightness.
10. **Rebuild:** write an exact rebuild spec, render it, compare, and fix the worst seconds first.
11. **Generalise:** strip the timings and keep the looks and rules (caption rules, title template, B-roll window and beats, slow-mo, CTA, fade, music gain and BPM). Add a planner regression test from a fake transcript, with the good takes where the editor cut and failed takes earlier.

## Pitfalls
- Contact sheets made with `fps=3` can show the wrong frame, so trust frame-indexed comparisons.
- Audio resampling breaks sample-wise subtraction; use envelopes to detect cuts.
- Don't normalise B-roll exposure by default, because it flattens intentional mood.
- Never ship a client's footage, voice, face or texts inside a style without their written consent.
