# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
"""Entry point of the Mac app (GRIN Reels.app inside the DMG).

First launch copies the starter library into ~/Library/Application Support/GRIN Reels;
later launches only add files that are new in an update (the person's own files stay).
ffmpeg/ffprobe ship inside the app.
"""
import os
import shutil
import sys
from pathlib import Path

BUNDLE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
HOME = Path.home() / "Library/Application Support/GRIN Reels"


def _sync(src: Path, dst: Path, overwrite: bool = False) -> None:
    for p in src.rglob("*"):
        q = dst / p.relative_to(src)
        if p.is_dir():
            q.mkdir(parents=True, exist_ok=True)
        elif overwrite or not q.exists():
            q.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, q)


def prepare() -> None:
    HOME.mkdir(parents=True, exist_ok=True)
    for name, over in (("library", False), ("styles", False), ("presets", False), ("web", True)):
        if (BUNDLE / name).exists():
            _sync(BUNDLE / name, HOME / name, overwrite=over)
    for d in ("jobs", "uploads"):
        (HOME / d).mkdir(exist_ok=True)
    os.environ["GRIN_ROOT"] = str(HOME)
    os.environ["PATH"] = f"{BUNDLE / 'bin'}:{os.environ.get('PATH', '')}:/opt/homebrew/bin:/usr/local/bin"
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")


def selftest() -> int:
    """Run by the build: everything the app needs is inside and works."""
    import subprocess
    prepare()
    out = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    for f in ("subtitles", "lut3d", "zoompan", "colortemperature"):
        assert f" {f} " in out, f"ffmpeg has no {f} filter"
    subprocess.run(["ffprobe", "-version"], check=True, capture_output=True)
    import faster_whisper, ctranslate2, cv2, av, resvg_py  # noqa: F401
    from autocut.icons import render
    render("heart", HOME / "jobs" / "_selftest.png", 64)
    from autocut.server import app  # noqa: F401
    print("SELFTEST OK", HOME)
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    prepare()
    from autocut.launch import main
    main()
