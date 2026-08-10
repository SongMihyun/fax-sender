import os
import shutil
import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from fastapi.responses import Response
import cv2
import fitz
import numpy as np
import pytesseract
from PIL import Image, ImageOps

from backend.core.settings import settings
from backend.database.db import get_conn, now_iso
from backend.models.schemas import DocumentMetadata, DocumentOut, DocumentPageInfo, DocumentPreview, ExtractFieldRequest
from backend.services.file_normalizer import normalize_to_pdf


def _configure_tesseract() -> None:
    # The desktop build ships its own Tesseract binary and Korean language
    # data.  Prefer the explicitly configured portable path so a new PC never
    # falls back to a developer machine's global installation (or PATH).
    configured_cmd = os.environ.get("TESSERACT_CMD") or settings.tesseract_cmd
    if configured_cmd and Path(configured_cmd).is_file():
        pytesseract.pytesseract.tesseract_cmd = configured_cmd
    else:
        bundled_cmd = settings.root_dir / "Tesseract-OCR" / "tesseract.exe"
        default_cmd = Path("C:/Program Files/Tesseract-OCR/tesseract.exe")
        if bundled_cmd.is_file():
            pytesseract.pytesseract.tesseract_cmd = str(bundled_cmd)
        elif default_cmd.is_file():
            pytesseract.pytesseract.tesseract_cmd = str(default_cmd)

    if settings.tessdata_dir.exists():
        korean_data = settings.tessdata_dir / "kor.traineddata"
        if korean_data.is_file():
            # Do not inherit an invalid machine-wide TESSDATA_PREFIX.
            os.environ["TESSDATA_PREFIX"] = str(settings.tessdata_dir)


_configure_tesseract()


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


def cleanup_process_document(document_id: int) -> None:
    """Drop a one-off /process, /fax upload once its result PDF has been produced.

    These uploads only exist to feed a single merge; unlike admin-registered
    template source PDFs, they don't need to stick around in 문서 관리 afterward.
    """
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        if not row:
            return
        used = conn.execute("SELECT id FROM pdf_templates WHERE document_id = ? LIMIT 1", (document_id,)).fetchone()
        if used:
            return
        conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))

    for path_str in {row["stored_original_path"], row["normalized_pdf_path"], row["file_path"]}:
        if not path_str:
            continue
        path = Path(path_str)
        try:
            if path.exists() and settings.storage_dir in path.parents:
                path.unlink()
        except OSError:
            pass


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


def _ocr_crop(pdf_path: Path, field: ExtractFieldRequest, zoom: float, padding: float) -> Image.Image | None:
    with fitz.open(pdf_path) as pdf:
        if field.page < 1 or field.page > pdf.page_count:
            return None
        page = pdf[field.page - 1]
        page_rect = page.rect
        # Pad the box before clipping: a tight box can shave off a character's top stroke
        # (e.g. ㅎ's top dash), which is enough for Tesseract to misread it as a different jamo (ㅇ).
        rect = fitz.Rect(
            max(page_rect.x0, field.x - padding),
            max(page_rect.y0, field.y - padding),
            min(page_rect.x1, field.x + field.width + padding),
            min(page_rect.y1, field.y + field.height + padding),
        )
        pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=rect, alpha=False)
        image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    return ImageOps.autocontrast(image.convert("L"))


OCR_LOW_CONFIDENCE_THRESHOLD = 60.0
HIEUT_INDEX = 18  # ㅎ in the 19-way initial-consonant table
IEUNG_INDEX = 11  # ㅇ
YEO_MEDIAL_INDEX = 6  # ㅕ
YE_MEDIAL_INDEX = 7  # ㅖ


def _swap_hieut_ieung_initial(char: str) -> str | None:
    """Swap a syllable's initial between ㅎ and ㅇ (e.g. 현<->연), else None if not applicable."""
    code = ord(char) - 0xAC00
    if code < 0 or code > 11171:
        return None
    initial_index, remainder = divmod(code, 588)
    if initial_index == HIEUT_INDEX:
        swapped_index = IEUNG_INDEX
    elif initial_index == IEUNG_INDEX:
        swapped_index = HIEUT_INDEX
    else:
        return None
    return chr(0xAC00 + swapped_index * 588 + remainder)


def _medial_index(char: str) -> int | None:
    code = ord(char) - 0xAC00
    if code < 0 or code > 11171:
        return None
    return (code % 588) // 28


def _replace_medial(char: str, target_medial_index: int) -> str:
    code = ord(char) - 0xAC00
    initial_index, remainder = divmod(code, 588)
    final_index = remainder % 28
    return chr(0xAC00 + initial_index * 588 + target_medial_index * 28 + final_index)


