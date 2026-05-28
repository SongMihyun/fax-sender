import json
import random
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile

from backend.core.settings import settings
from backend.models.schemas import SignatureAssetOut


ALLOWED_SUFFIXES = {".png", ".jpg", ".jpeg"}
DEFAULT_CATEGORY = "fallback"


def _safe_slug(value: str, default: str = DEFAULT_CATEGORY) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", (value or "").strip()).strip("_").lower()
    return (slug or default)[:60]


def _relative_path(path: Path) -> str:
    try:
        return path.relative_to(settings.root_dir).as_posix()
    except ValueError:
        return path.as_posix()


def _asset_id(path: Path) -> str:
    return f"{path.parent.name}__{path.stem}"


def _parse_asset_id(asset_id: str) -> tuple[str, str]:
    parts = asset_id.split("__", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="invalid signature asset id")
    return _safe_slug(parts[0]), Path(parts[1]).stem


def _meta_path(path: Path) -> Path:
    return path.with_suffix(".json")


def _read_meta(path: Path) -> dict[str, Any]:
    meta_path = _meta_path(path)
    if not meta_path.exists():
        return {"active": True, "label": path.stem, "category": path.parent.name}
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"active": True, "label": path.stem, "category": path.parent.name}
    return data if isinstance(data, dict) else {"active": True, "label": path.stem, "category": path.parent.name}


def _write_meta(path: Path, data: dict[str, Any]) -> None:
    _meta_path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _to_asset(path: Path) -> SignatureAssetOut:
    meta = _read_meta(path)
    stat = path.stat()
    asset_id = _asset_id(path)
    return SignatureAssetOut(
        id=asset_id,
        category=str(meta.get("category") or path.parent.name),
        label=str(meta.get("label") or path.stem),
        filename=path.name,
        path=_relative_path(path),
        image_url=f"/api/admin/signatures/{asset_id}/image",
        active=bool(meta.get("active", True)),
        size_bytes=stat.st_size,
        created_at=datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
    )


def resolve_signature_asset(asset_id: str) -> Path:
    category, stem = _parse_asset_id(asset_id)
    directory = settings.signatures_dir / category
    for suffix in ALLOWED_SUFFIXES:
        candidate = directory / f"{stem}{suffix}"
        if candidate.exists():
            return candidate
    raise HTTPException(status_code=404, detail="signature asset not found")


def list_signature_assets(category: str | None = None, include_inactive: bool = True) -> list[SignatureAssetOut]:
    root = settings.signatures_dir
    root.mkdir(parents=True, exist_ok=True)
    search_root = root / _safe_slug(category) if category else root
    paths = sorted(search_root.glob("**/*")) if search_root.exists() else []
    assets = [_to_asset(path) for path in paths if path.is_file() and path.suffix.lower() in ALLOWED_SUFFIXES]
    if not include_inactive:
        assets = [asset for asset in assets if asset.active]
    return sorted(assets, key=lambda asset: asset.created_at or "", reverse=True)


async def upload_signature_asset(file: UploadFile, category: str = DEFAULT_CATEGORY, label: str | None = None) -> SignatureAssetOut:
    if not file.filename:
        raise HTTPException(status_code=400, detail="signature image is required")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail="png, jpg, jpeg files are supported")

    safe_category = _safe_slug(category)
    safe_label = (label or Path(file.filename).stem or safe_category).strip()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    directory = settings.signatures_dir / safe_category
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"signature_{safe_category}_{timestamp}_{random.randint(1000, 9999)}{suffix}"
    output_path = directory / filename
    with output_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    _write_meta(output_path, {"active": True, "category": safe_category, "label": safe_label})
    return _to_asset(output_path)


def update_signature_asset(asset_id: str, active: bool | None = None, label: str | None = None) -> SignatureAssetOut:
    path = resolve_signature_asset(asset_id)
    meta = _read_meta(path)
    if active is not None:
        meta["active"] = active
    if label is not None:
        meta["label"] = label.strip() or path.stem
    meta["category"] = path.parent.name
    _write_meta(path, meta)
    return _to_asset(path)


def delete_signature_asset(asset_id: str) -> dict[str, str]:
    path = resolve_signature_asset(asset_id)
    path.unlink()
    meta_path = _meta_path(path)
    if meta_path.exists():
        meta_path.unlink()
    return {"status": "deleted"}


def pick_fallback_signature(category: str | None = None) -> Path | None:
    preferred: list[SignatureAssetOut] = []
    if category:
        preferred = list_signature_assets(category=category, include_inactive=False)
    fallback = list_signature_assets(category=DEFAULT_CATEGORY, include_inactive=False)
    general = list_signature_assets(include_inactive=False)
    candidates = preferred or fallback or general
    if not candidates:
        return None
    return resolve_signature_asset(random.choice(candidates).id)
