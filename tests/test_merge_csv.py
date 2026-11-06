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
    "2,second,,2,,9,,,\n"
)


class MergeCsvTest(unittest.TestCase):
    def test_merge(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "secret_case.csv").write_text(SAMPLE, encoding="cp949")
            (d / "drm.csv").write_bytes(b"SCDSA\x00\x01")
            r = subprocess.run([sys.executable, str(ROOT / "tools" / "merge_csv.py"), str(d)],
                               capture_output=True, text=True, encoding="utf-8", errors="replace",
                               env={**os.environ, "PYTHONIOENCODING": "utf-8"})
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn("secret", r.stdout)          # 화면에 파일 이름이 찍히지 않음
            self.assertIn("파일 1개, 2줄", r.stdout)
            self.assertIn("DRM", r.stdout)
            with (d / "result.csv").open(encoding="utf-8-sig", newline="") as f:
                rows = list(csv.reader(f))
            self.assertEqual(rows[0], ["test", "tc", "", "", ""])
            self.assertEqual(rows[1], ["secret_case", "1", "first", "a : 1", "a : 0\nx : 5"])
            self.assertEqual(rows[2], ["secret_case", "2", "second", "b : 2", ""])


if __name__ == "__main__":
    unittest.main()