def _has_hieut_cap_stroke(char_crop: Image.Image) -> bool:
    """Tell ㅎ from ㅇ by looking for ㅎ's short cap stroke above the circle.

    ㅎ draws as a horizontal stroke sitting apart from the circle below it, which shows up as a
    sharp ink-density spike in the top ~40% of the glyph followed by a clear dip. Ieung's circle
    just curves smoothly into view with no such isolated spike.
    """
    if char_crop.width < 4 or char_crop.height < 4:
        return False
    arr = np.array(char_crop.convert("L"))
    _, thresh = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    ink = thresh > 0
    row_density = ink.sum(axis=1) / max(1, ink.shape[1])

    def longest_ink_run(row: np.ndarray) -> int:
        longest = 0
        current = 0
        for pixel in row:
            if pixel:
                current += 1
                longest = max(longest, current)
            else:
                current = 0
        return longest

    top_row_count = max(1, int(len(row_density) * 0.4))
    top_rows = row_density[:top_row_count]
    peak_index = int(np.argmax(top_rows))
    peak = top_rows[peak_index]
    lead_in = min(top_rows[:peak_index]) if peak_index > 0 else 0.0
    trail_out = min(top_rows[peak_index + 1 :]) if peak_index + 1 < len(top_rows) else peak
    cap_width = longest_ink_run(ink[peak_index]) / max(1, ink.shape[1])

    # Printed ㅎ on these forms often has a cap only half as wide as its
    # glyph box. The earlier density-only rule expected a much wider stroke,
    # so ``혜`` could be read as ``예``. A long upper horizontal run followed
    # by a clear gap is distinctive for ㅎ and is stable for any name position.
    return (
        cap_width >= 0.42
        and peak >= 0.18
        and (peak - lead_in) >= 0.18
        and (peak - trail_out) >= 0.12
    )


def _has_ye_right_facing_bars(char_crop: Image.Image) -> bool:
    """Detect ㅖ's extra right-hand vertical stem, distinguishing it from ㅕ.

    This check is only used after a glyph is already identified as ㅎ. It keeps
    the correction conservative: an OCR result such as ``여`` becomes ``혜``
    only when the image contains both the ㅎ cap and the extra ㅖ stem.
    """
    if char_crop.width < 10 or char_crop.height < 10:
        return False
    arr = np.array(char_crop.convert("L"))
    _, threshold = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    ink = threshold > 0
    height, width = ink.shape

    def longest_run(row: np.ndarray) -> int:
        longest = current = 0
        for pixel in row:
            if pixel:
                current += 1
                longest = max(longest, current)
            else:
                current = 0
        return longest

    # ㅖ is distinguished from ㅕ by two short horizontal bars extending to
    # the right of the vowel spine.  The former vertical-stem rule could not
    # recognise ordinary handwriting, so `혜` stayed incorrectly as `혀`.
    start_y, end_y = int(height * 0.20), int(height * 0.85)
    min_bar_width = max(3, int(width * 0.14))
    right_bar_rows: list[int] = []
    for y in range(start_y, max(start_y + 1, end_y)):
        right_run = longest_run(ink[y, int(width * 0.50) :])
        left_run = longest_run(ink[y, : int(width * 0.50)])
        if min_bar_width <= right_run <= int(width * 0.45) and right_run > left_run + 1:
            right_bar_rows.append(y)

    groups = 0
    previous = -3
    for row in right_bar_rows:
        if row > previous + 2:  # allow a 1px anti-aliasing gap
            groups += 1
        previous = row
    if groups >= 2:
        return True

    # A low-resolution scan can merge the two short ㅖ bars into nearly
    # vertical blobs. Keep a strict fallback for that resampling artifact.
    stem_groups = 0
    previous = -2
    for x in range(int(width * 0.52), width):
        if longest_run(ink[:, x]) >= height * 0.38:
            if x > previous + 1:
                stem_groups += 1
            previous = x
    return stem_groups >= 2


