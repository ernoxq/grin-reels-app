"""Storyboard sheet (раскадровка) for agreeing on the plan BEFORE the render: one PNG the person looks
at, Claude doesn't (sent unread: ~0 tokens).

    python -m autocut sheet jobs/r1        -> jobs/r1/storyboard.png

Left: every kept line with a frame, time, length and words (unsure words in yellow; lines that
continue a cut thought in red, with the cut sentence quoted). Right: a real frame in the final look
(layout, captions in their font/size/place, title), the look settings, and what is cut with its
time in the source.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .media import FFMPEG

ROOT = Path(__file__).resolve().parent.parent
W, PAD, TH = 1600, 40, 150
LEFT = 1000          # width of the lines column
PW = 440             # preview width (9:16)
FONT_DIR = ROOT / "library" / "fonts"


def _font(size: int, bold=False):
    f = FONT_DIR / ("montserrat/Montserrat-Bold.ttf" if bold else "Montserrat-Medium.ttf")
    try:
        return ImageFont.truetype(str(f), size)
    except Exception:
        return ImageFont.load_default()


def _font_for(name: str, size: int):
    from .look import FONT_FILES
    rel = FONT_FILES.get(name)
    for p in ([FONT_DIR / rel.replace("fonts/", "", 1)] if rel else []) + [FONT_DIR / "Montserrat-SemiBold.ttf"]:
        try:
            return ImageFont.truetype(str(p), size)
        except Exception:
            continue
    return ImageFont.load_default()


def _wrap(dr, text, font, width):
    out, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if dr.textlength(t, font=font) > width and cur:
            out.append(cur); cur = w
        else:
            cur = t
    if cur:
        out.append(cur)
    return out


def _src_file(spec: dict, job: Path, key: str) -> str:
    p = Path(spec["sources"][key])
    return str(p if p.is_absolute() else job / p)


def _src_at(spec: dict, job: Path, t: float) -> tuple[str, float]:
    acc = 0.0
    for v in spec["voice"]:
        if acc <= t <= acc + v["dur"]:
            return _src_file(spec, job, v["src"]), v["in"] + (t - acc) + 0.3
        acc += v["dur"]
    v = spec["voice"][-1]
    return _src_file(spec, job, v["src"]), v["in"]


def _grab(src: str, t: float, out: Path, vf: str) -> Image.Image | None:
    subprocess.run([FFMPEG, "-v", "error", "-y", "-ss", f"{max(0, t):.2f}", "-i", src, "-frames:v", "1", "-vf", vf, str(out)])
    if out.exists():
        im = Image.open(out).convert("RGB"); im.load(); out.unlink()
        return im
    return None


def _preview(spec: dict, job: Path, caption: str) -> Image.Image:
    """The reel's look in one frame, drawn at 1080x1920 then scaled: layout, captions, title."""
    from .reel import FRAME_TOP
    Wc, Hc = spec["canvas"]["w"], spec["canvas"]["h"]
    look = spec.get("aroll_look", {})
    frame = look.get("frame", "fill")
    v = spec["voice"][min(1, len(spec["voice"]) - 1)]
    src, t = _src_file(spec, job, v["src"]), v["in"] + min(1.0, v["dur"] / 2)
    canvas = Image.new("RGB", (Wc, Hc), "black")
    tmp = job / "_prev.jpg"
    if frame in ("fit", "blur"):
        if frame == "blur":
            bg = _grab(src, t, tmp, f"scale={Wc}:{Hc}:force_original_aspect_ratio=increase,crop={Wc}:{Hc},boxblur=28:2,eq=brightness=-0.12")
            if bg:
                canvas.paste(bg, (0, 0))
        fg = _grab(src, t, tmp, f"scale={Wc}:-2")
        if fg:
            canvas.paste(fg, (0, int((Hc - fg.height) * FRAME_TOP)))
    else:
        im = _grab(src, t, tmp, f"scale={Wc}:{Hc}:force_original_aspect_ratio=increase,crop={Wc}:{Hc}")
        if im:
            canvas.paste(im, (0, 0))
    dr = ImageDraw.Draw(canvas)
    cs = spec.get("caption_style", {})
    fnt = _font_for(cs.get("font_name", ""), int(cs.get("size", 60)))
    txt = caption.upper() if cs.get("uppercase") else caption
    lines = _wrap(dr, txt, fnt, Wc * 0.8)[:2]
    cy = Hc / 2 - cs.get("y", -0.4) * Hc / 2
    gap = cs.get("line_gap", int(cs.get("size", 60) * 0.75))
    for i, ln in enumerate(lines):
        y = cy + (i - (len(lines) - 1) / 2) * (gap + cs.get("size", 60) * 0.35)
        dr.text((Wc / 2 + 3, y + 3), ln, font=fnt, fill=(0, 0, 0), anchor="mm")
        dr.text((Wc / 2, y), ln, font=fnt, fill=cs.get("color", "#FFFFFF"), anchor="mm")
    return canvas.resize((PW, int(PW * Hc / Wc)))


