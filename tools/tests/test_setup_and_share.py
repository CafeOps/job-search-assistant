import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import paths  # noqa: E402
import setup_check  # noqa: E402


class SetupCheckTests(unittest.TestCase):
    def test_check_mode_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            data = Path(d) / "not" / "yet"
            with mock.patch.dict(os.environ, {paths.ENV_VAR: str(data)}), \
                    mock.patch.object(setup_check, "net_ok", lambda: False):
                setup_check.main(["--check"])
            self.assertFalse(data.exists())
            self.assertFalse((Path(d) / "not").exists())

    def test_report_has_abilities_section(self):
        with tempfile.TemporaryDirectory() as d:
            data = Path(d) / "job"
            with mock.patch.dict(os.environ, {paths.ENV_VAR: str(data)}), \
                    mock.patch.object(setup_check, "net_ok", lambda: True):
                setup_check.main([])
            text = (data / "SETUP.md").read_text(encoding="utf-8")
        self.assertIn("## Abilities", text)
        for item in ("Network", "Secure credential store", "Scheduler", "Browser control", "File uploads"):
            self.assertIn(item, text)
        self.assertIn("Python command to use for every kit command", text)

    def test_check_with_data_dir_refused(self):
        with self.assertRaises(SystemExit):
            setup_check.main(["--check", "--data-dir", "x"])


if __name__ == "__main__":
    unittest.main()
