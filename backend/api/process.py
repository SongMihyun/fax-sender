from fastapi import APIRouter, File, Form, UploadFile

from backend.models.schemas import ProcessExtractResponse, ProcessMergeRequest, ProcessPdfResponse, ProcessRunRequest, ProcessStatusResponse, ProcessUploadResponse, TemplateMergeRequest
from backend.services.document_service import cleanup_process_document, save_process_upload
from backend.services.process_service import get_process_status, retry_process, run_full_process, upload_process_document
from backend.services.template_merge_service import extract_template_batch_fields_detail, merge_template_pdf

router = APIRouter()


@router.post("/upload", response_model=ProcessUploadResponse)
async def upload_process_file(file: UploadFile = File(...)):
    return await upload_process_document(file)


@router.post("/{document_id}/run", response_model=ProcessStatusResponse)
def run_process_document(document_id: int, payload: ProcessRunRequest = ProcessRunRequest()):
    return run_full_process(document_id, payload)


@router.get("/{document_id}", response_model=ProcessStatusResponse)
def process_document_status(document_id: int):
    return get_process_status(document_id)


@router.post("/{document_id}/retry", response_model=ProcessStatusResponse)
def retry_process_document(document_id: int, payload: ProcessRunRequest = ProcessRunRequest()):
    return retry_process(document_id, payload)


@router.post("/extract", response_model=ProcessExtractResponse)
async def extract_process_pdf(template_id: int = Form(...), file: UploadFile = File(...)):
    document = await save_process_upload(file)
    detail = extract_template_batch_fields_detail(template_id, document_id_override=document.id)
    return ProcessExtractResponse(
        document_id=document.id,
        original_name=document.original_name,
        extracted_fields=detail.get("fields", {}),
        raw_fields=detail.get("raw_fields", {}),
        warnings=detail.get("warnings", {}),
        page_count=detail.get("page_count"),
        group_page_count=detail.get("group_page_count"),
        batch_count=detail.get("batch_count"),
        batch_items=detail.get("batch_items", []),
    )


@router.post("/merge", response_model=ProcessPdfResponse)
def merge_process_pdf(payload: ProcessMergeRequest):
    result = merge_template_pdf(
        payload.template_id,
        TemplateMergeRequest(form_data=payload.form_data),
        document_id_override=payload.document_id,
    )
    if result.success:
        cleanup_process_document(payload.document_id)
    return ProcessPdfResponse(
        success=result.success,
        process_id=None,
        extracted_fields=result.extracted_fields,
        raw_fields={},
        warnings=result.applied_style_profile.get("extract_warnings", {}),
        page_count=result.applied_style_profile.get("source_page_count"),
        group_page_count=result.applied_style_profile.get("group_page_count"),
        batch_count=result.applied_style_profile.get("batch_count"),
        batch_items=result.applied_style_profile.get("batch_items", []),
        output_filename=result.output_filename,
        output_path=result.output_path,
        download_url=f"/final-output/{result.output_filename}",
        message=result.message,
        applied_style_profile=result.applied_style_profile,
    )


@router.post("/pdf", response_model=ProcessPdfResponse)
async def process_pdf(template_id: int = Form(...), file: UploadFile = File(...)):
    document = await save_process_upload(file)
    result = merge_template_pdf(template_id, TemplateMergeRequest(), document_id_override=document.id)
    if result.success:
        cleanup_process_document(document.id)
    batch_items = result.applied_style_profile.get("batch_items", [])
    first_batch = batch_items[0] if batch_items else {}
    return ProcessPdfResponse(
        success=result.success,
        process_id=None,
        extracted_fields=result.extracted_fields,
        raw_fields=first_batch.get("raw_fields", {}),
        warnings=result.applied_style_profile.get("extract_warnings", {}),
        page_count=result.applied_style_profile.get("source_page_count"),
        group_page_count=result.applied_style_profile.get("group_page_count"),
        batch_count=result.applied_style_profile.get("batch_count"),
        batch_items=batch_items,
        output_filename=result.output_filename,
        output_path=result.output_path,
        download_url=f"/final-output/{result.output_filename}",
        message=result.message,
        applied_style_profile=result.applied_style_profile,
    )
