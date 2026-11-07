#!/usr/bin/env bash
# macOS: schedule the daily scan with a launchd agent (if the Mac is asleep at the set time, it runs on wake).
# Usage:  bash scanner/install-launchagent.sh [HH:MM] [smtp|claude|codex|none]
#           HH:MM defaults to 07:00. The mail method defaults to config email.mode, else smtp. claude and
#           codex need a mail connector set up in that app; none = digest file only (see the run.sh header).
#         DATA_DIR=/path/to/data bash scanner/install-launchagent.sh   (else JOBHUNT_DATA_DIR, else the saved choice)
#         bash scanner/install-launchagent.sh --run-now     (run the installed job through launchd to test it)
#         bash scanner/install-launchagent.sh --uninstall
# Python: the "Python command to use for every kit command: `<path>`" line in SETUP.md in the data folder,
# else python3 found on PATH. PYTHON=/path/to/python3 overrides both.
set -eu
LABEL="com.jobsearchassistant.scan"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
DOMAIN="gui/$(id -u)"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Data folder, resolved to an ABSOLUTE path now and baked into the job.
DATA="${DATA_DIR:-${JOBHUNT_DATA_DIR:-}}"
if [ -z "$DATA" ]; then
  SAVED="${XDG_CONFIG_HOME:-$HOME/.config}/job-search-assistant/config.json"
  [ -f "$SAVED" ] && DATA="$( (command -v python3 >/dev/null 2>&1 && python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8")).get("data_dir", ""))' "$SAVED" 2>/dev/null) || sed -n 's/.*"data_dir"[[:space:]]*:[[:space:]]*"\(.*\)".*/\1/p' "$SAVED" | head -n 1 )"
fi
DATA="${DATA:-$ROOT/profile}"
mkdir -p "$DATA"
DATA="$(cd "$DATA" && pwd)"

if [ "${1:-}" = "--uninstall" ]; then
  launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"
  echo "Removed $LABEL."
  exit 0
fi

if [ "${1:-}" = "--run-now" ]; then
  [ -f "$PLIST" ] || { echo "Not installed yet. Run this script without --run-now first." >&2; exit 1; }
  launchctl kickstart -k "$DOMAIN/$LABEL"
  echo "Started $LABEL through launchd. Read $DATA/scan/out/ (newest .log) and $DATA/scan/launchd.err.log in a minute."
  exit 0
fi

PYBIN="${PYTHON:-}"
if [ -z "$PYBIN" ] && [ -f "$DATA/SETUP.md" ]; then
  PYBIN="$(sed -n 's/.*Python command to use for every kit command: *`\([^`]*\)`.*/\1/p' "$DATA/SETUP.md" | head -n 1)"
fi
if [ -z "$PYBIN" ]; then PYBIN="$(command -v python3 || true)"; fi
if [ -z "$PYBIN" ] || [ "$("$PYBIN" -c 'print(1)' 2>/dev/null)" != "1" ]; then
  echo "No working Python 3 found. Install it (python.org or brew install python) and run this again." >&2; exit 1
fi
PYBIN="$(command -v "$PYBIN")"   # absolute path, so launchd does not depend on PATH

TIME="${1:-07:00}"
MAIL="${2:-}"
case "$MAIL" in ""|smtp|claude|codex|none) ;; *) echo "Mail method must be smtp, claude, codex or none." >&2; exit 1 ;; esac
if ! [[ "$TIME" =~ ^([01]?[0-9]|2[0-3]):([0-5][0-9])$ ]]; then
  echo "Time must look like 07:00 (24-hour)." >&2; exit 1
fi
HOUR=$((10#${BASH_REMATCH[1]}))
MINUTE=$((10#${BASH_REMATCH[2]}))

# Escape the characters that are special in XML so paths with spaces, & or ' stay valid.
xml() { local s="$1"; s="${s//&/&amp;}"; s="${s//</&lt;}"; s="${s//>/&gt;}"; printf '%s' "$s"; }

mkdir -p "$DATA/scan" "$HOME/Library/LaunchAgents"
cat >"$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$(xml "$ROOT/scanner/run.sh")</string>
    <string>--python</string>
    <string>$(xml "$PYBIN")</string>
    <string>--data-dir</string>
    <string>$(xml "$DATA")</string>
  </array>
  <key>WorkingDirectory</key><string>$(xml "$ROOT")</string>
  <key>EnvironmentVariables</key>
  <dict><key>MAIL</key><string>$MAIL</string><key>JOBHUNT_DATA_DIR</key><string>$(xml "$DATA")</string></dict>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>$HOUR</integer><key>Minute</key><integer>$MINUTE</integer></dict>
  <key>StandardOutPath</key><string>$(xml "$DATA/scan/launchd.out.log")</string>
  <key>StandardErrorPath</key><string>$(xml "$DATA/scan/launchd.err.log")</string>
</dict>
</plist>
PLISTEOF

plutil -lint "$PLIST" >/dev/null
launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true   # replace an older copy
launchctl bootstrap "$DOMAIN" "$PLIST"
echo "Installed $LABEL: runs daily at $(printf '%02d:%02d' "$HOUR" "$MINUTE") with mail method ${MAIL:-from config (default smtp)}."
echo "Python:       $PYBIN"
echo "Data folder:  $DATA"
echo "Test it now:  bash scanner/install-launchagent.sh --run-now   (runs it through launchd, the same path as the schedule)"
echo "Remove it:    bash scanner/install-launchagent.sh --uninstall"
