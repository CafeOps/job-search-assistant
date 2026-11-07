#!/usr/bin/env bash
# Daily job scan for macOS/Linux: scan, email the digest, then acknowledge exactly that batch.
# Schedule with scanner/install-launchagent.sh (macOS) or cron (see docs/06-daily-scan.md).
# Usage: [MAIL=smtp|claude|codex|none] run.sh [--python /path/to/python3] [--data-dir /path/to/data/folder]
# MAIL picks how the digest is sent. Empty: config "email": {"mode": "..."}, else smtp.
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
# Python: --python, else PYTHON, else detected.
# Data folder: --data-dir, else JOBHUNT_DATA_DIR, else the saved choice (tools/paths.py), else <kit>/profile.
set -uo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"   # launchd and cron start with a bare PATH
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MAIL="${MAIL:-}"
TODAY="$(date +%F)"
PYTHON="${PYTHON:-}"
while [ $# -gt 0 ]; do
  case "$1" in
    --python) PYTHON="${2:-}"; shift 2 ;;
    --data-dir) JOBHUNT_DATA_DIR="${2:-}"; shift 2 ;;
    *) shift ;;
  esac
done
if [ -z "${JOBHUNT_DATA_DIR:-}" ]; then
  SAVED="${XDG_CONFIG_HOME:-$HOME/.config}/job-search-assistant/config.json"
  [ -f "$SAVED" ] && JOBHUNT_DATA_DIR="$( (command -v python3 >/dev/null 2>&1 && python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8")).get("data_dir", ""))' "$SAVED" 2>/dev/null) || sed -n 's/.*"data_dir"[[:space:]]*:[[:space:]]*"\(.*\)".*/\1/p' "$SAVED" | head -n 1 )"
fi
export JOBHUNT_DATA_DIR="${JOBHUNT_DATA_DIR:-$ROOT/profile}"   # child processes (jobscan, send_email) read it
DATA="$JOBHUNT_DATA_DIR"
OUT="$DATA/scan/out"
CFG="$DATA/scanner-config.json"
mkdir -p "$OUT"
LOG="$OUT/$TODAY.log"
log() { printf '%s %s\n' "$(date +%T)" "$*" >>"$LOG"; }
fail() { log "STOP: $*"; exit 1; }

PY="${PYTHON:-}"
if [ -n "$PY" ] && [ "$("$PY" -c 'print(1)' 2>/dev/null)" != "1" ]; then fail "the Python given ($PY) does not run"; fi
if [ -z "$PY" ]; then
  for c in python3 python; do
    if command -v "$c" >/dev/null 2>&1 && [ "$("$c" -c 'print(1)' 2>/dev/null)" = "1" ]; then PY="$c"; break; fi
  done
fi
[ -n "$PY" ] || fail "Python 3 was not found"

# 1. Scan. Any nonzero exit stops the run: no email, nothing acknowledged.
SCAN_OUT="$("$PY" "$ROOT/scanner/jobscan.py" 2>&1)"; SCAN_RC=$?
printf '%s\n' "$SCAN_OUT" >>"$LOG"
[ "$SCAN_RC" -eq 0 ] || fail "scan failed (exit $SCAN_RC); nothing was emailed"

BATCH_LINE="$(printf '%s\n' "$SCAN_OUT" | grep -E '^BATCH [^ ]+ ' | tail -n 1)"
[ -n "$BATCH_LINE" ] || fail "scan finished but printed no BATCH line; nothing was emailed"
BATCH="$(printf '%s' "$BATCH_LINE" | cut -d' ' -f2)"
DIGEST="${BATCH_LINE#BATCH $BATCH }"
[ -f "$DIGEST" ] && grep -qF "Batch: $BATCH" "$DIGEST" || fail "digest for batch $BATCH is missing; nothing was emailed"

