#!/usr/bin/env python3
"""
C 함수 단위 비교 도구 (func_diff.py)

두 폴더에서 같은 상대 경로의 .c 파일끼리 짝지은 뒤, 파일 안의 함수를 이름으로 짝지어 비교합니다.
함수 순서가 바뀌어도 같은 함수끼리 비교하고, 함수 밖 코드(전역 변수·#define 등)는 '(함수 외)'로 묶어 비교합니다.

사용 예:
    python func_diff.py 폴더A 폴더B -l 목록.xlsx -o report   # 목록(파일명·함수명)에 있는 함수만
    python func_diff.py 폴더A 폴더B -o report                # 모든 함수 + (함수 외)

비교 대상 목록 (-l):
    .xlsx는 첫 시트 A열 = 파일명, B열 = 함수명 (파일명이 비어 있거나 병합 셀이면 위 파일명을 이어 씀)
    텍스트는 한 줄에 '파일명,함수명' (탭도 가능, #은 주석)
    함수명이 비어 있으면 그 파일의 모든 함수, '(함수 외)'는 함수 밖 영역

그 밖의 옵션(-w -B -x -e -c -o --html --excel --summary --no-color)은 folder_diff.py와 같습니다.
종료 코드: 0 = 차이 없음, 1 = 차이 있음, 2 = 읽기 오류 또는 분석 불가 파일 있음
folder_diff.py와 같은 폴더에 있어야 합니다.
"""
import bisect
import re

import folder_diff as fd  # noqa: F401  (Task 3부터 사용)

FUNC_OUTSIDE = "(함수 외)"   # 함수에 속하지 않는 줄을 묶은 단위
WHOLE_FILE = "(파일 전체)"   # 분석 불가 파일이나 목록의 '모든 함수' 항목
NOT_FUNC_NAMES = {"__attribute__", "__declspec", "if", "while", "for", "switch", "sizeof", "return"}
IDENT_END = re.compile(r"([A-Za-z_]\w*)\s*$")


# ---------------------------------------------------------------- C 스캐너
def mask_c(text):
    """주석·문자열·문자 리터럴·전처리 줄을 공백으로 가린 같은 길이의 문자열 (줄바꿈은 유지)"""
    out = list(text)
    n, i, line_start = len(text), 0, True

    def blank(a, b):
        for k in range(a, b):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        ch = text[i]
        if ch == "\n":
            line_start = True
            i += 1
            continue
        if line_start and ch in " \t":
            i += 1
            continue
        if line_start and ch == "#":  # 전처리 줄: 주석·문자열을 건너뛰며 논리적 줄 끝('\' 이어짐 포함)까지
            j = i
            while j < n:
                c = text[j]
                if c == "\n":
                    k = j - 1
                    while k >= i and text[k] in " \t\r":
                        k -= 1
                    if k >= i and text[k] == "\\":
                        j += 1
                        continue
                    break
                if text.startswith("/*", j):
                    e = text.find("*/", j + 2)
                    j = n if e < 0 else e + 2
                elif text.startswith("//", j):
                    e = text.find("\n", j)
                    j = n if e < 0 else e
                elif c in "\"'":
                    j += 1
                    while j < n and text[j] != c and text[j] != "\n":
                        j += 2 if text[j] == "\\" else 1
                    if j < n and text[j] == c:
                        j += 1
                else:
                    j += 1
            j = min(j, n)
            blank(i, j)
            i = j
            continue
        line_start = False
        if text.startswith("/*", i):
            e = text.find("*/", i + 2)
            e = n if e < 0 else e + 2
            blank(i, e)
            i = e
        elif text.startswith("//", i):
            e = text.find("\n", i)
            e = n if e < 0 else e
            blank(i, e)
            i = e
        elif ch in "\"'":
            j = i + 1
            while j < n and text[j] != ch and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            e = j + 1 if j < n and text[j] == ch else j
            blank(i, e)
            i = e
        else:
            i += 1
    return "".join(out)


def func_name(header):
    """최상위 '{' 앞의 선언부(가려진 텍스트)가 함수 정의면 함수 이름, 아니면 None"""
    h = header.rstrip()

    # 뒤에 붙은 __attribute__(…) 또는 __declspec(…) 제거
    while True:
        if not h.endswith(")"):
            return None
        # 마지막 ) 앞의 ( 찾기
        depth = 0
        for k in range(len(h) - 1, -1, -1):
            if h[k] == ")":
                depth += 1
            elif h[k] == "(":
                depth -= 1
                if depth == 0:
                    break
        else:
            return None
        # k부터 len(h)까지가 마지막 (...) 그룹
        paren_group = h[k:len(h)]
        rest = h[:k].rstrip()
        # rest의 끝이 __attribute__ 또는 __declspec인지 확인
        if rest.endswith("__attribute__") or rest.endswith("__declspec"):
            # 그 부분을 제거
            if rest.endswith("__attribute__"):
                h = rest[:-len("__attribute__")].rstrip()
            else:
                h = rest[:-len("__declspec")].rstrip()
            continue
        # 더 이상 제거할 것이 없으면 나감
        break

    if not h.endswith(")"):
        return None
    depth = 0
    for k in range(len(h) - 1, -1, -1):  # 마지막 ( … ) 묶음의 여는 괄호 찾기
        if h[k] == ")":
            depth += 1
        elif h[k] == "(":
            depth -= 1
            if depth == 0:
                break
    else:
        return None
    depth = 0
    for ch in h:  # 괄호 밖 '='가 있으면 초기화 식 (int a[] = {…})
        depth += (ch == "(") - (ch == ")")
        if ch == "=" and depth == 0:
            return None
    m = IDENT_END.search(h[:k])
    if not m or m.group(1) in NOT_FUNC_NAMES:
        return None
    return m.group(1)


def find_functions(lines):
    """줄 목록에서 최상위 함수 정의를 찾아 [(이름, 시작 줄, 끝 줄)] 반환 (줄 번호는 1부터).
    중괄호 짝이 맞지 않으면 None"""
    m = mask_c("\n".join(lines))
    starts = [0] + [x.end() for x in re.finditer("\n", m)]
    funcs, depth, seg, head = [], 0, 0, None
    for x in re.finditer(r"[{};]", m):
        i, ch = x.start(), x.group()
        if ch == "{":
            if depth == 0:
                head = (seg, i)
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                return None
            if depth == 0:
                text = m[head[0]:head[1]]
                name = func_name(text)
                if name:
                    first = head[0] + len(text) - len(text.lstrip())
                    funcs.append((name, bisect.bisect_right(starts, first), bisect.bisect_right(starts, i)))
                seg = i + 1
        elif depth == 0:  # ';'
            seg = i + 1
    return funcs if depth == 0 else None


def split_units(lines):
    """파일을 비교 단위로 나눔: {이름: [줄 번호…]}. 첫 항목은 '(함수 외)'(함수에 속하지 않는 줄),
    그 뒤로 함수가 파일 순서대로 옴. 같은 이름이 또 나오면 '이름#2'. 분석할 수 없으면 None"""
    funcs = find_functions(lines)
    if funcs is None:
        return None
    units, seen, inside = {FUNC_OUTSIDE: []}, {}, set()
    for name, s, e in funcs:
        seen[name] = seen.get(name, 0) + 1
        units[name if seen[name] == 1 else f"{name}#{seen[name]}"] = list(range(s, e + 1))
        inside.update(range(s, e + 1))
    units[FUNC_OUTSIDE] = [n for n in range(1, len(lines) + 1) if n not in inside]
    return units
