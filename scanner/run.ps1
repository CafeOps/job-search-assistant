# Daily job scan for Windows: scan, email the digest, then acknowledge exactly that batch.
# Schedule it with scanner\install-task.ps1. Works in Windows PowerShell 5.1 and PowerShell 7.
# -Mail picks how the digest is sent. Empty: config "email": {"mode": "..."}, else smtp.
#   smtp    SMTP with the saved app password (default; set up with tools/email_setup.py)
#   claude  `claude -p` and the user's Gmail connector, which must already be set up in the Claude app.
#           Config email.claude_tool names the send tool.
#   codex   `codex exec` and the ChatGPT Gmail connector, which must already be set up in that app.
#   none    digest only: write the digest, print its path, do NOT acknowledge.
# For claude and codex, config email.ai_model picks the model; unset means the app's default.
# For smtp, claude and codex the batch is acknowledged only after exit code 0 AND an exact "SENT" line.
# In digest-only mode the picks stay queued and come back in every scan until the user has read them. Then run
#   <python> scanner/jobscan.py --mark-read-latest      (acknowledges the newest batch)
# or  <python> scanner/jobscan.py --mark-sent <batch>   (a specific batch id)
# -Python: full path to python.exe (install-task.ps1 passes it so the scheduled task does not depend on PATH).
# -DataDir: the user's data folder (install-task.ps1 passes it). Default: JOBHUNT_DATA_DIR, then the saved choice.
param(
  [string]$Mail = '',
  [string]$Python = '',
  [string]$DataDir = ''
)
# Native commands write to stderr; with 'Stop' that would abort the script. Exit codes are checked by hand.
$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = 'utf-8'
$root = Split-Path $PSScriptRoot -Parent
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
$today = Get-Date -Format 'yyyy-MM-dd'
# Data folder: -DataDir, else the JOBHUNT_DATA_DIR variable, else the saved choice (tools\paths.py), else the old profile folder.
if ($DataDir) { $env:JOBHUNT_DATA_DIR = $DataDir }
$data = $env:JOBHUNT_DATA_DIR
if (-not $data) {
  $saved = Join-Path $env:APPDATA 'job-search-assistant\config.json'
  if (Test-Path $saved) { try { $data = (Get-Content $saved -Raw -Encoding utf8 | ConvertFrom-Json).data_dir } catch { $data = $null } }
}
if (-not $data) { $data = Join-Path $root 'profile' }
$env:JOBHUNT_DATA_DIR = $data   # child processes (jobscan, send_email) read it
$out = Join-Path $data 'scan\out'
New-Item -ItemType Directory -Force $out | Out-Null
$log = Join-Path $out "$today.log"

function Log([string]$msg) { "$(Get-Date -Format 'HH:mm:ss') $msg" | Out-File -FilePath $log -Append -Encoding utf8 }
function Fail([string]$msg) { Log "STOP: $msg"; exit 1 }

# Find a python that really runs (the Microsoft Store 'python.exe' stub prints nothing and exits 0).
function Test-Py([string]$exe, [string[]]$pre) {
  try { $r = & $exe @pre -c 'print(1)' 2>$null; return ($LASTEXITCODE -eq 0 -and "$r".Trim() -eq '1') } catch { return $false }
}
$pyArgs = @()
if ($Python -and (Test-Path $Python)) { $py = $Python }
elseif ((Get-Command py -ErrorAction SilentlyContinue) -and (Test-Py 'py' @('-3'))) { $py = 'py'; $pyArgs = @('-3') }
elseif ((Get-Command python -ErrorAction SilentlyContinue) -and (Test-Py 'python' @())) { $py = 'python' }
else { Fail 'Python was not found. Install Python 3 from python.org and run scanner\install-task.ps1 again.' }

$scan = Join-Path $PSScriptRoot 'jobscan.py'
$send = Join-Path $PSScriptRoot 'send_email.py'

# 1. Scan. Any nonzero exit stops the run: no email, nothing acknowledged.
$scanOut = & $py @pyArgs $scan 2>&1 | ForEach-Object { "$_" }
$scanCode = $LASTEXITCODE
$scanOut | Out-File -FilePath $log -Append -Encoding utf8
if ($scanCode -ne 0) { Fail "scan failed (exit $scanCode); nothing was emailed" }

