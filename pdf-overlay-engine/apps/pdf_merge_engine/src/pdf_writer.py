from pathlib import Path


def save_pdf(doc, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    doc.close()