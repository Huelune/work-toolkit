"""
이미지 안의 글자를 텍스트 파일로 바꾸는 스크립트.

Windows에 들어 있는 글자 인식(OCR)을 Python에서 직접 부른다.
따로 설치할 것이 없고, 다른 프로그램(PowerShell 등)을 띄우지 않으며,
이미지가 PC 밖으로 나가지 않는다.

출력: 이미지와 같은 폴더에 같은 이름의 .txt (예: 화면.png → 화면.txt)

사용법:
  python img_text.py <이미지 또는 폴더>
"""
import ctypes
import sys
import time
import uuid
from collections import Counter
from pathlib import Path

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff"}

# 화면에는 정해 둔 문구만 찍는다 (파일 이름·경로·예외 원문은 찍지 않음)
REASONS = {
    "BIG": "이미지가 너무 큼 → 줄이거나 잘라서 다시 실행",
    "FAIL": "이미지를 열 수 없음 → 형식·문서보안(DRM) 확인",
}

# Windows 런타임 인터페이스 식별자. 메서드 번호는 인터페이스에 정의된 순서 + 6
IID_ASYNC_INFO = "00000036-0000-0000-c000-000000000046"
IID_STREAM = "905a0fe1-bc53-11df-8c49-001e4fc686da"
IID_DECODER_STATICS = "438ccb26-bcef-4e95-bad6-23a822e58d01"
IID_FRAME_BITMAP = "fe287c9a-420c-4963-87ad-691436e08383"
IID_OCR_STATICS = "5bffa85a-3384-3540-9940-699120d428a8"

P = ctypes.c_void_p


def guid(text):
    return (ctypes.c_byte * 16).from_buffer_copy(uuid.UUID(text).bytes_le)


def call(obj, index, *args):
    """COM 객체의 index번째 메서드를 부른다. 실패하면 OSError."""
    vtable = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(P))).contents
    func = ctypes.WINFUNCTYPE(ctypes.HRESULT, P, *[P] * len(args))(vtable[index])
    return func(obj, *args)


def get(obj, index, *args):
    """결과 포인터 하나를 돌려주는 메서드를 부른다."""
    out = P()
    call(obj, index, *args, ctypes.byref(out))
    return out


def get_int(obj, index):
    out = ctypes.c_uint32()
    call(obj, index, ctypes.byref(out))
    return out.value


def query(obj, iid):
    return get(obj, 0, ctypes.byref(guid(iid)))


def release(*objs):
    for obj in objs:
        if obj:
            call(obj, 2)


class Ocr:
    def __init__(self):
        self.base = ctypes.WinDLL("combase")
        self.base.WindowsCreateString.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.POINTER(P)]
        self.base.WindowsGetStringRawBuffer.argtypes = [P, P]
        self.base.WindowsGetStringRawBuffer.restype = ctypes.c_wchar_p
        self.base.WindowsDeleteString.argtypes = [P]
        self.base.RoGetActivationFactory.argtypes = [P, P, ctypes.POINTER(P)]
        self.open_stream = ctypes.WinDLL("shcore").CreateRandomAccessStreamOnFile
        self.open_stream.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, P, ctypes.POINTER(P)]
        self.open_stream.restype = ctypes.HRESULT
        self.base.RoInitialize(1)     # 다중 스레드 방식: 비동기 작업이 기다리는 동안에도 끝난다

        self.decoders = self.factory("Windows.Graphics.Imaging.BitmapDecoder", IID_DECODER_STATICS)
        ocr = self.factory("Windows.Media.Ocr.OcrEngine", IID_OCR_STATICS)
        self.max_size = get_int(ocr, 6)
        self.engine = get(ocr, 10)    # TryCreateFromUserProfileLanguages. 언어가 없으면 빈 값

    def factory(self, name, iid):
        text, out = P(), P()
        self.base.WindowsCreateString(name, len(name), ctypes.byref(text))
        hr = self.base.RoGetActivationFactory(text, ctypes.byref(guid(iid)), ctypes.byref(out))
        self.base.WindowsDeleteString(text)
        if hr:
            raise OSError("activation")
        return out

    def text(self, obj, index):
        handle = get(obj, index)
        value = self.base.WindowsGetStringRawBuffer(handle, None) or ""
        self.base.WindowsDeleteString(handle)
        return value

    def wait(self, operation):
        """비동기 작업이 끝나기를 기다렸다가 결과를 돌려준다."""
        info = query(operation, IID_ASYNC_INFO)
        try:
            while get_int(info, 7) == 0:      # 0 = 진행 중
                time.sleep(0.005)
            if get_int(info, 7) != 1:         # 1 = 완료
                raise OSError("async")
            return get(operation, 8)          # GetResults
        finally:
            release(info, operation)

    def read(self, path):
        """이미지 → 줄 목록. 너무 크면 None."""
        made = []                             # 끝나면 놓아 줄 객체들
        def keep(obj):
            made.append(obj)
            return obj
        try:
            stream = P()
            self.open_stream(str(path), 0, ctypes.byref(guid(IID_STREAM)), ctypes.byref(stream))
            keep(stream)
            decoder = keep(self.wait(get(self.decoders, 14, stream)))        # CreateAsync
            frame = keep(query(decoder, IID_FRAME_BITMAP))
            bitmap = keep(self.wait(get(frame, 6)))                          # GetSoftwareBitmapAsync
            if max(get_int(bitmap, 8), get_int(bitmap, 9)) > self.max_size:  # 가로, 세로
                return None
            result = keep(self.wait(get(self.engine, 6, bitmap)))            # RecognizeAsync
            lines = keep(get(result, 6))
            out = []
            for i in range(get_int(lines, 7)):
                line = get(lines, 6, i)
                out.append(self.text(line, 7))
                release(line)
            return out
        finally:
            release(*reversed(made))


def main():
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    if target.is_dir():
        images = sorted(p for p in target.iterdir() if p.suffix.lower() in IMAGE_EXTS)
    else:
        images = [target]
    if not images:
        print("이미지가 없습니다 (png, jpg, bmp, gif, tif)")
        return 1

    try:
        ocr = Ocr()
    except (OSError, AttributeError):
        print("[오류] 글자 인식을 쓸 수 없음 → Windows 10 이상인지 확인")
        return 2
    if not ocr.engine:
        print("[오류] 글자 인식 언어가 없음 → Windows 설정 > 시간 및 언어 > 언어에서 언어 팩 설치")
        return 2

    counts = Counter()
    for path in images:
        try:
            lines = ocr.read(path.resolve())
        except OSError:
            counts["FAIL"] += 1
            continue
        if lines is None:
            counts["BIG"] += 1
            continue
        path.with_suffix(".txt").write_text("".join(s + "\n" for s in lines), encoding="utf-8-sig")
        counts["OK"] += 1

    print(f"변환: 이미지 {counts['OK']}개 → 같은 이름의 .txt")
    for key, reason in REASONS.items():
        if counts[key]:
            print(f"[실패] {reason}: {counts[key]}개")
    return 0 if counts["OK"] == len(images) else 1


if __name__ == "__main__":
    sys.exit(main())
