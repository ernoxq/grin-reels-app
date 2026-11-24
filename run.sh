#!/bin/bash
# GRIN Reels — © 2026 Ernest Grin. One quiet command for the chat skill.
# usage: bash run.sh FILES... [--all-talking | --talking a.MOV b.MOV] [--lang ro] [--script s.txt] [--title "..."] [--out jobs/x]
# Prints ONE json line at the end. Everything else goes to grin.log (read it only if something failed).
cd "$(dirname "$0")"
LOG="$PWD/grin.log"
{
  python3 -c "import faster_whisper, av, numpy, PIL, fontTools, cv2" 2>/dev/null || \
    pip install -q --break-system-packages numpy Pillow fonttools faster-whisper "av<16" opencv-python-headless
  command -v ffmpeg >/dev/null || (apt-get install -y -qq ffmpeg)
} >>"$LOG" 2>&1
python3 -m autocut auto "$@" 2>>"$LOG" | tail -1
