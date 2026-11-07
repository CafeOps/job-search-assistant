# Registers a Windows scheduled task that runs the scan every day. Works in Windows PowerShell 5.1.
# Usage (from the kit folder):  powershell -ExecutionPolicy Bypass -File scanner\install-task.ps1 -Time 07:00
#   -Mail smtp|claude|codex|none   mail method; omit it to use config email.mode, else smtp. claude and codex
#                             need a mail connector already set up in that app. none = digest file only.
#                             See the run.ps1 header for details.
#   -Python <path>            use this python.exe instead of detecting one
#   -DataDir <path>           the user's data folder (default: JOBHUNT_DATA_DIR, then the saved choice from
#                             tools\setup_check.py --data-dir). Its absolute path is baked into the task.
#   -RunNow                   also run the scan once right after registering (it sends a REAL email)
#   -Uninstall                remove the task
param(
  [string]$Time = '07:00',
  [ValidateSet('', 'smtp', 'claude', 'codex', 'none')][string]$Mail = '',
  [string]$Python = '',
  [string]$DataDir = '',
  [switch]$RunNow,
  [switch]$Uninstall
)
$ErrorActionPreference = 'Stop'
$taskName = 'Job Search Assistant - daily scan'
if ($Uninstall) {
  Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
  Write-Host "Removed the '$taskName' task."
  return
}

$root = Split-Path $PSScriptRoot -Parent
$run = Join-Path $PSScriptRoot 'run.ps1'

# Only the kit's own scripts are unblocked (files from a zip carry a "downloaded from the internet" mark).
Get-ChildItem -LiteralPath $PSScriptRoot -Filter '*.ps1' | Unblock-File

# Find a python that really runs. The Microsoft Store stub 'python.exe' exits 0 and prints nothing, so test it.
function Resolve-Python {
  if ($Python) { return $Python }
  if (Get-Command py -ErrorAction SilentlyContinue) {
    $r = & py -3 -c "print(1)" 2>$null
    if ($LASTEXITCODE -eq 0 -and "$r".Trim() -eq '1') {
      $exe = & py -3 -c "import sys; print(sys.executable)" 2>$null
      if ($exe -and (Test-Path "$exe".Trim())) { return "$exe".Trim() }
    }
  }
  foreach ($c in @(Get-Command python -All -ErrorAction SilentlyContinue)) {
    $r = & $c.Source -c "print(1)" 2>$null
    if ($LASTEXITCODE -eq 0 -and "$r".Trim() -eq '1') { return $c.Source }
  }
  return $null
}
$py = Resolve-Python
if (-not $py) { throw 'No working Python 3 found. Install it from python.org (tick "Add python.exe to PATH") and run this again.' }
Write-Host "Using Python: $py"

# Resolve the data folder to an ABSOLUTE path now, so the scheduled job never depends on the environment later.
if (-not $DataDir) { $DataDir = $env:JOBHUNT_DATA_DIR }
if (-not $DataDir) {
  $saved = Join-Path $env:APPDATA 'job-search-assistant\config.json'
  if (Test-Path $saved) { try { $DataDir = (Get-Content $saved -Raw -Encoding utf8 | ConvertFrom-Json).data_dir } catch { $DataDir = '' } }
}
if (-not $DataDir) { $DataDir = Join-Path $root 'profile' }
New-Item -ItemType Directory -Force $DataDir | Out-Null
$DataDir = (Resolve-Path -LiteralPath $DataDir).Path
Write-Host "Data folder: $DataDir"

$mailArg = if ($Mail) { " -Mail $Mail" } else { '' }
$shell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'   # present on every Windows
$arg = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$run`"$mailArg -Python `"$py`" -DataDir `"$DataDir`""
$action = New-ScheduledTaskAction -Execute $shell -Argument $arg -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Daily -At ([datetime]$Time)
# StartWhenAvailable: if the PC was off at the time, run when it comes back. Battery is allowed (laptops).
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable `
  -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

if (-not $RunNow) {
  Write-Host "Registered '$taskName' daily at $Time. To test now (this sends a real email): re-run this script with -RunNow"
  return
}
Write-Host "Registered '$taskName' daily at $Time. Running it once now to check it works..."
Start-ScheduledTask -TaskName $taskName
$deadline = (Get-Date).AddMinutes(10)
do {
  Start-Sleep -Seconds 5
  $state = (Get-ScheduledTask -TaskName $taskName).State
} while ($state -eq 'Running' -and (Get-Date) -lt $deadline)
$info = Get-ScheduledTaskInfo -TaskName $taskName
if ($state -eq 'Running') {
  Write-Host "Still running after 10 minutes. Read the newest .log file in $DataDir\scan\out\ for the progress."
} elseif ($info.LastTaskResult -eq 0) {
  Write-Host 'Test run finished with result 0 (success). Check your inbox for the digest.'
} else {
  Write-Host "Test run finished with result $($info.LastTaskResult). Read the newest .log file in $DataDir\scan\out\ to see why."
}
