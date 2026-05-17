import shutil
from pathlib import Path

from fastapi import HTTPException

from backend.services.ozd_converter import convert_ozd_to_pdf


def normalize_to_pdf(input_path: str | Path, output_dir: str | Path) -> Path:
    """Return a PDF path for supported input files.

    PDF files are copied into the normalized directory. OZD files are converted
    to PDF first, then the rest of the pipeline can reuse the existing PDF flow.
    """
    source = Path(input_path)
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    suffix = source.suffix.lower()
    if suffix == ".pdf":
        target = target_dir / source.with_suffix(".pdf").name
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        return target

    if suffix == ".ozd":
        target = target_dir / source.with_suffix(".pdf").name
        return convert_ozd_to_pdf(source, target)

    raise HTTPException(status_code=400, detail="UNSUPPORTED_FILE_TYPE: PDF 또는 OZD 파일만 업로드할 수 있습니다.")
