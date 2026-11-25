# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
"""Storyboard: a short text plan of the reel BEFORE rendering, and edits to it in plain words.

The person reads the plan, says what to change («убери фразу про…», «другой заголовок»,
«вставку на слова про кофе»), Claude applies it with flags/commands, and only then renders.
Costs a few hundred tokens instead of rendering and re-rendering video.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

END = re.compile(r"[.!?…]$")


def _norm(s: str) -> str:
    return re.sub(r"[^\w\s]", "", s.lower()).replace("ё", "е").strip()


def sentences(words: list[dict]) -> list[list[dict]]:
    out, cur = [], []
    for w in words:
        cur.append(w)
        if END.search(w["text"].strip()):
            out.append(cur); cur = []
    if cur:
        out.append(cur)
    return out


def drop_phrases(words: list[dict], phrases: list[str]) -> list[dict]:
    """Remove every sentence that contains one of the phrases (approximate, case/punctuation-insensitive)."""
    keys = [_norm(p) for p in phrases if p.strip()]
    keep = []
    for s in sentences(words):
        text = _norm(" ".join(w["text"] for w in s))
        if not any(k and k in text for k in keys):
            keep += s
    return keep


def plan_text(job: Path) -> str:
    spec = json.loads((job / "spec.json").read_text())
    words = json.loads((job / "words.json").read_text())
    if (job / "words_edit.json").exists():
        words = json.loads((job / "words_edit.json").read_text())
    segs, t = [], 0.0
    for v in spec["voice"]:
        segs.append((v["in"], v["in"] + v["dur"], t)); t += v["dur"]

    def out_time(w: dict):
        mid = (w["start"] + w["end"]) / 2
        for a, b, o in segs:
            if a <= mid <= b:
                return o + (mid - a)
        return None

    raw = (words[-1]["end"] - words[0]["start"]) if words else 0
    lines = [f"Длина: {spec['duration']:.0f} с (сырое видео {raw:.0f} с). Язык: {spec.get('lang', '?')}."]
    if spec.get("title", {}).get("lines"):
        lines.append(f"Заголовок: «{' '.join(spec['title']['lines'])}»")
    ins = sorted(spec.get("broll", []), key=lambda b: b["start"])
    kept, cut = [], []
    for s in sentences(words):
        ts = [out_time(w) for w in s]
        txt = " ".join(w["text"] for w in s)
        if any(x is not None for x in ts):
            txt = " ".join(w["text"] for w, x in zip(s, ts) if x is not None)
            kept.append((min(x for x in ts if x is not None), txt))
        else:
            cut.append(txt)
    lines.append("Остаётся:")
    for i, (t0, txt) in enumerate(kept, 1):
        nxt = kept[i][0] if i < len(kept) else spec["duration"]
        here = [b for b in ins if t0 - 0.05 <= b["start"] < nxt]
        tag = "".join(f"  [вставка {Path(spec['sources'][b['src']]).name} {b['dur']:.0f} с]" for b in here)
        lines.append(f"{i}. {t0:4.1f} с  {txt}{tag}")
    if cut:
        lines.append("Вырезано (повторы, оговорки):")
        lines += [f"- {c[:90]}" for c in cut]
    used = {b["src"] for b in ins}
    unused = [Path(p).name for k, p in spec["sources"].items() if k != "A" and k not in used]
    if unused:
        lines.append("Не вошли: " + ", ".join(unused))
    if spec.get("sticker", {}).get("asset"):
        lines.append(f"Конец: кнопка на {spec['sticker']['start']:.1f} с")
    return "\n".join(lines)