def _correct_hieut_ieung_confusion(image: Image.Image, text: str, data: dict) -> str:
    """Re-check ambiguous initial syllables against the actual pixels.

    Tesseract sometimes reads ㅎ as ㅇ (or vice versa) even when the top stroke is visible.
    Every Hangul syllable is inspected independently, so a ㅎ can be corrected at the beginning,
    middle, or end of a person's name; it is not tied to the character's position in the string.
    """
    hangul_chars = [char for char in text if "가" <= char <= "힣"]
    if not hangul_chars:
        return text

    boxes = [
        (left, top, width, height)
        for word, left, top, width, height in zip(data["text"], data["left"], data["top"], data["width"], data["height"])
        if any("가" <= char <= "힣" for char in word)
    ]
    if not boxes:
        return text

    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[0] + b[2] for b in boxes)
    y1 = max(b[1] + b[3] for b in boxes)
    if x1 <= x0 or y1 <= y0:
        return text

    char_width = (x1 - x0) / len(hangul_chars)
    corrected = list(hangul_chars)
    changed = False
    for index, char in enumerate(hangul_chars):
        swapped = _swap_hieut_ieung_initial(char)
        if swapped is None:
            continue
        left = int(x0 + index * char_width)
        right = int(x0 + (index + 1) * char_width)
        char_crop = image.crop((max(0, left), y0, min(image.width, right), y1))
        should_be_hieut = _has_hieut_cap_stroke(char_crop)
        is_hieut = (ord(char) - 0xAC00) // 588 == HIEUT_INDEX
        candidate = swapped if should_be_hieut != is_hieut else char
        if should_be_hieut and _medial_index(candidate) == YEO_MEDIAL_INDEX and _has_ye_right_facing_bars(char_crop):
            candidate = _replace_medial(candidate, YE_MEDIAL_INDEX)
        if candidate != char:
            corrected[index] = candidate
            changed = True

    if not changed:
        return text

    corrected_iter = iter(corrected)
    return "".join(next(corrected_iter) if "가" <= char <= "힣" else char for char in text)


def _ocr_pdf_region(pdf_path: Path, field: ExtractFieldRequest, zoom: float = 6.0, padding: float = 4.0) -> tuple[str, float | None]:
    """OCR a single field's box, used when the PDF has no text layer there (scanned form).

    Returns (text, worst_word_confidence). Confidence is None when nothing was recognized.
    The *minimum* per-word confidence is used (not the average) so a single misread character
    (e.g. one wrong jamo in a name) isn't diluted away by other, easier words in the same box.
    """
    image = _ocr_crop(pdf_path, field, zoom, padding)
    if image is None:
        return "", None
    try:
        # Most registered regions contain one line.  Some scans, however,
        # shift a separator line into the crop; PSM 7 then reports no text at
        # all despite the name being visible.  Retry only that empty case with
        # the compact multi-line mode rather than dropping the field.
        text = pytesseract.image_to_string(image, lang="kor+eng", config="--psm 7")
        data = pytesseract.image_to_data(image, lang="kor+eng", config="--psm 7", output_type=pytesseract.Output.DICT)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            text = pytesseract.image_to_string(image, lang="kor+eng", config="--psm 6")
            data = pytesseract.image_to_data(image, lang="kor+eng", config="--psm 6", output_type=pytesseract.Output.DICT)
            text = re.sub(r"\s+", " ", text).strip()
    except pytesseract.TesseractNotFoundError:
        return "", None
    if not text:
        return "", None
    confidences = [float(conf) for word, conf in zip(data["text"], data["conf"]) if word.strip() and str(conf) not in ("-1", "")]
    min_confidence = min(confidences) if confidences else None
    # A name can contain one confidently misread syllable while the whole OCR
    # word reports high confidence. This glyph check changes only the known
    # ㅎ/ㅇ ambiguity, so run it for every OCR result.
    text = _correct_hieut_ieung_confusion(image, text, data)
    return text, min_confidence


def extract_text_with_ocr_fallback(pdf_path: Path, field: ExtractFieldRequest) -> tuple[str, float | None]:
    """Returns (text, ocr_confidence). ocr_confidence is None when the text layer was used (no OCR needed)."""
    text_layer_result = extract_text_from_pdf_region(pdf_path, field)
    if text_layer_result:
        return text_layer_result, None
    # No text under this box -> likely a scanned/image-only PDF, fall back to OCR.
    return _ocr_pdf_region(pdf_path, field)


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
    # A PSM-6 fallback can retain a small amount of table-line noise around a
    # scanned name.  Prefer an actual Korean name token when one was found.
    korean_names = re.findall(r"[가-힣]{2,5}", text)
    if korean_names:
        return korean_names[-1]
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
        raw_text, _ocr_confidence = extract_text_with_ocr_fallback(pdf_path, field)
        clean_text, warning = sanitize_extracted_field(field.field_key, raw_text)
        raw_fields[field.field_key] = raw_text
        clean_fields[field.field_key] = clean_text
        if warning:
            warnings[field.field_key] = warning
    return {"fields": clean_fields, "raw_fields": raw_fields, "warnings": warnings}


def extract_document_fields(document_id: int, fields: list[ExtractFieldRequest]) -> dict[str, str]:
    return extract_document_fields_detail(document_id, fields)["fields"]
