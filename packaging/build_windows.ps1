param(
    [ValidateSet('CPU', 'CUDA', 'DirectML')]
    [string]$Backend = 'DirectML',
    [string]$TesseractDir = $env:TESSERACT_INSTALL_DIR
)
$ErrorActionPreference = 'Stop'
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo

function Invoke-PythonChecked {
    param([string[]]$Arguments)
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Python command failed ($LASTEXITCODE): $Arguments" }
}

if (-not (Test-Path '.venv')) {
    Write-Host '[1/6] Creating Python 3.11 environment'
    py -3.11 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python 3.11 virtual environment.' }
}
$Python = Join-Path $Repo '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { throw "Expected Python executable not found: $Python" }

Write-Host '[2/6] Installing clean build dependencies'
Invoke-PythonChecked @('-m', 'pip', 'uninstall', '-y', 'onnxruntime', 'onnxruntime-gpu', 'onnxruntime-directml')
Invoke-PythonChecked @('-m', 'pip', 'install', '--upgrade', 'pip')
Invoke-PythonChecked @('-m', 'pip', 'install', '-r', 'requirements.txt', 'pyinstaller')

# Provider packages overlap; install exactly one runtime implementation.
if ($Backend -ne 'CPU') {
    Write-Host "[3/6] Selecting ONNX Runtime provider: $Backend"
    Invoke-PythonChecked @('-m', 'pip', 'uninstall', '-y', 'onnxruntime')
    if ($Backend -eq 'CUDA') { Invoke-PythonChecked @('-m', 'pip', 'install', 'onnxruntime-gpu') }
    if ($Backend -eq 'DirectML') { Invoke-PythonChecked @('-m', 'pip', 'install', 'onnxruntime-directml') }
}

Write-Host '[4/6] Packaging the desktop app with PyInstaller'
Invoke-PythonChecked @('-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed', '--name', 'SurvivorsBuddy', '--paths', 'src', '--collect-all', 'onnxruntime', '--collect-all', 'pytesseract', '--hidden-import', 'vgamepad', '--hidden-import', 'win32gui', 'packaging/launcher.py')

$Dist = Join-Path $Repo 'dist\SurvivorsBuddy'
if (-not (Test-Path (Join-Path $Dist 'SurvivorsBuddy.exe'))) {
    throw 'PyInstaller finished without creating SurvivorsBuddy.exe.'
}

Write-Host '[5/6] Adding OCR resources and portable instructions'
if ($TesseractDir -and (Test-Path (Join-Path $TesseractDir 'tesseract.exe'))) {
    $TessDest = Join-Path $Dist 'resources\tesseract'
    New-Item -ItemType Directory -Force -Path $TessDest | Out-Null
    Copy-Item -Path (Join-Path $TesseractDir '*') -Destination $TessDest -Recurse -Force
} else {
    Write-Warning 'Tesseract was not bundled. Install Tesseract OCR separately and add it to PATH, or set TESSERACT_INSTALL_DIR and rebuild.'
}

@'
Survivors Buddy is an external single-player helper.
Prerequisites: Windows 10/11 and ViGEmBus virtual gamepad driver. If OCR is not bundled, install Tesseract and add it to PATH.
Launch SurvivorsBuddy.exe. Review the in-app safety prompt before starting.
'@ | Set-Content -Encoding UTF8 (Join-Path $Dist 'README-FIRST.txt')

Write-Host '[6/6] Compressing the portable folder'
$Zip = Join-Path $Repo 'dist\SurvivorsBuddy-Windows.zip'
if (Test-Path $Zip) { Remove-Item $Zip -Force }
Compress-Archive -Path (Join-Path $Dist '*') -DestinationPath $Zip -CompressionLevel Fastest
if (-not (Test-Path $Zip)) { throw 'Portable ZIP was not created.' }
Write-Host "Build complete: $Dist"
Write-Host "Portable package: $Zip ($([math]::Round((Get-Item $Zip).Length / 1MB, 1)) MB)"
Write-Host 'Distribute the whole folder/zip, not only the .exe.'
