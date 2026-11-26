---
name: grin-reel-auto-edit
description: Монтаж. Finished vertical reel from the person's videos and photos: cuts pauses and bad takes, subtitles, title, colour, inserts, motion text + a CapCut project. Use for «собери рилс», «смонтируй».
---

<!-- GRIN Reels skill — © 2026 Ernest Grin (GRIN studio). All rights reserved. Licensed to the buyer for personal use; redistribution or resale prohibited. -->

# Монтаж

The engine makes every editing decision. You run ONE command and send the file. The person pays for every word you read and write.

## Save limits (strict)
- Open `reference.md` only for the section a request needs (A–J). Never read spec.json, logs or frames unless something failed.
- Don't look at the video, don't explain steps. Before: «Собираю рилс, это займёт несколько минут». After: max 3 short lines.
- Small change = edit the spec and `render` (reference.md F), never a full rebuild.
- Cuts the person names in seconds («вырежи 12.4–13.1») are approximate: change `voice` in the spec as asked; the engine moves each cut to the nearest pause, so word starts and ends are never eaten, and adds click-free fades. Never shave pads yourself. If they say a word is still clipped, widen that segment by 0.1 s.
- Editing is done by asking you in this chat. The only editor project is **CapCut**, and only when the person's Mac folder is connected (reference.md I). Never make DaVinci/Final Cut/SRT files.

## 1. Setup
Computer folder «Монтаж Claude» connected (the session has `mcp__remote-devices__*` tools and a folder with `Исходники`)? → follow reference.md I instead of this section.
Otherwise (files attached to the chat):
```bash
[ -d grin ] || cp -r <this skill's folder>/engine ./grin
```

## 2. Storyboard first, then build
```bash
nohup bash grin/run.sh <ALL attached videos and photos, absolute paths> --plan --out grin/jobs/r1 [options] > grin/out.txt 2>&1 &
```
Wait cheaply: `sleep 120; tail -25 grin/out.txt` until the plan appears (~1.5 min per minute of raw video).
Fix obvious recognition mistakes yourself with `--fix "wrong=right"` (one or several words; you know the language) and drop clear stumbles/repeats with `--drop`, re-plan once. Show the plan as it is and ask: «Собираю так или что-то поменять?». Apply, re-plan (fast, no new recognition):
- `--drop "фраза"` (undo `--keep`), `--title "..."`; same `--out` remembers earlier choices; a new reel gets a new `--out`.
- photo / video / icon on certain words: `place` (reference.md E); animated text: reference.md J.
Render: `cd grin && nohup python -m autocut finish jobs/r1 > out.txt 2>&1 &`, poll, read the JSON line.
«сразу» / «без плана» → skip `--plan`.

Options only if the person said so: `--all-talking` («соедини все»), `--talking IMG_1 IMG_4`, `--lang ro|ru|en` (wrong subtitle language), `--script script.txt`, `--no-inserts`. No end button unless asked (reference.md D).
The engine joins talking clips in file-name order, removes repeats, pauses and mistakes, spreads the other files as inserts, detects the language.

## 3. Colour: natural by default (strict)
No LUT or «cinematic look» unless asked. Asked for a look: one preset at 40-70 % (reference.md D). Small wishes: sliders ±0.3 («чуть теплее» `temp 0.2`, «светлее» `exposure 0.2`, «сочнее» `saturation 0.2`). Never stack preset + sliders + reference colour. After a colour change look at ONE frame (`ffmpeg -ss 3 -i final.mp4 -frames:v 1 -vf scale=360:-2 f.png`): skin must look like skin, else halve the strength.

## 4. Any other wish
Content (what stays, order, words, title) → plan flags. Something on screen at certain words → `place`. Fonts, colours, music, captions → reference.md D. Their vibe from 1-5 reels → `gubka-learn`. Studio format → `grin-reel-studio`. Link to a reference → reference.md J. Anything else → one small ffmpeg step on `final.mp4`.
Safe zone: captions and graphics stay in y 270–1495 of 1920; warn before moving them lower.

## 5. Deliver
Send `video` from the JSON with SendUserFile (folder mode: just say where). 2–3 lines: length, which clips became the talk, language. One offer: «Поменять шрифт, цвет, заголовок или поставить фото на нужные слова?» or «Проверить на кринж перед публикацией?» (antikrinzh).

## 6. If it fails
Read only the last 15 lines of `grin/grin.log`, explain in plain words with the fix, never a traceback:
- no code execution → «Включи Settings → Capabilities → Code execution and file creation и напиши ещё раз»;
- model download failed → ask for the text and use `--script`;
- file too big → «Сними в 1080p вместо 4K или пришли видео покороче».
Reply in Russian unless the person writes in another language.
