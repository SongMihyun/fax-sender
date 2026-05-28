from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import FileResponse

from backend.models.schemas import SignatureAssetOut, SignatureAssetPatch
from backend.services.signature_asset_service import (
    delete_signature_asset,
    list_signature_assets,
    resolve_signature_asset,
    update_signature_asset,
    upload_signature_asset,
)

router = APIRouter()


@router.get("", response_model=list[SignatureAssetOut])
def assets(category: str | None = Query(default=None), include_inactive: bool = True):
    return list_signature_assets(category=category, include_inactive=include_inactive)


@router.post("", response_model=SignatureAssetOut)
async def upload_asset(
    file: UploadFile = File(...),
    category: str = Form("fallback"),
    label: str | None = Form(default=None),
):
    return await upload_signature_asset(file=file, category=category, label=label)


@router.get("/{asset_id}/image")
def asset_image(asset_id: str):
    return FileResponse(resolve_signature_asset(asset_id))


@router.patch("/{asset_id}", response_model=SignatureAssetOut)
def patch_asset(asset_id: str, payload: SignatureAssetPatch):
    return update_signature_asset(asset_id, active=payload.active, label=payload.label)


@router.delete("/{asset_id}")
def remove_asset(asset_id: str):
    return delete_signature_asset(asset_id)
