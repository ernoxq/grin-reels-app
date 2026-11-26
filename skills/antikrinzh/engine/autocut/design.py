# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
# Licensed, not sold: see LICENSE.md. Redistribution or resale is prohibited.
"""Дизайнер: slides.json -> finished PNG slides (edits happen in the chat; a CapCut draft only with --capcut).

Claude writes only the words and picks a layout per slide; this module does the
typography (auto-fit, wrapping, *accent* words), photos, page numbers and the
CapCut draft, where the background is one picture per slide and EVERY text block
is its own CapCut text layer (font, colour, size, words - all editable).

slides.json:
{"format": "carousel" | "story" | "post",
 "theme": {"preset": "clean|night|editorial|soft|bold", "bg": "#..", "ink": "#..", "accent": "#..",
           "title_font": "Manrope Bold", "body_font": "Manrope Medium", "align": "left|center",
           "uppercase": false, "handle": "@name", "numbers": true},
 "slides": [{"layout": "cover|text|list|quote|number|photo|end", "kicker": "", "title": "with *accent*",
             "body": "", "items": ["", ""], "author": "", "big": "30%", "photo": "/path.jpg",
             "focus": "top|center|bottom", "cta": "Сохрани"}]}
"""
from __future__ import annotations

import copy
import json
import re
import shutil
import time
import uuid
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from .paths import app_root

US = 1_000_000
SIZES = {"carousel": (1080, 1350), "post": (1080, 1350), "square": (1080, 1080), "story": (1080, 1920)}
# CapCut text "size" -> pixels on a 1080-wide canvas (measured on a real CapCut 9 draft: size 16 = 54 px)
CC_PX = 3.38

PRESETS = {
    "clean": {"bg": "#F3F1EC", "ink": "#141413", "accent": "#E8462F", "title_font": "Manrope Bold",
              "body_font": "Manrope Medium"},
    "night": {"bg": "#111111", "ink": "#F5F3EE", "accent": "#E4F23C", "title_font": "Montserrat Black",
              "body_font": "Inter Medium"},
    "editorial": {"bg": "#EEE8DC", "ink": "#1B1A17", "accent": "#C8361F", "title_font": "Playfair Display Bold",
                  "body_font": "Inter Regular"},
    "soft": {"bg": "#EFE6DA", "ink": "#3A2F28", "accent": "#A8744A", "title_font": "Cormorant Garamond SemiBold",
             "body_font": "Jost Regular"},
    "bold": {"bg": "#1F3D2B", "ink": "#FFFFFF", "accent": "#F2C230", "title_font": "Roboto Condensed Black",
             "body_font": "Source Sans 3 Medium", "uppercase": True},
}
DEFAULT = {"preset": "clean", "align": "left", "uppercase": False, "handle": "", "numbers": True}


# ------------------------------------------------------------------ fonts
def _fonts() -> list[Path]:
    root = app_root() / "library/fonts"
    return sorted(p for p in root.rglob("*") if p.suffix.lower() in (".ttf", ".otf"))


def find_font(spec: str) -> Path:
    """'Manrope Bold' / 'manrope/Manrope-Bold.ttf' / an absolute path -> a font file."""
    p = Path(spec)
    if p.is_absolute() and p.exists():
        return p
    q = app_root() / "library/fonts" / spec
    if q.exists():
        return q
    words = spec.replace("-", " ").replace("_", " ").split()
    weights = {"thin", "light", "regular", "medium", "semibold", "bold", "extrabold", "black", "italic"}
    w = [x.lower() for x in words if x.lower() in weights] or ["regular"]
    fam = "".join(x.lower() for x in words if x.lower() not in weights)
    best, score = None, -1
    for f in _fonts():
        key = (f.parent.name + f.stem).lower().replace("-", "").replace("_", "")
        if fam not in key:
            continue
        stem = f.stem.lower().split("-")[-1].replace("_", "")
        s = 10 if stem == "".join(w) else sum(2 for x in w if x in stem) - (1 if "italic" in stem and "italic" not in w else 0)
        if s > score:
            best, score = f, s
    if best is None:
        raise SystemExit(f"design: font '{spec}' not found (see library/fonts)")
    return best


