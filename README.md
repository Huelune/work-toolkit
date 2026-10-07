# work-toolkit

업무에 유용한 파이썬 도구 모음입니다. 모두 표준 라이브러리만 사용합니다 (Python 3.8+).

## 도구 목록

### folder_diff.py — 두 폴더 비교

같은 상대 경로의 파일끼리 비교하고, 변경된 줄을 보여줍니다.

```bash
python folder_diff.py 폴더A 폴더B
python folder_diff.py 폴더A 폴더B --html report.html
python folder_diff.py 폴더A 폴더B -w --exclude build "*.log"
python folder_diff.py 폴더A 폴더B --ext .py .c .h .m
```

- 내용은 같고 줄바꿈(CRLF/LF)·인코딩·BOM·파일 끝 줄바꿈만 다른 파일은 "형식만 다름"으로 표시
- `-w`/`-B` 옵션으로 무시된 공백 차이는 "무시됨"으로 별도 표시 (`-w`는 줄바꿈 형식 차이도 무시)
- 차이가 있으면 종료 코드 1
