# GRIN Reels - extra recipes (read ONLY the section you need)

All commands run inside `./grin` (the engine copy).

## A. The person prefers buttons?
Tell them to double-click «Запустить GRIN Reels» in the GRIN Reels folder. It opens a page with drop zones for the video, shots/photos, optional text, simple choices (font, colour, music, LUT, end button) and a «Мои файлы» tab for their own fonts, music, stickers and LUTs. On the same Wi-Fi the page also opens on an iPhone, at the address the window shows.

## B. The person sends their own files - just do it
People send files in the chat and say what they want. Put each file into the right `library/<kind>/my/` folder. Then write a style copy with `autocut.choices.apply_choices(style, {...})`, which handles font family names, exposure and B-roll colour. Keys: `title_font`, `caption_font` (`fonts/my/X.ttf`), `accent` (hex), `lut` (`luts/my/X` or `none`), `music` (`music/my/X.mp3`), `music_db`, and `cta` (`stickers/my/X.png` or `none`). Run with `--style` set to that copy. Don't ask them to sort files into folders.
- **Colour, LUT file (.cube):** copy it to `library/luts/my/` and set `lut`.
- **Colour, screenshot or reference picture:** run `python -m autocut lut-from-ref A.MOV ref.png --name ref_look`. Use `--strength 0.4` for subtle and `0.8` for strong; the default is 0.6. Set the `lut` it returns. Check one frame against the reference.
- **Font file (.ttf/.otf):** copy it to `library/fonts/my/`. Set `title_font` or `caption_font`. Check that it has Cyrillic, or render one test caption.
- **Font screenshot:** name the closest free Google Fonts family in one line. Fetch the static TTF from the `google/fonts` GitHub repo (`ofl/<family>/`) and use it. If that can't be fetched, ask the person to send the font file.
- **Music (.mp3/.wav/.m4a):** copy it to `library/music/my/`. Set `music` and `music_db` to between −12 and −18. Remind them once that they need the rights.
- **Photos and pictures:** pass them as B-roll in the order or at the words the person describes; images get the slow camera push. To place one on a phrase, move its `start` in `spec.json` and re-`render`.
- **End sticker or button (PNG):** copy it to `library/stickers/my/` and set `cta`. It pops on the last phrase.

## C. Any look from one reference reel or a few words
**One finished reel someone else made** (no source clips): run `python -m autocut style-from-ref REF1.mp4 [REF2.mp4 ... up to 5] --name ref_x`. It measures the editing pace, the B&W share and music under the voice. It saves colour reference frames, so each new video gets its own LUT toward that colour automatically. It writes `styles/ref_x.json`. Then open `library/looks/ref_x/sheet.png` once and set what only eyes can judge, editing only `caption_style`, `title` and `sticker` in that style file:
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

## D. Fonts, icons, colour presets
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

Set one with `apply_choices(style, {"lut": "luts/presets/04_teal_orange", "lut_strength": 0.6})` - 0.4 subtle, 0.6 normal, 0.8 strong; full strength is almost always too much.

**White point:** choices `{"wb": "auto"}` neutralises colour casts for each video.

**Sliders:** choices `{"adjust": {"temp": -1..1, "exposure": -1..1, "contrast": -1..1, "saturation": -1..1}}`. A positive `temp` is warmer.

## E. Anything on top, at the right words
After a reel is built, the person can ask to put something on top of it: «на словах про кофе покажи это фото», «сердечко на словах ‘очень рада’», «моё видео маленьким окном сверху». Use `place`, then re-render:
- `python -m autocut place jobs/NAME/spec.json FILE --words "про кофе" [--how full|window|sticker] [--pos top|center|bottom|left|right|top-left|top-right] [--anim pop|fade|slide|none] [--dur 2]`
- For an icon: `python -m autocut place jobs/NAME/spec.json --icon heart --color "#1E1E1D" --bg "#E4F23C" [--label "текст"] --words "..."`
- Then run `python -m autocut render jobs/NAME/spec.json --out jobs/NAME/final.mp4`.

`full` covers the screen, like B-roll; the voice keeps playing. `window` is a small photo or video on top. `sticker` is a small PNG or icon. By default these sit at the top, away from the face and the captions. The words are found in the subtitles, and approximate word forms work.

## F. Fixes: edit the spec, then re-render
Change `jobs/NAME/spec.json` (caption `text`/`start`/`end`, B-roll `in`/`start`/`dur`/`speed`/`look`, `title.lines`), then run `python -m autocut render jobs/NAME/spec.json`. Speech recognition does not run again.

