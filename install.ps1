# GRIN Reels installer for Windows 10/11 — © 2026 Ernest Grin (GRIN studio). See LICENSE.md.
# Run in PowerShell:  Set-ExecutionPolicy -Scope Process Bypass; .\install.ps1
# Status: BETA (not yet verified on real Windows machines). Renders with libx264 instead of Apple VideoToolbox.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
Write-Host "== GRIN Reels: installing to $PSScriptRoot"

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements }
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements }
Write-Host "If ffmpeg/python were just installed, close and reopen PowerShell, then run this script again."

python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt

# Fonts for the current user
$fontDir = "$env:LOCALAPPDATA\Microsoft\Windows\Fonts"; New-Item -ItemType Directory -Force $fontDir | Out-Null
Get-ChildItem library\fonts\*.ttf | ForEach-Object {
  Copy-Item $_.FullName $fontDir -Force
  New-ItemProperty -Path "HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Fonts" -Name $_.BaseName -Value "$fontDir\$($_.Name)" -PropertyType String -Force | Out-Null
}

# Speech model (once)
.\.venv\Scripts\python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8'); print('model ready')"

Write-Host ""
Write-Host "Done. Run:  .\.venv\Scripts\python -m autocut reel take.mp4 broll1.mp4 broll2.mp4"
Write-Host "Claude: Customize > Skills > + > Upload a skill > skills\grin-reel-auto-edit.zip"
