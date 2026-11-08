"""build_resume.py: build the resume (.docx + .pdf) and run the quality gate on it.

Usage:
  <python> tools/build_resume.py <data>/resume/resume.md
  options: --pages 2 (allowed pages, default 1)   --spacing compact|normal|roomy|relaxed|airy (force a layout)
           --suffix Endpoint (variant name)       --profile <folder> (where RESUME-RULES, VOICE, NUMBERS live)
           --out <folder> (write elsewhere, for samples and tests)   --no-pdf (Word file only, no gate)

What it does:
  1. Builds First_Last_Resume.docx: one column, Calibri, real Title, Heading and bullet styles, contact details
     in the page body, no tables, text boxes, images, headers or footers. That is what ATS software reads best.
  2. Makes the PDF (Word on Windows, LibreOffice on Mac/Linux) in five layouts, compact to airy, and keeps the
     one that fills the page best without going past the allowed page count.
  3. Moves the previous live files to <data>/resume/history/NN_YYYY-MM-DD/ first. Nothing is deleted.
  4. Renders every page to <data>/resume/preview/page-N.png.
  5. Prints the QUALITY GATE and exits 1 if anything FAILs. Fix it in resume.md, then build again.
  6. The AI then OPENS AND LOOKS AT the page images and works through the visual checklist in docs/03.
     A script can't judge how a page looks.
Needs python-docx. Better with pypdf (text check) and pypdfium2 + pillow (page images). pdftoppm also works.
The resume.md format is shown in examples/john-smith/resume.md.
"""
import datetime as dt
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

FONT = "Calibri"
ACCENT = (0x1F, 0x3A, 0x5F)
TIERS = {  # tightest first. Sizes in pt, margins in inches.
    "compact": dict(body=10.5, after=1, section=8, role=4, lr=0.6, tb=0.5, line=1.0),
    "normal": dict(body=11, after=1.5, section=10, role=6, lr=0.7, tb=0.6, line=1.0),
    "roomy": dict(body=11, after=3, section=14, role=9, lr=0.75, tb=0.7, line=1.07),
    "relaxed": dict(body=11, after=4, section=16, role=10, lr=0.75, tb=0.7, line=1.12),
    "airy": dict(body=11.5, after=4, section=17, role=11, lr=0.8, tb=0.75, line=1.12),
}
DEFAULT_BANNED = ["leveraged", "spearheaded", "streamlined", "seamless", "seamlessly", "synergy", "orchestrated",
                  "passionate", "dynamic", "results-driven", "go-getter", "in order to", "it is worth noting",
                  "responsible for", "helped to", "utilized", "cutting-edge", "best-in-class", "proven track record"]
MONTH = r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec) \d{4}"
DATE_RE = re.compile(rf"^({MONTH} to ({MONTH}|Present)|\d{{4}}|In progress)$")


def die(msg):
    print(msg)
    sys.exit(1)


def clean(s):
    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", s).replace("**", "").replace("__", "").strip()


def parse(md):
    doc = {"name": "", "contact": "", "headline": "", "sections": []}
    sec = None
    for line in (raw.rstrip() for raw in md.splitlines()):
        if not line.strip():
            continue
        if line.startswith("# ") and not doc["name"]:
            doc["name"] = clean(line[2:])
        elif line.startswith("## "):
            sec = {"title": clean(line[3:]), "items": []}
            doc["sections"].append(sec)
        elif sec is None:
            if line.lower().startswith("headline:"):
                doc["headline"] = clean(line.split(":", 1)[1])
            elif not doc["contact"]:
                doc["contact"] = clean(line)
            else:
                doc["headline"] = doc["headline"] or clean(line)
        elif line.startswith("### "):
            left, _, right = line[4:].partition("|")
            sec["items"].append(("role", clean(left), clean(right)))
        elif line.lstrip().startswith(("- ", "* ")):
            body = line.lstrip()[2:]
            m = re.match(r"\*\*(.+?)\*\*\s*(.*)", body)
            sec["items"].append(("labelled", clean(m.group(1)), clean(m.group(2))) if m else ("bullet", clean(body), ""))
        elif line.startswith("**") and sec["items"] and sec["items"][-1][0] == "role":
            left, _, right = line.partition("|")
            sec["items"].append(("org", clean(left), clean(right)))
        else:
            sec["items"].append(("text", clean(line), ""))
    if not doc["name"]:
        die("resume.md needs the name on the first line, like: # First Last")
    return doc


