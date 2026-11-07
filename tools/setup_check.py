"""Setup check. The AI runs this first, before the harvest or the interview.

It checks what this computer can do and writes the answer to SETUP.md in the user's data folder, so later
steps don't fail halfway. It changes nothing except creating the data folder and that one file.

Usage:
  python tools/setup_check.py                      # check, and show which data folder is in use
  python tools/setup_check.py --data-dir <path>    # choose the data folder (created if missing), then check
  python tools/setup_check.py --check              # read-only: print the same report, write NOTHING
"""
import importlib.util
import os
import platform
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402

ROOT = paths.kit_root()

TEMPLATES = ["PROFILE.md", "TARGETS.md", "SCREEN.md", "VOICE.md", "NUMBERS.md", "STORIES.md",
             "DECISIONS.md", "PIPELINE.md", "PROGRESS.md", "RESUME-RULES.md", "AUTHORIZATIONS.md"]


def has_module(name):
    return importlib.util.find_spec(name) is not None


def tool(name):
    return shutil.which(name)


def writable_target(data):
    """True when `data` (or, if it does not exist yet, its nearest existing parent) can be written. Writes nothing."""
    p = Path(data)
    while not p.exists() and p != p.parent:
        p = p.parent
    return p.is_dir() and os.access(str(p), os.W_OK)


NET_PROBES = ["https://www.linkedin.com", "https://boards-api.greenhouse.io", "https://www.example.com"]


def net_ok():
    """True when any of the job sources the scan uses (or example.com) answers within 5 seconds.
    Testing the real sources avoids false 'no network' answers on networks that filter example.com."""
    import urllib.error
    import urllib.request
    for url in NET_PROBES:
        try:
            req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as r:
                if r.status < 500:
                    return True
        except urllib.error.HTTPError as e:  # the server answered, so the network works
            if e.code < 500:
                return True
        except Exception:
            continue
    return False


def keyring_state():
    """-> (ok, detail). Never installs anything."""
    if not has_module("keyring"):
        return False, "keyring is not installed"
    try:
        import keyring
        name = type(keyring.get_keyring()).__name__
    except Exception as e:
        return False, f"keyring failed to load ({type(e).__name__})"
    if any(bad in name.lower() for bad in ("fail", "plaintext", "null")):
        return False, f"no secure backend ({name})"
    return True, f"backend {name}"


def gui_available():
    if not has_module("tkinter"):
        return False
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        return False
    return True


def scheduler_state(os_name):
    if os_name == "Windows":
        found = tool("schtasks") or tool("powershell") or tool("pwsh")
        return bool(found), found or "schtasks and PowerShell not found"
    if os_name == "macOS":
        found = tool("launchctl")
        return bool(found), found or "launchctl not found"
    found = tool("crontab")
    return bool(found), found or "crontab not found"


def probably_own_computer(data):
    home_ok = Path.home().is_dir()
    sandbox = ("/mnt/data", "/home/sandbox", "/mnt/user-data", "/tmp")
    places = [str(Path(data).resolve()), str(Path.home()), str(ROOT), str(Path.cwd())]
    in_sandbox = any(p.replace("\\", "/").startswith(sandbox) for p in places)
    return home_ok and writable_target(data) and not in_sandbox, in_sandbox


def abilities(data, os_name):
    """Probe what this environment can do. Returns rows of (ability, answer, detail). Writes nothing."""
    rows = []
    rows.append(("Local file write (data folder)", "yes" if writable_target(data) else "NO", str(data)))
    rows.append(("Terminal", "yes", "this script is running"))
    net = net_ok()
    rows.append(("Network", "yes" if net else "NO", "a job source answered within 5 seconds"
                 if net else "LinkedIn, Greenhouse and example.com did not answer in 5 seconds"))
    tty = sys.stdin is not None and sys.stdin.isatty()
    rows.append(("Interactive input", "yes" if tty else "NO",
                 "a person can type in this terminal" if tty else "no interactive terminal here"))
    gui = gui_available()
    rows.append(("GUI for the password box", "yes" if gui else "NO", "tkinter usable" if gui else "tkinter missing or no display"))
    ok, detail = keyring_state()
    rows.append(("Secure credential store", "yes" if ok else "NO", detail))
    ok, detail = scheduler_state(os_name)
    rows.append(("Scheduler for the daily scan", "yes" if ok else "NO", detail))
    own, in_sandbox = probably_own_computer(data)
    rows.append(("Runs on the user's own computer", "probably yes" if own else "probably NO",
                 "home folder and data folder look like a real user machine" if own else
                 ("paths look like a sandbox" if in_sandbox else "home or data folder not usable")
                 + ". If this is a cloud sandbox, the daily scan and email must be set up on the user's own computer."))
    rows.append(("Browser control", "ask the AI tool", "Cannot be probed from Python. Ask the AI tool whether it can "
                 "drive a browser, then test it as described in docs/07."))
    rows.append(("File uploads", "ask the AI tool", "Cannot be probed from Python. Ask the AI tool whether the user "
                 "can attach files in this chat, then test it as described in docs/07."))
    return rows


