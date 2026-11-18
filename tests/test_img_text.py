import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 흰 바탕에 검은 글자 "HELLO 123"을 그린 PNG를 만든다
DRAW = (
    "Add-Type -AssemblyName System.Drawing;"
    "$b = New-Object System.Drawing.Bitmap 600,200;"
    "$g = [System.Drawing.Graphics]::FromImage($b);"
    "$g.Clear([System.Drawing.Color]::White);"
    "$f = New-Object System.Drawing.Font 'Arial',48;"
    "$g.DrawString('HELLO 123', $f, [System.Drawing.Brushes]::Black, 20, 50);"
    "$b.Save($env:IMG_OUT, [System.Drawing.Imaging.ImageFormat]::Png)"
)


@unittest.skipUnless(sys.platform == "win32", "Windows 내장 OCR 필요")
class ImgTextTest(unittest.TestCase):
    def test_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            subprocess.run(["powershell", "-NoProfile", "-Command", DRAW], check=True,
                           env={**os.environ, "IMG_OUT": str(d / "secret_shot.png")})
            (d / "secret_broken.png").write_bytes(b"SCDSA\x00\x01")
            r = subprocess.run([sys.executable, str(ROOT / "tools" / "img_text.py"), str(d)],
                               capture_output=True, text=True, encoding="utf-8", errors="replace",
                               env={**os.environ, "PYTHONIOENCODING": "utf-8"})
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)   # 1개 실패
            text = (d / "secret_shot.txt").read_text(encoding="utf-8-sig")
            self.assertIn("HELLO", text)
            self.assertIn("123", text)
            self.assertFalse((d / "secret_broken.txt").exists())
            self.assertIn("이미지 1개", r.stdout)
            self.assertIn("[실패]", r.stdout)
            self.assertNotIn("secret", r.stdout + r.stderr)          # 이름·경로는 화면에 없음


if __name__ == "__main__":
    unittest.main()
