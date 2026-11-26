# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
"""GRIN Studio template: the speaker cut out of the room and placed on a calm light set, with dark-green
motion cards (title, name plate with photo, typewriter quote, opening Bible, checklist, headline...) above the
head, yellow captions inside the Reels/TikTok/Shorts safe zone, and an optional layered CapCut project.

The talk itself (cuts, pauses, captions) comes from a normal GRIN job (`auto --plan` / `finish`).
The cards come from `scenes.json`, written per video (see SCENES below). Run with --plan first and show the
scene list to the person before rendering.

    python -m autocut studio jobs/r1 --scenes scenes.json --plan          # list + checks, no render
    python -m autocut studio jobs/r1 --scenes scenes.json                 # -> jobs/r1/studio/studio.mp4
    python -m autocut studio jobs/r1 --scenes scenes.json --video WIDE.MOV --capcut "Name" \
        --capcut-root ".../com.lveditor.draft" --media-dir ".../GRIN media/name" [--map LOCAL=REAL]

Best source: the speaker filmed with room on both sides (horizontal is fine) and down to the table, so the
cut-out has no hard edges. A tight vertical crop works but shows straight edges where the frame cut the body.

Speaker matting: Robust Video Matting (mobilenetv3, GPL-3.0 weights, downloaded on first use; see
THIRD_PARTY_NOTICES). Swap `MATTE_URL` for a permissive model before selling a bundle that includes it.
"""
from __future__ import annotations

import functools
import io
import json
import math
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .paths import app_root

ROOT = app_root()
W, H, FPS = 1080, 1920, 30
MATTE_URL = "https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_mobilenetv3_fp32.onnx"
SAFE_TOP, SAFE_BOTTOM = 270, 1495          # Reels / TikTok / Shorts UI never covers this band
ANCHOR = 1690                              # table line of the speaker sits here

THEME = dict(bg="#ECE9E1", accent="#1F4A32", accent2="#2E6B45", ink="#1B281F", gold="#C9962E",
             light="#CDECD2", red="#B24034", caption="#FFD60A", caption_stroke="#141C16", caption_y=1430)

SCENES = """scenes.json = {"theme": {...optional overrides of THEME...}, "scenes": [ {...}, ... ]}
Times: "from"/"to"/"at" are seconds or a phrase from the captions ("from" = phrase start, "to" = phrase end).
Every scene may carry "pills": [{"text","icon","style":"dark|light|red","at","x","y","rot"}].
  title      tag, bold, script                       big two-font title (+ small outlined tag)
  name       name, role, photo, chips:[{text,icon,at}] name plate with the person's photo
  stack      small, big, icon                         tilted card stack ("Course / leaders")
  bible      -                                        Bible opens, a page turns, warm glow + sparkles
  typewriter header, text, type_from, type_to        quote typed in sync with the speech
  headline   bold, script, script_at, gold, icon      big bold word + handwritten line
  giant      text, note, note_at                      huge word BEHIND the speaker's head
  checklist  title, items:[{text,at}], fail:{text,at} ticks on words; card greys out + red stamp
  rows       title, rows:[{text,ok,at}]               ✓ / ✗ rows
  icon_card  icon, small, big, dots                   round icon + two lines (comment, bell, ...)
  autograph  title                                    a signature draws itself
  end        bold, script, button, button_at          final question + "Save" button
  pill       text, icon, style, x, y, rot             a single chip anywhere
Icons: any GRIN icon (python -m autocut icons) + book, refresh, pen, dropf."""


# ---------------------------------------------------------------- small helpers
def rgb(h: str, a: int | None = None) -> tuple:
    h = h.lstrip("#"); c = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    return c + (a,) if a is not None else c


def clamp(x, a=0., b=1.):
    return max(a, min(b, x))


def ease_out(x):
    x = clamp(x); return 1 - (1 - x) ** 3


def back_out(x):
    x = clamp(x); c = 1.7
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def life(t, t0, t1, fin=0.3, fout=0.22):
    if t < t0 or t > t1 + fout: return None
    return back_out((t - t0) / fin), min(ease_out(clamp((t - t0) / fin) * 1.4), 1 - clamp((t - t1) / fout))


@functools.lru_cache(None)
def font(w: str, s: int):
    lib = ROOT / "library/fonts"
    if w == "script":
        return ImageFont.truetype(str(lib / "marckscript/MarckScript-Regular.ttf"), s)
    return ImageFont.truetype(str(lib / f"inter/Inter-{w}.ttf"), s)


EXTRA = {"book": '<path d="M4 5.5A2 2 0 0 1 6 3.5h13v15H6a2 2 0 0 0-2 2z"/><path d="M4 20.5a2 2 0 0 1 2-2h13v2.5H6"/><path d="M9 8h6"/>',
         "refresh": '<path d="M19.5 9A8 8 0 0 0 5 7.5M4.5 15A8 8 0 0 0 19 16.5"/><path d="M5 3.5v4h4M19 20.5v-4h-4"/>',
         "dropf": '<path d="M12 3s6.5 7 6.5 11.5a6.5 6.5 0 0 1-13 0C5.5 10 12 3 12 3z" fill="C"/>',
         "pen": '<path d="M4 20l1-4L16 5l3 3L8 19z"/><path d="M14 7l3 3"/>'}


@functools.lru_cache(None)
def icon(name: str, size: int, color=(255, 255, 255), stroke=2.0):
    import resvg_py
    from .icons import ICONS
    body = EXTRA.get(name) or ICONS[name][1]
    c = "#%02x%02x%02x" % tuple(color[:3])
    body = body.replace('fill="C"', f'fill="{c}"')
    s = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="{stroke}" '
         f'stroke-linecap="round" stroke-linejoin="round">{body}</svg>')
    return Image.open(io.BytesIO(bytes(resvg_py.svg_to_bytes(svg_string=s, width=size, height=size)))).convert("RGBA")


def shadowed(img, blur=26, off=14, op=70):
    pad = blur * 2
    out = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2 + off), (0, 0, 0, 0))
    sh = Image.new("RGBA", out.size, (0, 0, 0, 0))
    sh.paste((10, 30, 18, 255), (pad, pad + off), img.split()[3].point(lambda v: v * op // 255))
    out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur))); out.alpha_composite(img, (pad, pad))
    return out


def card(w, h, col, r=34):
    g = np.zeros((h, w, 4), np.uint8)
    yy = np.linspace(0, 1, h)[:, None]
    for i in range(3):
        g[..., i] = np.clip(col[i] * (1.12 - 0.22 * yy), 0, 255)
    g[..., 3] = 255
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    m = Image.new("L", (w, h), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), r, fill=255)
    im.paste(Image.fromarray(g), (0, 0), m)
    ImageDraw.Draw(im).rounded_rectangle((1, 1, w - 2, h - 2), r, outline=(255, 255, 255, 34), width=2)
    return im


