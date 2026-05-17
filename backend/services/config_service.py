import json
from pathlib import Path
from typing import Any

from backend.core.settings import settings


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        _write_json(path, default)
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        backup = path.with_suffix(path.suffix + ".broken")
        path.replace(backup)
        _write_json(path, default)
        return default


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def read_overlay_config() -> dict[str, Any]:
    return _read_json(settings.overlay_config_path, {"pages": {}})


def save_overlay_config(data: dict[str, Any]) -> None:
    _write_json(settings.overlay_config_path, data)


def read_form_data() -> dict[str, Any]:
    return _read_json(settings.form_data_path, {})


def save_form_data(data: dict[str, Any]) -> None:
    _write_json(settings.form_data_path, data)
