import argparse
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import email_setup  # noqa: E402


def args(**kw):
    base = dict(provider="gmail", sender="me@gmail.com", to=None, smtp_host=None, smtp_port=None)
    base.update(kw)
    return argparse.Namespace(**base)


class EmailSetupTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cfg = Path(self._tmp.name) / "scanner-config.json"
        self._p = mock.patch.object(email_setup, "CFG", self.cfg)
        self._k = mock.patch.object(email_setup, "ensure_keyring", lambda: None)
        self._p.start()
        self._k.start()

    def tearDown(self):
        self._p.stop()
        self._k.stop()
        self._tmp.cleanup()

    def test_configure_without_config_writes_only_email_block(self):
        out = io.StringIO()
        with redirect_stdout(out):
            email_setup.configure(args())
        data = json.loads(self.cfg.read_text(encoding="utf-8"))
        self.assertEqual(list(data), ["email"])
        self.assertNotIn("Toronto", json.dumps(data))
        self.assertIn("intake", out.getvalue())

    def test_configure_updates_only_email_in_existing_config(self):
        self.cfg.write_text(json.dumps({"keywords": ["x"], "email": {"subject_prefix": "Mine"}}), encoding="utf-8")
        with redirect_stdout(io.StringIO()):
            email_setup.configure(args())
        data = json.loads(self.cfg.read_text(encoding="utf-8"))
        self.assertEqual(data["keywords"], ["x"])
        self.assertEqual(data["email"]["subject_prefix"], "Mine")
        self.assertEqual(data["email"]["from"], "me@gmail.com")

    def test_spaces_stripped_only_for_gmail(self):
        gmail = {"email": {"smtp_host": "smtp.gmail.com"}}
        other = {"email": {"smtp_host": "smtp.mail.yahoo.com"}}
        self.assertEqual(email_setup.clean_password(gmail, "abcd efgh ijkl mnop"), "abcdefghijklmnop")
        self.assertEqual(email_setup.clean_password(other, "abcd efgh"), "abcd efgh")


class DepsAndRefusalTests(unittest.TestCase):
    def test_missing_keyring_message(self):
        with mock.patch.dict(sys.modules, {"keyring": None}):
            with self.assertRaises(SystemExit) as cm:
                email_setup.ensure_keyring()
        msg = str(cm.exception)
        self.assertIn("--install-deps", msg)
        self.assertIn("ask the user first", msg)

    def test_configure_stops_without_keyring_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = Path(d) / "scanner-config.json"
            with mock.patch.object(email_setup, "CFG", cfg), mock.patch.dict(sys.modules, {"keyring": None}):
                with self.assertRaises(SystemExit):
                    email_setup.configure(args())
            self.assertFalse(cfg.exists())

    def test_password_refused_when_not_interactive(self):
        class WinVaultKeyring:
            pass
        fake = mock.Mock()
        fake.get_keyring.return_value = WinVaultKeyring()
        with tempfile.TemporaryDirectory() as d:
            cfg = Path(d) / "scanner-config.json"
            cfg.write_text(json.dumps({"email": {"from": "me@gmail.com", "smtp_host": "smtp.gmail.com"}}),
                           encoding="utf-8")
            with mock.patch.object(email_setup, "CFG", cfg), mock.patch.dict(sys.modules, {"keyring": fake}), \
                    mock.patch.object(email_setup, "gui_available", lambda: False), \
                    mock.patch.object(email_setup, "interactive", lambda: False), \
                    mock.patch.object(email_setup, "password_box") as box:
                with self.assertRaises(SystemExit) as cm:
                    email_setup.save_password()
        self.assertFalse(box.called)
        self.assertIn("USER must run this command themselves", str(cm.exception))
        self.assertIn("email_setup.py --password", str(cm.exception))
        fake.set_password.assert_not_called()

    def test_no_secure_store_refused(self):
        class PlaintextKeyring:
            pass
        fake = mock.Mock()
        fake.get_keyring.return_value = PlaintextKeyring()
        with mock.patch.dict(sys.modules, {"keyring": fake}):
            with self.assertRaises(SystemExit) as cm:
                email_setup.ensure_keyring()
        self.assertIn("No secure password store", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
