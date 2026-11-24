---
name: grin-reel-auto-edit
description: Make a finished vertical reel (Instagram/TikTok/Shorts) from whatever videos and photos the person drops into the chat — cuts pauses and bad takes, adds subtitles, title, colour, inserts and an end button — with the GRIN Reels engine bundled in this skill. Use for «собери рилс», «смонтируй видео», «сделай рилс из этого».
---

<!-- GRIN Reels skill — © 2026 Ernest Grin (GRIN studio). All rights reserved. Licensed to the buyer for personal use; redistribution or resale prohibited. See LICENSE.md in the GRIN Reels folder. -->

# GRIN Reels — auto-edit

The goal is to turn a raw talking-head take plus B-roll into a 1080×1920 reel in a saved style. The engine makes every editing decision; you only run it, read the one-line JSON summary, and check the result once. Do not re-derive edits with the model, because that wastes the user's tokens.

## Start here — the person may be using AI for the first time
They will usually just drop a pile of videos and photos and write «Собери рилс» or even nothing. Do not ask them to sort the files or to explain anything technical.
1. **Sort the files yourself:** run `python -m autocut pick <all attached files>`. The video with the most speech is the talking video; everything else becomes inserts, in the order they were sent. If no video has speech, say in one plain sentence that you need a video where they talk into the camera.
2. **Say one short line before working,** for example: «Собираю рилс, это займёт 2–4 минуты». Do not narrate the steps.
3. **If something blocks you, explain it in plain words with the exact fix.** Never show a traceback.
   - No code execution: «Включи в Claude: Settings → Capabilities → Code execution and file creation, и напиши ещё раз».
   - pip or the model download fails because there is no internet: switch to LITE and ask for the text of the speech.
   - The file is too big to upload: «Сними в 1080p вместо 4K или пришли видео покороче».
4. **Finish with the video file and two short lines.** Say what was done, then give one offer, for example: «Хочешь — поменяю шрифт, цвет или заголовок, просто напиши». Speak Russian unless they write in another language.

## 0. Engine — it ships inside this skill
The full GRIN Reels engine is in this skill's own folder, under `engine/`. The person does not need to install or attach anything else.

**Default: Claude chat (any device, nothing installed).**
1. Copy the engine to the workspace: `cp -r <this skill's folder>/engine ./grin && cd grin`.
2. Run `pip install --break-system-packages numpy Pillow fonttools faster-whisper "av<16"`. ffmpeg is usually already there; if not, `apt-get install -y ffmpeg`.
3. **Full mode (try first):** `python -m autocut reel A.MOV B*.MOV --model cloud --out jobs/NAME`. The first run in a chat downloads the speech model (about 480 MB, roughly 40 s) from the GRIN GitHub release; later runs in the same chat reuse it. A 1-minute take takes about 2–3 minutes in total. Full mode hears the speech, picks the best takes and cuts the mistakes, so no script is needed. If the person sent their text anyway, add `--script script.txt` for exact spelling.
4. **If the download fails** (no network access, or GitHub is blocked in their settings), fall back to LITE. Get the words the person says from `script.txt` or the message, write them one sentence per line, and run `python -m autocut reel A.MOV B*.MOV --script script.txt --lite --out jobs/NAME`. If they gave no text, ask once: «Пришли текст, который ты говоришь в видео». LITE needs **one clean take that follows the script**. Timing is within about 0.2 s.
5. Send `jobs/NAME/final.mp4` with SendUserFile.

**Optional: the person's own computer.** If a computer is connected and has `~/grin-reels` installed with `bash install.sh` on Mac or `install.ps1` on Windows, run `~/grin-reels/.venv/bin/python -m autocut reel …` there. It is faster, works without Claude through its button page, and can use the larger speech model.

## 0c. The person prefers buttons?
Tell them to double-click «Запустить GRIN Reels» in the GRIN Reels folder. It opens a page with drop zones for the video, shots/photos, optional text, simple choices (font, colour, music, LUT, end button) and a «Мои файлы» tab for their own fonts, music, stickers and LUTs. On the same Wi-Fi the page also opens on an iPhone, at the address the window shows.

