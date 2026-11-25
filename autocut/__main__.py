# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
# Licensed, not sold: see LICENSE.md. Redistribution or resale is prohibited.
"""CLI:
    python -m autocut run clip.mp4 --preset presets/talking_head.toml
    python -m autocut library                 # list what the asset library sees
    python -m autocut rebuild jobs/clip       # re-export after hand-editing timeline.json
    python -m autocut serve                   # mobile web UI on http://<mac>:8765
"""
from __future__ import annotations

from autocut.paths import app_root
import argparse
import json
from pathlib import Path

ROOT = app_root()


def fetch_model_path(m: str | None):
    if m in (None, "cloud"):
        from .fetch_model import fetch
        return fetch()
    return m


def _split(spec_path: Path, parts: list[dict]) -> None:
    from .prep import split_voice
    sp = json.loads(spec_path.read_text())
    if (spec_path.parent / "lang.txt").exists():
        sp["lang"] = (spec_path.parent / "lang.txt").read_text().strip()
    spec_path.write_text(json.dumps(split_voice(sp, parts), ensure_ascii=False, indent=1))


def _finish(job: Path, t0: float) -> dict:
    import time
    from .reel import load_spec, render_reel
    args = json.loads((job / "auto_args.json").read_text())
    spec_path = job / "spec.json"
    video = render_reel(load_spec(spec_path), job / "final.mp4")
    s = json.loads(spec_path.read_text())
    extra = {}
    if args.get("deliver") or args.get("export"):
        from .nle import export_all
        name = args.get("name") or time.strftime("Рилс %d.%m %H-%M")
        kinds = tuple(k.strip() for k in (args.get("export") or "").split(",") if k.strip()) or ("srt",)
        extra = export_all(spec_path, Path(args["deliver"]) if args.get("deliver") else job, name, video,
                           Path(args["capcut_root"]) if args.get("capcut_root") else None, args.get("map"), kinds)
    return {**extra, "video": extra.get("video") or str(Path(video).resolve()), "sec": round(s["duration"], 1),
            "parts": [Path(x).name for x in args.get("parts", [])], "inserts": len(s["broll"]),
            "lang": s.get("lang"), "took_s": round(time.time() - t0)}


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
    rl.add_argument("--lang", help="speech language (ro, ru, en...); default: detect automatically")

    fe = sub.add_parser("fetch", help="download reels by link (Instagram, TikTok, YouTube) into a folder")
    fe.add_argument("urls", nargs="+")
    fe.add_argument("--out", type=Path, default=Path("refs"))

    fi = sub.add_parser("finish", help="render a planned job (after the storyboard was approved) + export")
    fi.add_argument("job", type=Path)

    ex = sub.add_parser("export", help="spec.json -> CapCut draft / FCPXML / SRT in the person's folders")
    ex.add_argument("spec", type=Path)
    ex.add_argument("--deliver", type=Path, required=True)
    ex.add_argument("--name", required=True)
    ex.add_argument("--video", type=Path)
    ex.add_argument("--export", default="capcut,fcpxml,srt")
    ex.add_argument("--capcut-root", type=Path)
    ex.add_argument("--map", nargs="*", default=[])

    au = sub.add_parser("auto", help="ALL files from the chat -> one finished reel (joins every talking part)")
    au.add_argument("files", type=Path, nargs="+")
    au.add_argument("--talking", nargs="*", help="names of the clips where the person talks (default: detect)")
    au.add_argument("--style", type=Path, default=ROOT / "styles/natural.json")
    au.add_argument("--script", type=Path)
    au.add_argument("--title")
    au.add_argument("--lang")
    au.add_argument("--model", default="cloud")
    au.add_argument("--out", type=Path)
    au.add_argument("--all-talking", action="store_true", help="every video is a part of the talk, join them all")
    au.add_argument("--deliver", type=Path, help="folder for the results (the «Готовое» folder)")
    au.add_argument("--name", help="name of the reel / project (default: Рилс <date time>)")
    au.add_argument("--export", default="", help="comma list: capcut,fcpxml,srt (editable projects)")
    au.add_argument("--capcut-root", type=Path, help="CapCut drafts folder …/com.lveditor.draft as seen here")
    au.add_argument("--map", nargs="*", default=[], help="THIS_SHELL_PATH=REAL_COMPUTER_PATH for paths inside projects")
    au.add_argument("--plan", action="store_true", help="storyboard only: print the plan, render later with `finish`")
    au.add_argument("--drop", nargs="*", default=[], help="phrases whose sentences must be cut (kept between re-plans)")
    au.add_argument("--keep", nargs="*", default=[], help="undo an earlier --drop")
    au.add_argument("--fix", nargs="*", default=[], help='wrongly recognised words: "wrong=right" (kept between re-plans)')
    au.add_argument("--no-inserts", action="store_true", help="talking parts only, no B-roll")

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

    lr = sub.add_parser("style-from-ref", help="learn a style from 1-5 finished reels (no source clips)")
    lr.add_argument("reference", type=Path, nargs="+")
    lr.add_argument("--name", required=True)
    lr.add_argument("--base", default="natural")
    lr.add_argument("--colour", action="store_true", help="also copy the colour (only when the person asks for it)")

    ic = sub.add_parser("icon", help="GRIN icon -> PNG sticker (any colour)")
    ic.add_argument("name"); ic.add_argument("--out", type=Path); ic.add_argument("--size", type=int, default=256)
    ic.add_argument("--color", default="#1E1E1D"); ic.add_argument("--bg"); ic.add_argument("--shape", default="circle")
    ic.add_argument("--label"); ic.add_argument("--stroke", type=float, default=1.75)
    sub.add_parser("icons", help="contact sheet of all GRIN icons -> library/icons/_sheet.png")
    pl = sub.add_parser("place", help="put a photo/video/icon on top at the given words, then re-render")
    pl.add_argument("spec"); pl.add_argument("file", nargs="?")
    pl.add_argument("--words"); pl.add_argument("--at", type=float); pl.add_argument("--dur", type=float)
    pl.add_argument("--how", default="full", choices=["full", "window", "sticker"]); pl.add_argument("--pos")
    pl.add_argument("--width", type=float); pl.add_argument("--icon"); pl.add_argument("--color", default="#FFFFFF")
    pl.add_argument("--bg", default="#1E1E1D"); pl.add_argument("--label")
    pl.add_argument("--anim", default="pop", choices=["pop", "fade", "slide", "none"])
    pl.add_argument("--motion", choices=["headline", "plate", "number", "step", "checklist"],
                    help="animated text: headline (*marked words*), plate, number (counts up), step, checklist (a|b|c)")
    pl.add_argument("--text"); pl.add_argument("--sub"); pl.add_argument("--n", default="01")
    pl.add_argument("--accent", default="#E4F23C"); pl.add_argument("--font")
    pk = sub.add_parser("pick", help="sort dropped files: talking video vs inserts")
    pk.add_argument("files", nargs="+")
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
                        model=a.model, language=a.lang)
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
    elif a.cmd == "export":
        from .nle import export_all
        print(json.dumps(export_all(a.spec, a.deliver, a.name, a.video, a.capcut_root, a.map,
                                    tuple(k.strip() for k in a.export.split(","))), ensure_ascii=False))
    elif a.cmd == "auto":
        import time
        from .autoreel import run
        from .prep import join, sort_files
        from .reel import load_spec, render_reel
        t0 = time.time()
        srt = sort_files([str(f) for f in a.files], a.talking, a.all_talking)
        if not srt["story"]:
            print(json.dumps({"error": "нет видео, где человек говорит"}, ensure_ascii=False)); raise SystemExit(1)
        if not a.out:
            a.out = ROOT / "jobs" / time.strftime("reel_%H%M%S")
        a.out = a.out.resolve()
        a.out.mkdir(parents=True, exist_ok=True)
        sp_f = a.out / "story_parts.json"
        if sp_f.exists() and [x["file"] for x in json.loads(sp_f.read_text())] != [str(Path(x).resolve()) for x in srt["story"]]:
            for f in ("story.wav", "story_parts.json", "words.json", "words_edit.json", "auto_args.json", "lang.txt"):
                (a.out / f).unlink(missing_ok=True)  # other files than last time: start this job fresh
        from .prep import join_audio, split_voice
        audio, parts = join_audio(srt["story"], a.out / "story.wav")  # sound only: seconds, not minutes
        if not (a.out / "words.json").exists():
            from .transcribe import transcribe
            transcribe(str(audio), a.out / "words.json", str(fetch_model_path(a.model)), a.lang)
        main = srt["story"][0]  # first clip = picture reference (size, colour); speech comes from words.json
        model = a.model
        if model == "cloud":
            from .fetch_model import fetch
            model = str(fetch())
        prev0 = json.loads((a.out / "auto_args.json").read_text()) if (a.out / "auto_args.json").exists() else {}
        a.title = a.title or prev0.get("title")  # a re-plan keeps everything said before unless changed now
        a.deliver = a.deliver or (Path(prev0["deliver"]) if prev0.get("deliver") else None)
        a.name = a.name or prev0.get("name")
        a.export = a.export or prev0.get("export") or ""
        a.capcut_root = a.capcut_root or (Path(prev0["capcut_root"]) if prev0.get("capcut_root") else None)
        a.map = a.map or prev0.get("map") or []
        a.lang = a.lang or prev0.get("lang")
        args = dict(inserts=[] if a.no_inserts else srt["inserts"], style=str(a.style),
                    script=str(a.script) if a.script else None, title=a.title, model=model, lang=a.lang,
                    deliver=str(a.deliver) if a.deliver else None, name=a.name, export=a.export,
                    capcut_root=str(a.capcut_root) if a.capcut_root else None, map=a.map, parts=srt["story"])
        spec_path = run(str(main), args["inserts"], args["style"], str(a.out), script=args["script"],
                        title=a.title, words_json=str(a.out / "words.json"), language=a.lang)
        _split(spec_path, parts)
        prev = json.loads((a.out / "auto_args.json").read_text()) if (a.out / "auto_args.json").exists() else {}
        drops = [d for d in prev.get("drop", []) if d not in a.keep] + [d for d in a.drop if d not in prev.get("drop", [])]
        args["drop"] = drops
        fixes = [f for f in prev.get("fix", []) if f.split("=")[0] not in {x.split("=")[0] for x in a.fix}] + a.fix
        args["fix"] = fixes
        if drops or fixes:
            a.drop = drops
            from .storyboard import drop_phrases, fix_words
            w = json.loads((a.out / "words.json").read_text())
            (a.out / "words_edit.json").write_text(json.dumps(drop_phrases(fix_words(w, fixes), a.drop),
                                                              ensure_ascii=False))
            spec_path = run(str(main), args["inserts"], args["style"], str(a.out), script=args["script"],
                            title=a.title, words_json=str(a.out / "words_edit.json"), language=a.lang)
            _split(spec_path, parts)
        (a.out / "auto_args.json").write_text(json.dumps(args, ensure_ascii=False))
        if a.plan:
            from .storyboard import plan_text
            txt = plan_text(a.out)
            (a.out / "plan.txt").write_text(txt)
            print(txt + f"\nJOB: {a.out}")
            return
        print(json.dumps(_finish(a.out, t0), ensure_ascii=False))
    elif a.cmd == "fetch":
        from .fetch import fetch_urls
        print(json.dumps(fetch_urls(a.urls, a.out), ensure_ascii=False))
    elif a.cmd == "finish":
        import time
        print(json.dumps(_finish(a.job.resolve(), time.time()), ensure_ascii=False))
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
        print(json.dumps(learn(a.reference, a.name, a.base, a.colour), ensure_ascii=False))
    elif a.cmd == "icon":
        from .icons import render
        out = a.out or ROOT / "library/stickers/my" / f"icon_{a.name}.png"
        print(render(a.name, out, a.size, color=a.color, bg=a.bg, shape=a.shape, label=a.label, stroke=a.stroke))
    elif a.cmd == "icons":
        from .icons import export_svgs, sheet
        export_svgs(); print(sheet(ROOT / "library/icons/_sheet.png"))
    elif a.cmd == "place":
        from .place import place
        if a.motion:
            from .motion import render as motion_render
            from .place import find_words
            spec = json.loads(Path(a.spec).read_text())
            t0, t1 = find_words(spec, a.words) if a.words else (a.at or 0.0, (a.at or 0.0) + 2)
            d = a.dur or max(2.0, min(3.5, t1 - t0 + 1.0))
            n = len(spec.get("overlays", []) or [])
            clip = motion_render(a.motion, a.text or a.words or "", Path(a.spec).parent / "motion" / f"m{n}_{a.motion}.mov",
                                 d, a.accent, sub=a.sub, label=a.label, n=a.n, font=a.font)
            print(json.dumps(place(a.spec, str(clip), a.words, a.at, "window", d, a.pos or "center", 1.0, None,
                                   anim="none"), ensure_ascii=False))
        else:
            print(json.dumps(place(a.spec, a.file, a.words, a.at, a.how, a.dur, a.pos, a.width, a.icon, a.color,
                                   a.bg, a.label, a.anim), ensure_ascii=False))
    elif a.cmd == "pick":
        from .pick import pick
        print(json.dumps(pick(a.files), ensure_ascii=False))
    elif a.cmd == "presets":
        from .grade import build_presets
        print(len(build_presets()), "presets")
    elif a.cmd == "serve":
        import uvicorn
        uvicorn.run("autocut.server:app", host=a.host, port=a.port, workers=1)


if __name__ == "__main__":
    import sys
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # one short line for Claude; the traceback goes to the log (stderr)
        import traceback
        traceback.print_exc()
        msg = str(e)
        hint = ("не хватило памяти - пришли видео короче или в 1080p" if isinstance(e, MemoryError)
                else "файл не читается - пришли его ещё раз или в другом формате" if "Invalid data" in msg
                or "moov atom" in msg else "ошибка движка - подробности в grin.log")
        print(json.dumps({"error": type(e).__name__, "hint": hint}, ensure_ascii=False))
        sys.exit(1)
