# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
"""Download reference reels by link with yt-dlp (public posts). Prints one short JSON result."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def fetch_urls(urls: list[str], out: Path) -> dict:
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "yt-dlp"], capture_output=True)
        try:
            import yt_dlp  # noqa: F401
        except ImportError:
            return {"error": "no_ytdlp", "hint": "yt-dlp не установился: нет доступа к интернету"}
    import yt_dlp
    out.mkdir(parents=True, exist_ok=True)
    got, failed = [], []
    opts = {"outtmpl": str(out / "%(uploader)s_%(id)s.%(ext)s"), "format": "mp4/bestvideo*+bestaudio/best",
            "merge_output_format": "mp4", "quiet": True, "no_warnings": True, "noprogress": True,
            "restrictfilenames": True, "socket_timeout": 20, "retries": 1}
    for u in urls:
        try:
            with yt_dlp.YoutubeDL(opts) as y:
                info = y.extract_info(u, download=True)
                got.append(Path(y.prepare_filename(info)).with_suffix(".mp4").name)
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            why = ("network" if any(k in msg for k in ("allow list", "proxy", "Tunnel", "resolve", "timed out"))
                   else "login" if any(k in msg.lower() for k in ("login", "cookies", "private", "rate-limit"))
                   else "other")
            failed.append({"url": u, "why": why})
    res = {"saved": got, "folder": str(out)}
    if failed:
        res["failed"] = failed
        res["hint"] = {"network": "у Claude закрыт доступ к этому сайту - скачай рилс сам и положи файл в папку",
                       "login": "пост закрыт или нужен вход - скачай рилс сам и положи файл в папку",
                       "other": "не получилось скачать - пришли сам файл"}[failed[0]["why"]]
    return res
