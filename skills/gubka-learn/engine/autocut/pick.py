# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
"""Sort a pile of files: which video is the person talking, which are inserts.

People just drop everything into the chat. The talking video = the one with the
most speech (duration x share of non-silent audio). Everything else = B-roll,
photos included, in the order given.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

VIDEO = {".mov", ".mp4", ".m4v", ".mkv", ".avi", ".webm", ".3gp"}
IMAGE = {".jpg", ".jpeg", ".png", ".heic", ".webp"}


def _speech_seconds(p: Path) -> float:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(p), "-af", "silencedetect=n=-35dB:d=0.4", "-vn", "-f", "null",
                        "-"], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    if not m or "Audio:" not in r.stderr:
        return 0.0
    dur = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
    silent = sum(float(x) for x in re.findall(r"silence_duration: ([\d.]+)", r.stderr))
    return max(0.0, dur - silent)


def pick(files: list[str]) -> dict:
    vids = [Path(f) for f in files if Path(f).suffix.lower() in VIDEO]
    imgs = [Path(f) for f in files if Path(f).suffix.lower() in IMAGE]
    if not vids:
        return {"aroll": None, "broll": [str(p) for p in imgs], "note": "нет видео, где человек говорит"}
    scored = sorted(((_speech_seconds(v), v) for v in vids), key=lambda t: -t[0])
    aroll = scored[0][1]
    broll = [str(p) for p in (Path(f) for f in files) if p != aroll and (p in vids or p in imgs)]
    return {"aroll": str(aroll), "speech_s": round(scored[0][0], 1), "broll": broll}