def _parse(txt: str):
    head, kept, cut, mode = [], [], [], ""
    for ln in txt.splitlines():
        m = re.match(r"(\d+)\.\s+([\d.]+) с(?: \(([\d.]+) с\))?\s+(.*)", ln)
        if ln.startswith("Остаётся"):
            mode = "k"; continue
        if ln.startswith("Вырезано"):
            mode = "c"; continue
        if mode == "k" and m:
            body = m.group(4)
            wm = re.search(r"продолжает вырезанную мысль: «(.*?)»\. Без неё непонятно, к чему «(.*?)»", body)
            body = re.sub(r"\s+⚠.*$", "", body)
            body = re.sub(r"\s+\[вставка[^\]]*\]", "", body)
            kept.append((float(m.group(2)), m.group(3), body, (wm.group(1), wm.group(2)) if wm else None))
        elif mode == "c" and ln.startswith("- "):
            cut.append(ln[2:])
        elif not mode and ln.strip() and not ln.startswith(("JOB", "SPEC")):
            head.append(ln)
    return head, kept, cut


def _src_time(words: list[dict], phrase: str) -> str:
    from .storyboard import _norm
    want = [_norm(x) for x in phrase.split() if _norm(x)][:4]
    toks = [_norm(w["text"]) for w in words]
    for i in range(len(toks) - len(want) + 1):
        if want and toks[i:i + len(want)] == want:
            t = words[i]["start"]
            return f"{int(t // 60)}:{int(t % 60):02d}"
    return ""


