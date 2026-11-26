"""Scenes: the speaker shrinks into a card or slides into half the screen, and the words being
said are typeset around them (the "edited by a designer" look of top creator reels).

    python -m autocut scene jobs/r1/spec.json card  --from "но как монтажёр" --key "Клод в умелых руках|главный"
    python -m autocut scene jobs/r1/spec.json split --from "дизайн постов" --list "дизайн постов|аналитика|сценарии"
    python -m autocut scene jobs/r1/spec.json clear
then: python -m autocut render jobs/r1/spec.json

card  — speaker shrinks (0.35 s) into a card on a light background; the first spoken words sit above
        the card, the next ones run down its side, the rest stack below: key words big, others small.
split — light panel on top where key words / a list build up as they are said; speaker below.
Every word appears exactly when it is spoken. Captions are hidden while a scene is on.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

STYLE = {"bg": "#F4F2EE", "ink": "#2B2926", "key": "#D9B48F", "key_edge": "#8C6440"}
FONTS = ["fonts/montserrat/Montserrat-Black.ttf", "fonts/montserrat/Montserrat-Medium.ttf"]
SMALL, KEY = "Montserrat Medium", "Montserrat Black"
ANIM = 0.35


def _n(w: str) -> str:
    return re.sub(r"[^\w]+", "", w.lower().replace("ё", "е"))


def _words(spec: dict, s: float, e: float) -> list[dict]:
    return [w for c in spec.get("captions", []) for w in (c.get("words") or []) if s - 0.05 <= w["s"] < e - 0.05]


def _mark(words: list[dict], keys: list[str]) -> list[bool]:
    """True for words that belong to one of the key phrases (first match of each)."""
    big = [False] * len(words)
    toks = [_n(w["t"]) for w in words]
    for k in keys:
        want = [_n(x) for x in k.split() if _n(x)]
        for i in range(len(toks) - len(want) + 1):
            if all(toks[i + j] == x or (len(x) > 3 and toks[i + j].startswith(x[:-2])) for j, x in enumerate(want)):
                for j in range(len(want)):
                    big[i + j] = True
                break
    return big


def in_scene(spec: dict, t: float) -> bool:
    return any(sc["start"] <= t < sc["end"] for sc in spec.get("scenes") or [])


# ------------------------------------------------------------------ geometry (shared by video + text)
def card_box(W: int, H: int) -> tuple[float, float, float, float]:
    cw, ch = W * 0.40, H * 0.40
    cx, cy = W * 0.63, H * 0.31
    return cx - cw / 2, cy - ch / 2, cw, ch


SPLIT = 0.40  # top panel share


def video_filters(spec: dict, fc: list[str], last: str, W: int, H: int, FPS: int) -> str:
    st = dict(STYLE, **(spec.get("scene_style") or {}))
    bg = "0x" + st["bg"].lstrip("#")
    for k, sc in enumerate(spec.get("scenes") or []):
        s, e = sc["start"], sc["end"]
        d = e - s
        fc.append(f"[{last}]split[sa{k}][sb{k}]")
        fc.append(f"color=c={bg}:s={W}x{H}:r={FPS}:d={d:.4f},setpts=PTS+{s:.4f}/TB[sg{k}]")
        q = f"(1-pow(1-min(1,t/{ANIM}),3))"  # ease-out 0..1
        if sc["type"] == "card":
            x0, y0, cw, ch = card_box(W, H)
            sw = f"({W}-({W}-{cw:.1f})*{q})"
            fc.append(f"[sb{k}]trim={s:.4f}:{e:.4f},setpts=PTS-STARTPTS,"
                      f"drawbox=0:0:iw:ih:white@1:t={max(4, W // 60)},"
                      f"scale=w='trunc({sw}/2)*2':h='trunc({sw}*{H / W:.5f}/2)*2':eval=frame,"
                      f"setpts=PTS+{s:.4f}/TB[sc{k}]")
            cx, cy = x0 + cw / 2, y0 + ch / 2
            tt = f"(t-{s:.4f})"
            qq = f"(1-pow(1-min(1,{tt}/{ANIM}),3))"
            fc.append(f"[sg{k}][sc{k}]overlay=x='{W / 2}+({cx:.1f}-{W / 2})*{qq}-w/2':"
                      f"y='{H / 2}+({cy:.1f}-{H / 2})*{qq}-h/2':eval=frame[sm{k}]")
        else:  # split: speaker slides up into the lower part
            ph = int(H * SPLIT)
            lh = H - ph
            tt = f"(t-{s:.4f})"
            qq = f"(1-pow(1-min(1,{tt}/{ANIM}),3))"
            fc.append(f"[sb{k}]trim={s:.4f}:{e:.4f},setpts=PTS-STARTPTS,crop={W}:{lh}:0:{int(H * 0.08)},"
                      f"setpts=PTS+{s:.4f}/TB[sc{k}]")
            fc.append(f"[sg{k}][sc{k}]overlay=x=0:y='{H}-({lh})*{qq}':eval=frame[sm{k}]")
        fc.append(f"[sa{k}][sm{k}]overlay=eof_action=pass:enable='between(t,{s - 0.004:.4f},{e - 0.001:.4f})'[sv{k}]")
        last = f"sv{k}"
    return last


# ------------------------------------------------------------------ text (ASS events)
def ass_styles(spec: dict, H: int) -> list[str]:
    st = dict(STYLE, **(spec.get("scene_style") or {}))
    from .reel import _bgr
    small, key = int(H * 0.024), int(H * 0.05)
    return [f"Style: ScS,{SMALL},{small},{_bgr(st['ink'])},&H00000000,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1",
            f"Style: ScK,{KEY},{key},{_bgr(st['key'])},&H00000000,{_bgr(st['key_edge'])},&H40000000,"
            f"-1,0,0,0,100,100,0,0,1,{max(1, H // 640)},{max(1, H // 900)},7,0,0,0,1"]


def _font(spec: dict, big: bool, size: int):
    from PIL import ImageFont

    from .reel import _p
    try:
        return ImageFont.truetype(_p(spec, FONTS[0 if big else 1]), size)
    except Exception:
        return None


def ass_events(spec: dict, W: int, H: int) -> list[str]:
    from .reel import _ass_t
    ev = []
    small, key = int(H * 0.024), int(H * 0.05)
    fs, fk = _font(spec, False, small), _font(spec, True, key)
    wid = lambda t, big: (fk if big else fs).getlength(t) if (fk and fs) else len(t) * (key if big else small) * 0.6

    def grow(words, x, y, style, end, rot=""):
        """One line whose words appear one by one at their spoken time (left-anchored, so nothing shifts)."""
        for i, w in enumerate(words):
            nxt = words[i + 1]["s"] if i + 1 < len(words) else end
            txt = " ".join(v["t"] for v in words[: i + 1])
            ev.append(f"Dialogue: 2,{_ass_t(w['s'])},{_ass_t(max(nxt, w['s'] + 0.04))},{style},,0,0,0,,"
                      f"{{\\an7\\pos({int(x)},{int(y)}){rot}}}{txt}")

    def block(words, big, x, y, maxw, end):
        """Stack words below each other in lines; big/small runs keep their own style."""
        lines, cur, cb = [], [], None
        for w, b in zip(words, big):
            if cur and (b != cb or wid(" ".join(v["t"] for v in cur + [w]), b) > maxw):
                lines.append((cur, cb)); cur = []
            cur.append(w); cb = b
        if cur:
            lines.append((cur, cb))
        for ln, b in lines:
            grow(ln, x, y, "ScK" if b else "ScS", end)
            y += (key * 1.02) if b else (small * 1.45)
        return y

    for sc in spec.get("scenes") or []:
        s, e = sc["start"], sc["end"]
        words = _words(spec, s, e)
        if not words:
            continue
        keys = [k for k in (sc.get("key") or "").split("|") if k.strip()]
        if sc["type"] == "card":
            x0, y0, cw, ch = card_box(W, H)
            big = _mark(words, keys)
            first_big = big.index(True) if True in big else len(words)
            lead = words[: min(first_big, 5)]
            side = words[len(lead): min(first_big, len(lead) + 5)]
            rest = words[len(lead) + len(side):]
            if lead:
                grow(lead, x0, y0 - small * 1.5, "ScS", e)
            if side:  # down the right edge of the card
                grow(side, x0 + cw + small * 1.4, y0 + small * 0.4, "ScS", e, rot="\\frz-90")
            block(rest, big[len(lead) + len(side):], W * 0.07, y0 + ch + H * 0.035, W * 0.86, e)
        else:
            items = [x for x in (sc.get("list") or sc.get("key") or "").split("|") if x.strip()]
            toks = [_n(w["t"]) for w in words]
            y = H * 0.07
            shown = []
            for k, it in enumerate(items):  # each item appears when it is said (or evenly if never said)
                want = [_n(x) for x in it.split() if _n(x)]
                t0 = next((words[i]["s"] for i in range(len(toks))
                           if want and (toks[i] == want[0] or toks[i].startswith(want[0][: max(3, len(want[0]) - 2)]))
                           and words[i]["s"] not in shown), s + ANIM + k * (e - s - ANIM) / max(1, len(items)))
                shown.append(t0)
                ev.append(f"Dialogue: 2,{_ass_t(t0)},{_ass_t(e)},ScK,,0,0,0,,"
                          f"{{\\an7\\pos({int(W * 0.07)},{int(y)})\\fad(120,0)}}{it.strip()}")
                y += key * 1.05
    return ev


# ------------------------------------------------------------------ CLI
def scene(spec_path: str, kind: str, frm: str | None, to: str | None, key: str | None, lst: str | None) -> dict:
    from .place import find_words
    sp = Path(spec_path)
    spec = json.loads(sp.read_text())
    if kind == "clear":
        spec["scenes"] = []
        sp.write_text(json.dumps(spec, ensure_ascii=False, indent=1))
        return {"scenes": 0}
    anchor = frm or (key or lst or "").split("|")[0]
    s, e = find_words(spec, anchor)
    if to:
        e = find_words(spec, to)[1]
    else:  # to the end of the sentence (caption with a full stop) or ~4 s
        ends = [c["end"] for c in spec["captions"] if c["end"] > s + 2.0 and re.search(r"[.!?…]\s*$", c["text"])]
        e = min([x for x in ends if x <= s + 6.5] or [s + 4.0])
    e = min(e + 0.15, spec["duration"])
    s = max(0.0, s - 0.05)
    scenes = [x for x in spec.get("scenes") or [] if x["end"] <= s or x["start"] >= e]
    scenes.append({"type": kind, "start": round(s, 3), "end": round(e, 3), "key": key, "list": lst})
    spec["scenes"] = sorted(scenes, key=lambda x: x["start"])
    spec["broll"] = [b for b in spec.get("broll", []) if b["start"] + b["dur"] <= s or b["start"] >= e]
    for f in FONTS:
        if f not in spec.setdefault("fonts", []):
            spec["fonts"].append(f)
    sp.write_text(json.dumps(spec, ensure_ascii=False, indent=1))
    return {"scene": kind, "start": round(s, 2), "end": round(e, 2), "scenes": len(spec["scenes"])}
