"""Find old resumes, CVs and cover letters on this computer and COPY them into <data folder>/source/harvest/.

Old documents are the best intake material: real titles, dates and wording the user wrote at the time.
This script never moves, renames or deletes the originals. It only reads and copies.

Usage:
  py tools/harvest.py --roots                 # only PRINT the folders it would search, then exit
  py tools/harvest.py                         # list candidates (default); writes candidates.md + manifest.json
  py tools/harvest.py --copy --pick 3,a1b2c3d4   # copy only these rows or ids from candidates.md
  py tools/harvest.py --copy --all            # copy every candidate in the manifest
  py tools/harvest.py --root "D:\\Old Laptop Backup"   # add a folder to search (repeatable)
  py tools/harvest.py --only "D:\\Old Laptop Backup"   # search ONLY this folder, no default folders (repeatable)

--copy does NOT rescan. It reads manifest.json written by the last listing, so the numbers and ids the
user approved always point at the same files. Before copying it checks each original still exists and
still has the same SHA-256.

Searched by default: Documents, Downloads, Desktop (real Windows known-folder paths), OneDrive, Dropbox,
Google Drive, iCloud Drive and ~/Library/CloudStorage/* on a Mac. Matching: file name first (resume, cv,
cover letter, ...), then, for .pdf/.docx/.rtf files with unclear names, a look at the first page of text.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
import zlib
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # odd characters in file names on Windows
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402

KIT_ROOT = paths.kit_root()
DEST = paths.data_dir() / "source" / "harvest"
HOME = Path.home()
EXTS = {".pdf", ".docx", ".doc", ".odt", ".rtf", ".txt", ".pages"}
CONTENT_EXTS = {".pdf", ".docx", ".rtf"}  # plain-text notes and logs mention "experience" too often
SKIP_DIRS = {"node_modules", ".git", "AppData", "Library", "$RECYCLE.BIN", ".venv", "venv", "__pycache__",
             ".cache", "site-packages"}
LIBRARY_KEEP = {"CloudStorage", "Mobile Documents"}  # the only parts of ~/Library worth searching
NAME_HINT = re.compile(r"resume|résumé|curriculum|(^|[^a-z])cv([^a-z]|$)|cover[ _-]?letter|coverletter|"
                       r"lettre de motivation", re.I)
TEXT_HINT = re.compile(r"\b(experience|employment history|work history)\b.*\b(education|skills)\b|"
                       r"\bdear (hiring|recruit|sir|madam)|\bsincerely\b|\bcover letter\b", re.I | re.S)
MAX_MB = 20
PROGRESS_SECONDS = 2.0


# ---------- roots ----------

def _inside_kit(p):
    """True for the kit folder and the user's data folder: neither is searched."""
    return paths.inside(p, KIT_ROOT) or paths.inside(p, paths.data_dir())


def windows_known_folders():
    """Real Documents / Downloads / Desktop paths from the registry (they move when OneDrive backs them up)."""
    found = []
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
        names = {"Personal": "Documents", "{374DE290-123F-4565-9164-39C4925E467B}": "Downloads",
                 "Desktop": "Desktop"}
        for value_name in names:
            try:
                raw, _ = winreg.QueryValueEx(key, value_name)
                found.append(Path(os.path.expandvars(raw)))
            except OSError:
                continue
        winreg.CloseKey(key)
    except Exception:
        pass
    return found


def discover_roots(extra=(), only=()):
    """Return a list of (path, label). Only existing folders, de-duplicated, never the kit itself.
    With `only`, search just those folders and none of the default ones."""
    if only:
        cands = [(Path(x).expanduser(), "chosen with --only") for x in only]
    else:
        cands = [(p, "known folder") for p in windows_known_folders()] if sys.platform == "win32" else []
        for name in ("Documents", "Downloads", "Desktop"):
            cands.append((HOME / name, "home folder"))
        for env in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
            v = os.environ.get(env)
            if v:
                cands.append((Path(v), "OneDrive"))
        for p in sorted(HOME.glob("OneDrive*")):
            cands += [(p, "OneDrive"), (p / "Documents", "OneDrive"), (p / "Desktop", "OneDrive")]
        for p in sorted(HOME.glob("Dropbox*")):
            cands.append((p, "Dropbox"))
        for name in ("Google Drive", "My Drive", "iCloud Drive"):
            cands.append((HOME / name, name))
        cs = HOME / "Library" / "CloudStorage"
        if sys.platform == "darwin" or cs.exists():
            if cs.is_dir():
                try:
                    for p in sorted(cs.iterdir()):
                        if p.is_dir():
                            cands.append((p, "Mac cloud drive"))
                except OSError:
                    pass
            cands.append((HOME / "Library" / "Mobile Documents" / "com~apple~CloudDocs", "iCloud Drive"))
        cands += [(Path(x), "added with --root") for x in extra]

    seen, out = set(), []
    for p, label in cands:
        try:
            if not p.is_dir() or _inside_kit(p):
                continue
            key = os.path.normcase(os.path.realpath(str(p)))
        except OSError:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append((p, label))
    return out