$line = $scanOut | Where-Object { $_ -match '^BATCH \S+ ' } | Select-Object -Last 1
if (-not $line) { Fail 'scan finished but printed no BATCH line; nothing was emailed' }
$batch = ($line -split ' ')[1]
$digest = $line.Substring(('BATCH ' + $batch + ' ').Length)
# The path in the output can be garbled by console encoding; fall back to the dated file and check the batch id inside.
if (-not (Test-Path -LiteralPath $digest)) { $digest = Join-Path $out "$today.txt" }
if (-not (Test-Path -LiteralPath $digest) -or -not ((Get-Content -LiteralPath $digest -Raw -Encoding utf8) -match "Batch: $([regex]::Escape($batch))")) {
  Fail "digest file for batch $batch is missing or belongs to another run; nothing was emailed"
}

# 2. Pick the mail mode: the -Mail argument, else config email.mode, else smtp.
$cfg = $null
$cfgPath = Join-Path $data 'scanner-config.json'
if (Test-Path $cfgPath) { try { $cfg = Get-Content $cfgPath -Raw -Encoding utf8 | ConvertFrom-Json } catch { $cfg = $null } }
$mode = $Mail
if (-not $mode -and $cfg -and $cfg.email -and $cfg.email.mode) { $mode = "$($cfg.email.mode)" }
if (-not $mode) { $mode = 'smtp' }
if (@('smtp', 'claude', 'codex', 'none') -notcontains $mode) { Fail "unknown mail mode '$mode' (use smtp, claude, codex or none)" }
# Digest-only mode: stop here. Nothing is emailed and nothing is acknowledged, so the picks stay queued.
if ($mode -eq 'none') {
  Log "digest only: batch $batch written to $digest; not acknowledged. After reading it, run: jobscan.py --mark-read-latest"
  Write-Output "DIGEST $digest"
  exit 0
}

# 3. Mail it. Needs exit code 0 AND a SENT line.
$to = if ($cfg -and $cfg.email) { $cfg.email.to } else { $null }
$prefix = if ($cfg -and $cfg.email -and $cfg.email.subject_prefix) { $cfg.email.subject_prefix } else { 'Job picks' }
$model = if ($cfg -and $cfg.email -and $cfg.email.ai_model) { "$($cfg.email.ai_model)" } else { '' }
$prompt = "Read the file $digest. Send its exact contents, unchanged, as one plain-text email to $to and no other address. Subject: $prefix $today. Do nothing else. Reply with the single word SENT when it went out, or FAILED and the reason."
switch ($mode) {
  'claude' {
    if (-not $to) { Fail 'config email.to is missing; nothing was emailed' }
    $tool = if ($cfg.email.claude_tool) { $cfg.email.claude_tool } else { 'mcp__claude_ai_Gmail__send_message' }
    $cargs = @('-p', $prompt, '--allowedTools', "Read,$tool")
    if ($model) { $cargs += @('--model', $model) }   # only when the user set email.ai_model; else the app's default
    $reply = & claude @cargs 2>&1 | ForEach-Object { "$_" }
  }
  'codex' {
    if (-not $to) { Fail 'config email.to is missing; nothing was emailed' }
    $cargs = @('exec', '--skip-git-repo-check')
    if ($model) { $cargs += @('-m', $model) }
    $cargs += $prompt
    $reply = & codex @cargs 2>&1 | ForEach-Object { "$_" }
  }
  'smtp' {
    $reply = & $py @pyArgs $send --digest $digest --batch $batch 2>&1 | ForEach-Object { "$_" }
  }
}
$mailCode = $LASTEXITCODE
$reply | Out-File -FilePath $log -Append -Encoding utf8
$sent = [bool]($reply | Where-Object { $_ -match '^\s*SENT(\s+\S+)?\s*$' })
if ($mailCode -ne 0 -or -not $sent) {
  Fail "email not confirmed (exit $mailCode); batch $batch stays queued and comes back in the next scan"
}

# 4. Acknowledge exactly this batch.
$ack = & $py @pyArgs $scan --mark-sent $batch 2>&1 | ForEach-Object { "$_" }
$ackCode = $LASTEXITCODE
$ack | Out-File -FilePath $log -Append -Encoding utf8
if ($ackCode -ne 0) { Fail "email went out but acknowledging batch $batch failed (exit $ackCode); it may be re-sent" }
Log "done: batch $batch sent and acknowledged"
