"""Mute mouth noise (цоканье, чмок, вдох) in the pause around a moment the person names.

    python -m autocut quiet jobs/r1/spec.json 0:09        (several: 0:09 1:16)
    python -m autocut quiet jobs/r1/spec.json --clear
then render. Stored in the job (mute.json, source time), so it survives re-plans.

Why manual: lip smacks and tongue clicks sound like short soft syllables («-ти» in «вечности»);
any automatic rule that removes one eats the other. Pointed at a pause, it is safe: only the stretch
between two words is ducked (−30 dB), 40 ms away from both.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def _t(x: str) -> float:
    if ":" in x:
        m, s = x.split(":")
        return int(m) * 60 + float(s)
    return float(x)


def pause_at(d: np.ndarray, t: float) -> tuple[float, float] | None:
    """The pause (no >= 60 ms of speech-level sound) that contains t or is nearest to it within 0.6 s."""
    a, b = max(0, int((t - 1.5) * 100)), min(len(d), int((t + 1.5) * 100))
    w = d[a:b]
    loud = float(np.percentile(w, 95)) - 12
    up = w > loud
    word = np.zeros(len(w), bool)
    i = 0
    while i < len(w):
        if up[i]:
            j = i
            while j < len(w) and up[j]:
                j += 1
            if j - i >= 6:
                word[i:j] = True
            i = j
        else:
            i += 1
    gaps, i = [], 0
    while i < len(w):
        if word[i]:
            i += 1
            continue
        j = i
        while j < len(w) and not word[j]:
            j += 1
        if j - i >= 12:
            gaps.append(((a + i) / 100, (a + j) / 100))
        i = j
    if not gaps:
        return None
    g = min(gaps, key=lambda g: 0 if g[0] <= t <= g[1] else min(abs(t - g[0]), abs(t - g[1])))
    if not (g[0] - 0.6 <= t <= g[1] + 0.6):
        return None
    s, e = g[0] + 0.2, g[1] - 0.06  # 200 ms after the word (a final «к» bursts ~0.1 s after the vowel, plus the 35 ms fade): 150 ms after the word: a final «к», «т», «п» bursts ~0.1 s after the vowel
    return (round(s, 3), round(e, 3)) if e - s > 0.05 else None


def quiet(spec_path: str, times: list[str], clear: bool = False) -> dict:
    from .cutsafe import _db, _env, snap_voice
    from .reel import _src, load_spec
    sp = Path(spec_path)
    mf = sp.parent / "mute.json"
    mutes = [] if clear or not mf.exists() else json.loads(mf.read_text())
    if clear:
        mf.write_text("[]")
        return {"muted": 0}
    spec = load_spec(sp)
    if not spec.get("raw_cuts"):
        snap_voice(spec, lambda k: _src(spec, k))
    spd = float(spec.get("speed") or 1.0)
    done = []
    for x in times:
        ot = _t(x) * spd  # output time -> timeline before speed-up
        acc = 0.0
        for seg in spec["voice"]:
            if acc <= ot <= acc + seg["dur"]:
                src = str(_src(spec, seg["src"]))
                st = seg["in"] + (ot - acc)
                g = pause_at(_db(_env(src)), st)
                if g:
                    mutes.append({"src": spec["sources"][seg["src"]], "from": g[0], "to": g[1]})
                    done.append({"at": x, "muted_sec": round(g[1] - g[0], 2)})
                else:
                    done.append({"at": x, "muted_sec": 0, "note": "no pause there (inside a word): nothing muted"})
                break
            acc += seg["dur"]
    mf.write_text(json.dumps(mutes, ensure_ascii=False))
    return {"done": done, "total": len(mutes)}
