import json
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile

from backend.core.settings import settings
from backend.database.db import get_conn, now_iso
from backend.models.schemas import ExtractFieldRequest, ProcessRunRequest, ProcessStatusResponse, ProcessUploadResponse
from backend.services.admin_template_version_service import get_active_template_version
from backend.services.app_module_service import run_pdf_merge_engine
from backend.services.document_service import extract_document_fields_detail, get_document
from backend.services.file_normalizer import normalize_to_pdf
from backend.services.kakao_sender_adapter import send_pdf_to_self_via_kakao
from backend.services.template_merge_service import extract_template_batch_fields_detail, merge_template_pdf
from backend.models.schemas import TemplateMergeRequest


PROCESS_STEPS = {
    "upload": "UPLOADED",
    "normalize": "PDF_CONVERTED",
    "extract": "FIELD_EXTRACTED",
    "check_merge": "CHECK_MERGED",
    "signature_merge": "SIGNATURE_MERGED",
    "finalize": "FINALIZED",
    "kakao_send": "SENT",
}


def _log(document_id: int, step: str, status: str, message: str = "") -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO processing_logs(document_id, step, status, message, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (document_id, step, status, message, now_iso()),
        )


def update_document_status(document_id: int, status: str, **fields: Any) -> None:
    assignments = ["status = ?", "updated_at = ?"]
    values: list[Any] = [status, now_iso()]
    for key, value in fields.items():
        assignments.append(f"{key} = ?")
        values.append(value)
    values.append(document_id)
    with get_conn() as conn:
        conn.execute(f"UPDATE documents SET {', '.join(assignments)} WHERE id = ?", values)


def mark_document_failed(document_id: int, step: str, reason: str) -> None:
    update_document_status(document_id, "FAILED", failed_step=step, failed_reason=reason)
    _log(document_id, step, "FAILED", reason)


def _document_row(document_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="document not found")
    return row


def _legacy_template_exists(template_id: int | None) -> bool:
    if template_id is None:
        return False
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM pdf_templates WHERE id = ?", (template_id,)).fetchone()
    return row is not None


def _default_legacy_template_id() -> int | None:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT id
            FROM pdf_templates
            WHERE document_id IS NOT NULL
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
    return int(row["id"]) if row else None


def _overlay_has_positions(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    pages = data.get("pages", {}) if isinstance(data, dict) else {}
    if not isinstance(pages, dict):
        return False
    return any(page.get("positions") for page in pages.values() if isinstance(page, dict))


def _safe_filename_part(value: Any) -> str:
    text = str(value or "unknown").strip()
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r'[\\/:*?"<>|]', "", text)
    return (text or "unknown")[:60]


def _final_pdf_path(row) -> Path:
    base = "_".join(
        [
            _safe_filename_part(row["manager_code"]),
            _safe_filename_part(row["manager_name"]),
            _safe_filename_part(row["customer_name"]),
        ]
    )
    candidate = settings.final_output_dir / f"{base}.pdf"
    if not candidate.exists():
        return candidate
    return settings.final_output_dir / f"{base}_{now_iso().replace(':', '').replace('-', '').replace('T', '_')}.pdf"


