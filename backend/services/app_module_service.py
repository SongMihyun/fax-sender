"""Bridge layer: backend -> pdf-overlay-engine/apps modules.

원칙:
- 핵심 기능은 pdf-overlay-engine/apps/* 에 독립 모듈로 둔다.
- backend는 직접 PDF 합성 로직을 갖지 않고, apps 모듈을 호출한다.
- 기존 apps/pdf_merge_engine 코드와 함수명이 달라도 이 파일만 조정하면 된다.
"""
from __future__ import annotations

import importlib
import shutil
import subprocess
import sys
from pathlib import Path

from backend.core.settings import settings


def _ensure_engine_on_path() -> None:
    """pdf-overlay-engine 폴더명을 유지하면서 apps/shared import를 가능하게 한다."""
    engine_dir = settings.pdf_engine_dir
    if str(engine_dir) not in sys.path:
        sys.path.insert(0, str(engine_dir))


def run_pdf_merge_engine(
    pdf_path: Path,
    overlay_config_path: Path,
    form_data_path: Path,
    output_path: Path,
) -> Path:
    """Run existing pdf-overlay-engine/apps/pdf_merge_engine as a reusable module.

    1순위: apps.pdf_merge_engine.src.main.run_merge 직접 호출
    2순위: CLI 인자로 subprocess 실행
    3순위: 엔진 연결 전 API 흐름 검증용 원본 PDF 복사 fallback
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _ensure_engine_on_path()

    # 1) Preferred callable contract
    try:
        module = importlib.import_module("apps.pdf_merge_engine.src.main")
        run_merge = getattr(module, "run_merge", None)
        if callable(run_merge):
            result = run_merge(
                pdf_path=pdf_path,
                overlay_config_path=overlay_config_path,
                form_data_path=form_data_path,
                output_path=output_path,
            )
            return Path(result or output_path)
    except ModuleNotFoundError as exc:
        raise RuntimeError(f"pdf_merge_engine 모듈 import 실패: {exc}") from exc

    # 2) Backward-compatible subprocess contract
    engine_main = settings.apps_dir / "pdf_merge_engine" / "src" / "main.py"
    if engine_main.exists():
        cmd = [
            sys.executable,
            str(engine_main),
            "--pdf", str(pdf_path),
            "--overlay-config", str(overlay_config_path),
            "--form-data", str(form_data_path),
            "--output", str(output_path),
        ]
        completed = subprocess.run(
            cmd,
            cwd=str(settings.pdf_engine_dir),
            capture_output=True,
            text=True,
        )
        if completed.returncode == 0 and output_path.exists():
            return output_path
        raise RuntimeError(
            "pdf_merge_engine 실행 실패.\n"
            f"STDOUT: {completed.stdout}\nSTDERR: {completed.stderr}"
        )

    # 3) Temporary fallback for API scaffolding test only
    shutil.copyfile(pdf_path, output_path)
    return output_path