def build_docx(doc, path, tier="normal", created=None):
    try:
        import docx
        from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        from docx.shared import Inches, Pt, RGBColor
    except ImportError:
        die("python-docx is not installed. Ask the user, then run: <python> -m pip install python-docx")
    t, navy = TIERS[tier], RGBColor(*ACCENT)
    d = docx.Document()
    s = d.sections[0]
    s.page_width, s.page_height = Inches(8.5), Inches(11)
    s.left_margin = s.right_margin = Inches(t["lr"])
    s.top_margin = s.bottom_margin = Inches(t["tb"])
    width = s.page_width - s.left_margin - s.right_margin

    for sname in ("Normal", "List Bullet"):
        st = d.styles[sname]
        st.font.name, st.font.size = FONT, Pt(t["body"])
        st.paragraph_format.space_before = st.paragraph_format.space_after = Pt(0)
        st.paragraph_format.line_spacing = t["line"]
    d.styles["Normal"].element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    for sname, size in (("Title", 20), ("Heading 1", t["body"] + 0.5)):  # real structure, plain look
        st = d.styles[sname]
        rpr, ppr = st.element.get_or_add_rPr(), st.element.get_or_add_pPr()
        for old in rpr.findall(qn("w:rFonts")) + ppr.findall(qn("w:pBdr")):
            old.getparent().remove(old)
        st.font.name, st.font.size, st.font.bold, st.font.italic, st.font.color.rgb = FONT, Pt(size), True, False, navy
        st.paragraph_format.space_before = st.paragraph_format.space_after = Pt(0)
        st.paragraph_format.line_spacing = 1.0

    def para(before=0, after=0, align=None, style=None):
        p = d.add_paragraph(style=style)
        p.paragraph_format.space_before, p.paragraph_format.space_after = Pt(before), Pt(after)
        if align is not None:
            p.alignment = align
        return p

    def run(p, text, bold=False, italic=False, size=None, color=None):
        r = p.add_run(text)
        r.bold, r.italic = bold, italic
        if size:
            r.font.size = Pt(size)
        if color:
            r.font.color.rgb = color

    def two_sides(left, right, bold=False, italic=False, before=0):
        p = para(before=before)
        p.paragraph_format.tab_stops.add_tab_stop(width, WD_TAB_ALIGNMENT.RIGHT)
        p.paragraph_format.keep_with_next = True
        run(p, left, bold=bold, italic=italic)
        if right:
            run(p, "\t" + right, italic=italic)

    run(para(align=WD_ALIGN_PARAGRAPH.CENTER, style="Title"), doc["name"], bold=True, size=20, color=navy)
    if doc["contact"]:
        run(para(before=2, align=WD_ALIGN_PARAGRAPH.CENTER), doc["contact"], size=10)
    if doc["headline"]:
        run(para(before=4, align=WD_ALIGN_PARAGRAPH.CENTER), doc["headline"], bold=True, color=navy)
    for sec in doc["sections"]:
        h = para(before=t["section"], after=3, style="Heading 1")
        h.paragraph_format.keep_with_next = True
        run(h, sec["title"].upper(), bold=True, color=navy)
        bdr, b = OxmlElement("w:pBdr"), OxmlElement("w:bottom")
        for k, v in (("w:val", "single"), ("w:sz", "6"), ("w:space", "1"), ("w:color", "%02X%02X%02X" % ACCENT)):
            b.set(qn(k), v)
        bdr.append(b)
        h._p.get_or_add_pPr().append(bdr)
        first_role = True
        for kind, a, b in sec["items"]:
            if kind == "role":
                two_sides(a, b, bold=True, before=0 if first_role else t["role"])
                first_role = False
            elif kind == "org":
                two_sides(a, b, italic=True)
            elif kind in ("bullet", "labelled"):
                p = d.add_paragraph(style="List Bullet")
                pf = p.paragraph_format
                pf.space_after, pf.left_indent, pf.first_line_indent = Pt(t["after"]), Inches(0.22), Inches(-0.16)
                if kind == "labelled":
                    run(p, a + " ", bold=True)
                run(p, b if kind == "labelled" else a)
            else:
                run(para(after=2), a)

    cp = d.core_properties
    cp.title, cp.author, cp.last_modified_by = f"{doc['name']} Resume", doc["name"], doc["name"]
    cp.comments = cp.keywords = cp.subject = ""
    if created:
        cp.created = cp.modified = created
    d.save(str(path))
    if created:  # zip entry times otherwise carry the build computer's clock
        tmp = path.with_suffix(".tmp")
        with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                item.date_time = created.timetuple()[:6]
                zout.writestr(item, zin.read(item.filename))
        tmp.replace(path)


