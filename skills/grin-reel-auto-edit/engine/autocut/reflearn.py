# GRIN Reels — © 2026 Ernest Grin. All rights reserved.
"""Learn a style from ONE finished reel someone else made (no source clips needed).

Measured here (no AI): editing pace (cut length), how much B&W, colour grade
(reference frames -> a LUT built for each new A-roll), music under the voice.
Saved for Claude to look at once: a contact sheet of the reference, so it can
set the visual things a machine can't judge — caption look, title, sticker.

Output: styles/<name>.json (based on an existing style) + library/looks/<name>/.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent


def _dur(p: Path) -> float:
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                capture_output=True, text=True).stdout.strip() or 0)


def _cuts(p: Path, thr: float = 0.32) -> list[float]:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(p), "-vf", f"select='gt(scene,{thr})',showinfo",
                        "-an", "-f", "null", "-"], capture_output=True, text=True)
    return [float(m) for m in re.findall(r"pts_time:([\d.]+)", r.stderr)]


def _frame(p: Path, t: float, w: int = 360) -> Image.Image:
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(p), "-frames:v", "1",
                          "-vf", f"scale={w}:-2", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    from io import BytesIO
    return Image.open(BytesIO(raw)).convert("RGB")


def _sat(im: Image.Image) -> float:
    return float(np.asarray(im.convert("HSV"))[..., 1].mean())


def _music_under_voice(p: Path) -> bool:
    """Crude: in the quietest 10% of the track the level stays well above silence -> a bed is playing."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(p), "-af", "astats=metadata=1:reset=0.1,"
                        "ametadata=print:key=lavfi.astats.Overall.RMS_level", "-f", "null", "-"],
                       capture_output=True, text=True)
    lv = [float(x) for x in re.findall(r"RMS_level=(-?[\d.]+)", r.stderr) if x not in ("-inf",)]
    return bool(lv) and float(np.percentile(lv, 10)) > -45


def learn(ref: Path, name: str, base: str = "warm_intro") -> dict:
    dur = _dur(ref)
    cuts = [c for c in _cuts(ref) if 0.15 < c < dur - 0.15]
    bounds = [0.0] + cuts + [dur]
    shots = [(a, b) for a, b in zip(bounds, bounds[1:]) if b - a > 0.08]
    frames = [(a, b, _frame(ref, (a + b) / 2)) for a, b in shots[:40]]
    sats = [_sat(f) for _, _, f in frames]
    bw = [s < 14 for s in sats]
    lens = sorted(b - a for a, b in shots)
    short = [x for x in lens if x < 2.5] or lens  # montage shots, not the talking head
    cut_len = float(np.median(short)) if short else 1.0

    out = ROOT / "library/looks" / name
    out.mkdir(parents=True, exist_ok=True)
    # colour reference: the most typical colour shots (not B&W), full size
    colour = [(a, b) for (a, b, _), w in zip(frames, bw) if not w] or [(a, b) for a, b, _ in frames]
    refs = []
    for i, (a, b) in enumerate(sorted(colour, key=lambda s: -(s[1] - s[0]))[:3]):
        fp = out / f"ref_look_{i + 1}.png"
        _frame(ref, (a + b) / 2, 720).save(fp)
        refs.append(str(fp.relative_to(ROOT / "library")))
    # contact sheet every 0.5 s for Claude to judge text, title, sticker, framing
    ts = np.arange(0.25, dur, 0.5)[:40]
    tiles = [_frame(ref, t, 216) for t in ts]
    cols, th = 8, tiles[0].height
    sheet = Image.new("RGB", (216 * cols, (th + 18) * ((len(tiles) + cols - 1) // cols)), "white")
    d = ImageDraw.Draw(sheet)
    for i, (t, im) in enumerate(zip(ts, tiles)):
        x, y = (i % cols) * 216, (i // cols) * (th + 18)
        sheet.paste(im, (x, y + 18))
        d.text((x + 4, y + 3), f"{t:.1f}s", fill="black")
    sheet.save(out / "sheet.png")

    style = json.loads((ROOT / "styles" / f"{base}.json").read_text())
    style["_comment"] = f"GRIN Reels style '{name}' — learned from one reference reel ({ref.name}). © 2026 Ernest Grin."
    look = f"looks/{name}"
    style["aroll_look"] = {k: v for k, v in style["aroll_look"].items() if k not in ("lut", "input_luma")}
    style["aroll_look"]["lut_ref"] = refs
    style["broll_look"] = dict(style.get("broll_look", {}), lut_ref=refs)
    br = style.setdefault("broll_rules", {})
    br["cut_len"] = round(min(2.5, max(0.35, cut_len)), 2)
    br["looks"] = ["color", "bw"] if sum(bw) >= max(1, len(bw) // 6) else ["color"]
    music = _music_under_voice(ref)
    rep = {"name": name, "duration": round(dur, 2), "shots": len(shots), "cut_len": br["cut_len"],
           "bw_shots": int(sum(bw)), "looks": br["looks"], "music_under_voice": music,
           "colour_refs": refs, "sheet": str((out / "sheet.png").relative_to(ROOT)),
           "todo_for_claude": [
               "Open the sheet. Set caption_style: mode phrase|words, font (closest free font), size, y, color, "
               "uppercase, box plate, pop.",
               "Title at the start? set title.template (font, colors, size, y) or remove 'title'.",
               "End button/sticker? keep or remove 'sticker'.",
               "Zoomed-in talking head? set aroll_look.zoom/y.",
           ]}
    style["_learned"] = rep
    (ROOT / "styles" / f"{name}.json").write_text(json.dumps(style, ensure_ascii=False, indent=1))
    (out / "analysis.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    return rep
