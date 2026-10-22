$ErrorActionPreference = 'Continue'
$project = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -Path $project
python -u run_bot.py
