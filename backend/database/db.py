import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from backend.core.settings import settings


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    for name, ddl in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def init_db() -> None:
    for p in [
        settings.storage_dir,
        settings.uploads_dir,
        settings.incoming_dir,
        settings.original_uploads_dir,
        settings.normalized_dir,
        settings.normalized_uploads_dir,
        settings.extracted_dir,
        settings.generated_dir,
        settings.final_output_dir,
        settings.tmp_dir,
        settings.archive_dir,
        settings.failed_dir,
        settings.cache_dir,
        settings.cache_templates_dir,
        settings.cache_checks_dir,
        settings.cache_jamo_dir,
        settings.cache_fonts_dir,
        settings.cache_textures_dir,
        settings.signatures_dir,
        settings.check_sources_dir,
        settings.check_assets_base_dir,
        settings.check_assets_generated_dir,
        settings.jamo_sources_dir,
        settings.jamo_assets_dir,
        settings.configs_dir,
        settings.configs_dir / "templates",
        settings.logs_dir,
        settings.pdf_engine_standard_dir / "normalize",
        settings.pdf_engine_standard_dir / "extract",
        settings.pdf_engine_standard_dir / "merge",
    ]:
        p.mkdir(parents=True, exist_ok=True)
    if not settings.overlay_config_path.exists():
        settings.overlay_config_path.write_text('{"pages": {}}', encoding="utf-8")
    if not settings.form_data_path.exists():
        settings.form_data_path.write_text('{}', encoding="utf-8")

    with sqlite3.connect(settings.db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_name TEXT NOT NULL,
                stored_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                content_type TEXT,
                size_bytes INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                original_filename TEXT,
                stored_original_path TEXT,
                normalized_pdf_path TEXT,
                extracted_json_path TEXT,
                final_pdf_path TEXT,
                customer_name TEXT,
                manager_name TEXT,
                manager_code TEXT,
                template_id INTEGER,
                template_version_id INTEGER,
                status TEXT NOT NULL DEFAULT 'UPLOADED',
                failed_step TEXT,
                failed_reason TEXT,
                updated_at TEXT,
                sent_at TEXT
            )
            """
        )
        _ensure_columns(
            conn,
            "documents",
            {
                "original_filename": "TEXT",
                "stored_original_path": "TEXT",
                "normalized_pdf_path": "TEXT",
                "extracted_json_path": "TEXT",
                "final_pdf_path": "TEXT",
                "customer_name": "TEXT",
                "manager_name": "TEXT",
                "manager_code": "TEXT",
                "template_id": "INTEGER",
                "template_version_id": "INTEGER",
                "status": "TEXT NOT NULL DEFAULT 'UPLOADED'",
                "failed_step": "TEXT",
                "failed_reason": "TEXT",
                "updated_at": "TEXT",
                "sent_at": "TEXT",
            },
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS merge_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER,
                status TEXT NOT NULL,
                output_path TEXT,
                message TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(document_id) REFERENCES documents(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pdf_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                document_id INTEGER,
                overlay_config_json TEXT NOT NULL DEFAULT '{"pages": {}}',
                form_data_json TEXT NOT NULL DEFAULT '{}',
                render_style_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(document_id) REFERENCES documents(id)
            )
            """
        )
        existing_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(pdf_templates)").fetchall()
        }
        if "form_data_json" not in existing_columns:
            conn.execute("ALTER TABLE pdf_templates ADD COLUMN form_data_json TEXT NOT NULL DEFAULT '{}'")
        if "render_style_json" not in existing_columns:
            conn.execute("ALTER TABLE pdf_templates ADD COLUMN render_style_json TEXT NOT NULL DEFAULT '{}'")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_key TEXT NOT NULL UNIQUE,
                template_name TEXT NOT NULL,
                insurer_name TEXT,
                description TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS template_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id INTEGER NOT NULL,
                version TEXT NOT NULL,
                pdf_sample_path TEXT,
                overlay_config_path TEXT NOT NULL,
                extract_config_path TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(template_id) REFERENCES templates(id),
                UNIQUE(template_id, version)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS send_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                send_type TEXT NOT NULL,
                send_status TEXT NOT NULL,
                retry_count INTEGER NOT NULL DEFAULT 0,
                message TEXT,
                created_at TEXT NOT NULL,
                sent_at TEXT,
                FOREIGN KEY(document_id) REFERENCES documents(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS processing_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                step TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(document_id) REFERENCES documents(id)
            )
            """
        )
        conn.commit()


@contextmanager
def get_conn():
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")
