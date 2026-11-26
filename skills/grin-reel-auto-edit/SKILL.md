---
name: grin-reel-auto-edit
description: Монтаж. Finished vertical reel from the person's videos and photos: cuts pauses and bad takes, subtitles, title, colour, inserts, motion text + a CapCut project. Use for «собери рилс», «смонтируй».
---

<!-- GRIN Reels skill — © 2026 Ernest Grin (GRIN studio). All rights reserved. Licensed to the buyer for personal use; redistribution or resale prohibited. -->

# GRIN Reels: auto-edit

The engine makes every editing decision. Your job is to run ONE command and send the file. The person pays for every word you read and write, so save their limits.

## Save limits (strict)
- Do not read `reference.md`, `spec.json`, logs or frames unless something failed or the person asked for a change that needs them.
- Do not look at the video or make contact sheets. Do not explain the steps.
- Before working, write one line: «Собираю рилс, это займёт несколько минут». After, at most 3 short lines.
- Never re-run the whole build for a small change: edit the spec and `render` (see reference.md, F).

## 0. Folder mode: «Монтаж Claude» on the person's computer (check first)
If the session has `mcp__remote-devices__*` tools, call `get_device_info`. If a connected folder contains `Исходники` (or the person names their editing folder), work there and do NOT ask them to attach files:
- `Исходники/` - raw videos and photos (one reel at a time, or a subfolder per reel - take the one they name, else the newest files);
- `Референсы/` - reels or pictures whose style to copy (use them only if the person asks for that style);
- `Готовое/` - results go here;
- `Вкус/` - the creator's saved taste: reel styles `ref_*.json` (pass with `--style`), `taste_*.json` for carousels, `голос.md` for texts. Create the four folders if the connected folder is empty.

