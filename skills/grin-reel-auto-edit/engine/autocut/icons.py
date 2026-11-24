# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
"""GRIN icon set for reels: clean 24-px line icons, any colour, any size.

Every icon is drawn on a 24x24 grid with one stroke width and round ends, so
they all look like one family. `render()` turns one into a PNG sticker:
just the line, or inside a round / rounded-square / pill badge with a label.

    python -m autocut icon heart --color "#E4F23C" --bg "#1E1E1D" --shape circle --size 320
    python -m autocut icons            # contact sheet of the whole set
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# name -> (Russian label, SVG body on a 24x24 grid; stroke = currentColor, fill="C" = filled with currentColor)
ICONS: dict[str, tuple[str, str]] = {
    # --- edit & video
    "play": ("Плей", '<path d="M8 5.5v13l10.5-6.5z" fill="C"/>'),
    "pause": ("Пауза", '<path d="M8 5v14M16 5v14"/>'),
    "record": ("Запись", '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4" fill="C"/>'),
    "camera": ("Камера", '<path d="M4 8.5A1.5 1.5 0 0 1 5.5 7h2l1.5-2h6l1.5 2h2A1.5 1.5 0 0 1 20 8.5v9a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 17.5z"/><circle cx="12" cy="13" r="3.5"/>'),
    "video": ("Видео", '<rect x="3" y="6" width="13" height="12" rx="2"/><path d="M16 10.5l5-3v9l-5-3z"/>'),
    "phone": ("Вертикаль", '<rect x="7" y="2.5" width="10" height="19" rx="2.5"/><path d="M10.5 18.5h3"/>'),
    "mic": ("Микрофон", '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M9 21h6"/>'),
    "music": ("Музыка", '<path d="M9 18V5l11-2v13"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="17.5" cy="16" r="2.5"/>'),
    "scissors": ("Нарезка", '<circle cx="6" cy="6" r="2.5"/><circle cx="6" cy="18" r="2.5"/><path d="M8 7.5L20 18M8 16.5L20 6"/>'),
    "timeline": ("Таймлайн", '<rect x="3" y="9" width="8" height="6" rx="1.5"/><rect x="13" y="9" width="8" height="6" rx="1.5"/><path d="M12 4v16M10 4h4"/>'),
    "layers": ("Слои", '<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 13l9 5 9-5"/>'),
    "text": ("Текст", '<path d="M5 6V4.5h14V6M12 4.5v15M9 19.5h6"/>'),
    "captions": ("Субтитры", '<rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="M10.5 10.2a2.2 2.2 0 1 0 0 3.6M17 10.2a2.2 2.2 0 1 0 0 3.6"/>'),
    "image": ("Фото", '<rect x="3" y="4" width="18" height="16" rx="2.5"/><circle cx="9" cy="9.5" r="1.8"/><path d="M21 15l-5-5-9 10"/>'),
    "film": ("Плёнка", '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 3v18M16 3v18M4 7.5h4M4 12h4M4 16.5h4M16 7.5h4M16 12h4M16 16.5h4"/>'),
    "speed": ("Скорость", '<path d="M4.5 16a8 8 0 1 1 15 0"/><path d="M12 14l4-5"/><circle cx="12" cy="14" r="1.2" fill="C"/>'),
    "slowmo": ("Замедление", '<circle cx="12" cy="12" r="8.5"/><path d="M12 7v5l3 2"/><path d="M3 4.5l2 2M21 4.5l-2 2"/>'),
    "zoom": ("Приближение", '<circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5L20 20M10.5 8v5M8 10.5h5"/>'),
    "crop": ("Кадрирование", '<path d="M6 2.5V18h15.5M2.5 6H18v15.5"/>'),
    "volume": ("Звук", '<path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z"/><path d="M15.5 9a4.5 4.5 0 0 1 0 6M18 6.5a8 8 0 0 1 0 11"/>'),
    "mute": ("Без звука", '<path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z"/><path d="M16 9.5l5 5M21 9.5l-5 5"/>'),
    "wand": ("Магия", '<path d="M4 20L15 9"/><path d="M14 4v3M12.5 5.5h3M19 9v3M17.5 10.5h3M18 3.5l1 1"/>'),
    # --- colour
    "sun": ("Яркость", '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M4.6 4.6L6 6M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4L6 18M18 6l1.4-1.4"/>'),
    "contrast": ("Контраст", '<circle cx="12" cy="12" r="8.5"/><path d="M12 3.5a8.5 8.5 0 0 1 0 17z" fill="C"/>'),
    "drop": ("Насыщенность", '<path d="M12 3s6.5 7 6.5 11.5a6.5 6.5 0 0 1-13 0C5.5 10 12 3 12 3z"/>'),
    "temperature": ("Тепло / холод", '<path d="M10 14.5V5a2 2 0 0 1 4 0v9.5a4 4 0 1 1-4 0z"/><path d="M12 9v7"/>'),
    "palette": ("Палитра", '<path d="M12 3a9 9 0 1 0 0 18c1.2 0 1.8-.8 1.8-1.7 0-1.4-1.3-1.7-1.3-3 0-1 .8-1.8 1.8-1.8H17a4 4 0 0 0 4-4C21 6.4 17 3 12 3z"/><circle cx="7.5" cy="11" r="1.1" fill="C"/><circle cx="10" cy="7" r="1.1" fill="C"/><circle cx="15" cy="7.5" r="1.1" fill="C"/>'),
    "whitepoint": ("Точка белого", '<path d="M14.5 4.5l5 5M17 7l-9.5 9.5-3.5 1 1-3.5L14.5 4.5"/><circle cx="18.5" cy="18.5" r="2.5" fill="C" fill-opacity=".25"/>'),
    "lut": ("Фильтр LUT", '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M4 12h16M12 4v16"/><path d="M12 4h5a3 3 0 0 1 3 3v5h-8z" fill="C" fill-opacity=".35"/>'),
    "bw": ("Ч/Б", '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M4 4l16 16"/><path d="M4 4h13a3 3 0 0 1 3 3v13z" fill="C"/>'),
    # --- social & calls to action
    "heart": ("Лайк", '<path d="M12 20s-7.5-4.6-7.5-10A4.3 4.3 0 0 1 12 7.4 4.3 4.3 0 0 1 19.5 10c0 5.4-7.5 10-7.5 10z"/>'),
    "comment": ("Комментарий", '<path d="M20 11.5a7.5 7.5 0 0 1-11 6.7L4 19.5l1.4-4.4A7.5 7.5 0 1 1 20 11.5z"/>'),
    "send": ("Отправить", '<path d="M21 3.5L10 14.5M21 3.5l-6.5 17-4.5-6-6-4.5z"/>'),
    "bookmark": ("Сохранить", '<path d="M6.5 3.5h11v17l-5.5-4-5.5 4z"/>'),
    "share": ("Поделиться", '<circle cx="18" cy="5.5" r="2.5"/><circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="18.5" r="2.5"/><path d="M8.2 10.8l7.6-4M8.2 13.2l7.6 4"/>'),
    "bell": ("Подписка", '<path d="M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 1.5h-15z"/><path d="M10 20.5a2 2 0 0 0 4 0"/>'),
    "user": ("Профиль", '<circle cx="12" cy="8.5" r="4"/><path d="M4.5 20.5a7.5 7.5 0 0 1 15 0"/>'),
    "users": ("Команда", '<circle cx="9" cy="8.5" r="3.5"/><path d="M2.5 19.5a6.5 6.5 0 0 1 13 0"/><path d="M15.5 5.2a3.5 3.5 0 0 1 0 6.6M18 13.6a6.5 6.5 0 0 1 3.5 5.9"/>'),
    "message": ("Написать", '<rect x="3" y="5" width="18" height="13" rx="2.5"/><path d="M3.5 6.5l8.5 6 8.5-6"/>'),
    "link": ("Ссылка", '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>'),
    "pin": ("Место", '<path d="M12 21s-6.5-6-6.5-11a6.5 6.5 0 0 1 13 0c0 5-6.5 11-6.5 11z"/><circle cx="12" cy="10" r="2.5"/>'),
    "calendar": ("Дата", '<rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/><path d="M3.5 9.5h17M8 3v4M16 3v4"/>'),
    "clock": ("Время", '<circle cx="12" cy="12" r="8.5"/><path d="M12 7v5l3.5 2"/>'),
    "cart": ("Купить", '<path d="M3 4h2.5l2.2 11h10.6L20.5 7.5H7"/><circle cx="9" cy="19" r="1.5"/><circle cx="17" cy="19" r="1.5"/>'),
    "gift": ("Подарок", '<rect x="3.5" y="8.5" width="17" height="4" rx="1"/><path d="M5 12.5v8h14v-8M12 8.5v12M12 8.5C10 4 6.5 4.5 7.5 7.5c.5 1 4.5 1 4.5 1s4 0 4.5-1c1-3-2.5-3.5-4.5 1z"/>'),
    "star": ("Звезда", '<path d="M12 3.5l2.6 5.4 5.9.8-4.3 4.1 1 5.9L12 16.9l-5.2 2.8 1-5.9-4.3-4.1 5.9-.8z"/>'),
    "fire": ("Огонь", '<path d="M12 21a6.5 6.5 0 0 0 6.5-6.5c0-4-3-6-4.5-9.5-1 2.5-2.5 3.5-3.5 3.5 0-1.5-.5-3-1.5-4C7.5 7.5 5.5 10 5.5 14.5A6.5 6.5 0 0 0 12 21z"/><path d="M12 21a2.8 2.8 0 0 1-2.8-2.8c0-1.8 1.4-2.6 2.8-4.7 1.4 2.1 2.8 2.9 2.8 4.7A2.8 2.8 0 0 1 12 21z"/>'),
    "bolt": ("Молния", '<path d="M13 2.5L5 13.5h6l-1 8 8-11h-6z"/>'),
    "idea": ("Идея", '<path d="M9 17.5h6M10 21h4M12 3a6.5 6.5 0 0 0-3.8 11.8c.5.4.8 1 .8 1.7v1h6v-1c0-.7.3-1.3.8-1.7A6.5 6.5 0 0 0 12 3z"/>'),
    "target": ("Цель", '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="1" fill="C"/>'),
    "megaphone": ("Анонс", '<path d="M3.5 10v4h3l9 5V5l-9 5z"/><path d="M6.5 14l1.5 5.5h2.5L9.5 14M19 9.5a3 3 0 0 1 0 5"/>'),
    "chart": ("Рост", '<path d="M3.5 20.5h17"/><path d="M5 16l5-5 3.5 3.5L20 8"/><path d="M15.5 8H20v4.5"/>'),
    "eye": ("Просмотры", '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>'),
    "check": ("Готово", '<path d="M4.5 12.5l5 5L19.5 7"/>'),
    "cross": ("Нет", '<path d="M6 6l12 12M18 6L6 18"/>'),
    "plus": ("Плюс", '<path d="M12 5v14M5 12h14"/>'),
    "arrow-right": ("Стрелка вправо", '<path d="M4 12h15M13.5 6.5L19 12l-5.5 5.5"/>'),
    "arrow-down": ("Стрелка вниз", '<path d="M12 4v15M6.5 13.5L12 19l5.5-5.5"/>'),
    "swipe-up": ("Свайп вверх", '<path d="M12 20V6M7 10.5L12 5.5l5 5"/><path d="M8 20h8" stroke-opacity=".5"/>'),
    "hand-tap": ("Нажми", '<path d="M9.5 12V5.5a1.5 1.5 0 0 1 3 0V11l4.6.9a2 2 0 0 1 1.6 2.2l-.6 4.4a2.5 2.5 0 0 1-2.5 2.1h-4.2a2.5 2.5 0 0 1-2.1-1.1L5.5 15.3a1.4 1.4 0 0 1 2.2-1.7z"/><path d="M6.5 6.5a5 5 0 0 1 9 0" stroke-opacity=".5"/>'),
    "sparkle": ("Блеск", '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="M18.5 15.5l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7z"/>'),
}

GROUPS = {
    "Монтаж": ["play", "pause", "record", "camera", "video", "phone", "mic", "music", "scissors", "timeline", "layers",
               "text", "captions", "image", "film", "speed", "slowmo", "zoom", "crop", "volume", "mute", "wand"],
    "Цвет": ["sun", "contrast", "drop", "temperature", "palette", "whitepoint", "lut", "bw"],
    "Соцсети и призывы": ["heart", "comment", "send", "bookmark", "share", "bell", "user", "users", "message", "link",
                          "pin", "calendar", "clock", "cart", "gift", "star", "fire", "bolt", "idea", "target",
                          "megaphone", "chart", "eye", "check", "cross", "plus", "arrow-right", "arrow-down",
                          "swipe-up", "hand-tap", "sparkle"],
}


def svg(name: str, color: str = "#1E1E1D", stroke: float = 1.75, size: int = 24) -> str:
    body = ICONS[name][1].replace('fill="C"', f'fill="{color}"')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="{size}" height="{size}" fill="none" '
            f'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">{body}</svg>')


def badge_svg(name: str, color: str = "#1E1E1D", bg: str | None = None, shape: str = "circle",
              stroke: float = 1.75, label: str | None = None, label_color: str | None = None,
              font: str = "Montserrat") -> tuple[str, int, int]:
    """Icon alone, or on a circle / rounded square / pill (pill can carry a short label)."""
    inner = ICONS[name][1].replace('fill="C"', f'fill="{color}"')
    g = (f'<g fill="none" stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" '
         f'stroke-linejoin="round">{inner}</g>')
    if not bg and not label:
        return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-2 -2 28 28">{g}</svg>', 28, 28
    if shape == "pill" or label:
        tw = 0
        if label:
            from PIL import ImageFont
            fp = ROOT / "library/fonts/Montserrat-SemiBold.ttf"
            tw = int(ImageFont.truetype(str(fp), 16).getlength(label)) + 18 if fp.exists() else len(label) * 10 + 18
        w, h = 44 + tw, 44
        back = f'<rect x="0" y="0" width="{w}" height="{h}" rx="22" fill="{bg or "#FFFFFF"}"/>'
        txt = (f'<text x="{44 + 2}" y="28.5" font-family="{font}" font-weight="600" font-size="16" '
               f'fill="{label_color or color}">{label}</text>') if label else ""
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">{back}'
                f'<g transform="translate(10 10) scale(1)">{g}</g>{txt}</svg>', w, h)
    r = 22 if shape == "circle" else 12
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 44 44"><rect width="44" height="44" rx="{r}" '
            f'fill="{bg}"/><g transform="translate(10 10)">{g}</g></svg>', 44, 44)


def render(name: str, out: Path, size: int = 256, **kw) -> Path:
    """PNG with transparent background; `size` = height in pixels."""
    import resvg_py
    s, w, h = badge_svg(name, **kw)
    fonts = [str(p) for p in (ROOT / "library/fonts").rglob("*.ttf")]
    png = resvg_py.svg_to_bytes(svg_string=s, width=int(size * w / h), height=size, font_files=fonts[:60])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(bytes(png))
    return out


def sheet(out: Path, color: str = "#1E1E1D", bg: str = "#E6E5E0", accent: str = "#E4F23C") -> Path:
    """Contact sheet of the whole set (for choosing)."""
    import resvg_py
    cols, cell = 10, 110
    names = [n for g in GROUPS.values() for n in g]
    rows = (len(names) + cols - 1) // cols
    W, H = cols * cell + 40, rows * (cell + 26) + 40
    parts = [f'<rect width="{W}" height="{H}" fill="{bg}"/>']
    for i, n in enumerate(names):
        x, y = 20 + (i % cols) * cell, 20 + (i // cols) * (cell + 26)
        hl = n in ("heart", "whitepoint", "scissors", "captions", "send")
        parts.append(f'<rect x="{x + 15}" y="{y}" width="80" height="80" rx="40" fill="{accent if hl else "#FFFFFF"}"/>')
        inner = ICONS[n][1].replace('fill="C"', f'fill="{color}"')
        parts.append(f'<g transform="translate({x + 31} {y + 16}) scale(2)" fill="none" stroke="{color}" '
                     f'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{inner}</g>')
        parts.append(f'<text x="{x + 55}" y="{y + 102}" text-anchor="middle" font-family="Inter" font-size="12" '
                     f'fill="#6E6D69">{ICONS[n][0]}</text>')
    s = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}">{"".join(parts)}</svg>'
    fonts = [str(p) for p in (ROOT / "library/fonts/inter").glob("*.ttf")]
    out.write_bytes(bytes(resvg_py.svg_to_bytes(svg_string=s, width=W, font_files=fonts)))
    return out


def export_svgs(folder: Path = ROOT / "library/icons") -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for n in ICONS:
        (folder / f"{n}.svg").write_text(svg(n, color="currentColor"))