_FC: dict = {}


def font(path: Path, px: int) -> ImageFont.FreeTypeFont:
    k = (str(path), px)
    if k not in _FC:
        _FC[k] = ImageFont.truetype(str(path), px)
    return _FC[k]


def rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


# ------------------------------------------------------------------ text layout with *accent* runs
def _tokens(text: str) -> list[list[tuple[str, bool]]]:
    """-> paragraphs, each a list of (word, accent)."""
    paras = []
    for para in text.split("\n"):
        out, acc = [], False
        for part in re.split(r"(\*)", para):
            if part == "*":
                acc = not acc
                continue
            out += [(w, acc) for w in part.split()]
        paras.append(out)
    return paras


def wrap(text: str, f: ImageFont.FreeTypeFont, width: int) -> list[list[tuple[str, bool]]]:
    lines = []
    sp = f.getlength(" ")
    for para in _tokens(text):
        cur, cw = [], 0.0
        for w, a in para:
            ww = f.getlength(w)
            if cur and cw + sp + ww > width:
                lines.append(cur)
                cur, cw = [], 0.0
            cw += (sp if cur else 0) + ww
            cur.append((w, a))
        lines.append(cur)
    return lines


class Block:
    """One text block: drawn into the PNG and written as one CapCut text layer."""

    def __init__(self, text: str, fpath: Path, px: int, color: str, accent: str, x: int, y: int, w: int,
                 align: str = "left", lh: float = 1.18, upper: bool = False, max_px: int | None = None,
                 max_h: int | None = None, min_px: int = 26, anchor: str = "top"):
        text = text.upper() if upper else text
        px = max_px or px
        while True:  # shrink until it fits the box
            f = font(fpath, px)
            lines = wrap(text, f, w)
            h = int(len(lines) * px * lh)
            widest = max((f.getlength(" ".join(t for t, _ in ln)) for ln in lines), default=0)
            if (max_h is None or h <= max_h) and widest <= w + 1 or px <= min_px:
                break
            px = int(px * 0.93)
        self.text, self.fpath, self.px, self.color, self.accent = text, fpath, px, color, accent
        self.lines, self.lh, self.align, self.w = lines, lh, align, w
        self.h = int(len(lines) * px * lh)
        self.x, self.y = x, (y - self.h if anchor == "bottom" else y)
        self.overflow = max_h is not None and self.h > max_h

    def draw(self, d: ImageDraw.ImageDraw) -> None:
        f = font(self.fpath, self.px)
        sp = f.getlength(" ")
        asc = f.getmetrics()[0]
        for i, ln in enumerate(self.lines):
            lw = f.getlength(" ".join(t for t, _ in ln))
            cx = self.x + (self.w - lw) / 2 if self.align == "center" else self.x
            ty = self.y + i * self.px * self.lh + (self.px * self.lh - self.px) / 2 + self.px - asc
            for t, a in ln:
                d.text((cx, ty), t, font=f, fill=rgb(self.accent if a else self.color))
                cx += f.getlength(t) + sp

    def capcut(self) -> dict:
        """Plain text with line breaks + colour ranges, and the box centre in CapCut coordinates."""
        f = font(self.fpath, self.px)
        s, ranges = "", []
        for i, ln in enumerate(self.lines):
            for j, (t, a) in enumerate(ln):
                if j:
                    s += " "
                ranges.append((len(s), len(s) + len(t), a))
                s += t
            if i < len(self.lines) - 1:
                s += "\n"
        widest = max((f.getlength(" ".join(t for t, _ in ln)) for ln in self.lines), default=0)
        left = self.x + ((self.w - widest) / 2 if self.align == "center" else 0)
        return {"text": s, "ranges": ranges, "font": str(self.fpath), "size": round(self.px / CC_PX, 2),
                "color": self.color, "accent": self.accent, "align": self.align,
                "cx": left + widest / 2, "cy": self.y + self.h / 2, "lh": self.lh}