def make_pdf(docx_path, pdf_path):
    """Returns dict(ok, pages, wraps, how). wraps lists paragraphs that run onto a second line (Word only)."""
    if sys.platform == "win32":
        q = lambda p: str(p).replace("'", "''")
        ps = ("$w=$null;$d=$null;try{$w=New-Object -ComObject Word.Application;$w.Visible=$false;$w.DisplayAlerts=0;"
              f"$d=$w.Documents.Open('{q(docx_path)}',$false,$true,$false);$d.Repaginate();"
              "foreach($p in $d.Paragraphs){$t=$p.Range.Text.Trim();if(!$t){continue};"
              "$a=$p.Range.Characters.First;$b=$p.Range.Characters.Last;"
              "if(($a.Information(10) -ne $b.Information(10)) -or ($a.Information(3) -ne $b.Information(3))){"
              "Write-Output ('WRAP='+$t.Substring(0,[Math]::Min(70,$t.Length)))}};"
              f"$d.ExportAsFixedFormat('{q(pdf_path)}',17);Write-Output ('PAGES='+$d.ComputeStatistics(2))}}"
              "catch{Write-Output ('ERR='+$_.Exception.Message)}"
              "finally{if($d){$d.Close(0)|Out-Null};if($w){$w.Quit()|Out-Null}}")
        try:
            out = subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps],
                                 capture_output=True, text=True, timeout=240).stdout
            m = re.search(r"PAGES=(\d+)", out)
            if m and pdf_path.exists():
                return dict(ok=True, pages=int(m.group(1)), how="Microsoft Word",
                            wraps=[w.strip() for w in re.findall(r"WRAP=(.*)", out)])
        except Exception:
            pass
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    mac = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")
    soffice = soffice or (str(mac) if mac.exists() else None)
    if soffice:
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", tmp, str(docx_path)],
                           capture_output=True, timeout=240)
            made = Path(tmp) / (docx_path.stem + ".pdf")
            if made.exists():
                shutil.copy(made, pdf_path)
                return dict(ok=True, pages=None, how="LibreOffice", wraps=None)
    return dict(ok=False, pages=None, how=None, wraps=None)


def pdf_text(pdf_path):
    try:
        import pypdf
        r = pypdf.PdfReader(str(pdf_path))
        return "\n".join(pg.extract_text() or "" for pg in r.pages), len(r.pages)
    except ImportError:
        pass
    if shutil.which("pdftotext"):
        out = subprocess.run(["pdftotext", "-layout", str(pdf_path), "-"], capture_output=True, text=True).stdout
        return out, out.count("\f") or None
    return None, None