async def upload_process_document(file: UploadFile) -> ProcessUploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="UNSUPPORTED_FILE_TYPE: PDF 또는 OZD 파일만 업로드할 수 있습니다.")
    original_filename = Path(file.filename).name
    suffix = Path(original_filename).suffix.lower()
    if suffix not in {".pdf", ".ozd"}:
        raise HTTPException(status_code=400, detail="UNSUPPORTED_FILE_TYPE: PDF 또는 OZD 파일만 업로드할 수 있습니다.")

    settings.incoming_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}_{original_filename}"
    original_path = settings.incoming_dir / stored_name
    with original_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    now = now_iso()
    size = original_path.stat().st_size
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO documents(
                original_name, stored_name, file_path, content_type, size_bytes, created_at,
                original_filename, stored_original_path, status, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'UPLOADED', ?)
            """,
            (original_filename, stored_name, str(original_path), file.content_type, size, now, original_filename, str(original_path), now),
        )
        document_id = cur.lastrowid
    _log(document_id, "upload", "UPLOADED", original_filename)
    return ProcessUploadResponse(document_id=document_id, status="UPLOADED")


def run_normalize(document_id: int) -> Path:
    try:
        row = _document_row(document_id)
        source = Path(row["stored_original_path"] or row["file_path"])
        normalized = normalize_to_pdf(source, settings.normalized_dir)
        update_document_status(
            document_id,
            "PDF_CONVERTED",
            normalized_pdf_path=str(normalized),
            file_path=str(normalized),
            stored_name=normalized.name,
            content_type="application/pdf",
            size_bytes=normalized.stat().st_size,
        )
        _log(document_id, "normalize", "PDF_CONVERTED", str(normalized))
        return normalized
    except Exception as exc:
        mark_document_failed(document_id, "normalize", str(exc))
        raise


def _load_extract_fields(version_row) -> list[ExtractFieldRequest]:
    if not version_row:
        return []
    path = Path(version_row["extract_config_path"])
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    fields = data.get("fields", data if isinstance(data, list) else [])
    return [ExtractFieldRequest(**field) for field in fields if isinstance(field, dict)]


def run_extract(document_id: int) -> dict[str, Any]:
    try:
        row = _document_row(document_id)
        legacy_template_id = int(row["template_id"]) if _legacy_template_exists(row["template_id"]) else _default_legacy_template_id()
        version = None if legacy_template_id else get_active_template_version(row["template_id"]) if row["template_id"] else get_active_template_version()

        if legacy_template_id:
            if row["template_id"] != legacy_template_id:
                update_document_status(document_id, row["status"], template_id=legacy_template_id)
            detail = extract_template_batch_fields_detail(legacy_template_id, document_id_override=document_id)
        else:
            if version and not row["template_version_id"]:
                update_document_status(document_id, row["status"], template_id=version["template_id"], template_version_id=version["id"])
            fields = _load_extract_fields(version)
            detail = extract_document_fields_detail(document_id, fields) if fields else {"fields": {}, "raw_fields": {}, "warnings": {}}

        settings.extracted_dir.mkdir(parents=True, exist_ok=True)
        extracted_path = settings.extracted_dir / f"document_{document_id}_extracted.json"
        extracted_path.write_text(json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8")
        clean = detail.get("fields", {})
        update_document_status(
            document_id,
            "FIELD_EXTRACTED",
            extracted_json_path=str(extracted_path),
            customer_name=clean.get("customer_name"),
            manager_name=clean.get("manager_name"),
            manager_code=clean.get("manager_code"),
        )
        _log(document_id, "extract", "FIELD_EXTRACTED", str(extracted_path))
        return detail
    except Exception as exc:
        mark_document_failed(document_id, "extract", str(exc))
        raise


def run_check_merge(document_id: int) -> None:
    update_document_status(document_id, "CHECK_MERGED")
    _log(document_id, "check_merge", "CHECK_MERGED", "check merge is handled by final PDF merge")


def run_signature_merge(document_id: int) -> None:
    update_document_status(document_id, "SIGNATURE_MERGED")
    _log(document_id, "signature_merge", "SIGNATURE_MERGED", "signature merge is handled by final PDF merge")


def run_finalize(document_id: int) -> Path:
    try:
        row = _document_row(document_id)
        pdf_path = Path(row["normalized_pdf_path"] or row["file_path"])
        if not pdf_path.exists():
            raise HTTPException(status_code=404, detail="normalized PDF not found")
        output_path = _final_pdf_path(row)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        legacy_template_id = int(row["template_id"]) if _legacy_template_exists(row["template_id"]) else _default_legacy_template_id()
        version = None if legacy_template_id else get_active_template_version(row["template_id"]) if row["template_id"] else get_active_template_version()
        if version and not _overlay_has_positions(Path(version["overlay_config_path"])):
            legacy_template_id = _default_legacy_template_id()
            version = None

        if legacy_template_id:
            if row["template_id"] != legacy_template_id:
                update_document_status(document_id, row["status"], template_id=legacy_template_id)
            result = merge_template_pdf(legacy_template_id, TemplateMergeRequest(), document_id_override=document_id)
            output_path = Path(result.output_path)
            row = _document_row(document_id)
        else:
            if version:
                form_data_path = settings.extracted_dir / f"document_{document_id}_form_data.json"
                form_data = {
                    "customer_name": row["customer_name"],
                    "manager_name": row["manager_name"],
                    "manager_code": row["manager_code"],
                }
                form_data_path.write_text(json.dumps(form_data, ensure_ascii=False, indent=2), encoding="utf-8")
                output_path = run_pdf_merge_engine(
                    pdf_path=pdf_path,
                    overlay_config_path=Path(version["overlay_config_path"]),
                    form_data_path=form_data_path,
                    output_path=output_path,
                )
            else:
                shutil.copy2(pdf_path, output_path)

        update_document_status(document_id, "FINALIZED", final_pdf_path=str(output_path))
        _log(document_id, "finalize", "FINALIZED", str(output_path))
        return Path(output_path)
    except Exception as exc:
        mark_document_failed(document_id, "finalize", str(exc))
        raise


def run_kakao_send(document_id: int, enabled: bool = False) -> None:
    row = _document_row(document_id)
    final_pdf_path = row["final_pdf_path"]
    if not final_pdf_path:
        raise HTTPException(status_code=400, detail="final PDF is required before Kakao send")
    if not enabled:
        _log(document_id, "kakao_send", "SKIPPED", "Kakao send disabled")
        return
    result = send_pdf_to_self_via_kakao(final_pdf_path)
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO send_logs(document_id, send_type, send_status, retry_count, message, created_at, sent_at)
            VALUES (?, 'KAKAO_SELF', ?, 0, ?, ?, ?)
            """,
            (document_id, "SUCCESS" if result.success else "FAILED", result.message, now_iso(), now_iso() if result.success else None),
        )
    if result.success:
        update_document_status(document_id, "SENT", sent_at=now_iso())
        _log(document_id, "kakao_send", "SENT", result.message)
    else:
        _log(document_id, "kakao_send", "FAILED", result.message)


def run_full_process(document_id: int, payload: ProcessRunRequest | None = None) -> ProcessStatusResponse:
    payload = payload or ProcessRunRequest()
    if payload.template_id or payload.template_version_id:
        update_document_status(document_id, _document_row(document_id)["status"], template_id=payload.template_id, template_version_id=payload.template_version_id)
    run_normalize(document_id)
    run_extract(document_id)
    run_check_merge(document_id)
    run_signature_merge(document_id)
    run_finalize(document_id)
    run_kakao_send(document_id, enabled=payload.send_kakao)
    return get_process_status(document_id)


def get_process_status(document_id: int) -> ProcessStatusResponse:
    row = _document_row(document_id)
    return ProcessStatusResponse(
        document_id=document_id,
        status=row["status"],
        customer_name=row["customer_name"],
        manager_name=row["manager_name"],
        manager_code=row["manager_code"],
        final_pdf_path=row["final_pdf_path"],
        failed_step=row["failed_step"],
        failed_reason=row["failed_reason"],
    )


def retry_process(document_id: int, payload: ProcessRunRequest | None = None) -> ProcessStatusResponse:
    update_document_status(document_id, "UPLOADED", failed_step=None, failed_reason=None)
    return run_full_process(document_id, payload)