## 0d. The person sends their own files — just do it
People send files in the chat and say what they want. Put each file into the right `library/<kind>/my/` folder. Then write a style copy with `autocut.choices.apply_choices(style, {...})`, which handles font family names, exposure and B-roll colour. Keys: `title_font`, `caption_font` (`fonts/my/X.ttf`), `accent` (hex), `lut` (`luts/my/X` or `none`), `music` (`music/my/X.mp3`), `music_db`, and `cta` (`stickers/my/X.png` or `none`). Run with `--style` set to that copy. Don't ask them to sort files into folders.
- **Colour, LUT file (.cube):** copy it to `library/luts/my/` and set `lut`.
- **Colour, screenshot or reference picture:** run `python -m autocut lut-from-ref A.MOV ref.png --name ref_look`. Use `--strength 0.4` for subtle and `0.8` for strong; the default is 0.6. Set the `lut` it returns. Check one frame against the reference.
- **Font file (.ttf/.otf):** copy it to `library/fonts/my/`. Set `title_font` or `caption_font`. Check that it has Cyrillic, or render one test caption.
- **Font screenshot:** name the closest free Google Fonts family in one line. Fetch the static TTF from the `google/fonts` GitHub repo (`ofl/<family>/`) and use it. If that can't be fetched, ask the person to send the font file.
- **Music (.mp3/.wav/.m4a):** copy it to `library/music/my/`. Set `music` and `music_db` to between −12 and −18. Remind them once that they need the rights.
- **Photos and pictures:** pass them as B-roll in the order or at the words the person describes; images get the slow camera push. To place one on a phrase, move its `start` in `spec.json` and re-`render`.
- **End sticker or button (PNG):** copy it to `library/stickers/my/` and set `cta`. It pops on the last phrase.

## 0e. Any look from one reference reel or a few words
**One finished reel someone else made** (no source clips): run `python -m autocut style-from-ref REF.mp4 --name ref_x`. It measures the editing pace, the B&W share and music under the voice. It saves colour reference frames, so each new video gets its own LUT toward that colour automatically. It writes `styles/ref_x.json`. Then open `library/looks/ref_x/sheet.png` once and set what only eyes can judge, editing only `caption_style`, `title` and `sticker` in that style file:
- caption mode: `phrase` = short phrases; `words` = 1–3 big words with the spoken word lit up;
- caption font, size, color and `uppercase`;
- `box` (a plate behind the words, `{"color":"#000000","alpha":0.55,"pad":14}`) and `pop`;
- whether there is a title, and its colours;
- the end sticker.

Use the closest free font. Then run with `--style styles/ref_x.json`.

**A description in words** maps straight onto the same settings. Examples:
- «динамично» → `broll_rules.cut_len` 0.5–0.7.
- «спокойно / кинематографично» → `cut_len` 1.5–2.5, `looks` `["color"]`.
- «как у блогеров, крупные слова» → `caption_style.mode` `words`, `uppercase` true, `pop` true, `size` 82–96.
- «на плашке» → `box`.
- «без ч/б» → `broll_rules.looks` `["color"]`.
- «тёплый / холодный / плёнка» → a LUT, or a reference picture via `lut-from-ref`.

Change only what was asked, run, and show the result.

**Safe zone:** titles and captions are kept automatically inside the area that Reels, TikTok and Shorts never cover. They are also moved off the speaker's face, using YuNet in `library/models`. If the person sends their own safe-zone frame picture (white = safe), run `python -m autocut safe-from-frame frame.png` and put the JSON into the style as `safe_zone`.

## 0f. Fonts, icons, colour presets
**Fonts (all OFL, Cyrillic).** The skill carries Montserrat, Oswald and Inter. Other families live in the public repo; fetch one only when the person picks it:
`curl -sSL -o library/fonts/<dir>/<File>.ttf https://raw.githubusercontent.com/ernoxq/grin-reels-app/main/library/fonts/<dir>/<File>.ttf`
Available folders:
- comforter, cormorantgaramond, didactgothic, greatvibes, inter, jost, lobster, manrope, marckscript;
- montserrat, notoserifdisplay, oldstandardtt, orelegaone, playfairdisplay, playfairdisplaysc, podkova, prata;
- ptserif, robotocondensed, sourcesans3.

File names follow the pattern `Family-Weight.ttf`, for example `PlayfairDisplay-Italic.ttf` or `Jost-SemiBold.ttf`.

Good pairs to suggest:
- Playfair Display + Inter;
- Cormorant Garamond + Jost;
- Prata + Lobster;
- Noto Serif Display + Manrope;
- Old Standard TT + Didact Gothic;
- Great Vibes + Montserrat;
- Roboto Condensed + Comforter.

**Icons.** There are 61 GRIN line icons in `autocut/icons.py`, one family on a 24 px grid. Make a PNG sticker in any colour with `python -m autocut icon send --color "#1E1E1D" --bg "#E4F23C" --label "Напиши мне" --out x.png`, then use it as `cta` or an overlay. Show the set with `python -m autocut icons`, which writes `library/icons/_sheet.png`. For the end button there is a shortcut: `apply_choices(style, {"cta_icon": "send", "cta_label": "...", "cta_color": "#...", "cta_bg": "#..."})`.

