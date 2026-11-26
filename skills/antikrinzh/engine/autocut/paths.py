# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
"""Where GRIN Reels keeps its files.

Source install: the project folder. Mac app (.app from the DMG): the app itself is
read-only, so everything lives in ~/Library/Application Support/GRIN Reels
(set by the app launcher through the GRIN_ROOT environment variable).
"""
import os
from pathlib import Path


def app_root() -> Path:
    env = os.environ.get("GRIN_ROOT")
    return Path(env) if env else Path(__file__).resolve().parent.parent
