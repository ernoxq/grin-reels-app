# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
# Licensed, not sold: see LICENSE.md. Redistribution or resale is prohibited.
"""Дизайнер -> one self-contained HTML editor (opens in Claude's side panel or any browser).

Every text is a layer: drag it, edit it, change font / size / colour / alignment /
line height / width, change the slide colour, add or delete text, undo, then download
PNGs. Fonts (subset to Latin + Romanian + Cyrillic) and the slide pictures are
embedded, so the file works offline. Claude never reads this file: zero tokens.
"""
from __future__ import annotations

import base64
import io
import json
from pathlib import Path

from PIL import Image

from .paths import app_root

# fonts offered in the editor's font menu (plus whatever the slides already use)
MENU = ["manrope/Manrope-Bold.ttf", "manrope/Manrope-Medium.ttf", "montserrat/Montserrat-Black.ttf",
        "montserrat/Montserrat-Medium.ttf", "inter/Inter-Bold.ttf", "inter/Inter-Regular.ttf",
        "playfairdisplay/PlayfairDisplay-Bold.ttf", "playfairdisplay/PlayfairDisplay-Italic.ttf",
        "cormorantgaramond/CormorantGaramond-SemiBold.ttf", "jost/Jost-Medium.ttf", "jost/Jost-Regular.ttf",
        "robotocondensed/RobotoCondensed-Black.ttf", "sourcesans3/SourceSans3-Medium.ttf", "prata/Prata-Regular.ttf"]
UNICODES = (list(range(0x20, 0x7F)) + list(range(0xA0, 0x180)) + list(range(0x218, 0x21C)) + list(range(0x400, 0x460))
            + list(range(0x2010, 0x2027)) + [0x2030, 0x2039, 0x203A, 0x20AC, 0x20BD, 0x2116, 0x2122, 0x2192, 0x2190, 0x2713])


def family(p: Path) -> str:
    return p.stem.replace("-Web", "").replace("_", " ").replace("-", " ")


def _font_b64(p: Path) -> str:
    try:
        from fontTools import subset
        from fontTools.ttLib import TTFont
        f = TTFont(str(p))
        sub = subset.Subsetter(subset.Options())
        sub.populate(unicodes=UNICODES)
        sub.subset(f)
        f.flavor = "woff"
        buf = io.BytesIO()
        f.save(buf)
        return "data:font/woff;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:  # no fontTools: embed the whole file
        return "data:font/ttf;base64," + base64.b64encode(p.read_bytes()).decode()


def _img_b64(im: Image.Image) -> str:
    buf = io.BytesIO()
    if im.getextrema()[3][0] == 255:  # fully opaque (a photo) -> JPEG, much smaller
        im.convert("RGB").save(buf, "JPEG", quality=90)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    im.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def write_editor(out: Path, name: str, W: int, H: int, bg: str, overlays: list, texts: list, used: set) -> Path:
    fonts = {}
    for p in list(used) + [app_root() / "library/fonts" / m for m in MENU]:
        p = Path(p)
        if p.exists() and family(p) not in fonts:
            fonts[family(p)] = _font_b64(p)
    slides = []
    for ov, blocks in zip(overlays, texts):
        slides.append({"bg": bg, "img": _img_b64(ov), "layers": [
            {"t": b.text, "f": family(b.fpath), "px": b.px, "c": b.color, "a": b.accent, "x": round(b.x), "y": round(b.y),
             "w": round(b.w), "al": b.align, "lh": b.lh} for b in blocks]})
    data = {"name": name, "W": W, "H": H, "slides": slides}
    css = "".join(f'@font-face{{font-family:"{k}";src:url({v});font-display:block}}' for k, v in fonts.items())
    html = (Path(__file__).with_name("editor.html").read_text(encoding="utf-8")
            .replace("/*FONTS*/", css)
            .replace("/*DATA*/null", json.dumps(data, ensure_ascii=False))
            .replace("/*FAMILIES*/[]", json.dumps(sorted(fonts), ensure_ascii=False))
            .replace("__TITLE__", name))
    out.write_text(html, encoding="utf-8")
    return out
