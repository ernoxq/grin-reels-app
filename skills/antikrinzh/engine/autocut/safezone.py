# GRIN Reels — © 2026 Ernest Grin. All rights reserved.
"""Keep title and captions inside the social-media safe zone and off the face.

Safe zone = the area of a 1080x1920 frame that Instagram Reels, TikTok and
YouTube Shorts never cover with their own buttons, captions and progress bar.
The right edge steps in lower down, where the like/comment/share column sits.

Face: the talking head is mostly static, so we sample a few A-roll frames,
find the face with OpenCV (optional dependency) and move the whole text block
below — or, if there is no room, above — the face. One level for the whole
reel, so subtitles never jump around.
"""
from __future__ import annotations

from .paths import app_root
import subprocess
import tempfile
from pathlib import Path

# Union of Reels / TikTok / Shorts overlays, on a 1080x1920 canvas.
DEFAULT = {"top": 270, "bottom": 1495, "left": 130, "right_top": 1000, "right_bottom": 914, "split_y": 876}


def scaled(zone: dict, W: int, H: int) -> dict:
    sx, sy = W / 1080, H / 1920
    return {k: v * (sx if k in ("left", "right_top", "right_bottom") else sy) for k, v in zone.items()}


def right_edge(z: dict, y0: float, y1: float) -> float:
    return z["right_top"] if y1 <= z["split_y"] else z["right_bottom"]


def from_frame(png: Path, W: int = 1080, H: int = 1920) -> dict:
    """Read a safe-zone frame picture: white/light = safe, anything else = covered."""
    import numpy as np
    from PIL import Image
    im = np.asarray(Image.open(png).convert("L").resize((W, H)))
    safe = im > 200
    width = safe.sum(1)
    rows = np.where(width > W * 0.3)[0]  # ignore thin anti-aliased edges
    top, bottom = int(rows[0]), int(rows[-1])
    lefts = np.array([np.where(safe[y])[0][0] for y in rows])
    rights = np.array([np.where(safe[y])[0][-1] for y in rows])
    rs = np.convolve(np.pad(rights, 7, mode="edge"), np.ones(15) / 15, mode="valid")
    d = rs[30:] - rs[:-30]
    if len(d) and d.min() < -20:  # right edge steps in
        k = int(np.argmin(d)) + 15
        rt, rb, split = np.median(rights[:k]), np.median(rights[k:]), int(rows[k])
    else:
        rt = rb = np.median(rights); split = bottom
    return {"top": top, "bottom": bottom, "left": int(np.median(lefts)),
            "right_top": int(rt), "right_bottom": int(rb), "split_y": split}


def face_box(spec: dict, root: Path, samples: int = 6) -> tuple[float, float, float, float] | None:
    """Median face box of the A-roll, in canvas pixels; None if OpenCV/face missing. Uses YuNet (MIT, Shiqi Yu)."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None
    W, H = spec["canvas"]["w"], spec["canvas"]["h"]
    look = spec.get("aroll_look", {})
    S, ax, ay = look.get("zoom", 1.0), look.get("x", 0.0), look.get("y", 0.0)
    sw, sh = round(W * S / 2) * 2, round(H * S / 2) * 2
    cx, cy = (sw - W) / 2 - ax * W / 2, (sh - H) / 2 + ay * H / 2
    segs = [s for s in spec.get("voice", []) if s.get("dur", 0) > 0.3]
    if not segs:
        return None
    model = app_root() / "library/models/face_detection_yunet_2023mar.onnx"
    try:
        det = cv2.FaceDetectorYN.create(str(model), "", (W // 3, H // 3), 0.7)
    except Exception:
        return None
    boxes = []
    with tempfile.TemporaryDirectory() as d:
        for n in range(samples):
            seg = segs[n * len(segs) // samples]
            src = spec["sources"][seg["src"]]
            src = src if Path(src).is_absolute() else str(root / src)
            f = Path(d) / f"{n}.png"
            r = subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{seg['in'] + seg['dur'] / 2:.2f}",
                                "-i", src, "-frames:v", "1", "-vf", f"scale={W // 3}:{H // 3}", str(f)])
            if r.returncode or not f.exists():
                continue
            img = cv2.imread(str(f))
            det.setInputSize((img.shape[1], img.shape[0]))
            _, found = det.detect(img)
            if found is not None and len(found):
                x, y, w, h = max(found, key=lambda b: b[2] * b[3])[:4] * 3.0
                # source (already W x H) -> scaled by S -> cropped
                boxes.append(((x * S) - cx, (y * S) - cy, (x + w) * S - cx, (y + h) * S - cy))
    if len(boxes) < max(2, samples // 3):
        return None
    b = np.median(np.array(boxes), axis=0)
    x0, y0, x1, y1 = b
    return float(x0), float(y0), float(x1), float(y1 + 0.25 * (y1 - y0))  # include chin/neck


def place_block(center_y: float, height: float, z: dict, face=None, pad: float = 24) -> float:
    """Best vertical center for a text block: inside the zone, off the face."""
    lo, hi = z["top"] + height / 2, z["bottom"] - height / 2
    y = min(max(center_y, lo), hi)
    if face:
        fx0, fy0, fx1, fy1 = face
        if y - height / 2 < fy1 + pad and y + height / 2 > fy0 - pad:  # overlaps face vertically
            below = fy1 + pad + height / 2
            above = fy0 - pad - height / 2
            if below <= hi:
                y = below
            elif above >= lo:
                y = above
            else:
                y = hi  # no clean spot: lowest safe line (chin at worst, never the eyes)
    return y
