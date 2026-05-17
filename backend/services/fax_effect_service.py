import io
import random
import shutil
import tempfile
from pathlib import Path
from typing import Any

import fitz
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from backend.core.settings import settings


def apply_fax_effect(pdf_path: Path, config: dict[str, Any] | None = None, seed: int | None = None) -> Path:
    config = config or {}
    dpi = int(config.get("dpi", 170))
    contrast = float(config.get("contrast", 1.18))
    brightness = float(config.get("brightness", 1.02))
    noise = int(config.get("noise", 7))
    rotation_range = config.get("rotation", [-0.35, 0.35])
    blur_radius = float(config.get("blur", 0.18))
    rng = random.Random(seed)

    source = fitz.open(pdf_path)
    output = fitz.open()
    zoom = dpi / 72

    for page in source:
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        image = Image.open(io.BytesIO(pix.tobytes("png"))).convert("L")
        image = ImageOps.autocontrast(image)
        image = ImageEnhance.Contrast(image).enhance(contrast)
        image = ImageEnhance.Brightness(image).enhance(brightness)
        if noise > 0:
            arr = np.asarray(image).astype(np.float32)
            arr += rng.normalvariate(0, noise)
            noise_arr = np.random.default_rng(rng.randint(1, 999999)).normal(0, noise, arr.shape)
            arr = np.clip(arr + noise_arr, 0, 255).astype(np.uint8)
            image = Image.fromarray(arr, "L")
        if blur_radius > 0:
            image = image.filter(ImageFilter.GaussianBlur(blur_radius))
        image = image.convert("RGB")
        angle = rng.uniform(float(rotation_range[0]), float(rotation_range[1]))
        image = image.rotate(angle, expand=True, fillcolor=(255, 255, 255), resample=Image.Resampling.BICUBIC)

        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=int(config.get("jpeg_quality", 82)), optimize=True)
        rect = page.rect
        next_page = output.new_page(width=rect.width, height=rect.height)
        next_page.insert_image(rect, stream=buffer.getvalue(), keep_proportion=True)

    settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(prefix="fax_effect_", suffix=".pdf", delete=False, dir=settings.tmp_dir)
    tmp_path = Path(tmp.name)
    tmp.close()
    output.save(tmp_path, garbage=4, deflate=True)
    output.close()
    source.close()
    shutil.move(str(tmp_path), str(pdf_path))
    return pdf_path
