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


def _created(p: Path) -> str:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format_tags=creation_time:stream_tags=creation_time",
                        "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    vals = [v.strip() for v in r.stdout.replace(",", "\n").splitlines() if v.strip()]
    return min(vals) if vals else ""


def order_by_recording(files: list[Path]) -> list[Path]:
    """Talking parts in the order they were filmed (camera time); file names when the time is missing."""
    times = {f: _created(f) for f in files}
    if all(times.values()) and len(set(times.values())) == len(files):
        return sorted(files, key=lambda f: times[f])
    return sorted(files, key=_natural)


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
    elif talking:  # the person said which ones are the story - and in which order
        story = []
        for t in talking:
            n = Path(t).name.lower()
            for v in vids:
                if v not in story and (v.name.lower() == n or n in v.name.lower()):
                    story.append(v)
                    break
    else:
        story = []
        for v in vids:
            info = _probe(v)
            if not info["audio"] or info["dur"] <= 0:
                continue
            sp = speech_seconds(v)
            if sp >= 3 and sp / info["dur"] >= 0.5 and face_share(v, info["dur"]) != 0:
                story.append(v)
        if not story:  # nobody clearly talks: take the longest clip that has sound at all
            voiced = [v for v in vids if _probe(v)["audio"]]
            if voiced:
                story = [max(voiced, key=lambda v: _probe(v)["dur"])]
    if not talking:
        story = order_by_recording(story)
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
    # where each original clip sits inside the joined story (for CapCut / DaVinci project export)
    t, parts = 0.0, []
    for s in story:
        d = _probe(Path(s))["dur"]
        parts.append({"file": str(Path(s).resolve()), "start": round(t, 4), "dur": round(d, 4)})
        t += d
    (out.parent / "story_parts.json").write_text(json.dumps(parts, ensure_ascii=False, indent=1))
    return out


def join_audio(story: list[str], out: Path) -> tuple[Path, list[dict]]:
    """Glue only the SOUND of all talking parts (seconds, no video decoding) for speech recognition.
    Returns the audio file and where each part starts on that common timeline."""
    out.parent.mkdir(parents=True, exist_ok=True)
    parts, t = [], 0.0
    for s in story:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=duration",
                            "-of", "csv=p=0", s], capture_output=True, text=True)
        try:
            d = float(r.stdout.strip().splitlines()[0])
        except (ValueError, IndexError):
            d = _probe(Path(s))["dur"]
        parts.append({"file": str(Path(s).resolve()), "start": round(t, 4), "dur": round(d, 4)})
        t += d
    if not out.exists():
        inp, cat = [], ""
        for i, s in enumerate(story):
            inp += ["-i", s]
            cat += f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo[a{i}];"
        fc = cat + "".join(f"[a{i}]" for i in range(len(story))) + f"concat=n={len(story)}:v=0:a=1[a]"
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inp, "-filter_complex", fc,
                        "-map", "[a]", "-c:a", "pcm_s16le", str(out)], check=True)
    (out.parent / "story_parts.json").write_text(json.dumps(parts, ensure_ascii=False, indent=1))
    return out, parts


def split_voice(spec: dict, parts: list[dict]) -> dict:
    """Voice segments on the common timeline -> segments of the original clips (render decodes only those)."""
    keys = {}
    for i, p in enumerate(parts):
        keys[p["file"]] = f"A{i + 1}"
        spec["sources"][f"A{i + 1}"] = p["file"]
    out = []
    for seg in spec["voice"]:
        a, left = seg["in"], seg["dur"]
        while left > 0.01:
            p = next((x for x in parts if x["start"] <= a + 1e-6 < x["start"] + x["dur"] - 0.02), None)
            if p is None:
                nxt = [x for x in parts if x["start"] > a]
                if not nxt:
                    break
                left -= nxt[0]["start"] - a; a = nxt[0]["start"]
                continue
            take = min(left, p["start"] + p["dur"] - a)
            out.append({"src": keys[p["file"]], "in": round(a - p["start"], 4), "dur": round(take, 4)})
            a += take; left -= take
    spec["voice"] = out
    return spec
