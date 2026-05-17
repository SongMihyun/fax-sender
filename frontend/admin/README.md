# Fax Sender Admin Frontend

React, TypeScript, Vite, Tailwind 기반 관리자 MVP입니다.

## 실행

백엔드:

```bash
cd D:\M-project\fax-sender
poetry run uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

프론트엔드:

```bash
cd D:\M-project\fax-sender\frontend\admin
npm install
npm run dev
```

브라우저:

```text
http://127.0.0.1:5173
```

API 주소를 바꾸려면 `.env` 또는 실행 환경에 아래 값을 지정합니다.

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## 연결 API

- `GET /api/health`
- `POST /api/documents/upload`
- `GET /api/documents`
- `GET /api/documents/{document_id}/preview`
- `GET /api/documents/{document_id}/metadata`
- `GET /api/documents/{document_id}/pages/{page_no}/image`
- `POST /api/documents/{document_id}/extract-fields`
- `DELETE /api/documents/{document_id}`
- `GET /api/templates`
- `POST /api/templates`
- `GET /api/templates/{template_id}`
- `PATCH /api/templates/{template_id}`
- `POST /api/templates/{template_id}/extract-fields`
- `POST /api/templates/{template_id}/merge`
- `PUT /api/templates/{template_id}`
- `DELETE /api/templates/{template_id}`
- `POST /api/check-assets/sources`
- `GET /api/check-assets`
- `GET /api/check-assets/{asset_id}/image`
- `DELETE /api/check-assets/{asset_id}`
- `GET /api/configs/overlay`
- `POST /api/configs/overlay`
- `GET /api/configs/form-data`
- `POST /api/configs/form-data`
- `POST /api/merge/pdf`

## 현재 기능

- 백엔드 health 확인
- 좌측 메인 메뉴 기반 Admin 구조
- PDF 업로드
- 문서 삭제. 템플릿에서 사용 중인 문서는 백엔드에서 삭제 차단
- 문서 목록 조회와 선택
- 공통 PDF 템플릿 생성/수정/삭제
- 템플릿 관리 내부 탭: 기본 정보, 좌표 설정, 스타일 설정, 테스트
- 템플릿별 기준 PDF 지정
- PDF 좌표 에디터로 체크, 날짜, 서명, 이름 영역 지정
- PDF 좌표 에디터로 고객명/팀장명/코드 추출 영역 지정
- 좌표 에디터 PDF 미리보기는 백엔드 PyMuPDF PNG 렌더링 사용
- 체크 원본 사진 업로드 및 자동 분리
- 추출된 투명 PNG 체크 에셋 미리보기/삭제
- 템플릿별 overlay config JSON 조회/수정
- form-data JSON 조회/수정
- render_style JSON 조회/수정
- 선택 템플릿 좌표 기준 PDF merge 실행
- 테스트 합성 시 check 위치에 체크 에셋 랜덤 적용
- 테스트 합성 시 customer_name 기반 generated_signature 자동 생성
- 최종 PDF 파일명 자동 생성: `manager_code_manager_name_customer_name.pdf`
- merge 결과 또는 에러 메시지 표시

## 화면 구조

- `문서 관리`: PDF 업로드, 문서 목록, 상세 확인, 삭제
- `템플릿 관리`: 템플릿 목록, 상세 편집, 좌표/스타일/form_data 관리
- `체크 에셋 관리`: 손체크 원본 업로드, 자동 분리, PNG 미리보기, 삭제
- `테스트 합성`: 템플릿 선택, form_data 입력, 합성 실행, 결과 확인
- `서명 관리`, `팩스 발송 관리`, `로그 관리`: 향후 확장 placeholder

## 좌표 저장 방식

좌표 에디터는 화면 픽셀 좌표가 아니라 PDF 원본 크기 기준 좌표로 저장합니다.

```json
{
  "id": "p1_signature_1",
  "type": "signature",
  "page": 1,
  "x": 410,
  "y": 680,
  "width": 160,
  "height": 55,
  "unit": "pdf_point"
}
```
