"""Caption look + punch-in zoom in one command (no code reading needed).

    python -m autocut look jobs/r1/spec.json --captions minimal
    python -m autocut look jobs/r1/spec.json --captions bold --size 80 --y -0.35 --punch 1.08
then: python -m autocut render jobs/r1/spec.json --out jobs/r1/final.mp4

--captions  minimal (small clean white, soft rise) | bold (big caps, pop) | box (text on a dark plate) |
            words (1-3 words, the spoken one lights up)
--size N    caption size in px on 1080x1920 (minimal 58, bold 74)   --y  -1..1 (−0.4 = lower third, 0 = centre)
--font      Montserrat Medium|SemiBold|Bold|Black, Inter Medium|SemiBold|Bold|Black, Oswald
--upper / --no-upper   --color "#FFFFFF"   --highlight "#F6DB92" (words mode)
--anim      rise | pop | fade
--frame     fill (crop to vertical) | fit (whole horizontal frame on black, captions under it; default for
            horizontal video) | blur (whole frame over its own blurred copy; only if asked)
--music     file.mp3 [--music-db -20]: background track, looped, faded; -16 audible, -20 quiet («тихонько»), -24 barely
--punch     1.0 off, 1.06 subtle, 1.10 strong: every other cut is a bit closer (classic talking-head rhythm)
"""
from __future__ import annotations

import json
from pathlib import Path

FONT_FILES = {
    "Montserrat Medium": "fonts/Montserrat-Medium.ttf", "Montserrat SemiBold": "fonts/Montserrat-SemiBold.ttf",
    "Montserrat Bold": "fonts/montserrat/Montserrat-Bold.ttf", "Montserrat Black": "fonts/montserrat/Montserrat-Black.ttf",
    "Inter Medium": "fonts/inter/Inter-Medium.ttf", "Inter SemiBold": "fonts/inter/Inter-SemiBold.ttf",
    "Inter Bold": "fonts/inter/Inter-Bold.ttf", "Inter Black": "fonts/inter/Inter-Black.ttf",
    "Oswald": "fonts/Oswald-Bold.ttf",
}
PRESETS = {
    "minimal": dict(font_name="Montserrat Medium", size=58, uppercase=False, anim="rise", mode="phrase",
                    shadow=1.2, shadow_alpha=0.35, box=None, pop=False),
    "bold": dict(font_name="Montserrat Black", size=74, uppercase=True, anim="pop", mode="phrase",
                 shadow=2, shadow_alpha=0.45, box=None, pop=True),
    "box": dict(font_name="Montserrat SemiBold", size=60, uppercase=False, anim="rise", mode="phrase",
                box={"color": "#000000", "alpha": 0.55, "pad": 14}, pop=False),
    "words": dict(font_name="Montserrat Bold", size=76, uppercase=True, anim="pop", mode="words",
                  highlight="#F6DB92", box=None, pop=True, words_per=3),
}


def look(spec_path: str, captions=None, size=None, y=None, font=None, upper=None, color=None,
         highlight=None, anim=None, punch=None, frame=None, music=None, music_db=None) -> dict:
    sp = Path(spec_path)
    spec = json.loads(sp.read_text())
    cs = spec["caption_style"]
    if captions:
        cs.update(PRESETS[captions])
        cs["line_gap"] = int(cs["size"] * 0.75)
    for k, v in (("size", size), ("y", y), ("font_name", font), ("uppercase", upper), ("color", color),
                 ("highlight", highlight), ("anim", anim)):
        if v is not None:
            cs[k] = v
    if size is not None:
        cs["line_gap"] = int(size * 0.75)
    if cs.get("anim") == "pop":
        cs["pop"] = True
    elif anim:
        cs["pop"] = False
    if cs.get("box") is None:
        cs.pop("box", None)
    f = FONT_FILES.get(cs["font_name"])
    if f and f not in spec.setdefault("fonts", []):
        spec["fonts"].append(f)
    if punch is not None:
        spec.setdefault("aroll_look", {})["punch"] = punch
    if frame:
        spec.setdefault("aroll_look", {})["frame"] = frame
        if frame in ("fit", "blur") and y is None:  # captions just under the horizontal frame
            import subprocess
            from .reel import FRAME_TOP, _p
            src = _p(dict(spec, _base=str(sp.parent)), spec["sources"][spec["voice"][0]["src"]])
            wh = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                 "stream=width,height:stream_side_data=rotation", "-of", "csv=p=0", src],
                                capture_output=True, text=True).stdout.split()[0].split(",")
            w, h = int(wh[0]), int(wh[1])
            W, H = spec["canvas"]["w"], spec["canvas"]["h"]
            fh = W * h / w
            bottom = (H - fh) * FRAME_TOP + fh
            cs["y"] = round(max(-0.6, 1 - 2 * (bottom + 0.07 * H) / H), 3)
            spec["avoid_face"] = False
    if music:
        spec["music"] = {"asset": str(Path(music).resolve()), "gain_db": music_db if music_db is not None else -20}
    elif music_db is not None and spec.get("music"):
        spec["music"]["gain_db"] = music_db
    sp.write_text(json.dumps(spec, ensure_ascii=False, indent=1))
    return {"captions": {k: cs.get(k) for k in ("font_name", "size", "y", "uppercase", "anim", "mode")},
            "punch": spec.get("aroll_look", {}).get("punch", 1.0), "frame": spec.get("aroll_look", {}).get("frame", "fill"),
            "music": spec.get("music")}


def auto_frame(spec_path) -> str | None:
    """Horizontal talking video: show the whole frame on black (clean, like most creators do) instead of
    cropping the head off. Blur only when the person asks for it."""
    import subprocess
    from .reel import _p
    sp = Path(spec_path)
    spec = json.loads(sp.read_text())
    if spec.get("aroll_look", {}).get("frame") or not spec.get("voice"):
        return None
    src = _p(dict(spec, _base=str(sp.parent)), spec["sources"][spec["voice"][0]["src"]])
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height:stream_side_data=rotation", "-of", "default=nw=1", src],
                       capture_output=True, text=True).stdout
    vals = dict(l.split("=", 1) for l in r.splitlines() if "=" in l)
    w, h = int(vals.get("width", 0)), int(vals.get("height", 0))
    if abs(int(float(vals.get("rotation", 0) or 0))) in (90, 270):
        w, h = h, w
    if w > h * 1.1:
        look(str(sp), frame="fit")
        return "fit"
    return None
