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

Memory model (Render free tier, 512 MB — see docs/OCR_MEMORY_REPORT.md):
pages are rendered, pre-processed and handed to OCR ONE AT A TIME via
`iter_preprocessed_pages()`, so at most one full-resolution page exists in
memory. Page count and pixel dimensions are validated before anything
large is allocated, and every PDFium handle is closed deterministically.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger("scas.ocr.preprocessing")

_MAX_DIMENSION = 1600  # px — cap resize so OCR stays within Vol 7.13's <=5s target
_DEFAULT_PDF_DPI = 200
# Hard ceiling on a rendered PDF page's longer edge, independent of DPI.
# A4/Letter/Legal at 200 DPI are ~2200-2800 px and are unaffected; this
# only stops an oversized (e.g. poster/A0) page from rendering to hundreds
# of megabytes before it is downscaled to _MAX_DIMENSION anyway.
_MAX_RENDER_DIMENSION = 4000
_DEFAULT_MAX_PDF_PAGES = 5
_DEFAULT_MAX_IMAGE_PIXELS = 60_000_000
_PDF_EXTENSIONS = {".pdf"}
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


class DocumentError(ValueError):
    """The uploaded document itself cannot be processed (not a server fault)."""

    user_message = "Could not process the uploaded file. Please re-upload a clearer scan or photo."


class UnsupportedDocumentError(DocumentError):
    user_message = "Unsupported file type. Only PDF, JPG and PNG are accepted."


class CorruptDocumentError(DocumentError):
    user_message = (
        "The uploaded file appears to be damaged or is not a valid PDF/JPG/PNG. "
        "Please re-upload the original report."
    )


class DocumentTooLargeError(DocumentError):
    def __init__(self, message: str, user_message: str):
        super().__init__(message)
        self.user_message = user_message


class EmptyDocumentError(DocumentError):
    user_message = "The uploaded PDF has no pages."


def _settings_or_defaults() -> tuple[int, int, int, int]:
    try:
        from app.core.config import get_settings

        s = get_settings()
        return s.ocr_max_pdf_pages, s.ocr_pdf_dpi, s.ocr_max_image_dimension, s.ocr_max_image_pixels
    except Exception:  # pragma: no cover - settings unavailable (standalone scripts)
        return _DEFAULT_MAX_PDF_PAGES, _DEFAULT_PDF_DPI, _MAX_DIMENSION, _DEFAULT_MAX_IMAGE_PIXELS


def _open_pdf(pdf_path: str | Path):
    import pypdfium2 as pdfium  # lazy import: only needed for PDF uploads

    try:
        return pdfium.PdfDocument(str(pdf_path))
    except Exception as exc:  # PdfiumError and friends
        raise CorruptDocumentError(f"Unreadable PDF {pdf_path}: {exc}") from exc


def count_pdf_pages(pdf_path: str | Path) -> int:
    pdf = _open_pdf(pdf_path)
    try:
        return len(pdf)
    finally:
        pdf.close()


def iter_pdf_pages(
    pdf_path: str | Path,
    dpi: int = _DEFAULT_PDF_DPI,
    max_pages: int | None = None,
) -> Iterator[np.ndarray]:
    """
    Renders PDF pages to BGR numpy images (OpenCV convention) ONE AT A
    TIME. The page count is validated before anything is rendered, and
    every PDFium page/bitmap handle is closed before the next page.

    AIB Vol 7.2: "Multi-page PDFs" are a supported input.
    """
    pdf = _open_pdf(pdf_path)
    try:
        page_count = len(pdf)
        if page_count == 0:
            raise EmptyDocumentError(f"PDF {pdf_path} has no pages")
        if max_pages is not None and page_count > max_pages:
            raise DocumentTooLargeError(
                f"PDF {pdf_path} has {page_count} pages (limit {max_pages})",
                f"The PDF has {page_count} pages; at most {max_pages} pages can be processed. "
                "Please upload only the soil report pages.",
            )
        for page_index in range(page_count):
            page = pdf[page_index]
            bitmap = None
            try:
                width_pt, height_pt = page.get_size()
                scale = dpi / 72
                longest_px = max(width_pt, height_pt) * scale
                if longest_px > _MAX_RENDER_DIMENSION:
                    scale = _MAX_RENDER_DIMENSION / max(width_pt, height_pt)
                bitmap = page.render(scale=scale)
                pixels = bitmap.to_numpy()
                # PDFium renders opaque pages as BGR — exactly OpenCV's
                # channel order, so this is pixel-identical to the former
                # to_pil().convert("RGB") -> RGB2BGR round trip without
                # its three extra full-page copies.
                if bitmap.mode == "BGR":
                    image = np.array(pixels, copy=True)
                elif bitmap.mode in ("BGRA", "BGRX"):
                    image = cv2.cvtColor(pixels, cv2.COLOR_BGRA2BGR)
                else:  # pragma: no cover - grayscale/other render modes
                    image = cv2.cvtColor(np.array(bitmap.to_pil().convert("RGB")), cv2.COLOR_RGB2BGR)
                del pixels
            except DocumentError:
                raise
            except Exception as exc:
                raise CorruptDocumentError(f"Could not render page {page_index + 1}: {exc}") from exc
            finally:
                if bitmap is not None:
                    bitmap.close()
                page.close()
            yield image
            del image
    finally:
        pdf.close()


