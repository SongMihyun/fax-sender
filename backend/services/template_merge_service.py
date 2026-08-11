import json
import random
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import fitz
from fastapi import HTTPException
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

from backend.core.settings import settings
from backend.database.db import get_conn, now_iso
from backend.models.schemas import ExtractFieldRequest, TemplateMergeRequest, TemplateMergeResponse
from backend.services.app_module_service import run_pdf_merge_engine
from backend.services.document_service import extract_document_fields_detail, get_document
from backend.services.page_registration_service import align_positions_to_document
from backend.services.fax_effect_service import apply_fax_effect
from backend.services.template_service import get_template


FIELD_LABELS = {
    "customer_name": "고객명",
    "manager_name": "팀장명",
    "manager_code": "코드",
}

EXTRACT_FIELD_KEYS = {"customer_name", "manager_name", "manager_code"}


def _positions(template) -> list[dict[str, Any]]:
    pages = template.overlay_config.get("pages", {})
    positions: list[dict[str, Any]] = []
    for page_no, page_config in pages.items():
        for position in page_config.get("positions", []):
            positions.append({**position, "page": int(position.get("page", page_no))})
    return positions


def _page_count(pdf_path: Path) -> int:
    with fitz.open(pdf_path) as pdf:
        return int(pdf.page_count)


def _template_group_page_count(template, positions: list[dict[str, Any]] | None = None) -> int:
    style = _default_render_style(template.render_style)
    configured = style.get("page_group_size") or style.get("batch_page_count") or 3
    try:
        group_page_count = max(1, int(configured))
    except (TypeError, ValueError):
        group_page_count = 3
    max_position_page = max((int(position.get("page", 1)) for position in (positions or _positions(template))), default=1)
    return max(group_page_count, max_position_page)


def _batch_count_for_pdf(page_count: int, group_page_count: int) -> int:
    if page_count <= group_page_count:
        return 1
    if page_count % group_page_count != 0:
        raise HTTPException(
            status_code=400,
            detail=f"업로드 PDF는 {group_page_count}페이지 단위 템플릿과 맞아야 합니다. 현재 {page_count}페이지라서 마지막 묶음이 맞지 않습니다.",
        )
    return page_count // group_page_count


def _position_with_offset(position: dict[str, Any], page_offset: int, group_index: int, force_suffix: bool) -> dict[str, Any]:
    next_position = {**position, "page": int(position.get("page", 1)) + page_offset}
    position_id = str(position.get("id") or "")
    if position_id and force_suffix:
        next_position["source_id"] = position_id
        next_position["id"] = f"{position_id}__g{group_index + 1}"
    return next_position


def _overlay_config_from_positions(positions: list[dict[str, Any]]) -> dict[str, Any]:
    pages: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for position in positions:
        page_key = str(int(position.get("page", 1)))
        pages.setdefault(page_key, {"positions": []})["positions"].append(position)
    return {"pages": pages}


