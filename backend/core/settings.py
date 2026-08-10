import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_root_dir() -> Path:
    configured = os.environ.get("FAX_SENDER_ROOT")
    return Path(configured).expanduser().resolve() if configured else Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Central server settings for the local fax sender app."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "fax-sender-backend"
    root_dir: Path = Field(default_factory=_default_root_dir)
    host: str = "127.0.0.1"
    port: int = 8791
    cors_origins: list[str] = [
        "http://127.0.0.1:5791",
        "http://127.0.0.1:5792",
        "http://127.0.0.1:5793",
        "http://127.0.0.1:5794",
        "http://127.0.0.1:5795",
        "http://127.0.0.1:5796",
        "http://127.0.0.1:5797",
        "http://127.0.0.1:5891",
        "http://127.0.0.1:5892",
        "http://localhost:5791",
        "http://localhost:5792",
        "http://localhost:5793",
        "http://localhost:5794",
        "http://localhost:5795",
        "http://localhost:5796",
        "http://localhost:5797",
        "http://localhost:5891",
        "http://localhost:5892",
    ]
    kakao_my_name: str = ""
    kakao_speed_mode: str = "normal"
    tesseract_cmd: str = ""

    @property
    def backend_dir(self) -> Path:
        return self.root_dir / "backend"

    @property
    def frontend_dir(self) -> Path:
        return self.root_dir / "frontend"

    @property
    def pdf_engine_dir(self) -> Path:
        return self.root_dir / "pdf-overlay-engine"

    @property
    def pdf_engine_standard_dir(self) -> Path:
        return self.root_dir / "pdf-engine"

    @property
    def apps_dir(self) -> Path:
        return self.pdf_engine_dir / "apps"

    @property
    def configs_dir(self) -> Path:
        return self.root_dir / "configs"

    @property
    def storage_dir(self) -> Path:
        return self.root_dir / "storage"

    @property
    def uploads_dir(self) -> Path:
        return self.storage_dir / "uploads"

    @property
    def incoming_dir(self) -> Path:
        return self.storage_dir / "incoming"

    @property
    def original_uploads_dir(self) -> Path:
        return self.incoming_dir

    @property
    def normalized_dir(self) -> Path:
        return self.storage_dir / "normalized"

    @property
    def normalized_uploads_dir(self) -> Path:
        return self.normalized_dir

    @property
    def extracted_dir(self) -> Path:
        return self.storage_dir / "extracted"

    @property
    def generated_dir(self) -> Path:
        return self.storage_dir / "generated"

    @property
    def final_output_dir(self) -> Path:
        return self.storage_dir / "final"

    @property
    def tmp_dir(self) -> Path:
        return self.storage_dir / "tmp"

    @property
    def archive_dir(self) -> Path:
        return self.storage_dir / "archive"

    @property
    def failed_dir(self) -> Path:
        return self.storage_dir / "failed"

    @property
    def cache_dir(self) -> Path:
        return self.storage_dir / "cache"

    @property
    def cache_templates_dir(self) -> Path:
        return self.cache_dir / "templates"

    @property
    def cache_checks_dir(self) -> Path:
        return self.cache_dir / "checks"

    @property
    def cache_jamo_dir(self) -> Path:
        return self.cache_dir / "jamo"

    @property
    def cache_fonts_dir(self) -> Path:
        return self.cache_dir / "fonts"

    @property
    def cache_textures_dir(self) -> Path:
        return self.cache_dir / "textures"

    @property
    def logs_dir(self) -> Path:
        return self.root_dir / "logs"

    @property
    def signatures_dir(self) -> Path:
        return self.storage_dir / "signatures"

    @property
    def check_sources_dir(self) -> Path:
        return self.storage_dir / "check_sources"

    @property
    def check_assets_base_dir(self) -> Path:
        return self.root_dir / "shared" / "assets" / "checks" / "base"

    @property
    def check_assets_generated_dir(self) -> Path:
        return self.root_dir / "shared" / "assets" / "checks" / "generated"

    @property
    def jamo_sources_dir(self) -> Path:
        return self.storage_dir / "jamo_sources"

    @property
    def jamo_assets_dir(self) -> Path:
        return self.root_dir / "shared" / "assets" / "jamo"

    @property
    def tessdata_dir(self) -> Path:
        return self.root_dir / "tools" / "tessdata"

    @property
    def db_path(self) -> Path:
        return self.storage_dir / "app.sqlite3"

    @property
    def overlay_config_path(self) -> Path:
        return self.configs_dir / "overlay_config.json"

    @property
    def form_data_path(self) -> Path:
        return self.configs_dir / "form_data.json"

    @property
    def active_template_path(self) -> Path:
        return self.configs_dir / "active_template.json"


settings = Settings()