def render_pages(pdf_path, out_dir, dpi=110):
    """Every page to out_dir/page-N.png. Returns the image paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("page-*.png"):
        old.unlink()
    try:
        import pypdfium2 as pdfium
        pdf, made = pdfium.PdfDocument(str(pdf_path)), []
        for i in range(len(pdf)):
            made.append(out_dir / f"page-{i + 1}.png")
            pdf[i].render(scale=dpi / 72).to_pil().save(made[-1])
        pdf.close()
        return made
    except Exception:
        pass
    if shutil.which("pdftoppm"):
        subprocess.run(["pdftoppm", "-png", "-r", str(dpi), str(pdf_path), str(out_dir / "page")], capture_output=True)
        for p in out_dir.glob("page-*.png"):  # pdftoppm may zero-pad: page-01.png
            n = int(re.search(r"(\d+)\.png$", p.name).group(1))
            p.replace(out_dir / f"page-{n}.png")
        return sorted(out_dir.glob("page-*.png"))
    return []


def page_fill(png):
    """Share of the page height that holds content, from the image (0 to 1). None without pillow."""
    try:
        from PIL import Image
    except ImportError:
        return None
    img = Image.open(png).convert("L")
    w, h = img.size
    px = img.load()
    for y in range(h - 1, -1, -1):
        if any(px[x, y] < 200 for x in range(0, w, 3)):
            return y / h
    return 0.0


def scrub_pdf(pdf_path, doc, when):
    """Plain metadata only: title, author, fixed date. Used for the shared sample."""
    try:
        import pypdf
    except ImportError:
        return
    w = pypdf.PdfWriter()
    for pg in pypdf.PdfReader(str(pdf_path)).pages:
        w.add_page(pg)
    stamp = when.strftime("D:%Y%m%d%H%M%SZ")
    w.add_metadata({"/Title": f"{doc['name']} Resume", "/Author": doc["name"],
                    "/CreationDate": stamp, "/ModDate": stamp, "/Producer": "", "/Creator": ""})
    tmp = pdf_path.with_suffix(".tmp")
    with open(tmp, "wb") as f:
        w.write(f)
    tmp.replace(pdf_path)


def archive_live(live):
    """Move the current live files to history/NN_YYYY-MM-DD/. Nothing is deleted."""
    current = [p for p in live.glob("*") if p.suffix.lower() in (".docx", ".pdf")]
    if not current:
        return None
    hist = live.parent / "history"
    hist.mkdir(parents=True, exist_ok=True)
    dest = hist / f"{len([p for p in hist.iterdir() if p.is_dir()]) + 1:02d}_{dt.date.today().isoformat()}"
    dest.mkdir()
    for p in current:
        shutil.move(str(p), dest / p.name)
    with open(hist / "README.md", "a", encoding="utf-8") as f:
        f.write(f"- {dest.name}: replaced on {dt.date.today().isoformat()}. What changed and why: \n")
    return dest


def read_profile(folder):
    """Width band, bullets per role, banned words and locked numbers from the user's files."""
    prof = {"band": None, "per_role": None, "banned": list(DEFAULT_BANNED), "numbers": None}
    if not folder:
        return prof
    read = lambda name: (folder / name).read_text(encoding="utf-8", errors="replace") if (folder / name).exists() else ""
    rules, voice = read("RESUME-RULES.md"), read("VOICE.md")
    m = re.search(r"line width band.*?(\d{2,3})\s*(?:-|to)\s*(\d{2,3})", rules, re.I)
    prof["band"] = (int(m.group(1)), int(m.group(2))) if m else None
    m = re.search(r"bullets per role.*?current\s+(\d+).*?previous\s+(\d+)", rules, re.I)
    prof["per_role"] = (int(m.group(1)), int(m.group(2))) if m else None
    section = lambda title: voice.split(title, 1)[1].split("\n## ", 1)[0] if title in voice else ""
    banned_block = "\n".join(l for l in section("## Banned").splitlines() if not l.lower().startswith("punctuation"))
    words = re.findall(r'"([^"]+)"', banned_block + section("## Added by the user"))
    words += [w for w in re.split(r",\s*|\n", re.sub(r'"[^"]*"', "", banned_block)) if re.fullmatch(r"[a-z][a-z -]+", w.strip())]
    for w in (x.strip(" ,.;:").lower() for x in words):
        if len(w) > 3 and w not in prof["banned"]:
            prof["banned"].append(w)
    allowed = section("## Allowed").lower()
    prof["banned"] = [w for w in prof["banned"] if w not in allowed]
    prof["numbers"] = read("NUMBERS.md") or None
    return prof


