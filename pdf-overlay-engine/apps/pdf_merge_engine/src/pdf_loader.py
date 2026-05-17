from pathlib import Path
import fitz


def load_pdf(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"PDF 파일이 없습니다: {path}")

    return fitz.open(path)