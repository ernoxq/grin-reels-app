"""Safe cut points for the voice track.

Cuts typed by hand ("cut 12.4 to 13.1") or taken from word timestamps often land
mid-phoneme, so the first/last sound of a word gets eaten and the hard edge clicks.
snap_voice() moves every segment edge to the quietest 10 ms frame nearby
(searching outward, so speech is kept rather than trimmed), then re-times captions,
titles, B-roll and overlays so nothing drifts. render adds 12 ms micro-fades on top.
"""
from __future__ import annotations

import subprocess
from functools import lru_cache

import numpy as np

from .media import FFMPEG

SR = 16000
HOP = 160  # 10 ms
REACH_OUT = 0.20  # how far an edge may move away from speech (keeps sound)
REACH_IN = 0.04   # how far it may move into the kept part (trims a little)
TIME_KEYS = ("start", "end", "s", "e")
TIMED = ("captions", "broll", "title", "sticker", "overlays")


@lru_cache(maxsize=8)
def _env(path: str) -> np.ndarray:
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR),
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    n = len(x) // HOP
    return np.sqrt((x[: n * HOP].reshape(n, HOP) ** 2).mean(1) + 1e-10)


def _quietest(env: np.ndarray, t: float, lo: float, hi: float) -> float:
    a, b = max(0, int((t - lo) * 100)), min(len(env), int((t + hi) * 100) + 1)
    if b - a < 2:
        return t
    w = env[a:b]
    cur = env[min(len(env) - 1, max(0, int(t * 100)))]
    if w.min() >= cur * 0.7:  # nothing clearly quieter nearby: leave it
        return t
    # the quiet frame closest to the requested time (don't add extra silence)
    quiet = np.flatnonzero(w <= w.min() * 2 + 1e-4)
    k = quiet[np.argmin(np.abs(a + quiet - t * 100))]
    return (a + int(k)) / 100


def snap_voice(spec: dict, src_path) -> dict:
    """src_path(key) -> file path. Mutates and returns spec."""
    voice = spec.get("voice") or []
    if not voice:
        return spec
    old, t = [], 0.0
    for seg in voice:
        old.append((t, seg["in"], seg["dur"]))
        t += seg["dur"]
    for k, seg in enumerate(voice):
        env = _env(str(src_path(seg["src"])))
        s, e = seg["in"], seg["in"] + seg["dur"]
        s2 = _quietest(env, s, REACH_OUT, REACH_IN)
        e2 = _quietest(env, e, REACH_IN, REACH_OUT)
        # never overlap the neighbour from the same take
        if k and voice[k - 1]["src"] == seg["src"]:
            pe = voice[k - 1]["in"] + voice[k - 1]["dur"]
            if pe <= s:
                s2 = max(s2, pe)
        if k + 1 < len(voice) and voice[k + 1]["src"] == seg["src"] and voice[k + 1]["in"] >= e:
            e2 = min(e2, voice[k + 1]["in"])
        if e2 - s2 > 0.1:
            seg["in"], seg["dur"] = round(max(0.0, s2), 4), round(e2 - max(0.0, s2), 4)

    new, t = [], 0.0
    for seg in voice:
        new.append((t, seg["in"]))
        t += seg["dur"]

    def remap(x: float) -> float:
        for (o0, in0, d0), (n0, in1) in zip(old, new):
            if x <= o0 + d0 + 1e-6:
                return round(max(n0, n0 + (x - o0) + (in0 - in1)), 4)
        return round(x - sum(d for _, _, d in old) + t, 4)

    def walk(o):
        if isinstance(o, dict):
            for key, v in o.items():
                if key in TIME_KEYS and isinstance(v, (int, float)):
                    o[key] = remap(v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    for key in TIMED:
        if key in spec:
            walk(spec[key])
    if "duration" in spec:
        spec["duration"] = round(t, 4)
    return spec
