# apps/pdf_merge_engine/src/overlay_renderer.py

import random
import tempfile
from pathlib import Path

import fitz
from PIL import Image, ImageEnhance, ImageFilter


def build_position_map(overlay_config: dict) -> dict:
    """
    overlay_config.json의 pages 구조를
    position_id 기준으로 빠르게 찾을 수 있는 dict로 변환한다.

    return 예:
    {
        "p1_check_1": {
            "page_index": 0,
            "x": 690,
            "y": 323,
            "width": 24,
            "height": 24
        }
    }
    """
    position_map = {}

    pages_config = overlay_config.get("pages", {})

    for page_no, page_config in pages_config.items():
        page_index = int(page_no) - 1

        positions = page_config.get("positions", [])

        for position in positions:
            position_id = position.get("id")

            if not position_id:
                continue

            position_map[position_id] = {
                **position,
                "page_index": page_index,
            }

    return position_map


def render_overlays(doc: fitz.Document, overlay_config: dict, form_data: dict, project_root: Path) -> None:
    position_map = build_position_map(overlay_config)
    overlays = form_data.get("overlays", [])

    rendered_count = 0
    skipped_count = 0

    for overlay in overlays:
        position_id = overlay.get("position_id")
        overlay_type = overlay.get("type")

        if not position_id:
            print("[WARN] position_id 없는 overlay 스킵")
            skipped_count += 1
            continue

        position = position_map.get(position_id)

        if not position:
            print(f"[WARN] 좌표 없음: {position_id}")
            skipped_count += 1
            continue

        if overlay_type == "image":
            _render_image(doc, overlay, position, project_root)
            rendered_count += 1

        elif overlay_type == "text":
            _render_text(doc, overlay, position)
            rendered_count += 1

        else:
            print(f"[WARN] 지원하지 않는 overlay type: {overlay_type}")
            skipped_count += 1

    print(f"Overlays rendered: {rendered_count}, skipped: {skipped_count}")


def _render_image(doc: fitz.Document, overlay: dict, position: dict, project_root: Path) -> None:
    image_path_text = overlay.get("image_path")

    if overlay.get("source_type") == "check_asset" and not image_path_text:
        image_path_text = _pick_check_asset(project_root)

    if not image_path_text:
        raise ValueError(f"image overlay에 image_path가 없습니다: {overlay}")

    image_path = Path(image_path_text)

    if not image_path.is_absolute():
        image_path = project_root / image_path

    if not image_path.exists():
        raise FileNotFoundError(f"이미지 파일이 없습니다: {image_path}")

    page = doc[int(position["page_index"])]

    x = float(position["x"])
    y = float(position["y"])
    width = float(position.get("width", overlay.get("width", 24)))
    height = float(position.get("height", overlay.get("height", 24)))
    if overlay.get("source_type") == "check_asset":
        x, y, width, height, image_path = _prepare_check_asset_image(image_path, x, y, width, height, overlay)

    rect = fitz.Rect(x, y, x + width, y + height)

    page.insert_image(
        rect,
        filename=str(image_path),
        keep_proportion=True,
    )


def _pick_check_asset(project_root: Path) -> str:
    repo_root = project_root.parent
    candidates = []
    for directory in [
        repo_root / "shared" / "assets" / "checks" / "generated",
        repo_root / "shared" / "assets" / "checks" / "base",
    ]:
        if directory.exists():
            candidates.extend(sorted(directory.glob("*.png")))

    if not candidates:
        raise FileNotFoundError("사용 가능한 체크 에셋 PNG가 없습니다.")
    return str(random.choice(candidates))


def _prepare_check_asset_image(image_path: Path, x: float, y: float, width: float, height: float, overlay: dict):
    random_range = overlay.get("random_range", {})
    scale_min, scale_max = random_range.get("scale", [0.9, 1.1])
    offset_x_min, offset_x_max = random_range.get("offset_x", [-2, 2])
    offset_y_min, offset_y_max = random_range.get("offset_y", [-2, 2])
    opacity_min, opacity_max = random_range.get("opacity", [0.85, 1.0])
    rotation_min, rotation_max = random_range.get("rotation", [-5, 5])

    scale = random.uniform(float(scale_min), float(scale_max))
    offset_x = random.uniform(float(offset_x_min), float(offset_x_max))
    offset_y = random.uniform(float(offset_y_min), float(offset_y_max))
    opacity = random.uniform(float(opacity_min), float(opacity_max))
    opacity = max(opacity, float(overlay.get("check_ink_opacity", 0)))
    rotation = random.uniform(float(rotation_min), float(rotation_max))

    next_width = width * scale
    next_height = height * scale
    next_x = x + offset_x + (width - next_width) / 2
    next_y = y + offset_y + (height - next_height) / 2

    image = Image.open(image_path).convert("RGBA")
    image = _apply_check_stroke_profile(image, str(overlay.get("check_stroke_profile", "normal")))
    alpha = image.getchannel("A")
    alpha = ImageEnhance.Brightness(alpha).enhance(opacity)
    image.putalpha(alpha)
    image = image.rotate(rotation, expand=True, resample=Image.Resampling.BICUBIC)

    tmp = tempfile.NamedTemporaryFile(prefix="check_asset_", suffix=".png", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()
    image.save(tmp_path)
    return next_x, next_y, next_width, next_height, tmp_path


def _apply_check_stroke_profile(image: Image.Image, profile: str) -> Image.Image:
    if profile == "normal":
        return image
    alpha = image.getchannel("A")
    if profile == "thick":
        alpha = alpha.filter(ImageFilter.MaxFilter(3))
        alpha = ImageEnhance.Brightness(alpha).enhance(1.22)
    elif profile == "extra_thick":
        alpha = alpha.filter(ImageFilter.MaxFilter(5))
        alpha = ImageEnhance.Brightness(alpha).enhance(1.5)
    elif profile == "ultra_dark":
        # Preserve the user's sampled check shape. Only its existing ink is
        # darkened and slightly reinforced for legibility after fax rendering.
        alpha = alpha.filter(ImageFilter.MaxFilter(5))
        alpha = ImageEnhance.Brightness(alpha).enhance(1.8)
        red, green, blue, _ = image.split()
        image = Image.merge(
            "RGBA",
            (
                ImageEnhance.Brightness(red).enhance(0.42),
                ImageEnhance.Brightness(green).enhance(0.42),
                ImageEnhance.Brightness(blue).enhance(0.42),
                alpha,
            ),
        )
        return image
    elif profile == "dark":
        alpha = alpha.filter(ImageFilter.MaxFilter(3))
        alpha = ImageEnhance.Brightness(alpha).enhance(1.35)
    elif profile == "light":
        alpha = ImageEnhance.Brightness(alpha).enhance(0.72)
    image.putalpha(alpha)
    return image


def _render_text(doc: fitz.Document, overlay: dict, position: dict) -> None:
    value = overlay.get("value", "")

    if value is None or value == "":
        print(f"[WARN] text overlay value 없음: {overlay}")
        return

    page = doc[int(position["page_index"])]

    x = float(position["x"])
    y = float(position["y"])

    fontsize = float(position.get("fontsize", overlay.get("fontsize", 10)))

    page.insert_text(
        fitz.Point(x, y),
        str(value),
        fontsize=fontsize,
        fontname="helv",
        color=(0, 0, 0),
    )
