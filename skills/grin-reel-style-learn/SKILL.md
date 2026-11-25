---
name: grin-reel-style-learn
description: Learn the editing style of any reel the person likes, from just that finished video ("сделай в таком стиле", "разбери этот ролик"), or very precisely from the reel plus its source clips, and save it as a reusable GRIN Reels style - including the studio format (speaker cut out on a light set with animated cards) and motion graphics. Then the person's own videos are edited in that style. Use for «сделай в таком стиле», «как этот ролик», «разбери референс», «повтори этот монтаж».
---

<!-- GRIN Reels skill — © 2026 Ernest Grin (GRIN studio). All rights reserved. Licensed to the buyer for personal use; redistribution or resale prohibited. See LICENSE.md in the GRIN Reels folder. -->

# GRIN Reels - learn a style from a reference

Save the person's limits: the script measures pace, colour and music; you look at ONE small picture (8 key frames) once, and never at the reel itself. Reply in 2-3 lines.

**Folder «Монтаж Claude»:** if the person's computer folder is connected (see the auto-edit skill, section 0), take the reference from `Референсы/` (the one they name, else the newest) and run the same commands there with `device_bash` in `$HOME/grin`; the style is saved in `$HOME/grin/styles/` and used for the next reels in this chat.

**Colour is NOT copied by default** (another light easily turns skin green or grey). Add `--colour` only when the person asks for the colour/look of the reference; it is applied at 40 %. Then check one frame of the result: skin must look like skin.

**3-5 reels are better than one** when they are by the same creator: pass them all in one command; pace, colour and music become their common style, and the picture shows 8 frames across all of them. In the folder mode take every file in `Референсы/` (or the ones the person names). Don't mix different creators unless asked.

## Understanding the request (read first, every time)
Do exactly what was asked, change nothing else, and keep earlier decisions. Before a build or re-render that takes minutes, say in one line what you understood: «Понял: убираю фразу про X, субтитры делаю жёлтыми, остальное как было». If a wish can mean two different results, ask ONE short question with 2–3 concrete options instead of guessing; never guess texts that will appear on screen.

| The person says | Do |
|---|---|
| «собери / смонтируй рилс», «сделай видео из этого» | auto-edit, storyboard first (section 2) |
| «сразу», «без плана», «не спрашивай» | skip `--plan`, build in one go |
| «в таком стиле», «как этот ролик», + a reel | style-learn: Step 0 (look at the whole reference), then the matching mode |
| «студийный стиль», «вырежи меня», «на светлом фоне с карточками» | Studio mode |
| «добавь анимацию / надпись на словах …» | `place --motion` on those words (texts approved first) |
| «поставь фото / видео / иконку, когда говорю …» | `place` on those words |
| «убери фразу / кусок про …» / «верни …» | `--drop "…"` / `--keep "…"` |
| «в субтитрах ошибка: … → …» | `--fix "wrong=right"` (several words are fine) |
| «другой заголовок: …» | `--title "…"` (studio: the `title` card) |
| «сделай короче, до N секунд» | drop the weakest sentences until it fits, show the plan |
| «субтитры выше / ниже / крупнее / жёлтые / другим шрифтом» | caption style (studio: `theme.caption_y`, `theme.caption`); keep inside the safe band 270–1495 and say so if asked lower |
| «закрывает лицо», «текст на лице» | `--pos auto` (default) or move the card up; studio: cards stay above the head |
| «теплее / светлее / сочнее» | one slider, ±0.2 (Colour section) |
| «музыку тише / другую / без музыки» | music in the style (reference.md, D) |
| «вставь моё фото в карточку» | studio `name` card `photo` (the file they sent) |
| «натуральнее», «не надо всё в белое», «руки обрезаны» | studio: no white fade; ask for the wide take (`--video`) |
| «хочу редактировать в CapCut» | folder mode `--export capcut` / studio `--capcut` |
| «покажи, что будет» | `--plan` (and `studio --plan`), no render |
| something you cannot do | say so in one line and offer the nearest thing you can do |

