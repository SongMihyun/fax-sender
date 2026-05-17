from fastapi import APIRouter
from backend.core.settings import settings
from backend.models.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(status="ok", app=settings.app_name)
