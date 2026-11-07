#!/usr/bin/env bash
# check_render.sh: the Mac/Linux version of check_render.ps1. It turns the resume into a PDF with
# LibreOffice (on a copy), then reports the page count and the text line by line, so you can spot
# bullets that wrap. It also saves a picture of page 1 if pdftoppm is installed.
#
# Usage:
#   bash tools/check_render.sh <data folder>/resume/live/Resume.docx
#   bash tools/check_render.sh Resume.docx 2        (second argument: page limit, default 1)
#
# Needs: LibreOffice (soffice). Optional: poppler (pdftotext, pdfinfo, pdftoppm).
#   Mac:   brew install --cask libreoffice && brew install poppler
#   Linux: sudo apt install libreoffice poppler-utils
# Output: the PDF next to the resume, and <data folder>/resume/preview.png (page 1) when possible.
# The data folder comes from JOBHUNT_DATA_DIR or the saved choice (tools/paths.py); without one, the
# picture goes next to the resume file.
# Note: LibreOffice can lay out text a little differently from Word. If the user's employers will
# open the file in Word, a final look in Word is still worth it.

set -u
DOCX="${1:-}"
MAXPAGES="${2:-1}"
if [ -z "$DOCX" ] || [ ! -f "$DOCX" ]; then
  echo "File not found. Usage: bash tools/check_render.sh path/to/Resume.docx [page limit]"
  exit 1
fi

SOFFICE="$(command -v soffice || command -v libreoffice || true)"
if [ -z "$SOFFICE" ] && [ -x "/Applications/LibreOffice.app/Contents/MacOS/soffice" ]; then
  SOFFICE="/Applications/LibreOffice.app/Contents/MacOS/soffice"
fi
if [ -z "$SOFFICE" ]; then
  echo "LibreOffice is not installed, so this check can't run."
  echo "Install it (see the top of this file), or open the resume in Word or Google Docs and look for"
  echo "bullets that wrap to a second line."
  exit 2
fi

DIR="$(cd "$(dirname "$DOCX")" && pwd)"
BASE="$(basename "$DOCX" .docx)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cp "$DOCX" "$WORK/$BASE.docx"     # work on a copy, the original is never touched

"$SOFFICE" --headless --convert-to pdf --outdir "$WORK" "$WORK/$BASE.docx" >/dev/null 2>&1
if [ ! -f "$WORK/$BASE.pdf" ]; then
  echo "LibreOffice could not convert the file. Close any open LibreOffice windows and try again."
  exit 1
fi
cp "$WORK/$BASE.pdf" "$DIR/$BASE.pdf"
echo "Resume: $BASE.docx"
echo "PDF saved: $DIR/$BASE.pdf"

if command -v pdfinfo >/dev/null 2>&1; then
  PAGES="$(pdfinfo "$WORK/$BASE.pdf" | awk '/^Pages:/ {print $2}')"
  if [ "$PAGES" -gt "$MAXPAGES" ]; then
    echo "PAGES: $PAGES (limit $MAXPAGES). Too long: cut or shorten something."
  else
    echo "PAGES: $PAGES (limit $MAXPAGES). OK."
  fi
fi

if command -v pdftotext >/dev/null 2>&1; then
  echo
  echo "LINES as laid out on the page (a bullet split over two lines here is too long):"
  pdftotext -layout "$WORK/$BASE.pdf" - | sed '/^[[:space:]]*$/d' | nl -ba | sed 's/^/  /'
else
  echo "pdftotext not found, so the line-by-line view is skipped (install poppler)."
fi

if command -v pdftoppm >/dev/null 2>&1; then
  DATA="${JOBHUNT_DATA_DIR:-}"
  if [ -z "$DATA" ]; then
    SAVED="${XDG_CONFIG_HOME:-$HOME/.config}/job-search-assistant/config.json"
    [ -f "$SAVED" ] && DATA="$( (command -v python3 >/dev/null 2>&1 && python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8")).get("data_dir", ""))' "$SAVED" 2>/dev/null) || sed -n 's/.*"data_dir"[[:space:]]*:[[:space:]]*"\(.*\)".*/\1/p' "$SAVED" | head -n 1 )"
  fi
  if [ -n "$DATA" ]; then PREVIEW_DIR="$DATA/resume"; else PREVIEW_DIR="$DIR"; fi
  mkdir -p "$PREVIEW_DIR"
  pdftoppm -png -r 150 -f 1 -l 1 -singlefile "$WORK/$BASE.pdf" "$PREVIEW_DIR/preview"
  echo
  echo "Picture of page 1: $PREVIEW_DIR/preview.png (open it and look before sending anything)."
fi
exit 0
