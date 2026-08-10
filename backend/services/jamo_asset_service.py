import json
import random
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from fastapi import HTTPException, UploadFile
from PIL import Image, ImageEnhance

from backend.core.settings import settings
from backend.models.schemas import (
    JamoAssetCreate,
    JamoAssetOut,
    JamoSignaturePreviewResponse,
    JamoSourceUploadResponse,
)

ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png"}
VALID_CATEGORIES = {"initial", "medial", "final"}
INITIALS = ["ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"]
MEDIALS = ["ㅏ", "ㅐ", "ㅑ", "ㅒ", "ㅓ", "ㅔ", "ㅕ", "ㅖ", "ㅗ", "ㅘ", "ㅙ", "ㅚ", "ㅛ", "ㅜ", "ㅝ", "ㅞ", "ㅟ", "ㅠ", "ㅡ", "ㅢ", "ㅣ"]
FINALS = ["", "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ", "ㄻ", "ㄼ", "ㄽ", "ㄾ", "ㄿ", "ㅀ", "ㅁ", "ㅂ", "ㅄ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"]
VERTICAL_MEDIALS = {"ㅏ", "ㅐ", "ㅑ", "ㅒ", "ㅓ", "ㅔ", "ㅕ", "ㅖ", "ㅣ"}
HORIZONTAL_MEDIALS = {"ㅗ", "ㅛ", "ㅜ", "ㅠ", "ㅡ"}
MIXED_MEDIALS = {"ㅘ", "ㅙ", "ㅚ", "ㅝ", "ㅞ", "ㅟ", "ㅢ"}

COMPOSITE_JAMO: dict[str, list[str]] = {
    "ㄲ": ["ㄱ", "ㄱ"],
    "ㄸ": ["ㄷ", "ㄷ"],
    "ㅃ": ["ㅂ", "ㅂ"],
    "ㅆ": ["ㅅ", "ㅅ"],
    "ㅉ": ["ㅈ", "ㅈ"],
    "ㅘ": ["ㅗ", "ㅏ"],
    "ㅙ": ["ㅗ", "ㅐ"],
    "ㅚ": ["ㅗ", "ㅣ"],
    "ㅝ": ["ㅜ", "ㅓ"],
    "ㅞ": ["ㅜ", "ㅔ"],
    "ㅟ": ["ㅜ", "ㅣ"],
    "ㅢ": ["ㅡ", "ㅣ"],
    "ㄳ": ["ㄱ", "ㅅ"],
    "ㄵ": ["ㄴ", "ㅈ"],
    "ㄶ": ["ㄴ", "ㅎ"],
    "ㄺ": ["ㄹ", "ㄱ"],
    "ㄻ": ["ㄹ", "ㅁ"],
    "ㄼ": ["ㄹ", "ㅂ"],
    "ㄽ": ["ㄹ", "ㅅ"],
    "ㄾ": ["ㄹ", "ㅌ"],
    "ㄿ": ["ㄹ", "ㅍ"],
    "ㅀ": ["ㄹ", "ㅎ"],
    "ㅄ": ["ㅂ", "ㅅ"],
}

# Compound vertical vowels are not a horizontal sequence of two glyphs.  The
# source handwriting set intentionally stores simple jamo, so construct these
# by retaining the base vowel and adding the ㅣ stroke in its own narrow lane.
# Unicode escapes keep this mapping independent of a source-file encoding.
MEDIAL_I_COMPOUNDS: dict[str, tuple[str, str]] = {
    "\u3150": ("\u314f", "left"),   # ㅐ = ㅏ + ㅣ
    "\u3152": ("\u3151", "left"),   # ㅒ = ㅑ + ㅣ
    "\u3154": ("\u3153", "left"),   # ㅔ = ㅓ + ㅣ
    "\u3156": ("\u3155", "left"),   # ㅖ = ㅕ + ㅣ
    "\u315a": ("\u3161", "right"),  # ㅢ = ㅡ + ㅣ
}

