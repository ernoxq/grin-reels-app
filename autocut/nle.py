# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
"""Finished reel -> editable project for CapCut (desktop 9.x draft), DaVinci Resolve / Final Cut (FCPXML).

The project references the ORIGINAL clips (not the rendered mp4): every cut, insert, caption and
the title sit on the timeline as separate pieces, so the person keeps editing by hand.
Paths inside the project are the paths on the person's computer: pass --map CLOUD_DIR=MAC_DIR.
"""
from __future__ import annotations

import copy
import json
import subprocess
import time
import uuid
from fractions import Fraction
from pathlib import Path
from xml.sax.saxutils import escape

from .paths import app_root

US = 1_000_000


# ------------------------------------------------------------------ neutral timeline
def _probe(p: str) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,r_frame_rate:stream_side_data=rotation:stream_tags=rotate:format=duration",
                        "-of", "json", p], capture_output=True, text=True)
    j = json.loads(r.stdout or "{}")
    st = (j.get("streams") or [{}])[0]
    w, h = st.get("width", 1080), st.get("height", 1920)
    rot = 0
    for sd in st.get("side_data_list", []) or []:
        rot = int(sd.get("rotation", 0) or 0)
    rot = rot or int((st.get("tags") or {}).get("rotate", 0) or 0)
    if abs(rot) % 180 == 90:
        w, h = h, w
    dur = float((j.get("format") or {}).get("duration", 0) or 0)
    return {"w": w, "h": h, "dur": dur, "image": Path(p).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".heic"}}


def build_timeline(spec_path: Path) -> dict:
    spec = json.loads(Path(spec_path).read_text())
    job = Path(spec_path).parent
    parts_f = job / "story_parts.json"
    parts = json.loads(parts_f.read_text()) if parts_f.exists() else [
        {"file": spec["sources"]["A"], "start": 0.0, "dur": 1e9}]
    main, t = [], 0.0
    for seg in spec["voice"]:  # map story time -> original clip, split across clip borders
        a, left = seg["in"], seg["dur"]
        while left > 0.01:
            p = next((x for x in parts if x["start"] <= a + 1e-6 < x["start"] + x["dur"] - 0.02), None)
            if p is None:  # in the last few ms of a clip: jump to the next one
                nxt = [x for x in parts if x["start"] > a]
                if not nxt:
                    break
                left -= nxt[0]["start"] - a; a = nxt[0]["start"]
                continue
            take = min(left, p["start"] + p["dur"] - a)
            main.append({"file": p["file"], "in": a - p["start"], "dur": take, "start": t})
            t, a, left = t + take, a + take, left - take
    over = []
    for b in spec.get("broll", []):
        over.append({"file": spec["sources"][b["src"]], "in": b["in"], "start": b["start"], "dur": b["dur"],
                     "speed": b.get("speed", 1.0), "image": bool(b.get("image"))})
    for o in spec.get("overlays", []) or []:
        f = o.get("file") or o.get("asset")
        if f:
            over.append({"file": str(f if Path(f).is_absolute() else app_root() / "library" / f), "in": 0.0,
                         "start": o["start"], "dur": o["end"] - o["start"], "speed": 1.0,
                         "image": Path(f).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}})
    caps = [{"text": c["text"].replace("\n", " "), "start": c["start"], "end": c["end"]} for c in spec["captions"]]
    title = spec.get("title") or {}
    st = spec.get("sticker") or {}
    sticker = None
    if st.get("asset"):
        sticker = {"file": str(app_root() / "library" / st["asset"]), "start": st["start"], "end": st["end"]}
    return {"duration": spec["duration"], "main": main, "over": over, "captions": caps,
            "title": {"text": "\n".join(title.get("lines", [])), "start": title.get("start", 0),
                      "end": title.get("end", 0)} if title.get("lines") else None,
            "sticker": sticker, "canvas": spec["canvas"],
            "fonts": {"caption": spec["caption_style"].get("font_name"),
                      "title": (title.get("style") or {}).get("font_name")}}


