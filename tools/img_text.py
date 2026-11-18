"""
이미지 안의 글자를 텍스트 파일로 바꾸는 스크립트.

Windows에 들어 있는 글자 인식(OCR)을 쓰므로 따로 설치할 것이 없고,
이미지가 PC 밖으로 나가지 않는다.

출력: 이미지와 같은 폴더에 같은 이름의 .txt (예: 화면.png → 화면.txt)

사용법:
  python img_text.py <이미지 또는 폴더>
"""
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff"}

# 화면에는 정해 둔 문구만 찍는다 (파일 이름·경로·예외 원문은 찍지 않음)
REASONS = {
    "BIG": "이미지가 너무 큼 → 줄이거나 잘라서 다시 실행",
    "FAIL": "이미지를 열 수 없음 → 형식·문서보안(DRM) 확인",
}

# 목록 파일의 이미지마다 .txt를 쓰고 OK/BIG/FAIL 한 줄씩 출력한다 (ASCII만 사용)
PS_SCRIPT = r"""
param($ListFile)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]
$asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' } | Select-Object -First 1
function Await($op, $type) {
    $task = $asTask.MakeGenericMethod($type).Invoke($null, @($op))
    $task.Wait()
    $task.Result
}
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($null -eq $engine) { exit 3 }
$max = [Windows.Media.Ocr.OcrEngine]::MaxImageDimension
$utf8 = New-Object System.Text.UTF8Encoding $true
foreach ($path in Get-Content -LiteralPath $ListFile -Encoding UTF8) {
    try {
        $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($path)) ([Windows.Storage.StorageFile])
        $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
        try {
            $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
            if ($decoder.PixelWidth -gt $max -or $decoder.PixelHeight -gt $max) { 'BIG'; continue }
            $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
            $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
        } finally { $stream.Dispose() }
        $lines = [string[]]@($result.Lines | ForEach-Object { $_.Text })
        [System.IO.File]::WriteAllLines([System.IO.Path]::ChangeExtension($path, '.txt'), $lines, $utf8)
        'OK'
    } catch { 'FAIL' }
}
"""


def main():
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    if target.is_dir():
        images = sorted(p for p in target.iterdir() if p.suffix.lower() in IMAGE_EXTS)
    else:
        images = [target]
    if not images:
        print("이미지가 없습니다 (png, jpg, bmp, gif, tif)")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        script, listing = Path(tmp, "ocr.ps1"), Path(tmp, "list.txt")
        script.write_text(PS_SCRIPT, encoding="ascii")
        listing.write_text("\n".join(str(p.resolve()) for p in images), encoding="utf-8-sig")
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                                "-File", str(script), str(listing)],
                               capture_output=True, text=True, encoding="ascii", errors="replace")
        except FileNotFoundError:
            print("[오류] Windows에서만 쓸 수 있습니다")
            return 2
    if r.returncode == 3:
        print("[오류] 글자 인식 언어가 없음 → Windows 설정 > 시간 및 언어 > 언어에서 언어 팩 설치")
        return 2
    if r.returncode != 0:
        print("[오류] 글자 인식을 실행하지 못함 → Windows 10 이상인지 확인")
        return 2

    counts = Counter(r.stdout.split())
    print(f"변환: 이미지 {counts['OK']}개 → 같은 이름의 .txt")
    for key, reason in REASONS.items():
        if counts[key]:
            print(f"[실패] {reason}: {counts[key]}개")
    return 0 if counts["OK"] == len(images) else 1


if __name__ == "__main__":
    sys.exit(main())
