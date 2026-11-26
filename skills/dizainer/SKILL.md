---
name: dizainer
description: Дизайнер. Carousels (up to 10 slides), posts and stories in the creator's taste, on Claude's Design canvas to edit by hand (drag, fonts, sizes) + ready PNGs. Use for «сделай карусель», «сторис».
---

<!-- Губка Спанч / GRIN — © 2026 Ernest Grin (GRIN studio). Licensed to the buyer for personal use; resale prohibited. -->

# Дизайнер

The engine does the typography and photos and writes the slides as ready-made files. You only write a short `slides.json` and send files: never write or read the slides' HTML yourself. No CapCut here: CapCut is only for video. Save the person's limits: one command, look at ONE small sheet once, reply in 2-3 lines.

## 1. Taste first
Use, in this order: a `taste_*.json` in the connected `Вкус/` folder or one they send → their words («тёмное, строго, жёлтый акцент») → a preset. Have none and the job matters (a series, a brand)? Offer once: «Пришли 5-10 референсов, и я запомню твой вкус» (that's the `gubka-learn` skill). Otherwise don't block: pick a preset and go.
Presets: `clean` (светлый, рыжий акцент), `night` (чёрный, лаймовый), `editorial` (журнал, антиква), `soft` (беж, мягкий), `bold` (тёмно-зелёный, жёлтый, капс).

## 2. Words
Their text → use it, only split it into slides. No text → write it by the `scenarist-hook-doctor` rules (slide 1 hook, one idea per slide, title ≤ 7 words, body ≤ 25 words, last slide = action, no канцелярит, no long dashes). Mark 1-2 key words per slide with `*звёздочки*` → accent colour.

## 3. slides.json
```json
{"format": "carousel", "name": "Короткое имя",
 "theme": {"preset": "clean", "handle": "@ник", "align": "left", "uppercase": false,
           "title_font": "Manrope Bold", "body_font": "Manrope Medium", "bg": "#F3F1EC", "ink": "#141413", "accent": "#E8462F"},
 "slides": [
  {"layout": "cover", "kicker": "тема", "title": "Хук с *акцентом*", "body": "подзаголовок", "photo": "/abs/photo.jpg"},
  {"layout": "text", "kicker": "", "title": "", "body": ""},
  {"layout": "list", "title": "", "items": ["", "", ""]},
  {"layout": "number", "big": "+18%", "title": "", "body": ""},
  {"layout": "quote", "title": "цитата", "author": "кто"},
  {"layout": "photo", "photo": "/abs/x.jpg", "focus": "top|center|bottom", "title": "", "body": ""},
  {"layout": "end", "title": "Сохрани, чтобы не потерять", "body": "", "cta": "Написать в директ"}]}
```
`format`: `carousel` 1080×1350 (default), `story` 1080×1920 (text kept out of the top/bottom UI), `square` 1080×1080. Theme keys are optional (only what overrides the taste/preset). Mix layouts: no three `text` slides in a row. Photos only from the person's files (cover photos get a dark gradient for white text).

## 4. Build
```bash
[ -d grin ] || { mkdir -p grin && tar xzf <this skill's folder>/engine.tar.gz -C grin; }
pip install --break-system-packages -q numpy Pillow fonttools
cd grin && python -m autocut design ../slides.json --out ../design [--taste /abs/taste_x.json] [--canvas <canvas folder>]
```
It prints JSON: `slides` (PNGs), `sheet`, `editor` (an HTML file), `warnings`, and with `--canvas` a `canvas` block. Fix every warning (shorten the text, cut a list item) and run again (1 s). Look at `sheet` ONCE: nothing cut off, accents on the right words.

## 5. Deliver: on the Design canvas, so they edit by hand
**Your Artifact tool offers a Design type** (check its type list once): 
1. Create ONE canvas from the Design type, title = the carousel's name. Its instructions arrive with it: from them you only need where the canvas's files must live (`<canvas folder>`, the folder holding `project/`) and how to send files and upload assets. Don't read the type's reference files, don't verify, don't render.
2. Run the build with `--canvas <canvas folder>`. It writes `project/canvas.json` and one artboard per slide (`Main.dc.html`, `Slide-02.dc.html`…): every text is its own element, so on the canvas they drag it, retype it and change font, size and colour by hand.
3. Upload every file in `canvas.upload_first` as an asset (one call). Then `python -m autocut canvas-fill <canvas folder> slide_01.png=<its url> slide_03.png=<url> …`.
4. Send `project/canvas.json` + `project/Main.dc.html`, then all other artboards in one more send. Never send anything outside `project/`.
5. Reply: «Карусель на холсте: двигай тексты мышкой, шрифт, размер и цвет справа в панели. Скачать: Share → Export. Готовые PNG тоже прикладываю.» and send the PNGs.
Later wishes in words («на 3 слайде другой заголовок») → follow the canvas type's «Revising» rules on that one artboard.

**No Design type** (or it refuses): send the PNGs + the `editor` HTML file with SendUserFile: «Открой редактор: тексты двигаются мышкой, шрифт, размер, цвет меняются справа, кнопка «Скачать» сохраняет PNG».

Either way: one offer («Поменять что-то? Можно руками или просто напиши») and once «Перепиши тексты своими словами, если звучит не как ты.»
Folder «Монтаж Claude» connected: also put the PNGs into `Готовое/` (run with `--out "$HOME/mnt/<folder>/Готовое"` via `device_bash`).
