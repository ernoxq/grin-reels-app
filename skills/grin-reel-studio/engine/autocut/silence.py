# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
# Licensed, not sold: see LICENSE.md. Redistribution or resale is prohibited.
"""Silence / pause detection -> list of KEEP ranges (source seconds).

Two backends:
  * ffmpeg `silencedetect` (default): zero extra deps, streams audio, ~10 MB RAM.
  * Silero VAD via faster-whisper (optional): better on noisy rooms / music beds.
Both return the same shape so the rest of the pipeline doesn't care.
"""
from __future__ import annotations

import re
import subprocess

from .media import FFMPEG

Range = tuple[float, float]

_START = re.compile(r"silence_start:\s*(-?[\d.]+)")
_END = re.compile(r"silence_end:\s*(-?[\d.]+)")


def detect_silences_ffmpeg(path: str, noise_db: float = -35.0, min_silence: float = 0.45) -> list[Range]:
    """Stream the audio through ffmpeg and parse silence markers from stderr."""
    cmd = [FFMPEG, "-hide_banner", "-nostats", "-i", path, "-vn", "-sn", "-dn",
           "-af", f"silencedetect=noise={noise_db}dB:d={min_silence}", "-f", "null", "-"]
    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True)
    silences: list[Range] = []
    start: float | None = None
    assert proc.stderr is not None
    for line in proc.stderr:  # line-by-line: never holds the whole log in memory
        if m := _START.search(line):
            start = max(0.0, float(m.group(1)))
        elif (m := _END.search(line)) and start is not None:
            silences.append((start, float(m.group(1))))
            start = None
    proc.wait()
    if start is not None:  # file ended while silent
        silences.append((start, float("inf")))
    return silences


def detect_speech_silero(path: str, min_silence: float = 0.45) -> list[Range]:
    """Speech ranges using Silero VAD bundled in faster-whisper (ONNX, CPU, ~50 MB RAM)."""
    from faster_whisper.audio import decode_audio
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    audio = decode_audio(path, sampling_rate=16000)  # float32 mono: ~230 MB per hour
    opts = VadOptions(min_silence_duration_ms=int(min_silence * 1000), speech_pad_ms=0)
    return [(t["start"] / 16000, t["end"] / 16000) for t in get_speech_timestamps(audio, opts)]


def invert(ranges: list[Range], duration: float) -> list[Range]:
    out, cursor = [], 0.0
    for s, e in sorted(ranges):
        if s > cursor:
            out.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < duration:
        out.append((cursor, duration))
    return out


def keep_ranges_from_silences(silences: list[Range], duration: float, *, pad: float = 0.12,
                              min_keep: float = 0.20) -> list[Range]:
    """Speech = complement of silence, padded so cuts land on breath, not mid-phoneme."""
    keeps = []
    for s, e in invert([(s, min(e, duration)) for s, e in silences], duration):
        s, e = max(0.0, s - pad), min(duration, e + pad)
        if e - s >= min_keep:
            keeps.append((s, e))
    return merge(keeps)


def pad_speech(speech: list[Range], duration: float, pad: float = 0.12, min_keep: float = 0.20) -> list[Range]:
    return merge([(max(0, s - pad), min(duration, e + pad)) for s, e in speech if e - s >= min_keep])


def merge(ranges: list[Range], gap: float = 0.0) -> list[Range]:
    out: list[list[float]] = []
    for s, e in sorted(ranges):
        if out and s <= out[-1][1] + gap:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return [(s, e) for s, e in out]


def subtract(keeps: list[Range], cuts: list[Range], min_keep: float = 0.15) -> list[Range]:
    """Remove filler-word ranges (from the transcript) out of the keep list."""
    result = []
    for ks, ke in keeps:
        pieces = [(ks, ke)]
        for cs, ce in cuts:
            nxt = []
            for ps, pe in pieces:
                if ce <= ps or cs >= pe:
                    nxt.append((ps, pe))
                    continue
                if cs > ps:
                    nxt.append((ps, cs))
                if ce < pe:
                    nxt.append((ce, pe))
            pieces = nxt
        result.extend(p for p in pieces if p[1] - p[0] >= min_keep)
    return result
