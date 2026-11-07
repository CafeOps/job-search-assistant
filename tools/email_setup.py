"""Daily-email setup wizard (SMTP). The AI runs the steps. The USER types the password.

Steps:
  python tools/email_setup.py --configure --provider gmail --from me@gmail.com --to me@gmail.com
      writes the email block into <data folder>/scanner-config.json (stops if `keyring` is missing)
  python tools/email_setup.py --install-deps
      installs `keyring` into this Python. Ask the user first. Nothing else installs anything.
  python tools/email_setup.py --password
      THE USER runs this themselves, in a terminal on their own computer. A small password box opens (a
      hidden prompt if there is no screen) and the user pastes the app password there. It is saved in Windows
      Credential Manager / macOS Keychain, and never printed, logged, passed as an argument or environment
      variable, or shown to the AI. With no secure store, or no GUI and no interactive terminal, it refuses
      and prints the exact command for the user to run.
  python tools/email_setup.py --test
      sends one test email (only after the user said yes to a test)
  python tools/email_setup.py --remove
      deletes the saved password

Gmail needs 2-Step Verification on, then an app password: https://myaccount.google.com/apppasswords
Some accounts can't make app passwords (work or school accounts, Advanced Protection, security-key-only
sign-in). Then use another address, or skip email and read the digest file.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402

ROOT = paths.kit_root()
CFG = paths.data_dir() / "scanner-config.json"
SERVICE = "job-search-assistant-smtp"
PROVIDERS = {
    "gmail": ("smtp.gmail.com", 465),
    "outlook": ("smtp-mail.outlook.com", 587),
    "yahoo": ("smtp.mail.yahoo.com", 465),
    "icloud": ("smtp.mail.me.com", 587),
}


def load():
    """The scanner config if there is one, else an empty dict. The example config is never copied in:
    its made-up search settings would silently become the user's real ones."""
    if CFG.exists():
        return json.loads(CFG.read_text(encoding="utf-8"))
    return {}


def command(flag):
    return f'"{sys.executable}" tools/email_setup.py {flag}'


def ensure_keyring():
    """Return the keyring module, or stop. Never installs anything (that is --install-deps, with the user's OK)."""
    try:
        import keyring
    except ImportError:
        sys.exit(f"The 'keyring' package is missing. Run: {command('--install-deps')} (ask the user first)")
    try:
        name = type(keyring.get_keyring()).__name__.lower()
    except Exception as e:
        sys.exit(f"The password store could not start ({type(e).__name__}). Email can't be set up safely. "
                 "Skip email and use digest-only mode (email mode none).")
    if "fail" in name or "plaintext" in name or "null" in name:
        sys.exit(f"No secure password store is available here ({name}). Email can't be set up safely. "
                 "Skip email and use digest-only mode (email mode none).")
    return keyring


def install_deps():
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    cmd = [sys.executable, "-m", "pip", "install", "keyring"] + ([] if in_venv else ["--user"])
    print("Installing the 'keyring' package into this Python: " + " ".join(cmd))
    subprocess.run(cmd, check=True)
    ensure_keyring()
    print("keyring is installed and a secure password store is available.")


def gui_available():
    try:
        import tkinter  # noqa: F401
    except Exception:
        return False
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        return False
    return True


def interactive():
    return sys.stdin is not None and sys.stdin.isatty()


def configure(a):
    ensure_keyring()        # stop before writing anything if the password store is not ready
    cfg = load()
    had_config = CFG.exists()
    if a.smtp_host or a.smtp_port:  # explicit settings win over the provider preset
        host, port = a.smtp_host, a.smtp_port
    else:
        host, port = PROVIDERS.get(a.provider, (None, None))
    if not host or not port:
        sys.exit("Unknown provider. Pass --smtp-host and --smtp-port.")
    cfg["email"] = {"from": a.sender, "to": a.to or a.sender, "smtp_host": host, "smtp_port": int(port),
                    "subject_prefix": cfg.get("email", {}).get("subject_prefix", "Job picks")}
    CFG.parent.mkdir(parents=True, exist_ok=True)
    CFG.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    if not had_config:
        print(f"NOTE: {CFG} now holds ONLY the email settings. The scanner settings (keywords, places, pay) "
              "do not exist yet: the intake interview still has to create them before a scan can run.")
    print(f"Email configured: from {a.sender} to {cfg['email']['to']} via {host}:{port}. "
          "Next: python tools/email_setup.py --password (the user types the password).")


def password_box():
    """Ask for the app password in a local window. Fallback: hidden terminal input."""
    try:
        import tkinter as tk
        from tkinter import simpledialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        pw = simpledialog.askstring("Job search assistant: email password",
                                    "Paste the APP PASSWORD for the sending address.\n"
                                    "It is saved in your computer's password store, not shown to the AI.",
                                    show="*", parent=root)
        root.destroy()
        return pw
    except Exception:
        import getpass
        return getpass.getpass("App password (typing is hidden): ")


def clean_password(cfg, pw):
    """Gmail shows app passwords in groups of four with spaces, so strip them. Other providers: keep as typed."""
    if cfg.get("email", {}).get("smtp_host") == "smtp.gmail.com":
        return pw.replace(" ", "")
    return pw


def save_password():
    cfg = load()
    sender = cfg.get("email", {}).get("from")
    if not sender:
        sys.exit("Run --configure first.")
    keyring = ensure_keyring()
    if not gui_available() and not interactive():
        sys.exit("STOP: this environment has no screen and no interactive terminal, so the password can't be typed "
                 "safely here. The USER must run this command themselves, in a terminal on their own computer "
                 f"(not through the AI tool): {command('--password')}")
    pw = password_box()
    if not pw:
        sys.exit("No password entered. Nothing saved.")
    try:
        keyring.set_password(SERVICE, sender, clean_password(cfg, pw))
    except Exception as e:  # never echo the password, only the store's error type
        sys.exit(f"The password store refused to save it ({type(e).__name__}). Nothing was saved.")
    print("Password saved in the system password store. To revoke it completely, also delete the app "
          "password in your email account's security settings.")


def remove():
    keyring = ensure_keyring()
    sender = load().get("email", {}).get("from")
    try:
        keyring.delete_password(SERVICE, sender)
        print("Saved password removed.")
    except Exception:
        print("No saved password found.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--configure", action="store_true")
    ap.add_argument("--provider", default="gmail")
    ap.add_argument("--from", dest="sender")
    ap.add_argument("--to")
    ap.add_argument("--smtp-host")
    ap.add_argument("--smtp-port", type=int)
    ap.add_argument("--install-deps", action="store_true")
    ap.add_argument("--password", action="store_true")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--remove", action="store_true")
    a = ap.parse_args()
    if a.install_deps:
        install_deps()
    elif a.configure:
        if not a.sender:
            sys.exit("--from is required")
        configure(a)
    elif a.password:
        save_password()
    elif a.test:
        r = subprocess.run([sys.executable, str(ROOT / "scanner" / "send_email.py"), "--test"])
        sys.exit(r.returncode)
    elif a.remove:
        remove()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