def _mapper(pairs: list[str]):
    pm = [p.split("=", 1) for p in pairs or []]

    def f(path: str) -> str:
        for a, b in pm:
            if path.startswith(a):
                return b.rstrip("/") + "/" + path[len(a):].lstrip("/")
        return path
    return f


# ------------------------------------------------------------------ SRT
def _ts(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def write_srt(tl: dict, out: Path) -> Path:
    lines = []
    for i, c in enumerate(tl["captions"], 1):
        lines += [str(i), f"{_ts(c['start'])} --> {_ts(c['end'])}", c["text"], ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


# ------------------------------------------------------------------ FCPXML (DaVinci Resolve, Final Cut Pro)
def write_fcpxml(tl: dict, out: Path, mapper=lambda p: p, name: str = "GRIN Reel") -> Path:
    fps = int(tl["canvas"].get("fps", 30))
    W, H = tl["canvas"]["w"], tl["canvas"]["h"]

    def rt(sec: float) -> str:
        fr = int(round(sec * fps))
        return f"{fr * 100}/{fps * 100}s" if fr else "0s"

    assets, res = {}, []

    def asset(path: str) -> str:
        if path in assets:
            return assets[path]
        info = _probe(path)
        aid = f"r{len(assets) + 3}"
        assets[path] = aid
        url = "file://" + "/".join(escape(x) for x in mapper(path).split("/"))
        dur = rt(info["dur"] or 5)
        if info["image"]:
            res.append(f'<asset id="{aid}" name="{escape(Path(path).name)}" start="0s" duration="0s" hasVideo="1" '
                       f'format="r1"><media-rep kind="original-media" src="{url}"/></asset>')
        else:
            res.append(f'<asset id="{aid}" name="{escape(Path(path).name)}" start="0s" duration="{dur}" hasVideo="1" '
                       f'hasAudio="1" format="r1" audioSources="1" audioChannels="2">'
                       f'<media-rep kind="original-media" src="{url}"/></asset>')
        return aid

    def connected(item: dict, parent: dict, lane: int, mute: bool) -> str:
        off = parent["in"] + (item["start"] - parent["start"])
        aid = asset(item["file"])
        vol = '<adjust-volume amount="-96dB"/>' if mute else ""
        speed = item.get("speed", 1.0)
        tm = ""
        if abs(speed - 1.0) > 0.01 and not item.get("image"):
            tm = (f'<timeMap><timept time="0s" value="{rt(item["in"])}" interp="smooth2"/>'
                  f'<timept time="{rt(item["dur"])}" value="{rt(item["in"] + item["dur"] * speed)}" interp="smooth2"/></timeMap>')
        return (f'<asset-clip ref="{aid}" lane="{lane}" offset="{rt(off)}" name="{escape(Path(item["file"]).name)}" '
                f'start="{rt(item["in"])}" duration="{rt(item["dur"])}" format="r1">{tm}{vol}</asset-clip>')

    def title_el(text: str, start: float, end: float, parent: dict, lane: int, size: int, n: int, ypos: int) -> str:
        off = parent["in"] + (start - parent["start"])
        body = escape(text)
        return (f'<title ref="r2" lane="{lane}" offset="{rt(off)}" name="{escape(text[:30])}" start="0s" '
                f'duration="{rt(max(0.1, end - start))}">'
                f'<param name="Position" key="9999/999166631/999166633/1/100/101" value="0 {ypos}"/>'
                f'<text><text-style ref="ts{n}">{body}</text-style></text>'
                f'<text-style-def id="ts{n}"><text-style font="Montserrat" fontSize="{size}" fontColor="1 1 1 1" '
                f'bold="1" alignment="center"/></text-style-def></title>')

    def parent_at(t: float) -> dict:
        for m in tl["main"]:
            if m["start"] <= t < m["start"] + m["dur"]:
                return m
        return tl["main"][-1]

    attached: dict[int, list[str]] = {i: [] for i in range(len(tl["main"]))}
    n = 0
    for o in tl["over"]:
        p = parent_at(o["start"]); attached[tl["main"].index(p)].append(connected(o, p, 1, True))
    if tl.get("sticker"):
        s = tl["sticker"]; p = parent_at(s["start"])
        attached[tl["main"].index(p)].append(connected(
            {"file": s["file"], "in": 0, "start": s["start"], "dur": s["end"] - s["start"], "image": True}, p, 2, True))
    for c in tl["captions"]:
        n += 1; p = parent_at(c["start"])
        attached[tl["main"].index(p)].append(title_el(c["text"], c["start"], c["end"], p, 3, 60, n, -560))
    if tl.get("title"):
        t = tl["title"]; n += 1; p = parent_at(t["start"])
        attached[tl["main"].index(p)].append(title_el(t["text"], t["start"], t["end"], p, 4, 110, n, 380))

    spine = []
    for i, m in enumerate(tl["main"]):
        aid = asset(m["file"])
        spine.append(f'<asset-clip ref="{aid}" offset="{rt(m["start"])}" name="{escape(Path(m["file"]).name)}" '
                     f'start="{rt(m["in"])}" duration="{rt(m["dur"])}" format="r1" tcFormat="NDF">'
                     + "".join(attached[i]) + "</asset-clip>")
    total = sum(m["dur"] for m in tl["main"])
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>\n<fcpxml version="1.9"><resources>'
           f'<format id="r1" name="FFVideoFormatRateUndefined" frameDuration="100/{fps * 100}s" width="{W}" height="{H}"/>'
           '<effect id="r2" name="Basic Title" uid=".../Titles.localized/Bumper:Opener.localized/Basic Title.localized/Basic Title.moti"/>'
           + "".join(res) + f'</resources><library><event name="GRIN Reels"><project name="{escape(name)}">'
           f'<sequence format="r1" duration="{rt(total)}" tcStart="0s" tcFormat="NDF" audioLayout="stereo" audioRate="48k">'
           "<spine>" + "".join(spine) + "</spine></sequence></project></event></library></fcpxml>\n")
    out.write_text(xml, encoding="utf-8")
    return out


# ------------------------------------------------------------------ CapCut desktop 9.x draft
def _uid() -> str:
    return str(uuid.uuid4()).upper()


def write_capcut(tl: dict, out_dir: Path, mac_draft_dir: str, mapper=lambda p: p, name: str = "GRIN Reel",
                 font_files: dict | None = None) -> Path:
    """Write a CapCut draft folder (draft_info.json + draft_meta_info.json) into out_dir.
    mac_draft_dir = where this folder will live on the Mac (…/com.lveditor.draft/<name>)."""
    tpl = json.loads((app_root() / "library/capcut/template_9x.json").read_text())
    home = mac_draft_dir.split("/Movies/")[0] if "/Movies/" in mac_draft_dir else "/Users/user"
    tpl = json.loads(json.dumps(tpl).replace("__HOME__", home))
    W, H = tl["canvas"]["w"], tl["canvas"]["h"]
    mats: dict[str, list] = {k: [] for k in tpl["materials_keys"]}
    media: dict[str, dict] = {}

    def video_mat(path: str) -> str:
        if path in media:
            return media[path]["id"]
        info = _probe(path)
        m = copy.deepcopy(tpl["video_material"])
        mid = _uid()
        m.update({"id": mid, "path": mapper(path), "material_name": Path(path).name, "width": info["w"],
                  "height": info["h"], "duration": int((info["dur"] or 10800) * US),
                  "type": "photo" if info["image"] else "video", "has_audio": not info["image"],
                  "local_material_id": str(uuid.uuid4())})
        mats["videos"].append(m)
        media[path] = m
        return mid

    def extras(pack: dict, speed: float = 1.0) -> list[str]:
        refs = []
        for e in pack["extras"]:
            m = copy.deepcopy(e["m"]); m["id"] = _uid()
            if e["kind"] == "speeds":
                m["speed"] = speed
            if e["kind"] == "material_animations":
                m["animations"] = []
            mats.setdefault(e["kind"], []).append(m); refs.append(m["id"])
        return refs

    def vseg(item: dict, render: int, volume: float, scale: float = 1.0) -> dict:
        s = copy.deepcopy(tpl["video"]["segment"])
        sp = item.get("speed", 1.0) or 1.0
        s.update({"id": _uid(), "material_id": video_mat(item["file"]), "speed": sp, "volume": volume,
                  "extra_material_refs": extras(tpl["video"], sp), "render_index": render,
                  "track_render_index": render, "keyframe_refs": [], "common_keyframes": [],
                  "target_timerange": {"start": int(item["start"] * US), "duration": int(item["dur"] * US)},
                  "source_timerange": None if item.get("image") else
                  {"start": int(item["in"] * US), "duration": int(item["dur"] * sp * US)}})
        s["clip"]["scale"] = {"x": scale, "y": scale}
        s["clip"]["transform"] = {"x": 0.0, "y": 0.0}
        return s

    def text_seg(text: str, start: float, end: float, size: float, y: float, font: str | None, color=(1, 1, 1),
                 render: int = 14000) -> dict:
        m = copy.deepcopy(tpl["text_material"])
        mid = _uid()
        style = {"fill": {"content": {"solid": {"color": list(color)}, "render_type": "solid"}},
                 "range": [0, len(text)], "size": size,
                 "strokes": [{"width": 0.06, "mode": 0, "content": {"solid": {"color": [0, 0, 0]}, "render_type": "solid"}}],
                 "font": {"path": font or m.get("font_path", ""), "id": ""}}
        m.update({"id": mid, "content": json.dumps({"styles": [style], "text": text}, ensure_ascii=False),
                  "base_content": "", "font_size": size, "font_path": font or "", "font_resource_id": "",
                  "fonts": [], "words": {"end_time": [], "start_time": [], "text": []},
                  "current_words": {"end_time": [], "start_time": [], "text": []}})
        mats["texts"].append(m)
        s = copy.deepcopy(tpl["text"]["segment"])
        s.update({"id": _uid(), "material_id": mid, "extra_material_refs": extras(tpl["text"]),
                  "render_index": render, "track_render_index": render,
                  "target_timerange": {"start": int(start * US), "duration": int(max(0.1, end - start) * US)}})
        s["clip"]["transform"] = {"x": 0.0, "y": y}
        s["clip"]["scale"] = {"x": 1.0, "y": 1.0}
        return s

    def track(kind: str, segs: list, attr: int = 0) -> dict:
        t = copy.deepcopy(tpl["video_track" if kind == "video" else "text_track"])
        t.update({"id": _uid(), "segments": segs, "attribute": attr})
        return t

    fonts = font_files or {}
    tracks = [track("video", [vseg(m, 0, 1.0) for m in tl["main"]])]
    if tl["over"]:
        tracks.append(track("video", [vseg(o, 1, 0.0) for o in tl["over"]]))
    if tl.get("sticker"):
        s = tl["sticker"]
        tracks.append(track("video", [vseg({"file": s["file"], "in": 0, "start": s["start"], "dur": s["end"] - s["start"],
                                             "image": True}, 2, 0.0, 0.37)]))
    tracks.append(track("text", [text_seg(c["text"], c["start"], c["end"], 7.0, -0.55, fonts.get("caption"))
                                 for c in tl["captions"]]))
    if tl.get("title"):
        t = tl["title"]
        tracks.append(track("text", [text_seg(t["text"], t["start"], t["end"], 15.0, 0.25, fonts.get("title"),
                                              render=14001)]))
    total = int(max(tl["duration"], sum(m["dur"] for m in tl["main"])) * US)
    d = copy.deepcopy(tpl["draft"])
    now = int(time.time())
    did = _uid()
    d.update({"id": did, "name": name, "duration": total, "tracks": tracks, "materials": mats, "fps": float(tl["canvas"].get("fps", 30)),
              "canvas_config": {"background": None, "height": H, "ratio": "original", "width": W},
              "create_time": now, "update_time": now, "path": "", "cover": None})
    for k in ("platform", "last_modified_platform"):
        if isinstance(d.get(k), dict):
            d[k].update({"device_id": "", "hard_disk_id": "", "mac_address": ""})
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "draft_info.json").write_text(json.dumps(d, ensure_ascii=False))
    meta = copy.deepcopy(tpl["meta"])
    meta.update({"draft_id": _uid(), "draft_name": name, "draft_fold_path": mac_draft_dir,
                 "draft_root_path": mac_draft_dir.rsplit("/", 1)[0], "draft_cover": "",
                 "tm_draft_create": now * US, "tm_draft_modified": now * US, "tm_duration": total,
                 "draft_materials": [], "draft_timeline_materials_size_": 0})
    (out_dir / "draft_meta_info.json").write_text(json.dumps(meta, ensure_ascii=False))
    return out_dir


