# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
# Licensed, not sold: see LICENSE.md. Redistribution or resale is prohibited.
"""Reel engine: talking-head A-roll + B-roll inserts + title + phrase captions + CTA sticker.

An edit is fully described by a small JSON "reel spec" (see specs/*.json). The spec is the
contract between the *planner* (autoreel.py: ASR -> takes -> captions -> B-roll on beats)
and the *renderers* below. Same spec -> same video, zero tokens.

    render_reel(spec)  -> final MP4 (1080x1920, max-quality single ffmpeg pass)
    capcut_reel(spec)  -> editable CapCut draft (A-roll main track, B-roll overlay track,
                          text track, CTA sticker, music) — open & fine-tune in CapCut

Units: seconds on the output timeline; x/y in CapCut units (-1..1 = half canvas, +y = up).
"""
from __future__ import annotations

from .paths import app_root
import json
import shutil
from pathlib import Path

from .grade import adjust_filters, wb_filter
from .media import FFMPEG, IS_MAC, run

ROOT = app_root()


# ------------------------------------------------------------------ helpers
def load_spec(path: str | Path) -> dict:
    spec = json.loads(Path(path).read_text())
    base = Path(path).resolve().parent
    spec["_base"] = str(base)
    return spec


def _p(spec: dict, rel: str) -> str:
    """Resolve source/asset paths: absolute, relative to the spec, or a library id."""
    if rel is None:
        return None
    p = Path(rel).expanduser()
    if p.is_absolute() and p.exists():
        return str(p)
    for cand in (Path(spec["_base"]) / rel, ROOT / "library" / rel):
        if cand.exists():
            return str(cand.resolve())
    for ext in (".cube", ".png", ".ttf", ".otf", ".wav", ".mp3", ".m4a"):
        c = ROOT / "library" / f"{rel}{ext}"
        if c.exists():
            return str(c)
    raise FileNotFoundError(rel)


def _src(spec: dict, key: str) -> str:
    return _p(spec, spec["sources"][key])


def _esc(path: str) -> str:  # ffmpeg filter-arg escaping
    return path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _gain(g: float | None) -> str:
    return f",colorchannelmixer=rr={g}:gg={g}:bb={g}" if g and abs(g - 1) > 0.01 else ""


def _final_encoder(quality: str) -> list[str]:
    if quality == "prores":
        return ["-c:v", "prores_videotoolbox" if IS_MAC else "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le"]
    if IS_MAC:  # Apple Silicon hardware HEVC, ~45 Mbit/s like CapCut's "Higher"
        return ["-c:v", "hevc_videotoolbox", "-b:v", "18M", "-maxrate", "24M", "-tag:v", "hvc1", "-pix_fmt", "yuv420p"]
    # smooth playback in phone players / chat previews; still far above what Instagram keeps (~3-5 Mbit/s)
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-maxrate", "14M", "-bufsize", "28M",
            "-profile:v", "high", "-level", "4.2", "-pix_fmt", "yuv420p"]


# ------------------------------------------------------------------ captions (ASS)
def _ass_t(t: float) -> str:
    t = max(0.0, t)
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _bgr(hexcol: str, alpha: int = 0) -> str:
    h = hexcol.lstrip("#")
    return f"&H{alpha:02X}{h[4:6]}{h[2:4]}{h[0:2]}".upper()


