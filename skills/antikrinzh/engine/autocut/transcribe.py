# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
# Licensed, not sold: see LICENSE.md. Redistribution or resale is prohibited.
"""Local speech-to-text with word timestamps (faster-whisper, CTranslate2, int8 on CPU).

On an 8 GB Mac: model "small" int8 ~ 0.6-1 GB RAM, roughly real-time on M1.
Use "base" for speed, "medium" only if you close everything else.
Results are cached next to the job as words.json, so re-runs cost nothing.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Word:
    text: str
    start: float
    end: float
    prob: float = 1.0


def _pcm(path: str):
    """Decode with ffmpeg ourselves: newer PyAV breaks faster-whisper's own decoder."""
    import subprocess

    import numpy as np

    from .media import FFMPEG
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", str(path), "-ac", "1", "-ar", "16000",
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


def transcribe(path: str, cache: Path, model_size: str = "small", language: str | None = None) -> list[Word]:
    if cache.exists():
        return [Word(**w) for w in json.loads(cache.read_text())]

    from faster_whisper import WhisperModel  # imported lazily: not needed for silence-only runs

    model = WhisperModel(model_size, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4)
    segments, info = model.transcribe(_pcm(path), language=language, word_timestamps=True,
                                       vad_filter=True, beam_size=1)
    words: list[Word] = []
    for seg in segments:  # generator: segments are decoded lazily, memory stays flat
        for w in seg.words or []:
            words.append(Word(w.word.strip(), float(w.start), float(w.end), float(w.probability)))
    del model
    cache.with_name("lang.txt").write_text(info.language or "")
    cache.write_text(json.dumps([asdict(w) for w in words], ensure_ascii=False))
    return words


def load_srt(path: Path) -> list[Word]:
    """Fallback when you already have subtitles (e.g. exported from CapCut auto-captions)."""
    import re
    ts = r"(\d+):(\d+):(\d+)[,.](\d+)"
    words, block = [], path.read_text(encoding="utf-8-sig").strip().split("\n\n")
    for b in block:
        lines = b.strip().splitlines()
        m = next((re.findall(ts, l) for l in lines if "-->" in l), None)
        if not m:
            continue
        to_s = lambda h, mi, s, ms: int(h) * 3600 + int(mi) * 60 + int(s) + int(ms) / 1000
        text = " ".join(lines[lines.index(next(l for l in lines if "-->" in l)) + 1:])
        s, e = to_s(*m[0]), to_s(*m[1])
        toks = text.split() or [text]
        step = (e - s) / len(toks)  # no per-word timing in SRT: spread evenly
        words += [Word(t, s + i * step, s + (i + 1) * step) for i, t in enumerate(toks)]
    return words


def filler_ranges(words: list[Word], fillers: set[str]) -> list[tuple[float, float]]:
    norm = lambda s: "".join(ch for ch in s.lower() if ch.isalnum())
    return [(w.start, w.end) for w in words if norm(w.text) in fillers]


VOWELS = set("аеёиоуыэюяaeiouyăâîіїєáéíóú")


def align_script(path: str, script_lines: list[str], noise_db: float = -35, min_silence: float = 0.3) -> list[Word]:
    """LITE mode (no speech model available, e.g. iPhone-only cloud session).
    Speech ranges come from ffmpeg silencedetect; script words are laid over them in order,
    each word's length proportional to its vowel count (syllables). Needs ONE clean take that
    follows the script; timing error is typically 0.1-0.3 s, fine for phrase captions."""
    from .media import probe
    from .silence import detect_silences_ffmpeg, keep_ranges_from_silences
    dur = probe(path).duration
    speech = keep_ranges_from_silences(detect_silences_ffmpeg(path, noise_db, min_silence), dur, pad=0.0, min_keep=0.15)
    toks = [t for line in script_lines for t in line.split()]
    weight = lambda t: max(1, sum(ch in VOWELS for ch in t.lower())) + 0.3
    total_w = sum(weight(t) for t in toks)
    total_s = sum(e - s for s, e in speech) or dur
    words, ri, t = [], 0, speech[0][0] if speech else 0.0
    for tok in toks:
        need = weight(tok) / total_w * total_s
        while ri < len(speech) and t >= speech[ri][1] - 1e-3:
            ri += 1
            if ri < len(speech):
                t = speech[ri][0]
        end = t + need
        if ri < len(speech):
            end = min(end, speech[ri][1])
        words.append(Word(tok, round(t, 3), round(max(end, t + 0.05), 3), 0.8))
        t = end
    return words
