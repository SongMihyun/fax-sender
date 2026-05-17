from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central server settings for the local fax sender app."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "fax-sender-backend"
    root_dir: Path = Path(__file__).resolve().parents[2]
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]

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
    def db_path(self) -> Path:
        return self.storage_dir / "app.sqlite3"

    @property
    def overlay_config_path(self) -> Path:
        return self.configs_dir / "overlay_config.json"

    @property
    def form_data_path(self) -> Path:
        return self.configs_dir / "form_data.json"


settings = Settings()