JAMO_SLUGS = {
    "ㄱ": "giyeok",
    "ㄲ": "ssang_giyeok",
    "ㄳ": "giyeok_siot",
    "ㄴ": "nieun",
    "ㄵ": "nieun_jieut",
    "ㄶ": "nieun_hieut",
    "ㄷ": "digeut",
    "ㄸ": "ssang_digeut",
    "ㄹ": "rieul",
    "ㄺ": "rieul_giyeok",
    "ㄻ": "rieul_mieum",
    "ㄼ": "rieul_bieup",
    "ㄽ": "rieul_siot",
    "ㄾ": "rieul_tieut",
    "ㄿ": "rieul_pieup",
    "ㅀ": "rieul_hieut",
    "ㅁ": "mieum",
    "ㅂ": "bieup",
    "ㅃ": "ssang_bieup",
    "ㅄ": "bieup_siot",
    "ㅅ": "siot",
    "ㅆ": "ssang_siot",
    "ㅇ": "ieung",
    "ㅈ": "jieut",
    "ㅉ": "ssang_jieut",
    "ㅊ": "chieut",
    "ㅋ": "kieuk",
    "ㅌ": "tieut",
    "ㅍ": "pieup",
    "ㅎ": "hieut",
    "ㅏ": "a",
    "ㅐ": "ae",
    "ㅑ": "ya",
    "ㅒ": "yae",
    "ㅓ": "eo",
    "ㅔ": "e",
    "ㅕ": "yeo",
    "ㅖ": "ye",
    "ㅗ": "o",
    "ㅘ": "wa",
    "ㅙ": "wae",
    "ㅚ": "oe",
    "ㅛ": "yo",
    "ㅜ": "u",
    "ㅝ": "wo",
    "ㅞ": "we",
    "ㅟ": "wi",
    "ㅠ": "yu",
    "ㅡ": "eu",
    "ㅢ": "ui",
    "ㅣ": "i",
}

SIMILAR_JAMO: dict[str, list[str]] = {
    "ㄲ": ["ㄱ"],
    "ㄸ": ["ㄷ"],
    "ㅃ": ["ㅂ"],
    "ㅆ": ["ㅅ"],
    "ㅉ": ["ㅈ"],
    "ㅋ": ["ㄱ"],
    "ㅌ": ["ㄷ"],
    "ㅍ": ["ㅂ"],
    "ㅊ": ["ㅈ"],
    "ㅎ": ["ㅇ"],
    "ㄳ": ["ㄱ", "ㅅ"],
    "ㄵ": ["ㄴ", "ㅈ"],
    "ㄶ": ["ㄴ", "ㅎ", "ㅇ"],
    "ㄺ": ["ㄹ", "ㄱ"],
    "ㄻ": ["ㄹ", "ㅁ"],
    "ㄼ": ["ㄹ", "ㅂ"],
    "ㄽ": ["ㄹ", "ㅅ"],
    "ㄾ": ["ㄹ", "ㅌ", "ㄷ"],
    "ㄿ": ["ㄹ", "ㅍ", "ㅂ"],
    "ㅀ": ["ㄹ", "ㅎ", "ㅇ"],
    "ㅄ": ["ㅂ", "ㅅ"],
    "ㅐ": ["ㅏ", "ㅣ"],
    "ㅒ": ["ㅑ", "ㅣ", "ㅐ"],
    "ㅔ": ["ㅓ", "ㅣ"],
    "ㅖ": ["ㅕ", "ㅣ", "ㅔ"],
    "ㅑ": ["ㅏ"],
    "ㅕ": ["ㅓ"],
    "ㅛ": ["ㅗ"],
    "ㅠ": ["ㅜ"],
    "ㅘ": ["ㅗ", "ㅏ"],
    "ㅙ": ["ㅗ", "ㅐ", "ㅏ", "ㅣ"],
    "ㅚ": ["ㅗ", "ㅣ"],
    "ㅝ": ["ㅜ", "ㅓ"],
    "ㅞ": ["ㅜ", "ㅔ", "ㅓ", "ㅣ"],
    "ㅟ": ["ㅜ", "ㅣ"],
    "ㅢ": ["ㅡ", "ㅣ"],
    "ㅡ": ["ㅜ", "ㅗ"],
    "ㅣ": ["ㅏ"],
}


def _relative_path(path: Path) -> str:
    try:
        return path.relative_to(settings.root_dir).as_posix()
    except ValueError:
        return path.as_posix()


