import csv
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SAMPLE = (
    "x\nx\n"
    ",<input>,a,b,<expect>,a,<output>,a,x\n"
    "1,first,1,,,9,,0,5\n"
    ",,,,,,,,\n"
    "2,second,3,2,,9,,,\n"
    "3,third,\"L1\nL2\",,,,,,\n"
)


def run(d, *opts):
    return subprocess.run([sys.executable, str(ROOT / "tools" / "merge_csv.py"), str(d), *opts],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env={**os.environ, "PYTHONIOENCODING": "utf-8"})


class MergeCsvTest(unittest.TestCase):
    def test_no_sum_option(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "case.csv").write_text(SAMPLE, encoding="cp949")
            r = run(d)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn("합계 제외", r.stdout)
            with (d / "result.csv").open(encoding="utf-8-sig", newline="") as f:
                rows = list(csv.reader(f))
            self.assertEqual(rows[0], ["test", "tc", "", "input", "expect", "output"])
            self.assertEqual(rows[1], ["case", "1", "first", "a : 1", "a : 9", "a : 0\nx : 5"])

    def test_sum_other_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "case.csv").write_text(SAMPLE, encoding="cp949")
            r = run(d, "--sum", "a", "--sum", "expect:a")
            self.assertEqual(r.returncode, 0, r.stderr)
            with (d / "result.csv").open(encoding="utf-8-sig", newline="") as f:
                rows = list(csv.reader(f))
            self.assertEqual(rows[0][6:], ["a 합", "a 합"])
            self.assertEqual(rows[1][6:], ["4", "18"])

    def test_merge(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "secret_case.csv").write_text(SAMPLE, encoding="cp949")
            (d / "drm.csv").write_bytes(b"SCDSA\x00\x01")
            r = run(d, "--sum", "a")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn("secret", r.stdout)          # 화면에 파일 이름이 찍히지 않음
            self.assertIn("파일 1개, 3줄", r.stdout)
            self.assertIn("DRM", r.stdout)
            with (d / "result.csv").open(encoding="utf-8-sig", newline="") as f:
                rows = list(csv.reader(f))
            self.assertIn("숫자가 아닌 값: 1개", r.stdout)
            self.assertEqual(rows[0], ["test", "tc", "", "input", "expect", "output", "a 합"])
            # 합계(1+3)는 파일 첫 줄에만, 숫자가 아닌 값은 빼고 더함
            self.assertEqual(rows[1], ["secret_case", "1", "first", "a : 1", "a : 9", "a : 0\nx : 5", "4"])
            self.assertEqual(rows[2], ["", "2", "second", "a : 3\nb : 2", "a : 9", "", ""])
            self.assertEqual(rows[3], ["", "3", "third", "a : L1\nL2", "", "", ""])  # 셀 안 줄바꿈 유지


if __name__ == "__main__":
    unittest.main()
