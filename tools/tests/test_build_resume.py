import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import build_resume  # noqa: E402

SAMPLE = ROOT / "examples" / "jordan-rivera" / "resume.md"


class BuildResume(unittest.TestCase):
    def test_parse_sample(self):
        d = build_resume.parse(SAMPLE.read_text(encoding="utf-8"))
        self.assertEqual(d["name"], "Jordan Rivera")
        self.assertIn("@", d["contact"])
        titles = [s["title"] for s in d["sections"]]
        self.assertEqual(titles[:3], ["Summary", "Skills", "Experience"])
        kinds = [k for k, _, _ in d["sections"][2]["items"]]
        self.assertEqual(kinds.count("role"), 2)
        self.assertEqual(kinds.count("bullet"), 10)

    def test_build_docx_named_and_archived(self):
        try:
            import docx  # noqa: F401
        except ImportError:
            self.skipTest("python-docx not installed")
        with tempfile.TemporaryDirectory() as t:
            live = Path(t) / "resume" / "live"
            live.mkdir(parents=True)
            (live / "Old_Resume.docx").write_bytes(b"old")
            moved = build_resume.archive_live(live)
            self.assertTrue((moved / "Old_Resume.docx").exists())
            self.assertTrue((live.parent / "history" / "README.md").exists())
            out = live / "Jordan_Rivera_Resume.docx"
            build_resume.build_docx(build_resume.parse(SAMPLE.read_text(encoding="utf-8")), out)
            self.assertTrue(out.exists() and out.stat().st_size > 5000)

    def test_help_exits_clean(self):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "build_resume.py"), "--help"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertIn("build_resume.py", r.stdout)


if __name__ == "__main__":
    unittest.main()
