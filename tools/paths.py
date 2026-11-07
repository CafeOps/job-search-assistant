"""Where the user's job-hunt files live. One resolver, shared by every tool and the scanner.

The kit folder holds only code. The user's personal files (profile, resumes, scan state, email settings)
live in a separate DATA FOLDER the user chooses. data_dir() finds it, in this order:
  1. the environment variable JOBHUNT_DATA_DIR
  2. the per-user config file, key "data_dir":
       Windows:    %APPDATA%/job-search-assistant/config.json
       macOS/Linux: ~/.config/job-search-assistant/config.json
  3. the old default: <kit>/profile (kept so earlier installs keep working)

Set it once with:  python tools/setup_check.py --data-dir <path>
"""
import json
import os
import sys
from pathlib import Path

APP = "job-search-assistant"
ENV_VAR = "JOBHUNT_DATA_DIR"
CLOUD_MARKERS = ("onedrive", "icloud", "clouddocs", "mobile documents", "dropbox", "google drive", "googledrive")


def kit_root():
    return Path(__file__).resolve().parent.parent


def config_path():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / APP / "config.json"
    return Path.home() / ".config" / APP / "config.json"


def legacy_dir():
    return kit_root() / "profile"


def _from_config():
    p = config_path()
    try:
        value = json.loads(p.read_text(encoding="utf-8")).get("data_dir")
    except (OSError, ValueError, AttributeError):
        return None
    return Path(value).expanduser() if value else None


def is_chosen():
    """True when the user (or the environment) picked a data folder; False when only the legacy default applies."""
    return bool(os.environ.get(ENV_VAR, "").strip()) or _from_config() is not None


def data_dir():
    env = os.environ.get(ENV_VAR, "").strip()
    if env:
        return Path(env).expanduser()
    return _from_config() or legacy_dir()


def set_data_dir(path):
    """Create the folder and remember it in the per-user config file. Returns the absolute path."""
    p = Path(path).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    cfg_file = config_path()
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
        if not isinstance(cfg, dict):
            cfg = {}
    except (OSError, ValueError):
        cfg = {}
    cfg["data_dir"] = str(p)
    cfg_file.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


def in_cloud_sync(path):
    """True when the path looks like it sits inside OneDrive, iCloud, Dropbox or Google Drive."""
    try:
        text = str(Path(path).expanduser().resolve()).lower()
    except OSError:
        text = str(path).lower()
    return any(m in text for m in CLOUD_MARKERS)


def inside(child, parent):
    """True when child is the same as, or inside, parent."""
    a = os.path.normcase(os.path.realpath(str(child)))
    b = os.path.normcase(os.path.realpath(str(parent)))
    return a == b or a.startswith(b + os.sep)


if __name__ == "__main__":
    print(data_dir())