def gate(doc, prof, res, text, fill, allowed):
    rows = []
    add = lambda name, ok, note: rows.append((name, "PASS" if ok else "FAIL", note))
    bullets = [a for s in doc["sections"] for k, a, _ in s["items"] if k == "bullet"]
    lines = bullets + [f"{a} {b}" for s in doc["sections"] for k, a, b in s["items"] if k == "labelled"]

    add("Page count", res["pages"] is not None and res["pages"] <= allowed, f"{res['pages']} of {allowed} allowed")
    if fill is None:
        rows.append(("Page fill", "LOOK", "no pillow: judge it in the visual check"))
    else:
        add("Page fill", fill >= 0.85, f"{int(fill * 100)}% of the last page used (85%+ needed, else add true content)")
    if res["wraps"] is None:
        rows.append(("Wrapped bullets", "LOOK", "no Word: check every bullet is one line in the images"))
    else:
        bad = [w for w in res["wraps"] if any(b.startswith(w[:40]) for b in lines)]
        add("Wrapped bullets", not bad, "; ".join(w[:45] + "..." for w in bad) or "none")
    if prof["band"]:
        lo, hi = prof["band"]
        off = [f"{len(b)}: {b[:40]}..." for b in bullets if not lo <= len(b) <= hi]
        add(f"Width band {lo}-{hi}", not off, "; ".join(off) or f"all {len(bullets)} bullets in band")
    if prof["per_role"]:
        counts = []
        for s in (s for s in doc["sections"] if s["title"].lower() == "experience"):
            for k, _, _ in s["items"]:
                if k == "role":
                    counts.append(0)
                elif k == "bullet" and counts:
                    counts[-1] += 1
        cur, prev = prof["per_role"]
        add("Bullets per role", counts[:1] == [cur] and all(c == prev for c in counts[1:2]),
            f"have {counts}, rules say current {cur}, previous {prev}")
    full = " ".join([doc["headline"]] + [f"{a} {b}" for s in doc["sections"] for _, a, b in s["items"]]).lower()
    hits = sorted(w for w in prof["banned"] if re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", full))
    add("Banned words", not hits, ", ".join(hits) or f"none of {len(prof['banned'])}")
    add("No em or en dashes", "\u2014" not in full and "\u2013" not in full, "checked every line")
    if prof["numbers"]:
        locked = prof["numbers"].replace(",", "")
        missing = [f"{n} in '{b[:30]}...'" for b in bullets for n in re.findall(r"\d[\d,.]*", b)
                   if n.rstrip(".").replace(",", "") not in locked]
        add("Numbers in NUMBERS.md", not missing, "; ".join(missing) or "every figure is locked")
    bad_dates = [b for s in doc["sections"] for k, _, b in s["items"] if k == "role" and b and not DATE_RE.match(b)]
    add("One date format", not bad_dates, "; ".join(bad_dates) or "Mon YYYY to Mon YYYY or Present")
    if text is None:
        rows.append(("ATS text order", "LOOK", "install pypdf to check"))
    else:
        flat, probs, pos = re.sub(r"\s+", " ", text).lower(), [], -1
        if doc["name"].lower() not in flat[:200]:
            probs.append("name is not first, or the text can't be selected")
        for s in doc["sections"]:
            i = flat.find(s["title"].lower())
            if i < 0 or i < pos:
                probs.append(f"'{s['title']}' missing or out of order")
            pos = max(pos, i)
        add("ATS text order", not probs, "; ".join(probs) or "selectable, name first, headings in order")
    rows.append(("Visual check", "TODO", "open every page image and work through the visual checklist (docs/03)"))
    return rows


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return
    src = Path(args[0]).resolve()
    if not src.exists():
        die(f"Not found: {src}")
    opt = lambda k: args[args.index(k) + 1] if k in args and args.index(k) + 1 < len(args) else None
    doc, allowed = parse(src.read_text(encoding="utf-8")), int(opt("--pages") or 1)
    if opt("--out"):
        live = Path(opt("--out")).resolve()
        previews = live / "preview"
    else:
        try:
            import paths
            live = paths.data_dir() / "resume" / "live"
        except Exception:
            live = src.parent / "live"
        previews = live.parent / "preview"
    live.mkdir(parents=True, exist_ok=True)
    candidates = [Path(opt("--profile")).resolve()] if opt("--profile") else [src.parent, src.parent.parent]
    prof_dir = next((c for c in candidates if (c / "RESUME-RULES.md").exists()), None)
    base = re.sub(r"[^A-Za-z0-9]+", "_", doc["name"]).strip("_") + "_Resume"
    if opt("--suffix"):
        base += "_" + re.sub(r"[^A-Za-z0-9]+", "_", opt("--suffix")).strip("_")
    created = dt.datetime.strptime(opt("--meta-date"), "%Y-%m-%d") if opt("--meta-date") else None
    moved = None if opt("--out") else archive_live(live)
    out_docx, out_pdf = live / f"{base}.docx", live / f"{base}.pdf"

    if "--no-pdf" in args:
        build_docx(doc, out_docx, opt("--spacing") or "normal", created)
        print(f"Word file: {out_docx}\nNo PDF and no quality gate. Build again without --no-pdf before calling it done.")
        return

    best = None  # ((fits, fill), tier, result, text, fill): the fullest layout that stays inside the page limit
    with tempfile.TemporaryDirectory() as tmp:
        for tier in [opt("--spacing")] if opt("--spacing") else list(TIERS):
            tdocx, tpdf = Path(tmp) / f"{base}.docx", Path(tmp) / f"{base}.pdf"
            build_docx(doc, tdocx, tier, created)
            res = make_pdf(tdocx, tpdf)
            if not res["ok"]:
                shutil.copy(tdocx, out_docx)
                print(f"Word file: {out_docx}\nNo Word or LibreOffice found, so no PDF and no gate. Open the .docx in "
                      "Word, Google Docs or Pages, save it as a PDF with the same name, then screenshot the page and LOOK at it.")
                return
            text, n = pdf_text(tpdf)
            res["pages"] = res["pages"] or n
            imgs = render_pages(tpdf, Path(tmp) / tier)
            fill = page_fill(imgs[-1]) if imgs else None
            score = (res["pages"] is None or res["pages"] <= allowed, fill or 0)
            if best is None or score > best[0]:
                best = (score, tier, res, text, fill)
                shutil.copy(tdocx, out_docx)
                shutil.copy(tpdf, out_pdf)
            if not score[0] and best[0][0]:
                break  # roomier layouts only overflow more
    _, tier, res, text, fill = best
    if created:
        scrub_pdf(out_pdf, doc, created)
    imgs = render_pages(out_pdf, previews)

    print(f"Word file: {out_docx}\nPDF ({res['how']}): {out_pdf}\nLayout: {tier}")
    if moved:
        print(f"Previous version moved to {moved}. Say what changed in history/README.md.")
    if not prof_dir:
        print("No RESUME-RULES.md found: band, bullet counts and numbers were not checked. Use --profile <data folder>.")
    rows = gate(doc, read_profile(prof_dir), res, text, fill, allowed)
    pad = max(len(r[0]) for r in rows)
    print("\nQUALITY GATE")
    for name, status, note in rows:
        print(f"  {status:<4}  {name:<{pad}}  {note}")
    fails = sum(r[1] == "FAIL" for r in rows)
    print(f"\n{'FAIL: fix ' + str(fails) + ' item(s) in resume.md and build again.' if fails else 'Automatic checks passed.'}")
    if imgs:
        print("Now OPEN AND LOOK AT every page image (Claude Code: read the PNG. Codex: view the image):")
        print("\n".join(f"  {p}" for p in imgs))
    else:
        print("No page image could be made. Ask the user's OK for '<python> -m pip install pypdfium2 pillow' and build "
              "again, or open the PDF on screen, take a screenshot and look at it.")
    print("Then the visual checklist in docs/03, the gate line in PROGRESS.md, and show the page to the user.")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
