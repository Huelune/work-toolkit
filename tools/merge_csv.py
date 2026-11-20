"""
폴더 안의 테스트 CSV들을 읽어 하나의 result.csv로 합치는 스크립트.

입력 (a.csv 형식)
  1~2행 : 'x' 더미 행 → 무시
  3행   : 헤더  ,<input>,a,b,c,d,<expect>,a,x,c,d,<output>,a,x,c,d,<toutput>,...
  4행~  : 번호, 테스트명, 신호값들...

출력 (result.csv) - 테스트 케이스 1개당 1줄
  test,tc,,input,expect,output
  파일명, 번호, 테스트명, input "a : 1\nb : 2", expect "a : 1\n...", output "a : 1\nx : 0\n..."
  (값이 있는 신호만 '신호 : 값' 형태로 셀 안에서 줄바꿈)
  --sum을 주면 맨 오른쪽 칸에 그 신호의 파일별 합계 (그 파일의 첫 줄에만)

사용법:
  python merge_csv.py <입력폴더> [출력파일] [--sum 신호] [--sum 섹션:신호] ...
  --sum a          input 섹션의 a를 파일마다 더함
  --sum output:a   다른 섹션은 '섹션:신호'
"""
import argparse
import csv
import io
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

HEADER_ROW = 2                        # 0부터 셈 → 3번째 줄
OUT_SECTIONS = ["input", "expect", "output"]    # result에 넣을 섹션 순서 (toutput 추가 가능)
OUT_HEADER = ["test", "tc", ""] + OUT_SECTIONS
IN_ENCODINGS = ("utf-8-sig", "cp949")
OUT_ENCODING = "utf-8-sig"            # 엑셀 한글용. 필요하면 "cp949"
DRM_SIGNATURE = b"SCDSA"              # 문서보안(DRM) 암호화 파일 헤더


def read_rows(path: Path):
    raw = path.read_bytes()
    if raw.startswith(DRM_SIGNATURE):
        raise ValueError("DRM 암호화 파일 → 보안 해제 후 다시 실행")
    for enc in IN_ENCODINGS:
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("인코딩을 알 수 없음 → UTF-8이나 CP949로 저장 후 다시 실행")
    lines = text.splitlines()
    if len(lines) <= HEADER_ROW:
        return []
    head = lines[HEADER_ROW]
    delim = "\t" if head.count("\t") > head.count(",") else ","
    # 줄로 자른 lines가 아니라 원문을 넘겨야 따옴표 셀 안의 줄바꿈이 남는다
    return list(csv.reader(io.StringIO(text, newline=""), delimiter=delim))


def map_sections(header):
    """헤더 → {열번호: (섹션, 신호명)}, 테스트명이 있는 열 번호"""
    colmap, section, name_col = {}, None, None
    for i, cell in enumerate(header):
        cell = cell.strip()
        if cell.startswith("<") and cell.endswith(">"):
            section = cell[1:-1].lower()
            if name_col is None:
                name_col = i          # 첫 마커(<input>) 열 = 테스트명
        elif cell and section:
            colmap[i] = (section, cell)
    return colmap, name_col


def parse_file(path: Path, sum_signals=()):
    """sum_signals: 파일마다 합계를 낼 (섹션, 신호)들 → (결과 줄들, 합계에서 뺀 숫자 아닌 값의 개수)"""
    rows = read_rows(path)
    if not rows:
        return [], 0
    colmap, name_col = map_sections(rows[HEADER_ROW])

    out, bad = [], 0
    sums = {key: None for key in sum_signals}    # None = 더한 값이 없음 → 빈칸
    for row in rows[HEADER_ROW + 1:]:
        if not any(c.strip() for c in row):
            continue
        cells = {s: [] for s in OUT_SECTIONS}
        for i, (section, sig) in colmap.items():
            val = row[i].strip().replace("\r\n", "\n") if i < len(row) else ""
            if section in cells and val != "":
                cells[section].append(f"{sig} : {val}")
            if (section, sig) in sums and val != "":
                try:
                    sums[section, sig] = (sums[section, sig] or 0) + Decimal(val)
                except InvalidOperation:
                    bad += 1
        tc = row[0].strip()
        name = row[name_col].strip() if name_col is not None and name_col < len(row) else ""
        out.append([path.stem, tc, name] + ["\n".join(cells[s]) for s in OUT_SECTIONS]
                   + [""] * len(sums))
    if out:
        out[0][3 + len(OUT_SECTIONS):] = ["" if v is None else str(v) for v in sums.values()]
    return out, bad


def main():
    ap = argparse.ArgumentParser(description="폴더 안의 테스트 CSV를 result.csv 하나로 합칩니다.")
    ap.add_argument("in_dir", nargs="?", default=".", type=Path, help="CSV 폴더")
    ap.add_argument("out", nargs="?", type=Path, help="출력 파일 (기본: 입력폴더/result.csv)")
    ap.add_argument("--sum", action="append", default=[], metavar="[섹션:]신호",
                    help="파일마다 합계를 낼 신호. 섹션을 빼면 input. 여러 번 쓸 수 있음")
    args = ap.parse_args()
    in_dir = args.in_dir
    out_path = args.out or in_dir / "result.csv"
    # "a" → ("input", "a"), "output:a" → ("output", "a")
    sum_signals = [(sec.lower() or "input", sig) for sec, _, sig in (s.rpartition(":") for s in args.sum)]

    # 화면에는 개수와 이유만 찍는다 (파일 이름·경로는 찍지 않음)
    result, read, skipped, not_number = [], 0, Counter(), 0
    for path in sorted(in_dir.glob("*.csv")):
        if path.resolve() == out_path.resolve():
            continue
        try:
            rows, bad = parse_file(path, sum_signals)
        except ValueError as e:
            skipped[str(e)] += 1
            continue
        result.extend(rows)
        not_number += bad
        read += 1

    with out_path.open("w", newline="", encoding=OUT_ENCODING) as f:
        w = csv.writer(f)
        w.writerow(OUT_HEADER + [f"{sig} 합" for _, sig in sum_signals])
        w.writerows(result)
    print(f"읽음: 파일 {read}개, {len(result)}줄")
    for reason, n in skipped.items():
        print(f"[건너뜀] {reason}: {n}개")
    if not_number:
        print(f"[합계 제외] 숫자가 아닌 값: {not_number}개")
    print(f"완료 → {out_path.name}")


if __name__ == "__main__":
    main()
