"""Safe cut points for the voice track.

Cuts typed by hand ("cut 12.4 to 13.1") or taken from word timestamps often land
mid-phoneme, so the first/last sound of a word gets eaten and the hard edge clicks.
snap_voice() listens at every segment edge: a piece starts where the voice really starts (a sound
lasting >= 60 ms above the speech threshold, so lip smacks and breaths before a word are left out)
and ends after the word's natural decay. Short clicks inside kept pauses are listed in seg["duck"]
and ducked by the renderer. Captions, titles, B-roll and overlays are re-timed so nothing drifts.
"""
from __future__ import annotations

import subprocess
from functools import lru_cache

import numpy as np

from .media import FFMPEG

SR = 16000
HOP = 160  # 10 ms
TIME_KEYS = ("start", "end", "s", "e")
TIMED = ("captions", "broll", "title", "sticker", "overlays")


@lru_cache(maxsize=8)
def _env(path: str) -> np.ndarray:
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR),
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    n = len(x) // HOP
    return np.sqrt((x[: n * HOP].reshape(n, HOP) ** 2).mean(1) + 1e-10)


def _db(env: np.ndarray) -> np.ndarray:
    return 20 * np.log10(env + 1e-9)


SUSTAIN = 6  # frames (60 ms): real speech lasts; lip smacks / clicks don't


def _thr(d: np.ndarray, a: int, b: int) -> float:
    """Speech threshold for this stretch: 28 dB under its loud parts, at least 12 dB over its floor."""
    seg = d[max(0, a):min(len(d), b)]
    if len(seg) < 10:
        return -45.0
    return max(float(np.percentile(seg, 3)) + 12, float(np.percentile(seg, 95)) - 28)


def _onset(d: np.ndarray, t: float, thr: float, limit: float) -> float:
    """Where the voice really starts near t (Whisper starts are often 0.3-0.4 s off).
    From 0.25 s before t: first get out of any sound still going on there (the tail of the
    previous, cut-away words), then take the first run >= 60 ms above thr; start 30 ms before
    it so the consonant attack stays. Never later than `limit`."""
    a, b = max(0, int((t - 0.25) * 100)), min(len(d) - SUSTAIN, int(min(t + 0.6, limit) * 100))
    i = a
    while i < b and d[i] > thr:  # still inside earlier sound
        i += 1
    if i >= b:  # no pause at all before this word: cut at the quietest point
        return _dip(d, t)
    while i < b:
        if (d[i:i + SUSTAIN] > thr).all():
            return max(0.0, i / 100 - 0.03)
        i += 1
    return t


def _offset(d: np.ndarray, t: float, thr: float) -> float:
    """Where the voice really ends near t. Find the first 120 ms without a sounding run after t-0.15 (up to t+0.5;
    a dip inside a word, like between «жиз» and «ни» or before «ц» in «месяца», is shorter), then end 60 ms after the
    last sounding run >= 30 ms before that point (so a lone click after the word stays out)."""
    a = max(0, int((t - 0.15) * 100))
    stop = min(len(d) - 12, int((t + 0.5) * 100))
    def voiced_run(x: np.ndarray) -> bool:  # any >= 30 ms above thr (a lone click is shorter)
        up = x > thr
        return any(up[k:k + 3].all() for k in range(len(up) - 2))

    q = a
    # 120 ms with no sounding run: the word is over (closures inside words, before ц/т/к, are shorter)
    while q < stop and voiced_run(d[q:q + 12]):
        q += 1
    if q >= stop:  # words run on without a pause: cut at the quietest point between them
        return _dip(d, t)
    last, i = None, max(0, int((t - 0.6) * 100))
    while i < q:
        if d[i] > thr:
            j = i
            while j < q and d[j] > thr:
                j += 1
            if j - i >= 3:
                last = j
            i = j
        else:
            i += 1
    return (last if last is not None else q) / 100 + 0.06


def _dip(d: np.ndarray, t: float) -> float:
    a, b = max(0, int((t - 0.15) * 100)), min(len(d), int((t + 0.35) * 100))
    return (a + int(np.argmin(d[a:b]))) / 100 if b > a else t


