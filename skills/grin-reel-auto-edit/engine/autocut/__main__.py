# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
# Licensed, not sold: see LICENSE.md. Redistribution or resale is prohibited.
"""CLI:
    python -m autocut run clip.mp4 --preset presets/talking_head.toml
    python -m autocut library                 # list what the asset library sees
    python -m autocut rebuild jobs/clip       # re-export after hand-editing timeline.json
    python -m autocut serve                   # mobile web UI on http://<mac>:8765
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    ap = argparse.ArgumentParser("autocut")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run")
    r.add_argument("src", type=Path)
    r.add_argument("--preset", type=Path, default=ROOT / "presets/talking_head.toml")
    r.add_argument("--library", type=Path, default=ROOT / "library")
    r.add_argument("--jobs", type=Path, default=ROOT / "jobs")
    r.add_argument("--name", help="CapCut draft name")
    r.add_argument("--drafts", type=Path, help="CapCut draft root (default: CapCut's folder on macOS)")
    r.add_argument("--no-preview", action="store_true")

    lb = sub.add_parser("library")
    lb.add_argument("--library", type=Path, default=ROOT / "library")

    rb = sub.add_parser("rebuild")
    rb.add_argument("job", type=Path)
    rb.add_argument("--name", required=True)

    rl = sub.add_parser("reel", help="talking head + B-roll -> finished reel + CapCut draft (no reference needed)")
    rl.add_argument("aroll", type=Path)
    rl.add_argument("broll", type=Path, nargs="*", help="B-roll clips in the order you want them used")
    rl.add_argument("--style", type=Path, default=ROOT / "styles/warm_intro.json")
    rl.add_argument("--script", type=Path, help="text file, one line per sentence (best takes + exact spelling)")
    rl.add_argument("--title", help="override title text (default: first sentence)")
    rl.add_argument("--words", type=Path, help="pre-made words.json (skip ASR)")
    rl.add_argument("--out", type=Path, help="job folder (default jobs/<aroll name>)")
    rl.add_argument("--capcut", help="also write a CapCut draft with this name")
    rl.add_argument("--lite", action="store_true",
                    help="no speech model (iPhone-only / offline): align --script to the audio by pauses; one clean take")
    rl.add_argument("--model", help='speech model name or folder; "cloud" = download from the GRIN GitHub release')
    rl.add_argument("--plan-only", action="store_true", help="only write spec.json (edit it, then `render`)")
    rl.add_argument("--quality", default="high", choices=["high", "prores"])

    rd = sub.add_parser("render", help="render a reel spec.json (after hand edits)")
    rd.add_argument("spec", type=Path)
    rd.add_argument("--out", type=Path)
    rd.add_argument("--capcut")
    rd.add_argument("--preview", action="store_true")

    lm = sub.add_parser("lut-from-ref", help="make a .cube that moves a video's colour toward a reference picture")
    lm.add_argument("source", type=Path, help="your video (or a frame from it)")
    lm.add_argument("reference", type=Path, help="screenshot / picture with the colour you want")
    lm.add_argument("--name", default="my_look")
    lm.add_argument("--strength", type=float, default=0.6)

    sz = sub.add_parser("safe-from-frame", help="read a safe-zone frame picture (white = safe) -> JSON for style['safe_zone']")
    sz.add_argument("frame", type=Path)

    lr = sub.add_parser("style-from-ref", help="learn a style from ONE finished reel (no source clips)")
    lr.add_argument("reference", type=Path)
    lr.add_argument("--name", required=True)
    lr.add_argument("--base", default="warm_intro")

    ic = sub.add_parser("icon", help="GRIN icon -> PNG sticker (any colour)")
    ic.add_argument("name"); ic.add_argument("--out", type=Path); ic.add_argument("--size", type=int, default=256)
    ic.add_argument("--color", default="#1E1E1D"); ic.add_argument("--bg"); ic.add_argument("--shape", default="circle")
    ic.add_argument("--label"); ic.add_argument("--stroke", type=float, default=1.75)
    sub.add_parser("icons", help="contact sheet of all GRIN icons -> library/icons/_sheet.png")
    sub.add_parser("presets", help="(re)build colour presets -> library/luts/presets")

    sv = sub.add_parser("serve")
    sv.add_argument("--host", default="0.0.0.0")
    sv.add_argument("--port", type=int, default=8765)

    a = ap.parse_args()
    if a.cmd == "run":
        from .pipeline import load_preset, run_job
        res = run_job(a.src, a.jobs / a.src.stem, load_preset(a.preset), a.library,
                      draft_name=a.name, draft_root=a.drafts, preview=not a.no_preview)
        print(res)
    elif a.cmd == "library":
        from .library import Library
        for asset in Library(a.library).assets:
            print(f"{asset.kind:9} {asset.id:40} tags={asset.tags} triggers={asset.triggers}")
    elif a.cmd == "rebuild":
        from .pipeline import rebuild_from_timeline
        print(rebuild_from_timeline(a.job, a.name))
    elif a.cmd == "reel":
        from .autoreel import run
        from .reel import capcut_reel, load_spec, render_reel
        out = a.out or ROOT / "jobs" / a.aroll.stem
        if a.model == "cloud":
            from .fetch_model import fetch
            a.model = str(fetch())
        spec_path = run(str(a.aroll), [str(b) for b in a.broll], str(a.style), str(out),
                        script=str(a.script) if a.script else None, title=a.title,
                        words_json=str(a.words) if a.words else None, lite=a.lite,
                        model=a.model)
        res = {"spec": str(spec_path)}
        if not a.plan_only:
            spec = load_spec(spec_path)
            res["video"] = str(render_reel(spec, out / "final.mp4", quality=a.quality))
            if a.capcut:
                res["capcut"] = str(capcut_reel(spec, a.capcut))
            s = json.loads(spec_path.read_text())
            res.update(duration=s["duration"], cuts=len(s["voice"]), broll=len(s["broll"]),
                       captions=len(s["captions"]))
        print(json.dumps(res, ensure_ascii=False))
    elif a.cmd == "render":
        from .reel import capcut_reel, load_spec, render_reel
        spec = load_spec(a.spec)
        out = a.out or a.spec.with_name("final.mp4")
        print(render_reel(spec, out, preview=a.preview))
        if a.capcut:
            print(capcut_reel(spec, a.capcut))
    elif a.cmd == "lut-from-ref":
        from .lutmatch import build
        out = build(a.source, a.reference, ROOT / "library/luts/my" / f"{a.name}.cube", strength=a.strength)
        print(json.dumps({"cube": str(out), "lut": f"luts/my/{a.name}"}))
    elif a.cmd == "safe-from-frame":
        from .safezone import from_frame
        print(json.dumps(from_frame(a.frame)))
    elif a.cmd == "style-from-ref":
        from .reflearn import learn
        print(json.dumps(learn(a.reference, a.name, a.base), ensure_ascii=False, indent=1))
    elif a.cmd == "icon":
        from .icons import render
        out = a.out or ROOT / "library/stickers/my" / f"icon_{a.name}.png"
        print(render(a.name, out, a.size, color=a.color, bg=a.bg, shape=a.shape, label=a.label, stroke=a.stroke))
    elif a.cmd == "icons":
        from .icons import export_svgs, sheet
        export_svgs(); print(sheet(ROOT / "library/icons/_sheet.png"))
    elif a.cmd == "presets":
        from .grade import build_presets
        print(len(build_presets()), "presets")
    elif a.cmd == "serve":
        import uvicorn
        uvicorn.run("autocut.server:app", host=a.host, port=a.port, workers=1)


if __name__ == "__main__":
    main()
