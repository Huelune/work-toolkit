# merge_csv — 테스트 CSV 합치기

[← README](../README.md)

폴더 안의 `*.csv`를 모두 읽어 **테스트 케이스 1개당 1줄**인 `result.csv` 하나로 합칩니다. 표준 라이브러리만 씁니다.

```bash
python tools/merge_csv.py "D:\test\csv"                  # → D:\test\csv\result.csv
python tools/merge_csv.py "D:\test\csv" reports/합본.csv  # 저장 위치 지정
python tools/merge_csv.py "D:\test\csv" --sum a          # input의 a를 파일마다 더해 적기
python tools/merge_csv.py "D:\test\csv" --sum a --sum output:b   # 여러 개, 다른 섹션은 섹션:신호
```

## 입력 형식

| 행 | 내용 |
|---|---|
| 1~2행 | 더미 행 (무시) |
| 3행 | 헤더: `,<input>,a,b,…,<expect>,…,<output>,…,<toutput>,…` — `<섹션>` 뒤의 칸이 그 섹션의 신호 이름 |
| 4행~ | 번호, 테스트명(`<input>` 열), 신호값들 |

쉼표·탭 구분 모두 되고, 인코딩은 UTF-8·CP949를 자동 인식합니다. 빈 행은 건너뜁니다.

## 결과 (`result.csv`)

| test | tc | | input | expect | output | a 합 |
|---|---|---|---|---|---|---|
| 파일명 | 번호 | 테스트명 | 신호 | 신호 | 신호 | 파일별 합계 |

- 값이 있는 신호만 `신호 : 값`으로, 셀 안에서 줄바꿈해 적습니다.
- 넣을 섹션은 스크립트 위쪽 `OUT_SECTIONS`에서 바꿉니다 (예: `["input", "expect", "output", "toutput"]`).
- `--sum 신호`를 주면 맨 오른쪽에 `신호 합` 칸이 생기고, 그 신호를 한 파일의 모든 케이스에 걸쳐 더한 값을 그 파일의 첫 줄에만 적습니다. 섹션을 빼면 input이고, 다른 섹션은 `--sum output:신호`처럼 씁니다. 숫자가 아닌 값은 빼고 더하며, 뺀 개수는 화면에 나옵니다. `--sum`이 없으면 합계 칸도 없습니다.
- 엑셀에서 한글이 보이도록 UTF-8(BOM)로 저장합니다. 필요하면 `OUT_ENCODING = "cp949"`.
- 화면에는 읽은 파일 수·줄 수와 건너뛴 이유별 개수만 나옵니다. 문서보안(DRM)이 걸린 파일은 건너뜁니다.
