# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
# Licensed, not sold: see LICENSE.md. Redistribution or resale is prohibited.
"""GRIN Reels app: a local web page (computer browser or iPhone on the same Wi-Fi).

Three steps on one screen: your video -> your shots and photos -> «Собрать рилс».
"Мои файлы" tab: drop fonts, music, stickers, LUTs; they appear in the choices at once.
One job at a time (one worker thread) so an 8 GB laptop never runs out of memory.
"""
from __future__ import annotations

import json
import queue
import re
import socket
import threading
import time
import traceback
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from .choices import KINDS, LIB, ROOT, apply_choices, list_library

JOBS, UPLOADS = ROOT / "jobs", ROOT / "uploads"
for d in (JOBS, UPLOADS):
    d.mkdir(exist_ok=True)

app = FastAPI(title="GRIN Reels")
q: "queue.Queue[str]" = queue.Queue()
state: dict[str, dict] = {}


def _safe(name: str) -> str:
    stem, ext = Path(name or "file").stem, Path(name or "").suffix.lower()
    return (re.sub(r"[^\w\-]+", "_", stem, flags=re.UNICODE).strip("_") or "file")[:60] + ext


async def _save(up: UploadFile, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        while chunk := await up.read(1 << 20):  # stream: big iPhone videos never sit in RAM
            f.write(chunk)
    return dest


def _worker() -> None:
    from .autoreel import run
    from .reel import load_spec, render_reel
    while True:
        jid = q.get()
        job = state[jid]
        job.update(status="running", step="Слушаю видео и расставляю субтитры…")
        try:
            out = JOBS / jid
            out.mkdir(parents=True, exist_ok=True)
            style = json.loads((ROOT / "styles" / job["style"]).read_text())
            style = apply_choices(style, job["choices"])
            sp = out / "style.json"
            sp.write_text(json.dumps(style, ensure_ascii=False))
            spec_path = run(job["aroll"], job["broll"], str(sp), str(out), script=job.get("script"),
                            title=job["choices"].get("title") or None, lite=job.get("lite", False))
            job["step"] = "Монтирую и раскрашиваю…"
            render_reel(load_spec(spec_path), out / "final.mp4")
            try:  # keep a copy where people look for videos: ~/Movies/GRIN Reels
                import shutil
                mv = Path.home() / "Movies" / "GRIN Reels"
                mv.mkdir(parents=True, exist_ok=True)
                job["saved"] = str(shutil.copy2(out / "final.mp4", mv / f"GRIN_{jid}.mp4"))
            except OSError:
                pass
            job.update(status="done", step="Готово!")
        except Exception as e:  # keep the worker alive whatever happens
            job.update(status="error", step="Не получилось", error=str(e)[:400], trace=traceback.format_exc()[-1200:])
        q.task_done()


threading.Thread(target=_worker, daemon=True).start()


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (ROOT / "web" / "app.html").read_text(encoding="utf-8")


@app.get("/manifest.json")
def manifest() -> dict:  # iPhone: Share -> Add to Home Screen opens full screen like an app
    return {"name": "GRIN Reels", "short_name": "GRIN Reels", "start_url": "/", "display": "standalone",
            "background_color": "#E6E5E0", "theme_color": "#2A2A28",
            "icons": [{"src": "/icon.png", "sizes": "1024x1024", "type": "image/png"}]}


@app.get("/icon.png")
def icon() -> FileResponse:
    return FileResponse(ROOT / "web" / "icon.png", media_type="image/png")


@app.post("/api/style-from-ref")
def style_from_ref(video: UploadFile = File(...), name: str = Form("")) -> dict:
    """Learn pace, B&W share and colour from one finished reel someone else made."""
    from .reflearn import learn
    nm = _safe(name or Path(video.filename or "ref").stem).lower().replace(".", "_")[:40] or "ref"
    dest = UPLOADS / "refs" / (nm + Path(video.filename or "x.mp4").suffix.lower())
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        while chunk := video.file.read(1 << 20):
            f.write(chunk)
    rep = learn(dest, f"ref_{nm}")
    return {"style": f"ref_{nm}.json", "report": rep, "library": list_library()}


@app.post("/api/jobs/{jid}/reveal")
def reveal(jid: str) -> dict:  # «Показать в Finder» in the Mac app
    import subprocess
    import sys
    p = state.get(jid, {}).get("saved") or str(JOBS / jid / "final.mp4")
    if sys.platform == "darwin":
        subprocess.run(["open", "-R", p])
    elif sys.platform.startswith("win"):
        subprocess.run(["explorer", "/select,", p])
    return {"path": p}


@app.get("/api/icon/{name}.svg")
def icon_svg(name: str, color: str = "#1E1E1D"):
    from fastapi.responses import Response
    from .icons import ICONS, svg
    if name not in ICONS or not re.fullmatch(r"#?[0-9A-Fa-f]{3,8}|currentColor", color):
        raise HTTPException(404)
    return Response(svg(name, color if color.startswith("#") or color == "currentColor" else "#" + color, size=24),
                    media_type="image/svg+xml")


@app.get("/api/library")
def library() -> dict:
    return list_library()


@app.post("/api/library/{kind}")
async def add_to_library(kind: str, files: list[UploadFile] = File(...)) -> dict:
    if kind not in KINDS:
        raise HTTPException(400, "unknown kind")
    folder, exts = KINDS[kind]
    added, skipped = [], []
    for up in files:
        name = _safe(up.filename)
        if Path(name).suffix.lower() not in exts:
            skipped.append(up.filename)
            continue
        await _save(up, LIB / folder / "my" / name)
        added.append(name)
    if (LIB / ".index.json").exists():
        (LIB / ".index.json").unlink()
    return {"added": added, "skipped": skipped, "library": list_library()}


@app.post("/api/reel")
async def make_reel(aroll: UploadFile = File(...), broll: list[UploadFile] = File(default=[]),
                    script: str = Form(""), style: str = Form("warm_intro.json"), choices: str = Form("{}")) -> dict:
    if not (ROOT / "styles" / style).exists():
        raise HTTPException(400, "unknown style")
    jid = time.strftime("%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
    folder = UPLOADS / jid
    a = await _save(aroll, folder / ("main_" + _safe(aroll.filename)))
    bs = [str(await _save(b, folder / f"b{i + 1:02d}_{_safe(b.filename)}")) for i, b in enumerate(broll) if b.filename]
    ch = json.loads(choices or "{}")
    sp = None
    if script.strip():
        sp = folder / "script.txt"
        sp.write_text(script.strip(), encoding="utf-8")
    state[jid] = {"id": jid, "status": "queued", "step": "В очереди…", "aroll": str(a), "broll": bs,
                  "script": str(sp) if sp else None, "style": style, "choices": ch,
                  "lite": bool(ch.get("lite")) and bool(sp)}
    q.put(jid)
    return {"id": jid}


@app.get("/api/jobs/{jid}")
def job(jid: str) -> dict:
    if jid not in state:
        raise HTTPException(404)
    j = state[jid]
    return {k: j.get(k) for k in ("id", "status", "step", "error", "saved")}


@app.get("/api/jobs/{jid}/video")
def video(jid: str, download: int = 0) -> FileResponse:
    p = JOBS / jid / "final.mp4"
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p, media_type="video/mp4", filename=f"GRIN_reel_{jid}.mp4" if download else None)


def local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"
