#!/usr/bin/env bash
# Губка Спанч / GRIN Reels — rebuild every skill's engine from the source and zip it for
# Claude → Customize → Skills → Upload a skill.   Usage: bash packaging/build_skills.sh
set -euo pipefail
cd "$(dirname "$0")/.."
S=skills

core() {  # python engine only
  rm -rf "$1"; mkdir -p "$1"
  cp -r autocut LICENSE.md THIRD_PARTY_NOTICES.md "$1"/
  find "$1" -name __pycache__ -prune -exec rm -rf {} +
}

full() {  # montage engine: styles, presets, LUTs, icons, 3 font families
  core "$1"
  cp -r styles presets web requirements.txt run.sh "$1"/
  tar --exclude='fonts/*/*' --exclude='luts/my/auto_*' --exclude='looks' --exclude='.index.json' -cf - library | tar -C "$1" -xf -
  for f in inter montserrat marckscript; do cp -r "library/fonts/$f" "$1/library/fonts/"; done
}

design() {  # designer engine: fonts of the presets + CapCut template
  core "$1"
  mkdir -p "$1/library/capcut" "$1/library/fonts"
  cp library/capcut/template_9x.json "$1/library/capcut/"
  for f in manrope montserrat inter jost robotocondensed sourcesans3 prata; do cp -r "library/fonts/$f" "$1/library/fonts/"; done
  mkdir -p "$1/library/fonts/playfairdisplay" "$1/library/fonts/cormorantgaramond"
  cp library/fonts/playfairdisplay/{OFL.txt,PlayfairDisplay-Regular.ttf,PlayfairDisplay-Bold.ttf,PlayfairDisplay-Italic.ttf} "$1/library/fonts/playfairdisplay/"
  cp library/fonts/cormorantgaramond/{OFL.txt,CormorantGaramond-Regular.ttf,CormorantGaramond-SemiBold.ttf,CormorantGaramond-Bold.ttf,CormorantGaramond-Italic.ttf} "$1/library/fonts/cormorantgaramond/"
}

full   $S/grin-reel-auto-edit/engine
full   $S/grin-reel-studio/engine
full   $S/gubka-spanch/engine
design $S/dizainer/engine
core   $S/antikrinzh/engine

cd $S
rm -f ./*.zip
for d in grin-reel-auto-edit grin-reel-studio gubka-spanch dizainer antikrinzh scenarist-hook-doctor; do
  zip -qr "$d.zip" "$d" -x '*.DS_Store' -x '*/__pycache__/*'
done
for d in */SKILL.md; do  # claude.ai rejects descriptions over 200 characters
  n=$(grep -m1 '^description:' "$d" | sed 's/^description: //' | python3 -c 'import sys; print(len(sys.stdin.read().strip()))')
  [ "$n" -le 200 ] || { echo "TOO LONG ($n): $d"; exit 1; }
done
ls -lh ./*.zip
