import shutil
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from fastapi import HTTPException, UploadFile

from backend.core.settings import settings
from backend.models.schemas import CheckAssetOut, CheckAssetUploadResponse

ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png"}


def _asset_dirs() -> list[tuple[str, Path]]:
    return [("base", settings.check_assets_base_dir), ("generated", settings.check_assets_generated_dir)]


def _asset_id(path: Path) -> str:
    return path.stem


def _relative_path(path: Path) -> str:
    try:
        return path.relative_to(settings.root_dir).as_posix()
    except ValueError:
        return path.as_posix()


def _to_asset(path: Path, source: str) -> CheckAssetOut:
    stat = path.stat()
    return CheckAssetOut(
        id=_asset_id(path),
        filename=path.name,
        path=_relative_path(path),
        image_url=f"/api/check-assets/{_asset_id(path)}/image",
        source=source,
        size_bytes=stat.st_size,
        created_at=datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
    )


def list_check_assets() -> list[CheckAssetOut]:
    assets: list[CheckAssetOut] = []
    for source, directory in _asset_dirs():
        directory.mkdir(parents=True, exist_ok=True)
        assets.extend(_to_asset(path, source) for path in sorted(directory.glob("*.png")))
    return sorted(assets, key=lambda asset: asset.created_at or "", reverse=True)


def resolve_check_asset(asset_id: str) -> Path:
    safe_id = Path(asset_id).stem
    for _, directory in _asset_dirs():
        candidate = directory / f"{safe_id}.png"
        if candidate.exists():
            return candidate
    raise HTTPException(status_code=404, detail="체크 에셋을 찾을 수 없습니다.")


def delete_check_asset(asset_id: str) -> dict[str, str]:
    path = resolve_check_asset(asset_id)
    path.unlink()
    return {"status": "deleted"}


async def upload_and_extract_check_assets(file: UploadFile) -> CheckAssetUploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="이미지 파일이 필요합니다.")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail="jpg, jpeg, png 파일만 업로드할 수 있습니다.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    settings.check_sources_dir.mkdir(parents=True, exist_ok=True)
    settings.check_assets_generated_dir.mkdir(parents=True, exist_ok=True)

    source_id = f"source_{timestamp}"
    source_path = settings.check_sources_dir / f"{source_id}{suffix}"
    with source_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    created_paths = _extract_checks(source_path, timestamp)
    return CheckAssetUploadResponse(
        source_id=source_id,
        created_count=len(created_paths),
        assets=[_to_asset(path, "generated") for path in created_paths],
    )


def _extract_checks(source_path: Path, timestamp: str) -> list[Path]:
    image = cv2.imread(str(source_path), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=400, detail="이미지를 읽을 수 없습니다.")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    thresh = cv2.adaptiveThreshold(
        blur,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        31,
        10,
    )
    kernel = np.ones((2, 2), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=1)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_h, image_w = thresh.shape
    boxes: list[tuple[int, int, int, int]] = []

    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = cv2.contourArea(contour)
        if w < 20 or h < 20 or area < 80:
            continue
        if w > image_w * 0.6 or h > image_h * 0.6:
            continue
        boxes.append((x, y, w, h))

    boxes = _merge_nearby_boxes(boxes)
    saved: list[Path] = []
    for index, (x, y, w, h) in enumerate(sorted(boxes, key=lambda box: (box[1], box[0])), start=1):
        output_path = settings.check_assets_generated_dir / f"check_{timestamp}_{index:03d}.png"
        if _save_transparent_crop(image, thresh, x, y, w, h, output_path):
            saved.append(output_path)
    return saved


def _merge_nearby_boxes(boxes: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
    merged: list[tuple[int, int, int, int]] = []
    for box in boxes:
        x, y, w, h = box
        did_merge = False
        for idx, existing in enumerate(merged):
            ex, ey, ew, eh = existing
            if x <= ex + ew + 8 and ex <= x + w + 8 and y <= ey + eh + 8 and ey <= y + h + 8:
                nx = min(x, ex)
                ny = min(y, ey)
                nr = max(x + w, ex + ew)
                nb = max(y + h, ey + eh)
                merged[idx] = (nx, ny, nr - nx, nb - ny)
                did_merge = True
                break
        if not did_merge:
            merged.append(box)
    return merged


def _save_transparent_crop(image: np.ndarray, mask: np.ndarray, x: int, y: int, w: int, h: int, output_path: Path) -> bool:
    padding = 16
    image_h, image_w = mask.shape
    x1 = max(0, x - padding)
    y1 = max(0, y - padding)
    x2 = min(image_w, x + w + padding)
    y2 = min(image_h, y + h + padding)

    crop = image[y1:y2, x1:x2]
    crop_mask = mask[y1:y2, x1:x2]
    if crop.size == 0 or cv2.countNonZero(crop_mask) < 60:
        return False

    rgba = cv2.cvtColor(crop, cv2.COLOR_BGR2BGRA)
    alpha = np.where(crop_mask > 0, 255, 0).astype(np.uint8)
    rgba[:, :, 3] = alpha
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return bool(cv2.imwrite(str(output_path), rgba))