# ---------- reading content ----------

def _pdf_fallback_text(p):
    """Tiny stdlib PDF text grab: plain and flate-compressed streams, simple (text) strings only."""
    try:
        with open(p, "rb") as f:
            data = f.read(4 << 20)
    except OSError:
        return ""
    chunks = [data]
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.S):
        try:
            chunks.append(zlib.decompress(m.group(1)))
        except Exception:
            continue
    parts = []
    for c in chunks:
        for s in re.findall(rb"\(((?:\\.|[^\\()])*)\)\s*(?:Tj|TJ|'|\")|\[((?:[^\]]*))\]\s*TJ", c):
            raw = s[0] or b" ".join(re.findall(rb"\(((?:\\.|[^\\()])*)\)", s[1]))
            raw = re.sub(rb"\\([()\\])", rb"\1", raw)
            parts.append(raw.decode("latin-1", "ignore"))
        if sum(map(len, parts)) > 6000:
            break
    text = " ".join(parts)
    return text if len(re.findall(r"[A-Za-z]{3,}", text)) >= 5 else ""


def read_content(p):
    """First page or so of text. Returns None when a PDF could not be read at all."""
    ext = p.suffix.lower()
    try:
        if ext == ".docx":
            with zipfile.ZipFile(p) as z:
                xml = z.read("word/document.xml").decode("utf-8", "ignore")
            return re.sub(r"<[^>]+>", " ", xml)[:6000]
        if ext in (".txt", ".md", ".rtf"):
            return p.read_text("utf-8", "ignore")[:6000]
        if ext == ".pdf":
            if shutil.which("pdftotext"):
                try:
                    r = subprocess.run(["pdftotext", "-l", "2", str(p), "-"], capture_output=True, text=True,
                                       timeout=20)
                    if r.stdout.strip():
                        return r.stdout[:6000]
                except Exception:
                    pass
            text = _pdf_fallback_text(p)
            return text[:6000] if text else None
    except Exception:
        return ""
    return ""


# ---------- hashing ----------

def sha_of(p):
    """SHA-256 of a file, or of a bundle directory (.pages on macOS can be a folder)."""
    p = Path(p)
    h = hashlib.sha256()
    if p.is_dir():
        for sub in sorted(x for x in p.rglob("*") if x.is_file()):
            h.update(sub.relative_to(p).as_posix().encode("utf-8", "ignore"))
            with open(sub, "rb") as f:
                for b in iter(lambda: f.read(1 << 20), b""):
                    h.update(b)
        return h.hexdigest()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _bundle_size(p):
    total = 0
    for sub in Path(p).rglob("*"):
        try:
            if sub.is_file():
                total += sub.stat().st_size
        except OSError:
            continue
    return total


# ---------- scanning ----------

class Progress:
    def __init__(self, stream=None, every=PROGRESS_SECONDS):
        self.stream = stream if stream is not None else sys.stderr
        self.every = every
        self.last = time.monotonic()
        self.folders = 0
        self.cands = 0

    def tick(self, folder):
        if self.stream is None:
            return
        now = time.monotonic()
        if now - self.last >= self.every:
            self.last = now
            print(f"scanned {self.folders} folders, {self.cands} candidates, now in {folder}",
                  file=self.stream, flush=True)


def _walk(roots, visited, skipped, progress):
    """Yield (path, is_bundle). Each real folder is visited once, so loops and overlaps are harmless."""
    for root in roots:
        stack = [Path(root)]
        while stack:
            d = stack.pop()
            try:
                real = os.path.normcase(os.path.realpath(str(d)))
                if real in visited or _inside_kit(d):
                    continue
                visited.add(real)
                progress.folders += 1
                progress.tick(d)
                entries = list(os.scandir(d))
            except (PermissionError, OSError) as e:
                skipped.append((str(d), type(e).__name__))
                continue
            for e in entries:
                try:
                    name = e.name
                    is_dir = e.is_dir()
                except OSError:
                    continue
                ext = os.path.splitext(name)[1].lower()
                if is_dir:
                    if ext == ".pages":  # macOS bundle: a document, not a folder to search
                        yield Path(e.path), True
                    elif name == "Library":
                        for keep in LIBRARY_KEEP:
                            sub = Path(e.path) / keep
                            if sub.is_dir():
                                stack.append(sub)
                    elif name not in SKIP_DIRS and not name.startswith("."):
                        stack.append(Path(e.path))
                elif ext in EXTS:
                    yield Path(e.path), False