def text_img(s, f, fill, pad=4):
    b = f.getbbox(s)
    im = Image.new("RGBA", (b[2] - b[0] + pad * 2, b[3] - b[1] + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((pad - b[0], pad - b[1]), s, font=f, fill=fill)
    return im


def fit_text(s, weight, size, fill, maxw=1000):
    while size > 30 and font(weight, size).getlength(s) > maxw:
        size -= 4
    return text_img(s, font(weight, size), fill)


def wrap(s, f, maxw):
    lines, cur = [], ""
    for w in s.split():
        t = (cur + " " + w).strip()
        if f.getlength(t) > maxw and cur: lines.append(cur); cur = w
        else: cur = t
    return lines + [cur]


def pill(s, f, fg, bg, padx=26, h=None, ic=None, outline=None):
    ti = text_img(s, f, fg)
    h = h or ti.height + 30
    iw = (h - 26 + 10) if ic else 0
    w = ti.width + padx * 2 + iw
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w - 1, h - 1), h // 2, fill=bg, outline=outline, width=3 if outline else 0)
    if ic:
        im.alpha_composite(icon(ic, h - 30, fg[:3]), (padx - 4, 15))
    im.alpha_composite(ti, (padx + iw, (h - ti.height) // 2))
    return im


def put(cv, img, cx, cy, scale=1., alpha=1., rot=0.):
    if alpha <= 0.01 or scale <= 0.01: return
    if rot: img = img.rotate(rot, Image.BICUBIC, expand=True)
    if abs(scale - 1) > 0.005:
        img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.BILINEAR)
    if alpha < 0.999:
        img = img.copy(); img.putalpha(img.split()[3].point(lambda v: int(v * alpha)))
    x, y = int(cx - img.width / 2), int(cy - img.height / 2)
    if x >= W or y >= H or x + img.width <= 0 or y + img.height <= 0: return
    cv.alpha_composite(img.crop((max(0, -x), max(0, -y), min(img.width, W - x), min(img.height, H - y))), (max(0, x), max(0, y)))


def pop(cv, img, t, t0, t1, cx, cy, rot=0., s0=0.7, slide=0):
    l = life(t, t0, t1)
    if not l: return
    p, a = l
    put(cv, img, cx, cy + slide * (1 - ease_out((t - t0) / 0.35)), s0 + (1 - s0) * p, a, rot)


# ---------------------------------------------------------------- timing from the captions
class Clock:
    def __init__(self, spec: dict):
        self.words = [(re.sub(r"[^\w]+", "", w["t"].lower().replace("ё", "е")), w["s"], w["e"])
                      for c in spec.get("captions", []) for w in c.get("words", [])]
        self.dur = spec["duration"]

    def find(self, phrase: str, after: float = 0.0):
        want = [re.sub(r"[^\w]+", "", x.lower().replace("ё", "е")) for x in phrase.split()]
        want = [x for x in want if x]
        ws = self.words
        for i in range(len(ws)):
            if ws[i][1] + 1e-3 < after: continue
            if all(i + j < len(ws) and ws[i + j][0].startswith(want[j][:max(3, len(want[j]) - 2)]) for j in range(len(want))):
                return ws[i][1], ws[i + len(want) - 1][2]
        raise SystemExit(f"studio: не нашёл фразу «{phrase}» в субтитрах")

    def t(self, v, end=False, after=0.0):
        if v is None: return None
        if isinstance(v, (int, float)): return float(v)
        a, b = self.find(v, after)
        return b if end else a


# ---------------------------------------------------------------- scenes
class Studio:
    def __init__(self, scenes: dict, spec: dict, job: Path):
        self.th = dict(THEME, **scenes.get("theme", {}))
        T = self.th
        self.A, self.A2, self.INK, self.GOLD = rgb(T["accent"]), rgb(T["accent2"]), rgb(T["ink"]), rgb(T["gold"])
        self.LIGHT, self.RED = rgb(T["light"]), rgb(T["red"])
        self.job = job
        clk = Clock(spec)
        self.sc = []
        last = 0.0
        for s in scenes["scenes"]:
            s = dict(s)
            s["t0"] = clk.t(s.get("from", s.get("at", last)), after=max(0, last - 0.5))
            s["t1"] = clk.t(s.get("to"), end=True, after=s["t0"]) if s.get("to") is not None else s["t0"] + 3
            for k in ("script_at", "note_at", "button_at", "type_from", "type_to"):
                if s.get(k) is not None: s[k] = clk.t(s[k], end=(k == "type_to"), after=s["t0"] - 0.5)
            for lst in ("chips", "items", "rows", "pills"):
                for it in s.get(lst, []) or []:
                    it["t"] = clk.t(it.get("at"), after=s["t0"] - 0.5) if it.get("at") is not None else s["t0"]
            if s.get("fail"): s["fail"]["t"] = clk.t(s["fail"].get("at"), after=s["t0"]) if s["fail"].get("at") else s["t1"] - 1
            s["t1"] = min(s["t1"], spec["duration"])
            self.sc.append(s); last = s["t1"]
        self.dur = spec["duration"]
        self._prep()

    # ---- sprites
    def _prep(self):
        A, A2, INK = self.A, self.A2, self.INK
        Y0 = SAFE_TOP + 20
        for s in self.sc:
            k = s["type"]; sp = {}
            if k == "title":
                if s.get("tag"): sp["tag"] = pill(s["tag"], font("Medium", 34), INK + (255,), (255, 255, 255, 255), outline=(40, 60, 45, 255), h=64)
                sp["bold"] = fit_text(s.get("bold", ""), "Bold", 104, A)
                if s.get("script"): sp["script"] = fit_text(s["script"], "script", 118, A2)
                sp["pos"] = [Y0 + 10, Y0 + 125, Y0 + 260]; s["bottom"] = Y0 + 330
            elif k == "name":
                c = card(940, 340, A); d = ImageDraw.Draw(c)
                if s.get("photo"):
                    ph = Image.open(s["photo"]).convert("RGB")
                    q = min(ph.size); ph = ph.crop(((ph.width - q) // 2, (ph.height - q) // 2, (ph.width + q) // 2, (ph.height + q) // 2)).resize((280, 280), Image.LANCZOS)
                    m = Image.new("L", (280, 280), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, 279, 279), 28, fill=255)
                    o = Image.new("RGBA", (280, 280)); o.paste(ph, (0, 0), m)
                    ImageDraw.Draw(o).rounded_rectangle((0, 0, 279, 279), 28, outline=(255, 255, 255, 200), width=4)
                    c.alpha_composite(o, (30, 30)); tx = 330
                else:
                    d.ellipse((40, 80, 220, 260), fill=(255, 255, 255, 30)); c.alpha_composite(icon("user", 110), (75, 115)); tx = 250
                f = font("Bold", 64)
                while f.getlength(s.get("name", "")) > 940 - tx - 40 and f.size > 36: f = font("Bold", f.size - 4)
                d.text((tx, 92), s.get("name", ""), font=f, fill="white")
                d.text((tx + 2, 178), s.get("role", ""), font=font("Medium", 36), fill=(255, 255, 255, 190))
                sp["card"] = shadowed(c)
                sp["chips"] = [shadowed(pill(ch["text"], font("SemiBold", 38), A + (255,), self.LIGHT + (255,), h=74, ic=ch.get("icon")), 14, 8, 50)
                               for ch in s.get("chips", [])]
                sp["pos"] = [Y0 + 80]; s["bottom"] = Y0 + 330 if s.get("chips") else Y0 + 240
            elif k == "stack":
                sp["back"] = self._stack_card(True); sp["front"] = self._stack_card(False, s)
                sp["pos"] = [Y0 + 80]; s["bottom"] = Y0 + 330
            elif k == "bible":
                s["bottom"] = Y0 + 380
            elif k == "typewriter":
                s.setdefault("type_from", s["t0"] + 1.5); s.setdefault("type_to", s["t1"] - 0.3)
                s["bottom"] = Y0 + 360
            elif k == "headline":
                sp["bold"] = fit_text(s.get("bold", ""), "Black" if len(s.get("bold", "")) < 12 else "Bold", 170 if len(s.get("bold", "")) < 12 else 100, A)
                if s.get("script"): sp["script"] = fit_text(s["script"], "script", 200 if s.get("gold") else 130, self.GOLD if s.get("gold") else A2)
                if s.get("icon"): sp["icon"] = icon(s["icon"], 120, self.GOLD if s.get("gold") else A2, 1.0 if s["icon"] == "dropf" else 2.4)
                sp["pos"] = [Y0 + 10 + sp["bold"].height / 2, Y0 + sp["bold"].height + 50]
                s["bottom"] = Y0 + sp["bold"].height + 50 + (sp["script"].height / 2 if "script" in sp else 0)
            elif k == "giant":
                sp["big"] = fit_text(s.get("text", ""), "Black", 172, A, 1020)
                if s.get("note"): sp["note"] = text_img(s["note"], font("script", 110), A2)
                s["bottom"] = Y0 + 200; s["giant"] = True
            elif k == "checklist":
                s["bottom"] = Y0 + 120 + 110 * len(s.get("items", [])) + (70 if s.get("fail") else 0)
                if s.get("fail"): sp["fail"] = shadowed(pill(s["fail"]["text"], font("Bold", 46), (255, 255, 255, 255), self.RED + (255,), h=92, ic="cross"), 16, 8, 60)
            elif k == "rows":
                s["bottom"] = Y0 + 140 + 112 * len(s.get("rows", []))
            elif k == "icon_card":
                sp["card"] = self._icon_card(s, 0); s["bottom"] = Y0 + 200
            elif k == "autograph":
                s["bottom"] = Y0 + 290
            elif k == "end":
                sp["bold"] = fit_text(s.get("bold", ""), "Bold", 92, A)
                if s.get("script"): sp["script"] = fit_text(s["script"], "script", 150, A2)
                if s.get("button"): sp["button"] = shadowed(pill(s["button"], font("SemiBold", 42), (255, 255, 255, 255), A + (255,), h=92, ic="bookmark"), 14, 8, 60)
                s["bottom"] = Y0 + 420
            elif k == "pill":
                s.setdefault("pills", []).insert(0, dict(s, t=s["t0"]))
                s["bottom"] = 0
            pills = []
            for p in s.get("pills", []):
                st = p.get("style", "light")
                fg, bg = {"dark": ((255, 255, 255, 255), A + (255,)), "red": ((255, 255, 255, 255), self.RED + (255,)),
                          "light": (A + (255,), self.LIGHT + (255,)), "green": ((255, 255, 255, 255), A2 + (255,))}[st]
                im = shadowed(pill(p["text"], font("Bold", 42), fg, bg, h=86, ic=p.get("icon")), 14, 8, 60)
                p.setdefault("y", s["bottom"] + 60); p.setdefault("x", 0); p.setdefault("rot", -3)
                if p["y"] < 900: s["bottom"] = max(s["bottom"], p["y"] + 50)
                pills.append(im)
            sp["pills"] = pills
            s["sp"] = sp

    def _stack_card(self, back, s=None):
        c = card(640, 380, tuple(int(v * 0.8) for v in self.A) if back else self.A)
        d = ImageDraw.Draw(c)
        for i in range(6):
            d.rounded_rectangle((22, 34 + i * 54, 44, 60 + i * 54), 6, fill=(255, 255, 255, 40))
        if back:
            d.ellipse((340, 60, 600, 320), outline=(255, 255, 255, 25), width=26)
        else:
            c.alpha_composite(icon(s.get("icon", "book"), 74), (80, 52))
            d.text((80, 160), s.get("small", ""), font=font("Medium", 50), fill=(255, 255, 255, 220))
            f = font("Bold", 88)
            while f.getlength(s.get("big", "")) > 520 and f.size > 40: f = font("Bold", f.size - 4)
            d.text((80, 225), s.get("big", ""), font=f, fill="white")
        return shadowed(c)

    def _icon_card(self, s, t):
        c = card(880, 210, self.A); d = ImageDraw.Draw(c)
        d.ellipse((40, 45, 160, 165), fill=(255, 255, 255, 30)); c.alpha_composite(icon(s.get("icon", "comment"), 72), (64, 69))
        d.text((190, 50), s.get("small", ""), font=font("Medium", 40), fill=(255, 255, 255, 190))
        f = font("Bold", 62)
        while f.getlength(s.get("big", "")) > 560 and f.size > 36: f = font("Bold", f.size - 4)
        d.text((190, 98), s.get("big", ""), font=f, fill="white")
        if s.get("dots"):
            for i in range(3):
                a = 80 + int(175 * (0.5 + 0.5 * math.sin(t * 6 - i * 0.9)))
                d.ellipse((770 + i * 30, 98, 790 + i * 30, 118), fill=(255, 255, 255, a))
        return shadowed(c)

    def _typewriter(self, s, n):
        c = card(940, 470, self.A); d = ImageDraw.Draw(c)
        d.text((48, 36), s.get("header", ""), font=font("SemiBold", 38), fill=(255, 255, 255, 200))
        d.line((48, 100, 892, 100), fill=(255, 255, 255, 45), width=2)
        f = font("Medium", 52); full = s.get("text", ""); txt = full[:n]; y = 132; part = ""
        for ln in wrap(full, f, 840):
            part = txt[:len(ln)]; txt = txt[len(ln) + 1:]
            d.text((48, y), part, font=f, fill="white"); y += 72
            if len(part) < len(ln): break
        if n < len(full):
            lx = 48 + f.getlength(part); d.rectangle((lx + 4, y - 66, lx + 10, y - 16), fill=(255, 255, 255, 200))
        return shadowed(c)

    def _checklist(self, s, t):
        items = s.get("items", [])
        grey = 0.55 * clamp((t - s["fail"]["t"]) / 0.4) if s.get("fail") else 0
        c = card(820, 120 + 110 * len(items), tuple(int(self.A[i] * (1 - grey) + 150 * grey) for i in range(3)))
        d = ImageDraw.Draw(c)
        d.text((50, 38), s.get("title", ""), font=font("SemiBold", 38), fill=(255, 255, 255, 200))
        for i, it in enumerate(items):
            y = 112 + i * 110
            d.rounded_rectangle((50, y, 120, y + 70), 18, fill=(255, 255, 255, 30), outline=(255, 255, 255, 90), width=3)
            k = clamp((t - it["t"]) / 0.25)
            if k > 0:
                ic = icon("check", 56, (255, 255, 255), 3.2)
                if k < 1: ic = ic.resize((max(1, int(56 * k)),) * 2)
                c.alpha_composite(ic, (85 - ic.width // 2, y + 35 - ic.height // 2))
            d.text((150, y + 6), it["text"], font=font("Bold", 54), fill="white")
        return shadowed(c)

    def _rows(self, s, t):
        rows = s.get("rows", [])
        c = card(820, 140 + 112 * len(rows), self.A); d = ImageDraw.Draw(c)
        d.text((50, 38), s.get("title", ""), font=font("SemiBold", 40), fill=(255, 255, 255, 200))
        for i, r in enumerate(rows):
            y = 122 + i * 112
            d.text((50, y), r["text"], font=font("Bold", 58), fill="white")
            if t >= r["t"]:
                col = (125, 214, 150) if r.get("ok", True) else (240, 140, 130)
                d.ellipse((690, y - 4, 770, y + 76), fill=col + (255,))
                c.alpha_composite(icon("check" if r.get("ok", True) else "cross", 52, (255, 255, 255), 3.4), (704, y + 10))
        return shadowed(c)

    def _autograph(self, s, k):
        c = card(760, 300, self.A); d = ImageDraw.Draw(c)
        d.text((48, 36), s.get("title", ""), font=font("SemiBold", 38), fill=(255, 255, 255, 200))
        c.alpha_composite(icon("pen", 60), (650, 30))
        d.line((60, 250, 700, 250), fill=(255, 255, 255, 70), width=3)
        pts = []
        for i in range(160):
            u = i / 159
            pts.append((110 + 540 * u + 18 * math.cos(u * 19), 180 - 55 * math.sin(u * 19) * (0.5 + 0.5 * math.sin(u * 4.3)) - 20 * math.sin(u * 3)))
        n = int(len(pts) * clamp(k))
        if n > 1: d.line(pts[:n], fill="white", width=7, joint="curve")
        return shadowed(c)

    # ---- the opening Bible
    def _bible(self, cv, t, t0, t1):
        l = life(t, t0, t1, 0.35, 0.3)
        if not l: return
        p, alpha = l
        PW, PH = 330, 440
        B = self.__dict__.setdefault("_B", {})
        if not B:
            B["cover"] = _bible_cover(PW, PH, self.A); B["inner"] = Image.new("RGBA", (PW, PH), tuple(int(v * 1.05) for v in self.A) + (255,))
            B["L"] = _page(PW, PH, 1, False); B["R"] = _page(PW, PH, 2, True); B["R2"] = _page(PW, PH, 3, True); B["L2"] = _page(PW, PH, 4, False)
        layer = Image.new("RGBA", (900, 640), (0, 0, 0, 0))
        sx, top = 450, 90
        open_k = ease_out((t - t0 - 0.35) / 0.9); flip_k = ease_out((t - t0 - 1.45) / 0.7)
        g = clamp((t - t0 - 0.9) / 0.6)
        if g > 0:
            gl = Image.new("RGBA", (900, 640), (0, 0, 0, 0))
            ImageDraw.Draw(gl).ellipse((200, 120, 700, 520), fill=(255, 214, 120, int(130 * g)))
            layer.alpha_composite(gl.filter(ImageFilter.GaussianBlur(70)))
        sh = Image.new("RGBA", (900, 640), (0, 0, 0, 0))
        ImageDraw.Draw(sh).ellipse((sx - PW * open_k - 10, top + PH - 20, sx + PW + 10, top + PH + 40), fill=(20, 40, 25, 90))
        layer.alpha_composite(sh.filter(ImageFilter.GaussianBlur(18)))
        layer.alpha_composite(B["R2"] if flip_k >= 1 else B["R"], (sx, top))
        if open_k > 0.5:
            layer.alpha_composite(B["L2"] if flip_k >= 0.5 else B["L"], (sx - PW, top))
        for k, front, backside, lift in ((flip_k, B["R"], B["L2"], 0.10), (open_k, B["cover"], B["inner"], 0.14)):
            if 0 < k < 1 or (front is B["cover"] and k <= 0):
                c = math.cos(k * math.pi)
                q, oh = _quad(front if c > 0 else backside, PW * c, PH, lift * math.sin(k * math.pi))
                if q is not None:
                    layer.alpha_composite(q, (sx if c > 0 else sx - q.width, top - (oh - PH) // 2))
        if g > 0:
            for i in range(6):
                a = (t * 1.3 + i / 6) % 1
                si = icon("sparkle", int(34 + 20 * math.sin(i)), self.GOLD, 2.2)
                si.putalpha(si.split()[3].point(lambda v: int(v * (1 - a) * g)))
                layer.alpha_composite(si, (int(450 + math.cos(i * 2.1) * (180 + 160 * a)), int(300 - 260 * a + math.sin(i) * 40)))
        put(cv, layer, W / 2, SAFE_TOP + 130, 1.0 + 0.2 * p, alpha)

    # ---- per-frame drawing
    def draw(self, cv, t, behind=False, only=None):
        Y0 = SAFE_TOP + 20
        for i, s in enumerate(self.sc):
            if only is not None and only != i: continue
            t0, t1 = s["t0"], s["t1"]
            if t < t0 - 0.05 or t > t1 + 0.4: continue
            k, sp = s["type"], s["sp"]
            if behind:
                if k == "giant":
                    l = life(t, t0, t1)
                    if l: put(cv, sp["big"], W / 2, Y0 + 180, 0.85 + 0.15 * l[0], l[1])
                continue
            if k == "title":
                if "tag" in sp: pop(cv, sp["tag"], t, t0 + 0.05, t1, W / 2, sp["pos"][0])
                pop(cv, sp["bold"], t, t0 + 0.15, t1, W / 2, sp["pos"][1], s0=0.85, slide=30)
                if "script" in sp: pop(cv, sp["script"], t, t0 + 0.5, t1, W / 2, sp["pos"][2], s0=0.85, slide=30)
            elif k == "name":
                pop(cv, sp["card"], t, t0, t1, W / 2, sp["pos"][0] + 80, slide=-40)
                xs = _row_x([c.width for c in sp["chips"]])
                for ch, im, x in zip(s.get("chips", []), sp["chips"], xs):
                    pop(cv, im, t, ch["t"], t1, x, Y0 + 330)
            elif k == "stack":
                pop(cv, sp["back"], t, t0, t1, W / 2 - 60, Y0 + 110, rot=7)
                pop(cv, sp["front"], t, t0 + 0.17, t1, W / 2 + 20, Y0 + 140, rot=-4)
            elif k == "bible":
                self._bible(cv, t, t0, t1)
            elif k == "typewriter":
                l = life(t, t0, t1)
                if l:
                    n = int(len(s.get("text", "")) * clamp((t - s["type_from"]) / max(0.1, s["type_to"] - s["type_from"])))
                    put(cv, self._typewriter(s, n), W / 2, Y0 + 150, 0.85 + 0.15 * l[0], l[1])
            elif k == "headline":
                pop(cv, sp["bold"], t, t0, t1, W / 2, sp["pos"][0], s0=0.8)
                if "script" in sp: pop(cv, sp["script"], t, s.get("script_at") or t0 + 0.3, t1, W / 2 + 40, sp["pos"][1], s0=0.8)
                if "icon" in sp:
                    l = life(t, t0 + 0.5, t1)
                    if l: put(cv, sp["icon"], W / 2 - sp["script"].width / 2 - 60 if "script" in sp else W / 2 - 300,
                              sp["pos"][1] + 10 * math.sin(t * 5), l[0], l[1], rot=-12)
            elif k == "giant":
                if "note" in sp: pop(cv, sp["note"], t, s.get("note_at") or t0, t1, W / 2 - 250, Y0 + 30, rot=-6)
            elif k == "checklist":
                l = life(t, t0, t1)
                if l: put(cv, self._checklist(s, t), W / 2, Y0 + 60 + 55 * len(s.get("items", [])), 0.85 + 0.15 * l[0], l[1])
                if s.get("fail"): pop(cv, sp["fail"], t, s["fail"]["t"], t1, W / 2 + 170, Y0 + 120 + 110 * len(s["items"]) + 30, rot=-4)
            elif k == "rows":
                l = life(t, t0, t1)
                if l: put(cv, self._rows(s, t), W / 2, Y0 + 70 + 56 * len(s.get("rows", [])), 0.85 + 0.15 * l[0], l[1])
            elif k == "icon_card":
                l = life(t, t0, t1)
                if l: put(cv, self._icon_card(s, t) if s.get("dots") else sp["card"], W / 2, Y0 + 80, 0.85 + 0.15 * l[0], l[1])
            elif k == "autograph":
                l = life(t, t0, t1)
                if l: put(cv, self._autograph(s, (t - t0 - 0.3) / 1.2), W / 2, Y0 + 120, 0.85 + 0.15 * l[0], l[1], rot=-2)
            elif k == "end":
                pop(cv, sp["bold"], t, t0, 1e9, W / 2, Y0 + 40, s0=0.85, slide=30)
                if "script" in sp: pop(cv, sp["script"], t, t0 + 0.35, 1e9, W / 2, Y0 + 180, s0=0.85, slide=30)
                if "button" in sp: pop(cv, sp["button"], t, s.get("button_at") or t0 + 0.7, 1e9, W / 2, Y0 + 340)
            for p, im in zip(s.get("pills", []), sp.get("pills", [])):
                pop(cv, im, t, p["t"], t1, W / 2 + p["x"], p["y"], rot=p["rot"])

    def bottom(self, t):
        """lowest y used by graphics now (the speaker is placed below it)."""
        b = None
        for s in self.sc:
            if s["t0"] - 0.1 <= t <= s["t1"] + 0.1:
                v = s["bottom"] - (220 if s.get("giant") else 0)
                b = v if b is None else max(b, v)
        return b


def _row_x(ws, gap=24):
    tot = sum(ws) + gap * (len(ws) - 1); x = W / 2 - tot / 2; out = []
    for w in ws: out.append(x + w / 2); x += w + gap
    return out


def _page(w, h, seed, right=True):
    paper = (247, 242, 228)
    im = Image.new("RGBA", (w, h), paper + (255,)); d = ImageDraw.Draw(im)
    rnd = np.random.RandomState(seed)
    for col in range(2):
        x0 = 34 + col * (w - 50) // 2
        for i in range(17):
            y = 52 + i * 24
            ln = (w - 90) // 2 - rnd.randint(0, 40) if i % 6 != 5 else rnd.randint(30, 90)
            d.rounded_rectangle((x0, y, x0 + ln, y + 7), 3, fill=(150, 140, 120, 150))
    xs = np.arange(w); dist = xs if right else (w - 1 - xs)
    sh = np.tile((np.exp(-dist / 38.0) * 70)[None, :], (h, 1))
    dk = Image.new("RGBA", (w, h), (60, 45, 20, 255)); dk.putalpha(Image.fromarray(sh.astype(np.uint8)))
    im.alpha_composite(dk)
    return im


def _bible_cover(w, h, col):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    gold = (214, 172, 80, 255)
    d.rounded_rectangle((0, 0, w - 1, h - 1), 18, fill=tuple(int(v * 0.8) for v in col) + (255,), outline=(201, 160, 70, 255), width=4)
    d.rounded_rectangle((22, 22, w - 23, h - 23), 12, outline=(201, 160, 70, 140), width=2)
    cx = w // 2
    d.rectangle((cx - 8, 110, cx + 8, 250), fill=gold); d.rectangle((cx - 50, 150, cx + 50, 166), fill=gold)
    d.text((cx, 320), "БИБЛИЯ", font=font("Bold", 40), fill=gold, anchor="mm")
    return im


def _quad(img, width_signed, h, lift):
    w = abs(width_signed)
    if w < 2: return None, 0
    oh = int(h * (1 + lift)) + 2
    out = img.transform((int(w), oh), Image.QUAD, (0, 0, 0, img.height, img.width, img.height, img.width, 0), Image.BICUBIC)
    src = Image.new("RGBA", (int(w), oh), (0, 0, 0, 0))
    for x in range(0, int(w), 2):
        colh = int(h * (1 + lift * x / max(1, w - 1)))
        col = out.crop((x, 0, min(int(w), x + 2), oh)).resize((min(2, int(w) - x), colh))
        src.alpha_composite(col, (x, int((oh - colh) / 2)))
    if width_signed < 0: src = src.transpose(Image.FLIP_LEFT_RIGHT)
    return src, oh


# ---------------------------------------------------------------- speaker cut-out
def _model() -> Path:
    p = ROOT / "library/models/rvm_mobilenetv3_fp32.onnx"
    if not p.exists():
        import urllib.request
        p.parent.mkdir(parents=True, exist_ok=True)
        print("studio: downloading the matting model (15 MB)...", file=sys.stderr)
        urllib.request.urlretrieve(MATTE_URL, p)
    return p


def _probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration",
                        "-of", "json", str(path)], capture_output=True, text=True)
    j = json.loads(r.stdout); st = j["streams"][0]
    return st["width"], st["height"], float(j["format"]["duration"])


def _matte(src: Path, out: Path, w: int, h: int, vf: str = "", every: int = 1):
    """Robust Video Matting over a whole clip -> gray alpha video (ffv1). Returns list of per-frame bboxes (sampled)."""
    import onnxruntime as ort
    so = ort.SessionOptions(); so.intra_op_num_threads = 4
    sess = ort.InferenceSession(str(_model()), so)
    rd = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(src), "-vf", (vf + "," if vf else "") + f"scale={w}:{h}",
                           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    wr = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{w}x{h}", "-r", str(FPS),
                           "-i", "-", "-c:v", "ffv1", str(out)], stdin=subprocess.PIPE) if out else None
    rec = [np.zeros([1, 1, 1, 1], np.float32)] * 4
    ds = np.array([min(1.0, 512 / max(w, h))], np.float32)
    boxes, n = [], 0
    while True:
        b = rd.stdout.read(w * h * 3)
        if len(b) < w * h * 3: break
        x = np.frombuffer(b, np.uint8).reshape(h, w, 3).transpose(2, 0, 1)[None].astype(np.float32) / 255
        _, pha, *rec = sess.run(None, {"src": x, "r1i": rec[0], "r2i": rec[1], "r3i": rec[2], "r4i": rec[3], "downsample_ratio": ds})
        a = (pha[0, 0] * 255).clip(0, 255).astype(np.uint8)
        if wr: wr.stdin.write(a.tobytes())
        if n % every == 0:
            ys, xs = np.where(a > 128)
            if len(xs) > 200: boxes.append((xs.min(), ys.min(), xs.max(), ys.max()))
        n += 1
    if wr: wr.stdin.close(); wr.wait()
    return boxes


def _audio_offset(a: Path, b: Path) -> float:
    """seconds to add to times of `a` to land on the same moment in `b` (same recording, different export)."""
    def pcm(p):
        r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-t", "40", "-ac", "1", "-ar", "8000", "-f", "f32le", "-"], capture_output=True)
        return np.frombuffer(r.stdout, np.float32)
    x, y = pcm(a), pcm(b)
    if not len(x) or not len(y): return 0.0
    seg = x[8000 * 5: 8000 * 15]
    n = 1 << int(np.ceil(np.log2(len(y) + len(seg))))
    c = np.fft.irfft(np.fft.rfft(y, n) * np.conj(np.fft.rfft(seg, n)), n)[:len(y)]
    return float(round(int(np.argmax(c)) / 8000 - 5, 3))


def prepare_speaker(job: Path, spec: dict, video: Path | None) -> dict:
    """cut-out of the speaker, cut like the talk: studio/cut.mp4 + studio/alpha.mkv + geometry."""
    d = job / "studio"; d.mkdir(exist_ok=True)
    meta_p = d / "speaker.json"
    src_a = Path(spec["sources"]["A1"] if "A1" in spec["sources"] else spec["sources"]["A"])
    video = video or src_a
    key = f"{video}|{json.dumps(spec['voice'])}"
    if meta_p.exists() and json.loads(meta_p.read_text()).get("key") == key and (d / "alpha.mkv").exists():
        return json.loads(meta_p.read_text())
    vw, vh, vdur = _probe(video)
    off = _audio_offset(src_a, video) if Path(video) != src_a else 0.0
    # 1) quick low-res pass: where is the person over the whole clip?
    qw = 384; qh = int(vh * qw / vw) // 2 * 2
    boxes = _matte(video, None, qw, qh, every=5)
    bx = np.array(boxes, float) * (vw / qw)
    x0, y0 = np.percentile(bx[:, 0], 2), np.percentile(bx[:, 1], 2)
    x1, y1 = np.percentile(bx[:, 2], 98), np.percentile(bx[:, 3], 98)
    touches = dict(left=bool(x0 < vw * 0.01), right=bool(x1 > vw * 0.99), bottom=bool(y1 > vh * 0.99))
    pw, ph = x1 - x0, y1 - y0
    cx0 = max(0, x0 - 0.06 * pw); cx1 = min(vw, x1 + 0.06 * pw)
    cy0 = max(0, y0 - 0.04 * ph); cy1 = min(vh, y1 + 0.02 * ph)
    cw, chh = int(cx1 - cx0) // 2 * 2, int(cy1 - cy0) // 2 * 2
    sc = min(1.0, 760 / chh)
    SW, SH = int(cw * sc) // 2 * 2, int(chh * sc) // 2 * 2
    crop = f"crop={cw}:{chh}:{int(cx0)}:{int(cy0)}"
    # 2) full matte on the crop, then cut both like the talk (skipped when already done for this crop and cut)
    heavy_key = f"{key}|{crop}|{SW}x{SH}|{off}"
    stamp = d / "heavy.key"
    if stamp.exists() and stamp.read_text() == heavy_key and (d / "alpha.mkv").exists() and (d / "cut.mp4").exists():
        meta = dict(key=key, SW=SW, SH=SH, base=round(float((y1 - cy0) / chh), 4), touches=touches, offset=off, aspect=SW / SH)
        meta_p.write_text(json.dumps(meta)); return meta
    full_a = d / "alpha_full.mkv"
    _matte(video, full_a, SW, SH, vf=crop)
    n = len(spec["voice"])
    pad = ",tpad=stop_mode=clone:stop_duration=4"
    outs = "".join(f"[s{i}]" for i in range(n))
    cuts = "".join(f"[s{i}]trim=start={max(0, v['in'] + off)}:duration={v['dur']},setpts=PTS-STARTPTS[v{i}];"
                   for i, v in enumerate(spec["voice"]))
    cat = "".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0,fps={FPS}[o]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-filter_complex",
                    f"[0:v]{crop},scale={SW}:{SH},fps={FPS}{pad},split={n}{outs};{cuts}{cat}",
                    "-map", "[o]", "-an", "-c:v", "libx264", "-crf", "12", "-preset", "veryfast", str(d / "cut.mp4")], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(full_a), "-filter_complex",
                    f"[0:v]fps={FPS}{pad},split={n}{outs};{cuts}{cat}",
                    "-map", "[o]", "-c:v", "ffv1", str(d / "alpha.mkv")], check=True)
    stamp.write_text(heavy_key)
    base = (y1 - cy0) / chh
    meta = dict(key=key, SW=SW, SH=SH, base=round(float(base), 4), touches=touches, offset=float(off),
                aspect=SW / SH)
    meta_p.write_text(json.dumps(meta))
    return meta


