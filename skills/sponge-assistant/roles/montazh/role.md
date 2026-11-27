
<!-- GRIN Reels skill — © 2026 Ernest Grin (GRIN studio). All rights reserved. Licensed to the buyer for personal use; redistribution or resale prohibited. -->

# Монтаж

The engine makes every editing decision. You run ONE command and send the file. The person pays for every word you read and write.

## Save limits (strict)
- **Never read, grep or edit the engine's code** (`autocut/*.py`, `styles/`, `--help` output). Every wish is a command below or in reference.md. Not covered → say so in one line and offer the closest command; never patch the engine.
- Budget for one reel: about 10 tool calls (unpack → plan → one `--fix` re-plan → `look`/`scene` → render → send). Going past 15 = stop and tell the person what is blocking.
- Proofread from the plan text only: `слово(?)` marks words the model is unsure of. Never open `words.json`, confidences or the speech model.
- Work from inside `grin` (`cd grin` once); job paths like `jobs/r1` are relative to it.
- Render failed → the error line already says why (ffmpeg's own words). Fix the flag/spec value it names, render once more; don't debug the renderer.
- Open `reference.md` only for the section a request needs (A–J). Never read spec.json, logs or frames unless something failed.
- Don't look at the video, don't explain steps. Before: «Собираю рилс, это займёт несколько минут». After: max 3 short lines.
- Small change = edit the spec and `render` (reference.md F), never a full rebuild.
- Cuts the person names in seconds («вырежи 12.4–13.1») are approximate: change `voice` in the spec as asked; the engine moves each cut to the nearest pause, so word starts and ends are never eaten, and adds click-free fades. Never shave pads yourself. If they say a word is still clipped, widen that segment by 0.1 s.
- Editing is done by asking you in this chat. The only editor project is **CapCut**, and only when the person's Mac folder is connected (reference.md I). Never make DaVinci/Final Cut/SRT files.

## 1. Setup
Computer folder «Монтаж Claude» connected (the session has `mcp__remote-devices__*` tools and a folder with `Исходники`)? → follow reference.md I instead of this section.
Otherwise (files attached to the chat):
```bash
[ -d grin ] || { mkdir -p grin && tar xzf <this skill's folder>/engine.tar.gz -C grin; }
```

## 2. Storyboard first, then build
```bash
nohup bash grin/run.sh <ALL attached videos and photos, absolute paths> --plan --out grin/jobs/r1 [options] > grin/out.txt 2>&1 &
```
Wait cheaply: `sleep 120; tail -25 grin/out.txt` until the plan appears (~1.5 min per minute of raw video).
**Captions must be CapCut-level or better: proofread every plan before showing it.** Read the whole text once like an editor: misheard words («к Лоду»→«Клоду», «клад»→«Клод», «Терраспалета не обойдет с стороной»→«Тирасполь это не обойдёт стороной»), names and brands, case endings, numbers. Fix ALL of them in one `--fix "wrong=right" ...` re-plan (several words → any number of words, timing is kept); you know the language and the meaning, Whisper doesn't. Never paraphrase what they said, only what was misheard. Drop clear stumbles/repeats with `--drop`.
First run: pass `--vocab "names, brands, terms"` you already know (their name, brand, city, Claude/CapCut...; folder mode: the contents of `Вкус/словарь.txt` if it exists). When they correct a word, offer once to add it to `Вкус/словарь.txt`.
- `--drop "фраза"` (undo `--keep`), `--trim "[Но] пока что"` (removes only the bracketed words, cut in place; undo `--untrim`; a word said fused with its neighbours, with no gap, may stay audible: prefer trimming at sentence starts and after pauses), `--target 60` (plan shows how much to cut), `--title "..."`; same `--out` remembers earlier choices; a new reel gets a new `--out`.

**Shortening («на минуту», «короче»): logic first, seconds second.** Keep an arc: hook (what this is about) → the point → conclusion. Prefer dropping repeats, side stories and filler over the point or the ending. Never keep a line marked ⚠ (it continues a thought that was cut: «Но…», «Это…», «Не знаю, но…», a lowercase fragment); the plan quotes the removed sentence it needs. Fix with `--keep "<that sentence>"` or `--trim "[Но] …"`, or drop the line too. Use the per-line seconds in the plan to choose ALL cuts at once (one re-plan, not trial and error). Over target by <15 % → suggest `look --speed 1.1` instead of cutting meaning.

**Agree before building (one short message, then wait):** after the proofread plan run `python -m autocut sheet jobs/r1` and send `jobs/r1/storyboard.png` (the storyboard: a frame, time and words per line, ⚠ in red, cuts in grey) WITHOUT opening it yourself, with the brief below:
«План (≈N с):
1. Хук: «…»
2. Суть: «…» → «…»
3. Вывод: «…»
Убираю: <2–4 words per removed part>. Вид: <субтитры / кадр / музыка / скорость — only what they asked or the defaults>.
Собираю так?»
Build only after a yes or edits.

**Voice: never process it.** The engine only brings it to −14 LUFS (no denoise on clean recordings, no declick, no EQ). Don't add filters, don't "repair" it: every attempt so far made it worse. Mouth clicks («цоканье») all over → say plainly the engine can't remove them without hurting the voice and offer: run the ORIGINAL clip's audio through Adobe Podcast Enhance (podcast.adobe.com/enhance, free), send the file back → `look jobs/r1/spec.json --voice-audio enhanced.wav` → render. Montage, captions and timing stay the same.
**One noise at a named moment («цоканье на 0:09»)** → `python -m autocut quiet jobs/r1/spec.json 0:09 [1:16 …]`, then render. It mutes only the pause between words at that moment (the engine does not guess mouth noise on its own: it sounds like soft syllables). Reply says `muted_sec: 0` → that moment is inside a word; tell them. Skip the brief only if they said «сразу» / «без плана» or they already approved this plan.
- photo / video / icon on certain words: `place` (reference.md E); animated text: reference.md J.
Render: `cd grin && nohup python -m autocut finish jobs/r1 > out.txt 2>&1 &`, poll, read the JSON line.
«сразу» / «без плана» → skip `--plan`.

Options only if the person said so: `--all-talking` («соедини все»), `--talking IMG_1 IMG_4`, `--lang ro|ru|en` (wrong subtitle language), `--script script.txt`, `--no-inserts`. No end button unless asked (reference.md D).
The engine joins talking clips in file-name order, removes repeats, pauses and mistakes, spreads the other files as inserts, detects the language.

## 3. Colour: natural by default (strict)
No LUT or «cinematic look» unless asked. Asked for a look: one preset at 40-70 % (reference.md D). Small wishes: sliders ±0.3 («чуть теплее» `temp 0.2`, «светлее» `exposure 0.2`, «сочнее» `saturation 0.2`). Never stack preset + sliders + reference colour. After a colour change look at ONE frame (`ffmpeg -ss 3 -i final.mp4 -frames:v 1 -vf scale=360:-2 f.png`): skin must look like skin, else halve the strength.

## 4. Any other wish
Content (what stays, order, words, title) → plan flags. Something on screen at certain words → `place`. Fonts, colours, music, captions → reference.md D. Their vibe from 1-5 reels → `gubka-learn`. Studio format → `grin-reel-studio`. Link to a reference → reference.md J. Anything else → one small ffmpeg step on `final.mp4`.

**Caption look + punch-in (one command, then render):** `python -m autocut look jobs/r1/spec.json --captions minimal|bold|box|words [--size 58] [--y -0.4] [--font "Montserrat Medium|SemiBold|Bold|Black, Inter …, Oswald"] [--upper|--no-upper] [--color "#FFFFFF"] [--highlight "#F6DB92"] [--anim rise|pop|fade] [--punch 1.06] [--speed 1.1]`. «аккуратные/минималистичные субтитры» → `minimal`; «крупные» → `bold`; «слово подсвечивается» → `words`; «на плашке» → `box`; «зум на склейках / динамичнее» → `--punch 1.06` (1.10 strong).
Same command: `--frame fill|fit|blur` (horizontal video gets `fit` automatically: whole frame on black, captions under it; «на весь экран» → `fill`; `blur` only if they ask for a blurred background), `--music FILE --music-db -20` («тихонько» −20, «фоном» −16; looped and faded by the engine).
**A screenshot or reel of the wanted look attached → open it ONCE before the first render** and translate it into `look`/`scene` flags (layout, caption size, position, case, animation). Never render first and compare afterwards.

**Designer scenes (default for talking-head reels over 20 s, unless they say «просто»):** from the plan, pick 2–3 moments: a strong claim → `card`, an enumeration → `split`. Never in the first 1.5 s; ~1 scene per 10 s; key = 2–4 words that carry the meaning.
```bash
python -m autocut scene jobs/r1/spec.json card --from "первые слова" [--to "последние слова"] --key "ключевая фраза|ещё слово"
python -m autocut scene jobs/r1/spec.json split --from "первые слова" --list "пункт 1|пункт 2|пункт 3"
python -m autocut render jobs/r1/spec.json --out jobs/r1/final.mp4
```
Colours: `scene_style` in spec (`bg`, `ink`, `key`, `key_edge`), e.g. from their taste. Scenes are in the MP4 only; the CapCut project keeps the plain cut (say so in one line if they edit in CapCut). Undo: `scene ... clear`.
Safe zone: captions and graphics stay in y 270–1495 of 1920; warn before moving them lower.

## 5. Deliver
Send `video` from the JSON with SendUserFile (folder mode: just say where). 2–3 lines: length, which clips became the talk, language. One offer: «Поменять шрифт, цвет, заголовок или поставить фото на нужные слова?» or «Проверить на кринж перед публикацией?» (antikrinzh).

## 6. If it fails
Read only the last 15 lines of `grin/grin.log`, explain in plain words with the fix, never a traceback:
- no code execution → «Включи Settings → Capabilities → Code execution and file creation и напиши ещё раз»;
- model download failed → ask for the text and use `--script`;
- file too big → «Сними в 1080p вместо 4K или пришли видео покороче».
Reply in Russian unless the person writes in another language.
