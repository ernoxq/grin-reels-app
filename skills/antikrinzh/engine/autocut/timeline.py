# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
# Licensed, not sold: see LICENSE.md. Redistribution or resale is prohibited.
"""Editor-agnostic timeline = the single source of truth.

Pipeline:  analysis (keeps, words)  +  library  +  preset  ->  Timeline (timeline.json)
Exporters (CapCut draft, preview render, later FCPXML/OTIO) only READ this.
Because it's plain JSON you can diff it, hand-edit it, or re-export without re-analysis.
All times are seconds on the OUTPUT timeline unless named src_*.
"""
from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .library import Asset, Library
from .transcribe import Word

Range = tuple[float, float]


@dataclass
class VideoClip:
    src: str
    src_in: float
    src_out: float
    start: float

    @property
    def dur(self) -> float:
        return self.src_out - self.src_in


@dataclass
class AudioClip:
    src: str
    start: float
    dur: float
    src_in: float = 0.0
    volume: float = 1.0
    fade_in: float = 0.0
    fade_out: float = 0.0
    volume_keys: list[tuple[float, float]] = field(default_factory=list)  # (offset_s, gain)
    asset_id: str = ""


@dataclass
class Overlay:
    src: str
    start: float
    dur: float
    x: float = 0.0          # CapCut units: -1..1 = half-canvas
    y: float = 0.0
    scale: float = 0.35
    anim: str = "pop"       # pop | slide_up | none
    asset_id: str = ""


@dataclass
class Caption:
    text: str
    start: float
    dur: float
    words: list[tuple[str, float, float]] = field(default_factory=list)  # for karaoke styling later


@dataclass
class Timeline:
    width: int
    height: int
    fps: int
    source: str
    main: list[VideoClip] = field(default_factory=list)
    overlays: list[Overlay] = field(default_factory=list)
    sfx: list[AudioClip] = field(default_factory=list)
    music: list[AudioClip] = field(default_factory=list)
    captions: list[Caption] = field(default_factory=list)
    caption_style: dict = field(default_factory=dict)
    lut: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return self.main[-1].start + self.main[-1].dur if self.main else 0.0

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=1))

    @classmethod
    def load(cls, path: Path) -> "Timeline":
        d = json.loads(path.read_text())
        return cls(
            **{k: v for k, v in d.items() if k not in ("main", "overlays", "sfx", "music", "captions")},
            main=[VideoClip(**c) for c in d["main"]],
            overlays=[Overlay(**c) for c in d["overlays"]],
            sfx=[AudioClip(**c) for c in d["sfx"]],
            music=[AudioClip(**c) for c in d["music"]],
            captions=[Caption(**c) for c in d["captions"]],
        )

    # map a source time to output time (None if it was cut)
    def map_time(self, t: float) -> float | None:
        for c in self.main:
            if c.src_in <= t < c.src_out:
                return c.start + (t - c.src_in)
        return None