## G. Deliver
Send `final.mp4`. Music is not bundled: set `music.asset` to a licensed file in `library/music/`, or the user adds music afterwards. CapCut draft export is optional and experimental (`requirements-capcut-experimental.txt`); don't promise that it works.

## H. Built-in rules (don't re-derive)
- **Takes:** the last good take wins, pauses over 0.55 s are cut, and cuts keep 80 ms before and 140 ms after the speech.
- **Captions:** 2–6 words per caption, wrapped at 16 characters onto at most 2 lines. Lowercase except proper nouns, and never a dangling «и/в/на/то» at a line end.
- **Title:** the first sentence in uppercase on 2 lines; line 2 uses the accent colour and blurs in.
- **B-roll:** every other sentence gets an insert (never the title sentence or the last one); with few clips they are spread evenly over the whole video; one insert covers at most 4 s, then the face returns. A clause of 3 s or more becomes a beat montage cut every 2 beats, alternating colour and B&W. Clips shot at 60 fps play at 0.8×.
- **Look:** zoom 1.105, frame shifted up, A-roll exposure normalised, then LUTs and the bottom shadow. The video ends with the CTA pop and a 0.53 s fade.

## I. Folder mode: «Монтаж Claude» on the person's computer (CapCut project)
If the session has `mcp__remote-devices__*` tools, call `get_device_info`. A connected folder with `Исходники` (or the folder they name) → work there, don't ask them to attach files:
- `Исходники/` raw videos and photos (a subfolder per reel: take the one they name, else the newest files);
- `Референсы/` reels/pictures whose style to copy (only if asked);
- `Готовое/` results; `Вкус/` saved taste: `ref_*.json` (pass with `--style`), `taste_*.json`, `голос.md`. Create the four folders if empty.
Run on the computer with `device_bash` (nothing is uploaded):
```bash
[ -d $HOME/grin ] || git clone -q --depth 1 https://github.com/ernoxq/grin-reels-app $HOME/grin; cd $HOME/grin && git pull -q
F="$HOME/mnt/<folder>"; nohup bash run.sh "$F/Исходники/"* --plan --out $HOME/grin/jobs/r1 --deliver "$F/Готовое" --name "<short name>" \
  --export capcut [--capcut-root "$HOME/mnt/CapCut/User Data/Projects/com.lveditor.draft"] \
  --map "$HOME/mnt/<folder>=<real path of that folder>" ["$HOME/mnt/CapCut=<real path of CapCut folder>"] > $HOME/out.txt 2>&1 &
```
Real paths: `get_device_info.connectedFolders`. Poll `sleep 170; tail -25 $HOME/out.txt` (device_bash stops at 180 s; the job keeps running). Show the plan as in section 2, then `cd $HOME/grin && nohup python3 -m autocut finish jobs/r1 > $HOME/out.txt 2>&1 &`.
- CapCut: ask once to connect `~/Movies/CapCut` (device_request_folder_access) and pass `--capcut-root`; the reel appears after CapCut is restarted (Cmd+Q, open). Without it the project is left in `Готовое/<name> - проект/CapCut/`: «скопируй эту папку в папку проектов CapCut».
- Result: `Готовое/<name>.mp4` + the CapCut project. Say where in one line; don't send the video into the chat unless asked.
- No `device_bash`, only file tools: stage the files, build in the cloud (section 2), write `final.mp4` back with `device_commit_files` (send it with SendUserFile first, commit by file_uuid). No CapCut project in this case.
- On a Mac the engine needs `install.sh` once (ffmpeg + Python). If `run.sh` says ffmpeg is missing: «Один раз запусти install.sh из архива GRIN Reels».

## J. Motion graphics and references by link
Animated GRIN text, offer when a number, a name, a step or a key phrase deserves it:
`python -m autocut place grin/jobs/r1/spec.json --motion KIND --text "..." --words "слова из речи" [--pos auto|top|center|bottom] [--accent "#E4F23C"]`
`auto` finds the face and puts the graphic above the head or on the chest, never on the face. Show the list of texts with their words before rendering: you invent them, they approve.
- `headline` big words pop in, `*phrase*` gets a marker; `plate` name plate, `--sub` small line; `number` counts up, `--label`; `step` numbered circle, `--n 02`; `checklist` `"п1|п2|п3"` with ticks.
Each is its own clip in the CapCut project.
Reference by link: `python -m autocut fetch URL --out refs`. Answer `network` or `login` → «Не могу скачать по ссылке - сохрани рилс и пришли файл».
