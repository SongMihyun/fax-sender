import shutil
import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from fastapi.responses import Response
import fitz

from backend.core.settings import settings
from backend.database.db import get_conn, now_iso
from backend.models.schemas import DocumentMetadata, DocumentOut, DocumentPageInfo, DocumentPreview, ExtractFieldRequest
from backend.services.file_normalizer import normalize_to_pdf


def _file_url(path: str) -> str | None:
    file_path = Path(path)
    try:
        relative = file_path.relative_to(settings.storage_dir)
    except ValueError:
        return None
    return "/storage/" + relative.as_posix()


def _row_to_document(row) -> DocumentOut:
    return DocumentOut(
        id=row["id"],
        original_name=row["original_name"],
        stored_name=row["stored_name"],
        file_path=row["file_path"],
        file_url=_file_url(row["file_path"]),
        content_type=row["content_type"],
        size_bytes=row["size_bytes"],
        created_at=row["created_at"],
    )


async def save_upload(file: UploadFile) -> DocumentOut:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드할 수 있습니다.")

    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}_{Path(file.filename).name}"
    target_path = settings.uploads_dir / stored_name

    with target_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    size = target_path.stat().st_size
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO documents(
                original_name, stored_name, file_path, content_type, size_bytes, created_at,
                original_filename, stored_original_path, normalized_pdf_path, status, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PDF_CONVERTED', ?)
            """,
            (file.filename, stored_name, str(target_path), file.content_type, size, now_iso(), file.filename, str(target_path), str(target_path), now_iso()),
        )
        doc_id = cur.lastrowid

    return get_document(doc_id)


async def save_process_upload(file: UploadFile) -> DocumentOut:
    if not file.filename:
        raise HTTPException(status_code=400, detail="UNSUPPORTED_FILE_TYPE: PDF 또는 OZD 파일만 업로드할 수 있습니다.")

    original_name = Path(file.filename).name
    suffix = Path(original_name).suffix.lower()
    if suffix not in {".pdf", ".ozd"}:
        raise HTTPException(status_code=400, detail="UNSUPPORTED_FILE_TYPE: PDF 또는 OZD 파일만 업로드할 수 있습니다.")

    settings.original_uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.normalized_uploads_dir.mkdir(parents=True, exist_ok=True)
    stored_original_name = f"{uuid.uuid4().hex}_{original_name}"
    original_path = settings.original_uploads_dir / stored_original_name

    with original_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    normalized_path = normalize_to_pdf(original_path, settings.normalized_uploads_dir)
    size = normalized_path.stat().st_size
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO documents(
                original_name, stored_name, file_path, content_type, size_bytes, created_at,
                original_filename, stored_original_path, normalized_pdf_path, status, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PDF_CONVERTED', ?)
            """,
            (original_name, normalized_path.name, str(normalized_path), "application/pdf", size, now_iso(), original_name, str(original_path), str(normalized_path), now_iso()),
        )
        doc_id = cur.lastrowid

    return get_document(doc_id)


def list_documents() -> list[DocumentOut]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM documents ORDER BY id DESC").fetchall()
    return [_row_to_document(r) for r in rows]


def get_document(document_id: int) -> DocumentOut:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
    return _row_to_document(row)


def delete_document(document_id: int) -> dict[str, str]:
    document = get_document(document_id)
    with get_conn() as conn:
        used = conn.execute("SELECT id, name FROM pdf_templates WHERE document_id = ? LIMIT 1", (document_id,)).fetchone()
        if used:
            raise HTTPException(status_code=409, detail="이 문서는 템플릿에서 사용 중이므로 삭제할 수 없습니다.")
        conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))

    file_path = Path(document.file_path)
    if file_path.exists():
        file_path.unlink()
    return {"status": "deleted"}


def get_document_preview(document_id: int) -> DocumentPreview:
    document = get_document(document_id)
    file_path = Path(document.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="원본 PDF 파일을 찾을 수 없습니다.")

    pages: list[DocumentPageInfo] = []
    with fitz.open(file_path) as pdf:
        for index, page in enumerate(pdf, start=1):
            rect = page.rect
            pages.append(DocumentPageInfo(page=index, width=float(rect.width), height=float(rect.height)))

    return DocumentPreview(document=document, file_url=document.file_url or "", pages=pages)


def get_document_metadata(document_id: int) -> DocumentMetadata:
    preview = get_document_preview(document_id)
    return DocumentMetadata(document_id=document_id, page_count=len(preview.pages), pages=preview.pages)


