"""Storyboard sheet (раскадровка) for agreeing on the plan: one PNG the person looks at, Claude doesn't.

    python -m autocut sheet jobs/r1        -> jobs/r1/storyboard.png

Each kept line: a frame from that moment, its time and length, the words; ⚠ lines in red;
what is cut, in grey; the total length (and target / speed) on top. Send it with the 3-line brief;
don't open it yourself (saves tokens).
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .media import FFMPEG

ROOT = Path(__file__).resolve().parent.parent
W, PAD, TH = 1080, 40, 150


def _font(size: int, bold=False):
    f = ROOT / "library" / "fonts" / ("montserrat/Montserrat-Bold.ttf" if bold else "Montserrat-Medium.ttf")
    try:
        return ImageFont.truetype(str(f), size)
    except Exception:
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


def _src_at(spec: dict, job: Path, t: float) -> tuple[str, float]:
    acc = 0.0
    for v in spec["voice"]:
        if acc <= t <= acc + v["dur"]:
            p = Path(spec["sources"][v["src"]])
            return str(p if p.is_absolute() else job / p), v["in"] + (t - acc) + 0.3
        acc += v["dur"]
    v = spec["voice"][-1]
    p = Path(spec["sources"][v["src"]])
    return str(p if p.is_absolute() else job / p), v["in"]


def sheet(job: str) -> str:
    from .storyboard import plan_text
    job = Path(job)
    spec = json.loads((job / "spec.json").read_text())
    txt = plan_text(job)
    head, kept, cut, mode = [], [], [], ""
    for ln in txt.splitlines():
        m = re.match(r"(\d+)\.\s+([\d.]+) с(?: \(([\d.]+) с\))?\s+(.*)", ln)
        if ln.startswith("Остаётся"):
            mode = "k"; continue
        if ln.startswith("Вырезано"):
            mode = "c"; continue
        if mode == "k" and m:
            body = m.group(4)
            warn = "⚠" in body
            body = re.sub(r"\s+⚠.*$", "", body).replace("(?)", "")
            body = re.sub(r"\s+\[вставка[^\]]*\]", "", body)
            kept.append((float(m.group(2)), m.group(3), body, warn))
        elif mode == "c" and ln.startswith("- "):
            cut.append(ln[2:])
        elif not mode and ln.strip() and not ln.startswith(("JOB", "SPEC")):
            head.append(ln)
    img = Image.new("RGB", (W, 4000), "#111111")
    dr = ImageDraw.Draw(img)
    f_h, f_t, f_s, f_m = _font(34, True), _font(28), _font(24), _font(22)
    y = PAD
    dr.text((PAD, y), "Раскадровка", font=f_h, fill="white"); y += 52
    for h in head[:3]:
        for l in _wrap(dr, h, f_s, W - 2 * PAD):
            dr.text((PAD, y), l, font=f_s, fill="#BBBBBB"); y += 32
    y += 16
    tw = int(TH * 9 / 16) if spec["canvas"]["h"] > spec["canvas"]["w"] else int(TH * 16 / 9)
    tmp = job / "_thumb.jpg"
    for i, (t0, dur, body, warn) in enumerate(kept, 1):
        src, st = _src_at(spec, job, t0)
        subprocess.run([FFMPEG, "-v", "error", "-y", "-ss", f"{max(0, st):.2f}", "-i", src, "-frames:v", "1",
                        "-vf", f"scale={tw}:{TH}:force_original_aspect_ratio=increase,crop={tw}:{TH}", str(tmp)])
        lines = _wrap(dr, body, f_t, W - 3 * PAD - tw)
        hgt = max(TH, 40 + len(lines) * 36) + 20
        if tmp.exists():
            img.paste(Image.open(tmp).convert("RGB"), (PAD, y))
        x = PAD * 2 + tw
        meta = f"{i}.  {t0:.0f} с" + (f"  ·  {dur} с" if dur else "")
        dr.text((x, y), meta, font=f_m, fill="#FF6B6B" if warn else "#8FD3FF")
        if warn:
            dr.text((x + dr.textlength(meta, font=f_m) + 16, y), "⚠ опирается на убранную фразу", font=f_m, fill="#FF6B6B")
        yy = y + 34
        for l in lines:
            dr.text((x, yy), l, font=f_t, fill="#FF9A9A" if warn else "white"); yy += 36
        y += hgt
        dr.line((PAD, y - 10, W - PAD, y - 10), fill="#2A2A2A", width=2)
    args = json.loads((job / "auto_args.json").read_text()) if (job / "auto_args.json").exists() else {}
    cut = [f"«{d}…»" for d in args.get("drop", [])] + cut
    if cut:
        y += 10
        dr.text((PAD, y), "Убрано:", font=f_t, fill="#888888"); y += 40
        for c in cut[:12]:
            for l in _wrap(dr, c, f_s, W - 2 * PAD):
                dr.text((PAD, y), l, font=f_s, fill="#777777"); y += 32
    tmp.unlink(missing_ok=True)
    out = job / "storyboard.png"
    img.crop((0, 0, W, y + PAD)).save(out)
    return str(out)