# ------------------------------------------------------------------ pictures
def cover_fit(path: str, w: int, h: int, focus: str = "center") -> Image.Image:
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    cy = {"top": 0.2, "center": 0.5, "bottom": 0.8}.get(focus, 0.5)
    return ImageOps.fit(im, (w, h), Image.LANCZOS, centering=(0.5, cy))


def _round(im: Image.Image, r: int) -> Image.Image:
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, im.width - 1, im.height - 1), r, fill=255)
    im = im.convert("RGBA")
    im.putalpha(m)
    return im


def _shade(im: Image.Image, start: float = 0.35, strength: float = 0.82) -> Image.Image:
    """Dark gradient at the bottom so white text reads on any photo."""
    w, h = im.size
    g = Image.new("L", (1, h))
    for y in range(h):
        t = max(0.0, (y / h - start) / (1 - start))
        g.putpixel((0, y), int(255 * strength * t ** 1.3))
    black = Image.new("RGB", (w, h), (0, 0, 0))
    return Image.composite(black, im, g.resize((w, h)))


# ------------------------------------------------------------------ slides
def theme_of(spec: dict, taste: dict | None) -> dict:
    t = dict(DEFAULT)
    t.update((taste or {}).get("theme", taste or {}))
    t.update(spec.get("theme", {}))
    base = dict(PRESETS.get(t.get("preset", "clean"), PRESETS["clean"]))
    base.update({k: v for k, v in t.items() if v is not None})
    return base


