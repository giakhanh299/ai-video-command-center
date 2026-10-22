$ErrorActionPreference = 'Continue'
$project = Split-Path -Parent $MyInvocation.MyCommand.Path
$config = Join-Path $project 'cloudflare\tiktok-dubber.yml'
$logs = Join-Path $project 'logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null

# Dedicated config/tunnel. Never reads or changes ~/.cloudflared/config.yml (telegram-bot).
& cloudflared tunnel --config $config run tiktok-dubber 2>&1 |
  Tee-Object -FilePath (Join-Path $logs 'tunnel-tiktok-dubber.log') -Append
