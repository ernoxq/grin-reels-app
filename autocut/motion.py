# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
"""Motion graphics constructor: animated headline, plate, number, step, checklist.

Each one is rendered to a transparent ProRes 4444 .mov (1080 px wide, only as tall as needed),
so it can be placed on any words of the reel (place --motion) and stays a separate, movable
clip in CapCut / DaVinci. Text, colours, font and timing are parameters, not a fixed template.
"""
from __future__ import annotations

import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .paths import app_root

W, FPS = 1080, 30
KINDS = ("headline", "plate", "number", "step", "checklist")


# ------------------------------------------------------------------ helpers
def _font(size: int, family: str | None = None, weight: str = "Black") -> ImageFont.FreeTypeFont:
    lib = app_root() / "library/fonts"
    cands = []
    if family:
        f = Path(family)
        cands += [f, lib / family] if f.suffix else [*sorted((lib / family.lower().replace(" ", "")).glob(f"*-{weight}.ttf")),
                                                     *sorted((lib / family.lower().replace(" ", "")).glob("*.ttf"))]
    cands += [lib / "inter" / f"Inter-{weight}.ttf", lib / "inter/Inter-Bold.ttf",
              lib / "montserrat" / f"Montserrat-{weight}.ttf", lib / "Montserrat-SemiBold.ttf"]
    for c in cands:
        if Path(c).exists():
            return ImageFont.truetype(str(c), size)
    return ImageFont.load_default()


