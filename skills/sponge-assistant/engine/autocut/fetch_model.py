# GRIN Reels — © 2026 Ernest Grin. All rights reserved.
"""Download the speech model from the GRIN Reels GitHub release.

Used in the Claude cloud workspace, where the usual model host is blocked but
GitHub is reachable. Model: faster-whisper "small" (MIT, © OpenAI / SYSTRAN).
"""
from __future__ import annotations

import os
import urllib.request
from pathlib import Path

REPO = os.environ.get("GRIN_MODEL_REPO", "ernoxq/grin-reels-models")
TAG = os.environ.get("GRIN_MODEL_TAG", "v1")
FILES = ["config.json", "model.bin", "tokenizer.json", "vocabulary.txt"]


def fetch(dest: Path = Path.home() / ".cache/grin-reels/whisper-small") -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    for f in FILES:
        p = dest / f
        if p.exists() and p.stat().st_size > 0:
            continue
        url = f"https://github.com/{REPO}/releases/download/{TAG}/{f}"
        tmp = p.with_suffix(p.suffix + ".part")
        urllib.request.urlretrieve(url, tmp)
        tmp.rename(p)
    return dest
