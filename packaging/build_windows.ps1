param(
    [ValidateSet('CPU', 'CUDA', 'DirectML')]
    [string]$Backend = 'DirectML',
    [ValidateSet('All', 'Install', 'Desktop', 'Runtime', 'Package', 'Archive')]
    [string]$Stage = 'All',
    [string]$TesseractDir = $env:TESSERACT_INSTALL_DIR,
    [switch]$UseRunnerPython
)
$ErrorActionPreference = 'Stop'
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo
$VenvPython = Join-Path $Repo '.venv\Scripts\python.exe'

function Invoke-PythonChecked {
    param([string[]]$Arguments)
    if ($UseRunnerPython) { & py -3.11 @Arguments }
    else { & $VenvPython @Arguments }
    if ($LASTEXITCODE -ne 0) { throw "Python command failed ($LASTEXITCODE): $($Arguments -join ' ')" }
}

if ($UseRunnerPython -and $Stage -eq 'Desktop') {
    Write-Host 'Installing Windows UI and packaging tools'
    Invoke-PythonChecked @('-m', 'pip', 'install', '--prefer-binary', 'PySide6-Essentials', 'pywin32', 'pyinstaller')
    Write-Host 'Installing vgamepad bindings without starting its privileged MSI driver prompt'
    Invoke-PythonChecked @('packaging/install_vgamepad.py')
}

if ($UseRunnerPython -and $Stage -eq 'Runtime') {
    Write-Host "Installing the $Backend inference runtime"
    Invoke-PythonChecked @('-m', 'pip', 'uninstall', '-y', 'onnxruntime', 'onnxruntime-gpu', 'onnxruntime-directml')
    if ($Backend -eq 'CPU') { Invoke-PythonChecked @('-m', 'pip', 'install', '--prefer-binary', 'onnxruntime') }
    if ($Backend -eq 'CUDA') { Invoke-PythonChecked @('-m', 'pip', 'install', '--prefer-binary', 'onnxruntime-gpu') }
    if ($Backend -eq 'DirectML') { Invoke-PythonChecked @('-m', 'pip', 'install', '--prefer-binary', 'onnxruntime-directml') }
}

if ($Stage -in @('All', 'Install')) {
    if ($UseRunnerPython) {
        # CI already installed and tested the core requirements in its base Python.
        # Reuse those packages rather than redownloading them into a second venv.
        Write-Host "Installing only the Windows packaging extras and $Backend runtime into runner Python"
        Invoke-PythonChecked @('-m', 'pip', 'uninstall', '-y', 'onnxruntime', 'onnxruntime-gpu', 'onnxruntime-directml')
        $BuildPackages = @('PySide6-Essentials', 'vgamepad', 'pywin32', 'pyinstaller')
        if ($Backend -eq 'CPU') { $BuildPackages += 'onnxruntime' }
        if ($Backend -eq 'CUDA') { $BuildPackages += 'onnxruntime-gpu' }
        if ($Backend -eq 'DirectML') { $BuildPackages += 'onnxruntime-directml' }
        Invoke-PythonChecked (@('-m', 'pip', 'install', '--prefer-binary') + $BuildPackages)
    } else {
        if (-not (Test-Path '.venv')) {
            Write-Host 'Creating Python 3.11 virtual environment'
            py -3.11 -m venv .venv
            if ($LASTEXITCODE -ne 0) { throw 'Could not create Python 3.11 virtual environment.' }
        }
        if (-not (Test-Path $VenvPython)) { throw "Python executable not found: $VenvPython" }
        Write-Host "Installing $Backend build dependencies"
        Invoke-PythonChecked @('-m', 'pip', 'uninstall', '-y', 'onnxruntime', 'onnxruntime-gpu', 'onnxruntime-directml')
        Invoke-PythonChecked @('-m', 'pip', 'install', '--upgrade', 'pip')
        Invoke-PythonChecked @('-m', 'pip', 'install', '-r', 'requirements.txt', 'pyinstaller')
        Invoke-PythonChecked @('packaging/install_vgamepad.py')
        if ($Backend -ne 'CPU') {
            Invoke-PythonChecked @('-m', 'pip', 'uninstall', '-y', 'onnxruntime')
            if ($Backend -eq 'CUDA') { Invoke-PythonChecked @('-m', 'pip', 'install', 'onnxruntime-gpu') }
            if ($Backend -eq 'DirectML') { Invoke-PythonChecked @('-m', 'pip', 'install', 'onnxruntime-directml') }
        }
    }
    Write-Host 'Dependencies installed.'
}

if ($Stage -in @('All', 'Package')) {
    if (-not $UseRunnerPython -and -not (Test-Path $VenvPython)) { throw 'Run Stage=Install before Stage=Package.' }
    Write-Host 'Running PyInstaller; this can take several minutes on a fresh runner.'
    Invoke-PythonChecked @('-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed', '--name', 'SurvivorsBuddy', '--paths', 'src', '--collect-all', 'onnxruntime', '--collect-all', 'pytesseract', '--hidden-import', 'vgamepad', '--hidden-import', 'win32gui', 'packaging/launcher.py')
    if (-not (Test-Path (Join-Path $Repo 'dist\SurvivorsBuddy\SurvivorsBuddy.exe'))) {
        throw 'PyInstaller finished without creating SurvivorsBuddy.exe.'
    }
    Write-Host 'PyInstaller executable created.'
}

if ($Stage -in @('All', 'Archive')) {
    $Dist = Join-Path $Repo 'dist\SurvivorsBuddy'
    if (-not (Test-Path (Join-Path $Dist 'SurvivorsBuddy.exe'))) { throw 'Run Stage=Package before Stage=Archive.' }
    Write-Host 'Adding OCR files and portable instructions.'
    if ($TesseractDir -and (Test-Path (Join-Path $TesseractDir 'tesseract.exe'))) {
        $TessDest = Join-Path $Dist 'resources\tesseract'
        New-Item -ItemType Directory -Force -Path $TessDest | Out-Null
        Copy-Item -Path (Join-Path $TesseractDir '*') -Destination $TessDest -Recurse -Force
    } else {
        Write-Warning 'Tesseract was not bundled. Install Tesseract OCR separately and add it to PATH.'
    }
    @'
Survivors Buddy is an external single-player helper.
Prerequisites: Windows 10/11 and ViGEmBus virtual gamepad driver. If OCR is not bundled, install Tesseract and add it to PATH.
Launch SurvivorsBuddy.exe. Review the in-app safety prompt before starting.
'@ | Set-Content -Encoding UTF8 (Join-Path $Dist 'README-FIRST.txt')
    $Zip = Join-Path $Repo 'dist\SurvivorsBuddy-Windows.zip'
    if (Test-Path $Zip) { Remove-Item $Zip -Force }
    Compress-Archive -Path (Join-Path $Dist '*') -DestinationPath $Zip -CompressionLevel Fastest
    if (-not (Test-Path $Zip)) { throw 'Portable ZIP was not created.' }
    Write-Host "Portable package created: $Zip ($([math]::Round((Get-Item $Zip).Length / 1MB, 1)) MB)"
}