def _extract_fields_from_positions(document_id: int, positions: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    fields = [
        ExtractFieldRequest(
            field_key=str(position.get("field_key", "")),
            page=int(position["page"]),
            x=float(position["x"]),
            y=float(position["y"]),
            width=float(position["width"]),
            height=float(position["height"]),
            unit=str(position.get("unit", "pdf_point")),
        )
        for position in positions
        if position.get("type") == "extract_text" and position.get("field_key")
    ]
    return extract_document_fields_detail(document_id, fields)


def _extract_fields_from_template_detail(template, document_id: int | None = None) -> dict[str, dict[str, str]]:
    target_document_id = document_id if document_id is not None else template.document_id
    if target_document_id is None:
        raise HTTPException(status_code=400, detail="템플릿에 기준 PDF가 연결되어 있지 않습니다.")

    fields = [
        ExtractFieldRequest(
            field_key=str(position.get("field_key", "")),
            page=int(position["page"]),
            x=float(position["x"]),
            y=float(position["y"]),
            width=float(position["width"]),
            height=float(position["height"]),
            unit=str(position.get("unit", "pdf_point")),
        )
        for position in _positions(template)
        if position.get("type") == "extract_text" and position.get("field_key")
    ]
    return extract_document_fields_detail(target_document_id, fields)


def extract_template_fields(template_id: int) -> dict[str, str]:
    return _extract_fields_from_template_detail(get_template(template_id))["fields"]


def extract_template_fields_detail(template_id: int, document_id_override: int | None = None) -> dict[str, dict[str, str]]:
    return _extract_fields_from_template_detail(get_template(template_id), document_id_override)


def extract_template_batch_fields_detail(template_id: int, document_id_override: int | None = None) -> dict[str, Any]:
    template = get_template(template_id)
    target_document_id = document_id_override if document_id_override is not None else template.document_id
    if target_document_id is None:
        raise HTTPException(status_code=400, detail="?쒗뵆由우뿉 湲곗? PDF媛 ?곌껐?섏뼱 ?덉? ?딆뒿?덈떎.")
    document = get_document(target_document_id)
    pdf_path = Path(document.file_path)
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="?먮낯 PDF ?뚯씪??李얠쓣 ???놁뒿?덈떎.")

    base_positions = _positions(template)
    group_page_count = _template_group_page_count(template, base_positions)
    source_page_count = _page_count(pdf_path)
    batch_count = _batch_count_for_pdf(source_page_count, group_page_count)
    items: list[dict[str, Any]] = []
    for group_index in range(batch_count):
        page_offset = group_index * group_page_count
        group_positions = [
            _position_with_offset(position, page_offset, group_index, force_suffix=batch_count > 1)
            for position in base_positions
            if int(position.get("page", 1)) + page_offset <= source_page_count
        ]
        detail = _extract_fields_from_positions(target_document_id, group_positions)
        items.append(
            {
                "group_index": group_index + 1,
                "page_start": page_offset + 1,
                "page_end": min(page_offset + group_page_count, source_page_count),
                **detail,
            }
        )

    first = items[0] if items else {"fields": {}, "raw_fields": {}, "warnings": {}}
    return {
        "fields": first.get("fields", {}),
        "raw_fields": first.get("raw_fields", {}),
        "warnings": first.get("warnings", {}),
        "page_count": source_page_count,
        "group_page_count": group_page_count,
        "batch_count": batch_count,
        "batch_items": items,
    }


def _safe_filename_part(value: Any) -> str:
    text = str(value or "unknown").strip()
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r'[\\/:*?"<>|]', "", text)
    return (text or "unknown")[:60]


def _output_filename(form_data: dict[str, Any]) -> str:
    base = "_".join(
        [
            _safe_filename_part(form_data.get("manager_code")),
            _safe_filename_part(form_data.get("manager_name")),
            _safe_filename_part(form_data.get("customer_name")),
        ]
    )
    candidate = f"{base}.pdf"
    if not (settings.final_output_dir / candidate).exists():
        return candidate
    return f"{base}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"


def _default_render_style(render_style: dict[str, Any]) -> dict[str, Any]:
    merged = {
        "randomize": True,
        "pdf_level_style": True,
        "page_group_size": 3,
        "signature_generation_modes": [
            "jamo_composed_signature",
            "first_korean_char",
            "english_cursive_full",
            "english_initials",
            "last_korean_char",
            "full_korean_name",
            "neat_korean_name",
        ],
        "check_stroke_profiles": ["normal", "dark", "light"],
        "pen_textures": ["thin_ballpen", "thick_ballpen", "sign_pen", "weak_ballpen"],
        "keep_style_consistency_per_pdf": True,
        "fax_effect": True,
        "fax_effect_config": {
            "dpi": 200,
            "rotation": [-0.2, 0.2],
            "contrast": 1.42,
            "brightness": 0.96,
            "noise": 3,
            "blur": 0,
            "jpeg_quality": 92,
        },
        "random_range": {
            "rotation": [-3, 3],
            "offset_x": [-2, 2],
            "offset_y": [-2, 2],
            "scale": [0.95, 1.08],
            "opacity": [0.85, 1.0],
        },
    }
    merged.update(render_style or {})
    return merged


