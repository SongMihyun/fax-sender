from fastapi import APIRouter

from backend.models.schemas import ExtractFieldsResponse, TemplateCreate, TemplateMergeRequest, TemplateMergeResponse, TemplateOut, TemplatePublicOut, TemplateUpdate
from backend.services.template_merge_service import extract_template_fields_detail, merge_template_pdf
from backend.services.template_service import create_template, delete_template, get_template, list_public_templates, list_templates, update_template

router = APIRouter()


@router.get("", response_model=list[TemplateOut])
def templates():
    return list_templates()


@router.get("/public", response_model=list[TemplatePublicOut])
def public_templates():
    return list_public_templates()


@router.post("", response_model=TemplateOut)
def post_template(payload: TemplateCreate):
    return create_template(payload)


@router.get("/{template_id}", response_model=TemplateOut)
def template_detail(template_id: int):
    return get_template(template_id)


@router.post("/{template_id}/extract-fields", response_model=ExtractFieldsResponse)
def template_extract_fields(template_id: int):
    return ExtractFieldsResponse(**extract_template_fields_detail(template_id))


@router.post("/{template_id}/merge", response_model=TemplateMergeResponse)
def template_merge(template_id: int, payload: TemplateMergeRequest):
    return merge_template_pdf(template_id, payload)


@router.put("/{template_id}", response_model=TemplateOut)
def put_template(template_id: int, payload: TemplateUpdate):
    return update_template(template_id, payload)


@router.patch("/{template_id}", response_model=TemplateOut)
def patch_template(template_id: int, payload: TemplateUpdate):
    return update_template(template_id, payload)


@router.delete("/{template_id}")
def remove_template(template_id: int):
    return delete_template(template_id)
