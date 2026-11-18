"""
Pre-processing input handling, limits and memory behaviour
(docs/OCR_MEMORY_REPORT.md): sequential page rendering, page/pixel limits
validated before allocation, safe rejection of corrupt/unsupported files,
and deterministic release of PDFium handles.
"""

from pathlib import Path

import cv2
import numpy as np
import pypdfium2 as pdfium
import pytest

from app.ocr import preprocessing
from tests.conftest import KARNATAKA_SHC_PDF_PATH


def _make_pdf(path: Path, pages: int, size=(595, 842)) -> Path:
    pdf = pdfium.PdfDocument.new()
    for _ in range(pages):
        pdf.new_page(*size)
    pdf.save(str(path))
    pdf.close()
    return path


def _make_image(path: Path, size=(1200, 900)) -> Path:
    img = np.full((size[1], size[0], 3), 255, np.uint8)
    cv2.putText(img, "pH 6.5", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 0, 0), 5)
    assert cv2.imwrite(str(path), img)
    return path


@pytest.mark.parametrize("suffix", [".png", ".jpg", ".jpeg"])
def test_images_yield_one_preprocessed_page(tmp_path, suffix):
    path = _make_image(tmp_path / f"report{suffix}", size=(3000, 2000))
    pages = list(preprocessing.iter_preprocessed_pages(path))
    assert len(pages) == 1
    assert pages[0].ndim == 3 and pages[0].shape[2] == 3
    assert max(pages[0].shape[:2]) <= 1600


def test_single_and_multi_page_pdfs(tmp_path):
    assert len(list(preprocessing.iter_preprocessed_pages(_make_pdf(tmp_path / "one.pdf", 1)))) == 1
    assert len(list(preprocessing.iter_preprocessed_pages(_make_pdf(tmp_path / "three.pdf", 3)))) == 3


def test_pdf_at_page_limit_is_accepted(tmp_path):
    path = _make_pdf(tmp_path / "five.pdf", 5)
    assert len(list(preprocessing.iter_preprocessed_pages(path))) == 5


def test_pdf_over_page_limit_is_rejected_before_rendering(tmp_path, monkeypatch):
    path = _make_pdf(tmp_path / "six.pdf", 6)
    rendered = []
    original_render = pdfium.PdfPage.render
    monkeypatch.setattr(
        pdfium.PdfPage, "render", lambda self, *a, **k: rendered.append(1) or original_render(self, *a, **k)
    )
    with pytest.raises(preprocessing.DocumentTooLargeError) as exc:
        list(preprocessing.iter_preprocessed_pages(path))
    assert rendered == []
    assert "6 pages" in exc.value.user_message and "5" in exc.value.user_message


def test_corrupted_pdf_is_rejected(tmp_path):
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"%PDF-1.4\nthis is not really a pdf\n")
    with pytest.raises(preprocessing.CorruptDocumentError):
        list(preprocessing.iter_preprocessed_pages(path))


@pytest.mark.parametrize("suffix", [".png", ".jpg"])
def test_corrupted_image_is_rejected(tmp_path, suffix):
    path = tmp_path / f"broken{suffix}"
    path.write_bytes(b"\x89PNG\r\n\x1a\n garbage garbage garbage")
    with pytest.raises(preprocessing.CorruptDocumentError):
        list(preprocessing.iter_preprocessed_pages(path))


def test_unsupported_extension_is_rejected(tmp_path):
    path = tmp_path / "report.txt"
    path.write_text("pH 6.5")
    with pytest.raises(preprocessing.UnsupportedDocumentError):
        list(preprocessing.iter_preprocessed_pages(path))


def test_oversized_image_rejected_from_header_without_decoding(tmp_path, monkeypatch):
    path = _make_image(tmp_path / "huge.png", size=(2000, 1500))
    monkeypatch.setattr(cv2, "imread", lambda *a, **k: pytest.fail("pixels must not be decoded"))
    with pytest.raises(preprocessing.DocumentTooLargeError):
        preprocessing.load_image(path, max_pixels=1_000_000)


def test_pdf_pages_are_rendered_one_at_a_time(tmp_path, monkeypatch):
    """Sequential processing: page N+1 is not rendered until page N has
    been handed to the consumer."""
    path = _make_pdf(tmp_path / "four.pdf", 4)
    rendered = []
    original_render = pdfium.PdfPage.render

    def counting_render(self, *args, **kwargs):
        rendered.append(1)
        return original_render(self, *args, **kwargs)

    monkeypatch.setattr(pdfium.PdfPage, "render", counting_render)
    pages = preprocessing.iter_preprocessed_pages(path)
    for expected in range(1, 5):
        next(pages)
        assert len(rendered) == expected
    with pytest.raises(StopIteration):
        next(pages)


def test_pdf_handles_closed_after_full_and_partial_iteration(tmp_path, monkeypatch):
    path = _make_pdf(tmp_path / "three.pdf", 3)
    closed = {"doc": 0, "page": 0, "bitmap": 0}
    for cls, key in ((pdfium.PdfDocument, "doc"), (pdfium.PdfPage, "page"), (pdfium.PdfBitmap, "bitmap")):
        original = cls.close

        def counting_close(self, *a, _orig=original, _key=key, **k):
            closed[_key] += 1
            return _orig(self, *a, **k)

        monkeypatch.setattr(cls, "close", counting_close)

    list(preprocessing.iter_pdf_pages(path))
    assert closed["doc"] >= 1 and closed["page"] >= 3 and closed["bitmap"] >= 3

    closed.update(doc=0, page=0, bitmap=0)
    gen = preprocessing.iter_pdf_pages(path)
    next(gen)
    gen.close()  # consumer stops early (e.g. OCR failed on page 1)
    assert closed["doc"] >= 1 and closed["page"] >= 1


def test_direct_bgr_render_is_pixel_identical_to_previous_pil_path():
    """The memory-saving render path must not change a single pixel."""
    pdf = pdfium.PdfDocument(str(KARNATAKA_SHC_PDF_PATH))
    try:
        page = pdf[0]
        bitmap = page.render(scale=200 / 72)
        legacy = cv2.cvtColor(np.array(bitmap.to_pil().convert("RGB")), cv2.COLOR_RGB2BGR)
        bitmap.close()
        page.close()
    finally:
        pdf.close()
    current = next(preprocessing.iter_pdf_pages(KARNATAKA_SHC_PDF_PATH, dpi=200))
    assert np.array_equal(current, legacy)


def test_preprocess_file_list_api_still_works():
    pages = preprocessing.preprocess_file(KARNATAKA_SHC_PDF_PATH)
    assert len(pages) == 4
