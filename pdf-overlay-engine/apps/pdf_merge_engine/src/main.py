# apps/pdf_merge_engine/src/main.py

from __future__ import annotations

import argparse
import json
from pathlib import Path

from shared.paths import (
    CONFIG_PATH,
    FORM_DATA_PATH,
    ORIGINAL_PDF_PATH,
    OUTPUT_PATH,
    PROJECT_ROOT,
)

from apps.pdf_merge_engine.src.overlay_loader import load_overlay_config
from apps.pdf_merge_engine.src.overlay_renderer import render_overlays
from apps.pdf_merge_engine.src.pdf_loader import load_pdf
from apps.pdf_merge_engine.src.pdf_writer import save_pdf


def load_form_data(path: Path = FORM_DATA_PATH) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"form_data.json 파일이 없습니다: {path}")

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def run_merge(
    pdf_path: str | Path = ORIGINAL_PDF_PATH,
    overlay_config_path: str | Path = CONFIG_PATH,
    form_data_path: str | Path = FORM_DATA_PATH,
    output_path: str | Path = OUTPUT_PATH,
) -> Path:
    """PDF 합성 엔진 재사용 진입점.

    backend에서는 이 함수만 호출한다.
    기존 단독 실행 방식은 main()으로 유지한다.
    """
    pdf_path = Path(pdf_path)
    overlay_config_path = Path(overlay_config_path)
    form_data_path = Path(form_data_path)
    output_path = Path(output_path)

    doc = load_pdf(pdf_path)
    overlay_config = load_overlay_config(overlay_config_path)
    form_data = load_form_data(form_data_path)

    print("PDF loaded:", pdf_path)
    print("Overlay loaded:", overlay_config_path)
    print("Form data loaded:", form_data_path)

    render_overlays(
        doc=doc,
        overlay_config=overlay_config,
        form_data=form_data,
        project_root=PROJECT_ROOT,
    )

    save_pdf(doc, output_path)

    print("Final PDF saved:", output_path)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="PDF overlay merge engine")
    parser.add_argument("--pdf", default=str(ORIGINAL_PDF_PATH))
    parser.add_argument("--overlay-config", default=str(CONFIG_PATH))
    parser.add_argument("--form-data", default=str(FORM_DATA_PATH))
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    args = parser.parse_args()

    run_merge(
        pdf_path=args.pdf,
        overlay_config_path=args.overlay_config,
        form_data_path=args.form_data,
        output_path=args.output,
    )


if __name__ == "__main__":
    main()
