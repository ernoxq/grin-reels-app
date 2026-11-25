# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
"""Colour: clear presets (as .cube LUTs), automatic white point, simple sliders.

Order in the render: exposure gain -> white point fix -> LUT (preset/style) -> sliders.

    python -m autocut presets           # (re)build library/luts/presets/*.cube
"""
from __future__ import annotations

from .paths import app_root
import subprocess
import tempfile
from pathlib import Path

import numpy as np

ROOT = app_root()
OUT = ROOT / "library/luts/presets"

# id -> (name for people, what it does, params)
PRESETS: dict[str, tuple[str, str, dict]] = {
    "01_clean": ("Чистый нейтральный", "Правильные цвета, чуть больше глубины. Подходит всегда.",
                 dict(contrast=0.12, sat=0.05)),
    "02_warm_evening": ("Тёплый вечер", "Мягкое золотистое тепло, кожа выглядит живой.",
                        dict(wb=(1.06, 1.0, 0.9), contrast=0.12, sat=0.06, hi=(1.0, 0.85, 0.6), hi_amt=0.05)),
    "03_cool_morning": ("Холодное утро", "Свежий, чистый, слегка голубой.",
                        dict(wb=(0.94, 1.0, 1.07), contrast=0.08, sat=-0.05, lift=0.02)),
    "04_teal_orange": ("Кино: бирюза и оранжевый", "Классика кино: тёплая кожа, бирюзовые тени.",
                       dict(contrast=0.2, sat=0.08, sh=(0.0, 0.55, 0.6), sh_amt=0.10, hi=(1.0, 0.7, 0.4), hi_amt=0.07)),
    "05_film": ("Плёнка", "Приподнятые тени, мягкий контраст, тёплые светлые.",
                dict(contrast=0.1, lift=0.06, crush_hi=0.04, sat=-0.08, hi=(1.0, 0.9, 0.75), hi_amt=0.05,
                     sh=(0.2, 0.35, 0.45), sh_amt=0.04)),
    "06_pastel": ("Пастель", "Светло и нежно: свадьбы, бьюти, лайфстайл.",
                  dict(exposure=0.12, contrast=-0.1, sat=-0.2, lift=0.05, hi=(1.0, 0.92, 0.95), hi_amt=0.04)),
    "07_vivid": ("Сочный", "Яркие цвета и контраст — для еды, путешествий, рекламы.",
                 dict(contrast=0.22, sat=0.28, exposure=0.03)),
    "08_matte": ("Матовый", "Без чёрного, спокойно и стильно.",
                 dict(contrast=-0.05, lift=0.1, crush_hi=0.05, sat=-0.12)),
    "09_moody": ("Тёмный и глубокий", "Глубокие тени, приглушённые цвета — атмосферно.",
                 dict(exposure=-0.1, contrast=0.25, sat=-0.15, sh=(0.1, 0.25, 0.3), sh_amt=0.06)),
    "10_golden_hour": ("Золотой час", "Будто снято на закате.",
                       dict(wb=(1.1, 1.0, 0.82), contrast=0.1, sat=0.1, hi=(1.0, 0.8, 0.45), hi_amt=0.08)),
    "11_bw_soft": ("Ч/Б мягкий", "Чёрно-белый без резкости, светлые тени.", dict(bw=True, contrast=0.05, lift=0.04)),
    "12_bw_contrast": ("Ч/Б контрастный", "Глубокий чёрный, яркий белый.", dict(bw=True, contrast=0.35)),
}