Run it on the computer with `device_bash` (it has 4 cores and sees the files; nothing is uploaded):
```bash
[ -d $HOME/grin ] || git clone -q --depth 1 https://github.com/ernoxq/grin-reels-app $HOME/grin; cd $HOME/grin && git pull -q
F="$HOME/mnt/<folder>"; nohup bash run.sh "$F/Исходники/"* --plan --out $HOME/grin/jobs/r1 --deliver "$F/Готовое" --name "<short name>" \
  --export capcut,fcpxml,srt [--capcut-root "$HOME/mnt/CapCut/User Data/Projects/com.lveditor.draft"] \
  --map "$HOME/mnt/<folder>=<real path of that folder>" ["$HOME/mnt/CapCut=<real path of CapCut folder>"] > $HOME/out.txt 2>&1 &
```
Real paths come from `get_device_info.connectedFolders`. Poll: `sleep 170; tail -25 $HOME/out.txt` (device_bash calls stop at 180 s; the job keeps running). Then the storyboard as in section 2, and `cd $HOME/grin && nohup python3 -m autocut finish jobs/r1 > $HOME/out.txt 2>&1 &` - it renders and writes everything into `Готовое` (and CapCut).
- **CapCut project:** only if the person uses CapCut on this computer. Ask once to connect `~/Movies/CapCut` (device_request_folder_access) and pass `--capcut-root`; the reel then appears in CapCut after CapCut is restarted (Cmd+Q, open again). Without that folder the draft is left in `Готовое/<name> - проект/CapCut/`.
- **DaVinci Resolve / Final Cut:** `<name> (DaVinci, Final Cut).fcpxml` in the project folder: File → Import → Timeline (DaVinci) or File → Import → XML (Final Cut).
- Results: `Готовое/<name>.mp4`, `Готовое/<name> - проект/` (FCPXML, subtitles .srt, fonts and stickers). Say where they are in one line; do not send the video into the chat unless asked.
- No `device_bash`, only file tools: stage the files from `Исходники`, run section 2 here, then write `final.mp4` back with `device_commit_files` (send it with SendUserFile first and commit by its file_uuid; big files can't be committed by path).

## 1. Setup (once per chat, attached files)
```bash
[ -d grin ] || cp -r <this skill's folder>/engine ./grin
```

## 2. Storyboard first, then build
```bash
nohup bash grin/run.sh <ALL attached videos and photos, absolute paths> --plan --out grin/jobs/r1 [options] > grin/out.txt 2>&1 &
```
Wait cheaply: `sleep 120; tail -25 grin/out.txt` until the plan appears (about 1.5 min per minute of raw video).
Before showing it, fix obvious speech-recognition mistakes yourself with `--fix "wrong=right"` (one or several words, e.g. `"anuarii=ianuarie"`, `"и получаешь=и не получаешь"`; you know the language and the meaning) and re-plan once. If a kept sentence is clearly a stumble or a repeat of a later one, drop it with `--drop`. Then show the plan to the person as it is (it is short: kept sentences with times, inserts, what was cut, title) and ask: «Собираю так или что-то поменять?». Apply what they say, re-plan (fast, speech is not recognised again), show again:
- cut a phrase: `--drop "фраза"` (undo: `--keep "фраза"`); other title: `--title "..."`;
- photo / video / icon on certain words: `place` (reference.md, E); animated text: `place --motion` (below);
- run the same command with the same `--out` and the new options; earlier drops and title are remembered. A new reel gets a new `--out` (r2, r3...).
Then render: `nohup python -m autocut finish grin/jobs/r1 > grin/out.txt 2>&1 &` (run inside `grin`), poll, read the JSON line.
If the person says «сразу» / «без плана», skip `--plan` and the build finishes in one go.

Options (add only if the person said so):
- `--all-talking` - «соедини все», or all clips are the person talking; `--talking IMG_1 IMG_4` - only these are the talk.
- `--lang ro` / `ru` / `en` - only if subtitles came out in the wrong language. `--script script.txt` - exact text.
- `--no-inserts`.
- There is NO end button by default. Add one only if asked (reference.md, D: `cta_icon` / `cta`).

The engine itself joins every talking clip in file-name order, removes repeats, pauses and mistakes, spreads the other files evenly as inserts (never on the title or the end), detects the language.

**Motion graphics (animated text in GRIN style)** - offer when a number, a name, a step or a key phrase deserves it:
`python -m autocut place grin/jobs/r1/spec.json --motion KIND --text "..." --words "слова из речи" [--pos auto|top|center|bottom] [--accent "#E4F23C"]`
By default (`auto`) the engine finds the face and puts the graphic above the head if there is room, else on the chest above the captions — never on the face. Before rendering, show the person the list of motion texts with their words («что напишу и где») and let them correct it: you invent these texts, so they must approve them.
- `headline` - big words pop in, `*phrase in stars*` gets a marker: «Монтаж за *15 минут*»;
- `plate` - name plate, `--sub` small line above: «Кристина» / «свадебный рилсмейкер»;
- `number` - counts up: «30 000 лей», `--label` under it;
- `step` - numbered circle + label, `--n 02`;
- `checklist` - `"пункт 1|пункт 2|пункт 3"` with ticks.
Each is a separate clip in the CapCut / DaVinci project, so it stays editable. Do not look at the result yourself.

**Reference by link:** `python -m autocut fetch URL --out <Референсы or refs>`. If it answers `network` or `login`, tell the person: «Не могу скачать по ссылке - сохрани рилс и положи файл в папку Референсы (или пришли сюда)».

**Studio format** (speaker cut out of the room on a light set + cards, like many "expert" reels): use the `grin-reel-studio` skill on the same job. Tip for the person: film with room on both sides and down to the table; a tight vertical crop leaves straight edges on the cut-out.

**Safe zones:** captions, titles and graphics stay inside the Reels/TikTok/Shorts safe band (y 270–1495 of 1920). Never move them lower than that on request without warning that the app's caption and buttons will cover them.

## Colour: natural by default (strict)
- The default style `natural` keeps real colours: a gentle white-balance nudge (only if there is something white/grey in the shot), +8 % contrast, +6 % saturation. Do not add a LUT, filter or "cinematic look" unless the person asks.
- Asked for a look («теплее», «как плёнка», «кино»): one preset at 60 % (`apply_choices` with `lut` and `lut_strength` 0.4-0.7, reference.md D). Never stack a preset + sliders + a reference colour.
- Small wishes go to sliders, max ±0.3: «чуть теплее» `temp 0.2`, «светлее» `exposure 0.2`, «сочнее» `saturation 0.2`.
- Colour from a reference reel only when the person asks for that colour: `style-from-ref ... --colour` (applied at 40 %). By default a learned style copies pace, captions and music, not the colour.
- After any colour change look at ONE frame (`ffmpeg -ss 3 -i final.mp4 -frames:v 1 -vf scale=360:-2 f.png`). Skin must look like skin; if it went green, grey, orange or too dark, halve the strength and render again.

## Flexibility: what to do with any wish
- About the content (what stays, order, words, title): storyboard flags `--drop`, `--keep`, `--fix`, `--title`, `--talking` (order of the parts = order you list them).
- Something on screen at certain words: `place` (photo, video window, icon, sticker) or `place --motion` (animated text).
- Fonts, colours, music, end button, captions look: `apply_choices` / style fields (reference.md B-D).
- The person's whole vibe from 1-5 reels: `gubka-spanch` skill (styles saved in `Вкус/`).
- Anything the engine has no option for: do it as a small extra step on `final.mp4` with ffmpeg (one command, `-loglevel error`), or tell them it is a manual touch in CapCut - the project is there.

## 3. Deliver
Send the `video` path from the JSON with SendUserFile (folder mode: just say where it is). Then 2–3 lines: length, which clips became the talk, language. One offer: «Могу поменять шрифт, цвет, заголовок или поставить фото на нужные слова» or «Проверить на кринж перед публикацией?» (antikrinzh skill).

## 4. If it fails
Read only the last 15 lines of `grin/grin.log`. Explain in plain words with the fix, never a traceback:
- no code execution → «Включи Settings → Capabilities → Code execution, и напиши ещё раз»;
- the model download failed → ask for the text and add `--script` (see reference.md for LITE);
- the file is too big → «Сними в 1080p вместо 4K или пришли видео покороче».

## 5. Changes after the first version
Fonts, colour presets, LUTs, music, own files, icons, a photo or sticker on certain words, a style from someone's reel: open `reference.md` and read ONLY the matching section (A–H). Speak Russian unless the person writes in another language.
