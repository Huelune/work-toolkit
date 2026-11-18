# 문제 해결 · 개발자용

[← README](../README.md)

## 문제 해결

| 증상 | 해결 |
|---|---|
| `엑셀 파일을 다루려면 openpyxl이 필요합니다` | `pip install -r requirements.txt` |
| `구버전 엑셀(.xls)은 읽을 수 없습니다` | 엑셀에서 `.xlsx`로 다른 이름으로 저장 |
| 리포트 저장 시 `Permission denied` | 같은 이름의 엑셀 파일이 열려 있음 → 닫거나 `-o`에 다른 이름 사용 |
| 한글이 깨져 보임 | 파일은 UTF-8·CP949·UTF-16을 자동 인식합니다. 콘솔이 깨지면 `-o`로 리포트를 만들어 확인 |
| 엑셀 링크를 눌렀는데 HTML 맨 위가 열림 | 일부 Office 환경의 제한입니다. HTML에서 해당 파일·함수를 클릭해 펼치세요 |

## 폴더 구성

```
work-toolkit/
├─ tools/             도구 (folder_diff.py, func_diff.py, merge_csv.py, img_text.py)
├─ reports/           리포트 저장 위치 (git에 올라가지 않음)
├─ tests/             자동 테스트
├─ docs/              사용 설명서, 설계 문서
├─ requirements.txt   엑셀 기능용 패키지 목록
└─ README.md
```

## 개발자용

```bash
python -m unittest discover -s tests -v
```

- 엑셀 기능 외에는 표준 라이브러리만 사용합니다.
- `func_diff.py`는 `folder_diff.py`의 기능을 가져다 쓰므로 두 파일은 같은 폴더(`tools/`)에 있어야 합니다.
- 설계 문서: `docs/superpowers/specs/`, 구현 계획: `docs/superpowers/plans/`
