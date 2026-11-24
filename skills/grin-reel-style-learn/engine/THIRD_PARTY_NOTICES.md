# Third-party notices

GRIN Reels does not bundle the software below unless stated. The installer downloads it from its official
source; each item stays under its own license.

| Component | Use | License | Bundled? |
|---|---|---|---|
| ffmpeg (via Homebrew) | decode, render, encode | LGPL/GPL (build-dependent) | No: installed by `brew` |
| faster-whisper | local speech-to-text | MIT | No: installed by `pip` |
| Whisper model weights (OpenAI) | speech-to-text model | MIT | No: downloaded on first run |
| numpy, Pillow, fonttools, FastAPI, uvicorn | utilities, web UI | BSD / HPND / MIT | No: installed by `pip` |
| Montserrat (instanced Medium/SemiBold) | caption font | SIL OFL 1.1 (`library/fonts/OFL-Montserrat.txt`) | Yes |
| Oswald (Bold, Latin+Cyrillic merged) | title font | SIL OFL 1.1 (`library/fonts/OFL-Oswald.txt`) | Yes |
| pyCapCut | **optional**, experimental CapCut draft export | **No license published** | No: you install it yourself, at your own discretion |

Fonts under the OFL may be bundled and sold with software but may not be sold by themselves.

CapCut is a trademark of its owner. GRIN Reels is not affiliated with, endorsed by, or connected to CapCut
or ByteDance. CapCut draft files are an unofficial format and may stop working after a CapCut update.

## YuNet face detector — library/models/face_detection_yunet_2023mar.onnx
MIT License, Copyright (c) 2020 Shiqi Yu. From opencv/opencv_zoo. Full text: library/models/LICENSE-yunet.txt

## Whisper "small" speech model (downloaded at run time from github.com/ernoxq/grin-reels-models)
MIT License, Copyright (c) 2022 OpenAI; CTranslate2 conversion (c) 2023 SYSTRAN.

## Font library — library/fonts/<family>/ (SIL Open Font License 1.1, text in each folder's OFL.txt)
Comforter, Cormorant Garamond, Didact Gothic, Great Vibes, Inter, Jost, Lobster, Manrope, Marck Script, Montserrat,
Noto Serif Display, Old Standard TT, Orelega One, Playfair Display, Playfair Display SC, Podkova, Prata, PT Serif,
Roboto Condensed, Source Sans 3 — from github.com/google/fonts. Variable fonts were cut into static weights
(Regular…Black) for subtitle rendering; family names unchanged (no Reserved Font Name is used for a modified version).

## resvg-py — renders GRIN icons to PNG (MIT / Apache-2.0)

## GRIN icon set and colour presets — © 2026 Ernest Grin, part of GRIN Reels (see LICENSE.md)
