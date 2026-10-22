$ErrorActionPreference = 'Continue'
$project = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $project 'backend'
$logs = Join-Path $project 'logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null

Set-Location -Path $backend
$env:PYTHONUNBUFFERED = "1"

while ($true) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path (Join-Path $logs 'backend-8005.log') -Value "[$timestamp] Khoi dong FastAPI Backend..."
    try {
        & python -m uvicorn main:app --host 127.0.0.1 --port 8005 2>&1 |
            Tee-Object -FilePath (Join-Path $logs 'backend-8005.log') -Append
    } catch {
        Add-Content -Path (Join-Path $logs 'backend-8005.log') -Value "[$timestamp] Backend gap su co: $_"
    }
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path (Join-Path $logs 'backend-8005.log') -Value "[$timestamp] Backend bi dung. Tu dong khoi dong lai sau 3 giay..."
    Start-Sleep -Seconds 3
}