def shooting_tips(meta: dict) -> list[str]:
    tips = []
    if meta["touches"]["left"] or meta["touches"]["right"]:
        tips.append("Плечи/руки упираются в край кадра — по бокам будут ровные срезы. Снимай с запасом по бокам "
                    "(горизонтально или отойди от камеры).")
    return tips


# ---------------------------------------------------------------- captions
def _captions(spec: dict, job: Path):
    caps = [(c["start"], c["end"], c["text"].replace("\n", " ")) for c in spec.get("captions", [])]
    ti = spec.get("title")
    if ti and caps and ti.get("end", 0) > 0.3:
        wp = job / "words_edit.json" if (job / "words_edit.json").exists() else job / "words.json"
        try:
            ws = json.loads(wp.read_text()); ws = ws if isinstance(ws, list) else ws.get("words", [])
            first = [w["text"] for w in ws if w["start"] < caps[0][0] - 0.05]
            if first and ws:
                s = " ".join(first).strip(" ?.!,")
                caps.insert(0, (0.25, caps[0][0], s[:1].upper() + s[1:] if len(s) < 40 else " ".join(s.split()[:5])))
        except Exception:
            pass
    return caps


@functools.lru_cache(128)
def caption_img(s: str, color: str, stroke: str):
    f = font("Bold", 58)
    ims = []
    for l in wrap(s, f, 860):
        b = f.getbbox(l, stroke_width=7)
        im = Image.new("RGBA", (b[2] - b[0] + 20, b[3] - b[1] + 20), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((10 - b[0], 10 - b[1]), l, font=f, fill=rgb(color), stroke_width=7, stroke_fill=rgb(stroke))
        ims.append(im)
    im = Image.new("RGBA", (max(i.width for i in ims), sum(i.height for i in ims)), (0, 0, 0, 0)); y = 0
    for i in ims: im.alpha_composite(i, ((im.width - i.width) // 2, y)); y += i.height
    return shadowed(im, 12, 6, 80)


# ---------------------------------------------------------------- background
def make_bg(col: str):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt((xx - W / 2) ** 2 + ((yy - H * 0.62) / 1.45) ** 2)
    v = 1 - 0.035 * np.clip(r / 900, 0, 1.5)
    rings = 0.012 * (0.5 + 0.5 * np.cos(r / 46)) * np.exp(-r / 700)
    img = np.array(rgb(col), np.float32)[None, None, :] * (v - rings)[..., None]
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert("RGBA")


def floor_shadow(pw):
    sh = Image.new("RGBA", (int(pw) + 200, 160), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse((100, 50, int(pw) + 100, 110), fill=(40, 45, 35, 70))
    return sh.filter(ImageFilter.GaussianBlur(22))


# ---------------------------------------------------------------- speaker motion
def speaker_track(st: Studio, meta: dict, dur: float):
    """per frame (top, height) of the cut-out: as big as fits under the cards, glides between sizes."""
    pmax = min(1150, W * 1.0 / meta["aspect"])
    ph = pmax; out = []
    for i in range(int(dur * FPS)):
        t = i / FPS
        b = st.bottom(t)
        target = pmax if b is None else clamp((ANCHOR - (b + 40)) / meta["base"], 700, pmax)
        ph += (target - ph) * 0.16
        out.append((ANCHOR - meta["base"] * ph, ph))
    return out


def _speaker_rgba(rb, ab, SW, SH, meta):
    rgbf = np.clip(np.frombuffer(rb, np.uint8).reshape(SH, SW, 3).astype(np.float32) * 1.04 + 3, 0, 255)
    m = np.frombuffer(ab, np.uint8).reshape(SH, SW).astype(np.float32)
    if meta["touches"]["left"] or meta["touches"]["right"]:
        xs = np.arange(SW); m = m * np.clip(np.minimum(xs, SW - 1 - xs) / 6, 0, 1)[None, :]
    m = m * np.clip((SH - np.arange(SH)) / 30, 0, 1)[:, None]
    return rgbf, m


# ---------------------------------------------------------------- render
def render(job: Path, scenes_p: Path, video: Path | None = None, out: Path | None = None, plan: bool = False) -> dict:
    spec = json.loads((job / "spec.json").read_text())
    scenes = json.loads(Path(scenes_p).read_text())
    st = Studio(scenes, spec, job)
    if plan:
        lines = [f"{s['t0']:5.1f}–{s['t1']:5.1f} с  {s['type']:10s} " + " · ".join(
            str(s[k]) for k in ("tag", "bold", "script", "name", "role", "small", "big", "header", "text", "title", "button") if s.get(k))
            + "".join(f"\n{'':22s}+ «{x.get('text')}» на {x['t']:.1f} с" for k in ("chips", "items", "rows", "pills") for x in s.get(k, []) or [])
            for s in st.sc]
        return {"plan": "\n".join(lines)}
    meta = prepare_speaker(job, spec, video)
    SW, SH = meta["SW"], meta["SH"]
    dur = spec["duration"]; N = int(dur * FPS)
    th = st.th
    bg = make_bg(th["bg"]); caps = _captions(spec, job)
    track = speaker_track(st, meta, dur)
    out = out or job / "studio" / "studio.mp4"
    audio = job / "final.mp4" if (job / "final.mp4").exists() else None
    vr = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(job / "studio/cut.mp4"), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    ar = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(job / "studio/alpha.mkv"), "-f", "rawvideo", "-pix_fmt", "gray", "-"], stdout=subprocess.PIPE)
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    cmd += (["-i", str(audio), "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "192k"] if audio else [])
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-shortest", "-movflags", "+faststart", str(out)]
    wr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    lastrb = lastab = None
    for i in range(N):
        t = i / FPS
        rb = vr.stdout.read(SW * SH * 3); ab = ar.stdout.read(SW * SH)
        if len(rb) < SW * SH * 3 or len(ab) < SW * SH: rb, ab = lastrb, lastab
        lastrb, lastab = rb, ab
        cv = bg.copy()
        st.draw(cv, t, behind=True)
        top, ph = track[i]; pw = ph * meta["aspect"]
        rgbf, m = _speaker_rgba(rb, ab, SW, SH, meta)
        p = Image.fromarray(np.dstack([rgbf, m]).astype(np.uint8), "RGBA").resize((int(pw), int(ph)), Image.BILINEAR)
        cv.alpha_composite(floor_shadow(pw), (int((W - pw) / 2) - 100, ANCHOR - 80))
        put(cv, p, W / 2, top + ph / 2)
        st.draw(cv, t)
        for a, b, s in caps:
            if a <= t < b:
                k = ease_out((t - a) / 0.12)
                put(cv, caption_img(s, th["caption"], th["caption_stroke"]), W / 2, th["caption_y"] + 10 * (1 - k), 0.94 + 0.06 * k, k)
                break
        if t < 0.2:  # glitch-in
            arr = np.array(cv)[..., :3].copy(); s_ = int(40 * (1 - t / 0.2))
            arr[..., 0] = np.roll(arr[..., 0], s_, 1); arr[..., 2] = np.roll(arr[..., 2], -s_, 1)
            arr = (arr * 0.4 + arr.mean(2, keepdims=True) * 0.6).astype(np.uint8)
            cv = Image.fromarray(arr).convert("RGBA")
        wr.stdin.write(cv.convert("RGB").tobytes())
    wr.stdin.close(); wr.wait()
    return {"video": str(out), "sec": round(dur, 1), "tips": shooting_tips(meta)}


# ---------------------------------------------------------------- CapCut: every part on its own layer
def capcut(job: Path, scenes_p: Path, name: str, draft_root: Path, media: Path, video: Path | None = None,
           maps: list[str] | None = None) -> dict:
    import pycapcut as cc
    from pycapcut import AudioMaterial, AudioSegment, ClipSettings, KeyframeProperty as KP, TextSegment, TextStyle, TrackType, VideoMaterial, VideoSegment
    spec = json.loads((job / "spec.json").read_text())
    st = Studio(json.loads(Path(scenes_p).read_text()), spec, job)
    meta = prepare_speaker(job, spec, video)
    SW, SH = meta["SW"], meta["SH"]; dur = spec["duration"]; N = int(dur * FPS); th = st.th
    media.mkdir(parents=True, exist_ok=True)
    bg = make_bg(th["bg"]); bg.alpha_composite(floor_shadow(1000), (-60, ANCHOR - 80)); bg.convert("RGB").save(media / "Фон.png")

    def clip(idx, a, b, fname, behind=False):
        def frames():
            for i in range(max(0, int(a * FPS)), min(N, int(b * FPS) + 1)):
                cv = Image.new("RGBA", (W, H), (0, 0, 0, 0)); st.draw(cv, i / FPS, behind=behind, only=idx); yield cv
        box = None
        for cv in frames():
            bb = cv.getbbox()
            if bb: box = bb if not box else (min(box[0], bb[0]), min(box[1], bb[1]), max(box[2], bb[2]), max(box[3], bb[3]))
        if not box: return None
        x0, y0, x1, y1 = box[0] // 2 * 2, box[1] // 2 * 2, (box[2] + 1) // 2 * 2, (box[3] + 1) // 2 * 2
        p = media / f"{fname}.mov"
        wr = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{x1 - x0}x{y1 - y0}",
                               "-r", str(FPS), "-i", "-", "-c:v", "png", str(p)], stdin=subprocess.PIPE)
        n = 0
        for cv in frames(): wr.stdin.write(cv.crop((x0, y0, x1, y1)).tobytes()); n += 1
        wr.stdin.close(); wr.wait()
        return dict(path=str(p), start=max(0, int(a * FPS)) / FPS, dur=n / FPS, cx=(x0 + x1) / 2, cy=(y0 + y1) / 2, w=x1 - x0, h=y1 - y0, behind=behind)

    clips = []
    for i, s in enumerate(st.sc):
        a, b = s["t0"] - 0.05, (dur if s["type"] == "end" else s["t1"] + 0.4)
        if s.get("giant"):
            c = clip(i, a, b, f"{i + 1:02d}a {s['type']} (за спиной)", behind=True)
            if c: clips.append(c)
        c = clip(i, a, b, f"{i + 1:02d} {s['type']}")
        if c: clips.append(c)
    # speaker: transparent PNG-in-MOV (CapCut reads its alpha; ProRes 4444 shows black there)
    pmov = media / "Спикер (вырезан).mov"
    lift = "clip(val*1.04+3\\,0\\,255)"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(job / "studio/cut.mp4"), "-i", str(job / "studio/alpha.mkv"),
                    "-filter_complex", f"[0:v]lutrgb=r={lift}:g={lift}:b={lift}[c];[c][1:v]alphamerge,format=rgba[o]",
                    "-map", "[o]", "-frames:v", str(N), "-c:v", "png", str(pmov)], check=True)  # native ffmpeg: fast
    audio = media / "Звук.m4a"
    src_audio = job / "final.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src_audio), "-vn", "-c:a", "aac", "-b:a", "192k", str(audio)], check=True)

    US = 1_000_000
    us = lambda x: int(round(x * US))
    tr = lambda s_, d_: cc.Timerange(us(s_), max(1, us(d_)))
    draft_root.mkdir(parents=True, exist_ok=True)
    sc = cc.DraftFolder(str(draft_root)).create_draft(name, W, H, FPS, allow_replace=True)
    for i, n in enumerate(["Фон", "За спиной", "Спикер", "Графика 1", "Графика 2"]):
        sc.add_track(TrackType.video, n, relative_index=i)
    sc.add_track(TrackType.text, "Субтитры"); sc.add_track(TrackType.audio, "Звук")
    D = N / FPS
    sc.add_segment(VideoSegment(VideoMaterial(str(media / "Фон.png")), tr(0, D)), "Фон")
    pm = VideoMaterial(str(pmov)); pdur = min(D, pm.duration / US)
    seg = VideoSegment(pm, tr(0, pdur), source_timerange=tr(0, pdur), volume=0)
    for i, (top, ph) in enumerate(speaker_track(st, meta, dur)):
        if i % 3 or i / FPS >= pdur: continue
        seg.add_keyframe(KP.uniform_scale, us(i / FPS), ph * meta["aspect"] / W)
        seg.add_keyframe(KP.position_y, us(i / FPS), -((top + ph / 2) - H / 2) / (H / 2))
    sc.add_segment(seg, "Спикер")
    ends = {"Графика 1": -1.0, "Графика 2": -1.0}
    for c in clips:
        m = VideoMaterial(c["path"]); d_ = min(c["dur"], m.duration / US)
        s_ = max(c["w"] / W, c["h"] / H)
        cs = ClipSettings(scale_x=s_, scale_y=s_, transform_x=(c["cx"] - W / 2) / (W / 2), transform_y=-(c["cy"] - H / 2) / (H / 2))
        if c["behind"]: trk = "За спиной"
        else:
            trk = "Графика 1" if ends["Графика 1"] <= c["start"] + 1e-3 else "Графика 2"; ends[trk] = c["start"] + d_
        sc.add_segment(VideoSegment(m, tr(c["start"], d_), source_timerange=tr(0, d_), clip_settings=cs), trk)
    style = TextStyle(size=10.0, bold=True, color=tuple(v / 255 for v in rgb(th["caption"])), align=1, auto_wrapping=True, max_line_width=0.8)
    border = cc.TextBorder(color=tuple(v / 255 for v in rgb(th["caption_stroke"])), width=45.0)
    prev = 0.0
    for a, b, s in _captions(spec, job):
        a = max(a, prev); b = min(b, D)
        if b - a < 0.05: continue
        sc.add_segment(TextSegment(s, tr(a, b - a), style=style, border=border,
                                   clip_settings=ClipSettings(transform_y=-(th["caption_y"] - H / 2) / (H / 2))), "Субтитры")
        prev = b
    am = AudioMaterial(str(audio))
    sc.add_segment(AudioSegment(am, tr(0, min(D, am.duration / US))), "Звук")
    sc.save()
    folder = draft_root / name
    content = folder / "draft_content.json"
    if content.exists():  # CapCut desktop for Mac reads draft_info.json
        (folder / "draft_info.json").write_text(content.read_text())
    for m_ in maps or []:  # paths as this shell sees them -> paths on the person's computer
        a_, b_ = m_.split("=", 1)
        for f in folder.glob("*.json"):
            f.write_text(f.read_text().replace(a_, b_))
    return {"capcut": str(folder), "media": str(media), "layers": len(clips) + 3}
