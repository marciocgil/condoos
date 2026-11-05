"""Document -> text. Docling (MIT) when installed, pypdfium2 (Apache-2.0/BSD) otherwise.

Docling handles scanned PDFs and photos (OCR) and keeps tables; pypdfium2 only reads the
text layer of born-digital PDFs. Images without Docling yield no text: they go to the model
as images, or to the human queue when the model is unavailable.
"""

import io
import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

from app.config import get_settings
from app.ingestion.filetypes import IMAGE_TYPES, PDF

logger = logging.getLogger(__name__)

MIN_CHARS_PER_PAGE = 80


@dataclass(frozen=True)
class Converted:
    text: str
    page_count: int
    engine: Literal["docling", "pdfium", "none"]

    @property
    def quality(self) -> Literal["good", "poor", "none"]:
        useful = sum(ch.isalnum() for ch in self.text)
        if useful == 0:
            return "none"
        return "good" if useful >= MIN_CHARS_PER_PAGE * max(1, self.page_count) else "poor"


@lru_cache
def docling_available() -> bool:
    try:
        import docling.document_converter  # noqa: F401
    except ImportError:
        return False
    return True


@lru_cache
def _docling_converter() -> Any:
    from docling.document_converter import DocumentConverter

    return DocumentConverter()


def _with_docling(data: bytes, mime: str, filename: str) -> Converted:
    from docling.datamodel.base_models import DocumentStream

    result = _docling_converter().convert(DocumentStream(name=filename, stream=io.BytesIO(data)))
    document = result.document
    text = document.export_to_markdown()
    pages = getattr(document, "pages", None)
    page_count = len(pages) if pages else 1
    return Converted(text=text, page_count=page_count, engine="docling")


def _with_pdfium(data: bytes) -> Converted:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(data)
    try:
        texts = []
        for page in pdf:
            textpage = page.get_textpage()
            texts.append(textpage.get_text_range())
            textpage.close()
            page.close()
        return Converted(text="\n\f\n".join(texts), page_count=len(texts), engine="pdfium")
    finally:
        pdf.close()


def convert(data: bytes, mime: str, filename: str) -> Converted:
    choice = get_settings().document_converter
    use_docling = choice == "docling" or (choice == "auto" and docling_available())
    if mime not in (PDF, *IMAGE_TYPES):
        return Converted(text="", page_count=0, engine="none")
    if use_docling:
        try:
            return _with_docling(data, mime, filename)
        except Exception:
            logger.exception("docling conversion failed; falling back")
    if mime == PDF:
        try:
            return _with_pdfium(data)
        except Exception:
            logger.warning("pdf text extraction failed")
    return Converted(text="", page_count=1, engine="none")
