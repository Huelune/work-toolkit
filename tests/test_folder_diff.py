import argparse
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import folder_diff as fd  # noqa: E402


def make_tree(root: Path, files: dict):
    for rel, data in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))


def ns(**kw):
    base = dict(exclude=None, ext=None, ignore_whitespace=False, ignore_blank_lines=False, context=3)
    base.update(kw)
    return argparse.Namespace(**base)


def run_script(script, *argv):
    return subprocess.run([sys.executable, str(ROOT / "tools" / script), *map(str, argv), "--no-color"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


class FolderDiffTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.a, self.b = Path(self.tmp.name, "A"), Path(self.tmp.name, "B")
        make_tree(self.a, {"same.txt": "x\n", "chg.py": "a\nb\n", "crlf.txt": "q\r\n", "only_a.txt": "1\n"})
        make_tree(self.b, {"same.txt": "x\n", "chg.py": "a\nB\n", "crlf.txt": "q\n", "only_b.txt": "1\n"})

    def tearDown(self):
        self.tmp.cleanup()

    def test_compare_categories(self):
        res = fd.compare(self.a, self.b, ns())
        self.assertEqual(res["same"], ["same.txt"])
        self.assertEqual([c["path"] for c in res["changed"]], ["chg.py"])
        self.assertEqual((res["changed"][0]["added"], res["changed"][0]["removed"]), (1, 1))
        self.assertEqual([c["path"] for c in res["format_changed"]], ["crlf.txt"])
        self.assertEqual(res["only_a"], ["only_a.txt"])
        self.assertEqual(res["only_b"], ["only_b.txt"])

    def test_line_diff(self):
        na = fd.normalize(["a", "", "b"], False, True)
        nb = fd.normalize(["a", "c"], False, True)
        d = fd.line_diff(na, nb, 3)
        self.assertEqual((d["added"], d["removed"]), (1, 1))
        self.assertEqual([x[0] for x in d["a"]], [1, 3])  # 원래 줄 번호 유지
        self.assertIsNone(fd.line_diff(na, na, 3))

    def test_read_rows_text(self):
        p = Path(self.tmp.name, "list.txt")
        p.write_text("# 주석\nmotor.c,Motor_Init\nsensor.c\tRead\nonly.c\n", encoding="utf-8")
        self.assertEqual(fd.read_rows(p, 2), [("motor.c", "Motor_Init"), ("sensor.c", "Read"), ("only.c", None)])
        self.assertEqual(fd.read_rows(p, 1), [("motor.c,Motor_Init",), ("sensor.c\tRead",), ("only.c",)])

    def test_relative_link(self):
        out = Path(self.tmp.name, "r")
        self.assertEqual(fd.relative_link(out / "rep.html", out / "rep.xlsx"), "rep.html")
        self.assertEqual(fd.relative_link(out / "h" / "rep.html", out / "rep.xlsx"), "h/rep.html")

    def test_cli_reports_and_exit_code(self):
        out = Path(self.tmp.name, "out", "r")
        r = run_script("folder_diff.py", self.a, self.b, "--summary", "-o", out)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertTrue(out.with_suffix(".html").is_file())
        self.assertTrue(out.with_suffix(".xlsx").is_file())
        self.assertEqual(run_script("folder_diff.py", self.a, self.a, "--summary").returncode, 0)


if __name__ == "__main__":
    unittest.main()
