# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
# Licensed, not sold: see LICENSE.md. Redistribution or resale is prohibited.
"""ffprobe / ffmpeg helpers. Everything streams through ffmpeg -> constant, low RAM."""
from __future__ import annotations

import json
import platform
import shutil
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"
IS_MAC = platform.system() == "Darwin"


@dataclass
class MediaInfo:
    path: str
    duration: float
    width: int = 0
    height: int = 0
    fps: float = 30.0
    has_audio: bool = False
    has_video: bool = False
    rotation: int = 0

    @property
    def display_size(self) -> tuple[int, int]:
        """iPhone footage is often stored landscape + rotation flag."""
        if self.rotation in (90, 270, -90, -270):
            return self.height, self.width
        return self.width, self.height


def probe(path: str | Path) -> MediaInfo:
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    data = json.loads(out)
    info = MediaInfo(path=str(Path(path).resolve()), duration=float(data["format"].get("duration", 0)))
    for s in data["streams"]:
        if s["codec_type"] == "video" and not info.has_video:
            info.has_video = True
            info.width, info.height = int(s["width"]), int(s["height"])
            rate = s.get("avg_frame_rate") or s.get("r_frame_rate") or "30/1"
            try:
                info.fps = float(Fraction(rate)) or 30.0
            except (ZeroDivisionError, ValueError):
                info.fps = 30.0
            rot = s.get("tags", {}).get("rotate")
            for sd in s.get("side_data_list", []):
                if "rotation" in sd:
                    rot = sd["rotation"]
            info.rotation = int(float(rot)) if rot is not None else 0
        elif s["codec_type"] == "audio":
            info.has_audio = True
    return info


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:  # show WHY right away (no digging through logs)
        tail = "\n".join((r.stderr or "").strip().splitlines()[-8:])
        raise RuntimeError(f"ffmpeg failed: {tail or 'no message'}")
    return r


def h264_encoder() -> list[str]:
    """Hardware encoder on Apple Silicon (near-zero CPU/RAM), software elsewhere."""
    if IS_MAC:
        return ["-c:v", "h264_videotoolbox", "-b:v", "6M"]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23"]


def prores_encoder() -> list[str]:
    """Mezzanine codec for graded intermediates: visually lossless, CapCut reads it."""
    if IS_MAC:
        return ["-c:v", "prores_videotoolbox", "-profile:v", "hq"]
    return ["-c:v", "prores_ks", "-profile:v", "3"]  # 3 = 422 HQ


def median_luma(path: str, start: float = 0.0, dur: float | None = None, n: int = 7) -> float:
    """Median luma (0-255) of n frames sampled across [start, start+dur]. Tiny decode, ~1 s."""
    import numpy as np
    total = dur if dur is not None else probe(path).duration - start
    vals = []
    for k in range(n):
        t = start + total * (k + 0.5) / n
        raw = subprocess.run([FFMPEG, "-loglevel", "error", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1",
                              "-vf", "scale=96:-2,format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
        if raw:
            vals.append(float(np.median(np.frombuffer(raw, np.uint8))))
    return float(np.median(vals)) if vals else 128.0
