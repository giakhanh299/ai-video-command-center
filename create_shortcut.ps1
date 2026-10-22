$WshShell = New-Object -comObject WScript.Shell
$project = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $project) { $project = Get-Location }
$Shortcut = $WshShell.CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\TiktokDubber.lnk")
$Shortcut.TargetPath = "wscript.exe"
$Shortcut.Arguments = "`"$project\run_hidden.vbs`""
$Shortcut.WorkingDirectory = "$project"
$Shortcut.Save()
Write-Host "[OK] Created Startup shortcut for TikTokDubber pointing to $project\run_hidden.vbs"