def scan(roots, progress_stream=None, quiet=False):
    """Walk the roots and return a result dict. Ctrl+C stops cleanly and keeps what was found."""
    progress = Progress(None if quiet else progress_stream)
    visited, skipped, found, hashes = set(), [], [], set()
    unreadable_pdfs = 0
    interrupted = False
    try:
        for f, is_bundle in _walk([Path(r) for r in roots], visited, skipped, progress):
            try:
                st = f.stat()
                size = _bundle_size(f) if is_bundle else st.st_size
            except OSError:
                continue
            if size > MAX_MB * 1024 * 1024 or size == 0:
                continue
            reason = None
            if NAME_HINT.search(f.stem):
                reason = "name"
            elif f.suffix.lower() in CONTENT_EXTS and not is_bundle:
                text = read_content(f)
                if text is None:
                    unreadable_pdfs += 1
                elif TEXT_HINT.search(text):
                    reason = "content"
            if not reason:
                continue
            try:
                h = sha_of(f)
            except OSError as e:
                skipped.append((str(f), type(e).__name__))
                continue
            if h in hashes:  # same file saved twice
                continue
            hashes.add(h)
            found.append({"path": str(f), "size": size, "mtime": st.st_mtime, "reason": reason,
                          "sha256": h, "id": h[:8], "bundle": is_bundle})
            progress.cands = len(found)
    except KeyboardInterrupt:
        interrupted = True
        print("\nStopped by Ctrl+C. Writing what was found so far.", file=sys.stderr)
    found.sort(key=lambda c: (-c["mtime"], c["path"]))
    for i, c in enumerate(found, 1):
        c["n"] = i
    return {"candidates": found, "skipped": skipped, "unreadable_pdfs": unreadable_pdfs,
            "interrupted": interrupted, "folders": progress.folders, "roots": [str(r) for r in roots],
            "pdftotext": bool(shutil.which("pdftotext"))}


