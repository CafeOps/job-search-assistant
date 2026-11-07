import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import harvest  # noqa: E402


def make_docx(path, text):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", f"<w:document><w:body><w:p><w:t>{text}</w:t></w:p></w:body></w:document>")


class HarvestTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.src = self.tmp / "docs"
        self.src.mkdir()
        self.dest = self.tmp / "out" / "harvest"

    def tearDown(self):
        self._tmp.cleanup()

    def list_(self):
        res = harvest.scan([self.src], quiet=True)
        harvest.write_listing(res, self.dest)
        return res

    def test_name_match(self):
        (self.src / "My Resume 2019.txt").write_text("hello")
        (self.src / "holiday.txt").write_text("beach")
        res = self.list_()
        self.assertEqual([Path(c["path"]).name for c in res["candidates"]], ["My Resume 2019.txt"])
        self.assertEqual(res["candidates"][0]["reason"], "name")

    def test_content_match_docx(self):
        make_docx(self.src / "untitled.docx", "Experience at Acme. Education and Skills listed here.")
        make_docx(self.src / "recipe.docx", "Flour and eggs")
        res = self.list_()
        self.assertEqual([Path(c["path"]).name for c in res["candidates"]], ["untitled.docx"])
        self.assertEqual(res["candidates"][0]["reason"], "content")

    def test_duplicate_names_get_distinct_copies(self):
        for sub, body in (("a", "one"), ("b", "two")):
            (self.src / sub).mkdir()
            f = self.src / sub / "resume.txt"
            f.write_text(body)
            os.utime(f, (1_600_000_000, 1_600_000_000))  # same date
        self.list_()
        copied, skipped = harvest.copy_from_manifest(self.dest, copy_all=True)
        self.assertEqual((len(copied), len(skipped)), (2, 0))
        self.assertEqual(len({n for _, n in copied}), 2)
        index = (self.dest / "INDEX.md").read_text(encoding="utf-8")
        self.assertEqual(index.count("resume_"), 2)

    def test_index_appends(self):
        (self.src / "resume.txt").write_text("one")
        self.list_()
        harvest.copy_from_manifest(self.dest, copy_all=True)
        (self.src / "cv.txt").write_text("two")
        self.list_()
        harvest.copy_from_manifest(self.dest, copy_all=True)
        index = (self.dest / "INDEX.md").read_text(encoding="utf-8")
        self.assertIn("resume_", index)
        self.assertIn("cv_", index)

    def test_empty_or_bad_pick_errors_and_copies_nothing(self):
        (self.src / "resume.txt").write_text("one")
        self.list_()
        for bad in ("", " , ", "zzzz", None):
            with self.assertRaises(harvest.PickError):
                harvest.copy_from_manifest(self.dest, pick=bad)
        self.assertEqual([p.name for p in self.dest.iterdir() if p.name not in ("manifest.json", "candidates.md")], [])

    def test_pick_by_id_and_row(self):
        (self.src / "resume.txt").write_text("one")
        (self.src / "cv.txt").write_text("two")
        res = self.list_()
        c1, c2 = res["candidates"]
        copied, _ = harvest.copy_from_manifest(self.dest, pick=f"{c1['id']},{c2['n']}")
        self.assertEqual(len(copied), 2)

    def test_manifest_ids_stable(self):
        (self.src / "resume.txt").write_text("one")
        (self.src / "cv.txt").write_text("two")
        first = {c["path"]: c["id"] for c in self.list_()["candidates"]}
        second = {c["path"]: c["id"] for c in self.list_()["candidates"]}
        self.assertEqual(first, second)
        m = json.loads((self.dest / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual({c["path"]: c["id"] for c in m["candidates"]}, first)
        self.assertTrue(all(len(c["sha256"]) == 64 and c["sha256"].startswith(c["id"]) for c in m["candidates"]))

    def test_changed_or_missing_source_is_skipped(self):
        a, b = self.src / "resume.txt", self.src / "cv.txt"
        a.write_text("one")
        b.write_text("two")
        self.list_()
        a.write_text("changed after listing")
        b.unlink()
        copied, skipped = harvest.copy_from_manifest(self.dest, copy_all=True)
        self.assertEqual((len(copied), len(skipped)), (0, 2))

    def test_symlink_loop_does_not_hang(self):
        (self.src / "resume.txt").write_text("one")
        sub = self.src / "sub"
        sub.mkdir()
        try:
            os.symlink(str(self.src), str(sub / "loop"), target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks not permitted on this machine")
        res = self.list_()
        self.assertEqual(len(res["candidates"]), 1)

    def test_pages_bundle_is_a_document_not_searched(self):
        bundle = self.src / "Old Resume.pages"
        bundle.mkdir()
        (bundle / "index.xml").write_text("inside")
        (bundle / "resume-inner.txt").write_text("should not be listed separately")
        res = self.list_()
        self.assertEqual([Path(c["path"]).name for c in res["candidates"]], ["Old Resume.pages"])
        copied, _ = harvest.copy_from_manifest(self.dest, copy_all=True)
        self.assertTrue((self.dest / copied[0][1]).is_dir())

    def test_unreadable_names_reported(self):
        d = self.src / "locked"
        d.mkdir()
        res = harvest.scan([self.src], quiet=True)
        res["skipped"] = [("C:/x", "PermissionError")] * 12
        text = harvest.write_listing(res, self.dest)
        self.assertIn("12 folders could not be read", text)
        self.assertEqual(text.count("- C:/x"), 10)

    def test_discover_roots_skips_kit_and_dedupes(self):
        roots = harvest.discover_roots([str(self.src), str(self.src)])
        self.assertEqual(sum(1 for p, _ in roots if Path(p) == self.src), 1)
        self.assertFalse(any(harvest._inside_kit(p) for p, _ in roots))


    def test_only_searches_just_that_folder(self):
        other = self.tmp / "other"
        other.mkdir()
        (self.src / "resume.txt").write_text("one")
        (other / "cv.txt").write_text("two")
        roots = harvest.discover_roots(only=[str(self.src)])
        self.assertEqual([str(p) for p, _ in roots], [str(self.src)])
        self.assertEqual(harvest.discover_roots(only=[str(self.tmp / "missing")]), [])
        old_dest = harvest.DEST
        harvest.DEST = self.dest
        try:
            harvest.main(["--only", str(self.src)])
        finally:
            harvest.DEST = old_dest
        names = [Path(c["path"]).name for c in json.loads((self.dest / "manifest.json").read_text(encoding="utf-8"))["candidates"]]
        self.assertEqual(names, ["resume.txt"])


if __name__ == "__main__":
    unittest.main()
