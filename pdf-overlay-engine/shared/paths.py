# shared/paths.py

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CONFIG_PATH = PROJECT_ROOT / "configs" / "overlay_config.json"

MP4_ROOT = PROJECT_ROOT / "apps" / "pdf_merge_engine"
INPUT_DIR = MP4_ROOT / "input"

ORIGINAL_PDF_PATH = INPUT_DIR / "original.pdf"
FORM_DATA_PATH = INPUT_DIR / "form_data.json"
SIGNATURE_PATH = INPUT_DIR / "signature.png"
CHECK_IMAGE_PATH = INPUT_DIR / "check.png"

OUTPUT_PATH = PROJECT_ROOT.parent / "storage" / "final" / "final_output.pdf"
