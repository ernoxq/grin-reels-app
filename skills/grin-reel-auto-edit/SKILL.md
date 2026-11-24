---
name: grin-reel-auto-edit
description: Make a finished vertical reel (Instagram/TikTok/Shorts) from whatever videos and photos the person drops into the chat — joins all talking parts, cuts pauses and bad takes, adds subtitles in the spoken language, title, colour, inserts and an end button — with the GRIN Reels engine bundled in this skill. Use for «собери рилс», «смонтируй видео», «сделай рилс из этого».
---

<!-- GRIN Reels skill — © 2026 Ernest Grin (GRIN studio). All rights reserved. Licensed to the buyer for personal use; redistribution or resale prohibited. -->

# GRIN Reels: auto-edit

The engine makes every editing decision. Your job is to run ONE command and send the file. The person pays for every word you read and write, so save their limits.

## Save limits (strict)
- Do not read `reference.md`, `spec.json`, logs or frames unless something failed or the person asked for a change that needs them.
- Do not look at the video or make contact sheets. Do not explain the steps.
- Before working, write one line: «Собираю рилс, это займёт несколько минут». After, at most 3 short lines.
- Never re-run the whole build for a small change: edit the spec and `render` (see reference.md, F).

## 1. Setup (once per chat)
```bash
[ -d grin ] || cp -r <this skill's folder>/engine ./grin
```

## 2. Build: one command for all files
```bash
nohup bash grin/run.sh <ALL attached videos and photos, absolute paths> [options] > grin/out.txt 2>&1 &
```
Then wait cheaply: `sleep 240; tail -1 grin/out.txt` and repeat until the JSON line appears. About 3 minutes per minute of raw video; a 3–4 minute reel can take 15–20 minutes.

What the engine does by itself:
- **Joins** every clip where the person talks to the camera into one story, in file-name order, and removes repeated takes, pauses and mistakes.
- **Everything else** (other videos, photos) becomes inserts, spread evenly over the video; never on the first sentence (title) or the last one (end button).
- **Detects the language** (Romanian, Russian, English...) and writes the subtitles in it.

Options (add only if the person said so):
- `--all-talking` - «соедини все», «это всё моя речь», or all clips are the person talking.
- `--talking IMG_1 IMG_4` - only these clips are the talk; the rest are inserts.
- `--lang ro` / `ru` / `en` - only if the person names the language or subtitles came out in the wrong one.
- `--script script.txt` - the person sent the text: one sentence per line, exact spelling.
- `--title "..."`, `--no-inserts`, `--out jobs/NAME` (each run gets its own folder by default).

The JSON line: `video`, `sec`, `parts` (clips used as the talk), `inserts`, `unused`, `lang`.
If `parts` looks wrong (an insert was taken as talk, or a talk clip is missing), rerun once with `--talking` and name the right clips.

## 3. Deliver
Send the `video` path from the JSON with SendUserFile. Then 2–3 lines: length, which clips became the talk, language. One offer: «Могу поменять шрифт, цвет, заголовок или поставить фото на нужные слова».

## 4. If it fails
Read only the last 15 lines of `grin/grin.log`. Explain in plain words with the fix, never a traceback:
- no code execution → «Включи Settings → Capabilities → Code execution, и напиши ещё раз»;
- the model download failed → ask for the text and add `--script` (see reference.md for LITE);
- the file is too big → «Сними в 1080p вместо 4K или пришли видео покороче».

## 5. Changes after the first version
Fonts, colour presets, LUTs, music, own files, icons, a photo or sticker on certain words, a style from someone's reel: open `reference.md` and read ONLY the matching section (A–H). Speak Russian unless the person writes in another language.
