# pdf-overlay-engine

## 프로젝트 목적

메리츠 가입설계 동의서 PDF 내 고정 입력 영역 좌표를 정의하는 독립 프로젝트입니다.

현재 MP-2 역할:

```text
어디에 입력할 것인가?
```

현재는 **좌표 정의 전용 엔진**이며 실제 데이터 삽입은 수행하지 않습니다.

---

# 프로젝트 경로

```text
D:\M-project\fax-sender\pdf-overlay-engine
```

---

# 개발 환경

* IDE: PyCharm Professional
* Python: 3.11.9
* Poetry 사용

가상환경:

```text
D:\M-project\fax-sender\pdf-overlay-engine\.venv
```

---

# 초기 환경 이슈

Poetry가 잘못된 python 경로를 참조함:

```text
C:\Users\idbla\AppData\Local\Microsoft\WindowsApps\python.exe
```

해결:

```bash
poetry env use "C:\Users\idbla\AppData\Local\Programs\Python\Python311\python.exe"
```

---

# 현재 프로젝트 구조

```text
pdf-overlay-engine/

├ .venv/
├ pyproject.toml
├ poetry.lock
├ README.md

├ configs/
│   └ overlay_config.json

└ apps/
    └ coordinate_picker/
        ├ sample/
        │   └ meritz_sample.pdf
        │
        └ src/
            ├ main.py
            └ json_exporter.py
```

---

# 삭제된 파일

초기 설계 대비 제거된 파일:

```text
pdf_loader.py
image_renderer.py
coordinate_picker.py
overlay_executor.py
```

사유:

현재 MP-2 범위를 초과했기 때문

---

# 핵심 산출물

```text
configs/overlay_config.json
```

현재 저장 정보:

* Page1 체크 3개
* Page2 체크 4개
* Page3 체크 3개
* 서명 영역 1개
* 날짜 영역 1개

총:

```text
체크 10개
서명 1개
날짜 1개
```

---

# 현재 역할 분리

## MP-2

```text
좌표 정의
```

## MP-3

```text
모바일 입력 데이터 생성
```

## MP-4

```text
실제 PDF 합성
```

## MP-5

```text
팩스 발송
```

---

# 현재 완료 상태

* 환경 구축 완료
* 좌표 구조 설계 완료
* 메리츠 PDF 하드코딩 완료
* JSON 분리 완료
* 상위 프로젝트 연동 준비 완료

## 상태

```text
MP-2 MVP 완료
```

---

# 향후 MP-2 v2

향후 개발 예정:

```text
새 PDF 업로드
→ 직접 클릭
→ 좌표 선택
→ JSON 자동 생성
```

---

# 다음 단계

```text
overlay_config.json
+
모바일 입력 데이터
=
최종 PDF 생성
```

즉, 다음 개발 단계는 **MP-4 PDF 합성 엔진 개발**입니다.
