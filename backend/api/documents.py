from fastapi import APIRouter, File, UploadFile
from fastapi.responses import Response

from backend.models.schemas import DocumentMetadata, DocumentOut, DocumentPreview, ExtractFieldsPayload, ExtractFieldsResponse
from backend.services.document_service import (
    delete_document,
    get_document,
    get_document_metadata,
    get_document_preview,
    extract_document_fields,
    extract_document_fields_detail,
    list_documents,
    render_document_page_image,
    save_upload,
)

router = APIRouter()


@router.post("/upload", response_model=DocumentOut)
async def upload_pdf(file: UploadFile = File(...)):
    return await save_upload(file)


@router.get("", response_model=list[DocumentOut])
def documents():
    return list_documents()


@router.get("/{document_id}/preview", response_model=DocumentPreview)
def document_preview(document_id: int):
    return get_document_preview(document_id)


@router.get("/{document_id}/metadata", response_model=DocumentMetadata)
def document_metadata(document_id: int):
    return get_document_metadata(document_id)


@router.post("/{document_id}/extract-fields", response_model=ExtractFieldsResponse)
def document_extract_fields(document_id: int, payload: ExtractFieldsPayload):
    return ExtractFieldsResponse(**extract_document_fields_detail(document_id, payload.fields))


@router.get("/{document_id}/pages/{page_no}/image", response_class=Response)
def document_page_image(document_id: int, page_no: int):
    return render_document_page_image(document_id, page_no)


@router.get("/{document_id}", response_model=DocumentOut)
def document_detail(document_id: int):
    return get_document(document_id)


@router.delete("/{document_id}")
def remove_document(document_id: int):
    return delete_document(document_id)