## Step 0 - look at the whole reference first (always, once)
`style-from-ref` measures only pace, colour and music; it does not see the FORMAT. So before anything else make one contact sheet of the whole reel and look at it:
`ffmpeg -v error -i REF.mp4 -vf "fps=1,scale=180:-2,tile=10x6" sheet_all.png` (one picture, read it once).
Decide which format it is and say it in one line:
- **talking head + inserts/captions** (person in their real room, B-roll, text) → continue with Quick mode below;
- **studio format** (person cut out of the background on a plain light set, cards/icons/headlines animate above them, the person shrinks when a card appears) → Studio mode, all in this engine: `python -m autocut studio-theme REF.mp4` gives the reference's colours (bg, accent, ink) for `"theme"`, then follow «Studio mode» below (`studio-help` lists the cards). Note in one line which cards the reference uses (title, name plate, quote, checklist, icons...) and use the same kinds;
- **talking head with motion graphics** (headlines, numbers, checklists over the real room) → Quick mode below for pace/captions, then `place --motion` on the key words (face-aware by default);
- anything else (screen recording, slideshow, faceless) → tell the person honestly which parts GRIN can copy and which it cannot.
Never deliver a first version in a different format than the reference: «похоже по темпу» is not «в таком же стиле».

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

## Studio mode: speaker cut out on a light set + animated cards (built in)
Use it when the person asks for it («студийный стиль», «вырежи меня на фон с карточками») or a reference is in this format (the style-learn skill tells). Same job, extra command; everything is in this engine.
1. Build the talk as usual (`python -m autocut reel` / `run.sh ... --plan` as in Quick mode) and `finish` it once - the studio uses its cuts, captions and sound. Fix recognition with `--fix` first.
2. Ask only for what is missing: the person's photo and name/role for the name plate, and **the widest take of the same recording** (horizontal is best; `--video`, aligned by sound automatically). With only a tight vertical crop say once: «по бокам будут ровные срезы - лучше снимать с запасом по бокам и до стола».
3. Colours: default dark green on light grey. From a reference: `python -m autocut studio-theme REF.mp4` → put the JSON into `"theme"`. On request: `"theme": {"accent": "#...", "bg": "#...", "caption": "#..."}`.
4. Write `scenes.json` from the meaning of the speech (`python -m autocut studio-help` lists every card): a title for the first 3 s, the name plate with the photo, a `typewriter` for any quoted verse/quote in sync with the speech, `bible` when the Bible is named, `checklist` for lists (ticks on the words), `rows` for ✓/✗ contrasts, `headline`/`giant` for punchlines, `icon_card` for «напишите в комментариях», `end` with «Сохранить». One idea per card, 2–7 s, on the words where it is said (`from`/`to`/`at` are phrases from the captions); leave 1–2 gaps without cards.
5. `python -m autocut studio jobs/r1 --scenes scenes.json --plan` → send the list as it is: «Ставлю такие карточки - что поменять?». The texts are yours, so they must approve them.
6. Render: `nohup python -m autocut studio jobs/r1 --scenes scenes.json --video WIDE.MOV > grin/out.txt 2>&1 &` (cut-out ~3 min per minute of video on 2 cores, render ~2 min) → `jobs/r1/studio/studio.mp4`. Check 4 frames once: cards never on the face, captions readable. Pass on any `tips` from the JSON in one sentence.
7. CapCut, when asked: add `--capcut "<name>" --capcut-root ".../com.lveditor.draft" --media-dir ".../GRIN media/<name>" [--map LOCAL=REAL]` - every card is its own transparent clip, the speaker a clip with scale/position keyframes, captions are CapCut text. The speaker layer is ~1 GB per minute: check disk space first. Card contents (typed text, Bible, ticks) stay baked in their clip.
Built in: yellow captions with outline inside the safe band, cards below the top UI, the speaker shrinks under a card and grows back, glitch-in at the start. The matting model (RVM, GPL-3.0) is downloaded on first use.

## Precise mode - the reel plus the source clips it was cut from
Only when the person has the original clips and wants an exact copy of a hand edit. Read `reference.md` then (it is long; skip it otherwise).
