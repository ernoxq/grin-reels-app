# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
# Licensed, not sold: see LICENSE.md. Redistribution or resale is prohibited.
"""Timeline -> editable CapCut desktop draft (via pyCapCut, MIT, by GuanYixuan).

Why a draft and not a render: the draft only REFERENCES your original files with
in/out points, so CapCut decodes the camera originals directly. Quality loss = zero
until you hit Export in CapCut (choose 4K / 60 fps / "Higher" bitrate / HEVC there).

macOS draft root (CapCut desktop, international build):
  ~/Movies/CapCut/User Data/Projects/com.lveditor.draft/
CapCut lists drafts it finds there on launch (or after you go back to the Home screen).

Known limits (check README "CapCut caveats"):
  * Custom .ttf/.otf fonts can't be referenced by path in the draft -> we write the text
    with CapCut's default font and record the wanted font in the draft name/notes; or
    use `caption_mode = "png"` to burn exact-font captions as transparent PNG overlays.
  * .cube LUTs aren't writable into the draft -> either graded ProRes intermediate
    (`--bake-lut`) or apply the LUT in CapCut: Adjust > LUT > Import.
  * CapCut's own sticker/effect/transition IDs come from its online catalogue; we use
    your local PNGs as image clips on an overlay track instead (fully offline).
"""
from __future__ import annotations

import os
from pathlib import Path

import pycapcut as cc
from pycapcut import (AudioMaterial, AudioSegment, ClipSettings, KeyframeProperty, TextSegment,
                      TextStyle, TrackType, VideoMaterial, VideoSegment)

from .timeline import Timeline

US = 1_000_000
DEFAULT_DRAFT_ROOT = Path.home() / "Movies/CapCut/User Data/Projects/com.lveditor.draft"


def us(t: float) -> int:
    return int(round(t * US))


def tr(start: float, dur: float) -> cc.Timerange:
    return cc.Timerange(us(start), max(1, us(dur)))


def hex_rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def export_capcut(tl: Timeline, name: str, draft_root: Path = DEFAULT_DRAFT_ROOT,
                  main_src_override: str | None = None, caption_pngs: list[tuple[str, float, float]] | None = None
                  ) -> Path:
    draft_root.mkdir(parents=True, exist_ok=True)
    folder = cc.DraftFolder(str(draft_root))
    script = folder.create_draft(name, tl.width, tl.height, tl.fps, allow_replace=True)

    # Track order = layer order (later added video track draws on top).
    script.add_track(TrackType.video, "main")
    script.add_track(TrackType.video, "overlays", relative_index=1)
    script.add_track(TrackType.video, "caption_png", relative_index=2)
    script.add_track(TrackType.text, "captions")
    script.add_track(TrackType.audio, "sfx")
    script.add_track(TrackType.audio, "music", relative_index=1)

    # --- main: one material, many segments (each = a kept range) ---------------
    src = main_src_override or tl.source
    main_mat = VideoMaterial(src)
    for c in tl.main:
        script.add_segment(VideoSegment(main_mat, tr(c.start, c.dur), source_timerange=tr(c.src_in, c.dur)), "main")

    # --- overlays (stickers / images) with keyframed "pop" ---------------------
    mats: dict[str, VideoMaterial] = {}
    for o in tl.overlays:
        m = mats.setdefault(o.src, VideoMaterial(o.src))
        seg = VideoSegment(m, tr(o.start, o.dur),
                           clip_settings=ClipSettings(scale_x=o.scale, scale_y=o.scale, transform_x=o.x, transform_y=o.y))
        if o.anim == "pop":
            seg.add_keyframe(KeyframeProperty.uniform_scale, 0, o.scale * 0.6)
            seg.add_keyframe(KeyframeProperty.uniform_scale, us(0.12), o.scale * 1.08)
            seg.add_keyframe(KeyframeProperty.uniform_scale, us(0.22), o.scale)
        elif o.anim == "slide_up":
            seg.add_keyframe(KeyframeProperty.position_y, 0, o.y - 0.3)
            seg.add_keyframe(KeyframeProperty.position_y, us(0.25), o.y)
        seg.add_keyframe(KeyframeProperty.alpha, max(0, us(o.dur - 0.15)), 1.0)
        seg.add_keyframe(KeyframeProperty.alpha, us(o.dur) - 1, 0.0)
        script.add_segment(seg, "overlays")

    # --- captions: editable CapCut text OR exact-font PNGs ----------------------
    st = tl.caption_style
    if caption_pngs:
        for path, s, d in caption_pngs:
            script.add_segment(VideoSegment(VideoMaterial(path), tr(s, d)), "caption_png")
    else:
        style = TextStyle(size=st.get("size", 9.0), bold=st.get("bold", True),
                          color=hex_rgb(st.get("color", "#FFFFFF")), align=1,
                          auto_wrapping=True, max_line_width=st.get("max_line_width", 0.8))
        border = cc.TextBorder(color=hex_rgb(st.get("stroke_color", "#000000")),
                               width=st.get("stroke_width", 40.0)) if st.get("stroke", True) else None
        for c in tl.captions:
            script.add_segment(TextSegment(c.text, tr(c.start, c.dur), style=style, border=border,
                                           clip_settings=ClipSettings(transform_y=st.get("y", -0.55))), "captions")

    # --- audio ------------------------------------------------------------------
    amats: dict[str, AudioMaterial] = {}
    for a in tl.sfx:
        m = amats.setdefault(a.src, AudioMaterial(a.src))
        d = min(a.dur, m.duration / US - a.src_in)
        script.add_segment(AudioSegment(m, tr(a.start, d), source_timerange=tr(a.src_in, d), volume=a.volume), "sfx")

    for a in tl.music:
        m = amats.setdefault(a.src, AudioMaterial(a.src))
        d = min(a.dur, m.duration / US - a.src_in)
        seg = AudioSegment(m, tr(a.start, d), source_timerange=tr(a.src_in, d), volume=1.0)
        if a.fade_in or a.fade_out:
            seg.add_fade(us(a.fade_in), us(a.fade_out))
        for off, gain in a.volume_keys:
            seg.add_keyframe(min(us(off), us(d) - 1), gain)
        script.add_segment(seg, "music")

    script.save()
    return draft_root / name


def default_draft_root() -> Path:
    env = os.environ.get("CAPCUT_DRAFTS")
    return Path(env).expanduser() if env else DEFAULT_DRAFT_ROOT