# ------------------------------------------------------------------ one call: everything into the person's folders
def export_all(spec_path: Path, deliver: Path, name: str, video: Path | None = None, capcut_root: Path | None = None,
               maps: list[str] | None = None, kinds: tuple = ("capcut", "fcpxml", "srt")) -> dict:
    """deliver = the «Готовое» folder (as seen by this shell). capcut_root = …/com.lveditor.draft (this shell).
    maps = ["/path/in/this/shell=/Users/x/real/path", ...] so the projects point at the person's real files."""
    import shutil
    spec = json.loads(Path(spec_path).read_text())
    tl = build_timeline(Path(spec_path))
    mapper = _mapper(maps or [])
    deliver.mkdir(parents=True, exist_ok=True)
    proj = deliver / f"{name} - проект"
    assets = proj / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    got = {}
    # library files (sticker, overlays) are copied next to the project so the editor can find them
    def keep(f: str) -> str:
        if str(f).startswith(str(app_root())):
            dst = assets / Path(f).name
            shutil.copy2(f, dst)
            return str(dst)
        return f
    if tl.get("sticker"):
        tl["sticker"]["file"] = keep(tl["sticker"]["file"])
    for o in tl["over"]:
        o["file"] = keep(o["file"])
    fonts = {}
    for f in spec.get("fonts", []):
        src = app_root() / "library" / f
        if src.exists():
            dst = assets / src.name
            shutil.copy2(src, dst)
            for role, fam in tl["fonts"].items():
                if fam and fam.split()[0].lower() in src.name.lower() and role not in fonts:
                    fonts[role] = mapper(str(dst))
    if video and Path(video).exists():
        dst = deliver / f"{name}.mp4"
        shutil.copy2(video, dst)
        got["video"] = str(dst)
    if "srt" in kinds:
        got["srt"] = str(write_srt(tl, proj / f"{name}.srt"))
    if "fcpxml" in kinds:
        got["fcpxml"] = str(write_fcpxml(tl, proj / f"{name} (DaVinci, Final Cut).fcpxml", mapper, name))
    if "capcut" in kinds:
        if capcut_root and Path(capcut_root).exists():
            d = Path(capcut_root) / name
            write_capcut(tl, d, mapper(str(d)), mapper, name, fonts)
            got["capcut"] = name
        else:  # no CapCut folder connected: leave the draft next to the project, the person can copy it
            d = proj / "CapCut" / name
            write_capcut(tl, d, mapper(str(d)), mapper, name, fonts)
            got["capcut_folder"] = str(d)
    return got