def _source_path(source_id: str) -> Path:
    safe_id = Path(source_id).stem
    for suffix in ALLOWED_SUFFIXES:
        candidate = settings.jamo_sources_dir / f"{safe_id}{suffix}"
        if candidate.exists():
            return candidate
    raise HTTPException(status_code=404, detail="자모 원본 이미지를 찾을 수 없습니다.")


def _asset_id(category: str, jamo: str, filename: str) -> str:
    return f"{category}__{jamo}__{Path(filename).stem}"


def _parse_asset_id(asset_id: str) -> tuple[str, str, str]:
    parts = asset_id.split("__", 2)
    if len(parts) != 3:
        raise HTTPException(status_code=400, detail="잘못된 자모 에셋 ID입니다.")
    return parts[0], parts[1], Path(parts[2]).stem


def _meta_path(path: Path) -> Path:
    return path.with_suffix(".json")


def _read_meta(path: Path) -> dict[str, Any]:
    meta_path = _meta_path(path)
    if not meta_path.exists():
        return {"active": True}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"active": True}


def _write_meta(path: Path, data: dict[str, Any]) -> None:
    _meta_path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _validate_category_jamo(category: str, jamo: str) -> None:
    if category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail="category는 initial, medial, final 중 하나여야 합니다.")
    valid_map = {"initial": INITIALS, "medial": MEDIALS, "final": FINALS[1:]}
    if jamo not in valid_map[category]:
        raise HTTPException(status_code=400, detail="해당 category에 사용할 수 없는 자모입니다.")


def resolve_jamo_asset(asset_id: str) -> Path:
    category, jamo, stem = _parse_asset_id(asset_id)
    path = settings.jamo_assets_dir / category / jamo / f"{stem}.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="자모 에셋을 찾을 수 없습니다.")
    return path


def _to_asset(path: Path) -> JamoAssetOut:
    category = path.parent.parent.name
    jamo = path.parent.name
    stat = path.stat()
    return JamoAssetOut(
        id=_asset_id(category, jamo, path.name),
        category=category,
        jamo=jamo,
        filename=path.name,
        path=_relative_path(path),
        image_url=f"/api/admin/jamo/assets/{_asset_id(category, jamo, path.name)}/image",
        active=bool(_read_meta(path).get("active", True)),
        size_bytes=stat.st_size,
        created_at=datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
    )


async def upload_jamo_source(file: UploadFile) -> JamoSourceUploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="이미지 파일이 필요합니다.")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail="jpg, jpeg, png 파일만 업로드할 수 있습니다.")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    settings.jamo_sources_dir.mkdir(parents=True, exist_ok=True)
    source_id = f"jamo_source_{timestamp}"
    source_path = settings.jamo_sources_dir / f"{source_id}{suffix}"
    with source_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return JamoSourceUploadResponse(source_id=source_id, filename=source_path.name, image_url=f"/api/admin/jamo/sources/{source_id}/image")


def resolve_jamo_source(source_id: str) -> Path:
    return _source_path(source_id)


def list_jamo_assets(category: str | None = None, jamo: str | None = None, include_inactive: bool = True) -> list[JamoAssetOut]:
    root = settings.jamo_assets_dir
    root.mkdir(parents=True, exist_ok=True)
    pattern_root = root / category if category else root
    paths = sorted(pattern_root.glob("**/*.png")) if pattern_root.exists() else []
    assets = [_to_asset(path) for path in paths if not jamo or path.parent.name == jamo]
    if not include_inactive:
        assets = [asset for asset in assets if asset.active]
    return sorted(assets, key=lambda asset: asset.created_at or "", reverse=True)