def check(data, write=True):
    rows, fixes = [], []

    def row(item, ok, detail, fix=None):
        rows.append((item, "OK" if ok else "MISSING", detail))
        if not ok and fix:
            fixes.append(f"- {item}: {fix}")

    os_name = "macOS" if platform.system() == "Darwin" else platform.system()
    row("Operating system", True, f"{os_name} {platform.release()}")
    v = sys.version_info
    row("Python", v >= (3, 9), f"{v.major}.{v.minor}.{v.micro} at {sys.executable}",
        "Install Python 3.12 from python.org (Windows: tick 'Add python.exe to PATH'). "
        "Or, with the user's OK: Windows `winget install Python.Python.3.12`, macOS `brew install python`.")

    missing = [t for t in TEMPLATES if not (ROOT / "templates" / "profile" / t).exists()]
    row("Kit files complete", not missing, "all templates present" if not missing else f"missing: {missing}",
        "The download is incomplete. Download the kit again as a ZIP from the original link.")

    if write:
        try:
            data.mkdir(parents=True, exist_ok=True)
            probe = data / ".write-test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            row("Can write to the data folder", True, str(data))
        except OSError as e:
            row("Can write to the data folder", False, str(e),
                "Pick another data folder you own (for example Documents\\Job Hunt) with --data-dir.")
    else:
        row("Can write to the data folder", writable_target(data), f"{data} (checked without writing)",
            "Pick another data folder you own with --data-dir.")

    row("Data folder outside cloud sync", not paths.in_cloud_sync(data), str(data),
        "Optional: the data folder is inside a synced folder (OneDrive, iCloud, Dropbox, Google Drive), so your "
        "personal files will sync to that cloud service. Tell the user; move it only if they ask.")

    row("PDF text tool (pdftotext)", bool(tool("pdftotext")), tool("pdftotext") or "not found",
        "Optional. Helps read old PDF resumes. Windows: `winget install oschwartz10612.Poppler`, "
        "macOS: `brew install poppler`. Without it, PDFs are matched by file name only.")
    row("Word files (python-docx)", has_module("docx"), "importable" if has_module("docx") else "not installed",
        f"Needed to build the resume as a Word file: `\"{sys.executable}\" -m pip install python-docx`")
    row("Password store package (keyring)", has_module("keyring"), "importable" if has_module("keyring") else "not installed",
        f"Needed only for the daily email (ask the user first): `\"{sys.executable}\" tools/email_setup.py --install-deps`")
    row("Pandoc (optional)", bool(tool("pandoc")), tool("pandoc") or "not found",
        "Optional fallback for making a Word file from text.")
    row("git (optional)", bool(tool("git")), tool("git") or "not found",
        "Not needed. The kit works from a downloaded ZIP.")
    return os_name, rows, fixes


def report(data, os_name, rows, fixes, abil):
    lines = [f"# Setup check ({datetime.now():%Y-%m-%d %H:%M})", "",
             f"Data folder: `{data}`", "",
             f"Python command to use for every kit command: `{sys.executable}`", "",
             "| Item | Status | Detail |", "|---|---|---|"]
    lines += [f"| {a} | {b} | {c} |" for a, b, c in rows]
    lines += ["", "## Abilities", "",
              "What this environment can do, probed by the script. Plan the setup around these answers, not "
              "around which AI tool is running.", "",
              "| Ability | Answer | Detail |", "|---|---|---|"]
    lines += [f"| {a} | {b} | {c} |" for a, b, c in abil]
    lines += ["", "## To fix (ask the user before installing anything)"] + (fixes or ["- Nothing."])
    return "\n".join(lines) + "\n"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    read_only = "--check" in argv
    if read_only and "--data-dir" in argv:
        sys.exit("--check writes nothing, so it can't be combined with --data-dir. Run them one after the other.")
    if "--data-dir" in argv:
        i = argv.index("--data-dir")
        if i + 1 >= len(argv):
            sys.exit("--data-dir needs a folder path.")
        wanted = Path(argv[i + 1]).expanduser().resolve()
        if paths.inside(wanted, ROOT):
            sys.exit("That folder is inside the kit folder. Personal files must live OUTSIDE the kit, so updating "
                     "or sharing the kit can never touch them. Pick another folder, for example Documents\\Job Hunt.")
        data = paths.set_data_dir(argv[i + 1])
        print(f"Data folder set to: {data}")
        if paths.in_cloud_sync(data):
            print("WARNING: this folder is inside a cloud-synced location (OneDrive, iCloud, Dropbox or Google "
                  "Drive). Your personal files will sync to that service. Tell the user; move it only if they ask.")
    elif not paths.is_chosen():
        print("No data folder chosen yet. Ask the user where to keep their job-hunt files (suggest "
              "Documents\\Job Hunt or ~/Job Hunt), then run: "
              f"\"{sys.executable}\" tools/setup_check.py --data-dir <path>")
        print(f"(Until then the old default is used: {paths.legacy_dir()})\n")
    data = paths.data_dir()
    print(f"Data folder: {data}")
    os_name, rows, fixes = check(data, write=not read_only)
    out = report(data, os_name, rows, fixes, abilities(data, os_name))
    if read_only:
        out += "\n(--check: read-only run. Nothing was written, no folder was created, SETUP.md was not updated.)\n"
    else:
        try:
            (data / "SETUP.md").write_text(out, encoding="utf-8")
        except OSError:
            pass
    print(out)


if __name__ == "__main__":
    main()
