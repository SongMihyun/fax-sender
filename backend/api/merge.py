from fastapi import APIRouter
from backend.models.schemas import MergeRequest, MergeResponse
from backend.services.merge_service import run_pdf_merge

router = APIRouter()


@router.post("/pdf", response_model=MergeResponse)
def merge_pdf(payload: MergeRequest):
    return run_pdf_merge(payload)
