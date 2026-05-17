from pathlib import Path

from fastapi import HTTPException

from backend.core.settings import settings
from backend.database.db import get_conn, now_iso
from backend.models.schemas import MergeRequest, MergeResponse
from backend.services.app_module_service import run_pdf_merge_engine
from backend.services.document_service import get_document
from backend.services.template_service import write_template_overlay_config


def _resolve_pdf_path(payload: MergeRequest) -> Path:
    if payload.document_id is not None:
        return Path(get_document(payload.document_id).file_path)
    if payload.pdf_path:
        return Path(payload.pdf_path)
    raise HTTPException(status_code=400, detail="document_id 또는 pdf_path가 필요합니다.")


def run_pdf_merge(payload: MergeRequest) -> MergeResponse:
    pdf_path = _resolve_pdf_path(payload)
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="원본 PDF 파일을 찾을 수 없습니다.")

    if payload.template_id is not None:
        overlay_config_path = write_template_overlay_config(payload.template_id)
    else:
        overlay_config_path = Path(payload.overlay_config_path) if payload.overlay_config_path else settings.overlay_config_path
    form_data_path = Path(payload.form_data_path) if payload.form_data_path else settings.form_data_path
    output_path = settings.final_output_dir / f"final_{now_iso().replace(':', '').replace('-', '').replace('T', '_')}.pdf"

    try:
        result_path = run_pdf_merge_engine(
            pdf_path=pdf_path,
            overlay_config_path=overlay_config_path,
            form_data_path=form_data_path,
            output_path=output_path,
        )
        status = "success"
        message = "PDF 합성이 완료되었습니다."
    except Exception as exc:
        result_path = None
        status = "failed"
        message = str(exc)

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO merge_runs(document_id, status, output_path, message, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (payload.document_id, status, str(result_path) if result_path else None, message, now_iso()),
        )

    if status == "failed":
        raise HTTPException(status_code=500, detail=message)

    return MergeResponse(status=status, output_path=str(result_path), message=message)
