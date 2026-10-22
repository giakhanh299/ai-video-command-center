param(
    [ValidateSet('Prepare', 'API', 'Agent', 'Test')]
    [string]$Action = 'API'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv-command-center/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Create .venv-command-center and install requirements-command-center.txt first; see docs/COMMAND_CENTER_LOCAL.md.'
}
$commands = @{ Prepare = 'prepare'; API = 'serve'; Agent = 'agent'; Test = 'test' }
Push-Location -LiteralPath $projectRoot
try {
    & $pythonPath -B -m command_center.dev $commands[$Action]
    if ($LASTEXITCODE -ne 0) { throw 'Command Center action failed; see the safe error code above.' }
} finally {
    Pop-Location
}
