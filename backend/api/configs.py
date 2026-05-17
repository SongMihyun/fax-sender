from fastapi import APIRouter
from backend.models.schemas import ConfigPayload
from backend.services.config_service import read_overlay_config, save_overlay_config, read_form_data, save_form_data

router = APIRouter()


@router.get("/overlay")
def get_overlay_config():
    return read_overlay_config()


@router.post("/overlay")
def post_overlay_config(payload: ConfigPayload):
    save_overlay_config(payload.data)
    return {"status": "saved"}


@router.get("/form-data")
def get_form_data():
    return read_form_data()


@router.post("/form-data")
def post_form_data(payload: ConfigPayload):
    save_form_data(payload.data)
    return {"status": "saved"}