def _rgb(h: str, a: int = 255) -> tuple:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def ease_out(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def ease_back(x: float) -> float:  # slight overshoot, the "pop"
    x = max(0.0, min(1.0, x))
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def _out_alpha(t: float, dur: float, out: float = 0.25) -> float:
    return max(0.0, min(1.0, (dur - t) / out))


def _shadow(img: Image.Image, r: int = 10, a: float = 0.45) -> Image.Image:
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    alpha = img.split()[3].point(lambda v: int(v * a))
    sh.putalpha(alpha.filter(ImageFilter.GaussianBlur(r)))
    base = Image.new("RGBA", img.size, (0, 0, 0, 0))
    base.alpha_composite(sh, (0, 6))
    base.alpha_composite(img)
    return base


def _wrap(words: list[str], font, maxw: int, d: ImageDraw.ImageDraw) -> list[list[str]]:
    lines, cur = [], []
    for w in words:
        test = " ".join(cur + [w]).replace("*", "")
        if cur and d.textlength(test, font=font) > maxw:
            lines.append(cur); cur = [w]
        else:
            cur.append(w)
    return lines + ([cur] if cur else [])


# ------------------------------------------------------------------ the five builders: frame(t) -> RGBA
def headline(text: str, dur: float, accent: str, ink: str, size: int = 96, font: str | None = None, **_):
    """Words pop in one by one; a *phrase in stars* gets one marker swept behind it."""
    import re
    f = _font(size, font)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    toks, g = [], 0  # (word, group or None)
    for part in re.split(r"(\*[^*]+\*)", text):
        if part.startswith("*") and part.endswith("*") and len(part) > 2:
            g += 1
            toks += [(w, g) for w in part.strip("*").split()]
        else:
            toks += [(w, None) for w in part.split()]
    lines, cur = [], []
    for j, tk in enumerate(toks):
        if tk[1] and cur and cur[-1][1] == tk[1]:  # never break inside a *highlighted phrase*
            cur.append(tk); continue
        unit = [tk] + ([t2 for t2 in toks[j + 1:] if t2[1] == tk[1]] if tk[1] else [])
        test = " ".join(w for w, _ in cur + unit)
        if cur and probe.textlength(test, font=f) > W - 140:
            lines.append(cur); cur = [tk]
        else:
            cur.append(tk)
    lines += [cur] if cur else []
    lh = int(size * 1.22)
    H = lh * len(lines) + 80
    sp = probe.textlength(" ", font=f) + 10
    items, marks, k = [], {}, 0
    for li, ln in enumerate(lines):
        ws = [probe.textlength(w, font=f) for w, _ in ln]
        x = (W - (sum(ws) + sp * (len(ln) - 1))) / 2
        y = 40 + li * lh
        for (w, grp), wl in zip(ln, ws):
            items.append((w, x, y, grp, k))
            if grp:
                key = (grp, li)
                x0, x1, k0 = marks.get(key, (x, x + wl, k))
                marks[key] = (min(x0, x), x + wl, k0)
            k += 1
            x += wl + sp
    step = min(0.12, 0.8 / max(1, k))

    def frame(t):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        oa = _out_alpha(t, dur)
        for (grp, li), (x0, x1, k0) in marks.items():
            m = ease_out((t - k0 * step - 0.1) / 0.3)
            if m > 0:
                y = 40 + li * lh
                d.rounded_rectangle((x0 - 16, y + size * 0.1, x0 - 16 + (x1 - x0 + 32) * m, y + size * 1.14),
                                    radius=16, fill=_rgb(accent, int(255 * oa)))
        for w, x, y, grp, i in items:
            p = (t - i * step) / 0.28
            if p <= 0:
                continue
            s_, a = ease_back(p), ease_out(p) * oa
            d.text((x, y + (1 - s_) * size * 0.5), w, font=f, fill=_rgb(ink if grp else "#FFFFFF", int(255 * a)))
        return _shadow(im)
    return frame, H


def plate(text: str, dur: float, accent: str, ink: str, size: int = 58, sub: str | None = None,
          bg: str = "#1E1E1D", font: str | None = None, **_):
    """A plate slides in from the left with an accent bar; optional small line above."""
    f, fs = _font(size, font), _font(int(size * 0.55), font, "Bold")
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    tw = probe.textlength(text, font=f)
    sw = probe.textlength(sub, font=fs) if sub else 0
    pw = int(max(tw, sw) + 120)
    ph = int(size * 1.6 + (size * 0.8 if sub else 0))
    H = ph + 60

    def frame(t):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        p, oa = ease_out(t / 0.4), _out_alpha(t, dur)
        x0 = int((W - pw) / 2 - (1 - p) * 120)
        a = int(235 * p * oa)
        d.rounded_rectangle((x0, 30, x0 + pw, 30 + ph), radius=26, fill=_rgb(bg, a))
        bar = ease_out((t - 0.15) / 0.3)
        d.rounded_rectangle((x0, 30, x0 + 14, 30 + int(ph * bar)), radius=7, fill=_rgb(accent, int(255 * oa)))
        ta = int(255 * ease_out((t - 0.12) / 0.3) * oa)
        y = 30 + size * 0.3
        if sub:
            d.text((x0 + 60, y), sub.upper(), font=fs, fill=_rgb(accent, ta)); y += size * 0.8
        d.text((x0 + 60, y), text, font=f, fill=_rgb("#FFFFFF", ta))
        return _shadow(im, 14, 0.35)
    return frame, H


def number(text: str, dur: float, accent: str, ink: str, size: int = 190, label: str | None = None,
           font: str | None = None, **_):
    """Big number counts up: text like '30 000', '+250%', '$1.5k' (digits are animated, the rest kept)."""
    import re
    f, fl = _font(size, font), _font(int(size * 0.26), font, "Bold")
    m = re.search(r"[\d][\d\s.,]*", text)
    if m:
        raw = m.group(0)
        num = raw.rstrip()
        pre, post = text[:m.start()], raw[len(num):] + text[m.end():]
    else:
        pre, num, post = text, "", ""
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    while probe.textlength(text, font=f) > W - 80 and size > 60:  # fit the width
        size -= 10; f = _font(size, font)
    target = float(num.replace(" ", "").replace(",", ".")) if num else 0
    decimals = len(num.replace(",", ".").split(".")[1]) if "." in num.replace(",", ".") and not num.count(" ") else 0
    H = int(size * 1.25 + (size * 0.45 if label else 0)) + 40

    def fmt(v):
        s = f"{v:,.{decimals}f}".replace(",", " ")
        return pre + s + post

    def frame(t):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        oa = _out_alpha(t, dur)
        p = ease_out(t / 0.9)
        s = fmt(target * p) if num else text
        sc = ease_back(t / 0.3)
        fz = _font(max(8, int(size * (0.6 + 0.4 * sc))), font)
        w = d.textlength(s, font=fz)
        d.text(((W - w) / 2, 20 + (size - fz.size) * 0.5), s, font=fz, fill=_rgb(accent, int(255 * min(1, t / 0.15) * oa)))
        if label:
            la = int(255 * ease_out((t - 0.4) / 0.3) * oa)
            lw = d.textlength(label, font=fl)
            d.text(((W - lw) / 2, 20 + size * 1.15), label, font=fl, fill=_rgb("#FFFFFF", la))
        return _shadow(im)
    return frame, H


def step(text: str, dur: float, accent: str, ink: str, size: int = 56, n: str = "01", font: str | None = None, **_):
    """A numbered circle pops, then the label slides out of it."""
    f, fn = _font(size, font), _font(int(size * 0.9), font)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    tw = probe.textlength(text, font=f)
    R = int(size * 1.05)
    total = 2 * R + 30 + tw + 60
    H = 2 * R + 60

    def frame(t):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        oa = _out_alpha(t, dur)
        x0 = int((W - total) / 2)
        cx, cy = x0 + R, 30 + R
        s = ease_back(t / 0.3)
        r = R * s
        if r > 1:
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=_rgb(accent, int(255 * oa)))
            nw = d.textlength(n, font=fn)
            d.text((cx - nw / 2, cy - fn.size * 0.62), n, font=fn, fill=_rgb(ink, int(255 * min(1, s) * oa)))
        p = ease_out((t - 0.25) / 0.35)
        if p > 0:
            pw = int((tw + 70) * p)
            d.rounded_rectangle((cx + R - 10, cy - size * 0.75, cx + R - 10 + pw + 20, cy + size * 0.75),
                                radius=int(size * 0.75), fill=_rgb("#1E1E1D", int(225 * oa)))
            tile = Image.new("RGBA", (int(tw) + 4, int(size * 1.4)), (0, 0, 0, 0))
            ImageDraw.Draw(tile).text((0, 0), text, font=f, fill=_rgb("#FFFFFF", int(255 * oa)))
            vis = tile.crop((0, 0, max(1, min(tile.width, pw - 30)), tile.height))
            im.alpha_composite(vis, (int(cx + R + 30), int(cy - size * 0.62)))
        return _shadow(im, 12, 0.35)
    return frame, H


