"""Clean voice for every output (MP4 render, studio, CapCut).

Phone audio has hiss and low rumble, and is usually quiet (-20..-28 LUFS); raising it in an
editor raises the hiss too. clean() makes a copy of a talking clip with:
  highpass 80 Hz (rumble, desk knocks) -> gentle FFT denoise with noise tracking (hiss, room hum;
  mild on purpose: strong settings make voices sound "underwater") -> static gain to -14 LUFS
  (Reels/TikTok level) -> limiter at -1 dBTP.
Video is stream-copied, so it is fast and lossless; the copy is cached next to the job.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .media import FFMPEG

TARGET_LUFS = -14.0


def _floor_db(path: str) -> float:
    """Noise floor = level of the quietest 3% of 50 ms frames (breaths/pauses between words)."""
    import numpy as np
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", "16000", "-af", "highpass=f=80",
                          "-f", "s16le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    n = len(x) // 800
    if n < 10:
        return -60.0
    rms = np.sqrt((x[: n * 800].reshape(n, 800) ** 2).mean(1) + 1e-12)
    return float(np.clip(20 * np.log10(np.percentile(rms, 3)), -80, -20))


def denoise(path: str) -> str:
    nf = _floor_db(path)
    if nf > -45:  # no real pauses in this clip (or already processed): denoise only, never gate speech
        return "highpass=f=80,afftdn=nr=10:nf=-50:tn=1"
    thr = 10 ** ((nf + 12) / 20)  # soft gate just above the hiss: quiet gaps go quieter, words untouched
    return (f"highpass=f=80,afftdn=nr=14:nf={nf:.0f}:tn=1,"
            f"agate=threshold={thr:.5f}:ratio=2.5:range=0.12:attack=8:release=180:knee=4")


def _lufs(path: str, dn: str) -> float | None:
    r = subprocess.run([FFMPEG, "-hide_banner", "-nostats", "-i", path, "-vn", "-af",
                        f"{dn},loudnorm=print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr)
    try:
        v = float(json.loads(m.group(0))["input_i"]) if m else None
    except (ValueError, KeyError):
        return None
    return v if v is not None and v > -70 else None


def has_audio(path: str) -> bool:
    r = subprocess.run([FFMPEG, "-hide_banner", "-i", path], capture_output=True, text=True)
    return "Audio:" in r.stderr


def clean(src: str | Path, cache_dir: str | Path, suffix: str = " (чистый звук)") -> str:
    """Return the path of a cleaned copy of src (made once, reused while src is unchanged)."""
    src = Path(src)
    if not src.exists() or src.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".heic"} or not has_audio(str(src)):
        return str(src)
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    dst = cache / f"{src.stem}{suffix}.mp4"
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime and dst.stat().st_size > 0:
        return str(dst)
    dn = denoise(str(src))
    lufs = _lufs(str(src), dn)
    gain = 0.0 if lufs is None else max(-12.0, min(20.0, TARGET_LUFS - lufs))
    af = f"{dn},volume={gain:.2f}dB,alimiter=limit=0.89:level=disabled,aresample=48000"
    tmp = dst.with_suffix(".part.mp4")
    subprocess.run([FFMPEG, "-v", "error", "-y", "-i", str(src), "-map", "0:v:0?", "-map", "0:a:0",
                    "-c:v", "copy", "-af", af, "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
                    "-movflags", "+faststart", str(tmp)], check=True)
    tmp.replace(dst)
    return str(dst)
