# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
# Licensed, not sold: see LICENSE.md. Redistribution or resale is prohibited.
"""Антикринж: measure a finished reel so Claude can judge it cheaply.

One command -> a short JSON (pace, first 3 seconds, pauses, dead air, loudness,
transcript by phrases with times, risk flags) + ONE contact sheet with times.
Claude reads the JSON and looks at the sheet once; it never watches the video.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from .reflearn import _cuts, _dur, _frame


def _lufs(p: Path) -> float | None:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(p), "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    return float(m[-1]) if m else None


def _phrases(words, gap: float = 0.55, max_words: int = 14) -> list[dict]:
    out, cur = [], []
    for w in words:
        if cur and (w.start - cur[-1].end > gap or len(cur) >= max_words):
            out.append(cur)
            cur = []
        cur.append(w)
    if cur:
        out.append(cur)
    return [{"t": round(p[0].start, 1), "end": round(p[-1].end, 1), "text": " ".join(w.text for w in p)} for p in out]


def review(reel: Path, out: Path, speech: bool = True, lang: str | None = None) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    dur = _dur(reel)
    cuts = [round(c, 2) for c in _cuts(reel) if 0.1 < c < dur - 0.1]
    bounds = [0.0] + cuts + [dur]
    shots = [round(b - a, 2) for a, b in zip(bounds, bounds[1:])]
    r: dict = {"file": reel.name, "sec": round(dur, 1), "cuts": len(cuts),
               "avg_shot": round(dur / max(1, len(shots)), 2), "longest_shot": max(shots) if shots else dur,
               "cuts_first_3s": sum(1 for c in cuts if c < 3), "first_cut": cuts[0] if cuts else None,
               "lufs": _lufs(reel)}
    flags = []
    if speech:
        from .fetch_model import fetch
        from .transcribe import transcribe
        try:
            words = transcribe(str(reel), out / "words.json", str(fetch()), lang)
        except Exception as e:  # no model / no network: still useful without speech
            words, r["speech_error"] = [], str(e)[:120]
        if words:
            talk = sum(w.end - w.start for w in words)
            r["speech_starts"] = round(words[0].start, 2)
            r["words"] = len(words)
            r["words_per_sec"] = round(len(words) / max(1.0, words[-1].end - words[0].start), 2)
            r["talk_share"] = round(talk / max(1.0, dur), 2)
            pauses = [(round(a.end, 1), round(b.start - a.end, 1)) for a, b in zip(words, words[1:]) if b.start - a.end > 0.8]
            r["pauses"] = [{"at": t, "sec": s} for t, s in sorted(pauses, key=lambda x: -x[1])[:6]]
            r["dead_air_end"] = round(dur - words[-1].end, 1)
            r["first_3s_words"] = " ".join(w.text for w in words if w.start < 3.0)
            r["transcript"] = _phrases(words)
            if words[0].start > 1.0:
                flags.append(f"речь начинается только на {words[0].start:.1f} с: первая секунда пустая")
            if r["words_per_sec"] < 1.9:
                flags.append("медленный темп речи: легко пролистать")
            if r["words_per_sec"] > 3.9:
                flags.append("очень быстрая речь: трудно успеть прочитать субтитры")
            for p in r["pauses"]:
                if p["sec"] >= 1.2:
                    flags.append(f"пауза {p['sec']} с на {p['at']} с: риск отвала")
            if r["dead_air_end"] > 1.5:
                flags.append(f"после последнего слова ещё {r['dead_air_end']} с: обрезать хвост")
    if (r["first_cut"] or dur) > 3.5 and dur > 8:
        flags.append("первая смена кадра позже 3,5 с: старт статичный")
    if r["longest_shot"] > 7 and dur > 12:
        flags.append(f"самый длинный кадр {r['longest_shot']} с без смены")
    if r["lufs"] is not None and r["lufs"] < -20:
        flags.append(f"звук тихий ({r['lufs']} LUFS, норма около -14)")
    r["flags"] = flags
    # one sheet: dense at the start (the hook), then even steps
    ts = [0.0, 0.7, 1.5, 2.5] + [3.5 + k * max(1.0, (dur - 4.5) / 7) for k in range(8)]
    ts = [min(t, max(0.0, dur - 0.3)) for t in ts if t < dur]
    tiles = [_frame(reel, t, 180) for t in ts]
    th = tiles[0].height
    cols = 6
    sheet = Image.new("RGB", (cols * 180, ((len(tiles) + cols - 1) // cols) * (th + 16)), "white")
    d = ImageDraw.Draw(sheet)
    for i, (t, im) in enumerate(zip(ts, tiles)):
        x, y = (i % cols) * 180, (i // cols) * (th + 16)
        sheet.paste(im, (x, y + 16))
        d.text((x + 4, y + 2), f"{t:.1f}s", fill="black")
    sheet.save(out / "sheet.png")
    r["sheet"] = str(out / "sheet.png")
    (out / "review.json").write_text(json.dumps(r, ensure_ascii=False, indent=1))
    return r
