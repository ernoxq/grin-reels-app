# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
# Licensed, not sold: see LICENSE.md. Redistribution or resale is prohibited.
"""One job = one folder in jobs/<id>/ with every intermediate cached:
    probe.json  silences.json  words.json  timeline.json  preview.mp4  (+ CapCut draft)
Re-running a job skips any step whose output exists -> tweak a preset, rebuild in seconds.
"""
from __future__ import annotations

import json
import tomllib
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from . import silence
from .export_capcut import default_draft_root, export_capcut
from .library import Library
from .media import probe
from .render import bake_lut, caption_pngs, render_preview
from .timeline import Timeline, build_timeline
from .transcribe import filler_ranges, load_srt, transcribe

Log = Callable[[str], None]


def load_preset(path: Path) -> dict:
    return tomllib.loads(path.read_text())


def run_job(src: Path, job_dir: Path, preset: dict, library_root: Path, *, draft_name: str | None = None,
            draft_root: Path | None = None, preview: bool = True, log: Log = print) -> dict:
    job_dir.mkdir(parents=True, exist_ok=True)
    src = src.resolve()
    lib = Library(library_root)
    info = probe(src)
    (job_dir / "probe.json").write_text(json.dumps(asdict(info), indent=1))
    log(f"probe: {info.display_size} @ {info.fps:.2f} fps, {info.duration:.1f}s")

    # 1. analysis --------------------------------------------------------------
    cut = preset.get("cut", {})
    words = []
    if preset.get("captions", {}).get("enabled", True) or cut.get("remove_fillers"):
        srt = src.with_suffix(".srt")
        if srt.exists():
            words = load_srt(srt)
            log(f"captions: using {srt.name}")
        else:
            try:
                words = transcribe(str(src), job_dir / "words.json", preset.get("asr", {}).get("model", "small"),
                                   preset.get("asr", {}).get("language"))
                log(f"asr: {len(words)} words")
            except ImportError:
                log("asr: faster-whisper not installed -> no captions (pip install faster-whisper)")

    if cut.get("vad", "ffmpeg") == "silero":
        keeps = silence.pad_speech(silence.detect_speech_silero(str(src), cut.get("min_silence", 0.45)),
                                   info.duration, cut.get("pad", 0.12))
    else:
        sil = silence.detect_silences_ffmpeg(str(src), cut.get("noise_db", -35), cut.get("min_silence", 0.45))
        (job_dir / "silences.json").write_text(json.dumps(sil))
        keeps = silence.keep_ranges_from_silences(sil, info.duration, pad=cut.get("pad", 0.12),
                                                  min_keep=cut.get("min_keep", 0.2))
    if cut.get("remove_fillers") and words:
        fillers = {f.lower() for f in cut.get("fillers", [])}
        keeps = silence.subtract(keeps, filler_ranges(words, fillers))
    saved = info.duration - sum(e - s for s, e in keeps)
    log(f"cut: {len(keeps)} segments, removed {saved:.1f}s of {info.duration:.1f}s")

    # 2. optional LUT bake (only if you want the grade locked in) -------------------
    tl = build_timeline(str(src), info.display_size, info.fps, keeps, words, lib, preset)
    main_override = None
    if tl.lut and preset.get("color", {}).get("bake", False):
        graded = job_dir / "graded_prores.mov"
        if not graded.exists():
            log("color: baking LUT to ProRes 422 HQ (slow, big, lossless-ish)…")
            bake_lut(str(src), tl.lut, graded)
        main_override = str(graded)
    tl.save(job_dir / "timeline.json")
    log(f"timeline: {len(tl.main)} clips, {len(tl.captions)} captions, {len(tl.overlays)} overlays, "
        f"{len(tl.sfx)} sfx, {len(tl.music)} music; {tl.duration:.1f}s")

    # 3. exports ---------------------------------------------------------------
    font = _font_path(lib, preset)
    cap_pngs = None
    if preset.get("captions", {}).get("mode", "text") == "png" and font and tl.captions:
        cap_pngs = caption_pngs(tl, job_dir / "captions_png", font)
    name = draft_name or f"auto_{src.stem}"
    draft = export_capcut(tl, name, draft_root or default_draft_root(), main_override, cap_pngs)
    log(f"capcut: draft written -> {draft}")

    out = {"job": str(job_dir), "draft": str(draft), "duration": tl.duration, "notes": tl.notes}
    if preview:
        out["preview"] = str(render_preview(tl, job_dir / "preview.mp4", font))
        log("preview: done")
    (job_dir / "result.json").write_text(json.dumps(out, indent=1))
    return out


def rebuild_from_timeline(job_dir: Path, name: str, draft_root: Path | None = None) -> Path:
    """You hand-edited timeline.json? Re-export without any analysis."""
    return export_capcut(Timeline.load(job_dir / "timeline.json"), name, draft_root or default_draft_root())


def _font_path(lib: Library, preset: dict) -> str | None:
    fid = preset.get("captions", {}).get("style", {}).get("font")
    a = lib.get(fid) if fid else None
    return a.path if a else None
