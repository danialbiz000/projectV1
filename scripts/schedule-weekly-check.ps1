# Registers a weekly Windows scheduled task that runs the Nexus agents' check:
#   claude -p "/nexus-check"   (in this project folder)
# Usage (PowerShell, from the project folder):
#   powershell -ExecutionPolicy Bypass -File scripts\schedule-weekly-check.ps1
# Remove:  Unregister-ScheduledTask -TaskName "Nexus weekly check" -Confirm:$false

$ErrorActionPreference = "Stop"
$project = Split-Path -Parent $PSScriptRoot
$claude = (Get-Command claude -ErrorAction SilentlyContinue).Source
if (-not $claude) { throw "Claude Code ('claude') not found on PATH. Install it first." }

$logDir = Join-Path $project "reports"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$cmd = "Set-Location '$project'; & '$claude' -p '/nexus-check' *>> '$logDir\weekly-check.log'"

$action  = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -WindowStyle Hidden -Command `"$cmd`""
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Saturday -At 9:17am
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries

Register-ScheduledTask -TaskName "Nexus weekly check" -Action $action -Trigger $trigger -Settings $settings `
  -Description "Runs the Nexus agents (paper-monitor, backtest-analyst, risk-guardian) every Saturday." -Force | Out-Null
Write-Host "Scheduled: every Saturday at 09:17 -> reports\weekly-<date>.md (log: reports\weekly-check.log)"
