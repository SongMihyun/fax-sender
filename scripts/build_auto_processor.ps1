param(
    [string]$Python = ".venv\\Scripts\\python.exe"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

& $Python -m pip install pyinstaller
& $Python .\scripts\generate_faxsender_icon.py
& $Python -m PyInstaller --noconfirm --clean --onedir --windowed `
    --name FaxSenderAutoProcessor `
    --icon "auto_processor\assets\faxsender.ico" `
    --paths $root `
    --add-data "backend;backend" `
    --add-data "pdf-overlay-engine;pdf-overlay-engine" `
    --add-data "shared;shared" `
    --add-data "tools;tools" `
    --add-data "auto_processor\resources;auto_processor\resources" `
    --add-data "C:\Program Files\Tesseract-OCR;Tesseract-OCR" `
    auto_processor\app.py

Write-Host "Built application: $root\dist\FaxSenderAutoProcessor\FaxSenderAutoProcessor.exe"
