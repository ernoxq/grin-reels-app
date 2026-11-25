---
name: grin-reel-style-learn
description: Learn the editing style of any reel the person likes, from just that finished video ("сделай в таком стиле", "разбери этот ролик"), or very precisely from the reel plus its source clips, and save it as a reusable GRIN Reels style. Then the person's own videos are edited in that style.
---

<!-- GRIN Reels skill — © 2026 Ernest Grin (GRIN studio). All rights reserved. Licensed to the buyer for personal use; redistribution or resale prohibited. See LICENSE.md in the GRIN Reels folder. -->

# GRIN Reels - learn a style from a reference

Save the person's limits: the script measures pace, colour and music; you look at ONE small picture (8 key frames) once, and never at the reel itself. Reply in 2-3 lines.

**Folder «Монтаж Claude»:** if the person's computer folder is connected (see the auto-edit skill, section 0), take the reference from `Референсы/` (the one they name, else the newest) and run the same commands there with `device_bash` in `$HOME/grin`; the style is saved in `$HOME/grin/styles/` and used for the next reels in this chat.

**Colour is NOT copied by default** (another light easily turns skin green or grey). Add `--colour` only when the person asks for the colour/look of the reference; it is applied at 40 %. Then check one frame of the result: skin must look like skin.

**3-5 reels are better than one** when they are by the same creator: pass them all in one command; pace, colour and music become their common style, and the picture shows 8 frames across all of them. In the folder mode take every file in `Референсы/` (or the ones the person names). Don't mix different creators unless asked.

## Quick mode - just someone else's finished reel (use this by default)
The engine ships inside this skill under `engine/`.
1. Copy it to the workspace with `cp -r <this skill's folder>/engine ./grin && cd grin`, then run `pip install --break-system-packages numpy Pillow fonttools faster-whisper "av<16" opencv-python-headless resvg-py`.
2. Run `python -m autocut style-from-ref REF1.mp4 [REF2.mp4 ... up to 5] --name ref_<short_name>`. This measures the editing pace, the share of B&W shots and the music under the voice. It saves colour reference frames, so every new video gets its own LUT toward that colour. It writes `styles/ref_<name>.json`.
3. Open `library/looks/ref_<name>/sheet.png` **once** and set only what eyes can judge, in that style file:
   - `caption_style`: `mode` is `phrase` for short phrases or `words` for 1–3 big words with the spoken word lit up. Also set the font (the closest free one; folders are listed in the auto-edit skill), size, `y`, colour, `uppercase`, `box` (plate) and `pop`.
   - `title`: keep it and set the font, colours and size, or remove it if the reel has no title.
   - `sticker`: keep or remove the end button.
4. Tell the person in two plain lines what you took from the reel, for example: «Темп — смена кадра каждые 0,8 с, цвет тёплый, субтитры крупными словами на плашке».
5. If their own video is attached, build the reel with `python -m autocut reel A.MOV B*.MOV --model cloud --style styles/ref_<name>.json --out jobs/NAME` and send it. Otherwise offer: «Пришли своё видео — соберу в этом стиле».

The style lives only in this chat's workspace. To reuse it in another chat, the person sends the same reference again; that takes a minute.

## Precise mode - the reel plus the source clips it was cut from
Only when the person has the original clips and wants an exact copy of a hand edit. Read `reference.md` then (it is long; skip it otherwise).
