"""Send a digest by email over SMTP. No AI is involved in delivery.

Set up with `tools/email_setup.py`: the user types the app password into a local password box (never the
chat), and it is kept in the operating system's credential store (Windows Credential Manager / macOS
Keychain) through the `keyring` package, never in this repo.

Usage (the run scripts call this):
  python scanner/send_email.py --digest "<path to digest .txt>" --batch "<batch id>"
  python scanner/send_email.py --test        # sends a short test message

Prints exactly "SENT <batch id>" (or "SENT test") and exits 0 only after the mail server accepted it.
"""
import argparse
import datetime as dt
import json
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import paths  # noqa: E402

SERVICE = "job-search-assistant-smtp"


def load_email_config():
    cfg_path = paths.data_dir() / "scanner-config.json"
    if not cfg_path.exists():
        sys.exit(f"No scanner-config.json in {cfg_path.parent} yet. Run the intake first.")
    email = json.loads(cfg_path.read_text(encoding="utf-8")).get("email", {})
    for key in ("to", "from", "smtp_host", "smtp_port"):
        if not email.get(key):
            sys.exit(f"Email is not set up (missing email.{key}). Run: python tools/email_setup.py")
    return email


def get_password(sender):
    try:
        import keyring
    except ImportError:
        sys.exit("The 'keyring' package is missing. Run: python tools/email_setup.py")
    pw = keyring.get_password(SERVICE, sender)
    if not pw:
        sys.exit("No saved mail password for this sender. Run: python tools/email_setup.py --password")
    return pw


def send(email, subject, body):
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = email["from"], email["to"], subject
    msg.set_content(body)
    host, port = email["smtp_host"], int(email["smtp_port"])
    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=60) as s:
            s.login(email["from"], get_password(email["from"]))
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=60) as s:
            s.starttls(context=ctx)
            s.login(email["from"], get_password(email["from"]))
            s.send_message(msg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--digest")
    ap.add_argument("--batch", default="")
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args()
    email = load_email_config()
    prefix = email.get("subject_prefix", "Job picks")
    if a.test:
        send(email, f"{prefix}: test message",
             "This is a test from your job search assistant. If you can read this, the daily email works.")
        print("SENT test")
        return
    if not a.digest or not Path(a.digest).exists():
        sys.exit(f"Digest file not found: {a.digest}")
    body = Path(a.digest).read_text(encoding="utf-8")
    send(email, f"{prefix} {dt.date.today().isoformat()}", body)
    print(f"SENT {a.batch}".rstrip())


if __name__ == "__main__":
    try:
        main()
    except smtplib.SMTPAuthenticationError:
        sys.exit("The mail server rejected the login. The app password may be wrong or revoked. "
                 "Run: python tools/email_setup.py --password")
    except (smtplib.SMTPException, OSError) as e:
        sys.exit(f"Email failed: {e}")