def checklist(text: str, dur: float, accent: str, ink: str, size: int = 54, font: str | None = None, **_):
    """Lines separated by | appear one by one, each with a ticked circle."""
    items = [s.strip() for s in text.split("|") if s.strip()][:5]
    f = _font(size, font, "Bold")
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    maxw = max(probe.textlength(s, font=f) for s in items)
    lh = int(size * 1.7)
    H = lh * len(items) + 60
    x0 = int((W - (maxw + size * 1.6)) / 2)

    def frame(t):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        oa = _out_alpha(t, dur)
        for i, s in enumerate(items):
            p = (t - i * 0.35) / 0.3
            if p <= 0:
                continue
            a = int(255 * ease_out(p) * oa)
            y = 30 + i * lh
            r = size * 0.55 * min(1.0, ease_back(p))
            cx, cy = x0 + size * 0.55, y + size * 0.62
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=_rgb(accent, a))
            if p > 0.6:  # the tick
                k = size * 0.22
                d.line([(cx - k, cy), (cx - k * 0.2, cy + k * 0.8), (cx + k * 1.1, cy - k * 0.8)],
                       fill=_rgb(ink, a), width=max(3, size // 12), joint="curve")
            dx = (1 - ease_out(p)) * 40
            d.text((x0 + size * 1.6 + dx, y), s, font=f, fill=_rgb("#FFFFFF", a))
        return _shadow(im)
    return frame, H


BUILDERS = {"headline": headline, "plate": plate, "number": number, "step": step, "checklist": checklist}


def render(kind: str, text: str, out: Path, dur: float = 2.5, accent: str = "#E4F23C", ink: str = "#1E1E1D",
           **kw) -> Path:
    if kind not in BUILDERS:
        raise SystemExit(f"motion: {kind}? есть: {', '.join(KINDS)}")
    frame, H = BUILDERS[kind](text, dur, accent, ink, **{k: v for k, v in kw.items() if v is not None})
    H += H % 2
    out.parent.mkdir(parents=True, exist_ok=True)
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt",
                          "yuva444p10le", "-alpha_bits", "8", str(out)], stdin=subprocess.PIPE)
    n = int(math.ceil(dur * FPS))
    for i in range(n):
        fr = frame(i / FPS)
        if fr.height != H:
            c = Image.new("RGBA", (W, H), (0, 0, 0, 0)); c.alpha_composite(fr); fr = c
        p.stdin.write(fr.tobytes())
    p.stdin.close(); p.wait()
    return out


def preview(paths: list[Path], out: Path) -> Path:
    """One small picture: the middle frame of each motion clip on a dark background (for checking)."""
    tiles = []
    for pth in paths:
        r = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", "1.2", "-i", str(pth), "-frames:v", "1", "-f", "image2pipe",
                            "-vcodec", "png", "-"], capture_output=True)
        import io
        im = Image.open(io.BytesIO(r.stdout)).convert("RGBA")
        bg = Image.new("RGBA", im.size, (70, 60, 55, 255)); bg.alpha_composite(im)
        tiles.append(bg.resize((540, int(im.height / 2))))
    H = sum(t.height for t in tiles)
    sheet = Image.new("RGB", (540, H))
    y = 0
    for t in tiles:
        sheet.paste(t.convert("RGB"), (0, y)); y += t.height
    sheet.save(out)
    return out
