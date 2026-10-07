# work-toolkit

업무에 유용한 파이썬 도구 모음입니다. 기본적으로 표준 라이브러리만 사용합니다 (Python 3.8+).

## 도구 목록

### folder_diff.py — 두 폴더 비교

같은 상대 경로의 파일끼리 비교하고, 변경된 줄을 보여줍니다.

```bash
python folder_diff.py 폴더A 폴더B
python folder_diff.py 폴더A 폴더B --html report.html --excel report.xlsx
python folder_diff.py 폴더A 폴더B -w --exclude build "src/*.tmp"
python folder_diff.py 폴더A 폴더B --ext .py .c .h .m
```

- 내용은 같고 줄바꿈(CRLF/LF)·인코딩·BOM·파일 끝 줄바꿈만 다른 파일은 "형식만 다름"으로 표시
- `-w`/`-B` 옵션으로 무시된 공백 차이는 "무시됨"으로 별도 표시 (`-w`는 줄바꿈 형식 차이도 무시)
- `-w`/`-B`를 써도 diff에는 원래 줄 번호와 원문(들여쓰기 포함)이 표시됨
- 제외 패턴에 `/`가 들어가면 상대 경로 전체와 비교 (예: `src/tmp`, `docs/*.bak`)
- UTF-8, CP949, UTF-16(BOM) 파일 지원
- 리포트
  - `--html`: 나란히 비교, 바뀐 글자 강조
  - `--excel`: `요약` / `파일 목록`(상태별 색상, 필터) / `변경 내용`(나란히 비교, 필터) 시트.
    **openpyxl 필요**: `pip install openpyxl`
- 종료 코드: 0 = 차이 없음, 1 = 차이 있음, 2 = 읽기 오류(권한 없음 등) 발생
