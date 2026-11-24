#!/usr/bin/env bash
# Build GRIN Reels.app + GRIN-Reels.dmg on an Apple Silicon Mac (or the GitHub macOS runner).
# © 2026 Ernest Grin (GRIN studio)
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .buildvenv && source .buildvenv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt pyinstaller

# ffmpeg + ffprobe (static, arm64, with libass/freetype) inside the app
mkdir -p build/bin
for t in ffmpeg ffprobe; do
  curl -sSL -o "build/$t.zip" "https://ffmpeg.martin-riedl.de/redirect/latest/macos/arm64/release/$t.zip"
  unzip -o -q "build/$t.zip" -d build/bin
done
chmod +x build/bin/ffmpeg build/bin/ffprobe
build/bin/ffmpeg -hide_banner -filters | grep -q " subtitles " || { echo "ffmpeg without libass"; exit 1; }

# icon
ICONSET=build/AppIcon.iconset; mkdir -p $ICONSET
for s in 16 32 128 256 512; do
  sips -z $s $s web/icon.png --out $ICONSET/icon_${s}x${s}.png >/dev/null
  sips -z $((s*2)) $((s*2)) web/icon.png --out $ICONSET/icon_${s}x${s}@2x.png >/dev/null
done
iconutil -c icns $ICONSET -o build/AppIcon.icns

pyinstaller --noconfirm --clean --windowed --name "GRIN Reels" \
  --icon build/AppIcon.icns --osx-bundle-identifier com.usegrin.reels \
  --add-data "web:web" --add-data "library:library" --add-data "styles:styles" --add-data "presets:presets" \
  --add-binary "build/bin/ffmpeg:bin" --add-binary "build/bin/ffprobe:bin" \
  --collect-all faster_whisper --collect-all ctranslate2 --collect-all webview --collect-all resvg_py \
  --collect-submodules autocut --collect-submodules uvicorn --hidden-import autocut.server \
  packaging/app_main.py

APP="dist/GRIN Reels.app"
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString ${GRIN_VERSION:-1.0}" "$APP/Contents/Info.plist" || true
/usr/libexec/PlistBuddy -c "Add :NSHumanReadableCopyright string © 2026 Ernest Grin (GRIN studio)" "$APP/Contents/Info.plist" || true
codesign --force --deep --sign - "$APP"   # ad-hoc signature (no Apple Developer account yet)

"$APP/Contents/MacOS/GRIN Reels" --selftest

# DMG: drag GRIN Reels to Applications
rm -rf build/dmg && mkdir -p build/dmg && cp -R "$APP" build/dmg/ && ln -s /Applications build/dmg/Applications
hdiutil create -volname "GRIN Reels" -srcfolder build/dmg -ov -format UDZO dist/GRIN-Reels.dmg
ls -la dist
