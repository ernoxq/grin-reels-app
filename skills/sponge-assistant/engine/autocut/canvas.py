# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
# Licensed, not sold: see LICENSE.md. Redistribution or resale is prohibited.
"""Дизайнер -> Claude's own Design canvas (the editor the person already knows).

Writes <root>/project/canvas.json + one artboard per slide (Main.dc.html, Slide-02.dc.html, …).
Every text is its own absolutely positioned element with inline styles, so on the canvas
the person drags it, retypes it and changes font, size and colour by hand. Photos and
shapes are one picture per slide (<root>/assets/slide_NN.png), uploaded as canvas assets;
`canvas-fill` then puts their /_blob/ urls into the artboards. Claude only sends files:
it never writes or reads the artboards, so they cost no tokens.
"""
from __future__ import annotations

import html
import json
import re
import time
from pathlib import Path

GOOGLE = {"manrope": "Manrope", "montserrat": "Montserrat", "inter": "Inter", "playfairdisplay": "Playfair Display",
          "cormorantgaramond": "Cormorant Garamond", "jost": "Jost", "robotocondensed": "Roboto Condensed",
          "sourcesans3": "Source Sans 3", "prata": "Prata", "notoserifdisplay": "Noto Serif Display",
          "ptserif": "PT Serif", "oldstandardtt": "Old Standard TT", "lobster": "Lobster", "comforter": "Comforter",
          "greatvibes": "Great Vibes", "marckscript": "Marck Script", "didactgothic": "Didact Gothic",
          "podkova": "Podkova", "orelegaone": "Oleo Script", "playfairdisplaysc": "Playfair Display SC"}
WEIGHTS = {"thin": 100, "extralight": 200, "light": 300, "regular": 400, "medium": 500, "semibold": 600,
           "bold": 700, "extrabold": 800, "black": 900}


def face(p: Path) -> tuple[str, int, bool]:
    """font file -> (Google family, weight, italic)"""
    fam = GOOGLE.get(p.parent.name.lower()) or re.sub(r"(?<!^)(?=[A-Z])", " ", p.stem.split("-")[0])
    st = p.stem.split("-")[-1].lower() if "-" in p.stem else "regular"
    italic = "italic" in st
    st = st.replace("italic", "") or "regular"
    return fam, WEIGHTS.get(st, 400), italic


def _text(b) -> str:
    out, acc = [], False
    for part in re.split(r"(\*)", b.text):
        if part == "*":
            acc = not acc
            continue
        if part:
            t = html.escape(part)
            out.append(f'<span style="color: {b.accent}">{t}</span>' if acc else t)
    return "".join(out)


def write_canvas(root: Path, name: str, W: int, H: int, bg: str, overlays: list, texts: list) -> dict:
    proj = root / "project"
    assets = root / "assets"
    proj.mkdir(parents=True, exist_ok=True)
    assets.mkdir(parents=True, exist_ok=True)
    files, need = [], []
    boards, order = {}, []
    for i, (ov, blocks) in enumerate(zip(overlays, texts)):
        fn = "Main.dc.html" if i == 0 else f"Slide-{i + 1:02d}.dc.html"
        fams: dict[str, set] = {}
        els = []
        if ov.getbbox():  # something drawn (photo, line, button) -> one picture under the texts
            a = f"slide_{i + 1:02d}.png"
            ov.save(assets / a)
            need.append(str(assets / a))
            els.append(f'<img src="__ASSET_{a}__" alt="" style="position: absolute; left: 0px; top: 0px; width: {W}px; '
                       f'height: {H}px; object-fit: cover">')
        for b in blocks:
            fam, wt, it = face(Path(b.fpath))
            fams.setdefault(fam, set()).add((wt, it))
            els.append(f'<div style="position: absolute; left: {round(b.x)}px; top: {round(b.y)}px; width: {round(b.w)}px; '
                       f'margin: 0px; font-family: \'{fam}\', sans-serif; font-weight: {wt}; '
                       f'font-style: {"italic" if it else "normal"}; font-size: {b.px}px; line-height: {b.lh}; '
                       f'color: {b.color}; text-align: {b.align}; white-space: pre-wrap">{_text(b)}</div>')
        q = "&amp;".join("family=" + f.replace(" ", "+") + ":ital,wght@" + ";".join(f"{1 if it else 0},{w}" for w, it in sorted(v, key=lambda x: (x[1], x[0])))
                         for f, v in sorted(fams.items()))
        link = f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?{q}&amp;display=swap">' if q else ""
        page = f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Слайд {i + 1}</title>
<script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
{link}
<style>
body{{margin:0}}
</style>
</helmet>
<div style="width: {W}px; height: {H}px; position: relative; overflow: hidden; box-sizing: border-box; background: {bg}">
{chr(10).join(els)}
</div>
</x-dc>
<script type="text/x-dc" data-dc-script data-props='{{"$preview":{{"width":{W},"height":{H}}}}}'>
class Component extends DCLogic {{
renderVals() {{
return {{}};
}}
}}
</script>
</body>
</html>
"""
        (proj / fn).write_text(page, encoding="utf-8")
        files.append(str(proj / fn))
        boards[fn] = {"x": i * (W + 80), "y": 0, "w": W, "h": H, "title": f"Слайд {i + 1}"}
        order.append(fn)
    idx = {"v": 3, "createdOnFiles": {"v": 1, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, "title": name,
           "launch": {"view": "canvas"}, "pages": [], "boards": boards, "order": order, "notes": {}, "designSystems": []}
    (proj / "canvas.json").write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"root": str(root), "index": str(proj / "canvas.json"), "artboards": files, "upload_first": need}


def fill(root: Path, pairs: list[str]) -> dict:
    """slide_01.png=/_blob/xyz … -> put the uploaded asset urls into the artboards."""
    m = dict(p.split("=", 1) for p in pairs)
    done = []
    for f in sorted((root / "project").glob("*.dc.html")):
        s = f.read_text(encoding="utf-8")
        s2 = re.sub(r"__ASSET_(slide_\d+\.png)__", lambda x: m.get(x.group(1), x.group(0)), s)
        if s2 != s:
            f.write_text(s2, encoding="utf-8")
            done.append(f.name)
        if "__ASSET_" in s2:
            raise SystemExit(f"canvas-fill: no url for an asset in {f.name}")
    return {"filled": done}
