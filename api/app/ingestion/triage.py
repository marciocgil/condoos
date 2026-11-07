"""File triage for every way a file comes in: upload, e-mail and delegated links (ADR-L06,
D95). No signature antivirus (ClamAV is GPL, forbidden here); instead, code with libraries
the product already uses (pypdfium2, Pillow):

- PDF: refused when it carries active content — JavaScript, launch actions, embedded files
  or rich media — found by its names (hex escapes decoded) and by pdfium (JavaScript actions,
  attachments, also inside compressed object streams). A PDF that asks for a password to open
  is refused; one with only usage restrictions (owner password, common in city-hall invoices)
  opens and is accepted. A corrupted PDF is kept: the reading says it could not read it.
- Images: opened with a pixel limit (decompression bombs) and saved again in the same format,
  which drops metadata and anything appended to the file.
- Other accepted types (XML, OFX, CSV, CNAB) are text parsed by code that already refuses
  what it does not expect.
"""

import io
import re

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from PIL import Image

from app.ingestion.filetypes import JPEG, PDF, PNG, WEBP

MAX_PIXELS = 40_000_000  # ~ 7300 x 5500: far above any phone photo of a document
ACTIVE_NAMES = {b"JavaScript", b"JS", b"Launch", b"EmbeddedFile", b"EmbeddedFiles", b"RichMedia"}
_NAME = re.compile(rb"/([A-Za-z0-9#]{2,40})")
_HEX = re.compile(rb"#([0-9A-Fa-f]{2})")
ACTIVE_PDF = (
    "PDF com conteúdo ativo (script, anexo ou ação automática) não é aceito. Envie o PDF "
    "original do emissor, sem anexos, ou uma foto do documento."
)


class Rejected(ValueError):
    """The file is refused; the message (pt-BR) tells the person what to do."""


def _names(data: bytes) -> set[bytes]:
    return {
        _HEX.sub(lambda m: bytes([int(m.group(1), 16)]), m.group(1)) for m in _NAME.finditer(data)
    }


def _pdf(data: bytes) -> bytes:
    if _names(data) & ACTIVE_NAMES:
        raise Rejected(ACTIVE_PDF)
    try:
        doc = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as exc:
        if getattr(exc, "err_code", None) == pdfium_c.FPDF_ERR_PASSWORD:
            raise Rejected(
                "Este PDF pede senha para abrir. Envie o arquivo sem senha ou uma foto do "
                "documento."
            ) from exc
        return data  # unreadable but harmless: the reading will say it could not read it
    try:
        if pdfium_c.FPDFDoc_GetJavaScriptActionCount(doc.raw) > 0 or doc.count_attachments() > 0:
            raise Rejected(ACTIVE_PDF)
    finally:
        doc.close()
    return data


def _image(mime: str, data: bytes) -> bytes:
    try:
        with Image.open(io.BytesIO(data)) as probe:
            width, height = probe.size
        if width * height > MAX_PIXELS:
            raise Rejected("Imagem grande demais. Envie uma foto com resolução menor.")
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            out = io.BytesIO()
            if mime == JPEG:
                rgb = img.convert("RGB") if img.mode not in ("RGB", "L") else img
                rgb.save(out, format="JPEG", quality=95)
            elif mime == PNG:
                img.save(out, format="PNG")
            else:
                img.save(out, format="WEBP", quality=95)
            return out.getvalue()
    except Rejected:
        raise
    except Image.DecompressionBombError as exc:
        raise Rejected("Imagem grande demais. Envie uma foto com resolução menor.") from exc
    except (OSError, ValueError) as exc:
        raise Rejected("Não consegui abrir esta imagem. Envie a foto de novo.") from exc


def triage(mime: str, data: bytes) -> bytes:
    """The bytes to store (an image is saved again), or ``Rejected``."""
    if mime == PDF:
        return _pdf(data)
    if mime in (JPEG, PNG, WEBP):
        return _image(mime, data)
    return data
