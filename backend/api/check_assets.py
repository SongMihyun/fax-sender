from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse

from backend.models.schemas import CheckAssetOut, CheckAssetUploadResponse
from backend.services.check_asset_service import (
    delete_check_asset,
    list_check_assets,
    resolve_check_asset,
    upload_and_extract_check_assets,
)

router = APIRouter()


@router.post("/sources", response_model=CheckAssetUploadResponse)
async def upload_check_source(file: UploadFile = File(...)):
    return await upload_and_extract_check_assets(file)


@router.get("", response_model=list[CheckAssetOut])
def check_assets():
    return list_check_assets()


@router.get("/{asset_id}/image")
def check_asset_image(asset_id: str):
    return FileResponse(resolve_check_asset(asset_id), media_type="image/png")


@router.delete("/{asset_id}")
def remove_check_asset(asset_id: str):
    return delete_check_asset(asset_id)
