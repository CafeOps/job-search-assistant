"""Make a clean ZIP of the kit to share with someone else. Personal files are never included.

It copies ONLY the public kit files (an allowlist). It never includes the data folder or the old profile/
folder, and refuses if git tracks any file in profile/ or if the data folder sits inside the kit folder and
holds files. Share this ZIP, or the original download link. Never share your filled-in folders.

Usage: python tools/share_kit.py            -> job-search-assistant-share.zip next to the kit folder
"""
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402

ROOT = paths.kit_root()
ALLOW = ["AGENTS.md", "CLAUDE.md", "README.md", ".gitignore", "docs", "scanner", "templates", "tools", "examples"]
SKIP_PARTS = {"__pycache__", ".git", "out", "scan"}
# Only these file types are shared. Anything else in an allowed folder (a stray .env, a PDF, a CSV, a
# screenshot) is refused and listed, so a misplaced personal file can't ride along.
PUBLIC_EXT = {".md", ".py", ".ps1", ".sh", ".json", ".txt", ".docx", ".pdf", ".png", ""}
PRIVATE_NAMES = {"scanner-config.json", "seen.json", "outbox.json", "status.json", "firstseen.json",
                 "manifest.json", ".env"}


def tracked_profile_files():
    if not shutil.which("git") or not (ROOT / ".git").exists():
        return []
    r = subprocess.run(["git", "-C", str(ROOT), "ls-files", "profile"], capture_output=True, text=True)
    return [x for x in r.stdout.splitlines() if x.strip()]


def data_folder_problem():
    """The data folder must not sit inside the kit folder with files in it (they could ride along or be committed)."""
    data = paths.data_dir()
    if paths.inside(data, ROOT) and data.is_dir() and any(f.is_file() for f in data.rglob("*")):
        return (f"STOP: the data folder {data} is inside the kit folder and holds files. "
                "Move it outside the kit (for example Documents/Job Hunt), set it with: "
                "python tools/setup_check.py --data-dir <new path> and then run this again.")
    return None


def main():
    problem = data_folder_problem()
    if problem:
        sys.exit(problem)
    bad = tracked_profile_files()
    if bad:
        sys.exit("STOP: git is tracking personal files:\n  " + "\n  ".join(bad) +
                 "\nRemove them from git first: git rm -r --cached profile")
    out = ROOT.parent / "job-search-assistant-share.zip"
    n, refused = 0, []
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name in ALLOW:
            p = ROOT / name
            if not p.exists():
                continue
            files = [p] if p.is_file() else [f for f in p.rglob("*") if f.is_file()]
            for f in files:
                rel = f.relative_to(ROOT)
                top, ext = rel.parts[0], f.suffix.lower()
                if SKIP_PARTS & set(rel.parts) or f.suffix == ".pyc" or top == "profile":
                    continue
                private = f.name in PRIVATE_NAMES and top != "examples"
                # Word, PDF and image files are shared only from templates/ and the fictional example.
                binary_elsewhere = ext in (".docx", ".pdf", ".png") and top not in ("templates", "examples")
                if f.is_symlink() or ext not in PUBLIC_EXT or private or binary_elsewhere:
                    refused.append(str(rel))
                    continue
                z.write(f, Path(ROOT.name) / rel)
                n += 1
    print(f"Wrote {out} with {n} files. No personal data included.")
    if refused:
        print("Left out (not part of the public kit, check they belong here):\n  " + "\n  ".join(refused))


if __name__ == "__main__":
    main()
