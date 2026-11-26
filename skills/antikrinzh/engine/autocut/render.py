# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
# Licensed, not sold: see LICENSE.md. Redistribution or resale is prohibited.
"""Local renders: (a) small preview MP4 for the iPhone, (b) graded ProRes intermediate,
(c) exact-font caption PNGs for CapCut. All single-pass ffmpeg, streaming, low RAM.
"""
from __future__ import annotations

from pathlib import Path

from .media import FFMPEG, h264_encoder, prores_encoder, run
from .timeline import Timeline


# ---------------------------------------------------------------- (a) preview
def render_preview(tl: Timeline, out: Path, font_file: str | None = None, height: int = 960) -> Path:
    """Burned-in preview (captions in your real font, stickers, sfx, music) at ~960p.
    Not the deliverable: the deliverable is the CapCut draft. This is for quick review."""
    ass = out.with_suffix(".ass")
    _write_ass(tl, ass, font_file)

    inputs = ["-i", tl.source]
    sel = "+".join(f"between(t,{c.src_in:.3f},{c.src_out:.3f})" for c in tl.main)
    vf = [f"[0:v]select='{sel}',setpts=N/FRAME_RATE/TB,scale=-2:{height},format=yuv420p[v0]"]
    af = [f"[0:a]aselect='{sel}',asetpts=N/SR/TB,aresample=48000[a0]"]

    last, idx = "v0", 1
    for o in tl.overlays:
        inputs += ["-loop", "1", "-t", f"{o.dur:.3f}", "-i", o.src]
        px = f"(W-w)/2+({o.x})*W/2"
        py = f"(H-h)/2-({o.y})*H/2"
        vf.append(f"[{idx}:v]scale=-2:{int(height * o.scale) // 2 * 2},format=rgba,"
                  f"setpts=PTS+{o.start:.3f}/TB[o{idx}]")
        vf.append(f"[{last}][o{idx}]overlay=x='{px}':y='{py}':eof_action=pass:"
                  f"enable='between(t,{o.start:.3f},{o.start + o.dur:.3f})'[v{idx}]")
        last, idx = f"v{idx}", idx + 1
    fontsdir = f":fontsdir='{Path(font_file).parent}'" if font_file else ""
    vf.append(f"[{last}]subtitles='{ass}'{fontsdir}[vout]")

    mix = ["[a0]"]
    for a in tl.sfx + tl.music:
        inputs += ["-i", a.src]
        vol = a.volume if not a.volume_keys else sum(g for _, g in a.volume_keys) / len(a.volume_keys)
        ms = int(a.start * 1000)
        af.append(f"[{idx}:a]atrim={a.src_in:.3f}:{a.src_in + a.dur:.3f},asetpts=PTS-STARTPTS,"
                  f"volume={vol:.3f},aresample=48000,adelay={ms}|{ms}[s{idx}]")
        mix.append(f"[s{idx}]")
        idx += 1
    af.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=first,"
              f"alimiter=limit=0.95[aout]")

    cmd = [FFMPEG, "-y", "-hide_banner", *inputs, "-filter_complex", ";".join(vf + af),
           "-map", "[vout]", "-map", "[aout]", *h264_encoder(), "-c:a", "aac", "-b:a", "160k",
           "-movflags", "+faststart", "-t", f"{tl.duration:.3f}", str(out)]
    run(cmd)
    return out


def _ass_time(t: float) -> str:
    h, rem = divmod(max(0, t), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _write_ass(tl: Timeline, path: Path, font_file: str | None) -> None:
    st = tl.caption_style
    font_name = st.get("font_name", "Arial")
    color = st.get("color", "#FFFFFF").lstrip("#")
    bgr = f"&H00{color[4:6]}{color[2:4]}{color[0:2]}"
    margin_v = int(tl.height * (1 + st.get("y", -0.55)) / 2)  # CapCut y -> ASS bottom margin
    header = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {tl.width}\nPlayResY: {tl.height}\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, "
        "Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV\n"
        f"Style: Cap,{font_name},{int(tl.height * 0.055)},{bgr},&H00000000,&H64000000,"
        f"{-1 if st.get('bold', True) else 0},0,1,{max(2, tl.height // 270)},0,2,60,60,{margin_v}\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Text\n"
    )
    lines = [f"Dialogue: 0,{_ass_time(c.start)},{_ass_time(c.start + c.dur)},Cap,"
             f"{c.text.replace(chr(10), ' ')}" for c in tl.captions]
    path.write_text(header + "\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------- (b) LUT bake
def bake_lut(src: str, lut: str, out: Path) -> Path:
    """Full-resolution ProRes 422 HQ with the LUT applied. ~10x bigger than HEVC but
    visually lossless, so CapCut's final export is the only lossy step."""
    run([FFMPEG, "-y", "-hide_banner", "-i", src, "-vf", f"lut3d='{lut}':interp=tetrahedral",
         *prores_encoder(), "-c:a", "pcm_s16le", "-map_metadata", "0", str(out)])
    return out


# ---------------------------------------------------------------- (c) caption PNGs
def caption_pngs(tl: Timeline, out_dir: Path, font_file: str) -> list[tuple[str, float, float]]:
    """Exact custom-font captions as transparent full-frame PNGs (CapCut-safe workaround
    for fonts it can't reference). Trade-off: re-generate to change the text."""
    from PIL import Image, ImageDraw, ImageFont

    st = tl.caption_style
    out_dir.mkdir(parents=True, exist_ok=True)
    size = int(tl.height * 0.055)
    font = ImageFont.truetype(font_file, size)
    fill = "#" + st.get("color", "#FFFFFF").lstrip("#")
    stroke = max(2, tl.height // 270)
    y_center = int(tl.height / 2 - st.get("y", -0.55) * tl.height / 2)
    result = []
    for i, c in enumerate(tl.captions):
        img = Image.new("RGBA", (tl.width, tl.height), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        box = d.textbbox((0, 0), c.text, font=font, stroke_width=stroke)
        x = (tl.width - (box[2] - box[0])) // 2
        d.text((x, y_center - (box[3] - box[1]) // 2), c.text, font=font, fill=fill,
               stroke_width=stroke, stroke_fill=st.get("stroke_color", "#000000"))
        p = out_dir / f"cap_{i:04d}.png"
        img.save(p, optimize=False, compress_level=1)
        result.append((str(p), c.start, c.dur))
    return result