def _pick_style_profile(render_style: dict[str, Any]) -> dict[str, Any]:
    style = _default_render_style(render_style)
    seed = random.randint(100000, 999999)
    rng = random.Random(seed)
    pen_texture = rng.choice(style.get("pen_textures") or ["thin_ballpen"])
    # Consent marks must remain legible after fax conversion, so do not randomly
    # select a light stroke profile for production output.
    # Use the original handwritten check asset, but keep its ink reliably
    # legible after grayscale/fax conversion instead of randomly fading it.
    check_profile = "ultra_dark"
    modes = style.get("signature_generation_modes") or ["full_korean_name"]
    profile = {
        "style_seed": seed,
        "font_profile": "fallback_default",
        "signature_generation_mode": rng.choice(modes),
        "check_stroke_profile": check_profile,
        "pen_texture": pen_texture,
        "base_opacity": rng.uniform(0.88, 0.98),
        "base_rotation_range": style["random_range"].get("rotation", [-3, 3]),
        "base_scale_range": style["random_range"].get("scale", [0.95, 1.08]),
        "random_range": style["random_range"],
        "fax_effect": bool(style.get("fax_effect", True)),
        "fax_effect_config": style.get("fax_effect_config", {}),
    }
    if check_profile in {"light"} or pen_texture == "weak_ballpen":
        profile["base_opacity"] = min(profile["base_opacity"], 0.88)
    if check_profile in {"dark", "thick", "extra_thick"} or pen_texture == "sign_pen":
        profile["base_opacity"] = max(profile["base_opacity"], 0.94)
    return profile