**Colour presets** live in `library/luts/presets/*.cube`. Each has a Russian title:
- 01 Чистый нейтральный, 02 Тёплый вечер, 03 Холодное утро, 04 Кино: бирюза и оранжевый;
- 05 Плёнка, 06 Пастель, 07 Сочный, 08 Матовый;
- 09 Тёмный и глубокий, 10 Золотой час, 11 Ч/Б мягкий, 12 Ч/Б контрастный.

Set one with `lut: "luts/presets/04_teal_orange"`.

**White point:** choices `{"wb": "auto"}` neutralises colour casts for each video.

**Sliders:** choices `{"adjust": {"temp": -1..1, "exposure": -1..1, "contrast": -1..1, "saturation": -1..1}}`. A positive `temp` is warmer.

## 0g. Anything on top, at the right words
After a reel is built, the person can ask to put something on top of it: «на словах про кофе покажи это фото», «сердечко на словах ‘очень рада’», «моё видео маленьким окном сверху». Use `place`, then re-render:
- `python -m autocut place jobs/NAME/spec.json FILE --words "про кофе" [--how full|window|sticker] [--pos top|center|bottom|left|right|top-left|top-right] [--anim pop|fade|slide|none] [--dur 2]`
- For an icon: `python -m autocut place jobs/NAME/spec.json --icon heart --color "#1E1E1D" --bg "#E4F23C" [--label "текст"] --words "..."`
- Then run `python -m autocut render jobs/NAME/spec.json --out jobs/NAME/final.mp4`.

`full` covers the screen, like B-roll; the voice keeps playing. `window` is a small photo or video on top. `sticker` is a small PNG or icon. By default these sit at the top, away from the face and the captions. The words are found in the subtitles, and approximate word forms work.

## 1. Inputs (don't open frames)
- The A-roll is the long clip with continuous speech; B-roll clips are the short ones. Check durations with `ffprobe` only.
- Keep the B-roll in the order the user gave it.
- Optional: `script.txt` with one sentence per line, for exact spelling and the best takes. Optional: `--title "…"`.
- The style defaults to `styles/warm_intro.json`. When the user names another look, copy the style file and change only the fields they asked about.

## 2. One command
```bash
python -m autocut reel A.MOV B1.MOV B2.MOV … --style styles/warm_intro.json [--script script.txt] [--out jobs/NAME]
```
It prints a JSON line with `spec`, `video`, `duration`, `cuts`, `broll` and `captions`. Don't read the full spec unless something looks wrong.

## 3. Verify once
```bash
ffmpeg -loglevel error -i jobs/NAME/final.mp4 -vf "fps=2,scale=180:-2" -frames:v 36 /tmp/f_%02d.png && ffmpeg -loglevel error -i /tmp/f_%02d.png -vf tile=9x4 -frames:v 1 jobs/NAME/sheet.png
```
Look at `sheet.png` a single time and check:
- the title sits on the first sentence;
- captions are readable and take at most 2 lines;
- B-roll appears mid-video and not on the CTA;
- the CTA and the fade come at the end.

## 4. Fixes: edit the spec, then re-render
Change `jobs/NAME/spec.json` (caption `text`/`start`/`end`, B-roll `in`/`start`/`dur`/`speed`/`look`, `title.lines`), then run `python -m autocut render jobs/NAME/spec.json`. Speech recognition does not run again.

## 5. Deliver
Send `final.mp4`. Music is not bundled: set `music.asset` to a licensed file in `library/music/`, or the user adds music afterwards. CapCut draft export is optional and experimental (`requirements-capcut-experimental.txt`); don't promise that it works.

## Built-in rules (don't re-derive)
- **Takes:** the last good take wins, pauses over 0.55 s are cut, and cuts keep 80 ms before and 140 ms after the speech.
- **Captions:** 2–6 words per caption, wrapped at 16 characters onto at most 2 lines. Lowercase except proper nouns, and never a dangling «и/в/на/то» at a line end.
- **Title:** the first sentence in uppercase on 2 lines; line 2 uses the accent colour and blurs in.
- **B-roll:** clauses alternate between face and B-roll within 8–68 % of the runtime. A clause of 3 s or more becomes a beat montage cut every 2 beats, alternating colour and B&W. Clips shot at 60 fps play at 0.8×.
- **Look:** zoom 1.105, frame shifted up, A-roll exposure normalised, then LUTs and the bottom shadow. The video ends with the CTA pop and a 0.53 s fade.
