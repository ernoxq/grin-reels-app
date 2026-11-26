# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
# Licensed, not sold: see LICENSE.md. Redistribution or resale is prohibited.
"""Bring-your-own-assets library.

Drop files into library/<kind>/... and they are picked up automatically.
Optional `manifest.toml` in any folder adds tags, volume, triggers, etc.
Sub-folder names become tags too: library/sfx/whoosh/swoosh_03.wav -> tags {"whoosh"}.

A JSON index is cached at library/.index.json and rebuilt only when files change
(cheap mtime check), so a 5,000-file library loads in milliseconds.
"""
from __future__ import annotations

import hashlib
import json
import random
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path

KINDS = {
    "fonts": {".ttf", ".otf"},
    "stickers": {".png", ".webp", ".gif", ".mov"},   # .mov = ProRes 4444 with alpha
    "images": {".png", ".jpg", ".jpeg", ".webp", ".heic"},
    "sfx": {".wav", ".mp3", ".m4a", ".aiff", ".flac"},
    "music": {".wav", ".mp3", ".m4a", ".aiff", ".flac"},
    "luts": {".cube"},
}


@dataclass
class Asset:
    id: str
    kind: str
    path: str
    tags: list[str] = field(default_factory=list)
    volume: float = 1.0           # linear gain, sfx/music
    triggers: list[str] = field(default_factory=list)  # words that summon a sticker/image
    duration: float = 0.0
    meta: dict = field(default_factory=dict)


class Library:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.assets: list[Asset] = []
        self._load()

    # ---------- indexing ----------
    def _fingerprint(self) -> str:
        h = hashlib.sha1()
        for p in sorted(self.root.rglob("*")):
            if p.is_file() and not p.name.startswith("."):
                h.update(f"{p}:{p.stat().st_mtime_ns}".encode())
        return h.hexdigest()

    def _load(self) -> None:
        index = self.root / ".index.json"
        fp = self._fingerprint()
        if index.exists():
            data = json.loads(index.read_text())
            if data.get("fingerprint") == fp:
                self.assets = [Asset(**a) for a in data["assets"]]
                return
        self.assets = self._scan()
        index.write_text(json.dumps({"fingerprint": fp, "assets": [asdict(a) for a in self.assets]},
                                    ensure_ascii=False, indent=1))

    def _scan(self) -> list[Asset]:
        assets = []
        for kind, exts in KINDS.items():
            base = self.root / kind
            if not base.exists():
                continue
            manifests = {m.parent: tomllib.loads(m.read_text()) for m in base.rglob("manifest.toml")}
            for p in sorted(base.rglob("*")):
                if p.suffix.lower() not in exts:
                    continue
                rel = p.relative_to(base)
                tags = [t.lower() for t in rel.parts[:-1]]
                a = Asset(id=f"{kind}/{rel.with_suffix('').as_posix()}", kind=kind, path=str(p), tags=tags)
                # folder-level defaults, then per-file overrides
                chain = [d for d in reversed(p.parents) if d == base or base in d.parents]
                for folder in chain:  # base -> ... -> file's own folder
                    m = manifests.get(folder)
                    if not m:
                        continue
                    self._apply(a, m.get("defaults", {}))
                    self._apply(a, m.get("files", {}).get(p.name, {}))
                if kind in ("sfx", "music"):
                    a.duration = _audio_duration(p)
                assets.append(a)
        return assets

    @staticmethod
    def _apply(a: Asset, cfg: dict) -> None:
        for k, v in cfg.items():
            if k == "tags":
                a.tags = sorted(set(a.tags) | {t.lower() for t in v})
            elif k == "triggers":
                a.triggers = sorted(set(a.triggers) | {t.lower() for t in v})
            elif hasattr(a, k):
                setattr(a, k, v)
            else:
                a.meta[k] = v

    # ---------- queries ----------
    def find(self, kind: str, tag: str | None = None) -> list[Asset]:
        return [a for a in self.assets if a.kind == kind and (tag is None or tag in a.tags)]

    def pick(self, kind: str, tag: str | None, rng: random.Random) -> Asset | None:
        pool = self.find(kind, tag)
        return rng.choice(pool) if pool else None

    def get(self, asset_id: str) -> Asset | None:
        return next((a for a in self.assets if a.id == asset_id), None)

    def trigger_map(self) -> dict[str, list[Asset]]:
        out: dict[str, list[Asset]] = {}
        for a in self.assets:
            for t in a.triggers:
                out.setdefault(t, []).append(a)
        return out


def _audio_duration(p: Path) -> float:
    from .media import probe
    try:
        return probe(p).duration
    except Exception:
        return 0.0
