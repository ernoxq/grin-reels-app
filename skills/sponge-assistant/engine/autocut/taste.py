# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
# Licensed, not sold: see LICENSE.md. Redistribution or resale is prohibited.
"""Губка Спанч for pictures: learn a design taste from 1-10 references
(stories, posts, carousel slides, screenshots; videos give 3 frames each).

Measured here: the palette (background / text / accent) and how light, airy and
text-heavy the references are. Claude then looks at ONE sheet and fills in only
what eyes can judge (fonts, alignment, case, layouts). Result: a small
taste_<name>.json that the Дизайнер uses for every new carousel or story.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from .paths import app_root
from .reflearn import _dur, _frame

VIDEO = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}


def _images(paths: list[Path]) -> list[tuple[str, Image.Image]]:
    out = []
    for p in paths:
        if p.suffix.lower() in VIDEO:
            d = _dur(p)
            out += [(f"{p.name} {t:.0f}s", _frame(p, t, 540)) for t in (0.5, d * 0.45, max(0.0, d - 1.0))]
        else:
            im = ImageOps.exif_transpose(Image.open(p)).convert("RGB")
            im.thumbnail((540, 960))
            out.append((p.name, im))
    return out


def _hex(c) -> str:
    return "#%02X%02X%02X" % tuple(int(x) for x in c)


def _lum(c) -> float:
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def _palette(ims: list[Image.Image]) -> list[tuple[tuple[int, int, int], float]]:
    px = np.concatenate([np.asarray(im.resize((240, int(240 * im.height / im.width)), Image.NEAREST)).reshape(-1, 3) for im in ims])
    q = Image.fromarray(px.reshape(1, -1, 3).astype("uint8")).quantize(8, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()[:24]
    cnt = np.bincount(np.asarray(q).ravel(), minlength=8) / q.width
    cols = [((pal[3 * i], pal[3 * i + 1], pal[3 * i + 2]), float(cnt[i])) for i in range(8) if cnt[i] > 0]
    return sorted(cols, key=lambda x: -x[1])


def learn_taste(paths: list[Path], name: str, out: Path | None = None) -> dict:
    ims = _images(paths)[:12]
    if not ims:
        raise SystemExit("taste: no pictures")
    pal = _palette([im for _, im in ims])
    bg = pal[0][0]
    px = np.concatenate([np.asarray(im.resize((240, int(240 * im.height / im.width)), Image.NEAREST)).reshape(-1, 3)
                         for _, im in ims]).astype(float)
    lum = px @ np.array([0.299, 0.587, 0.114])
    hsv = np.concatenate([np.asarray(im.resize((240, int(240 * im.height / im.width)), Image.NEAREST).convert("HSV"))
                          .reshape(-1, 3) for _, im in ims]).astype(float) / 255
    far = np.abs(lum - _lum(bg)) > 110
    grey = hsv[:, 1] < 0.35
    sel = px[far & grey] if (far & grey).sum() > 50 else px[far] if far.sum() > 50 else None
    ink = tuple(np.median(sel, axis=0)) if sel is not None else ((17, 17, 17) if _lum(bg) > 128 else (245, 245, 245))
    vivid = (hsv[:, 1] > 0.45) & (hsv[:, 2] > 0.35)
    if vivid.mean() > 0.001:
        v = px[vivid].astype("uint8").reshape(1, -1, 3)
        q = Image.fromarray(v).quantize(6, method=Image.Quantize.MEDIANCUT)
        cnt = np.bincount(np.asarray(q).ravel(), minlength=6)
        pal3 = [tuple(q.getpalette()[3 * i:3 * i + 3]) for i in range(6)]

        def vivid_score(i):  # a small bright accent beats a big brownish photo
            c = np.array(pal3[i], float) / 255
            sat = (c.max() - c.min()) / max(c.max(), 1e-6)
            return cnt[i] * sat ** 4 * c.max()
        accent = pal3[max(range(6), key=vivid_score)]
    else:
        accent = ink
    # how busy: share of edge pixels ~ text / detail density
    edges = []
    for _, im in ims:
        g = np.asarray(im.convert("L").resize((180, 320)), dtype=float)
        edges.append(float((np.abs(np.diff(g, axis=1)) > 40).mean()))
    folder = app_root() / "library/looks" / name
    folder.mkdir(parents=True, exist_ok=True)
    tw = 216
    tiles = [ImageOps.fit(im, (tw, int(tw * 1.25)), Image.LANCZOS) for _, im in ims]
    cols = min(5, len(tiles))
    sheet = Image.new("RGB", (cols * (tw + 6) + 6, ((len(tiles) + cols - 1) // cols) * (int(tw * 1.25) + 22) + 40), "white")
    d = ImageDraw.Draw(sheet)
    for i, ((lab, _), t) in enumerate(zip(ims, tiles)):
        x, y = 6 + (i % cols) * (tw + 6), (i // cols) * (int(tw * 1.25) + 22)
        d.text((x, y + 4), lab[:30], fill="black")
        sheet.paste(t, (x, y + 18))
    for k, (c, w) in enumerate(pal[:8]):
        d.rectangle((6 + k * 60, sheet.height - 34, 60 + k * 60, sheet.height - 6), fill=c)
    sheet.save(folder / "taste_sheet.png")
    taste = {
        "name": name, "refs": [p.name for p in paths],
        "theme": {"preset": "clean" if _lum(bg) > 128 else "night", "bg": _hex(bg), "ink": _hex(ink),
                  "accent": _hex(accent), "title_font": None, "body_font": None, "align": "left", "uppercase": False},
        "measured": {"palette": [_hex(c) for c, _ in pal[:8]], "light": _lum(bg) > 128,
                     "busy": round(float(np.mean(edges)), 3), "words_hint": "мало текста" if np.mean(edges) < 0.06 else "много текста"},
        "layouts": [], "notes": "",
        "sheet": str(folder / "taste_sheet.png"),
        "todo_for_claude": ["Look at the sheet once. Fix bg/ink/accent if the guess is wrong.",
                            "Set title_font and body_font (closest from library/fonts), align, uppercase.",
                            "layouts: which of cover|text|list|quote|number|photo|end they use; notes: 1-2 lines of taste "
                            "(e.g. 'много воздуха, один акцент на слайд, фото с тёплой плёнкой')."],
    }
    out = out or app_root() / "styles" / f"taste_{name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(taste, ensure_ascii=False, indent=1))
    return {**{k: taste[k] for k in ("theme", "measured", "sheet")}, "file": str(out)}