def render_slide(s: dict, i: int, n: int, th: dict, W: int, H: int) -> tuple[Image.Image, list[Block], list[str]]:
    lay = s.get("layout", "text")
    story = H >= 1800
    M = 96
    top, bottom = (260, H - 360) if story else (96, H - 110)
    ink, acc, bgc = th["ink"], th["accent"], th["bg"]
    tf, bf = find_font(th["title_font"]), find_font(th["body_font"])
    up = bool(th.get("uppercase"))
    center = th.get("align") == "center"
    al = "center" if center else "left"
    bg = Image.new("RGB", (W, H), rgb(bgc))
    blocks: list[Block] = []
    warn: list[str] = []
    cw = W - 2 * M
    photo = s.get("photo")
    if photo and not Path(photo).exists():
        warn.append(f"slide {i + 1}: photo not found {photo}")
        photo = None

    def head(color: str) -> None:
        if th.get("numbers", True) and n > 1 and not story:
            blocks.append(Block(f"{i + 1:02d}/{n:02d}", bf, 28, color, acc, M, top - 40, 300, lh=1.0))
        if th.get("handle"):
            hb = Block(th["handle"], bf, 28, color, acc, W - M - 500, top - 40, 500, lh=1.0)
            hb.align = "right"
            f = font(bf, hb.px)
            hb.x = W - M - int(f.getlength(hb.text)) - 1
            blocks.append(hb)

    if lay == "cover":
        light = ink
        if photo:
            bg = _shade(cover_fit(photo, W, H, s.get("focus", "center")))
            light = "#FFFFFF"
        head(light)
        y_end = bottom - 70
        if s.get("body"):
            b = Block(s["body"], bf, 40, light, acc, M, y_end, cw, al, 1.3, max_h=240, anchor="bottom")
            blocks.append(b)
            y_end = b.y - 36
        t = Block(s.get("title", ""), tf, 128, light, acc, M, y_end, cw, al, 1.05, up, max_h=int((y_end - top) * 0.8),
                  min_px=60, anchor="bottom")
        blocks.append(t)
        if s.get("kicker"):
            blocks.append(Block(s["kicker"], bf, 32, acc, acc, M, t.y - 58, cw, al, 1.0, True))
        if n > 1 and not story:
            blocks.append(Block("листай", bf, 28, light, acc, W - M - 200, bottom - 4, 160, lh=1.0))
            d = ImageDraw.Draw(bg)
            ax, ay = W - M - 28, bottom + 14
            d.line((ax - 30, ay, ax + 24, ay), fill=rgb(light), width=3)
            d.line((ax + 10, ay - 12, ax + 24, ay), fill=rgb(light), width=3)
            d.line((ax + 10, ay + 12, ax + 24, ay), fill=rgb(light), width=3)
    elif lay == "photo":
        head(ink)
        ph = int((bottom - top) * 0.58)
        if photo:
            pic = _round(cover_fit(photo, cw, ph, s.get("focus", "center")), 28)
            bg.paste(pic, (M, top + 20), pic)
        else:
            ImageDraw.Draw(bg).rounded_rectangle((M, top + 20, M + cw, top + 20 + ph), 28, outline=rgb(ink), width=2)
            warn.append(f"slide {i + 1}: layout photo without a photo")
        y = top + 20 + ph + 48
        t = Block(s.get("title", ""), tf, 64, ink, acc, M, y, cw, al, 1.1, up, max_h=170, min_px=40)
        blocks.append(t)
        if s.get("body"):
            blocks.append(Block(s["body"], bf, 36, ink, acc, M, t.y + t.h + 22, cw, al, 1.3, max_h=bottom - t.y - t.h - 22))
    elif lay == "quote":
        head(ink)
        q = Block("“", find_font("Playfair Display Bold"), 300, acc, acc, M, top + 10, cw, al, 1.0)
        blocks.append(q)
        t = Block(s.get("title") or s.get("body", ""), tf, 76, ink, acc, M, top + 250, cw, al, 1.18, False,
                  max_h=bottom - top - 420, min_px=40)
        blocks.append(t)
        if s.get("author"):
            blocks.append(Block("— " + s["author"] if not s["author"].startswith(("—", "-")) else s["author"],
                                bf, 36, ink, acc, M, t.y + t.h + 44, cw, al, 1.2))
    elif lay == "number":
        head(ink)
        big = Block(s.get("big", ""), tf, 300, acc, acc, M, top + 40, cw, al, 1.0, max_h=330, min_px=120)
        blocks.append(big)
        y = big.y + big.h + 30
        if s.get("title"):
            t = Block(s["title"], tf, 64, ink, acc, M, y, cw, al, 1.12, up, max_h=230, min_px=40)
            blocks.append(t)
            y = t.y + t.h + 30
        if s.get("body"):
            blocks.append(Block(s["body"], bf, 40, ink, acc, M, y, cw, al, 1.32, max_h=bottom - y))
    elif lay == "list":
        head(ink)
        t = Block(s.get("title", ""), tf, 76, ink, acc, M, top + 30, cw, al, 1.1, up, max_h=260, min_px=44)
        blocks.append(t)
        items = s.get("items", [])
        y = t.y + t.h + 56
        room = bottom - y
        per = room / max(1, len(items))
        px = int(min(44, max(28, per / 2.6)))
        d = ImageDraw.Draw(bg)
        for k, it in enumerate(items):
            num = Block(f"{k + 1:02d}", tf, px, acc, acc, M, y, 90, lh=1.3)
            b = Block(it, bf, px, ink, acc, M + 100, y, cw - 100, "left", 1.3, max_h=int(per - 34), min_px=24)
            blocks += [num, b]
            y += max(num.h, b.h) + 34
            if k < len(items) - 1:
                d.line((M + 100, y - 18, W - M, y - 18), fill=rgb(_mix(ink, bgc, 0.82)), width=2)
        if y > bottom + 10:
            warn.append(f"slide {i + 1}: list is too long, cut an item")
    elif lay == "end":
        head(ink)
        mid = top + int((bottom - top) * 0.30)
        t = Block(s.get("title", ""), tf, 96, ink, acc, M, mid, cw, al, 1.08, up, max_h=360, min_px=50)
        blocks.append(t)
        y = t.y + t.h + 36
        if s.get("body"):
            b = Block(s["body"], bf, 40, ink, acc, M, y, cw, al, 1.3, max_h=220)
            blocks.append(b)
            y = b.y + b.h + 60
        if s.get("cta"):
            f = font(bf, 40)
            bw = int(f.getlength(s["cta"])) + 110
            bx = (W - bw) // 2 if center else M
            ImageDraw.Draw(bg).rounded_rectangle((bx, y, bx + bw, y + 100), 50, fill=rgb(acc))
            blocks.append(Block(s["cta"], bf, 40, _contrast(acc), acc, bx + 55, y + 26, bw - 90, "left", 1.2))
    else:  # text
        head(ink)
        y = top + 30
        if s.get("kicker"):
            k = Block(s["kicker"], bf, 30, acc, acc, M, y, cw, al, 1.0, True)
            blocks.append(k)
            y += k.h + 26
        t = Block(s.get("title", ""), tf, 92, ink, acc, M, y, cw, al, 1.1, up, max_h=420, min_px=44)
        blocks.append(t)
        y = t.y + t.h + 44
        if s.get("body"):
            blocks.append(Block(s["body"], bf, 46, ink, acc, M, y, cw, al, 1.36, max_h=bottom - y, min_px=28))
    if lay in ("quote", "number"):  # little text: sit it at the optical centre instead of the top
        body = [b for b in blocks if b.y >= top]
        if body:
            y0, y1 = min(b.y for b in body), max(b.y + b.h for b in body)
            shift = int(top + (bottom - top - (y1 - y0)) * 0.42 - y0)
            if shift > 0:
                for b in body:
                    b.y += shift
    for b in blocks:
        if b.overflow:
            warn.append(f"slide {i + 1}: text too long ('{b.text[:30]}…'), shorten it")
    return bg, blocks, warn


