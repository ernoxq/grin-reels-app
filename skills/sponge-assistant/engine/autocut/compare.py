# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
# Licensed, not sold: see LICENSE.md. Redistribution or resale is prohibited.
"""Objective check: how close is our render to the reference?

    python -m autocut.compare ref.mov out.mp4 [--sheet side_by_side.jpg]

Prints per-second mean abs difference (0-255, tiny gray frames) and an overall score,
plus optional side-by-side contact sheet (ref | out) every 0.5 s. Cheap: ~50 MB RAM.
Rule of thumb: < 8 = visually the same grade/framing; 8-15 = small grade/caption drift;
> 25 on a second = wrong shot / timing at that second.
"""
from __future__ import annotations

import argparse
import subprocess

import numpy as np

from .media import FFMPEG


def _gray(path: str, w: int = 54, h: int = 96) -> np.ndarray:
    raw = subprocess.run([FFMPEG, "-loglevel", "error", "-i", path, "-vf", f"fps=30,scale={w}:{h},format=gray",
                          "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)


def compare(ref: str, out: str) -> dict:
    R, O = _gray(ref), _gray(out)
    n = min(len(R), len(O))
    d = np.abs(R[:n] - O[:n]).mean((1, 2))
    per_sec = [round(float(d[i:i + 30].mean()), 1) for i in range(0, n, 30)]
    return {"frames": n, "mean": round(float(d.mean()), 2), "median": round(float(np.median(d)), 2),
            "per_second": per_sec, "worst_second": int(np.argmax(per_sec))}


def sheet(ref: str, out: str, dest: str, step: float = 0.5, cols: int = 6) -> None:
    from PIL import Image
    import io
    def frames(p):
        raw = subprocess.run([FFMPEG, "-loglevel", "error", "-i", p, "-vf", f"fps={1 / step},scale=160:-2",
                              "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, check=True).stdout
        ims, i = [], 0
        while (j := raw.find(b"\x89PNG", i + 1)) != -1 or i < len(raw):
            chunk = raw[i:j if j != -1 else len(raw)]
            if chunk:
                ims.append(Image.open(io.BytesIO(chunk)).convert("RGB"))
            if j == -1:
                break
            i = j
        return ims
    a, b = frames(ref), frames(out)
    n = min(len(a), len(b))
    w, h = a[0].size
    rows = (n + cols - 1) // cols
    canvas = Image.new("RGB", (cols * (2 * w + 6), rows * h), (0, 0, 0))
    for k in range(n):
        x, y = (k % cols) * (2 * w + 6), (k // cols) * h
        canvas.paste(a[k], (x, y))
        canvas.paste(b[k], (x + w, y))
    canvas.save(dest, quality=85)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("ref")
    ap.add_argument("out")
    ap.add_argument("--sheet")
    a = ap.parse_args()
    print(compare(a.ref, a.out))
    if a.sheet:
        sheet(a.ref, a.out, a.sheet)
