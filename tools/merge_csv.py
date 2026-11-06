"""
폴더 안의 테스트 CSV들을 읽어 하나의 result.csv로 합치는 스크립트.

입력 (a.csv 형식)
  1~2행 : 'x' 더미 행 → 무시
  3행   : 헤더  ,<input>,a,b,c,d,<expect>,a,x,c,d,<output>,a,x,c,d,<toutput>,...
  4행~  : 번호, 테스트명, 신호값들...

출력 (result.csv) - 테스트 케이스 1개당 1줄
  test,tc,,,
  파일명, 번호, 테스트명, "a : 1\nb : 2", "a : 1\nx : 0\n..."
  (값이 있는 신호만 '신호 : 값' 형태로 셀 안에서 줄바꿈)

사용법:
  python merge_csv.py <입력폴더> [출력파일]
"""
import csv
import sys
from collections import Counter
from pathlib import Path

HEADER_ROW = 2                        # 0부터 셈 → 3번째 줄
OUT_SECTIONS = ["input", "output"]    # result에 넣을 섹션 순서 (expect, toutput 추가 가능)
OUT_HEADER = ["test", "tc", "", "", ""]
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
    return list(csv.reader(lines, delimiter=delim))


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


def parse_file(path: Path):
    rows = read_rows(path)
    if not rows:
        return []
    colmap, name_col = map_sections(rows[HEADER_ROW])

    out = []
    for row in rows[HEADER_ROW + 1:]:
        if not any(c.strip() for c in row):
            continue
        cells = {s: [] for s in OUT_SECTIONS}
        for i, (section, sig) in colmap.items():
            val = row[i].strip() if i < len(row) else ""
            if section in cells and val != "":
                cells[section].append(f"{sig} : {val}")
        tc = row[0].strip()
        name = row[name_col].strip() if name_col is not None and name_col < len(row) else ""
        out.append([path.stem, tc, name] + ["\n".join(cells[s]) for s in OUT_SECTIONS])
    return out


def main():
    in_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else in_dir / "result.csv"

    # 화면에는 개수와 이유만 찍는다 (파일 이름·경로는 찍지 않음)
    result, read, skipped = [], 0, Counter()
    for path in sorted(in_dir.glob("*.csv")):
        if path.resolve() == out_path.resolve():
            continue
        try:
            rows = parse_file(path)
        except ValueError as e:
            skipped[str(e)] += 1
            continue
        result.extend(rows)
        read += 1

    with out_path.open("w", newline="", encoding=OUT_ENCODING) as f:
        w = csv.writer(f)
        w.writerow(OUT_HEADER)
        w.writerows(result)
    print(f"읽음: 파일 {read}개, {len(result)}줄")
    for reason, n in skipped.items():
        print(f"[건너뜀] {reason}: {n}개")
    print(f"완료 → {out_path.name}")


if __name__ == "__main__":
    main()
