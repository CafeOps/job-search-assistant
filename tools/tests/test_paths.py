import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import paths  # noqa: E402


class PathsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        env = {"APPDATA": str(self.tmp / "appdata"), "HOME": str(self.tmp / "home"),
               "USERPROFILE": str(self.tmp / "home")}
        self._patch = mock.patch.dict(os.environ, env)
        self._patch.start()
        os.environ.pop(paths.ENV_VAR, None)
        self._home = mock.patch.object(Path, "home", return_value=self.tmp / "home")
        self._home.start()

    def tearDown(self):
        self._home.stop()
        self._patch.stop()
        self._tmp.cleanup()

    def test_legacy_fallback(self):
        self.assertEqual(paths.data_dir(), paths.kit_root() / "profile")
        self.assertFalse(paths.is_chosen())

    def test_config_file_second(self):
        chosen = self.tmp / "My Job Hunt"
        paths.set_data_dir(chosen)
        self.assertTrue(chosen.is_dir())
        self.assertEqual(paths.data_dir(), chosen.resolve())
        self.assertEqual(json.loads(paths.config_path().read_text(encoding="utf-8"))["data_dir"], str(chosen.resolve()))
        self.assertTrue(paths.is_chosen())

    def test_env_wins(self):
        paths.set_data_dir(self.tmp / "fromconfig")
        os.environ[paths.ENV_VAR] = str(self.tmp / "fromenv")
        self.assertEqual(paths.data_dir(), self.tmp / "fromenv")

    def test_broken_config_falls_back(self):
        cfg = paths.config_path()
        cfg.parent.mkdir(parents=True)
        cfg.write_text("{not json", encoding="utf-8")
        self.assertEqual(paths.data_dir(), paths.kit_root() / "profile")

    def test_cloud_sync_detection(self):
        self.assertTrue(paths.in_cloud_sync(Path("C:/Users/x/OneDrive/Documents/Job Hunt")))
        self.assertTrue(paths.in_cloud_sync(Path("/Users/x/Library/Mobile Documents/com~apple~CloudDocs/a")))
        self.assertTrue(paths.in_cloud_sync(Path("/Users/x/Dropbox/a")))
        self.assertFalse(paths.in_cloud_sync(self.tmp / "Job Hunt"))


if __name__ == "__main__":
    unittest.main()