def sheet(job: str) -> str:
    from .storyboard import plan_text
    job = Path(job)
    spec = json.loads((job / "spec.json").read_text())
    head, kept, cut = _parse(plan_text(job))
    args = json.loads((job / "auto_args.json").read_text()) if (job / "auto_args.json").exists() else {}
    raw = json.loads((job / "words.json").read_text()) if (job / "words.json").exists() else []
    cut = [d for d in args.get("drop", [])] + cut

    img = Image.new("RGB", (W, 6000), "#111111")
    dr = ImageDraw.Draw(img)
    f_h, f_t, f_s, f_m = _font(36, True), _font(28), _font(24), _font(22)
    y = PAD
    dr.text((PAD, y), "Раскадровка", font=f_h, fill="white"); y += 54
    for h in head[:3]:
        for l in _wrap(dr, h, f_s, W - 2 * PAD):
            dr.text((PAD, y), l, font=f_s, fill="#BBBBBB"); y += 32
    y += 14
    top = y
    # ---------------- left: the lines
    tw = int(TH * 9 / 16) if spec["canvas"]["h"] > spec["canvas"]["w"] else int(TH * 16 / 9)
    tmp = job / "_thumb.jpg"
    textw = LEFT - 3 * PAD - tw
    for i, (t0, dur, body, warn) in enumerate(kept, 1):
        src, st = _src_at(spec, job, t0 * float(spec.get("speed") or 1))
        th = _grab(src, st, tmp, f"scale={tw}:{TH}:force_original_aspect_ratio=increase,crop={tw}:{TH}")
        words = body.split()
        # wrap word by word, keeping «(?)» marks for colour
        lines, cur = [], []
        for w in words:
            test = " ".join(x.replace("(?)", "") for x in cur + [w])
            if cur and dr.textlength(test, font=f_t) > textw:
                lines.append(cur); cur = [w]
            else:
                cur.append(w)
        if cur:
            lines.append(cur)
        wl = (_wrap(dr, f"Эта фраза продолжает мысль, которую вырезали: «{warn[0]}». Без неё непонятно, к чему "
                        f"«{warn[1]}». Вернуть ту фразу или срезать «{warn[1]}».", f_m, textw) if warn else [])
        hgt = max(TH, 40 + len(lines) * 36 + len(wl) * 28) + 20
        if th:
            img.paste(th, (PAD, y))
        x = PAD * 2 + tw
        meta = f"{i}.  {t0:.0f} с" + (f"  ·  {dur} с" if dur else "")
        dr.text((x, y), meta, font=f_m, fill="#FF6B6B" if warn else "#8FD3FF")
        if warn:
            dr.text((x + dr.textlength(meta, font=f_m) + 16, y), "! мысль оборвана", font=f_m, fill="#FF6B6B")
        yy = y + 34
        for ln in lines:
            xx = x
            for w in ln:
                unsure = "(?)" in w and len(re.sub(r"\W", "", w.replace("(?)", ""))) >= 4
                w = w.replace("(?)", "")
                col = "#FFD54A" if unsure else ("#FF9A9A" if warn else "white")
                dr.text((xx, yy), w, font=f_t, fill=col)
                if unsure:
                    dr.line((xx, yy + 33, xx + dr.textlength(w, font=f_t), yy + 33), fill="#FFD54A", width=2)
                xx += dr.textlength(w + " ", font=f_t)
            yy += 36
        for l in wl:
            dr.text((x, yy), l, font=f_m, fill="#FF6B6B"); yy += 28
        y += hgt
        dr.line((PAD, y - 10, LEFT - PAD, y - 10), fill="#2A2A2A", width=2)
    left_end = y
    # ---------------- right: how it will look + what is cut
    rx, ry = LEFT + PAD // 2, top
    dr.text((rx, ry), "Как будет выглядеть", font=_font(28, True), fill="white"); ry += 44
    cap = next((c["text"].replace("\n", " ") for c in spec.get("captions", []) if len(c["text"]) > 12), "пример субтитра")
    pv = _preview(spec, job, cap)
    img.paste(pv, (rx, ry))
    dr.rectangle((rx - 1, ry - 1, rx + pv.width, ry + pv.height), outline="#333333")
    ry += pv.height + 18
    cs, look = spec.get("caption_style", {}), spec.get("aroll_look", {})
    frame = {"fit": "весь кадр на чёрном", "blur": "весь кадр на размытом фоне", "fill": "на весь экран"}.get(look.get("frame", "fill"))
    mus = spec.get("music") or {}
    rows = [("Субтитры", f"{cs.get('font_name', '?')}, {cs.get('size', '?')} px" + (", КАПС" if cs.get("uppercase") else ", строчные")),
            ("Цвет", cs.get("color", "#FFFFFF")),
            ("Появление", {"rise": "мягкий подъём", "pop": "прыжок", "fade": "проявление"}.get(cs.get("anim"), "проявление")),
            ("Кадр", frame),
            ("Зум на склейках", f"{round((float(look.get('punch', 1.04)) - 1) * 100)} %"),
            ("Скорость", f"×{spec.get('speed', 1.0):g}"),
            ("Музыка", f"{Path(mus['asset']).stem}, {mus.get('gain_db')} дБ" if mus.get("asset") else "нет")]
    LW = 220
    for k, v in rows:
        dr.text((rx, ry), k, font=f_m, fill="#888888")
        vl = _wrap(dr, str(v), f_m, W - rx - PAD - LW)
        for n, l in enumerate(vl):
            dr.text((rx + LW, ry + n * 28), l, font=f_m, fill="white")
        if k == "Цвет":
            ex = rx + LW + dr.textlength(str(v), font=f_m)
            dr.ellipse((ex + 10, ry + 2, ex + 32, ry + 24), fill=v, outline="#666666")
        ry += 28 * len(vl) + 6
    for l in _wrap(dr, "Не нравится размер или шрифт? Напиши: «крупнее», «капсом», «шрифт как у …».", _font(20), W - rx - PAD):
        dr.text((rx, ry + 6), l, font=_font(20), fill="#8FD3FF"); ry += 26
    ry += 24
    if cut:
        dr.text((rx, ry), "Убрано (время в исходнике):", font=f_t, fill="#888888"); ry += 40
        for c in cut[:16]:
            tm = _src_time(raw, c.strip("«»…. ")) if raw else ""
            for l in _wrap(dr, (f"{tm}  " if tm else "") + f"«{c.strip('«»… ')}…»", f_s, W - rx - PAD):
                dr.text((rx, ry), l, font=f_s, fill="#777777"); ry += 30
    tmp.unlink(missing_ok=True)
    out = job / "storyboard.png"
    img.crop((0, 0, W, max(left_end, ry) + PAD)).save(out)
    return str(out)
