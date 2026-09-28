param(
    [ValidateSet('CPU', 'CUDA', 'DirectML')]
    [string]$Backend = 'CPU',
    [string]$TesseractDir = $env:TESSERACT_INSTALL_DIR
)
$ErrorActionPreference = 'Stop'
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo

if (-not (Test-Path '.venv')) { py -3.11 -m venv .venv }
$Python = Join-Path $Repo '.venv\Scripts\python.exe'
& $Python -m pip uninstall -y onnxruntime onnxruntime-gpu onnxruntime-directml
& $Python -m pip install --upgrade pip
& $Python -m pip install -r requirements.txt pyinstaller

# ONNX Runtime provider wheels install overlapping runtime modules; keep exactly one.
if ($Backend -ne 'CPU') {
    & $Python -m pip uninstall -y onnxruntime
    if ($Backend -eq 'CUDA') { & $Python -m pip install onnxruntime-gpu }
    if ($Backend -eq 'DirectML') { & $Python -m pip install onnxruntime-directml }
}

& $Python -m PyInstaller --noconfirm --clean --windowed --name SurvivorsBuddy `
    --paths src --collect-all onnxruntime --collect-all pytesseract `
    --hidden-import vgamepad --hidden-import win32gui `
    packaging/launcher.py

$Dist = Join-Path $Repo 'dist\SurvivorsBuddy'
if ($TesseractDir -and (Test-Path $TesseractDir)) {
    $TessDest = Join-Path $Dist 'resources\tesseract'
    New-Item -ItemType Directory -Force -Path $TessDest | Out-Null
    Copy-Item -Path (Join-Path $TesseractDir '*') -Destination $TessDest -Recurse -Force
} else {
    Write-Warning 'Tesseract was not bundled. Install Tesseract OCR separately and add it to PATH, or set TESSERACT_INSTALL_DIR and rebuild.'
}

@'
Survivors Buddy is an external single-player helper.
Prerequisites: Windows 10/11, ViGEmBus virtual gamepad driver, and (if not bundled) Tesseract OCR.
Launch SurvivorsBuddy.exe. Review the in-app safety prompt before starting.
'@ | Set-Content -Encoding UTF8 (Join-Path $Dist 'README-FIRST.txt')
$Zip = Join-Path $Repo 'dist\SurvivorsBuddy-Windows.zip'
if (Test-Path $Zip) { Remove-Item $Zip -Force }
Compress-Archive -Path (Join-Path $Dist '*') -DestinationPath $Zip
Write-Host "Build complete: $Dist"
Write-Host "Portable package: $Zip"
Write-Host "Distribute the whole folder/zip, not only SurvivorsBuddy.exe."
