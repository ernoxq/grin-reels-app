---
name: grin-reel-studio
description: Монтаж: Студия. Speaker cut out onto a light set with animated cards above the head, captions in the safe zone, layered CapCut project. Use for «шаблон студия», «вырежи меня на фон с карточками».
---

<!-- GRIN Reels skill — © 2026 Ernest Grin (GRIN studio). All rights reserved. Licensed to the buyer for personal use; redistribution or resale prohibited. See LICENSE.md in the GRIN Reels folder. -->

# GRIN Reels - Studio template

The engine (`engine.tar.gz`, same as grin-reel-auto-edit plus `autocut/studio.py`) cuts the talk, cuts the person out (Robust Video Matting), draws the cards from a `scenes.json` you write, and renders. Reply in Russian, short.

## 1. Setup and the talk (same as auto-edit)
```bash
[ -d grin ] || { mkdir -p grin && tar xzf <this skill's folder>/engine.tar.gz -C grin; }
pip install --break-system-packages -q numpy Pillow fonttools faster-whisper "av<16" opencv-python-headless resvg-py onnxruntime pycapcut
nohup bash grin/run.sh <talking video(s)> --all-talking --plan --out grin/jobs/s1 > grin/out.txt 2>&1 &
```
Fix recognition mistakes with `--fix "wrong words=right words"` (several words are fine now), re-plan, then `python -m autocut finish grin/jobs/s1` (inside `grin`) - the studio uses the job's cuts, captions and sound (voice + music).

Ask the person for (only what is missing): their photo for the name plate, their name/role, and - important - **the widest take of the same recording** (horizontal is best). Pass it as `--video`; the engine aligns it by sound automatically. If they only have a tight vertical crop, warn once: «по бокам будут ровные срезы - лучше снимать с запасом по бокам и до стола».

## 2. Write scenes.json (you decide the cards from the meaning of the speech)
`python -m autocut studio-help` prints all scene types. Rules:
- one card per idea, 2–7 s each, on the words where the idea is said; use phrases from the captions for `from`/`to`/`at`;
- a card for: the title (first 3 s), the name (with photo), any Bible verse (`typewriter` in sync), the word «Библия» (`bible` - it opens), lists (`checklist` with ticks on the words), contrasts (`rows` ✓/✗), a call to comment (`icon_card` comment, dots), the final question (`end` with «Сохранить»);
- leave 1–2 short gaps without cards so the speaker is big sometimes;
- `theme` only if the person or the reference asks for other colours (`bg`, `accent`, `caption`).

## 3. Show the plan, get a yes (strict)
`python -m autocut studio grin/jobs/s1 --scenes scenes.json --plan` prints every card with its time and texts. Send it as it is and ask: «Ставлю такие карточки - что поменять?». The texts are yours, not the person's words, so they must approve them. Apply changes, re-plan.

## 4. Render
`nohup python -m autocut studio grin/jobs/s1 --scenes scenes.json --video WIDE.MOV > out.txt 2>&1 &` (inside `grin`; the cut-out takes ~3 min per minute of video on 2 cores, then ~2 min render). Look at 4 frames once (`ffmpeg -ss T -i jobs/s1/studio/studio.mp4 -frames:v 1 -vf scale=270:-2`), check: cards never cover the face, captions readable, nothing below the safe zone. Send `studio.mp4`. Pass on the `tips` from the JSON line in one sentence if there are any.

Built in, no need to ask: captions yellow with dark outline at y=1430 (inside the Reels/TikTok/Shorts safe band 270–1495); cards start below the top UI; the speaker shrinks under a card and grows back; small glitch-in at the start.

## 5. CapCut project (when asked «хочу редактировать в CapCut»)
Add `--capcut "<name>" --capcut-root "<…/com.lveditor.draft>" --media-dir "<folder for the layers>"`. Every card becomes its own transparent clip, the speaker a transparent clip with scale/position keyframes, captions are editable CapCut text, sound on its own track. Card contents (typed quote, opening Bible, ticks) stay baked in their clip - say so.
- Folder mode (Mac connected): ask once for `~/Movies/CapCut`, run on the computer with `device_bash` and pass `--map "$HOME/mnt/CapCut=/Users/<name>/Movies/CapCut"` so paths in the draft point at the real disk. CapCut shows the project after it is restarted.
- The speaker layer is PNG-in-MOV (~1 GB per minute): check free disk space first and tell the person.

## Licence note
The matting model (Robust Video Matting, mobilenetv3) is GPL-3.0 and is downloaded on first use, not bundled. Fine for your own work; swap `MATTE_URL` in `studio.py` for a permissive model before selling a bundle.