def write_ass(spec: dict, out: Path) -> Path:
    W, H = spec["canvas"]["w"], spec["canvas"]["h"]
    cs, ts = spec["caption_style"], spec.get("title", {}).get("style", {})
    yc = lambda y: int(H / 2 - y * H / 2)  # CapCut y -> pixels
    box = cs.get("box")  # text plate: {"color": "#000000", "alpha": 0.35, "pad": 14}
    if box:
        a = int(255 * (1 - box.get("alpha", 0.6)))
        cap_border = f"{_bgr(box.get('color', '#000000'), a)},&H00000000,{-1 if cs.get('bold') else 0},0,0,0,100,100," \
                     f"{cs.get('spacing', 0)},0,3,{box.get('pad', 14)},0"
    else:
        cap_border = f"&H00000000,&H{int(255 * (1 - cs.get('shadow_alpha', 0.35))):02X}000000," \
                     f"{-1 if cs.get('bold') else 0},0,0,0,100,100,{cs.get('spacing', 0)},0,1," \
                     f"{cs.get('outline', 0)},{cs.get('shadow', 1.5)}"
    styles = [f"Style: Cap,{cs['font_name']},{cs['size']},{_bgr(cs.get('color', '#FFFFFF'))},&H00000000,"
              f"{cap_border},5,40,40,0,1"]
    if ts:
        styles.append(
            f"Style: Title,{ts['font_name']},{ts['size']},{_bgr(ts.get('color', '#FFFFFF'))},&H00000000,"
            f"&H00000000,&H80000000,-1,0,0,0,{ts.get('scale_x', 100)},{ts.get('scale_y', 100)},0,0,1,0,"
            f"{ts.get('shadow', 2)},5,40,40,0,1")
    ev = []
    # ---- safe zone + face: one level for all captions, one for the title
    from .safezone import DEFAULT, scaled, face_box, place_block, right_edge
    z = scaled(spec.get("safe_zone") or DEFAULT, W, H)
    face = None
    if spec.get("avoid_face", True):
        if "_face" not in spec:
            rs = dict(spec, sources={k: _src(spec, k) for k in spec.get("sources", {})})
            fb = face_box(rs, ROOT)
            spec["_face"] = [fb[0] / W, fb[1] / H, fb[2] / W, fb[3] / H] if fb else None
        if spec["_face"]:
            f = spec["_face"]
            face = (f[0] * W, f[1] * H, f[2] * W, f[3] * H)
    fonts = {}
    for fp in spec.get("fonts", []):
        try:
            from PIL import ImageFont
            fpath = _p(spec, fp)
            fonts[ImageFont.truetype(fpath, 10).getname()[0].lower()] = fpath
        except Exception:
            pass

    def width(text: str, st: dict) -> float:
        from PIL import ImageFont
        fam = st["font_name"].lower()
        path = next((v for k, v in fonts.items() if fam.startswith(k) or k.startswith(fam.split()[0])), None)
        w = (ImageFont.truetype(path, int(st["size"])).getlength(text) if path
             else len(text) * st["size"] * 0.56)
        return w * st.get("scale_x", 100) / 100

    def fit(line: str, st: dict, y0: float, y1: float) -> tuple[float, str]:
        left, right = z["left"], right_edge(z, y0, y1)
        w = width(line, st)
        sc = min(1.0, (right - left) / w) if w else 1.0
        w *= sc
        x = W / 2 if (W / 2 - w / 2 >= left and W / 2 + w / 2 <= right) else (left + right) / 2
        tag = "" if sc >= 0.999 else f"\\fscx{st.get('scale_x', 100) * sc:.0f}\\fscy{st.get('scale_y', 100) * sc:.0f}"
        return x, tag, sc

    fade = int(cs.get("fade_ms", 80))
    gap = cs.get("line_gap", int(cs["size"] * 0.7))
    caps = spec.get("captions", [])
    nmax = max((len(c["text"].split("\n")) for c in caps), default=1)
    cap_c = place_block(yc(cs["y"]), gap * (nmax - 1) + cs["size"], z, face)
    up = (lambda x: x.upper()) if cs.get("uppercase") else (lambda x: x)
    def popa(sc: float, st: dict = cs) -> str:  # pop-in that ends at the fitted scale
        if not st.get("pop"):
            return ""
        bx, by = st.get("scale_x", 100) * sc, st.get("scale_y", 100) * sc
        return (f"\\fscx{bx * .9:.0f}\\fscy{by * .9:.0f}\\t(0,120,\\fscx{bx:.0f}\\fscy{by:.0f})")
    mode = cs.get("mode", "phrase")
    if mode == "words":  # 1-3 words at a time, the spoken word lights up (short-form "word pop" look)
        hl = _bgr(cs.get("highlight") or spec.get("title", {}).get("colors", ["#FFFFFF", "#F6DB92"])[-1])
        base = _bgr(cs.get("color", "#FFFFFF"))
        per = int(cs.get("words_per", 3))
        cap_c = place_block(yc(cs["y"]), cs["size"], z, face)
        for c in caps:
            ws = c.get("words")
            if not ws:  # older spec: spread words evenly over the caption
                tk = c["text"].split()
                d = (c["end"] - c["start"]) / max(1, len(tk))
                ws = [{"t": t, "s": c["start"] + i * d, "e": c["start"] + (i + 1) * d} for i, t in enumerate(tk)]
            groups, cur = [], []
            budget = int(cs.get("words_chars", 14))  # keep the words big: 1-3 words, ~14 letters a line
            for w in ws:
                if cur and (len(cur) >= per or len(" ".join(v["t"] for v in cur + [w])) > budget):
                    groups.append(cur); cur = []
                cur.append(w)
            if cur:
                groups.append(cur)
            for gi in range(len(groups) - 1):  # 'из', 'в', 'и' go with the next word, never dangle
                if len(groups[gi]) > 1 and len(groups[gi][-1]["t"]) <= 2:
                    groups[gi + 1].insert(0, groups[gi].pop())
            for gi, g in enumerate(groups):
                g_end = groups[gi + 1][0]["s"] if gi + 1 < len(groups) else c["end"]
                line = " ".join(up(w["t"]) for w in g)
                x, tag, sc = fit(line, cs, cap_c - cs["size"] / 2, cap_c + cs["size"] / 2)
                for wi, w in enumerate(g):
                    a = g[0]["s"] if wi == 0 else w["s"]
                    b = g[wi + 1]["s"] if wi + 1 < len(g) else g_end
                    if b - a < 0.02:
                        continue
                    txt = " ".join((f"{{\\1c{hl}}}{up(v['t'])}{{\\1c{base}}}" if vi == wi else up(v["t"]))
                                   for vi, v in enumerate(g))
                    anim = popa(sc) if wi == 0 else ""
                    ev.append(f"Dialogue: 0,{_ass_t(a)},{_ass_t(b)},Cap,,0,0,0,,"
                              f"{{\\an5\\pos({int(x)},{int(cap_c)}){tag}{anim}}}{txt}")
    else:
        for c in caps:
            lines = up(c["text"]).split("\n")
            y0 = cap_c - gap * (len(lines) - 1) / 2
            for li, line in enumerate(lines):  # one event per line -> exact line pitch like CapCut
                yy = y0 + li * gap
                x, tag, sc = fit(line, cs, yy - cs["size"] / 2, yy + cs["size"] / 2)
                ev.append(f"Dialogue: 0,{_ass_t(c['start'])},{_ass_t(c['end'])},Cap,,0,0,0,,"
                          f"{{\\an5\\pos({int(x)},{int(yy)}){tag}{popa(sc)}\\fad({fade},{fade})}}{line}")
    if t := spec.get("title"):
        lh = ts.get("line_gap", int(ts["size"] * 1.3))
        th = ts["size"] * ts.get("scale_y", 100) / 100
        n = len(t["lines"])
        tc = place_block(yc(ts["y"]) - lh // 2 + lh * (n - 1) / 2, lh * (n - 1) + th, z, face)
        y0 = tc - lh * (n - 1) / 2
        blur_ms = int(t.get("blur_in", 0.3) * 1000)
        for i, line in enumerate(t["lines"]):
            st = t["start"] + (t.get("line_delay", 0.5) * i)
            col = t.get("colors", ["#FFFFFF"] * len(t["lines"]))[i]
            yy = y0 + i * lh
            x, tag, sc = fit(line, ts, yy - th / 2, yy + th / 2)
            anim = "" if i == 0 else f"\\blur18\\t(0,{blur_ms},\\blur0)\\fad({blur_ms // 2},0)"
            ev.append(f"Dialogue: 1,{_ass_t(st)},{_ass_t(t['end'])},Title,,0,0,0,,"
                      f"{{\\an5\\pos({int(x)},{int(yy)}){tag}\\1c{_bgr(col)}{anim}}}{line}")
    out.write_text(
        "[Script Info]\nScriptType: v4.00+\nWrapStyle: 2\nScaledBorderAndShadow: yes\n"
        f"PlayResX: {W}\nPlayResY: {H}\n\n[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n" + "\n".join(styles) +
        "\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        + "\n".join(ev) + "\n", encoding="utf-8")
    return out


# ------------------------------------------------------------------ final render
def render_reel(spec: dict, out: Path, quality: str = "high", preview: bool = False) -> Path:
    """One ffmpeg pass. Memory stays ~constant (each input is decoded as a stream)."""
    if not spec.get("_snapped") and not spec.get("raw_cuts"):
        from .cutsafe import snap_voice
        snap_voice(spec, lambda k: _src(spec, k)); spec["_snapped"] = True
    W, H, FPS = spec["canvas"]["w"], spec["canvas"]["h"], spec["canvas"]["fps"]
    if preview:
        W, H = W // 2, H // 2
    dur = spec["duration"]
    look = spec.get("aroll_look", {})
    inputs: list[str] = []
    fc: list[str] = []
    n_in = [0]

    def add_raw(*args: str) -> int:
        inputs.extend(args)
        n_in[0] += 1
        return n_in[0] - 1

    def add_input(path: str, ss: float, t: float) -> int:
        return add_raw("-ss", f"{ss:.4f}", "-t", f"{t:.4f}", "-i", path)

    nlut = [0]

    def lut(name: str | None, mix: float | None = None) -> str:
        if not name:
            return ""
        f = f"lut3d='{_esc(_p(spec, name))}':interp=tetrahedral"
        if mix is None or mix >= 0.99:
            return "," + f
        nlut[0] += 1
        k = nlut[0]  # blend the graded picture over the original at `mix` strength
        return (f",format=gbrp,split[lo{k}][lg{k}];[lg{k}]{f}[lc{k}];[lc{k}][lo{k}]"
                f"blend=all_mode=normal:all_opacity={max(0.0, mix):.2f}")

    # A-roll: zoom + reframe + grade, segments concatenated (voice track drives timing)
    S, ax, ay = look.get("zoom", 1.0), look.get("x", 0.0), look.get("y", 0.0)
    sw, sh = int(round(W * S / 2) * 2), int(round(H * S / 2) * 2)
    cx = int((sw - W) / 2 - ax * W / 2)
    cy = int((sh - H) / 2 + ay * H / 2)
    vlabels, alabels = [], []
    for k, seg in enumerate(spec["voice"]):
        i = add_input(_src(spec, seg["src"]), seg["in"], seg["dur"])
        fc.append(f"[{i}:v]fps={FPS},scale={sw}:{sh}:force_original_aspect_ratio=increase:flags=lanczos,"
                  f"crop={sw}:{sh},crop={W}:{H}:{cx}:{cy},setsar=1"
                  f"{_gain(look.get('gain'))}{wb_filter(look.get('wb_gain'))}{lut(look.get('lut'), look.get('lut_mix'))}{adjust_filters(look.get('adjust'))}"
                  f",format=yuv420p,setpts=PTS-STARTPTS[av{k}]")
        fd = min(0.012, seg["dur"] / 4)  # micro-fades: no clicks at cut points
        fc.append(f"[{i}:a]aresample=48000,asetpts=PTS-STARTPTS,afade=t=in:d={fd:.3f},"
                  f"afade=t=out:st={seg['dur'] - fd:.4f}:d={fd:.3f}[aa{k}]")
        vlabels.append(f"[av{k}]")
        alabels.append(f"[aa{k}]")
    fc.append(f"{''.join(vlabels)}concat=n={len(vlabels)}:v=1:a=0[base]")
    fc.append(f"{''.join(alabels)}concat=n={len(alabels)}:v=0:a=1[voice]")

    # B-roll inserts (video only; voice keeps running underneath = J/L cuts)
    last, bl = "base", spec.get("broll_look", {})
    for k, b in enumerate(spec.get("broll", [])):
        sp = b.get("speed", 1.0)
        if b.get("image"):  # photo: gentle push-in (Ken Burns), same grade as video B-roll
            i = add_raw("-loop", "1", "-framerate", str(FPS), "-t", f"{b['dur'] + 0.1:.3f}", "-i", _src(spec, b["src"]))
            grade = _gain(b.get("gain")) + (lut(bl.get("bw")) + ",hue=s=0" if b.get("look") == "bw" else lut(bl.get("color"), bl.get("lut_mix"))) + adjust_filters(bl.get("adjust") or look.get("adjust"))
            frames = int(b["dur"] * FPS) + 3
            fc.append(f"[{i}:v]scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2},"
                      f"zoompan=z='1+0.06*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS},"
                      f"setsar=1{grade},format=yuv420p,trim=0:{b['dur']:.4f},setpts=PTS-STARTPTS+{b['start']:.4f}/TB[b{k}]")
            fc.append(f"[{last}][b{k}]overlay=eof_action=pass:enable='between(t,{b['start'] - 0.004:.4f},"
                      f"{b['start'] + b['dur'] - 0.001:.4f})'[v{k}]")
            last = f"v{k}"
            continue
        i = add_input(_src(spec, b["src"]), b["in"], b["dur"] * sp + 0.1)
        grade = _gain(b.get("gain")) + (lut(bl.get("bw")) + ",hue=s=0" if b.get("look") == "bw" else lut(bl.get("color"), bl.get("lut_mix"))) + adjust_filters(bl.get("adjust") or look.get("adjust"))
        fc.append(f"[{i}:v]setpts=(PTS-STARTPTS)/{sp},fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase,"
                  f"crop={W}:{H},setsar=1{grade},format=yuv420p,trim=0:{b['dur']:.4f},"
                  f"setpts=PTS+{b['start']:.4f}/TB[b{k}]")
        fc.append(f"[{last}][b{k}]overlay=eof_action=pass:enable='between(t,{b['start'] - 0.004:.4f},"
                  f"{b['start'] + b['dur'] - 0.001:.4f})'[v{k}]")
        last = f"v{k}"

    # full-frame shadow gradient (CapCut "Тени" layer) under the captions
    if sh := spec.get("shadow"):
        i = add_raw("-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", _p(spec, sh))
        fc.append(f"[{i}:v]format=rgba,scale={W}:{H}[shd]")
        fc.append(f"[{last}][shd]overlay=0:0:format=auto:shortest=1[vsh]")
        last = "vsh"

    # captions + title
    ass = write_ass(spec, Path(out).with_suffix(".ass")) if not preview else None
    if preview:
        ps = dict(spec, canvas=dict(spec["canvas"], w=W, h=H))
        ps["caption_style"] = dict(spec["caption_style"], size=spec["caption_style"]["size"] // 2)
        if spec.get("title"):
            ps["title"] = dict(spec["title"], style=dict(spec["title"]["style"], size=spec["title"]["style"]["size"] // 2,
                                                       line_gap=spec["title"]["style"].get("line_gap", 110) // 2))
        ass = write_ass(ps, Path(out).with_suffix(".ass"))
    # libass reads ONE fonts folder: gather every font the spec uses (any library subfolder) into one
    fdir = Path(out).parent / ".fonts"
    fdir.mkdir(parents=True, exist_ok=True)
    for f in spec.get("fonts", []):
        src = Path(_p(spec, f))
        if src.exists() and not (fdir / src.name).exists():
            shutil.copy2(src, fdir / src.name)
    fd = f":fontsdir='{_esc(str(fdir))}'" if spec.get("fonts") else ""
    fc.append(f"[{last}]subtitles='{_esc(str(ass))}'{fd}[vs]")
    last = "vs"

    # CTA sticker with pop (scale 0.2 -> 1.08 -> 1.0) — expression-driven, no extra frames in RAM
    # stickers on top: the end button + any overlays (photo, video, icon, PNG) placed on words/times
    layers = ([dict(spec["sticker"], _end=True)] if spec.get("sticker") else []) + list(spec.get("overlays", []))
    for k, st in enumerate(layers):
        if st.get("icon"):  # GRIN icon badge (any colour, optional label)
            from .icons import render as icon_png
            ic = st["icon"]
            st = dict(st, asset=str(icon_png(ic["name"], Path(out).parent / ".icons" / f"layer{k}.png", 220,
                                             color=ic.get("color", "#FFFFFF"), bg=ic.get("bg", "#1E1E1D"),
                                             shape=ic.get("shape", "circle"), label=ic.get("label") or None,
                                             label_color=ic.get("label_color"))))
        if not st.get("asset"):
            continue
        dur_l = st["end"] - st["start"]
        src = _p(spec, st["asset"])
        is_vid = Path(src).suffix.lower() in {".mov", ".mp4", ".m4v", ".webm", ".mkv"}
        if is_vid:  # small video window on top (picture-in-picture)
            i = add_input(src, st.get("in", 0.0), dur_l + 0.1)
        else:
            i = add_raw("-loop", "1", "-framerate", str(FPS), "-t", f"{dur_l:.3f}", "-i", src)
        tw = int(W * st.get("width", 0.37) / 2) * 2
        anim = st.get("anim", "pop")  # pop | fade | slide | none
        pop = st.get("pop", 0.35)
        sc = (f"if(lt(t,{pop}),0.2+0.88*t/{pop},if(lt(t,{pop + 0.12}),1.08-0.08*(t-{pop})/0.12,1))") \
            if anim == "pop" and pop else "1"
        pre = f"fps={FPS},trim=0:{dur_l:.4f}," if is_vid else ""
        fades = (f",fade=t=in:st=0:d=0.25:alpha=1,fade=t=out:st={max(0, dur_l - 0.25):.3f}:d=0.25:alpha=1"
                 if anim in ("fade", "slide") else "")
        fc.append(f"[{i}:v]{pre}format=rgba,scale=w='trunc({tw}*{sc}/2)*2':h=-2:eval=frame{fades},"
                  f"setpts=PTS-STARTPTS+{st['start']:.4f}/TB[stk{k}]")
        x = f"({W}-w)/2+{st.get('x', 0.0)}*{W}/2"
        y = f"({H}-h)/2-({st.get('y', 0.0)})*{H}/2"
        if anim == "slide":  # glides up 6% of the screen while appearing
            y += f"+{0.06 * H:.0f}*max(0,1-(t-{st['start']:.3f})/0.35)"
        fc.append(f"[{last}][stk{k}]overlay=x='{x}':y='{y}':eof_action=pass:format=auto:"
                  f"enable='between(t,{st['start']:.3f},{st['end']:.3f})'[vst{k}]")
        last = f"vst{k}"

    # fades
    fo = spec.get("fade_out", 0)
    fc.append(f"[{last}]fade=t=out:st={dur - fo:.4f}:d={fo:.4f},format=yuv420p[vout]" if fo
              else f"[{last}]format=yuv420p[vout]")

    # audio: voice (+ music bed under it)
    amix = "[voice]"
    if (m := spec.get("music")) and m.get("asset"):
        i = add_raw("-stream_loop", "-1", "-t", f"{dur:.3f}", "-i", _p(spec, m["asset"]))
        g = 10 ** (m.get("gain_db", -12) / 20)
        fc.append(f"[{i}:a]aresample=48000,volume={g:.4f},afade=t=in:d=0.3,"
                  f"afade=t=out:st={dur - max(fo, 0.5):.3f}:d={max(fo, 0.5):.3f}[mus]")
        fc.append("[voice][mus]amix=inputs=2:normalize=0:duration=first[amx]")
        amix = "[amx]"
    fc.append(f"{amix}afade=t=out:st={dur - max(fo, 0.05):.4f}:d={max(fo, 0.05):.4f},"
              f"alimiter=limit=0.97,atrim=0:{dur:.4f}[aout]")

    enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "26"] if preview else _final_encoder(quality)
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", *inputs, "-filter_complex", ";".join(fc),
           "-map", "[vout]", "-map", "[aout]", *enc, "-r", str(FPS), "-c:a", "aac", "-b:a", "256k",
           "-movflags", "+faststart", "-t", f"{dur:.4f}", str(out)]
    run(cmd)
    return Path(out)


# ------------------------------------------------------------------ CapCut draft
def capcut_reel(spec: dict, name: str, draft_root: Path | None = None) -> Path:
    if not spec.get("_snapped") and not spec.get("raw_cuts"):
        from .cutsafe import snap_voice
        snap_voice(spec, lambda k: _src(spec, k)); spec["_snapped"] = True
    try:
        import pycapcut as cc
    except ImportError as e:
        raise SystemExit("CapCut draft export is optional and experimental: "
                         "pip install -r requirements-capcut-experimental.txt (see THIRD_PARTY_NOTICES.md)") from e
    from pycapcut import (AudioMaterial, AudioSegment, ClipSettings, KeyframeProperty, TextSegment,
                          TextStyle, TrackType, VideoMaterial, VideoSegment)

    from .export_capcut import default_draft_root, hex_rgb, tr, us

    W, H, FPS = spec["canvas"]["w"], spec["canvas"]["h"], spec["canvas"]["fps"]
    root = draft_root or default_draft_root()
    root.mkdir(parents=True, exist_ok=True)
    script = cc.DraftFolder(str(root)).create_draft(name, W, H, FPS, allow_replace=True)
    for tt, nm, ri in [(TrackType.video, "aroll", 0), (TrackType.video, "broll", 1), (TrackType.video, "sticker", 2),
                       (TrackType.text, "captions", 0), (TrackType.text, "title", 1), (TrackType.text, "title2", 2),
                       (TrackType.audio, "music", 0)]:
        script.add_track(tt, nm, relative_index=ri)

    look, mats = spec.get("aroll_look", {}), {}
    mat = lambda key: mats.setdefault(key, VideoMaterial(_src(spec, key)))
    t = 0.0
    for seg in spec["voice"]:
        vs = VideoSegment(mat(seg["src"]), tr(t, seg["dur"]), source_timerange=tr(seg["in"], seg["dur"]),
                          clip_settings=ClipSettings(scale_x=look.get("zoom", 1), scale_y=look.get("zoom", 1),
                                                     transform_x=look.get("x", 0), transform_y=look.get("y", 0)))
        script.add_segment(vs, "aroll")
        t += seg["dur"]
    if fo := spec.get("fade_out"):  # fade to black on the last A-roll clip
        end = spec["voice"][-1]["dur"]
        vs.add_keyframe(KeyframeProperty.alpha, us(end - fo), 1.0)
        vs.add_keyframe(KeyframeProperty.alpha, us(end) - 1, 0.0)

    for b in spec.get("broll", []):
        sp = b.get("speed", 1.0)
        seg = VideoSegment(mat(b["src"]), tr(b["start"], b["dur"]), source_timerange=tr(b["in"], b["dur"] * sp),
                           speed=sp, volume=0.0)
        script.add_segment(seg, "broll")

    if sh := spec.get("shadow"):
        script.add_track(TrackType.video, "shadow", relative_index=3)
        script.add_segment(VideoSegment(VideoMaterial(_p(spec, sh)), tr(0, spec["duration"])), "shadow")

    cs = spec["caption_style"]
    cap_style = TextStyle(size=cs.get("capcut_size", 6.0), color=hex_rgb(cs.get("color", "#FFFFFF")), align=1,
                          auto_wrapping=False)
    for c in spec.get("captions", []):
        script.add_segment(TextSegment(c["text"], tr(c["start"], c["end"] - c["start"]), style=cap_style,
                                       clip_settings=ClipSettings(transform_y=cs["y"])), "captions")
    if ti := spec.get("title"):
        ts = ti["style"]
        for i, line in enumerate(ti["lines"]):
            st = ti["start"] + ti.get("line_delay", 0.5) * i
            col = ti.get("colors", ["#FFFFFF"] * 9)[i]
            y = ts["y"] + (0.06 if i == 0 else -0.06)
            script.add_segment(TextSegment(line, tr(st, ti["end"] - st),
                                           style=TextStyle(size=ts.get("capcut_size", 13.0), bold=True,
                                                           color=hex_rgb(col), align=1),
                                           clip_settings=ClipSettings(transform_y=y)), "title" if i == 0 else "title2")

    if st := spec.get("sticker"):
        sv = VideoSegment(VideoMaterial(_p(spec, st["asset"])), tr(st["start"], st["end"] - st["start"]),
                          clip_settings=ClipSettings(scale_x=st.get("capcut_scale", 0.5),
                                                     scale_y=st.get("capcut_scale", 0.5), transform_y=st.get("y", 0)))
        s0, pop = st.get("capcut_scale", 0.5), st.get("pop", 0.35)
        sv.add_keyframe(KeyframeProperty.uniform_scale, 0, s0 * 0.2)
        sv.add_keyframe(KeyframeProperty.uniform_scale, us(pop), s0 * 1.08)
        sv.add_keyframe(KeyframeProperty.uniform_scale, us(pop + 0.12), s0)
        script.add_segment(sv, "sticker")

    if (m := spec.get("music")) and m.get("asset"):
        am = AudioMaterial(_p(spec, m["asset"]))
        d = min(spec["duration"], am.duration / 1e6)
        seg = AudioSegment(am, tr(0, d), volume=10 ** (m.get("gain_db", -12) / 20))
        seg.add_fade(us(0.3), us(max(spec.get("fade_out", 0.5), 0.5)))
        script.add_segment(seg, "music")
    script.save()
    return root / name
