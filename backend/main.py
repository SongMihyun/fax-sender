from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.health import router as health_router
from backend.api.documents import router as documents_router
from backend.api.configs import router as configs_router
from backend.api.merge import router as merge_router
from backend.api.templates import router as templates_router
from backend.api.admin_templates import router as admin_templates_router
from backend.api.check_assets import router as check_assets_router
from backend.api.process import router as process_router
from backend.api.jamo_assets import router as jamo_assets_router
from backend.core.settings import settings
from backend.database.db import init_db


def create_app() -> FastAPI:
    init_db()
    app = FastAPI(
        title="Fax Sender Backend API",
        version="0.1.0",
        description="MP4 modular backend server. Frontend -> Backend API -> apps modules.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router, prefix="/api")
    app.include_router(documents_router, prefix="/api/documents", tags=["documents"])
    app.include_router(templates_router, prefix="/api/templates", tags=["templates"])
    app.include_router(check_assets_router, prefix="/api/check-assets", tags=["check-assets"])
    app.include_router(jamo_assets_router, prefix="/api/admin/jamo", tags=["admin-jamo"])
    app.include_router(admin_templates_router, prefix="/api/admin", tags=["admin-templates"])
    app.include_router(process_router, prefix="/api/process", tags=["process"])
    app.include_router(configs_router, prefix="/api/configs", tags=["configs"])
    app.include_router(merge_router, prefix="/api/merge", tags=["merge"])

    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/storage", StaticFiles(directory=str(settings.storage_dir)), name="storage")
    settings.final_output_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/final-output", StaticFiles(directory=str(settings.final_output_dir)), name="final-output")
    return app


app = create_app()
