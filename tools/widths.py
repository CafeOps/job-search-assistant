"""widths.py: count the characters in every resume line and flag bullets outside the width band.

Usage:
  py tools/widths.py <data folder>/resume/live/Resume.docx
  py tools/widths.py Resume.docx --band 95-110
  py tools/widths.py Resume.md              (also works on .md and .txt)
  python3 tools/widths.py Resume.docx       (Mac/Linux)

Where the band comes from, in order:
  1. --band A-B on the command line
  2. a line in RESUME-RULES.md (in the data folder) like:  Line width band (Rule 1): 95 to 110
  3. neither: the script only reports lengths, it flags nothing

What it prints:
  HEADER lines (name, contact, headline), SKILLS lines and BULLETS, each with its character count.
  Bullets outside the band are marked SHORT or LONG. Skills and header lines are not flagged, because
  lines heavy in capital letters are wider on the page and usually need a lower limit. Check those
  in the render (tools/check_render.ps1 or tools/check_render.sh).

Character count is only a stand-in for width on the page. The render is the real test.
Reading .docx needs python-docx (pip install python-docx). Without it, use the .md version.
Always exits 0, so an AI can run it after every edit without the run "failing".
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402

BULLET_MARK = re.compile(r"^\s*([-*•▪●]|\d+[.)])\s+")
HEADING_MD = re.compile(r"^\s*#{1,6}\s+")
BAND_LINE = re.compile(r"line width band.*?(\d{2,3})\s*(?:-|to)\s*(\d{2,3})", re.I)


def read_lines(path):
    """Return a list of (kind_hint, text). kind_hint is 'heading', 'bullet' or 'text'."""
    if path.suffix.lower() == ".docx":
        try:
            import docx  # python-docx
        except ImportError:
            print("python-docx is not installed. Run: pip install python-docx")
            print("Or run this script on the .md copy of the resume instead.")
            return None
        out = []
        for p in docx.Document(str(path)).paragraphs:
            text = p.text.strip()
            if not text:
                continue
            style = (p.style.name or "").lower()
            ppr = p._p.pPr
            numbered = ppr is not None and ppr.numPr is not None
            if style.startswith("heading") or style == "title":
                out.append(("heading", text))
            elif numbered or "list" in style or BULLET_MARK.match(text):
                out.append(("bullet", BULLET_MARK.sub("", text)))
            else:
                out.append(("text", text))
        return out
    out = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        text = raw.strip()
        if not text:
            continue
        if HEADING_MD.match(text):
            out.append(("heading", HEADING_MD.sub("", text)))
        elif BULLET_MARK.match(text):
            out.append(("bullet", BULLET_MARK.sub("", text)))
        else:
            out.append(("text", text))
    return out


def find_band(argv, start):
    """Band from --band, else from RESUME-RULES.md in the data folder (or searched upward from the resume)."""
    if "--band" in argv:
        i = argv.index("--band")
        m = re.match(r"(\d+)\s*-\s*(\d+)", argv[i + 1] if i + 1 < len(argv) else "")
        if m:
            return int(m.group(1)), int(m.group(2)), "--band"
        print("Could not read --band. Write it like: --band 95-110")
    for folder in [paths.data_dir(), start, *start.parents, Path.cwd()]:
        rules = folder / "RESUME-RULES.md"
        if not rules.exists():
            rules = folder / "profile" / "RESUME-RULES.md"
        if rules.exists():
            for line in rules.read_text(encoding="utf-8", errors="replace").splitlines():
                m = BAND_LINE.search(line)
                if m:
                    return int(m.group(1)), int(m.group(2)), str(rules)
            break
    return None


def main():
    argv = sys.argv[1:]
    files = [a for a in argv if not a.startswith("--") and not re.match(r"^\d+\s*-\s*\d+$", a)]
    if not files:
        print(__doc__)
        return
    path = Path(files[0]).resolve()
    if not path.exists():
        print(f"File not found: {path}")
        return
    lines = read_lines(path)
    if lines is None:
        return
    band = find_band(argv, path.parent)

    # Sort lines into sections: everything before the first section heading after the name is HEADER,
    # bullets under a heading with "skill" in it are SKILLS, all other bullets are BULLETS.
    section, seen_heading = "header", 0
    header, skills, bullets = [], [], []
    for kind, text in lines:
        if kind == "heading":
            seen_heading += 1
            if seen_heading > 1:
                section = "skills" if "skill" in text.lower() else "body"
            continue
        if section == "header":
            header.append(text)
        elif kind == "bullet" and section == "skills":
            skills.append(text)
        elif kind == "bullet":
            bullets.append(text)
        elif section == "skills" and ":" in text[:40]:
            skills.append(text)

    print(f"Resume: {path.name}")
    if band:
        lo, hi, src = band
        print(f"Bullet band: {lo} to {hi} characters (from {src})")
    else:
        print("No band set, so nothing is flagged. Set one with --band A-B, or add this line to")
        print("RESUME-RULES.md in the data folder:  Line width band (Rule 1): A to B")
    print()

    def show(title, items, flag):
        if not items:
            return 0
        print(f"{title} ({len(items)})")
        bad = 0
        for t in items:
            n = len(t)
            mark = ""
            if flag and band:
                if n < band[0]:
                    mark, bad = f"  SHORT by {band[0] - n}", bad + 1
                elif n > band[1]:
                    mark, bad = f"  LONG by {n - band[1]}", bad + 1
            print(f"  {n:>4}  {t[:90]}{'...' if len(t) > 90 else ''}{mark}")
        print()
        return bad

    show("HEADER lines (not flagged; check the render)", header, False)
    show("SKILLS lines (not flagged; capital-heavy lines need a lower limit)", skills, False)
    bad = show("BULLETS", bullets, True)

    if band:
        if bad:
            print(f"Result: {bad} of {len(bullets)} bullets are outside the band. Rewrite those, then run again.")
        else:
            print(f"Result: all {len(bullets)} bullets are inside the band. Now check the render for wraps.")
    longest = max(bullets, key=len, default="")
    if longest:
        print(f"Longest bullet: {len(longest)} characters. If it fits on one line in the render, it is a good")
        print("upper end for the band (Rule 1).")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # never fail the run, just explain
        print(f"widths.py could not finish: {e}")
    sys.exit(0)
