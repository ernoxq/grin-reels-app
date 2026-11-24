# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
# Licensed, not sold: see LICENSE.md. Redistribution or resale is prohibited.
"""Simple choices from the app (fonts, colour, music, LUT, sticker) applied on top of a style.

The person never edits JSON: the app sends a few plain choices, this file turns them into
style settings. Everything they drop into "Мои файлы" lands in library/ and shows up here.
"""
from __future__ import annotations

import copy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "library"
KINDS = {  # app tab -> folder + accepted extensions
    "fonts": ("fonts", {".ttf", ".otf"}),
    "music": ("music", {".mp3", ".wav", ".m4a", ".aac", ".aiff", ".flac"}),
    "stickers": ("stickers", {".png", ".webp"}),
    "luts": ("luts", {".cube"}),
}


def font_family(path: Path) -> str:
    """The family name a renderer needs (read from inside the font file, not the file name)."""
    from fontTools.ttLib import TTFont
    t = TTFont(str(path), lazy=True)
    for nid in (16, 1):
        rec = t["name"].getName(nid, 3, 1, 0x409) or t["name"].getName(nid, 1, 0, 0)
        if rec:
            return str(rec)
    return path.stem


def list_library() -> dict:
    out = {}
    for kind, (folder, exts) in KINDS.items():
        base = LIB / folder
        files = sorted(p for p in base.rglob("*") if p.suffix.lower() in exts) if base.exists() else []
        out[kind] = [{"id": str(p.relative_to(LIB)), "name": p.stem.replace("_", " ")} for p in files]
    names = {"warm_intro": "Тёплый интро (GRIN)"}
    out["styles"] = [{"id": p.name, "name": names.get(p.stem) or ("По референсу: " + p.stem[4:].replace("_", " ")
                                                                if p.stem.startswith("ref_") else p.stem.replace("_", " "))}
                     for p in sorted((ROOT / "styles").glob("*.json")) if not p.stem.startswith("test")]
    return out


def apply_choices(style: dict, ch: dict) -> dict:
    s = copy.deepcopy(style)
    fonts = set(s.get("fonts", []))
    if f := ch.get("title_font"):
        fam = font_family(LIB / f)
        s["title"]["template"]["style"]["font_name"] = fam
        fonts.add(f)
    if f := ch.get("caption_font"):
        s["caption_style"]["font_name"] = font_family(LIB / f)
        fonts.add(f)
    s["fonts"] = sorted(fonts)
    if c := ch.get("accent"):
        cols = s["title"]["template"].get("colors", ["#FFFFFF", "#FFFFFF"])
        s["title"]["template"]["colors"] = [cols[0], c]
    if (m := ch.get("music")) is not None:
        s["music"] = dict(s.get("music", {}), asset=m or None)
        if ch.get("music_db") not in (None, ""):
            s["music"]["gain_db"] = float(ch["music_db"])
    lut = ch.get("lut")
    if lut:  # an explicit choice replaces a colour learned from a reference reel
        s["aroll_look"].pop("lut_ref", None)
        s.get("broll_look", {}).pop("lut_ref", None)
    if lut == "none":
        s["aroll_look"]["lut"] = None
        s["aroll_look"].pop("input_luma", None)
        s["broll_look"] = {"bw": s["broll_look"].get("bw")}
    elif lut:
        s["aroll_look"]["lut"] = lut
        s["aroll_look"].pop("input_luma", None)  # exposure target belongs to the original LUT
        s["broll_look"]["color"] = lut
    if (st := ch.get("cta")) is not None:
        if st == "none":
            s.pop("sticker", None)
        elif st:
            s.setdefault("sticker", {"width": 0.366, "x": 0.0, "y": -0.2625, "pop": 0.4, "capcut_scale": 0.37})
            s["sticker"]["asset"] = st
    cap = ch.get("captions")  # phrase | words | words_box
    if cap:
        cs = s["caption_style"]
        if cap == "phrase":
            cs.update(mode="phrase", uppercase=False, pop=False)
            cs.pop("box", None)
        else:
            cs.update(mode="words", uppercase=True, pop=True, size=max(cs.get("size", 67), 82),
                      highlight=ch.get("accent") or cs.get("highlight"))
            semi = LIB / "fonts/Montserrat-SemiBold.ttf"
            if not ch.get("caption_font") and semi.exists():
                cs["font_name"] = font_family(semi)
                s["fonts"] = sorted(set(s["fonts"]) | {"fonts/Montserrat-SemiBold.ttf"})
            if cap == "words_box":
                cs["box"] = {"color": "#000000", "alpha": 0.55, "pad": 14}
            else:
                cs.pop("box", None)
    if ch.get("shadow") is False:
        s.pop("shadow", None)
    return s
