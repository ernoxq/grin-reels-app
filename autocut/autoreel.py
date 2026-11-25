# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
# Licensed, not sold: see LICENSE.md. Redistribution or resale is prohibited.
"""Auto-planner: raw talking-head take + B-roll clips + style  ->  reel spec (JSON).

Zero LLM tokens. Every decision is a rule learned from a reference edit (styles/*.json):

1. ASR words (faster-whisper, cached) -> phrases split on pauses / punctuation.
2. Take selection: people re-record lines. With script.txt we keep the LAST take that matches
   each script line; without it we drop any phrase that is repeated later (= failed take).
3. Voice segments = runs of kept phrases; long pauses tightened to `max_pause`.
4. Captions: phrase chunks (<= 2 lines, <= N chars/line), lowercase, no punctuation.
   Title = first sentence in UPPERCASE, split over 2 lines, line 2 accent colour.
5. B-roll: sentences alternate A / B inside the middle window of the video
   (never on the title, never on the CTA). Long B sentences become a montage cut on the
   beat grid (2 beats @ style BPM), alternating colour / B&W, slow-mo for 50/60 fps clips.
6. CTA sticker on the last sentence, bottom shadow, zoom/LUTs, fade-out, music bed.
"""
from __future__ import annotations

from .paths import app_root
import difflib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from .media import probe
from .transcribe import Word


# ------------------------------------------------------------------ phrases & takes
@dataclass
class Phrase:
    words: list[Word]

    @property
    def start(self) -> float:
        return self.words[0].start

    @property
    def end(self) -> float:
        return self.words[-1].end

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def norm(self) -> str:
        return _norm(self.text)


def _norm(s: str) -> str:
    return re.sub(r"[^\w ]+", "", s.lower().replace("ё", "е")).strip()


def split_phrases(words: list[Word], gap: float = 0.45) -> list[Phrase]:
    out, cur = [], []
    for w in words:
        if cur and (w.start - cur[-1].end > gap or cur[-1].text.endswith((".", "!", "?"))):
            out.append(Phrase(cur))
            cur = []
        cur.append(w)
    if cur:
        out.append(Phrase(cur))
    return out


