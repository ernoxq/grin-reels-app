# GRIN Reels — © 2026 Ernest Grin. All rights reserved.
"""Learn a style from ONE finished reel someone else made (no source clips needed).

Measured here (no AI): editing pace (cut length), how much B&W, colour grade
(reference frames -> a LUT built for each new A-roll), music under the voice.
Saved for Claude to look at once: a contact sheet of the reference, so it can
set the visual things a machine can't judge — caption look, title, sticker.

Output: styles/<name>.json (based on an existing style) + library/looks/<name>/.
"""
from __future__ import annotations

from .paths import app_root
import json
import re
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = app_root()


def _dur(p: Path) -> float:
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                capture_output=True, text=True).stdout.strip() or 0)


def _cuts(p: Path, thr: float = 0.32) -> list[float]:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(p), "-vf", f"select='gt(scene,{thr})',showinfo",
                        "-an", "-f", "null", "-"], capture_output=True, text=True)
    return [float(m) for m in re.findall(r"pts_time:([\d.]+)", r.stderr)]


def _frame(p: Path, t: float, w: int = 360) -> Image.Image:
    from io import BytesIO
    for tt in (t, max(0.0, t - 0.3), max(0.0, t - 1.0)):  # a seek right at the end can return nothing
        raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{tt:.3f}", "-i", str(p), "-frames:v", "1",
                              "-vf", f"scale={w}:-2", "-f", "image2pipe", "-vcodec", "png", "-"],
                             capture_output=True).stdout
        if raw:
            return Image.open(BytesIO(raw)).convert("RGB")
    return Image.new("RGB", (w, int(w * 16 / 9)), "black")


def _sat(im: Image.Image) -> float:
    return float(np.asarray(im.convert("HSV"))[..., 1].mean())


def _music_under_voice(p: Path) -> bool:
    """Crude: in the quietest 10% of the track the level stays well above silence -> a bed is playing."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(p), "-af", "astats=metadata=1:reset=0.1,"
                        "ametadata=print:key=lavfi.astats.Overall.RMS_level", "-f", "null", "-"],
                       capture_output=True, text=True)
    lv = [float(x) for x in re.findall(r"RMS_level=(-?[\d.]+)", r.stderr) if x not in ("-inf",)]
    return bool(lv) and float(np.percentile(lv, 10)) > -45


def _measure(ref: Path) -> dict:
    dur = _dur(ref)
    cuts = [c for c in _cuts(ref) if 0.15 < c < dur - 0.15]
    bounds = [0.0] + cuts + [dur]
    shots = [(a, b) for a, b in zip(bounds, bounds[1:]) if b - a > 0.08]
    frames = [(a, b, _frame(ref, (a + b) / 2)) for a, b in shots[:40]]
    bw = [_sat(f) < 14 for _, _, f in frames]
    lens = sorted(b - a for a, b in shots)
    short = [x for x in lens if x < 2.5] or lens  # montage shots, not the talking head
    return {"ref": ref, "dur": dur, "shots": shots, "frames": frames, "bw": bw, "short": short,
            "music": _music_under_voice(ref)}


def learn(ref, name: str, base: str = "natural", colour: bool = False) -> dict:
    """ref = one reel or a list of 1-5 reels by the same creator: the style is their common denominator."""
    refs_in = [Path(r) for r in (ref if isinstance(ref, (list, tuple)) else [ref])][:5]
    ms = [_measure(r) for r in refs_in]
    out = ROOT / "library/looks" / name
    out.mkdir(parents=True, exist_ok=True)
    # pace = median of all montage shots of all reels; B&W and music by majority
    short = [x for m in ms for x in m["short"]]
    cut_len = float(np.median(short)) if short else 1.0
    bw = [w for m in ms for w in m["bw"]]
    music = sum(1 for m in ms if m["music"]) * 2 >= len(ms)
    dur = sum(m["dur"] for m in ms)
    shots = [s for m in ms for s in m["shots"]]
    # colour reference: the longest colour shots, spread over the reels (max 5 frames in total)
    refs, per = [], max(1, 5 // len(ms))
    for m in ms:
        colour = [(a, b) for (a, b, _), w in zip(m["frames"], m["bw"]) if not w] or [(a, b) for a, b, _ in m["frames"]]
        for a, b in sorted(colour, key=lambda s: -(s[1] - s[0]))[:per if len(ms) > 1 else 3]:
            fp = out / f"ref_look_{len(refs) + 1}.png"
            _frame(m["ref"], (a + b) / 2, 720).save(fp)
            refs.append(str(fp.relative_to(ROOT / "library")))
    # 8 key frames in total (Claude looks once; images are the costly part): opening, middle shots, end
    picks = []
    k = max(1, -(-8 // len(ms)))
    for m in ms:
        mids = sorted({round((a + b) / 2, 2) for a, b, _ in sorted(m["frames"], key=lambda f: -(f[1] - f[0]))[:max(0, k - 2)]})
        ts = ([min(0.4, m["dur"] / 2)] + mids + [max(0.0, m["dur"] - 0.5)])[:k]
        picks += [(m["ref"], t) for t in ts]
    picks = picks[:8]
    tw = 200
    tiles = [_frame(r, t, tw) for r, t in picks]
    cols, th = 4, tiles[0].height
    sheet = Image.new("RGB", (tw * cols, (th + 18) * ((len(tiles) + cols - 1) // cols)), "white")
    d = ImageDraw.Draw(sheet)
    for i, ((r, t), im) in enumerate(zip(picks, tiles)):
        x, y = (i % cols) * tw, (i // cols) * (th + 18)
        sheet.paste(im, (x, y + 18))
        d.text((x + 4, y + 3), f"#{refs_in.index(r) + 1} {t:.1f}s", fill="black")
    sheet.save(out / "sheet.png")
    ref = refs_in[0]

    style = json.loads((ROOT / "styles" / f"{base}.json").read_text())
    style["_comment"] = f"GRIN Reels style '{name}' — learned from {len(refs_in)} reference reel(s) ({", ".join(r.name for r in refs_in)}). © 2026 Ernest Grin."
    look = f"looks/{name}"
    style["aroll_look"] = {k: v for k, v in style["aroll_look"].items() if k not in ("lut", "input_luma")}
    style["aroll_look"]["lut_ref"] = refs
    style["broll_look"] = dict(style.get("broll_look", {}), lut_ref=refs)
    # colour is copied only on request: a reference shot in another light easily turns skin green or grey
    style["aroll_look"]["use_ref_colour"] = bool(colour)
    style["aroll_look"]["lut_strength"] = 0.4
    br = style.setdefault("broll_rules", {})
    br["cut_len"] = round(min(2.5, max(0.35, cut_len)), 2)
    br["looks"] = ["color", "bw"] if sum(bw) >= max(1, len(bw) // 6) else ["color"]
    rep = {"name": name, "reels": len(ms), "duration": round(dur, 2), "shots": len(shots), "cut_len": br["cut_len"],
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
