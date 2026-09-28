# Build the Carrom desktop app on Windows -> dist\Carrom.exe
#   powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

python -c "import tkinter" | Out-Null
python -m pip install --upgrade --quiet pyinstaller

Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
python -m PyInstaller --noconfirm --clean carrom.spec

Write-Host "Built dist\Carrom.exe"
