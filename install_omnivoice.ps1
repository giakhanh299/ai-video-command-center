$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "[1/2] Cai/Cap nhat dependencies cua project..." -ForegroundColor Cyan
python -m pip install -r requirements.txt

Write-Host "[2/2] Cai OmniVoice tu source local..." -ForegroundColor Cyan
python -m pip install -e .\OmniVoice

Write-Host "Hoan tat. Model k2-fsa/OmniVoice se duoc tai/cache o lan chay dau neu chua co." -ForegroundColor Green