def render_document_page_image(document_id: int, page_no: int, zoom: float = 2.0) -> Response:
    document = get_document(document_id)
    file_path = Path(document.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="원본 PDF 파일을 찾을 수 없습니다.")

    try:
        with fitz.open(file_path) as pdf:
            if page_no < 1 or page_no > pdf.page_count:
                raise HTTPException(status_code=404, detail="PDF 페이지를 찾을 수 없습니다.")
            page = pdf[page_no - 1]
            matrix = fitz.Matrix(zoom, zoom)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False, annots=True)
            return Response(
                content=pixmap.tobytes("png"),
                media_type="image/png",
                headers={"Cache-Control": "no-store"},
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF 페이지 렌더링 실패: {exc}") from exc


def extract_text_from_pdf_region(pdf_path: Path, field: ExtractFieldRequest) -> str:
    if field.unit != "pdf_point":
        raise HTTPException(status_code=400, detail="extract field unit은 pdf_point여야 합니다.")

    with fitz.open(pdf_path) as pdf:
        if field.page < 1 or field.page > pdf.page_count:
            raise HTTPException(status_code=400, detail=f"PDF 페이지 범위가 올바르지 않습니다: {field.page}")
        page = pdf[field.page - 1]
        rect = fitz.Rect(field.x, field.y, field.x + field.width, field.y + field.height)
        text = page.get_text("text", clip=rect)
    return re.sub(r"\s+", " ", text).strip()


def extract_text_with_ocr_fallback(pdf_path: Path, field: ExtractFieldRequest) -> str:
    # OCR fallback hook. 1차 구현은 PDF text layer 추출만 수행한다.
    return extract_text_from_pdf_region(pdf_path, field)


def extract_after_second_slash(text: str) -> tuple[str, str | None]:
    slash_positions = [match.start() for match in re.finditer("/", text)]
    if len(slash_positions) < 2:
        if slash_positions:
            return text[slash_positions[-1] + 1 :], '"/" 문자가 한 번만 있어 마지막 "/" 이후 텍스트를 사용했습니다.'
        return text, '"/" 문자가 없어 전체 추출 텍스트를 사용했습니다.'
    return text[slash_positions[1] + 1 :], None


def sanitize_manager_name(text: str) -> str:
    source = re.sub(r"\([^)]*\)", " ", text)
    korean_names = re.findall(r"[가-힣]{2,5}", source)
    if korean_names:
        return korean_names[-1]
    return re.sub(r"\s+", " ", re.sub(r"[^가-힣a-zA-Z\s]", " ", source)).strip()


def sanitize_manager_code(text: str) -> str:
    paren_numbers = re.findall(r"\(([^)]*\d[^)]*)\)", text)
    if paren_numbers:
        digits = re.sub(r"[^0-9]", "", paren_numbers[-1])
        if digits:
            return digits
    digit_groups = re.findall(r"\d{5,}", text)
    if digit_groups:
        return digit_groups[-1]
    return re.sub(r"[^0-9]", "", text)


def sanitize_person_name(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^가-힣a-zA-Z\s]", " ", text)).strip()


def sanitize_extracted_field(field_key: str, raw_text: str) -> tuple[str, str | None]:
    if field_key in {"manager_name", "manager_code"}:
        source_text, warning = extract_after_second_slash(raw_text)
        if field_key == "manager_name":
            return sanitize_manager_name(source_text), warning
        return sanitize_manager_code(source_text), warning
    if field_key == "customer_name":
        return sanitize_person_name(raw_text), None
    return raw_text.strip(), None


def extract_document_fields_detail(document_id: int, fields: list[ExtractFieldRequest]) -> dict[str, dict[str, str]]:
    document = get_document(document_id)
    pdf_path = Path(document.file_path)
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="원본 PDF 파일을 찾을 수 없습니다.")

    clean_fields: dict[str, str] = {}
    raw_fields: dict[str, str] = {}
    warnings: dict[str, str] = {}
    for field in fields:
        if not field.field_key:
            continue
        raw_text = extract_text_with_ocr_fallback(pdf_path, field)
        clean_text, warning = sanitize_extracted_field(field.field_key, raw_text)
        raw_fields[field.field_key] = raw_text
        clean_fields[field.field_key] = clean_text
        if warning:
            warnings[field.field_key] = warning
    return {"fields": clean_fields, "raw_fields": raw_fields, "warnings": warnings}


def extract_document_fields(document_id: int, fields: list[ExtractFieldRequest]) -> dict[str, str]:
    return extract_document_fields_detail(document_id, fields)["fields"]
