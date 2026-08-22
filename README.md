# 송미현 자동팩스 프로젝트

## 확정 구조

```text
fax-sender/
├ backend/              # FastAPI API orchestration
├ frontend/             # admin / mobile UI
├ pdf-overlay-engine/   # PDF 좌표/합성/팩스/스케줄러 엔진
├ storage/              # 업로드/생성/서명/아카이브/DB 공용 저장소
├ shared/               # 향후 전역 공용 코드
├ main.py               # 개발용 backend 실행 shortcut
└ pyproject.toml        # 루트 Poetry 환경
```

## 역할 정의

```text
backend = API endpoint, DB, 상태관리, 엔진 호출
frontend = 관리자/모바일 UI
pdf-overlay-engine = 핵심 엔진 모듈
storage = 런타임 데이터 저장소
```

## 실행 방법

```bash
cd D:\M-project\fax-sender
poetry install
poetry run uvicorn backend.main:app --reload --host 127.0.0.1 --port 8791
```

또는:

```bash
poetry run python main.py
```

## 확인 URL

```text
http://127.0.0.1:8791/docs
http://127.0.0.1:8791/api/health
```

## 주요 변경점

- `pdf-overlay-engine/backend`를 `fax-sender/backend`로 분리
- `storage`를 루트 공용 저장소로 이동
- `pdf-overlay-engine/configs`는 기존 MP2/MP3 호환을 위해 유지
- backend에서 PDF 합성은 `backend/services/app_module_service.py`를 통해 엔진 호출
- PDF 합성 엔진에 재사용 진입점 `run_merge(...)` 추가

## PDF 합성 단독 실행

```bash
cd D:\M-project\fax-sender
poetry run python pdf-overlay-engine/main.py
```

## Backend에서 PDF 합성 호출 흐름

```text
/api/merge/pdf
→ backend.services.merge_service.run_pdf_merge
→ backend.services.app_module_service.run_pdf_merge_engine
→ pdf-overlay-engine/apps/pdf_merge_engine/src/main.py::run_merge
```

## Admin frontend

```bash
cd D:\M-project\fax-sender\frontend\admin
npm install
npm run dev
```

```text
http://127.0.0.1:5791/faxsender/
http://127.0.0.1:5791/admin/
```

기본 진입 화면은 `/process` 사용자단 PDF 자동 처리 화면입니다.
운영자 화면은 `/admin` 직접 URL로 진입하며, 1차 보호 비밀번호는 `VITE_ADMIN_PASSWORD` 환경변수로 바꿀 수 있습니다.
환경변수가 없으면 개발 기본값은 `admin`입니다.

관리자 화면에서는 공통 PDF 템플릿을 생성, 수정, 삭제할 수 있습니다.
각 템플릿은 기준 PDF 문서와 overlay config 좌표값을 함께 저장합니다.
좌표 에디터에서 저장되는 위치값은 화면 픽셀이 아니라 PDF 원본 좌표인 `pdf_point` 기준입니다.
체크 에셋 관리는 사용자가 업로드한 실제 체크 사진에서 선만 추출해 투명 PNG로 저장하며, 생성형 이미지로 새 체크를 만들지 않습니다.
손글씨 자모 관리는 `/admin`의 별도 메뉴에서 원본 사진을 업로드한 뒤 초성/중성/종성별 드래그 영역을 투명 PNG로 저장합니다.
`jamo_composed_signature` 서명 모드는 고객명을 한글 자모로 분해하고 저장된 자모 PNG를 랜덤 조합해 서명 이미지를 생성합니다.

## Kakao self notification

FaxSender can send a KakaoTalk PC self-chat notification after final PDF generation when `send_kakao=true`.

```toml
kakao-pc-driver = { path = "../KakaoCampaignSender/packages/kakao_pc_driver", develop = true }
```

Optional `.env` values:

```env
KAKAO_MY_NAME=Your Name
KAKAO_SPEED_MODE=normal
```

KakaoTalk PC must be running and signed in on Windows.