def _apply(rgb: np.ndarray, p: dict) -> np.ndarray:
    x = rgb * np.array(p.get("wb", (1, 1, 1)))
    x = x * (2 ** p.get("exposure", 0.0))
    if c := p.get("contrast", 0.0):  # S-curve around mid grey
        s = 1 / (1 + np.exp(-(x - 0.5) * 8))
        s = (s - 1 / (1 + np.exp(4))) / (1 / (1 + np.exp(-4)) - 1 / (1 + np.exp(4)))
        x = x + c * (s - x) * 1.6 if c > 0 else 0.5 + (x - 0.5) * (1 + c * 0.9)
    lum = (x * np.array([0.2126, 0.7152, 0.0722])).sum(-1, keepdims=True)
    if p.get("bw"):
        x = np.repeat(lum, 3, -1)
    else:
        x = lum + (x - lum) * (1 + p.get("sat", 0.0))
    lum = np.clip(lum, 0, 1)
    if a := p.get("sh_amt"):
        x = x + (np.array(p["sh"]) - 0.5) * a * (1 - lum) ** 2 * 2
    if a := p.get("hi_amt"):
        x = x + (np.array(p["hi"]) - 0.5) * a * lum ** 2 * 2
    lift, top = p.get("lift", 0.0), 1 - p.get("crush_hi", 0.0)
    x = lift + x * (top - lift)
    return np.clip(x, 0, 1)


def write_cube(p: dict, out: Path, title: str, size: int = 33) -> Path:
    g = np.linspace(0, 1, size)
    b, gg, r = np.meshgrid(g, g, g, indexing="ij")  # .cube: red changes fastest
    rgb = np.stack([r, gg, b], -1).reshape(-1, 3)
    y = _apply(rgb, p)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f'TITLE "{title}"\nLUT_3D_SIZE {size}\n' + "\n".join(f"{a:.6f} {c:.6f} {d:.6f}" for a, c, d in y) + "\n")
    return out


def build_presets() -> list[Path]:
    return [write_cube(p, OUT / f"{k}.cube", name) for k, (name, _, p) in PRESETS.items()]


def auto_white_point(video: str, ss: float = 0.0, dur: float | None = None, strength: float = 0.75) -> list[float]:
    """Find what should be white/grey in the shot and return RGB gains that make it neutral.

    Uses the brightest low-saturation pixels (white wall, shirt, paper); falls back to grey-world.
    """
    from PIL import Image
    if dur is None:
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                    video], capture_output=True, text=True).stdout.strip() or 1) - ss
    px = []
    with tempfile.TemporaryDirectory() as d:
        for i, t in enumerate((0.2, 0.5, 0.8)):
            f = Path(d) / f"{i}.png"
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{ss + dur * t:.2f}", "-i", video,
                            "-frames:v", "1", "-vf", "scale=320:-2", str(f)])
            if f.exists():
                px.append(np.asarray(Image.open(f).convert("RGB")).reshape(-1, 3).astype(float))
    if not px:
        return [1.0, 1.0, 1.0]
    a = np.concatenate(px)
    mx, mn = a.max(1), a.min(1)
    sat = (mx - mn) / np.maximum(mx, 1)
    lum = a.mean(1)
    sel = a[(sat < 0.25) & (lum > np.percentile(lum, 85)) & (mx < 250)]
    if len(sel) < 200:  # no clear white/grey object: leave the colour alone (grey-world ruins coloured scenes)
        return [1.0, 1.0, 1.0]
    ref = sel.mean(0)
    gains = ref[1] / np.maximum(ref, 1)
    gains = 1 + (gains - 1) * strength
    return [round(float(np.clip(g, 0.93, 1.07)), 4) for g in gains]  # a nudge, never a repaint


def adjust_filters(adj: dict | None) -> str:
    """Sliders -> ffmpeg filters (after the LUT). Values: -1..1 (temp/tint/exposure/contrast/saturation)."""
    if not adj:
        return ""
    f = []
    if t := adj.get("temp"):
        f.append(f"colortemperature=temperature={int(6500 - 2500 * t)}:mix={min(1, abs(t)) * 0.8:.2f}")
    if tint := adj.get("tint"):
        g = 1 - 0.08 * tint
        f.append(f"colorchannelmixer=gg={g:.3f}")
    e, c, s = adj.get("exposure", 0), adj.get("contrast", 0), adj.get("saturation", 0)
    if e or c or s:
        f.append(f"eq=brightness={0.08 * e:.3f}:contrast={1 + 0.35 * c:.3f}:saturation={1 + 0.6 * s:.3f}")
    return "".join("," + x for x in f)


def wb_filter(g: list[float] | None) -> str:
    if not g or all(abs(x - 1) < 0.005 for x in g):
        return ""
    return f",colorchannelmixer=rr={g[0]}:gg={g[1]}:bb={g[2]}"