def save_jamo_asset(payload: JamoAssetCreate) -> list[JamoAssetOut]:
    _validate_category_jamo(payload.category, payload.jamo)
    source_path = _source_path(payload.source_id)
    image = cv2.imread(str(source_path), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=400, detail="원본 이미지를 읽을 수 없습니다.")

    h, w = image.shape[:2]
    x = max(0, int(payload.crop.x))
    y = max(0, int(payload.crop.y))
    width = max(1, int(payload.crop.width))
    height = max(1, int(payload.crop.height))
    if x >= w or y >= h:
        raise HTTPException(status_code=400, detail="crop 좌표가 이미지 영역 밖입니다.")
    x2 = min(w, x + width)
    y2 = min(h, y + height)

    boxes = _detect_jamo_boxes(image[y:y2, x:x2])
    if not boxes:
        boxes = [(0, 0, x2 - x, y2 - y)]

    directory = settings.jamo_assets_dir / payload.category / payload.jamo
    directory.mkdir(parents=True, exist_ok=True)
    slug = JAMO_SLUGS.get(payload.jamo, re.sub(r"\W+", "", payload.jamo) or "jamo")
    count = len(list(directory.glob("*.png"))) + 1
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved: list[JamoAssetOut] = []
    for index, (box_x, box_y, box_w, box_h) in enumerate(boxes, start=count):
        output_path = directory / f"{payload.category}_{slug}_{timestamp}_{index:03d}.png"
        _save_transparent_crop(image, x + box_x, y + box_y, x + box_x + box_w, y + box_y + box_h, output_path)
        _write_meta(output_path, {"active": True, "source_id": payload.source_id, "jamo": payload.jamo, "category": payload.category})
        saved.append(_to_asset(output_path))
    return saved


