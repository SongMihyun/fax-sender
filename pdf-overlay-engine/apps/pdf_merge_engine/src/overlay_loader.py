import json
from pathlib import Path


def load_overlay_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)