from fastapi import APIRouter

from backend.models.schemas import AdminTemplateCreate, AdminTemplateOut, ExtractFieldsResponse, TemplateVersionCreate, TemplateVersionOut
from backend.services.admin_template_version_service import (
    activate_template_version,
    create_admin_template,
    create_template_version,
    get_template_version,
    list_admin_templates,
)

router = APIRouter()


@router.get("/templates", response_model=list[AdminTemplateOut])
def admin_templates():
    return list_admin_templates()


@router.post("/templates", response_model=AdminTemplateOut)
def post_admin_template(payload: AdminTemplateCreate):
    return create_admin_template(payload)


@router.post("/templates/{template_id}/versions", response_model=TemplateVersionOut)
def post_template_version(template_id: int, payload: TemplateVersionCreate):
    return create_template_version(template_id, payload)


@router.put("/template-versions/{version_id}/activate", response_model=TemplateVersionOut)
def put_template_version_activate(version_id: int):
    return activate_template_version(version_id)


@router.get("/template-versions/{version_id}", response_model=TemplateVersionOut)
def admin_template_version(version_id: int):
    return get_template_version(version_id)


@router.post("/template-versions/{version_id}/test-extract", response_model=ExtractFieldsResponse)
def template_version_test_extract(version_id: int):
    get_template_version(version_id)
    return ExtractFieldsResponse()


@router.post("/template-versions/{version_id}/test-merge")
def template_version_test_merge(version_id: int):
    get_template_version(version_id)
    return {"status": "not_configured", "message": "Sample based merge test endpoint is reserved for the Admin UI workflow."}
