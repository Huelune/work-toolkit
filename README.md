# work-toolkit

업무에 쓰는 파이썬 도구 모음입니다. 명령 한 줄로 씁니다.

## 준비 (한 번만)

Python 3.8 이상이 필요합니다. 엑셀 리포트를 쓰려면 한 번 설치합니다.

```bash
pip install -r requirements.txt
```

명령은 모두 이 폴더에서 실행합니다. 경로에 공백이 있으면 따옴표로 감쌉니다.

## 쓰는 법

### 바뀐 파일 찾기 — folder_diff

```bash
python tools/folder_diff.py 이전폴더 현재폴더 -o reports/결과
```

추가·삭제·변경된 파일을 `reports/결과.xlsx`(목록)와 `reports/결과.html`(바뀐 내용)로 만듭니다.
→ [자세히](docs/folder_diff.md)

### 바뀐 함수 찾기 — func_diff

```bash
python tools/func_diff.py 이전폴더 현재폴더 -o reports/결과
```

`.c` 파일에서 추가·삭제·변경된 함수를 찾습니다. 엑셀이 그대로 리뷰 체크리스트가 됩니다.
리뷰할 함수만 고르려면 `-l 목록.xlsx` (A열 파일명, B열 함수명).
→ [자세히](docs/func_diff.md)

### 테스트 CSV 합치기 — merge_csv

```bash
python tools/merge_csv.py CSV폴더
python tools/merge_csv.py CSV폴더 --sum 신호    # 신호의 파일별 합계 칸 추가
python tools/merge_csv.py CSV폴더 --test-once   # 파일명을 파일의 첫 줄에만 적기
```

폴더 안의 CSV를 테스트 케이스 1개당 1줄인 `result.csv` 하나로 합칩니다. 줄마다 input·expect·output 신호가 한 칸씩 들어갑니다.
→ [자세히](docs/merge_csv.md)

### 이미지 글자를 텍스트로 — img_text

```bash
python tools/img_text.py 이미지또는폴더
```

이미지 안의 글자를 읽어 같은 이름의 `.txt`로 저장합니다 (`화면.png` → `화면.txt`). 설치할 것이 없습니다.
→ [자세히](docs/img_text.md)

## 안 될 때

[문제 해결](docs/troubleshooting.md)을 봅니다. folder_diff·func_diff의 옵션은 `-h`로도 볼 수 있습니다.