# ---------------------------------------------------------------- builder
def build_timeline(src: str, size: tuple[int, int], fps: float, keeps: list[Range],
                   words: list[Word], lib: Library, preset: dict, seed: int = 7) -> Timeline:
    rng = random.Random(seed)  # deterministic: same input + preset => same edit
    w, h = size
    tl = Timeline(width=w, height=h, fps=round(fps) or 30, source=src)

    # 1) main track: concatenate keep ranges (pure in/out points, nothing re-encoded)
    t = 0.0
    for s, e in keeps:
        tl.main.append(VideoClip(src, s, e, round(t, 6)))
        t += e - s

    # 2) SFX on cuts (jump-cut whoosh/pop), with cooldown so it doesn't get annoying
    sp = preset.get("sfx", {})
    if sp.get("enabled", True):
        last = -1e9
        for clip in tl.main[1:]:
            if clip.start - last < sp.get("cooldown", 4.0):
                continue
            a = lib.pick("sfx", sp.get("on_cut_tag", "whoosh"), rng)
            if not a:
                tl.notes.append(f"no sfx with tag '{sp.get('on_cut_tag')}'")
                break
            lead = sp.get("lead", 0.08)  # whoosh peaks slightly before the cut
            d = min(a.duration or 1.0, sp.get("max_len", 1.2))
            tl.sfx.append(AudioClip(a.path, max(0, clip.start - lead), d,
                                    volume=a.volume * sp.get("gain", 0.5), asset_id=a.id))
            last = clip.start

    # 3) captions from word timestamps, remapped onto the cut timeline
    cp = preset.get("captions", {})
    if cp.get("enabled", True) and words:
        tl.captions = _chunk_captions(tl, words, cp.get("max_words", 3), cp.get("max_chars", 18),
                                      cp.get("uppercase", False))
        tl.caption_style = cp.get("style", {})

    # 4) stickers / images triggered by spoken keywords
    st = preset.get("stickers", {})
    if st.get("enabled", True) and words:
        tmap, last = lib.trigger_map(), -1e9
        norm = lambda s: "".join(ch for ch in s.lower() if ch.isalnum())
        for wd in words:
            hits = tmap.get(norm(wd.text))
            at = tl.map_time(wd.start)
            if not hits or at is None or at - last < st.get("cooldown", 3.0):
                continue
            a = rng.choice(hits)
            tl.overlays.append(Overlay(a.path, at, st.get("duration", 1.4),
                                       x=st.get("x", 0.55), y=st.get("y", 0.45),
                                       scale=a.meta.get("scale", st.get("scale", 0.35)),
                                       anim=st.get("anim", "pop"), asset_id=a.id))
            pop = lib.pick("sfx", st.get("sfx_tag", "pop"), rng)
            if pop:
                tl.sfx.append(AudioClip(pop.path, at, min(pop.duration or 0.6, 0.8),
                                        volume=pop.volume * sp.get("gain", 0.5), asset_id=pop.id))
            last = at

    # 5) music bed with ducking keyframes under speech
    mp = preset.get("music", {})
    if mp.get("enabled", False):
        a = lib.pick("music", mp.get("tag"), rng)
        if a and a.duration > 0:
            tl.music = _music_bed(tl, a, mp)

    # 6) LUT
    if lut_id := preset.get("color", {}).get("lut"):
        lut = lib.get(lut_id)
        tl.lut = lut.path if lut else None
        if not lut:
            tl.notes.append(f"LUT {lut_id} not found in library")
    return tl


def _chunk_captions(tl: Timeline, words: list[Word], max_words: int, max_chars: int,
                    upper: bool) -> list[Caption]:
    caps, cur = [], []

    def flush():
        if not cur:
            return
        s, e = cur[0][1], cur[-1][2]
        text = " ".join(x[0] for x in cur)
        caps.append(Caption(text.upper() if upper else text, s, max(0.25, e - s), list(cur)))
        cur.clear()

    for wd in words:
        s, e = tl.map_time(wd.start), tl.map_time(max(wd.start, wd.end - 1e-3))
        if s is None:
            continue  # word fell inside a removed region
        e = e if e is not None and e > s else s + (wd.end - wd.start)
        gap = s - cur[-1][2] if cur else 0
        txt_len = len(" ".join(x[0] for x in cur)) + len(wd.text) + 1
        if cur and (len(cur) >= max_words or txt_len > max_chars or gap > 0.35):
            flush()
        cur.append((wd.text, s, e))
        if wd.text.endswith((".", "!", "?", ",")):
            flush()
    flush()
    # no overlaps: each caption ends when the next starts
    for a, b in zip(caps, caps[1:]):
        a.dur = max(0.1, min(a.dur + 0.15, b.start - a.start))
    return caps


def _music_bed(tl: Timeline, a: Asset, mp: dict) -> list[AudioClip]:
    base, duck = mp.get("gain", 0.35), mp.get("duck_gain", 0.12)
    from .silence import merge
    # only un-duck in real gaps (>0.8 s), otherwise the bed "pumps" between words
    speech = merge([(c.start, c.start + c.dur) for c in tl.captions], gap=0.8) or [(0, tl.duration)]
    clips, t = [], 0.0
    while t < tl.duration - 0.05:  # loop the track if it's shorter than the edit
        d = min(a.duration, tl.duration - t)
        keys = []
        for s, e in speech:
            if e < t or s > t + d:
                continue
            s0, e0 = max(0.0, s - t), min(d, e - t)
            keys += [(max(0, s0 - 0.25), base), (s0, duck), (e0, duck), (min(d, e0 + 0.4), base)]
        clips.append(AudioClip(a.path, t, d, volume=1.0, fade_in=0.8 if t == 0 else 0,
                               fade_out=1.5 if t + d >= tl.duration - 0.05 else 0,
                               volume_keys=_dedupe(keys) or [(0, base)], asset_id=a.id))
        t += d
    return clips


def _dedupe(keys: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out: dict[float, float] = {}
    for k, v in sorted(keys):
        out[round(k, 3)] = v
    return sorted(out.items())
