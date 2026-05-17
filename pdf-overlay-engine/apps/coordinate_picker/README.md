# MP4-1 PDF 좌표 선택기

## 목적
샘플 PDF를 화면에 띄운 뒤, 사용자가 원하는 위치와 서명/체크/날짜/이미지 크기를 네모로 드래그 선택합니다.
선택한 좌표는 `configs/overlay_config.json`에 저장되며, 이후 MP-4 PDF 합성 엔진에서 그대로 사용할 수 있습니다.

## 기준 경로

```bash
pdf-overlay-engine
├ apps
│  └ coordinate_picker
│     ├ src
│     │  └ main.py
│     ├ assets
│     └ requirements.txt
├ configs
│  └ overlay_config.json
├ output
└ shared
```

## 설치
`pdf-overlay-engine` 루트에서 실행합니다.

```bash
pip install -r apps/coordinate_picker/requirements.txt
```

Poetry 사용 시:

```bash
poetry add PySide6 PyMuPDF
```

## 실행
`pdf-overlay-engine` 루트에서 실행합니다.

```bash
python apps/coordinate_picker/src/main.py
```

## 사용 순서
1. `PDF 열기` 클릭
2. 샘플 PDF 선택
3. 우측에서 영역 ID 입력 예: `signature_1`, `p1_check_1`, `date_1`
4. 종류 선택: `signature`, `check`, `date`, `image`
5. 필요 시 `매칭 이미지 선택` 클릭 후 서명 PNG 등 선택
6. PDF 위에서 원하는 위치와 크기를 사각형으로 드래그
7. `선택 영역 저장` 클릭
8. 모든 좌표 선택 후 `JSON 저장` 클릭

## 저장 JSON 예시

```json
{
  "pages": {
    "1": {
      "positions": [
        {
          "id": "signature_1",
          "type": "signature",
          "x": 400.0,
          "y": 720.0,
          "width": 150.0,
          "height": 60.0,
          "image_path": "D:/M-project/fax-sender/pdf-overlay-engine/apps/coordinate_picker/assets/signature.png"
        }
      ]
    }
  }
}
```

## MP-4 엔진 연동 포인트
기존 `overlay_renderer.py`가 `overlay_config.json`의 `pages > page_no > positions` 구조를 읽고 있다면 `id`, `x`, `y`, `width`, `height`는 그대로 사용 가능합니다.

`type`과 `image_path`는 MP4-1에서 추가한 필드입니다. 기존 엔진에서 무시해도 되고, 이미지 매칭 자동화에 활용해도 됩니다.
