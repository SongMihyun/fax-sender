import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from backend.core.settings import settings
from backend.database.db import get_conn, now_iso
from backend.models.schemas import TemplateCreate, TemplateOut, TemplatePublicOut, TemplateUpdate


def _default_overlay_config() -> dict[str, Any]:
    return {"pages": {}}


def _default_render_style() -> dict[str, Any]:
    return {
        "font_family": "random",
        "pen_texture": "random",
        "randomize": True,
        "pdf_level_style": True,
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
        "keep_style_consistency_per_pdf": True,
        "fax_effect": True,
        "fax_effect_config": {
            "dpi": 170,
            "rotation": [-0.35, 0.35],
            "contrast": 1.18,
            "brightness": 1.02,
            "noise": 7,
            "blur": 0.18,
        },
        "random_range": {
            "rotation": [-3, 3],
            "offset_x": [-2, 2],
            "offset_y": [-2, 2],
            "scale": [0.95, 1.05],
            "opacity": [0.85, 1.0],
        },
    }


def _loads_json_object(value: str, default: dict[str, Any]) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return default

    return parsed if isinstance(parsed, dict) else default


def _row_to_template(row) -> TemplateOut:
    return TemplateOut(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        document_id=row["document_id"],
        document_name=row["document_name"],
        overlay_config=_loads_json_object(row["overlay_config_json"], _default_overlay_config()),
        form_data=_loads_json_object(row["form_data_json"], {}),
        render_style=_loads_json_object(row["render_style_json"], _default_render_style()),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def list_templates() -> list[TemplateOut]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT t.*, d.original_name AS document_name
            FROM pdf_templates t
            LEFT JOIN documents d ON d.id = t.document_id
            ORDER BY t.updated_at DESC, t.id DESC
            """
        ).fetchall()
    return [_row_to_template(row) for row in rows]


def list_public_templates() -> list[TemplatePublicOut]:
    return [
        TemplatePublicOut(id=template.id, name=template.name, description=template.description, document_name=template.document_name)
        for template in list_templates()
        if template.document_id is not None
    ]


def get_template(template_id: int) -> TemplateOut:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT t.*, d.original_name AS document_name
            FROM pdf_templates t
            LEFT JOIN documents d ON d.id = t.document_id
            WHERE t.id = ?
            """,
            (template_id,),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없습니다.")
    return _row_to_template(row)


def create_template(payload: TemplateCreate) -> TemplateOut:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="템플릿 이름이 필요합니다.")

    created_at = now_iso()
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO pdf_templates(
                name, description, document_id, overlay_config_json, form_data_json, render_style_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                payload.description.strip(),
                payload.document_id,
                json.dumps(payload.overlay_config, ensure_ascii=False, indent=2),
                json.dumps(payload.form_data, ensure_ascii=False, indent=2),
                json.dumps(payload.render_style, ensure_ascii=False, indent=2),
                created_at,
                created_at,
            ),
        )
        template_id = cur.lastrowid

    return get_template(template_id)


def update_template(template_id: int, payload: TemplateUpdate) -> TemplateOut:
    current = get_template(template_id)
    updated_fields = payload.model_fields_set

    name = current.name if "name" not in updated_fields or payload.name is None else payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="템플릿 이름이 필요합니다.")

    description = current.description if "description" not in updated_fields or payload.description is None else payload.description.strip()
    document_id = current.document_id if "document_id" not in updated_fields else payload.document_id
    overlay_config = current.overlay_config if "overlay_config" not in updated_fields or payload.overlay_config is None else payload.overlay_config
    form_data = current.form_data if "form_data" not in updated_fields or payload.form_data is None else payload.form_data
    render_style = current.render_style if "render_style" not in updated_fields or payload.render_style is None else payload.render_style

    with get_conn() as conn:
        conn.execute(
            """
            UPDATE pdf_templates
            SET name = ?,
                description = ?,
                document_id = ?,
                overlay_config_json = ?,
                form_data_json = ?,
                render_style_json = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                name,
                description,
                document_id,
                json.dumps(overlay_config, ensure_ascii=False, indent=2),
                json.dumps(form_data, ensure_ascii=False, indent=2),
                json.dumps(render_style, ensure_ascii=False, indent=2),
                now_iso(),
                template_id,
            ),
        )

    return get_template(template_id)


def delete_template(template_id: int) -> dict[str, str]:
    get_template(template_id)
    with get_conn() as conn:
        conn.execute("DELETE FROM pdf_templates WHERE id = ?", (template_id,))
    return {"status": "deleted"}


def write_template_overlay_config(template_id: int) -> Path:
    template = get_template(template_id)
    target_dir = settings.configs_dir / "templates"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"template_{template.id}_overlay_config.json"
    target_path.write_text(json.dumps(template.overlay_config, ensure_ascii=False, indent=2), encoding="utf-8")
    return target_path