def _mix(a: str, b: str, t: float) -> str:
    x, y = rgb(a), rgb(b)
    return "#%02X%02X%02X" % tuple(int(x[k] * (1 - t) + y[k] * t) for k in range(3))


def _contrast(h: str) -> str:
    r, g, b = rgb(h)
    return "#111111" if 0.299 * r + 0.587 * g + 0.114 * b > 150 else "#FFFFFF"


# ------------------------------------------------------------------ CapCut draft
def _uid() -> str:
    return str(uuid.uuid4()).upper()


def write_capcut(slides: list[tuple[str, list[dict]]], W: int, H: int, out_dir: Path, mac_dir: str,
                 mapper, name: str, sec: float = 3.0) -> Path:
    """slides = [(background png, [text dicts from Block.capcut()]), ...] -> CapCut 9 draft folder."""
    from .nle import _probe
    tpl = json.loads((app_root() / "library/capcut/template_9x.json").read_text())
    home = mac_dir.split("/Movies/")[0] if "/Movies/" in mac_dir else "/Users/user"
    tpl = json.loads(json.dumps(tpl).replace("__HOME__", home))
    mats: dict[str, list] = {k: [] for k in tpl["materials_keys"]}

    def extras(pack: dict) -> list[str]:
        refs = []
        for e in pack["extras"]:
            m = copy.deepcopy(e["m"])
            m["id"] = _uid()
            if e["kind"] == "speeds":
                m["speed"] = 1.0
            if e["kind"] == "material_animations":
                m["animations"] = []
            mats.setdefault(e["kind"], []).append(m)
            refs.append(m["id"])
        return refs

    def img_seg(path: str, start: float) -> dict:
        info = _probe(path)
        m = copy.deepcopy(tpl["video_material"])
        mid = _uid()
        m.update({"id": mid, "path": mapper(path), "material_name": Path(path).name, "width": info["w"],
                  "height": info["h"], "duration": 10800 * US, "type": "photo", "has_audio": False,
                  "local_material_id": str(uuid.uuid4())})
        mats["videos"].append(m)
        s = copy.deepcopy(tpl["video"]["segment"])
        s.update({"id": _uid(), "material_id": mid, "speed": 1.0, "volume": 0.0, "extra_material_refs": extras(tpl["video"]),
                  "render_index": 0, "track_render_index": 0, "keyframe_refs": [], "common_keyframes": [],
                  "target_timerange": {"start": int(start * US), "duration": int(sec * US)}, "source_timerange": None})
        s["clip"]["scale"] = {"x": 1.0, "y": 1.0}
        s["clip"]["transform"] = {"x": 0.0, "y": 0.0}
        return s

    def col(h: str) -> list[float]:
        return [c / 255 for c in rgb(h)]

    def text_seg(t: dict, start: float, render: int) -> dict:
        m = copy.deepcopy(tpl["text_material"])
        mid = _uid()
        fp = mapper(t["font"])
        styles = [{"fill": {"content": {"solid": {"color": col(t["accent"] if a else t["color"])}, "render_type": "solid"}},
                   "range": [a0, a1], "size": t["size"], "font": {"path": fp, "id": ""}, "useLetterColor": True}
                  for a0, a1, a in t["ranges"]] or [
                  {"fill": {"content": {"solid": {"color": col(t["color"])}, "render_type": "solid"}},
                   "range": [0, len(t["text"])], "size": t["size"], "font": {"path": fp, "id": ""}}]
        m.update({"id": mid, "content": json.dumps({"styles": styles, "text": t["text"]}, ensure_ascii=False),
                  "base_content": "", "font_size": t["size"], "font_path": fp, "font_resource_id": "", "font_id": "",
                  "font_name": Path(t["font"]).stem, "fonts": [], "text_color": t["color"].lower(),
                  "alignment": {"left": 0, "center": 1, "right": 2}.get(t["align"], 0),
                  "border_width": 0.0, "fixed_width": -1.0, "line_max_width": 1.0, "type": "text",
                  "line_spacing": round(max(0.0, t["lh"] - 1.2) * 0.5, 3), "recognize_text": "",
                  "words": {"end_time": [], "start_time": [], "text": []},
                  "current_words": {"end_time": [], "start_time": [], "text": []}})
        mats["texts"].append(m)
        s = copy.deepcopy(tpl["text"]["segment"])
        s.update({"id": _uid(), "material_id": mid, "extra_material_refs": extras(tpl["text"]),
                  "render_index": render, "track_render_index": render,
                  "target_timerange": {"start": int(start * US), "duration": int(sec * US)}})
        s["clip"]["transform"] = {"x": round((t["cx"] - W / 2) / (W / 2), 4), "y": round((H / 2 - t["cy"]) / (H / 2), 4)}
        s["clip"]["scale"] = {"x": 1.0, "y": 1.0}
        return s

    def track(kind: str, segs: list) -> dict:
        tr = copy.deepcopy(tpl["video_track" if kind == "video" else "text_track"])
        tr.update({"id": _uid(), "segments": segs, "attribute": 0})
        return tr

    tracks = [track("video", [img_seg(bgp, k * sec) for k, (bgp, _) in enumerate(slides)])]
    depth = max((len(t) for _, t in slides), default=0)
    for j in range(depth):  # j-th text block of every slide on text track j (blocks of one slide overlap in time)
        segs = [text_seg(t[j], k * sec, 14000 + j) for k, (_, t) in enumerate(slides) if j < len(t)]
        tracks.append(track("text", segs))
    total = int(len(slides) * sec * US)
    d = copy.deepcopy(tpl["draft"])
    now = int(time.time())
    d.update({"id": _uid(), "name": name, "duration": total, "tracks": tracks, "materials": mats, "fps": 30.0,
              "canvas_config": {"background": None, "height": H, "ratio": "original", "width": W},
              "create_time": now, "update_time": now, "path": "", "cover": None})
    for k in ("platform", "last_modified_platform"):
        if isinstance(d.get(k), dict):
            d[k].update({"device_id": "", "hard_disk_id": "", "mac_address": ""})
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "draft_info.json").write_text(json.dumps(d, ensure_ascii=False))
    meta = copy.deepcopy(tpl["meta"])
    meta.update({"draft_id": _uid(), "draft_name": name, "draft_fold_path": mac_dir,
                 "draft_root_path": mac_dir.rsplit("/", 1)[0], "draft_cover": "",
                 "tm_draft_create": now * US, "tm_draft_modified": now * US, "tm_duration": total,
                 "draft_materials": [], "draft_timeline_materials_size_": 0})
    (out_dir / "draft_meta_info.json").write_text(json.dumps(meta, ensure_ascii=False))
    return out_dir


