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

import folder_diff as fd

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
            e = min(j + 1, n) if j < n and text[j] == ch else min(j, n)
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


# ---------------------------------------------------------------- 비교 대상 목록
FUNC_HEADERS = {"함수", "함수명", "함수 이름", "함수이름", "function", "func", "function name"}


def load_func_list(path):
    """목록 파일 → {파일 항목: 함수명 집합 또는 None(그 파일의 모든 함수)} (목록 순서 유지)"""
    plan, cur = {}, None
    for k, (f, fn) in enumerate(fd.read_rows(path, 2)):
        f = "" if f is None else str(f).strip()
        fn = "" if fn is None else str(fn).strip()
        if k == 0 and (f.casefold() in fd.TARGET_HEADERS or fn.casefold() in FUNC_HEADERS):
            continue  # 제목 행
        cur = f or cur  # 파일명이 비어 있거나 병합 셀이면 위 파일명을 이어 씀
        if not cur or not (f or fn):
            continue
        if fn.replace(" ", "") in ("(함수외)", "함수외"):
            fn = FUNC_OUTSIDE
        if not fn:
            plan[cur] = None
        elif cur not in plan:
            plan[cur] = {fn}
        elif plan[cur] is not None:
            plan[cur].add(fn)
    return plan


# ---------------------------------------------------------------- 함수 단위 비교
SAME, CHANGED, ONLY_A, ONLY_B = "동일", "변경", "A에만", "B에만"
NO_FUNC, NO_FILE, BROKEN = "함수 없음", "파일 없음", "분석 불가"


def make_row(file, func, status, a_range="", b_range="", diff=None, note=""):
    return {"file": file, "func": func, "status": status, "a_range": a_range, "b_range": b_range,
            "added": diff["added"] if diff else None, "removed": diff["removed"] if diff else None,
            "note": note, "diff": diff}


def read_side(path, args):
    """파일 한쪽을 읽어 (split_units 결과, normalize 결과) 반환. 파일이 없으면 None"""
    if path is None:
        return None
    lines, _ = fd.decode_lines(path.read_bytes())
    return split_units(lines), fd.normalize(lines, args.ignore_whitespace, args.ignore_blank_lines)


def pick(side, nums):
    """normalize 결과에서 nums 줄만 골라냄 (-B로 빠진 빈 줄은 이미 제외됨)"""
    if side is None or nums is None:
        return []
    keep = set(nums)
    return [x for x in side[1] if x[0] in keep]


def line_range(name, nums):
    return f"{nums[0]}-{nums[-1]}" if nums and name != FUNC_OUTSIDE else ""


def compare_c_file(rel, pa, pb, wanted, args, rows):
    """C 파일 한 쌍을 함수 단위로 비교해 rows에 결과 행을 추가. wanted: None(전부) 또는 함수명 집합"""
    sa, sb = read_side(pa, args), read_side(pb, args)
    broken = [s for s, side in (("A", sa), ("B", sb)) if side and side[0] is None]
    if broken:  # 중괄호 짝이 안 맞으면 파일 전체 diff로 대체
        d = fd.line_diff(sa[1] if sa else [], sb[1] if sb else [], args.context)
        rows.append(make_row(rel, WHOLE_FILE, BROKEN, diff=d,
                             note=f"중괄호 짝 불일치({', '.join(broken)}) - 파일 전체 비교로 대체"))
        return
    ua, ub = (sa[0] if sa else {}), (sb[0] if sb else {})
    names = list(ua) + [k for k in ub if k not in ua]
    if wanted is not None:
        names = [k for k in names if k.split("#")[0] in wanted]
    for name in names:
        la, lb = ua.get(name), ub.get(name)
        na, nb = pick(sa, la), pick(sb, lb)
        if name == FUNC_OUTSIDE and not na and not nb:
            continue
        d = fd.line_diff(na, nb, args.context)
        if la is not None and lb is not None:
            status = CHANGED if d else SAME
        else:  # 한쪽에만 있으면 본문 전체가 삭제/추가로 보임
            status = ONLY_A if la is not None else ONLY_B
        rows.append(make_row(rel, name, status, line_range(name, la), line_range(name, lb), d))
    if wanted is not None:
        found = {k.split("#")[0] for k in names}
        for fn in sorted(wanted - found):
            rows.append(make_row(rel, fn, NO_FUNC, note="A·B 양쪽 파일 모두에 없음 (함수명은 대소문자 구분)"))


def compare_funcs(dir_a, dir_b, args, plan=None):
    """두 폴더의 C 파일을 함수 단위로 비교. plan은 load_func_list() 결과(없으면 전체 비교).
    반환: {"rows": [결과 행…], "errors": [{"path", "detail"}…]}"""
    excludes, exts = fd.file_filters(args)
    errors, rows = [], []
    fa = fd.collect_files(dir_a, excludes, exts, errors)
    fb = fd.collect_files(dir_b, excludes, exts, errors)
    if plan is None:
        targets = {rel: None for rel in set(fa) | set(fb)}
    else:
        targets, every = {}, set(fa) | set(fb)
        for entry, funcs in plan.items():
            hits, _ = fd.match_targets(every, [entry])
            if not hits:
                for fn in (sorted(funcs) if funcs else [WHOLE_FILE]):
                    rows.append(make_row(entry, fn, NO_FILE, note="A·B 양쪽 폴더 모두에 없음"))
                continue
            for rel in hits:  # 같은 파일이 목록에 여러 번 나오면 함수 집합을 합침
                prev = targets.get(rel, set())
                targets[rel] = None if funcs is None or prev is None else prev | funcs
    for rel in sorted(targets):
        try:
            compare_c_file(rel, fa.get(rel), fb.get(rel), targets[rel], args, rows)
        except OSError as ex:
            errors.append({"path": rel, "detail": f"파일 읽기 실패: {ex.strerror or ex}"})
    return {"rows": rows, "errors": errors}
