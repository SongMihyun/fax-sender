"""Page-relative placement for scanned consent forms.

Coordinates in this template are authored against the original Letter-size
form. Some
scanners keep the A4 PDF size but shift or slightly scale the printed form
inside that page.  The Heungkuk form contains four black corner registration
marks, so use them when present to map template coordinates to the actual
printed content.  The same mapping is applied to OCR regions and overlays.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import tempfile
from typing import Any

import cv2
import fitz
import numpy as np

from backend.core.settings import settings


REFERENCE_TEMPLATE_WIDTH = 612.0
REFERENCE_TEMPLATE_HEIGHT = 792.0
# Centres of the four black registration marks in the original Letter-size
# Heungkuk sheet. They are deliberately page-relative rather than
# screen-pixel based. A4 printer output is a scaled instance of this form.
REFERENCE_MARKERS = np.float32(
    [
        [27.75, 15.25],
        [580.5, 15.25],
        [27.75, 724.5],
        [580.5, 724.5],
    ]
)


def normalize_pdf_to_template_page(pdf_path: Path) -> Path:
    """Copy every source page onto the fixed Letter-sized template canvas.

    The coordinate editor for this form was authored on a 612 x 792 point
    Letter PDF.  PDFs that look identical can nevertheless be stored as A4,
    Letter, or a scanner-specific page size.  Performing OCR and drawing on a
    single normalized canvas removes that page-size ambiguity completely.
    """
    settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        prefix="faxsender_normalized_", suffix=".pdf", delete=False, dir=settings.tmp_dir
    )
    normalized_path = Path(handle.name)
    handle.close()

    source = fitz.open(pdf_path)
    normalized = fitz.open()
    try:
        for page_number in range(source.page_count):
            source_page = source[page_number]
            page = normalized.new_page(
                width=REFERENCE_TEMPLATE_WIDTH, height=REFERENCE_TEMPLATE_HEIGHT
            )
            image = _normalized_page_image(source_page)
            encoded, png = cv2.imencode(".png", image)
            if not encoded:
                raise RuntimeError("Unable to encode normalized PDF page")
            page.insert_image(page.rect, stream=png.tobytes())
        normalized.save(normalized_path, garbage=4, deflate=True)
    except Exception:
        normalized_path.unlink(missing_ok=True)
        raise
    finally:
        normalized.close()
        source.close()
    return normalized_path


def _normalized_page_image(source_page: fitz.Page) -> np.ndarray:
    """Rasterize and register a page on the canonical template canvas."""
    render_scale = 3.0
    pixmap = source_page.get_pixmap(
        matrix=fitz.Matrix(render_scale, render_scale), colorspace=fitz.csRGB, alpha=False
    )
    image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, 3)
    target_size = (
        round(REFERENCE_TEMPLATE_WIDTH * render_scale),
        round(REFERENCE_TEMPLATE_HEIGHT * render_scale),
    )
    reference_to_source = _registration_matrix(source_page)
    if reference_to_source is None:
        # Some PDFs do not expose usable registration marks. They still get a
        # deterministic Letter canvas instead of leaking their original A4 /
        # scanner dimensions into the following OCR and overlay steps.
        return cv2.resize(image, target_size, interpolation=cv2.INTER_CUBIC)

    source_to_reference = cv2.invertAffineTransform(reference_to_source)
    source_to_reference[0, :] *= REFERENCE_TEMPLATE_WIDTH / source_page.rect.width
    source_to_reference[1, :] *= REFERENCE_TEMPLATE_HEIGHT / source_page.rect.height
    return cv2.warpAffine(
        image,
        source_to_reference,
        target_size,
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )


def align_positions_to_document(pdf_path: Path, positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return page-scaled, registration-aligned copies of template positions."""
    if not positions:
        return []

    by_page: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for position in positions:
        by_page[int(position.get("page", 1))].append(position)

    aligned: dict[int, list[dict[str, Any]]] = {}
    document = fitz.open(pdf_path)
    try:
        for page_number, page_positions in by_page.items():
            if not 1 <= page_number <= document.page_count:
                aligned[page_number] = [dict(position) for position in page_positions]
                continue
            page = document[page_number - 1]
            matrix = _registration_matrix(page)
            aligned[page_number] = [_transform_position(position, page.rect, matrix) for position in page_positions]
    finally:
        document.close()

    return [aligned[int(position.get("page", 1))].pop(0) for position in positions]


