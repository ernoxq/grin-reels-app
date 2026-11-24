#!/bin/bash
# GRIN Reels — двойной клик, чтобы запустить (macOS). © 2026 Ernest Grin
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then echo "Сначала установи: открой Terminal и выполни  bash install.sh"; read -n 1; exit 1; fi
.venv/bin/python -m autocut.launch
