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


def trim_words(words: list[dict], trims: list[str]) -> list[dict]:
    """--trim "[Но] пока что" / "вот [этот] весь": remove only the bracketed words, only where the
    whole phrase is said (first match). The next kept word gets cut=True, so the voice is cut there."""
    words = [dict(w) for w in words]
    for spec in trims:
        toks = re.findall(r"\[[^\]]+\]|[^\s\[\]]+", spec)
        ctx, drop = [], []
        for t in toks:
            if t.startswith("["):
                for x in t[1:-1].split():
                    if _norm(x):
                        ctx.append(_norm(x)); drop.append(True)
            elif _norm(t):
                ctx.append(_norm(t)); drop.append(False)
        if not ctx or not any(drop):
            continue
        norm = [_norm(w["text"]) for w in words]
        for i in range(len(words) - len(ctx) + 1):
            if all(norm[i + j] == ctx[j] for j in range(len(ctx))):
                rm = [i + j for j in range(len(ctx)) if drop[j]]
                after = max(rm) + 1
                if after < len(words):
                    words[after]["cut"] = True
                    first = min(rm)  # a removed sentence start: the next word starts the sentence
                    if first == 0 or END.search(words[first - 1]["text"].strip()):
                        words[after]["text"] = words[after]["text"][:1].upper() + words[after]["text"][1:]
                if rm and END.search(words[max(rm)]["text"].strip()) and min(rm) > 0:
                    words[min(rm) - 1]["text"] = words[min(rm) - 1]["text"].rstrip(",;:") + "."
                for k in sorted(rm, reverse=True):
                    del words[k]
                break
    return words


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
            txt = " ".join(w["text"] + ("(?)" if w.get("prob", 1) < 0.45 else "")
                           for w, x in zip(s, ts) if x is not None).replace(" -", "-")
            kw = [(w, x) for w, x in zip(s, ts) if x is not None]
            end = kw[-1][1] + (kw[-1][0]["end"] - kw[-1][0]["start"]) / 2
            kept.append((min(x for x in ts if x is not None), txt, end, s[0]))
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
    # length vs target (and speed), so cuts can be chosen in ONE re-plan
    sp = float(spec.get("speed") or 1.0)
    dur = spec["duration"] / sp
    tgt = args.get("target")
    head = f"Сейчас {dur:.0f} с" + (f" (с ускорением ×{sp:g})" if sp != 1 else "")
    if tgt:
        over = dur - tgt
        head += (f", цель {tgt:.0f} с: убрать ещё ~{over:.0f} с" if over > 2 else f", цель {tgt:.0f} с: укладываемся")
        if over > 2 and sp == 1:
            head += f" (или ускорить: ×1.1 даст {dur / 1.1:.0f} с)"
    lines.append(head + ".")
    # a kept sentence that leans on a removed one («Но…», «Это…», «Не знаю, но…») breaks the logic
    raw_sents = sentences(raw_words)
    kept_word_starts = set()
    for sx in sentences(words):
        for w in sx:
            if out_time(w) is not None:
                kept_word_starts.add(round(w["start"], 2))
    LEAN = {"но", "а", "и", "это", "этот", "эта", "эти", "тогда", "поэтому", "потому", "ну", "вот", "так",
            "значит", "тоже", "также", "причем", "кстати", "однако", "dar", "si", "deci", "asta", "but", "and",
            "so", "this", "that", "then", "конечно", "соответственно", "видите", "потом", "затем", "еще", "кроме",
            "тем", "именно", "причем", "зато", "поэтому", "отсюда"}

    def leans(w0: dict, txt: str) -> tuple[str, str] | None:
        """(first words, the removed sentence it leans on) or None."""
        first = _norm(txt).split()[:2]
        if not first:
            return None
        lower_start = txt.strip()[:1].islower()  # a sentence fragment: its start was cut away
        if not (first[0] in LEAN or first == ["не", "знаю"] or lower_start):
            return None
        r = next((k for k, rs in enumerate(raw_sents) if any(abs(x["start"] - w0["start"]) < 0.02 for x in rs)), None)
        if r is None or r == 0:
            return None
        prev_kept = any(round(x["start"], 2) in kept_word_starts for x in raw_sents[r - 1])
        if prev_kept:
            return None
        prev = " ".join(x["text"] for x in raw_sents[r - 1]).split()
        k = r - 2  # a very short removed sentence («Не знаю.») says little: add the one before it
        while len(prev) < 6 and k >= 0 and not any(round(x["start"], 2) in kept_word_starts for x in raw_sents[k]):
            prev = " ".join(x["text"] for x in raw_sents[k]).split() + prev
            k -= 1
        prev_txt = ("… " if len(prev) > 12 else "") + " ".join(prev[-12:])
        return " ".join(txt.split()[:2]).strip(",."), prev_txt
    lines.append("Остаётся (слово(?) = модель не уверена; ⚠ = опирается на убранную фразу):")
    for i, (t0, txt, t1, w0) in enumerate(kept, 1):
        nxt = kept[i][0] if i < len(kept) else spec["duration"]
        here = [b for b in ins if t0 - 0.05 <= b["start"] < nxt]
        tag = "".join(f"  [вставка {Path(spec['sources'][b['src']]).name} {b['dur']:.0f} с]" for b in here)
        lean = leans(w0, txt)
        warn = f"  ⚠ начинается с «{lean[0]}», а опирается на убранную фразу: «{lean[1]}»" if lean else ""
        lines.append(f"{i}. {t0 / sp:4.1f} с ({max(0.3, t1 - t0) / sp:.1f} с)  {txt}{tag}{warn}")
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