def _transform_position(position: dict[str, Any], page_rect: fitz.Rect, matrix: np.ndarray | None) -> dict[str, Any]:
    result = dict(position)
    scale_x = page_rect.width / REFERENCE_TEMPLATE_WIDTH
    scale_y = page_rect.height / REFERENCE_TEMPLATE_HEIGHT
    x = float(position["x"]) * scale_x
    y = float(position["y"]) * scale_y
    width = float(position["width"]) * scale_x
    height = float(position["height"]) * scale_y

    if matrix is not None:
        point = np.float32([[[x, y]]])
        mapped = cv2.transform(point, matrix)[0][0]
        # Keep the overlay axis-aligned, but preserve independent horizontal
        # and vertical scanner scaling when an A4 page was stretched slightly.
        scale_x = float(np.hypot(matrix[0, 0], matrix[1, 0]))
        scale_y = float(np.hypot(matrix[0, 1], matrix[1, 1]))
        x, y = float(mapped[0]), float(mapped[1])
        width *= scale_x
        height *= scale_y

    result.update({"x": round(x, 3), "y": round(y, 3), "width": round(width, 3), "height": round(height, 3)})
    return result


def _registration_matrix(page: fitz.Page) -> np.ndarray | None:
    """Find corner markers and return a conservative A4-to-content transform."""
    render_scale = 2.0
    pixmap = page.get_pixmap(matrix=fitz.Matrix(render_scale, render_scale), colorspace=fitz.csGRAY, alpha=False)
    image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width)
    mask = (image < 35).astype(np.uint8)
    component_count, _labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)

    candidates: list[tuple[float, float]] = []
    for index in range(1, component_count):
        x, y, width, height, area = (int(value) for value in stats[index])
        if not (120 <= area <= 1000 and 10 <= width <= 45 and 10 <= height <= 45):
            continue
        ratio = width / max(height, 1)
        if not 0.55 <= ratio <= 1.8:
            continue
        centre_x, centre_y = centroids[index]
        candidates.append((float(centre_x) / render_scale, float(centre_y) / render_scale))

    expected = REFERENCE_MARKERS.copy()
    expected[:, 0] *= page.rect.width / REFERENCE_TEMPLATE_WIDTH
    expected[:, 1] *= page.rect.height / REFERENCE_TEMPLATE_HEIGHT
    detected: list[tuple[float, float]] = []
    maximum_distance = min(page.rect.width, page.rect.height) * 0.12
    for expected_x, expected_y in expected:
        options = sorted(candidates, key=lambda item: (item[0] - expected_x) ** 2 + (item[1] - expected_y) ** 2)
        if not options:
            return None
        closest = options[0]
        if np.hypot(closest[0] - expected_x, closest[1] - expected_y) > maximum_distance:
            return None
        detected.append(closest)

    transform, _inliers = cv2.estimateAffine2D(expected, np.float32(detected), method=cv2.LMEDS)
    if transform is None:
        return None
    scale_x = float(np.hypot(transform[0, 0], transform[1, 0]))
    scale_y = float(np.hypot(transform[0, 1], transform[1, 1]))
    rotation_degrees = abs(float(np.degrees(np.arctan2(transform[1, 0], transform[0, 0]))))
    translation = float(np.hypot(transform[0, 2], transform[1, 2]))
    # Reject accidental matches against logos/text. Falling back to direct A4
    # scaling is safer than applying a large, surprising displacement.
    if not (0.92 <= scale_x <= 1.08 and 0.92 <= scale_y <= 1.08 and rotation_degrees <= 3.0 and translation <= 50.0):
        return None
    return transform