# 2. Read the mail settings (all optional here). The path goes in as an argument, never inside the Python source.
CFG_VALUES="$("$PY" - "$CFG" <<'EOF'
import json, os, sys
e = {}
if os.path.exists(sys.argv[1]):
    try:
        e = json.load(open(sys.argv[1], encoding="utf-8")).get("email") or {}
    except ValueError:
        pass
for k, d in (("mode", ""), ("to", ""), ("subject_prefix", "Job picks"),
             ("claude_tool", "mcp__claude_ai_Gmail__send_message"), ("ai_model", "")):
    print(e.get(k) or d)
EOF
)"
CFG_MODE="$(printf '%s\n' "$CFG_VALUES" | sed -n 1p)"
TO="$(printf '%s\n' "$CFG_VALUES" | sed -n 2p)"
PREFIX="$(printf '%s\n' "$CFG_VALUES" | sed -n 3p)"
TOOL="$(printf '%s\n' "$CFG_VALUES" | sed -n 4p)"
MODEL="$(printf '%s\n' "$CFG_VALUES" | sed -n 5p)"
[ -n "$MAIL" ] || MAIL="${CFG_MODE:-smtp}"
case "$MAIL" in smtp|claude|codex|none) ;; *) fail "unknown mail mode '$MAIL' (use smtp, claude, codex or none)" ;; esac
# Digest-only mode: stop here. Nothing is emailed and nothing is acknowledged, so the picks stay queued.
if [ "$MAIL" = "none" ]; then
  log "digest only: batch $BATCH written to $DIGEST; not acknowledged. After reading it, run: jobscan.py --mark-read-latest"
  echo "DIGEST $DIGEST"
  exit 0
fi

# 3. Mail it. Needs exit code 0 AND a SENT line. A model is passed only when config email.ai_model is set.
PROMPT="Read the file $DIGEST. Send its exact contents, unchanged, as one plain-text email to $TO and no other address. Subject: $PREFIX $TODAY. Do nothing else. Reply with the single word SENT when it went out, or FAILED and the reason."
case "$MAIL" in
  claude)
    [ -n "$TO" ] || fail "config email.to is missing; nothing was emailed"
    if [ -n "$MODEL" ]; then REPLY="$(claude -p "$PROMPT" --allowedTools "Read,$TOOL" --model "$MODEL" 2>&1)"; MAIL_RC=$?
    else REPLY="$(claude -p "$PROMPT" --allowedTools "Read,$TOOL" 2>&1)"; MAIL_RC=$?; fi ;;
  codex)
    [ -n "$TO" ] || fail "config email.to is missing; nothing was emailed"
    if [ -n "$MODEL" ]; then REPLY="$(codex exec --skip-git-repo-check -m "$MODEL" "$PROMPT" 2>&1)"; MAIL_RC=$?
    else REPLY="$(codex exec --skip-git-repo-check "$PROMPT" 2>&1)"; MAIL_RC=$?; fi ;;
  smtp)   REPLY="$("$PY" "$ROOT/scanner/send_email.py" --digest "$DIGEST" --batch "$BATCH" 2>&1)"; MAIL_RC=$? ;;
esac
printf '%s\n' "$REPLY" >>"$LOG"
if [ "$MAIL_RC" -ne 0 ] || ! grep -qE '^[[:space:]]*SENT([[:space:]]+[^[:space:]]+)?[[:space:]]*$' <<<"$REPLY"; then
  fail "email not confirmed (exit $MAIL_RC); batch $BATCH stays queued and comes back in the next scan"
fi

# 4. Acknowledge exactly this batch.
ACK="$("$PY" "$ROOT/scanner/jobscan.py" --mark-sent "$BATCH" 2>&1)"; ACK_RC=$?
printf '%s\n' "$ACK" >>"$LOG"
[ "$ACK_RC" -eq 0 ] || fail "email went out but acknowledging batch $BATCH failed (exit $ACK_RC); it may be re-sent"
log "done: batch $BATCH sent and acknowledged"