def write_listing(result, dest):
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    cands = result["candidates"]
    manifest = {"generated": datetime.now().isoformat(timespec="seconds"), "roots": result["roots"],
                "candidates": [{**c, "mtime_iso": datetime.fromtimestamp(c["mtime"]).isoformat(timespec="seconds")}
                               for c in cands]}
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = ["# Harvest candidates", ""]
    if result["interrupted"]:
        lines += ["**Scan was stopped early (Ctrl+C). This list is partial.**", ""]
    lines += ["Pick rows by number or by id: `--copy --pick 3,a1b2c3d4`, or `--copy --all`.", "",
              "| # | id | Modified | Matched by | File |", "|---|---|---|---|---|"]
    lines += [f"| {c['n']} | {c['id']} | {datetime.fromtimestamp(c['mtime']):%Y-%m-%d} | {c['reason']} | "
              f"{c['path']} |" for c in cands]
    lines += ["", f"Scanned {result['folders']} folders in {len(result['roots'])} roots."]
    sk = result["skipped"]
    if sk:
        lines += ["", f"**{len(sk)} folders could not be read** (permission or disk errors). First {min(10, len(sk))}:"]
        lines += [f"- {p} ({why})" for p, why in sk[:10]]
    if result["unreadable_pdfs"]:
        lines += ["", f"{result['unreadable_pdfs']} PDFs could not be read for content; only their names were checked."]
        if not result["pdftotext"]:
            lines += ["(Installing poppler's `pdftotext` would let the scan read most of them.)"]
    (dest / "candidates.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return "\n".join(lines)


# ---------- copying ----------

class PickError(Exception):
    pass


def parse_picks(spec, candidates):
    """Turn '3,a1b2c3d4' into a list of candidates. Raises PickError on empty or unknown tokens."""
    tokens = [t.strip().lower() for t in (spec or "").split(",") if t.strip()]
    if not tokens:
        raise PickError("--pick is empty. Give row numbers or ids from candidates.md (e.g. --pick 1,3), "
                        "or use --all to copy everything. Nothing was copied.")
    by_id = {c["id"]: c for c in candidates}
    by_n = {str(c["n"]): c for c in candidates}
    chosen, bad = [], []
    for t in tokens:
        c = by_id.get(t) or by_n.get(t)
        if c is None:
            bad.append(t)
        elif c not in chosen:
            chosen.append(c)
    if bad:
        raise PickError(f"Not in the list: {', '.join(bad)}. Use row numbers or ids from candidates.md. "
                        "Nothing was copied.")
    return chosen


def safe_name(stem):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-.") or "file"


def dest_name(c):
    p = Path(c["path"])
    date = datetime.fromtimestamp(c["mtime"]).strftime("%Y-%m-%d")
    return f"{date}_{safe_name(p.stem)}_{c['sha256'][:8]}{p.suffix.lower()}"


def copy_from_manifest(dest, pick=None, copy_all=False, out=print):
    """Copy manifest entries. Returns (copied, skipped) lists; raises PickError for bad input."""
    dest = Path(dest)
    mf = dest / "manifest.json"
    if not mf.exists():
        raise PickError("No manifest.json found. Run the listing first (py tools/harvest.py), "
                        "review it with the user, then copy.")
    cands = json.loads(mf.read_text(encoding="utf-8"))["candidates"]
    if copy_all and pick is not None:
        raise PickError("Use either --all or --pick, not both. Nothing was copied.")
    if copy_all:
        chosen = cands
    elif pick is not None:
        chosen = parse_picks(pick, cands)
    else:
        raise PickError("Say what to copy: --pick 1,3 (rows or ids from candidates.md) or --all. "
                        "Nothing was copied.")
    copied, skipped = [], []
    index_rows = []
    for c in chosen:
        src = Path(c["path"])
        if not src.exists():
            skipped.append((c, "original no longer exists"))
            continue
        try:
            current = sha_of(src)
        except OSError as e:
            skipped.append((c, f"cannot read original ({type(e).__name__})"))
            continue
        if current != c["sha256"]:
            skipped.append((c, "original changed since the list was made; re-run the listing"))
            continue
        name = dest_name(c)
        target = dest / name
        if target.exists():
            skipped.append((c, "already copied"))
            continue
        if src.is_dir():
            shutil.copytree(src, target)
        else:
            shutil.copy2(src, target)
        copied.append((c, name))
        index_rows.append(f"| {name} | {c['path']} | {datetime.fromtimestamp(c['mtime']):%Y-%m-%d} | "
                          f"{c['sha256']} |")
    idx = dest / "INDEX.md"
    if index_rows:
        if not idx.exists():
            idx.write_text("# Harvested files (copies; originals untouched)\n\n"
                           "| copy | original | modified | sha256 |\n|---|---|---|---|\n", encoding="utf-8")
        with open(idx, "a", encoding="utf-8") as f:
            f.write("\n".join(index_rows) + "\n")
    return copied, skipped


# ---------- CLI ----------

def main(argv=None):
    ap = argparse.ArgumentParser(description="Find old resumes and cover letters and copy them (never move).")
    ap.add_argument("--roots", action="store_true", help="only print the folders that would be searched")
    ap.add_argument("--root", action="append", default=[], help="add a folder to search (repeatable)")
    ap.add_argument("--only", action="append", default=[],
                    help="search only this folder, none of the default ones (repeatable)")
    ap.add_argument("--copy", action="store_true", help="copy files listed in manifest.json (no rescan)")
    ap.add_argument("--pick", default=None, help="comma-separated row numbers or ids from candidates.md")
    ap.add_argument("--all", action="store_true", help="with --copy: copy every candidate")
    args = ap.parse_args(argv)

    if args.roots:
        found = discover_roots(args.root, args.only)
        if not found:
            print("No folders found to search. Add one with --root \"<folder>\".")
        for p, label in found:
            print(f"{p}    ({label})")
        print(f"\n{len(found)} folders. Nothing was scanned.")
        return 0

    if args.copy:
        try:
            copied, skipped = copy_from_manifest(DEST, args.pick, args.all)
        except PickError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 2
        for c, why in skipped:
            print(f"Skipped {c['path']}: {why}")
        print(f"\nCopied {len(copied)} files, skipped {len(skipped)}. Folder: {DEST}")
        if copied:
            print(f"Index: {DEST / 'INDEX.md'}")
        return 0

    roots = [p for p, _ in discover_roots(args.root, args.only)]
    if args.only and not roots:
        print("None of the --only folders exist (or they are the kit or data folder). Nothing searched.",
              file=sys.stderr)
        return 2
    print(f"Searching {len(roots)} folders. This can take a few minutes; progress prints every 2 seconds.",
          file=sys.stderr)
    result = scan(roots, progress_stream=sys.stderr)
    print(write_listing(result, DEST))
    print(f"\n{len(result['candidates'])} candidates. Nothing copied. Review the list with the user, then run "
          "--copy --pick 1,2 (rows or ids) or --copy --all.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
