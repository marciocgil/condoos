"""File type detection from content (never trust the extension alone)."""

from app.ingestion.bank.cnab.common import looks_like_cnab
from app.ingestion.bank.ofx import looks_like_ofx

PDF = "application/pdf"
JPEG = "image/jpeg"
PNG = "image/png"
WEBP = "image/webp"
XML = "application/xml"
OFX = "application/x-ofx"
CNAB = "text/x-cnab"
CSV = "text/csv"
EML = "message/rfc822"

IMAGE_TYPES = (JPEG, PNG, WEBP)


class UnsupportedFile(ValueError):
    """Message is shown to the user (pt-BR)."""


def sniff(filename: str, data: bytes) -> str:
    head = data[:16]
    if head.startswith(b"%PDF"):
        return PDF
    if head.startswith(b"\xff\xd8\xff"):
        return JPEG
    if head.startswith(b"\x89PNG"):
        return PNG
    if head[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return WEBP
    name = filename.lower()
    if name.endswith((".heic", ".heif")) or data[4:12] in (b"ftypheic", b"ftypheix", b"ftypmif1"):
        raise UnsupportedFile(
            "Fotos HEIC do iPhone ainda não são aceitas. Envie em JPEG (Ajustes > Câmera > "
            "Formatos > Mais Compatível)."
        )
    if looks_like_cnab(data):
        return CNAB
    if looks_like_ofx(data):
        return OFX
    text_head = data[:400].lstrip(b"\xef\xbb\xbf \r\n\t")
    if text_head.startswith(b"<?xml") or text_head.startswith(b"<"):
        return XML
    if name.endswith(".csv"):
        return CSV
    raise UnsupportedFile(
        "Tipo de arquivo não aceito. Envie PDF, foto (JPEG/PNG), XML de nota fiscal, "
        "extrato OFX/CSV ou retorno CNAB."
    )
