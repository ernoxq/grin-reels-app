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
    raw_words = words
    if (job / "words_edit.json").exists():
        words = json.loads((job / "words_edit.json").read_text())
    parts = json.loads((job / "story_parts.json").read_text()) if (job / "story_parts.json").exists() else []
    off = {f"A{i + 1}": p["start"] for i, p in enumerate(parts)}
    segs, t = [], 0.0
    for v in spec["voice"]:  # back to the common timeline of the recognised words
        a = v["in"] + off.get(v["src"], 0.0)
        segs.append((a, a + v["dur"], t)); t += v["dur"]

    def out_time(w: dict):
        mid = (w["start"] + w["end"]) / 2
        for a, b, o in segs:
            if a <= mid <= b:
                return o + (mid - a)
        return None

    raw = (raw_words[-1]["end"] - raw_words[0]["start"]) if raw_words else 0
    lines = [f"Длина: {spec['duration']:.0f} с (сырое видео {raw:.0f} с). Язык: {spec.get('lang', '?')}."]
    if spec.get("title", {}).get("lines"):
        lines.append(f"Заголовок: «{' '.join(spec['title']['lines'])}»")
    ins = sorted(spec.get("broll", []), key=lambda b: b["start"])
    kept, cut = [], []
    for s in sentences(words):
        ts = [out_time(w) for w in s]
        txt = " ".join(w["text"] for w in s)
        if any(x is not None for x in ts):
            txt = " ".join(w["text"] for w, x in zip(s, ts) if x is not None).replace(" -", "-")
            kept.append((min(x for x in ts if x is not None), txt))
        else:
            cut.append(txt)
    args = json.loads((job / "auto_args.json").read_text()) if (job / "auto_args.json").exists() else {}
    if args.get("script") and Path(args["script"]).exists():  # the person's own text: show it, spelling is theirs
        lines.append("Остаётся (по твоему тексту, лучшие дубли):")
        lines += [f"{i}. {l.strip()}" for i, l in enumerate(
            [l for l in Path(args["script"]).read_text(encoding="utf-8").splitlines() if l.strip()], 1)]
        if spec.get("broll"):
            lines.append("Вставки: " + ", ".join(f"{Path(spec['sources'][b['src']]).name} на {b['start']:.0f} с"
                                                 for b in sorted(spec["broll"], key=lambda b: b["start"])))
        return "\n".join(lines)
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
    unused = [Path(p).name for k, p in spec["sources"].items() if not k.startswith("A") and k not in used]
    if unused:
        lines.append("Не вошли: " + ", ".join(unused))
    if spec.get("sticker", {}).get("asset"):
        lines.append(f"Конец: кнопка на {spec['sticker']['start']:.1f} с")
    return "\n".join(lines)


def fix_words(words: list[dict], fixes: list[str]) -> list[dict]:
    """--fix "wrong=right": one or several words ("получаешь от=не получаешь от", "Бавла Стадия=Bible Study").
    Timing is kept: the right text takes the time of the wrong words."""
    pairs = []
    for f in fixes:
        if "=" in f:
            a, b = f.split("=", 1)
            toks = [_norm(t) for t in a.split() if _norm(t)]
            if toks:
                pairs.append((toks, b.strip()))
    out, i = [], 0
    while i < len(words):
        done = False
        for toks, b in pairs:
            n = len(toks)
            if [_norm(w["text"]) for w in words[i:i + n]] == toks:
                last = words[i + n - 1]["text"]
                tail = last[len(last.rstrip(".,!?:;…")):]
                b2 = b[:1].upper() + b[1:] if words[i]["text"][:1].isupper() else b
                parts = (b2 + tail).split()
                t0, t1 = words[i]["start"], words[i + n - 1]["end"]
                tot = sum(len(x) for x in parts) or 1
                acc = t0
                for x in parts:
                    d = (t1 - t0) * len(x) / tot
                    out.append(dict(words[i], text=x, start=round(acc, 3), end=round(acc + d, 3)))
                    acc += d
                i += n; done = True
                break
        if not done:
            out.append(words[i]); i += 1
    return out