def _detect_jamo_boxes(crop: np.ndarray) -> list[tuple[int, int, int, int]]:
    if crop.size == 0:
        return []
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    mask = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 10)
    kernel = np.ones((2, 2), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

    components, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    crop_h, crop_w = mask.shape
    boxes: list[tuple[int, int, int, int]] = []
    for index in range(1, components):
        x = int(stats[index, cv2.CC_STAT_LEFT])
        y = int(stats[index, cv2.CC_STAT_TOP])
        w = int(stats[index, cv2.CC_STAT_WIDTH])
        h = int(stats[index, cv2.CC_STAT_HEIGHT])
        area = int(stats[index, cv2.CC_STAT_AREA])
        if area < 10 or w < 5 or h < 5:
            continue
        if w > crop_w * 0.85 and h > crop_h * 0.85:
            continue
        boxes.append((x, y, w, h))
    boxes = _merge_nearby_jamo_boxes(boxes)
    return sorted(boxes, key=lambda box: (box[1], box[0]))


def _merge_nearby_jamo_boxes(boxes: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
    merged: list[tuple[int, int, int, int]] = []
    for box in sorted(boxes, key=lambda item: (item[1], item[0])):
        x, y, w, h = box
        did_merge = False
        for index, existing in enumerate(merged):
            ex, ey, ew, eh = existing
            horizontal_overlap = x <= ex + ew + 8 and ex <= x + w + 8
            vertical_overlap = y <= ey + eh + 8 and ey <= y + h + 8
            if horizontal_overlap and vertical_overlap:
                nx = min(x, ex)
                ny = min(y, ey)
                nr = max(x + w, ex + ew)
                nb = max(y + h, ey + eh)
                merged[index] = (nx, ny, nr - nx, nb - ny)
                did_merge = True
                break
        if not did_merge:
            merged.append(box)
    return merged


def _save_transparent_crop(image: np.ndarray, x1: int, y1: int, x2: int, y2: int, output_path: Path) -> None:
    padding = 8
    h, w = image.shape[:2]
    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(w, x2 + padding)
    y2 = min(h, y2 + padding)
    crop = image[y1:y2, x1:x2]
    if crop.size == 0:
        raise HTTPException(status_code=400, detail="선택 영역이 비어 있습니다.")
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    mask = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 10)
    # 자모는 체크보다 선이 얇아서 open 연산을 걸면 실제 획이 사라질 수 있다.
    # 작은 점 잡음은 연결 성분 면적으로만 제거하고, 획 자체는 최대한 보존한다.
    components, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    cleaned = np.zeros_like(mask)
    for index in range(1, components):
        area = stats[index, cv2.CC_STAT_AREA]
        if area >= 3:
            cleaned[labels == index] = 255
    mask = cleaned
    if cv2.countNonZero(mask) < 8:
        raise HTTPException(status_code=400, detail="선택 영역에서 글씨 선을 찾지 못했습니다.")
    rgba = cv2.cvtColor(crop, cv2.COLOR_BGR2BGRA)
    rgba[:, :, 3] = np.where(mask > 0, 255, 0).astype(np.uint8)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    success, encoded = cv2.imencode(".png", rgba)
    if not success:
        raise HTTPException(status_code=500, detail="자모 PNG 인코딩에 실패했습니다.")
    output_path.write_bytes(encoded.tobytes())
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise HTTPException(status_code=500, detail="자모 PNG 저장에 실패했습니다.")


def delete_jamo_asset(asset_id: str) -> dict[str, str]:
    path = resolve_jamo_asset(asset_id)
    path.unlink()
    meta = _meta_path(path)
    if meta.exists():
        meta.unlink()
    return {"status": "deleted"}


def update_jamo_asset(asset_id: str, active: bool | None) -> JamoAssetOut:
    path = resolve_jamo_asset(asset_id)
    meta = _read_meta(path)
    if active is not None:
        meta["active"] = active
    _write_meta(path, meta)
    return _to_asset(path)


def decompose_hangul_syllable(char: str) -> tuple[str, str, str]:
    code = ord(char) - 0xAC00
    if code < 0 or code > 11171:
        return "", "", ""
    initial = INITIALS[code // 588]
    medial = MEDIALS[(code % 588) // 28]
    final = FINALS[code % 28]
    return initial, medial, final


def decompose_korean_name(name: str) -> list[tuple[str, str, str]]:
    return [decompose_hangul_syllable(char) for char in name if "\uac00" <= char <= "\ud7a3"]


def _pick_asset(category: str, jamo: str, rng: random.Random) -> Path | None:
    assets = list_jamo_assets(category, jamo, include_inactive=False)
    if not assets:
        return None
    scored: list[tuple[float, Path]] = []
    for asset in assets:
        path = resolve_jamo_asset(asset.id)
        score = _jamo_asset_score(path, category)
        if score > 0:
            scored.append((score, path))
    if scored:
        scored.sort(key=lambda item: item[0], reverse=True)
        top = scored[: min(4, len(scored))]
        return rng.choice(top)[1]
    return None


def _image_has_visible_pixels(path: Path) -> bool:
    try:
        image = Image.open(path).convert("RGBA")
        return image.getchannel("A").getbbox() is not None
    except Exception:
        return False


def _jamo_asset_score(path: Path, category: str) -> float:
    try:
        image = Image.open(path).convert("RGBA")
        bbox = image.getbbox()
        if bbox is None:
            return 0
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        if width < 8 or height < 8:
            return 0
        alpha_count = sum(1 for value in image.getchannel("A").crop(bbox).getdata() if value)
        density = alpha_count / max(1, width * height)
        aspect = width / max(1, height)
        if density < 0.015 or density > 0.55:
            return 0
        target_aspect = 0.28 if category == "medial" else 0.85
        if category == "medial" and aspect > 2.2:
            target_aspect = 2.8
        aspect_penalty = abs(aspect - target_aspect)
        size_score = min(width * height / 9000, 1.0)
        return max(0.001, size_score + density * 2 - aspect_penalty * 0.18)
    except Exception:
        return 0


def _compose_medial_i_compound(base: Image.Image, i_stroke: Image.Image, side: str) -> Image.Image:
    """Combine a base vowel with ㅣ without turning it into a second syllable."""
    base = _fit_image(base.copy(), 48, 74)
    i_stroke = _fit_image(i_stroke.copy(), 14, 74)
    gap = max(1, base.width // 12)
    width = base.width + i_stroke.width + gap
    height = max(base.height, i_stroke.height)
    canvas = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    base_y = max(0, (height - base.height) // 2)
    i_y = max(0, (height - i_stroke.height) // 2)
    if side == "left":
        canvas.alpha_composite(i_stroke, (0, i_y))
        canvas.alpha_composite(base, (i_stroke.width + gap, base_y))
    else:
        canvas.alpha_composite(base, (0, base_y))
        canvas.alpha_composite(i_stroke, (base.width + gap, i_y))
    return canvas.crop(canvas.getbbox() or (0, 0, canvas.width, canvas.height))


def _load_jamo_image(category: str, jamo: str, rng: random.Random, seen: set[tuple[str, str]] | None = None) -> tuple[Image.Image | None, list[str], list[str]]:
    seen = seen or set()
    key = (category, jamo)
    if key in seen:
        return None, [], [f"{category}:{jamo}"]
    seen.add(key)

    path = _pick_asset(category, jamo, rng)
    if path is not None:
        return Image.open(path).convert("RGBA"), [f"{category}:{jamo}"], []

    compound = MEDIAL_I_COMPOUNDS.get(jamo) if category == "medial" else None
    if compound:
        base_jamo, side = compound
        base, base_used, base_missing = _load_jamo_image("medial", base_jamo, rng, seen.copy())
        i_stroke, i_used, i_missing = _load_jamo_image("medial", "\u3163", rng, seen.copy())
        if base is not None and i_stroke is not None and not base_missing and not i_missing:
            return _compose_medial_i_compound(base, i_stroke, side), base_used + i_used + [f"auto:medial:{jamo}"], []

    component_jamos = COMPOSITE_JAMO.get(jamo)
    if not component_jamos:
        fallback_category = "initial" if category == "final" and jamo in INITIALS else category
        if fallback_category != category:
            path = _pick_asset(fallback_category, jamo, rng)
            if path is not None:
                return Image.open(path).convert("RGBA"), [f"{fallback_category}:{jamo}"], []
        similar_image, similar_used = _load_similar_jamo_image(category, jamo, rng, seen)
        if similar_image is not None:
            return similar_image, similar_used + [f"substitute:{category}:{jamo}"], []
        placeholder = _placeholder_jamo_image(category, jamo, rng)
        return placeholder, [f"placeholder:{category}:{jamo}"], []

    component_images: list[Image.Image] = []
    used: list[str] = []
    missing: list[str] = []
    for component in component_jamos:
        component_category = category
        if category == "final" and component in INITIALS:
            component_category = "final"
        image, component_used, component_missing = _load_jamo_image(component_category, component, rng, seen.copy())
        if image is None and component_category == "final":
            image, component_used, component_missing = _load_jamo_image("initial", component, rng, seen.copy())
        if image is None:
            missing.extend(component_missing or [f"{component_category}:{component}"])
            continue
        component_images.append(image)
        used.extend(component_used)
    if missing or len(component_images) != len(component_jamos):
        similar_image, similar_used = _load_similar_jamo_image(category, jamo, rng, seen)
        if similar_image is not None:
            return similar_image, used + similar_used + [f"substitute:{category}:{jamo}"], []
        return _placeholder_jamo_image(category, jamo, rng), used + [f"placeholder:{category}:{jamo}"], []
    return _compose_composite_jamo(category, component_images, rng), used + [f"auto:{category}:{jamo}"], []


def _load_similar_jamo_image(category: str, jamo: str, rng: random.Random, seen: set[tuple[str, str]] | None) -> tuple[Image.Image | None, list[str]]:
    for candidate in SIMILAR_JAMO.get(jamo, []):
        candidate_category = category
        if category == "final" and candidate in INITIALS:
            candidate_category = "final"
        image, used, missing = _load_jamo_image(candidate_category, candidate, rng, (seen or set()).copy())
        if image is None and candidate_category == "final":
            image, used, missing = _load_jamo_image("initial", candidate, rng, (seen or set()).copy())
        if image is not None and not missing:
            return image, used
    return None, []


def _placeholder_jamo_image(category: str, jamo: str, rng: random.Random) -> Image.Image:
    size = (42, 64) if category != "medial" else (38, 74)
    image = Image.new("RGBA", size, (255, 255, 255, 0))
    canvas = np.zeros((size[1], size[0], 4), dtype=np.uint8)
    color = (0, 0, 0, 210)
    if category == "medial":
        if jamo in HORIZONTAL_MEDIALS:
            cv2.line(canvas, (5, size[1] // 2), (size[0] - 5, size[1] // 2 + rng.randint(-2, 2)), color, 2)
        else:
            cv2.line(canvas, (size[0] // 2, 6), (size[0] // 2 + rng.randint(-2, 2), size[1] - 6), color, 2)
    else:
        cv2.line(canvas, (6, 8), (size[0] - 8, 10 + rng.randint(-2, 2)), color, 2)
        cv2.line(canvas, (8, 10), (10 + rng.randint(-2, 2), size[1] - 8), color, 2)
    return Image.fromarray(canvas, "RGBA")


def _compose_composite_jamo(category: str, images: list[Image.Image], rng: random.Random) -> Image.Image:
    fitted = []
    for image in images:
        target_w = 42 if category != "medial" else 34
        target_h = 58 if category != "medial" else 70
        fitted.append(_fit_image(image.copy(), target_w, target_h))
    width = sum(image.width for image in fitted) + max(0, len(fitted) - 1) * 2
    height = max(image.height for image in fitted)
    canvas = Image.new("RGBA", (max(1, width), max(1, height + 4)), (255, 255, 255, 0))
    cursor = 0
    for image in fitted:
        canvas.alpha_composite(image, (cursor, max(0, (canvas.height - image.height) // 2 + rng.randint(-1, 1))))
        cursor += image.width + 2
    return canvas.crop(canvas.getbbox() or (0, 0, canvas.width, canvas.height))


def create_jamo_signature_image(customer_name: str, profile: dict[str, Any] | None = None) -> tuple[Path, list[str], list[str]]:
    profile = profile or {}
    name = re.sub(r"[^가-힣]", "", customer_name or "")
    if not name:
        raise HTTPException(status_code=400, detail="자모 조합 서명을 만들 한글 customer_name이 필요합니다.")
    rng = random.Random(int(profile.get("style_seed", random.randint(100000, 999999))))
    syllables = decompose_korean_name(name)
    used: list[str] = []
    missing: list[str] = []
    syllable_images: list[Image.Image] = []

    for initial, medial, final in syllables:
        parts = [("initial", initial), ("medial", medial)]
        if final:
            parts.append(("final", final))
        part_images: dict[str, Image.Image] = {}
        for category, jamo in parts:
            image, component_used, component_missing = _load_jamo_image(category, jamo, rng)
            used.extend(component_used or [f"{category}:{jamo}"])
            if image is None:
                missing.extend(component_missing or [f"{category}:{jamo}"])
                continue
            part_images[category] = image
        if any(category not in part_images for category, _ in parts):
            fallback_parts = {
                "initial": part_images.get("initial") or _placeholder_jamo_image("initial", initial, rng),
                "medial": part_images.get("medial") or _placeholder_jamo_image("medial", medial, rng),
            }
            if final:
                fallback_parts["final"] = part_images.get("final") or _placeholder_jamo_image("final", final, rng)
            syllable_images.append(_compose_syllable(fallback_parts, medial, bool(final), rng))
            continue
        syllable_images.append(_compose_syllable(part_images, medial, bool(final), rng))

    if not syllable_images:
        return _fallback_empty_signature(name), used, sorted(set(missing))

    width = sum(image.width for image in syllable_images) + max(0, len(syllable_images) - 1) * 6
    height = max(image.height for image in syllable_images)
    signature = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    cursor = 0
    for image in syllable_images:
        signature.alpha_composite(image, (cursor, max(0, (height - image.height) // 2 + rng.randint(-2, 2))))
        cursor += image.width + 6
    opacity = int(255 * float(profile.get("base_opacity", 0.94)))
    if opacity < 255:
        alpha = signature.getchannel("A").point(lambda value: int(value * opacity / 255))
        signature.putalpha(alpha)
    rotation_min, rotation_max = profile.get("base_rotation_range", [-3, 3])
    signature = signature.rotate(rng.uniform(rotation_min, rotation_max), expand=True, resample=Image.Resampling.BICUBIC)
    signature_dir = settings.tmp_dir if profile.get("persist_preview") is not True else settings.generated_dir
    signature_dir.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(prefix="jamo_signature_", suffix=".png", delete=False, dir=signature_dir)
    tmp_path = Path(tmp.name)
    tmp.close()
    signature.save(tmp_path)
    return tmp_path, used, sorted(set(missing))


def _compose_syllable(parts: dict[str, Image.Image], medial: str, has_final: bool, rng: random.Random) -> Image.Image:
    canvas = Image.new("RGBA", (116, 124), (255, 255, 255, 0))
    boxes = _syllable_boxes(medial, has_final)
    for category, image in parts.items():
        x1, y1, x2, y2 = boxes[category]
        target_w = x2 - x1
        target_h = y2 - y1
        scale = rng.uniform(0.9, 1.08)
        image = _fit_image(image, int(target_w * scale), int(target_h * scale))
        image = image.rotate(rng.uniform(-4, 4), expand=True, resample=Image.Resampling.BICUBIC)
        x = x1 + (target_w - image.width) // 2 + rng.randint(-3, 3)
        y = y1 + (target_h - image.height) // 2 + rng.randint(-3, 3)
        canvas.alpha_composite(image, (x, y))
    return canvas.crop(canvas.getbbox() or (0, 0, 116, 124))


def _syllable_boxes(medial: str, has_final: bool) -> dict[str, tuple[int, int, int, int]]:
    if has_final and medial in HORIZONTAL_MEDIALS:
        return {
            "initial": (18, 4, 98, 50),
            "medial": (18, 42, 98, 72),
            "final": (20, 70, 96, 118),
        }
    if has_final and medial in MIXED_MEDIALS:
        return {
            "initial": (6, 6, 52, 64),
            "medial": (42, 10, 108, 78),
            "final": (20, 74, 98, 118),
        }
    if has_final:
        return {
            "initial": (4, 8, 50, 62),
            "medial": (42, 10, 98, 68),
            "final": (16, 62, 92, 112),
        }
    if medial in HORIZONTAL_MEDIALS:
        return {
            "initial": (18, 6, 98, 68),
            "medial": (18, 62, 98, 118),
            "final": (20, 78, 96, 118),
        }
    if medial in MIXED_MEDIALS:
        return {
            "initial": (6, 12, 54, 92),
            "medial": (44, 12, 110, 116),
            "final": (20, 78, 98, 118),
        }
    return {
        "initial": (8, 14, 58, 108),
        "medial": (52, 14, 112, 112),
        "final": (20, 78, 98, 118),
    }


def _fit_image(image: Image.Image, max_width: int, max_height: int) -> Image.Image:
    bbox = image.getbbox()
    if bbox:
        image = image.crop(bbox)
    image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
    return image


def _fallback_empty_signature(name: str) -> Path:
    rng = random.Random()
    syllable_images: list[Image.Image] = []
    for initial, medial, final in decompose_korean_name(name):
        parts = {
            "initial": _placeholder_jamo_image("initial", initial, rng),
            "medial": _placeholder_jamo_image("medial", medial, rng),
        }
        if final:
            parts["final"] = _placeholder_jamo_image("final", final, rng)
        syllable_images.append(_compose_syllable(parts, medial, bool(final), rng))

    if syllable_images:
        width = sum(image.width for image in syllable_images) + max(0, len(syllable_images) - 1) * 6
        height = max(image.height for image in syllable_images)
        image = Image.new("RGBA", (width, height), (255, 255, 255, 0))
        cursor = 0
        for syllable in syllable_images:
            image.alpha_composite(syllable, (cursor, max(0, (height - syllable.height) // 2)))
            cursor += syllable.width + 6
    else:
        image = Image.new("RGBA", (180, 70), (255, 255, 255, 0))
        canvas = np.zeros((70, 180, 4), dtype=np.uint8)
        cv2.line(canvas, (12, 36), (168, 28), (0, 0, 0, 220), 2)
        cv2.line(canvas, (32, 48), (132, 44), (0, 0, 0, 180), 1)
        image = Image.fromarray(canvas, "RGBA")
    settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(prefix="jamo_signature_missing_", suffix=".png", delete=False, dir=settings.tmp_dir)
    tmp_path = Path(tmp.name)
    tmp.close()
    image.save(tmp_path)
    return tmp_path


def create_jamo_signature_preview(customer_name: str) -> JamoSignaturePreviewResponse:
    output_path, used, missing = create_jamo_signature_image(customer_name, {"style_seed": random.randint(100000, 999999), "persist_preview": True})
    return JamoSignaturePreviewResponse(
        success=len(missing) == 0,
        preview_url=f"/storage/generated/{output_path.name}",
        used_jamo=used,
        missing_jamo=missing,
        output_path=str(output_path),
    )