def _romanize_name(name: str) -> str:
    # Small fallback: common surnames + syllable initials. Intended as editable test output, not official romanization.
    surname_map = {"김": "Kim", "이": "Lee", "박": "Park", "최": "Choi", "정": "Jung", "강": "Kang", "조": "Cho", "윤": "Yoon", "장": "Jang", "임": "Lim"}
    initial_map = [
        "G",
        "K",
        "N",
        "D",
        "T",
        "R",
        "M",
        "B",
        "P",
        "S",
        "S",
        "",
        "J",
        "J",
        "Ch",
        "K",
        "T",
        "P",
        "H",
    ]
    if not name:
        return ""
    if name[0] not in surname_map and "\uac00" <= name[0] <= "\ud7a3":
        return ""
    surname = surname_map.get(name[0], name[0])
    rest = []
    for char in name[1:]:
        code = ord(char) - 0xAC00
        if 0 <= code <= 11171:
            rest.append(initial_map[code // 588])
        else:
            rest.append(char)
    romanized = f"{surname} {''.join(rest).title()}".strip()
    return romanized if re.fullmatch(r"[A-Za-z\s.]+", romanized) else ""


def _signature_text(customer_name: str, profile: dict[str, Any]) -> str:
    customer_name = re.sub(r"[^가-힣a-zA-Z\s]", "", customer_name or "").strip()
    if not customer_name:
        raise HTTPException(status_code=400, detail="customer_name이 없어 자동 서명을 생성할 수 없습니다.")
    allowed_modes = {
        "first_korean_char",
        "english_cursive_full",
        "english_initials",
        "last_korean_char",
        "full_korean_name",
        "neat_korean_name",
        "jamo_composed_signature",
    }
    mode = profile.get("signature_generation_mode")
    if mode not in allowed_modes:
        mode = "full_korean_name"
        profile["signature_generation_mode"] = mode
    romanized = _romanize_name(customer_name)
    if mode == "first_korean_char":
        return customer_name[0]
    if mode == "last_korean_char":
        return customer_name[-1]
    if mode == "english_cursive_full" and romanized:
        return romanized
    if mode == "english_initials" and romanized:
        initials = "".join(part[0].upper() for part in romanized.split() if part)
        return initials if initials else customer_name
    return customer_name


def _font_supports_text(font: ImageFont.FreeTypeFont, text: str) -> bool:
    try:
        for char in text:
            if char.isspace():
                continue
            mask = font.getmask(char)
            if mask.getbbox() is None:
                return False
        return True
    except Exception:
        return False


def _font_file_supports_text(path: Path, text: str) -> bool:
    try:
        from fontTools.ttLib import TTCollection, TTFont
    except Exception:
        return True

    wanted = {ord(char) for char in text if not char.isspace()}
    if not wanted:
        return False

    def font_has_all(font: Any) -> bool:
        cmap: set[int] = set()
        for table in font["cmap"].tables:
            cmap.update(table.cmap.keys())
        return wanted.issubset(cmap)

    try:
        if path.suffix.lower() == ".ttc":
            collection = TTCollection(str(path))
            return any(font_has_all(font) for font in collection.fonts)
        with TTFont(str(path), lazy=True) as font:
            return font_has_all(font)
    except Exception:
        return True


def _font(size: int, text: str) -> tuple[ImageFont.ImageFont, str, bool]:
    candidates: list[Path] = []
    handwriting_dir = settings.root_dir / "shared" / "assets" / "fonts" / "handwriting"
    if handwriting_dir.exists():
        candidates.extend(sorted(handwriting_dir.glob("*.ttf")))
        candidates.extend(sorted(handwriting_dir.glob("*.otf")))
    windows_fonts = Path("C:/Windows/Fonts")
    for filename in ["malgun.ttf", "malgunbd.ttf", "gulim.ttc", "batang.ttc", "arial.ttf", "segoepr.ttf"]:
        candidates.append(windows_fonts / filename)

    fallback_used = True
    for path in candidates:
        if not path.exists():
            continue
        if not _font_file_supports_text(path, text):
            continue
        try:
            font = ImageFont.truetype(str(path), size=size)
        except OSError:
            continue
        if _font_supports_text(font, text):
            fallback_used = "handwriting" not in str(path).replace("\\", "/")
            return font, path.stem, fallback_used
    raise HTTPException(status_code=500, detail=f"서명 텍스트를 렌더링할 수 있는 폰트를 찾지 못했습니다: {text}")


def _create_signature_image(text: str, profile: dict[str, Any]) -> Path:
    forbidden = ["□", "�", "Mr", "Mrs", "Signature", "Sign"]
    if not text or any(token in text for token in forbidden):
        raise HTTPException(status_code=500, detail=f"허용되지 않는 서명 문자열입니다: {text}")
    image = Image.new("RGBA", (520, 180), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    font, font_name, fallback_used = _font(96, text)
    profile["generated_signature_text"] = text
    profile["generated_signature_font"] = font_name
    profile["generated_signature_font_fallback"] = fallback_used
    bbox = draw.textbbox((0, 0), text, font=font)
    draw.text((24, 24), text, fill=(10, 10, 10, int(255 * float(profile.get("base_opacity", 0.92)))), font=font)
    image = image.crop((0, 0, max(80, bbox[2] + 60), max(60, bbox[3] + 60)))
    rotation_min, rotation_max = profile.get("base_rotation_range", [-3, 3])
    image = image.rotate(random.uniform(rotation_min, rotation_max), expand=True, resample=Image.Resampling.BICUBIC)
    settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(prefix="generated_signature_", suffix=".png", delete=False, dir=settings.tmp_dir)
    tmp_path = Path(tmp.name)
    tmp.close()
    image.save(tmp_path)
    return tmp_path


def _is_english_signature_candidate(value: str) -> bool:
    text = (value or "").strip()
    return bool(text) and re.fullmatch(r"[A-Za-z\s.'-]+", text) is not None


def _needs_saved_signature_fallback(customer_name: str, used_jamo: list[str], missing_jamo: list[str]) -> tuple[bool, str]:
    if _is_english_signature_candidate(customer_name):
        return True, "english"
    if missing_jamo:
        return True, "missing_jamo"
    if any(item.startswith(("placeholder:", "substitute:")) for item in used_jamo):
        return True, "incomplete_jamo"
    return False, ""


def _record_signature_warning(profile: dict[str, Any], customer_name: str, reason: str, message: str) -> None:
    warnings = profile.setdefault("signature_fallback_warnings", [])
    if isinstance(warnings, list):
        warnings.append({"customer_name": customer_name, "reason": reason, "message": message})


def _saved_signature_or_none(reason: str, profile: dict[str, Any]) -> Path | None:
    from backend.services.signature_asset_service import pick_fallback_signature

    path = pick_fallback_signature(category=reason)
    if path is None:
        return None
    profile["saved_signature_fallback_reason"] = reason
    profile["saved_signature_fallback_path"] = str(path)
    return path


def _saved_signature_or_error(reason: str, profile: dict[str, Any]) -> Path:
    path = _saved_signature_or_none(reason, profile)
    if path is not None:
        return path
    raise HTTPException(
        status_code=500,
        detail="저장된 대체 서명이 없습니다. /admin 서명 관리에서 fallback 서명을 먼저 업로드하세요.",
    )


def _text_signature_fallback(customer_name: str, profile: dict[str, Any]) -> Path:
    text = _signature_text(customer_name, profile)
    profile["generated_signature_mode"] = "text_signature_fallback"
    return _create_signature_image(text, profile)


def _overlay_for_position(position: dict[str, Any], form_data: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any] | None:
    position_type = position.get("type")
    position_id = position.get("id")
    random_range = profile.get("random_range", {})
    if not position_id or position_type == "extract_text":
        return None
    if position_type == "check":
        return {
            "position_id": position_id,
            "type": "image",
            "source_type": "check_asset",
            "random_range": random_range,
            "check_stroke_profile": profile.get("check_stroke_profile", "normal"),
            "check_ink_opacity": 1.0,
        }
    if position_type == "signature":
        customer_name = str(form_data.get("customer_name", ""))
        try:
            from backend.services.jamo_asset_service import create_jamo_signature_image

            signature_path, used_jamo, missing_jamo = create_jamo_signature_image(customer_name, profile)
            needs_fallback, fallback_reason = _needs_saved_signature_fallback(customer_name, used_jamo, missing_jamo)
            if needs_fallback:
                saved_signature_path = _saved_signature_or_none(fallback_reason, profile)
                if saved_signature_path is not None:
                    if settings.tmp_dir in signature_path.parents and signature_path.exists():
                        signature_path.unlink()
                    signature_path = saved_signature_path
                    profile["generated_signature_mode"] = "saved_signature_fallback"
                else:
                    _record_signature_warning(
                        profile,
                        customer_name,
                        fallback_reason,
                        "saved fallback signature is missing; generated signature was used",
                    )
                    profile["generated_signature_mode"] = "generated_signature_without_saved_fallback"
            else:
                profile["generated_signature_mode"] = "jamo_composed_signature"
            profile["generated_signature_text"] = customer_name
            profile["signature_generation_mode"] = "jamo_composed_signature"
            profile["jamo_used"] = used_jamo
            profile["jamo_missing"] = missing_jamo
            return {
                "position_id": position_id,
                "type": "image",
                "source_type": "generated_signature",
                "image_path": str(signature_path),
                "random_range": random_range,
            }
        except HTTPException:
            if _is_english_signature_candidate(customer_name):
                signature_path = _saved_signature_or_none("english", profile)
                if signature_path is None:
                    _record_signature_warning(
                        profile,
                        customer_name,
                        "english",
                        "saved english fallback signature is missing; text signature was used",
                    )
                    signature_path = _text_signature_fallback(customer_name, profile)
                profile["generated_signature_text"] = customer_name
                profile.setdefault("generated_signature_mode", "saved_signature_fallback")
                return {
                    "position_id": position_id,
                    "type": "image",
                    "source_type": "generated_signature",
                    "image_path": str(signature_path),
                    "random_range": random_range,
                }
            raise
        except Exception as error:
            profile["jamo_signature_error"] = str(error)
        signature_path = _saved_signature_or_none("fallback", profile)
        if signature_path is None:
            _record_signature_warning(
                profile,
                customer_name,
                "fallback",
                "saved fallback signature is missing; text signature was used",
            )
            signature_path = _text_signature_fallback(customer_name, profile)
        profile["generated_signature_text"] = customer_name
        profile.setdefault("generated_signature_mode", "saved_signature_fallback")
        return {
            "position_id": position_id,
            "type": "image",
            "source_type": "generated_signature",
            "image_path": str(signature_path),
            "random_range": random_range,
        }
    if position_type == "date":
        value = form_data.get("date") or datetime.now().strftime("%Y.%m.%d")
    elif position_type == "name":
        value = form_data.get("customer_name") or form_data.get("name") or ""
        from backend.services.jamo_asset_service import create_jamo_signature_image

        name_profile = {
            **profile,
            "style_seed": int(profile.get("style_seed", 0)) + 817,
            "base_opacity": 0.92,
            "base_rotation_range": [-1.2, 1.2],
        }
        name_path, used_jamo, missing_jamo = create_jamo_signature_image(str(value), name_profile)
        profile["generated_name_mode"] = "jamo_composed_name"
        profile["name_jamo_used"] = used_jamo
        profile["name_jamo_missing"] = missing_jamo
        return {
            "position_id": position_id,
            "type": "image",
            "source_type": "generated_name",
            "image_path": str(name_path),
        }
    else:
        return None
    return {"position_id": position_id, "type": "text", "source_type": "text", "value": value, "fontsize": 11}


def _write_json_tmp(prefix: str, data: dict[str, Any]) -> Path:
    settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(prefix=prefix, suffix=".json", delete=False, dir=settings.tmp_dir, mode="w", encoding="utf-8")
    with tmp:
        json.dump(data, tmp, ensure_ascii=False, indent=2)
    return Path(tmp.name)


def merge_template_pdf(template_id: int, payload: TemplateMergeRequest, document_id_override: int | None = None) -> TemplateMergeResponse:
    template = get_template(template_id)
    target_document_id = document_id_override if document_id_override is not None else template.document_id
    if target_document_id is None:
        raise HTTPException(status_code=400, detail="템플릿에 기준 PDF가 연결되어 있지 않습니다.")
    document = get_document(target_document_id)
    pdf_path = Path(document.file_path)
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="원본 PDF 파일을 찾을 수 없습니다.")

    base_positions = _positions(template)
    source_page_count = _page_count(pdf_path)
    group_page_count = _template_group_page_count(template, base_positions)
    batch_count = _batch_count_for_pdf(source_page_count, group_page_count)
    profile = _pick_style_profile(template.render_style)

    all_positions: list[dict[str, Any]] = []
    overlays: list[dict[str, Any]] = []
    batch_items: list[dict[str, Any]] = []
    first_form_data: dict[str, Any] | None = None
    first_extracted: dict[str, str] = {}
    payload_form_data = dict(payload.form_data or {})

    for group_index in range(batch_count):
        page_offset = group_index * group_page_count
        source_group_positions = [
            _position_with_offset(position, page_offset, group_index, force_suffix=batch_count > 1)
            for position in base_positions
            if int(position.get("page", 1)) + page_offset <= source_page_count
        ]
        # Keep the known-good OCR rectangles in their original coordinates,
        # while rendering checks/names/signatures against the registered page
        # so Letter and A4 output share the same printed locations.
        group_positions = align_positions_to_document(pdf_path, source_group_positions)
        extract_detail = (
            _extract_fields_from_positions(target_document_id, source_group_positions)
            if payload.options.auto_extract
            else {"fields": {}, "raw_fields": {}, "warnings": {}}
        )
        extracted = extract_detail.get("fields", {})
        if group_index == 0:
            overrides = payload_form_data
        else:
            overrides = {key: value for key, value in payload_form_data.items() if key not in EXTRACT_FIELD_KEYS}
        form_data = {**template.form_data, **extracted, **overrides}
        form_data.setdefault("date", datetime.now().strftime("%Y.%m.%d"))
        group_overlays = [
            overlay
            for overlay in (_overlay_for_position(position, form_data, profile) for position in group_positions)
            if overlay is not None
        ]
        all_positions.extend(group_positions)
        overlays.extend(group_overlays)
        if first_form_data is None:
            first_form_data = dict(form_data)
            first_extracted = dict(extracted)
        batch_items.append(
            {
                "group_index": group_index + 1,
                "page_start": page_offset + 1,
                "page_end": min(page_offset + group_page_count, source_page_count),
                "fields": extracted,
                "raw_fields": extract_detail.get("raw_fields", {}),
                "warnings": extract_detail.get("warnings", {}),
            }
        )

    output_form_data = first_form_data or {}
    if batch_count > 1:
        output_form_data = {
            **output_form_data,
            "customer_name": f"{output_form_data.get('customer_name') or 'unknown'}_외{batch_count - 1}명",
        }
    merge_form_data = {**output_form_data, "overlays": overlays, "applied_style_profile": profile}

    output_filename = _output_filename(output_form_data) if payload.options.auto_filename else f"template_{template_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    output_path = settings.final_output_dir / output_filename
    overlay_path = _write_json_tmp(f"template_{template_id}_overlay_", _overlay_config_from_positions(all_positions))
    form_data_path = _write_json_tmp(f"template_{template_id}_form_data_", merge_form_data)

    try:
        result_path = run_pdf_merge_engine(pdf_path=pdf_path, overlay_config_path=overlay_path, form_data_path=form_data_path, output_path=output_path)
        if profile.get("fax_effect"):
            result_path = apply_fax_effect(Path(result_path), profile.get("fax_effect_config", {}), seed=int(profile["style_seed"]))
    finally:
        _cleanup_tmp_paths(
            [
                overlay_path,
                form_data_path,
                *(
                    Path(overlay["image_path"])
                    for overlay in overlays
                    if overlay.get("source_type") in {"generated_signature", "generated_name"} and overlay.get("image_path")
                ),
            ]
        )
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO merge_runs(document_id, status, output_path, message, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (target_document_id, "success", str(result_path), "템플릿 PDF 합성이 완료되었습니다.", now_iso()),
        )
    message = "템플릿 PDF 합성이 완료되었습니다."
    extract_warnings = batch_items[0].get("warnings", {}) if batch_items else {}
    response_profile = {
        **profile,
        "extract_warnings": extract_warnings,
        "source_page_count": source_page_count,
        "group_page_count": group_page_count,
        "batch_count": batch_count,
        "batch_items": batch_items,
    }
    response_fields = {
        key: str((first_form_data or {}).get(key, first_extracted.get(key, "")))
        for key in EXTRACT_FIELD_KEYS
        if (first_form_data or {}).get(key, first_extracted.get(key, "")) is not None
    }
    return TemplateMergeResponse(
        success=True,
        output_filename=Path(result_path).name,
        output_path=str(result_path),
        message=message,
        extracted_fields=response_fields,
        applied_style_profile=response_profile,
    )


def _cleanup_tmp_paths(paths: list[Path]) -> None:
    for path in paths:
        try:
            if path.is_file() and settings.tmp_dir in path.parents:
                path.unlink()
        except OSError:
            pass