# ------------------------------------------------------------------ one call
def design(spec_path: Path, out: Path, taste: Path | None = None, name: str | None = None,
           capcut_root: Path | None = None, maps: list[str] | None = None, capcut: bool = False) -> dict:
    from .nle import _mapper
    spec = json.loads(Path(spec_path).read_text())
    tst = json.loads(Path(taste).read_text()) if taste else None
    th = theme_of(spec, tst)
    W, H = SIZES.get(spec.get("format", "carousel"), SIZES["carousel"])
    name = name or spec.get("name") or time.strftime("Карусель %d.%m %H-%M")
    out.mkdir(parents=True, exist_ok=True)
    proj = out / f"{name} - проект"
    layers = proj / "слои"
    (layers if capcut else proj).mkdir(parents=True, exist_ok=True)
    pngs, cc_slides, warns, fonts = [], [], [], set()
    n = len(spec["slides"])
    for i, s in enumerate(spec["slides"]):
        bg, blocks, w = render_slide(s, i, n, th, W, H)
        warns += w
        bgp = layers / f"фон_{i + 1:02d}.png"
        if capcut:
            bg.save(bgp)
        full = bg.copy()
        d = ImageDraw.Draw(full)
        for b in blocks:
            b.draw(d)
            fonts.add(b.fpath)
        p = out / f"{name} {i + 1:02d}.png"
        full.save(p)
        pngs.append(p)
        cc_slides.append((str(bgp), [b.capcut() for b in blocks]))
    # fonts next to the project so CapCut finds the exact typeface
    fdir = proj / "шрифты"
    fmap = {}
    for f in (fonts if capcut else []):
        fdir.mkdir(exist_ok=True)
        shutil.copy2(f, fdir / f.name)
        fmap[str(f)] = str(fdir / f.name)
    for _, ts in cc_slides:
        for t in ts:
            t["font"] = fmap.get(t["font"], t["font"])
    # one small sheet for a single look
    tw = 270
    th_ = int(tw * H / W)
    cols = min(5, n)
    sheet = Image.new("RGB", (cols * (tw + 8) + 8, ((n + cols - 1) // cols) * (th_ + 8) + 8), "white")
    for i, p in enumerate(pngs):
        sheet.paste(Image.open(p).resize((tw, th_), Image.LANCZOS), (8 + (i % cols) * (tw + 8), 8 + (i // cols) * (th_ + 8)))
    sheet.save(proj / "sheet.png")
    res = {"slides": [str(p) for p in pngs], "sheet": str(proj / "sheet.png"), "size": f"{W}x{H}", "warnings": warns}
    if capcut:
        mapper = _mapper(maps or [])
        if capcut_root and Path(capcut_root).exists():
            dd = Path(capcut_root) / name
            res["capcut"] = name
        else:
            dd = proj / "CapCut" / name
            res["capcut_folder"] = str(dd)
        write_capcut(cc_slides, W, H, dd, mapper(str(dd)), mapper, name)
    (proj / "slides.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1))
    return res
