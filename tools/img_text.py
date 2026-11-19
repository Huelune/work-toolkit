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
from statistics import median

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff"}
FIXES = str.maketrans("〈〉", "<>")
TEXT_HEIGHT = 40     # 인식이 잘 되는 글자 높이(픽셀). 측정해서 정한 값

# 화면에는 정해 둔 문구만 찍는다 (파일 이름·경로·예외 원문은 찍지 않음)
REASONS = {
    "BIG": "이미지가 너무 큼 → 줄이거나 잘라서 다시 실행",
    "FAIL": "이미지를 열 수 없음 → 형식·문서보안(DRM) 확인",
}

# Windows 런타임 인터페이스 식별자. 메서드 번호는 인터페이스에 정의된 순서 + 6
IID_ASYNC_INFO = "00000036-0000-0000-c000-000000000046"
IID_STREAM = "905a0fe1-bc53-11df-8c49-001e4fc686da"
IID_DECODER_STATICS = "438ccb26-bcef-4e95-bad6-23a822e58d01"
IID_FRAME = "72a49a1c-8081-438d-91bc-94ecfc8185c6"
IID_FRAME_BITMAP = "fe287c9a-420c-4963-87ad-691436e08383"
IID_TRANSFORM = "ae755344-e268-4d35-adcf-e995d31a8d34"
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
        self.base.RoActivateInstance.argtypes = [P, ctypes.POINTER(P)]
        self.open_stream = ctypes.WinDLL("shcore").CreateRandomAccessStreamOnFile
        self.open_stream.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, P, ctypes.POINTER(P)]
        self.open_stream.restype = ctypes.HRESULT
        self.base.RoInitialize(1)     # 다중 스레드 방식: 비동기 작업이 기다리는 동안에도 끝난다

        self.decoders = self.factory("Windows.Graphics.Imaging.BitmapDecoder", IID_DECODER_STATICS)
        ocr = self.factory("Windows.Media.Ocr.OcrEngine", IID_OCR_STATICS)
        self.max_size = get_int(ocr, 6)
        self.engine = get(ocr, 10)    # TryCreateFromUserProfileLanguages. 언어가 없으면 빈 값

    def hstring(self, value):
        text = P()
        self.base.WindowsCreateString(value, len(value), ctypes.byref(text))
        return text

    def factory(self, name, iid):
        text, out = self.hstring(name), P()
        hr = self.base.RoGetActivationFactory(text, ctypes.byref(guid(iid)), ctypes.byref(out))
        self.base.WindowsDeleteString(text)
        if hr:
            raise OSError("activation")
        return out

    def transform(self, width, height):
        """이미지를 width x height로 부드럽게 늘리는 설정"""
        text, obj = self.hstring("Windows.Graphics.Imaging.BitmapTransform"), P()
        hr = self.base.RoActivateInstance(text, ctypes.byref(obj))
        self.base.WindowsDeleteString(text)
        if hr:
            raise OSError("activation")
        out = query(obj, IID_TRANSFORM)
        release(obj)
        call(out, 7, width)       # put_ScaledWidth
        call(out, 9, height)      # put_ScaledHeight
        call(out, 11, 2)          # put_InterpolationMode = 3차 곡선 (부드럽게)
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

    def words(self, frame, width, height, scale):
        """scale배로 늘려 읽은 낱말 목록 [(글자, x, y, 높이)]"""
        made = []                             # 끝나면 놓아 줄 객체들
        def keep(obj):
            made.append(obj)
            return obj
        try:
            change = keep(self.transform(width * scale, height * scale))
            # GetSoftwareBitmapAsync(Bgra8, 알파, 변환, 방향 무시, 색 관리 안 함)
            bitmap = keep(self.wait(get(frame, 8, 87, 0, change, 0, 0)))
            result = keep(self.wait(get(self.engine, 6, bitmap)))            # RecognizeAsync
            lines = keep(get(result, 6))
            out = []
            for i in range(get_int(lines, 7)):
                words = keep(get(keep(get(lines, 6, i)), 6))                 # 줄 → 낱말들
                for k in range(get_int(words, 7)):
                    word = keep(get(words, 6, k))
                    box = (ctypes.c_float * 4)()                             # x, y, 너비, 높이
                    call(word, 6, ctypes.byref(box))
                    out.append((self.text(word, 7), box[0], box[1], box[3]))
            return out
        finally:
            release(*reversed(made))

    def read(self, path, scale=None):
        """이미지 → 줄 목록. 너무 크면 None. scale을 안 주면 글자 크기를 보고 정한다."""
        made = []
        try:
            stream = P()
            self.open_stream(str(path), 0, ctypes.byref(guid(IID_STREAM)), ctypes.byref(stream))
            made.append(stream)
            decoder = self.wait(get(self.decoders, 14, stream))              # CreateAsync
            made.append(decoder)
            size = query(decoder, IID_FRAME)
            made.append(size)
            width, height = get_int(size, 12), get_int(size, 13)
            limit = self.max_size // max(width, height)                      # 늘릴 수 있는 한도
            if limit < 1:
                return None
            frame = query(decoder, IID_FRAME_BITMAP)
            made.append(frame)
            words = self.words(frame, width, height, min(scale or 1, limit))
            if scale is None and words:
                # 화면 캡처의 작은 글자는 잘 틀린다. 글자 높이가 TEXT_HEIGHT쯤 되게 늘려 다시 읽는다
                scale = min(round(TEXT_HEIGHT / median(w[3] for w in words)), limit)
                if scale > 1:
                    words = self.words(frame, width, height, scale)
            return to_lines(words)
        finally:
            release(*reversed(made))


def to_lines(words):
    """낱말 [(글자, x, y, 높이)] → 위에서 아래, 왼쪽에서 오른쪽 순서의 줄 목록.

    인식기가 한 줄을 좌우 두 덩어리로 나눠 순서를 섞을 때가 있어, 위치로 다시 줄을 맞춘다.
    """
    if not words:
        return []
    gap = median(w[3] for w in words) * 0.6       # 가운데 높이가 이만큼 안에 있으면 같은 줄
    rows = []
    for word in sorted(words, key=lambda w: w[2] + w[3] / 2):
        middle = word[2] + word[3] / 2
        if rows and middle - rows[-1][0] < gap:
            rows[-1][1].append(word)
        else:
            rows.append((middle, [word]))
    # 한국어 인식은 코드의 < > 를 전각 괄호로 읽는다
    return [" ".join(w[0] for w in sorted(row, key=lambda w: w[1])).translate(FIXES) for _, row in rows]


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
