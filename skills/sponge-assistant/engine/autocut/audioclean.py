"""Clean voice for every output (MP4 render, studio, CapCut).

Phone audio has hiss and low rumble, and is usually quiet (-20..-28 LUFS); raising it in an
editor raises the hiss too. clean() makes a copy of a talking clip with:
  highpass 70 Hz (rumble) -> FFT denoise ONLY if the recording is noisy (SNR < 40 dB), mild ->
  static gain to -14 LUFS (Reels/TikTok level) -> limiter at -1 dBTP. Audio kept as PCM.
Video is stream-copied, so it is fast and lossless; the copy is cached next to the job.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .media import FFMPEG

TARGET_LUFS = -14.0


def _levels(path: str) -> tuple[float, float]:
    """(speech level, noise floor) in dBFS from 50 ms frames: loud 95th vs quiet 3rd percentile."""
    import numpy as np
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", "16000", "-af", "highpass=f=80",
                          "-f", "s16le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    n = len(x) // 800
    if n < 10:
        return -20.0, -80.0
    rms = 20 * np.log10(np.sqrt((x[: n * 800].reshape(n, 800) ** 2).mean(1) + 1e-12))
    return float(np.percentile(rms, 95)), float(np.percentile(rms, 3))


def denoise(path: str) -> str:
    """Touch the voice only as much as the recording needs. A clean lav/phone recording (most of them)
    gets NO noise reduction: every denoiser dulls consonants and 'air'. No gate ever (it chops breaths
    and word tails). Noisy recordings get a mild FFT denoise tuned to their own noise floor."""
    speech, floor = _levels(path)
    snr = speech - floor
    if snr >= 40 or floor < -62:
        return "highpass=f=70"
    nf = max(-70, min(-30, round(floor)))
    return f"highpass=f=70,afftdn=nr={6 if snr >= 28 else 10}:nf={nf}:tn=1"


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
    dst = cache / f"{src.stem}{suffix}.mov"  # PCM inside: no second lossy encode before the final one
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime and dst.stat().st_size > 0:
        return str(dst)
    dn = denoise(str(src))
    lufs = _lufs(str(src), dn)
    gain = 0.0 if lufs is None else max(-12.0, min(20.0, TARGET_LUFS - lufs))
    af = f"{dn},volume={gain:.2f}dB,alimiter=limit=0.89:level=disabled,aresample=48000"
    tmp = dst.with_suffix(".part.mov")
    subprocess.run([FFMPEG, "-v", "error", "-y", "-i", str(src), "-map", "0:v:0?", "-map", "0:a:0",
                    "-c:v", "copy", "-af", af, "-c:a", "pcm_s16le", "-ar", "48000", str(tmp)], check=True)
    tmp.replace(dst)
    return str(dst)
