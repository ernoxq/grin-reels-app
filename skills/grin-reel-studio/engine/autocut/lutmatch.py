# GRIN Reels — © 2026 Ernest Grin. All rights reserved.
"""Build a .cube LUT that moves a video's colour toward a reference picture.

Per-channel histogram matching (on mid-frame samples of the source), softened
by `strength`, written as a 33^3 3D LUT. Good for "make it look like this
screenshot"; not a substitute for a hand-made grade.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

VIDEO_EXT = {".mov", ".mp4", ".m4v", ".mkv", ".avi", ".webm"}


def _pixels(path: Path) -> np.ndarray:
    if path.suffix.lower() in VIDEO_EXT:
        dur = float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
            capture_output=True, text=True).stdout.strip() or 1)
        frames = []
        with tempfile.TemporaryDirectory() as d:
            for i, t in enumerate((0.25, 0.5, 0.75)):
                f = Path(d) / f"{i}.png"
                subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{dur * t:.2f}", "-i", str(path),
                                "-frames:v", "1", "-vf", "scale=360:-2", str(f)], check=True)
                frames.append(np.asarray(Image.open(f).convert("RGB")).reshape(-1, 3))
        return np.concatenate(frames)
    im = Image.open(path).convert("RGB")
    im.thumbnail((640, 640))
    return np.asarray(im).reshape(-1, 3)


def _curve(src: np.ndarray, ref: np.ndarray) -> np.ndarray:
    """256-entry curve mapping src channel quantiles onto ref quantiles."""
    q = np.linspace(0, 1, 257)
    sq, rq = np.quantile(src, q), np.quantile(ref, q)
    sq = np.maximum.accumulate(sq + np.arange(257) * 1e-6)  # strictly increasing for interp
    return np.interp(np.arange(256), sq, rq)


def build(source: Path, reference, out: Path, strength: float = 0.6, size: int = 33) -> Path:
    refs = reference if isinstance(reference, (list, tuple)) else [reference]
    s = _pixels(Path(source)).astype(float)
    r = np.concatenate([_pixels(Path(x)) for x in refs]).astype(float)
    reference = Path(refs[0])
    ident = np.arange(256, dtype=float)
    curves = [ident + strength * (_curve(s[:, c], r[:, c]) - ident) for c in range(3)]
    # gentle smoothing so banding / noise in the histograms doesn't show
    k = np.ones(9) / 9
    curves = [np.convolve(np.pad(cv, 4, mode="edge"), k, mode="valid") for cv in curves]
    grid = np.linspace(0, 255, size)
    lut = [np.interp(grid, ident, cv) / 255.0 for cv in curves]
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [f'TITLE "GRIN match {reference.stem}"', f"LUT_3D_SIZE {size}"]
    for b in range(size):  # .cube order: red fastest
        for g in range(size):
            for rr in range(size):
                lines.append(f"{lut[0][rr]:.6f} {lut[1][g]:.6f} {lut[2][b]:.6f}")
    out.write_text("\n".join(lines) + "\n")
    return out