def _sim(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def select_takes(phrases: list[Phrase], script: list[str] | None = None, thr: float = 0.72) -> list[Phrase]:
    """Return the phrases to keep, in final order."""
    if script:
        words = [w for p in phrases for w in p.words]
        keep = []
        for line in script:
            target, n = _norm(line), len(line.split())
            best = None
            for i in range(len(words)):  # sliding word windows of length n-2 .. n+2
                for L in range(max(1, n - 2), n + 3):
                    if i + L > len(words):
                        break
                    cand = Phrase(words[i:i + L])
                    s = _sim(cand.norm, target)
                    if s < thr:
                        continue
                    later = best is not None and cand.start > best[1].end - 0.05
                    same = best is not None and not later and cand.start >= best[1].start - 0.05
                    if best is None or (later and s > best[0] - 0.12) or (same and s > best[0]) or s > best[0] + 0.15:
                        best = (s, cand)  # a LATER take wins unless clearly worse
            if best:
                keep.append(respell(best[1], line))
        return keep
    # no script: drop failed takes, false starts and mumbled fragments; the LAST good take wins
    def content(p: Phrase) -> set[str]:
        return {w for w in p.norm.split() if len(w) >= 4}

    def junk(p: Phrase) -> bool:
        n = len(p.words)
        prob = sum(w.prob for w in p.words) / max(1, n)
        last = p.words[-1].text.strip() if p.words else ""
        trails = last.endswith(("...", "…", "-", "—"))
        return (prob < 0.45
                or (n <= 3 and (prob < 0.7 or last.endswith("?") or trails))
                or (trails and n <= 7))

    keep = []
    for i, p in enumerate(phrases):
        head = p.norm[: max(12, int(len(p.norm) * 0.6))]
        nxt = phrases[i + 1:i + 6]
        restart = [q for q in nxt if _sim(head, q.norm[: len(head)]) > 0.75]
        cp = content(p)
        retold = [q for q in nxt if len(cp) >= 3 and len(cp & content(q)) >= 0.5 * len(cp)]
        if restart or retold or junk(p):
            continue
        keep.append(p)
    return keep


def respell(p: Phrase, line: str) -> Phrase:
    """Replace ASR spelling with the script's words, keeping ASR timing (CapCut-grade captions)."""
    toks = line.split()
    a, b = [_norm(w.text) for w in p.words], [_norm(t) for t in toks]
    out: list[Word] = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if op == "equal":
            out += [Word(toks[j1 + k], p.words[i1 + k].start, p.words[i1 + k].end, p.words[i1 + k].prob)
                    for k in range(i2 - i1)]
        elif op in ("replace", "insert") and j2 > j1:
            s0 = p.words[i1].start if i1 < len(p.words) else p.words[-1].end
            e0 = p.words[i2 - 1].end if i2 > i1 else s0 + 0.15 * (j2 - j1)
            step = (e0 - s0) / (j2 - j1)
            out += [Word(toks[j1 + k], s0 + k * step, s0 + (k + 1) * step, 0.9) for k in range(j2 - j1)]
    return Phrase(out or p.words)


def voice_segments(kept: list[Phrase], src_key: str, pad_in=0.08, pad_out=0.14, max_pause=0.55,
                   tight_pause=0.18) -> tuple[list[dict], list[tuple[float, float, float]]]:
    """Returns spec voice segments + a source->output time map [(src_in, src_out, out_start)]."""
    segs, mp, t = [], [], 0.0
    i = 0
    while i < len(kept):
        s0 = max(0.0, kept[i].start - pad_in)
        e0 = kept[i].end + pad_out
        j = i
        # extend run while next kept phrase directly follows in the source with a short pause
        while j + 1 < len(kept) and 0 <= kept[j + 1].start - kept[j].end <= max_pause:
            j += 1
            e0 = kept[j].end + pad_out
        segs.append({"src": src_key, "in": round(s0, 4), "dur": round(e0 - s0, 4)})
        mp.append((s0, e0, t))
        t += e0 - s0
        if j + 1 < len(kept) and kept[j + 1].start - kept[j].end > max_pause:
            pass  # next run starts a new segment (pause removed down to pads)
        i = j + 1
    # avoid overlap of consecutive segments from overlapping pads
    return segs, mp


def _map(t: float, mp) -> float | None:
    for s, e, o in mp:
        if s <= t <= e:
            return o + (t - s)
    return None


# ------------------------------------------------------------------ captions
WEAK = {"и", "в", "во", "на", "из", "к", "с", "со", "у", "о", "об", "по", "за", "от", "до", "то", "а", "но",
        "не", "что", "как", "для", "the", "a", "to", "of", "and", "in", "on", "si", "și", "în", "la", "de"}


def chunk_captions(kept: list[Phrase], mp, max_line=16, max_chars=34, max_words=6, min_dur=0.45) -> list[dict]:
    """Phrase captions like a human editor: 2-6 words, break at commas/pauses, never end a chunk
    on a dangling preposition/conjunction, wrap to 2 balanced lines when > max_line chars."""
    clean = lambda t: re.sub(r"[^\w\-]+", "", t).lower()
    caps, cur = [], []
    keep_case: set[int] = set()  # proper nouns (capitalised mid-sentence) keep their capital

    def flush():
        if not cur:
            return
        moved = []
        while len(cur) > 1 and clean(cur[-1].text) in WEAK:  # dangling 'и', 'в', 'то' -> next chunk
            moved.insert(0, cur.pop())
        toks = [re.sub(r"[^\w\-]+", "", w.text) if id(w) in keep_case else clean(w.text) for w in cur]
        text = " ".join(toks)
        words = [{"t": t, "s": round(_map(w.start, mp), 3), "e": round(_map(w.end, mp) or _map(w.start, mp), 3)}
                 for t, w in zip(toks, cur) if t]
        caps.append({"text": _wrap(text, max_line), "start": _map(cur[0].start, mp), "end": _map(cur[-1].end, mp),
                     "words": words})
        cur.clear()
        cur.extend(moved)

    for p in kept:
        ws = p.words
        for wi, w in enumerate(ws):
            if _map(w.start, mp) is None:
                continue
            prev = ws[wi - 1].text if wi else "."
            if w.text[:1].isupper() and not prev.endswith((".", "!", "?")):
                keep_case.add(id(w))
            trial = " ".join(clean(x.text) for x in cur + [w])
            ahead = 0  # words until the next punctuation mark
            for x in ws[wi:]:
                ahead += 1
                if x.text.endswith((",", ".", "!", "?", ";", ":")):
                    break
            conj = clean(w.text) in {"и", "а", "но", "and", "but", "și", "dar"} and len(cur) >= 3 and ahead >= 3
            if cur and (len(trial) > max_chars or len(cur) >= max_words or w.start - cur[-1].end > 0.3 or conj):
                flush()
            cur.append(w)
            if w.text.endswith((",", ".", "!", "?", ";", ":")):
                flush()
        flush()
    for a, b in zip(caps, caps[1:]):  # captions hold until the next one (no flicker)
        a["end"] = b["start"] if b["start"] - a["end"] < 0.35 else a["end"] + 0.15
    for c in caps:
        c["end"] = max(c["end"], c["start"] + min_dur)
        c["start"], c["end"] = round(c["start"], 3), round(c["end"], 3)
    return caps


def _wrap(text: str, max_line: int) -> str:
    if len(text) <= max_line:
        return text
    words = text.split()
    best, best_cost = text, 1e9
    for k in range(1, len(words)):  # balanced 2-line split
        a, b = " ".join(words[:k]), " ".join(words[k:])
        cost = abs(len(a) - len(b)) + (100 if max(len(a), len(b)) > max_line else 0)
        if cost < best_cost:
            best, best_cost = f"{a}\n{b}", cost
    return best


# ------------------------------------------------------------------ B-roll
def plan_broll(sentences: list[tuple[float, float]], clips: list[dict], style: dict, total: float) -> list[dict]:
    """Inserts go on every other sentence, never on the first (title) or the last (end button) one.
    With fewer clips than slots they are spread evenly over the whole video, not bunched at the start."""
    r = style["broll_rules"]
    lo, hi = r.get("window", [0.06, 0.95])
    beat = r.get("cut_len") or 60.0 / style.get("music", {}).get("bpm", 120) * r.get("beats_per_cut", 2)
    last = sentences[-1][0] if len(sentences) > 2 else total
    slots = [(s, e) for k, (s, e) in enumerate(sentences)
             if 0 < k < len(sentences) - 1 and k % 2 == 1 and s >= lo * total and e <= min(hi * total, last)
             and e - s >= r.get("min_insert", 1.5)]
    if not clips or not slots:
        return []
    if len(clips) < len(slots):  # spread evenly
        step = len(slots) / len(clips)
        slots = [slots[int(i * step + step / 2)] for i in range(len(clips))]
    out, ci = [], 0
    for s, e in slots:
        if ci >= len(clips):
            break
        span = e - s
        left = len(clips) - ci
        if span < r.get("montage_min", 3.0) or left < 2:  # single insert (long sentence: first part only)
            c = clips[ci]; ci += 1
            out.append(_ins(c, s, min(span, r.get("max_insert", 4.0)), 1.0, "color", r))
        else:  # montage on the beat grid, but leave clips for the slots still ahead
            ahead = len([x for x in slots if x[0] > s])
            n = max(1, min(int(span // beat), left - ahead))
            t, looks = s, r.get("looks", ["color", "bw"])
            for m in range(n):
                d = beat if m < n - 1 else min(e - t, r.get("max_insert", 4.0))
                c = clips[ci]; ci += 1
                sp = r.get("slowmo", 0.8) if c["fps"] >= 50 else 1.0
                out.append(_ins(c, t, d, sp, looks[m % 2], r))
                t += d
    return out


IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic"}


def _ins(c: dict, start: float, dur: float, speed: float, look: str, r: dict) -> dict:
    if c.get("image"):
        return {"src": c["key"], "in": 0.0, "start": round(start, 3), "dur": round(dur, 3), "speed": 1.0,
                "look": look, "image": True}
    need = dur * speed
    if c["dur"] - need > r.get("center_if_longer", 3.0) and c["dur"] < 10:
        src_in = (c["dur"] - need) / 2  # middle of medium clips (the "moment"), start of long ones
    else:
        src_in = 0.0
    src_in = max(0.0, min(src_in, c["dur"] - need - 0.02))
    if need > c["dur"]:  # clip too short: slow it down to fit instead of freezing
        speed = max(0.5, (c["dur"] - 0.02) / dur)
    return {"src": c["key"], "in": round(src_in, 3), "start": round(start, 3), "dur": round(dur, 3),
            "speed": round(speed, 3), "look": look}


# ------------------------------------------------------------------ main
def plan(aroll: Path, broll: list[Path], style: dict, words: list[Word], script: list[str] | None = None,
         title: str | None = None) -> dict:
    phrases = split_phrases(words, style.get("phrase_gap", 0.45))
    kept = select_takes(phrases, script)
    voice, mp = voice_segments(kept, "A", **style.get("cut", {}))
    total = sum(v["dur"] for v in voice)
    caps = chunk_captions(kept, mp, **style.get("caption_rules", {}))

    # sentences on the output timeline (for B-roll + CTA)
    clauses = []  # sentences split at commas too: B-roll alternates per clause
    for p in kept:
        cur = []
        for w in p.words:
            cur.append(w)
            if w.text.endswith((",", ".", "!", "?", ";")):
                clauses.append(Phrase(cur)); cur = []
        if cur:
            clauses.append(Phrase(cur))
    sents = [(_map(p.start, mp), _map(p.end, mp)) for p in clauses]
    sents = [(a, b) for a, b in sents if a is not None and b is not None]

    spec = {k: style[k] for k in ("canvas", "fonts", "aroll_look", "broll_look", "caption_style", "shadow", "safe_zone", "avoid_face") if k in style}
    spec["sources"] = {"A": str(aroll)}
    clips = []
    for i, b in enumerate(broll):
        key = f"B{i + 1}"
        spec["sources"][key] = str(b)
        if Path(b).suffix.lower() in IMAGE_EXT:  # photos work as B-roll: slow push-in, any length
            clips.append({"key": key, "dur": 60.0, "fps": 0, "image": True})
            continue
        info = probe(b)
        clips.append({"key": key, "dur": info.duration, "fps": info.fps})

    # exposure normalisation: bring new footage to the brightness the style's LUTs were fitted on
    from .media import median_luma
    if (target := style.get("aroll_look", {}).get("input_luma")):
        got = median_luma(str(aroll), voice[0]["in"], sum(v["dur"] for v in voice[:1]) or None)
        spec["aroll_look"] = dict(spec["aroll_look"], gain=round(min(1.45, max(0.7, target / max(got, 1))), 3))
    bt = style.get("broll_look", {}).get("input_luma")

    # title = first sentence
    ts = style.get("title")
    if ts and caps:
        first = caps[0]
        txt = (title or first["text"].replace("\n", " ")).upper().split()
        mid = max(1, len(txt) // 2)
        lines = [" ".join(txt[:mid]), " ".join(txt[mid:])] if len(txt) > 1 else txt
        spec["title"] = dict(ts["template"], lines=lines, start=0.0, end=round(first["end"], 3))
        caps = caps[1:]
    spec["captions"] = caps
    spec["voice"] = voice
    spec["duration"] = round(total, 3)
    spec["broll"] = plan_broll(sents, clips, style, total)
    if clips and not spec["broll"] and len(sents) >= 2:
        # short video: the person gave shots/photos, so show them on the middle sentences
        mids = sents[1:-1] if len(sents) >= 3 else sents[1:]
        ci, total_mid = 0, sum(b - a for a, b in mids) or 1
        for a, b in sorted(mids, key=lambda x: x[0]):
            share = round((len(clips) - ci) * (b - a) / total_mid) or 1  # clips for this sentence
            n = max(1, min(len(clips) - ci, share, int((b - a) / 0.5)))
            for k in range(n):
                d = (b - a) / n
                c = clips[ci]; ci += 1
                lk = style["broll_rules"].get("looks", ["color", "bw"])
                spec["broll"].append(_ins(c, a + k * d, d, 1.0, lk[len(spec["broll"]) % len(lk)],
                                          style["broll_rules"]))
            if ci >= len(clips):
                break
    if bt and style["broll_look"].get("normalize", False):  # softer for B-roll: keep each clip's own mood, only pull outliers in
        for b in spec["broll"]:
            got = median_luma(spec["sources"][b["src"]], b["in"], b["dur"] * b["speed"], n=3)
            b["gain"] = round(min(1.25, max(0.8, (bt / max(got, 1)) ** 0.5)), 3)

    if (st := style.get("sticker")) and caps:
        last_sent_start = sents[-1][0] if sents else caps[-1]["start"]
        spec["sticker"] = dict(st, start=round(max(last_sent_start, caps[-1]["start"]) - 0.03, 3),
                               end=spec["duration"])
    spec["fade_out"] = style.get("fade_out", 0.5)
    spec["music"] = style.get("music", {})
    return spec


def run(aroll: str, broll: list[str], style_path: str, out_dir: str, script: str | None = None,
        title: str | None = None, words_json: str | None = None, model: str | None = None,
        language: str | None = None, lite: bool = False) -> Path:
    from .transcribe import transcribe
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    style = json.loads(Path(style_path).read_text())
    refs = style.get("aroll_look", {}).get("lut_ref")
    if refs:  # style learned from a reference reel: build this video's LUT toward the reference colour
        from .lutmatch import build
        lib = app_root() / "library"
        nm = f"auto_{out.name}"
        build(Path(aroll), [lib / r for r in refs], lib / "luts/my" / f"{nm}.cube",
              strength=style["aroll_look"].get("lut_strength", 0.7))
        style["aroll_look"] = dict(style["aroll_look"], lut=f"luts/my/{nm}")
        style["broll_look"] = dict(style.get("broll_look", {}), color=f"luts/my/{nm}")
    if style.get("aroll_look", {}).get("wb") == "auto":  # white point: make whites white for this video
        from .grade import auto_white_point
        style["aroll_look"] = dict(style["aroll_look"], wb_gain=auto_white_point(str(aroll)))
    lines = [l.strip() for l in Path(script).read_text(encoding="utf-8").splitlines() if l.strip()] if script else None
    if words_json:
        words = [Word(**w) for w in json.loads(Path(words_json).read_text())]
    elif lite:
        if not lines:
            raise SystemExit("--lite needs --script (one clean take that follows the script)")
        from .transcribe import align_script
        words = align_script(aroll, lines)
        (out / "words.json").write_text(json.dumps([w.__dict__ for w in words], ensure_ascii=False))
    else:
        asr = style.get("asr", {})
        lang = language or asr.get("language")
        try:
            words = transcribe(aroll, out / "words.json", model or asr.get("model", "small"), lang)
        except Exception:  # no turbo model / model host unreachable -> small model from the GRIN GitHub release
            try:
                words = transcribe(aroll, out / "words.json", asr.get("fallback", "small"), lang)
            except Exception:
                from .fetch_model import fetch
                words = transcribe(aroll, out / "words.json", str(fetch()), lang)
    merged: list[Word] = []
    for w in words:  # Romanian/French clitics come split by ASR: "ne -a" -> "ne-a", "S -o" -> "S-o"
        if merged and w.text.startswith("-") and len(w.text) > 1 and w.start - merged[-1].end < 0.3:
            m = merged[-1]
            merged[-1] = Word(m.text + w.text, m.start, w.end, min(m.prob, w.prob))
        else:
            merged.append(w)
    words = merged
    spec = plan(Path(aroll).resolve(), [Path(b).resolve() for b in broll], style, words, lines, title)
    if (lf := out / "lang.txt").exists():
        spec["lang"] = lf.read_text().strip()
    p = out / "spec.json"
    p.write_text(json.dumps(spec, ensure_ascii=False, indent=1))
    return p
