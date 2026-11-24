# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
"""Put anything on top of a finished reel at the words where it belongs.

    python -m autocut place jobs/x/spec.json photo.jpg --words "про кофе"            # full screen insert
    python -m autocut place jobs/x/spec.json clip.mov  --words "моя работа" --how window   # small video window
    python -m autocut place jobs/x/spec.json --icon heart --color "#E4F23C" --words "люблю" # icon sticker
then: python -m autocut render jobs/x/spec.json

--anim: pop (default) | fade | slide | none
--how: full (covers the screen, like B-roll) | window (picture-in-picture) | sticker (small, pops in)
Where: --pos top|center|bottom|left|right|top-left|top-right (default: top for window/sticker, keeps the face/captions clear)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

IMG = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
POS = {"top": (0.0, 0.42), "center": (0.0, 0.0), "bottom": (0.0, -0.2), "left": (-0.45, 0.2), "right": (0.45, 0.2),
       "top-left": (-0.45, 0.45), "top-right": (0.45, 0.45)}


def _norm(w: str) -> str:
    return re.sub(r"[^\w]+", "", w.lower().replace("ё", "е"))


def find_words(spec: dict, words: str) -> tuple[float, float]:
    """Start/end time (in the reel) of the first place these words are spoken."""
    want = [_norm(w) for w in words.split() if _norm(w)]
    flat = [w for c in spec.get("captions", []) for w in (c.get("words") or [])]
    if not flat:  # older spec: caption-level timing
        for c in spec.get("captions", []):
            if all(x in _norm(c["text"]) or x in [_norm(t) for t in c["text"].split()] for x in want):
                return c["start"], c["end"]
        raise SystemExit(f"не нашёл слова «{words}» в субтитрах")
    toks = [_norm(w["t"]) for w in flat]
    for i in range(len(toks)):
        if all(i + j < len(toks) and (toks[i + j] == x or toks[i + j].startswith(x[:max(3, len(x) - 2)]))
               for j, x in enumerate(want)):
            return flat[i]["s"], flat[min(i + len(want), len(flat)) - 1]["e"]
    raise SystemExit(f"не нашёл слова «{words}» в субтитрах")


def place(spec_path: str, file: str | None, words: str | None, at: float | None, how: str = "full",
          dur: float | None = None, pos: str | None = None, width: float | None = None,
          icon: str | None = None, color: str = "#FFFFFF", bg: str | None = "#1E1E1D", label: str | None = None,
          anim: str = "pop") -> dict:
    sp = Path(spec_path)
    spec = json.loads(sp.read_text())
    if words:
        t0, t1 = find_words(spec, words)
    elif at is not None:
        t0, t1 = at, at + 1.5
    else:
        raise SystemExit("укажи --words или --at")
    d = dur or max(1.2, min(3.0, t1 - t0 + 0.6))
    d = min(d, spec["duration"] - t0 - 0.05)
    if icon or how in ("window", "sticker"):
        x, y = POS[pos or "top"]
        layer = {"start": round(t0, 3), "end": round(t0 + d, 3), "x": x, "y": y, "pop": 0.3, "anim": anim,
                 "width": width or (0.5 if how == "window" else 0.24)}
        if icon:
            layer["icon"] = {"name": icon, "color": color, "bg": bg, "label": label or "",
                             "shape": "pill" if label else "circle"}
            if label and not width:
                layer["width"] = 0.42
        else:
            layer["asset"] = str(Path(file).resolve())
        spec.setdefault("overlays", []).append(layer)
    else:  # full-screen insert, like B-roll (voice keeps running underneath)
        key = f"P{len(spec['sources']) + 1}"
        spec["sources"][key] = str(Path(file).resolve())
        item = {"src": key, "in": 0.0, "start": round(t0, 3), "dur": round(d, 3), "speed": 1.0, "look": "color"}
        if Path(file).suffix.lower() in IMG:
            item["image"] = True
        spec["broll"] = sorted([b for b in spec.get("broll", []) if b["start"] + b["dur"] <= t0 or b["start"] >= t0 + d]
                               + [item], key=lambda b: b["start"])
    sp.write_text(json.dumps(spec, ensure_ascii=False, indent=1))
    return {"placed": how if not icon else "icon", "start": round(t0, 2), "dur": round(d, 2)}
