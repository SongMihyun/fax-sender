import json
import re
from pathlib import Path

from fastapi import HTTPException

from backend.core.settings import settings
from backend.database.db import get_conn, now_iso
from backend.models.schemas import AdminTemplateCreate, AdminTemplateOut, TemplateVersionCreate, TemplateVersionOut


def _safe_key(value: str) -> str:
    key = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip()).strip("_").lower()
    if not key:
        raise HTTPException(status_code=400, detail="template_key is required")
    return key[:80]


def _row_to_admin_template(row) -> AdminTemplateOut:
    return AdminTemplateOut(
        id=row["id"],
        template_key=row["template_key"],
        template_name=row["template_name"],
        insurer_name=row["insurer_name"],
        description=row["description"],
        is_active=bool(row["is_active"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_version(row) -> TemplateVersionOut:
    return TemplateVersionOut(
        id=row["id"],
        template_id=row["template_id"],
        version=row["version"],
        pdf_sample_path=row["pdf_sample_path"],
        overlay_config_path=row["overlay_config_path"],
        extract_config_path=row["extract_config_path"],
        is_active=bool(row["is_active"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def list_admin_templates() -> list[AdminTemplateOut]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM templates ORDER BY updated_at DESC, id DESC").fetchall()
    return [_row_to_admin_template(row) for row in rows]


def create_admin_template(payload: AdminTemplateCreate) -> AdminTemplateOut:
    now = now_iso()
    key = _safe_key(payload.template_key)
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO templates(template_key, template_name, insurer_name, description, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, ?, ?)
            """,
            (key, payload.template_name.strip(), payload.insurer_name, payload.description, now, now),
        )
        template_id = cur.lastrowid
        row = conn.execute("SELECT * FROM templates WHERE id = ?", (template_id,)).fetchone()
    return _row_to_admin_template(row)


def create_template_version(template_id: int, payload: TemplateVersionCreate) -> TemplateVersionOut:
    with get_conn() as conn:
        template = conn.execute("SELECT * FROM templates WHERE id = ?", (template_id,)).fetchone()
    if not template:
        raise HTTPException(status_code=404, detail="template not found")

    version = _safe_key(payload.version)
    version_dir = settings.configs_dir / "templates" / template["template_key"] / version
    version_dir.mkdir(parents=True, exist_ok=True)
    overlay_path = version_dir / "overlay_config.json"
    extract_path = version_dir / "extract_config.json"
    overlay_path.write_text(json.dumps(payload.overlay_config, ensure_ascii=False, indent=2), encoding="utf-8")
    extract_path.write_text(json.dumps(payload.extract_config, ensure_ascii=False, indent=2), encoding="utf-8")

    now = now_iso()
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO template_versions(
                template_id, version, pdf_sample_path, overlay_config_path, extract_config_path, is_active, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (template_id, version, payload.pdf_sample_path, str(overlay_path), str(extract_path), now, now),
        )
        version_id = cur.lastrowid
        row = conn.execute("SELECT * FROM template_versions WHERE id = ?", (version_id,)).fetchone()
    return _row_to_version(row)


def activate_template_version(version_id: int) -> TemplateVersionOut:
    now = now_iso()
    with get_conn() as conn:
        version = conn.execute("SELECT * FROM template_versions WHERE id = ?", (version_id,)).fetchone()
        if not version:
            raise HTTPException(status_code=404, detail="template version not found")
        conn.execute("UPDATE template_versions SET is_active = 0, updated_at = ? WHERE template_id = ?", (now, version["template_id"]))
        conn.execute("UPDATE template_versions SET is_active = 1, updated_at = ? WHERE id = ?", (now, version_id))
        row = conn.execute("SELECT * FROM template_versions WHERE id = ?", (version_id,)).fetchone()
    return _row_to_version(row)


def get_template_version(version_id: int) -> TemplateVersionOut:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM template_versions WHERE id = ?", (version_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="template version not found")
    return _row_to_version(row)


def get_active_template_version(template_id: int | None = None):
    query = "SELECT * FROM template_versions WHERE is_active = 1"
    params: tuple[int, ...] = ()
    if template_id is not None:
        query += " AND template_id = ?"
        params = (template_id,)
    query += " ORDER BY id DESC LIMIT 1"
    with get_conn() as conn:
        return conn.execute(query, params).fetchone()
