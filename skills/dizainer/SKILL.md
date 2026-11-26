---
name: dizainer
description: Дизайнер. Carousels (up to 10 slides), posts and stories in the creator's taste: ready PNGs + a CapCut project with every text, font and colour editable. Use for «сделай карусель», «сторис».
---

<!-- Губка Спанч / GRIN — © 2026 Ernest Grin (GRIN studio). Licensed to the buyer for personal use; resale prohibited. -->

# Дизайнер

The engine does the typography, photos and the CapCut project. You only write a short `slides.json`. Save the person's limits: one command, look at ONE small sheet once, reply in 2-3 lines.

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
[ -d grin ] || cp -r <this skill's folder>/engine ./grin
pip install --break-system-packages -q numpy Pillow
cd grin && python -m autocut design ../slides.json --out ../design --no-capcut [--taste /abs/taste_x.json]
```
It prints JSON: `slides` (PNGs), `sheet`, `warnings`. Fix every warning (shorten the text, cut a list item) and run again. Look at `sheet` ONCE: nothing cut off, accents on the right words, slides not all alike. Fix in slides.json, re-run (1 s).
Edits are made here in the chat: change slides.json and re-run. A CapCut project only when the person asks for it AND their Mac folder is connected (CapCut needs real paths on their disk): run the same on the computer with `device_bash` in `$HOME/grin` (see the montage skill's reference.md I) without `--no-capcut`, with `--out "$HOME/mnt/<folder>/Готовое" --capcut-root "$HOME/mnt/CapCut/User Data/Projects/com.lveditor.draft" --map "$HOME/mnt/<folder>=<real path>" --map "$HOME/mnt/CapCut=<real path>"`. There every text is its own CapCut layer; restart CapCut to see it.

## 5. Deliver
Send the PNGs with SendUserFile (folder mode: just say where). Then: «Готово: N слайдов, можно выкладывать». One offer: «Поменять шрифт, цвет или текст на каком-то слайде? Просто напиши». Remind once: «Перепиши тексты своими словами, если звучит не как ты.»
