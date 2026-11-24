# GRIN Reels — talking head + B-roll, no reference needed

© 2026 Ernest Grin (GRIN studio). See LICENSE.md.

**Easiest:** double-click `Запустить GRIN Reels` (Mac `.command`, Windows `.bat`) → a page opens: drop your video, drop shots/photos, press «Собрать рилс». Own fonts/music/stickers/LUTs: tab «Мои файлы».

One command turns a raw talking-head take plus B-roll clips into a finished reel and an
editable CapCut draft. A local LLM or API isn't needed at runtime. Every creative decision lives in a
**style file** (`styles/*.json`) learned once from a hand-made edit.

```bash
python -m autocut reel take.MOV b1.MOV b2.MOV b3.MOV b4.MOV b5.MOV \
    --style styles/warm_intro.json \
    --script script.txt          # optional: one sentence per line -> best takes + exact spelling
    --capcut my_reel             # optional: also write a CapCut desktop draft
# -> jobs/take/spec.json, jobs/take/final.mp4  (+ CapCut draft), prints a 1-line JSON summary
```
**No Mac?** Windows: `install.ps1` (beta). iPhone only: run in a Claude cloud session with `--lite --script script.txt` (no speech model; one clean take; captions aligned by pauses).

Fix anything by hand in `jobs/take/spec.json` (caption text, a B-roll in-point) and run
`python -m autocut render jobs/take/spec.json --capcut my_reel`. That takes seconds, with no ASR re-run.

## Pipeline (autoreel.py -> reel.py)

| Step | What happens | Tunable in style |
|---|---|---|
| ASR | faster-whisper word timestamps, cached `words.json` (`large-v3-turbo`, falls back to `small`) | `asr` |
| Takes | with script: last take that matches each line (fuzzy, word windows); without: drop phrases repeated later | `phrase_gap` |
| Cuts | runs of kept phrases; pauses > `max_pause` removed; pads 80/140 ms | `cut` |
| Captions | 2–6 words, break at commas/pauses, no dangling «и/в/на/то», break before «и/а/но» if 3+ words follow, 2 balanced lines when > 16 chars, lowercase except proper nouns | `caption_rules`, `caption_style` |
| Title | first sentence, UPPERCASE, 2 lines, line 2 accent colour + blur-in | `title.template` |
| B-roll | after the title, clauses alternate face/B-roll inside 8–68 % of the runtime; clause ≥ 3 s → beat montage (2 beats @ BPM), colour/B&W alternating, 0.8× for 50/60 fps clips; medium clips use their middle | `broll_rules` |
| Look | A-roll zoom 1.105 + up 0.118, A-roll LUT, B-roll LUT / B&W LUT, bottom shadow gradient | `aroll_look`, `broll_look`, `shadow` |
| Exposure | A-roll brightness normalised to the LUT's training brightness (×0.7–1.45) | `aroll_look.input_luma` |
| End | CTA sticker pops on the last sentence, 0.5 s fade to black | `sticker`, `fade_out` |
| Music | bed at −12 dB under voice, looped, faded | `music` (`asset`, `gain_db`, `bpm`) |

## How the warm_intro style was built
Learned from one hand-made reference edit by measuring it (not guessing): best-take selection, J/L cuts under B-roll,
beat montage every 2 beats at 120 BPM, colour/B&W alternation, fitted LUTs + bottom shadow, title/caption typography,
CTA pop and fade. The rebuilt edit matched the reference at 5.4/255 mean frame difference.

## Libraries (bring your own)
- `library/fonts/`: put the real fonts here (`.ttf/.otf`). On Mac also install them (double-click), so CapCut sees them. Style refers by file + family name.
- `library/luts/`: any `.cube`. The three fitted LUTs are importable into CapCut too (Adjust → LUT → Import).
- `library/overlays/`, `library/stickers/cta/`, `library/music/`.

**New style without a reference:** copy `styles/warm_intro.json` and change fonts, colours,
LUT ids, BPM, B-roll window, sticker. **New style from a reference:** see the skill
`reel-style-from-reference` (same measurements as above, scripted in `autocut/compare.py`
and the steps listed there).

## Check quality objectively
`python -m autocut.compare reference.mov jobs/x/final.mp4 --sheet sbs.jpg`. Mean < 8 means the same look.
