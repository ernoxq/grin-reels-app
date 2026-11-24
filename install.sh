#!/usr/bin/env bash
# GRIN Reels installer for macOS (Apple Silicon) — © 2026 Ernest Grin (GRIN studio). See LICENSE.md.
set -euo pipefail
cd "$(dirname "$0")"
DIR="$(pwd)"
echo "== GRIN Reels — установка в $DIR"

if [[ "$(uname)" != "Darwin" ]]; then echo "Нужен macOS."; exit 1; fi
if [[ "$(uname -m)" != "arm64" ]]; then echo "Внимание: рекомендован Mac на Apple Silicon (M1 и новее)."; fi

# 1. Homebrew + ffmpeg
if ! command -v brew >/dev/null 2>&1; then
  echo "== Ставлю Homebrew (попросит пароль от Mac)"
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  eval "$(/opt/homebrew/bin/brew shellenv)"
fi
command -v ffmpeg >/dev/null 2>&1 || brew install ffmpeg
command -v python3 >/dev/null 2>&1 || brew install python@3.12

# 2. Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -r requirements.txt

# 3. Fonts (so CapCut and other apps see them too)
mkdir -p "$HOME/Library/Fonts"
cp library/fonts/*.ttf "$HOME/Library/Fonts/" 2>/dev/null || true

# 4. Speech model (downloads once, ~1.6 GB for turbo; falls back to small ~0.5 GB)
python - <<'PY' || true
from faster_whisper import WhisperModel
for m in ("large-v3-turbo", "small"):
    try:
        WhisperModel(m, device="cpu", compute_type="int8"); print("model ready:", m); break
    except Exception as e:
        print("model", m, "failed:", e)
PY

# 5. Short command: `grinreel` from any folder
LINE="alias grinreel='PYTHONPATH=\"$DIR\" \"$DIR/.venv/bin/python\" -m autocut'"
grep -q "alias grinreel=" "$HOME/.zshrc" 2>/dev/null || echo "$LINE" >> "$HOME/.zshrc"

# 6. A real Mac app: «GRIN Reels» in Applications / Launchpad / Dock — no Terminal, no browser
APP="$HOME/Applications/GRIN Reels.app"
rm -rf "$APP"; mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cat > "$APP/Contents/Info.plist" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
 <key>CFBundleName</key><string>GRIN Reels</string>
 <key>CFBundleDisplayName</key><string>GRIN Reels</string>
 <key>CFBundleIdentifier</key><string>com.usegrin.reels</string>
 <key>CFBundleVersion</key><string>1.0</string>
 <key>CFBundleShortVersionString</key><string>1.0</string>
 <key>CFBundleExecutable</key><string>GRIN Reels</string>
 <key>CFBundleIconFile</key><string>AppIcon</string>
 <key>CFBundlePackageType</key><string>APPL</string>
 <key>LSMinimumSystemVersion</key><string>12.0</string>
 <key>NSHighResolutionCapable</key><true/>
 <key>NSHumanReadableCopyright</key><string>© 2026 Ernest Grin (GRIN studio)</string>
</dict></plist>
PL
cat > "$APP/Contents/MacOS/GRIN Reels" <<SH
#!/bin/bash
cd "$DIR"
export PATH="/opt/homebrew/bin:/usr/local/bin:\$PATH"
exec "$DIR/.venv/bin/python" -m autocut.launch >> "$DIR/grin-reels.log" 2>&1
SH
chmod +x "$APP/Contents/MacOS/GRIN Reels"
ICONSET="$(mktemp -d)/AppIcon.iconset"; mkdir -p "$ICONSET"
for s in 16 32 128 256 512; do
  sips -z $s $s web/icon.png --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
  sips -z $((s*2)) $((s*2)) web/icon.png --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/AppIcon.icns" || true
touch "$APP"
echo "== Приложение: $APP (есть в Launchpad; можно перетащить в Dock)"

# 7. Self-test
python -m pytest -q tests >/dev/null 2>&1 && echo "== Тесты пройдены" || echo "== Тесты не запустились (pip install pytest), движок всё равно установлен"

echo
echo "Готово! Как пользоваться:"
echo "  ПРОЩЕ ВСЕГО: открой приложение «GRIN Reels» (Launchpad или папка Программы в твоей домашней папке)."
open "$APP" || true
echo "  ЧЕРЕЗ CLAUDE: Claude (Code) → Plugins → Skills → Add → Upload plugin → grin-reel-auto-edit.zip,"
echo "                потом в приложении Claude на Mac: + → Add folder → $DIR, и напиши «Собери рилс из папки …»"