def _onset_after_trim(d: np.ndarray, t: float, thr: float) -> float:
    """t = the kept word's start (ASR). If there is a pause just before it, start at its voice onset;
    if the trimmed word runs straight into it, cut at the quietest point in [t-0.08, t+0.08]."""
    a, b = max(0, int((t - 0.08) * 100)), min(len(d) - SUSTAIN, int((t + 0.25) * 100))
    if (d[a:a + 3] < thr).all():
        for i in range(a, b):
            if (d[i:i + SUSTAIN] > thr).all():
                return max(0.0, i / 100 - 0.03)
    lo, hi = max(0, int((t - 0.08) * 100)), min(len(d), int((t + 0.08) * 100))
    return (lo + int(np.argmin(d[lo:hi]))) / 100 if hi > lo else t


def _end_before_trim(d: np.ndarray, e: float, thr: float) -> float:
    """e = last kept word's ASR end + 0.14 pad; trimmed words follow. End at the first quiet frame
    after that word (never later than e), or at the quietest point if the words run on."""
    lo, hi = max(0, int((e - 0.22) * 100)), min(len(d) - 3, int((e + 0.02) * 100))
    for i in range(lo, hi):
        if (d[i:i + 3] < thr).all():
            return i / 100 + 0.03
    return (lo + int(np.argmin(d[lo:hi]))) / 100 if hi > lo else e


def _speech_mask(d: np.ndarray, thr: float) -> np.ndarray:
    """True on frames that belong to a run >= 60 ms above thr (real voice)."""
    up = d > thr
    m = np.zeros_like(up)
    i = 0
    while i < len(up):
        if up[i]:
            j = i
            while j < len(up) and up[j]:
                j += 1
            if j - i >= SUSTAIN:
                m[i:j] = True
            i = j
        else:
            i += 1
    return m


def clicks(d: np.ndarray, s: float, e: float, thr: float) -> list[tuple[float, float]]:
    """Lip smacks / clicks inside the pauses of a kept piece: bursts <= 50 ms, >= 15 dB over the
    pause, inside >= 300 ms without voice, >= 0.1 s away from words. Seconds relative to the piece start, to be ducked."""
    a, b = max(0, int(s * 100)), min(len(d), int(e * 100))
    seg = d[a:b]
    if len(seg) < 12:
        return []
    voice = _speech_mask(seg, thr)
    out, i = [], 0
    while i < len(seg):
        if voice[i]:
            i += 1
            continue
        j = i
        while j < len(seg) and not voice[j]:
            j += 1
        if j - i >= 30:  # a real pause (>= 300 ms); stop-consonant closures inside words are shorter
            q = seg[i:j]
            floor = float(np.percentile(q, 30))
            k = 0
            while k < len(q):
                if q[k] > floor + 15:
                    m = k
                    while m < len(q) and q[m] > floor + 8:
                        m += 1
                    # a burst right before a word is its consonant (к, т, п), right after one its tail: keep
                    if m - k <= 5 and k >= 8 and len(q) - m >= 10:
                        out.append((round(max(0.0, (i + k) / 100 - 0.01), 3), round((i + m) / 100 + 0.02, 3)))
                    k = m
                k += 1
        i = j
    return out


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
        d = _db(_env(str(src_path(seg["src"]))))
        s, e = seg["in"], seg["in"] + seg["dur"]
        thr = _thr(d, int((s - 1) * 100), int((e + 1) * 100))
        if seg.get("cut_in"):  # right after trimmed words: start at the kept word, never earlier
            s2 = _onset_after_trim(d, s + 0.02, thr)
        else:
            s2 = _onset(d, s + 0.08, thr, e - 0.2)   # pads were added around the words: look from the word itself
        e2 = _end_before_trim(d, e, thr) if seg.get("cut_out") else _offset(d, e - 0.12, thr)
        # never overlap the neighbour from the same take
        if k and voice[k - 1]["src"] == seg["src"]:
            pe = voice[k - 1]["in"] + voice[k - 1]["dur"]
            if pe <= s:
                s2 = max(s2, pe)
        if k + 1 < len(voice) and voice[k + 1]["src"] == seg["src"] and voice[k + 1]["in"] >= e:
            e2 = min(e2, voice[k + 1]["in"])
        if e2 - s2 > 0.1:
            seg["in"], seg["dur"] = round(max(0.0, s2), 4), round(e2 - max(0.0, s2), 4)
        seg["duck"] = clicks(d, seg["in"], seg["in"] + seg["dur"], thr)

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
