# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
"""One-shot preparation for a pile of files dropped into a chat.

- Sorts the files: every clip where a person talks = a part of the story, the rest = inserts.
- Joins all talking parts in file-name order into one 1080x1920 clip (also shrinks 4K, so
  everything after this is fast).
- Speech is found with the Silero VAD bundled in faster-whisper (street noise is not speech);
  falls back to ffmpeg silence detection.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .pick import IMAGE, VIDEO, _speech_seconds


def _natural(p: Path):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", p.name)]


def _probe(p: Path) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
                        "-of", "json", str(p)], capture_output=True, text=True)
    j = json.loads(r.stdout or "{}")
    return {"dur": float(j.get("format", {}).get("duration", 0) or 0),
            "audio": any(s.get("codec_type") == "audio" for s in j.get("streams", []))}


def speech_seconds(p: Path) -> float:
    try:
        from faster_whisper.audio import decode_audio
        from faster_whisper.vad import VadOptions, get_speech_timestamps
        a = decode_audio(str(p), sampling_rate=16000)
        ts = get_speech_timestamps(a, VadOptions(min_silence_duration_ms=500))
        return sum(t["end"] - t["start"] for t in ts) / 16000
    except Exception:
        return _speech_seconds(p)


def face_share(p: Path, dur: float, samples: int = 3) -> float:
    """Share of sampled frames with a clear face (person talking to camera). -1 if detector unavailable."""
    try:
        import cv2
        import tempfile
        from .paths import app_root
        det = cv2.FaceDetectorYN.create(str(app_root() / "library/models/face_detection_yunet_2023mar.onnx"), "",
                                        (360, 640), 0.7)
    except Exception:
        return -1.0
    hits = 0
    with tempfile.TemporaryDirectory() as d:
        for n in range(samples):
            f = Path(d) / f"{n}.png"
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{dur * (n + 1) / (samples + 1):.2f}", "-i",
                            str(p), "-frames:v", "1", "-vf", "scale=360:-2", str(f)])
            img = cv2.imread(str(f)) if f.exists() else None
            if img is None:
                continue
            det.setInputSize((img.shape[1], img.shape[0]))
            _, found = det.detect(img)
            if found is None or not len(found):
                continue
            areas = sorted((b[2] * b[3] for b in found), reverse=True)
            big = areas[0] > 0.01 * img.shape[0] * img.shape[1]
            alone = len(areas) == 1 or areas[0] > 2.5 * areas[1]  # one person to camera, not a couple / crowd
            hits += big and alone
    return hits / samples


def sort_files(files: list[str], talking: list[str] | None = None, all_talking: bool = False) -> dict:
    paths = [Path(f) for f in files]
    vids = [p for p in paths if p.suffix.lower() in VIDEO]
    imgs = [p for p in paths if p.suffix.lower() in IMAGE]
    if all_talking:
        story = list(vids)
    elif talking:  # the person said which ones are the story
        names = {Path(t).name.lower() for t in talking}
        story = [v for v in vids if v.name.lower() in names or any(n in v.name.lower() for n in names)]
    else:
        story = []
        for v in vids:
            info = _probe(v)
            if not info["audio"] or info["dur"] <= 0:
                continue
            sp = speech_seconds(v)
            if sp >= 3 and sp / info["dur"] >= 0.5 and face_share(v, info["dur"]) != 0:
                story.append(v)
        if not story and vids:
            story = [max(vids, key=lambda v: _probe(v)["dur"])]
    story.sort(key=_natural)
    inserts = [str(p) for p in paths if p not in story and (p in vids or p in imgs)]
    return {"story": [str(p) for p in story], "inserts": inserts}


def join(story: list[str], out: Path, width: int = 1080, height: int = 1920, fps: int = 30) -> Path:
    """Scale/crop every part to the canvas and glue them end to end (fast encode, high quality)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        return out
    inp, chains, cat = [], [], ""
    for i, s in enumerate(story):
        inp += ["-i", s]
        chains.append(f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},"
                      f"fps={fps},setsar=1,format=yuv420p[v{i}];"
                      f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo[a{i}]")
        cat += f"[v{i}][a{i}]"
    fc = ";".join(chains) + f";{cat}concat=n={len(story)}:v=1:a=1[v][a]"
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inp, "-filter_complex", fc, "-map", "[v]",
           "-map", "[a]", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "17", "-c:a", "aac", "-b:a", "256k",
           str(out)]
    subprocess.run(cmd, check=True)
    return out
