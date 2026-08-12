"""
Image pre-processing pipeline.

AIB v1.0 Vol 7.4:
    1. Format detection
    2. Resize
    3. Deskew
    4. Noise removal
    5. Adaptive thresholding
    6. Contrast enhancement
    7. Border cropping
    8. Rotation correction
    "Pre-processing must occur before OCR."
"""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger("scas.ocr.preprocessing")

_MAX_DIMENSION = 1600  # px — cap resize so OCR stays within Vol 7.13's <=5s target


def pdf_to_images(pdf_path: str | Path) -> list[np.ndarray]:
    """
    Renders every page of a PDF to a BGR numpy image array (OpenCV
    convention), for the OCR/pre-processing steps that follow.

    AIB Vol 7.2: "Multi-page PDFs" are a supported input.
    """
    import pypdfium2 as pdfium  # lazy import: only needed for PDF uploads

    pdf = pdfium.PdfDocument(str(pdf_path))
    images: list[np.ndarray] = []
    try:
        for page_index in range(len(pdf)):
            page = pdf[page_index]
            bitmap = page.render(scale=200 / 72)  # ~200 DPI
            pil_image = bitmap.to_pil().convert("RGB")
            rgb_array = np.array(pil_image)
            images.append(cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR))
    finally:
        pdf.close()
    return images


def load_image(path: str | Path) -> np.ndarray:
    """Format detection + load (Vol 7.4 step 1)."""
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Could not read image file: {path}")
    return image


def resize_if_needed(image: np.ndarray, max_dimension: int = _MAX_DIMENSION) -> np.ndarray:
    """Resize (Vol 7.4 step 2) — caps the longer edge to keep OCR fast."""
    height, width = image.shape[:2]
    longest_edge = max(height, width)
    if longest_edge <= max_dimension:
        return image
    scale = max_dimension / longest_edge
    return cv2.resize(image, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)


def deskew(image: np.ndarray) -> np.ndarray:
    """
    Deskew (Vol 7.4 step 3) via minimum-area-rectangle angle detection
    on thresholded foreground pixels.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thresh > 0))
    if coords.shape[0] < 10:
        return image  # not enough foreground to estimate an angle safely

    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    if abs(angle) < 0.3:
        return image  # negligible skew; avoid needless interpolation blur

    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        image, rotation_matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )


def denoise(image: np.ndarray) -> np.ndarray:
    """
    Noise removal (Vol 7.4 step 4).

    Operates on a single (grayscale) channel via `fastNlMeansDenoising`
    rather than the 3-channel `fastNlMeansDenoisingColored` variant.
    Soil report scans/photos carry no OCR-relevant color information, and
    the colored denoiser is roughly 100x slower per page — using it was
    measured at ~4.5s/page against this dataset, which alone would blow
    the Vol 7.13 <=5s OCR budget before OCR even starts. The grayscale
    path preserves the same noise-reduction quality for text recognition.
    """
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    denoised = cv2.fastNlMeansDenoising(gray, None, h=7, templateWindowSize=7, searchWindowSize=21)
    return cv2.cvtColor(denoised, cv2.COLOR_GRAY2BGR)


def adaptive_threshold(image: np.ndarray) -> np.ndarray:
    """Adaptive thresholding (Vol 7.4 step 5) — returns a 3-channel image
    (OCR engines generally expect BGR/RGB input even for binarized text)."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
    )
    return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)


def enhance_contrast(image: np.ndarray) -> np.ndarray:
    """Contrast enhancement (Vol 7.4 step 6) via CLAHE on the L channel."""
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_enhanced = clahe.apply(l_channel)
    merged = cv2.merge((l_enhanced, a_channel, b_channel))
    return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)


def crop_borders(image: np.ndarray, margin_ratio: float = 0.01) -> np.ndarray:
    """Border cropping (Vol 7.4 step 7) — trims a small uniform margin
    that scanners/phone cameras often add."""
    h, w = image.shape[:2]
    my, mx = int(h * margin_ratio), int(w * margin_ratio)
    if h - 2 * my <= 0 or w - 2 * mx <= 0:
        return image
    return image[my : h - my, mx : w - mx]


def preprocess(image: np.ndarray) -> np.ndarray:
    """
    Runs the full Vol 7.4 pipeline in order. Rotation correction (step 8)
    is folded into `deskew`, since minimum-area-rectangle skew detection
    inherently handles small rotational offsets; large (90/180-degree)
    orientation correction is a layout-analysis-stage concern (Vol 7.3)
    handled downstream by the OCR engine's own orientation classifier.
    """
    result = resize_if_needed(image)
    result = crop_borders(result)
    result = deskew(result)
    result = denoise(result)
    result = enhance_contrast(result)
    result = adaptive_threshold(result)
    return result


def preprocess_file(path: str | Path) -> list[np.ndarray]:
    """
    Preprocesses an uploaded file (image or PDF) into one or more
    OCR-ready image arrays. PDFs may have multiple pages (Vol 7.2).
    """
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        pages = pdf_to_images(path)
        return [preprocess(page) for page in pages]
    return [preprocess(load_image(path))]
