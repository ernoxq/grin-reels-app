
<!-- Губка Спанч / GRIN — © 2026 Ernest Grin (GRIN studio). All rights reserved. Licensed to the buyer for personal use; redistribution or resale prohibited. See LICENSE.md in the GRIN Reels folder. -->

# Губка Спанч - learn a taste from references

The sponge soaks up what the creator likes so every next reel or carousel looks like THEM, not like a template. Their taste decides; you only measure and copy faithfully.

**Which branch:** videos (reels) → the reel style below. Pictures (stories, posts, carousel slides, screenshots of a profile) → «Pictures» at the end. Their own texts or voice → that is the `scenarist-hook-doctor` skill's voice card, not this one.

**Where the taste lives:** folder «Монтаж Claude» connected → save everything into its `Вкус/` folder (create it), so the next chat finds it there. No folder → send the person the small style/taste `.json` file and say: «Сохрани этот файл и пришли его в следующем чате - вкус вернётся за секунду».

Save the person's limits: the script measures pace, colour and music; you look at ONE small picture (8 key frames) once, and never at the reel itself. Reply in 2-3 lines.

**Folder «Монтаж Claude»:** if the person's computer folder is connected (montage skill, reference.md I), take the reference from `Референсы/` (the one they name, else the newest) and run the same commands there with `device_bash` in `$HOME/grin`; the style is saved in `$HOME/grin/styles/` (stays on the computer for every next chat); also copy the `.json` into `Вкус/`.

**Colour is NOT copied by default** (another light easily turns skin green or grey). Add `--colour` only when the person asks for the colour/look of the reference; it is applied at 40 %. Then check one frame of the result: skin must look like skin.

**3-5 reels are better than one** when they are by the same creator: pass them all in one command; pace, colour and music become their common style, and the picture shows 8 frames across all of them. In the folder mode take every file in `Референсы/` (or the ones the person names). Don't mix different creators unless asked.

## Step 0 - look at the whole reference first (always, once)
`style-from-ref` measures only pace, colour and music; it does not see the FORMAT. So before anything else make one contact sheet of the whole reel and look at it:
`ffmpeg -v error -i REF.mp4 -vf "fps=1,scale=180:-2,tile=10x6" sheet_all.png` (one picture, read it once).
Decide which format it is and say it in one line:
- **talking head + inserts/captions** (person in their real room, B-roll, text) → continue with Quick mode below;
- **studio format** (person cut out of the background on a plain light set, cards/icons/headlines animate above them, the person shrinks when a card appears) → use the `grin-reel-studio` skill; take its colours (background, accent, caption colour) from the sheet into `theme`;
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

Without a connected folder the style lives only in this chat: send them `styles/ref_<name>.json` to keep. Next chat: copy it into `grin/styles/` and use it (pace, captions, music come back; the reference colour needs the reference again).

## Pictures - stories, posts, carousels (5-10 references are ideal)
If they gave fewer than 3, ask once: «Пришли 5-10 референсов: свои лучшие или те, что нравятся. Можно скриншоты профиля». Or offer to build one from scratch: ask 3 things (светлое/тёмное, строго/мягко/дерзко, один цвет-акцент) and pick a preset (`clean`, `night`, `editorial`, `soft`, `bold`).
1. Engine as in Quick mode step 1, then `python -m autocut taste REF1.jpg REF2.png REEL.mp4 ... --name <short> --out <Вкус or .>/taste_<short>.json`. It measures the palette (bg, ink, accent) and how busy the slides are, and makes one sheet.
2. Look at the `sheet` it prints ONCE. In the taste file fix only what eyes judge: `theme.title_font` / `body_font` (closest free font, e.g. «Playfair Display Bold», «Manrope Medium», «Montserrat Black», «Cormorant Garamond SemiBold», «Jost Regular», «Inter Medium», «Roboto Condensed Black», «Prata Regular»), `align` (left/center), `uppercase`, wrong colours, `layouts` they use, `notes` (1-2 lines of taste, e.g. «много воздуха, один акцент на слайд»).
3. Tell them in 2 lines what you took («тёплый беж, тёмно-коричневый текст, рыжий акцент, заголовки антиквой, много воздуха»). Then offer: «Сделать карусель в этом вкусе?» (dizainer skill with `--taste`).

## Precise mode - the reel plus the source clips it was cut from
Only when the person has the original clips and wants an exact copy of a hand edit. Read `reference.md` then (it is long; skip it otherwise).