def pdf_to_images(pdf_path: str | Path) -> list[np.ndarray]:
    """Backwards-compatible: renders every page into a list. Prefer
    `iter_pdf_pages`, which never holds more than one page in memory."""
    return list(iter_pdf_pages(pdf_path, dpi=_DEFAULT_PDF_DPI))


def _image_dimensions(path: Path) -> tuple[int, int]:
    """Reads only the image header — no pixel data is decoded."""
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(path) as img:
            return img.size
    except (UnidentifiedImageError, OSError) as exc:
        raise CorruptDocumentError(f"Unreadable image {path}: {exc}") from exc


def load_image(path: str | Path, max_pixels: int | None = None) -> np.ndarray:
    """Format detection + load (Vol 7.4 step 1)."""
    path = Path(path)
    width, height = _image_dimensions(path)
    if max_pixels is not None and width * height > max_pixels:
        raise DocumentTooLargeError(
            f"Image {path} is {width}x{height} ({width * height} px, limit {max_pixels})",
            "The photo's resolution is too high to process. Please upload a smaller photo "
            "(for example, a normal phone camera photo or a scan at 300 DPI or less).",
        )
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise CorruptDocumentError(f"Could not read image file: {path}")
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


def preprocess(image: np.ndarray, max_dimension: int = _MAX_DIMENSION) -> np.ndarray:
    """
    Runs the full Vol 7.4 pipeline in order. Rotation correction (step 8)
    is folded into `deskew`, since minimum-area-rectangle skew detection
    inherently handles small rotational offsets; large (90/180-degree)
    orientation correction is a layout-analysis-stage concern (Vol 7.3)
    handled downstream by the OCR engine's own orientation classifier.
    """
    result = resize_if_needed(image, max_dimension)
    result = crop_borders(result)
    result = deskew(result)
    result = denoise(result)
    result = enhance_contrast(result)
    result = adaptive_threshold(result)
    return result


def iter_preprocessed_pages(path: str | Path) -> Iterator[np.ndarray]:
    """
    Yields OCR-ready images one page at a time (image -> 1 page; PDF -> up
    to OCR_MAX_PDF_PAGES pages). Callers should OCR each page and drop it
    before advancing, so only one page is ever resident.
    """
    path = Path(path)
    max_pages, dpi, max_dimension, max_pixels = _settings_or_defaults()
    suffix = path.suffix.lower()
    if suffix in _PDF_EXTENSIONS:
        for page in iter_pdf_pages(path, dpi=dpi, max_pages=max_pages):
            processed = preprocess(page, max_dimension)
            del page
            yield processed
            del processed
    elif suffix in _IMAGE_EXTENSIONS:
        image = load_image(path, max_pixels=max_pixels)
        processed = preprocess(image, max_dimension)
        del image
        yield processed
    else:
        raise UnsupportedDocumentError(f"Unsupported document type: {suffix or '(none)'}")


def preprocess_file(path: str | Path) -> list[np.ndarray]:
    """
    Preprocesses an uploaded file (image or PDF) into one or more
    OCR-ready image arrays. PDFs may have multiple pages (Vol 7.2).

    Backwards-compatible list form; the OCR service uses
    `iter_preprocessed_pages` so pages are never all held at once.
    """
    return list(iter_preprocessed_pages(path))
