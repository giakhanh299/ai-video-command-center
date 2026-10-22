# Create watchdog script for OpenClaw Gateway
code = """$port = 18789
$logFile = 'C:\\Users\\w\\.openclaw\\logs\\watchdog.log'
$timestamp = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')

function Write-Log($msg) {
    "$timestamp $msg" | Out-File -FilePath $logFile -Append -Encoding utf8
}

$conn = Test-NetConnection -ComputerName 127.0.0.1 -Port $port -WarningAction SilentlyContinue
if (-not $conn.TcpTestSucceeded) {
    Write-Log "[WATCHDOG] Port 18789 is DOWN. Restarting OpenClaw Gateway..."
    & 'C:\\Users\\w\\AppData\\Roaming\\npm\\openclaw.cmd' gateway restart 2>&1 | Out-File -FilePath $logFile -Append -Encoding utf8
    Start-Sleep -Seconds 3
    $recheck = Test-NetConnection -ComputerName 127.0.0.1 -Port $port -WarningAction SilentlyContinue
    if ($recheck.TcpTestSucceeded) {
        Write-Log "[WATCHDOG] OpenClaw Gateway restarted successfully."
    } else {
        Write-Log "[WATCHDOG] Warning: Port 18789 still not listening after restart."
    }
}
"""

with open(r'C:\Users\w\.openclaw\watchdog.ps1', 'w', encoding='utf-8') as f:
    f.write(code)

print("SUCCESS: C:\\Users\\w\\.openclaw\\watchdog.ps1 created successfully.")
