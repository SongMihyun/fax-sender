from fastapi import APIRouter, File, Query, UploadFile
from fastapi.responses import FileResponse

from backend.models.schemas import JamoAssetCreate, JamoAssetOut, JamoAssetPatch, JamoSignaturePreviewRequest, JamoSignaturePreviewResponse, JamoSourceUploadResponse
from backend.services.jamo_asset_service import (
    create_jamo_signature_preview,
    delete_jamo_asset,
    list_jamo_assets,
    resolve_jamo_asset,
    resolve_jamo_source,
    save_jamo_asset,
    update_jamo_asset,
    upload_jamo_source,
)

router = APIRouter()


@router.post("/sources", response_model=JamoSourceUploadResponse)
async def upload_source(file: UploadFile = File(...)):
    return await upload_jamo_source(file)


@router.get("/sources/{source_id}/image")
def source_image(source_id: str):
    return FileResponse(resolve_jamo_source(source_id))


@router.post("/assets", response_model=list[JamoAssetOut])
def create_asset(payload: JamoAssetCreate):
    return save_jamo_asset(payload)


@router.get("/assets", response_model=list[JamoAssetOut])
def assets(category: str | None = Query(default=None), jamo: str | None = Query(default=None), include_inactive: bool = True):
    return list_jamo_assets(category=category, jamo=jamo, include_inactive=include_inactive)


@router.get("/assets/{asset_id}/image")
def asset_image(asset_id: str):
    return FileResponse(resolve_jamo_asset(asset_id), media_type="image/png")


@router.patch("/assets/{asset_id}", response_model=JamoAssetOut)
def patch_asset(asset_id: str, payload: JamoAssetPatch):
    return update_jamo_asset(asset_id, payload.active)


@router.delete("/assets/{asset_id}")
def remove_asset(asset_id: str):
    return delete_jamo_asset(asset_id)


@router.post("/signature-preview", response_model=JamoSignaturePreviewResponse)
def signature_preview(payload: JamoSignaturePreviewRequest):
    return create_jamo_signature_preview(payload.customer_name)
