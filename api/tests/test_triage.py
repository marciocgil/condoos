"""File triage (ADR-L06, D95): active PDF content and image payloads never get in, through
any channel; ordinary documents pass unchanged."""

import io
import struct
import zlib
from pathlib import Path

import pypdfium2 as pdfium
import pytest
from PIL import Image
from reportlab.lib.pdfencrypt import StandardEncryption
from reportlab.pdfgen.canvas import Canvas

from app.ingestion.filetypes import JPEG, PDF, PNG
from app.ingestion.triage import Rejected, triage

CORPUS = Path(__file__).parent / "fixtures" / "corpus"


def _pdf(extra: bytes = b"", encrypt: StandardEncryption | None = None) -> bytes:
    buf = io.BytesIO()
    c = Canvas(buf, encrypt=encrypt)
    c.drawString(72, 720, "Nota fiscal fictícia")
    c.showPage()
    c.save()
    data = buf.getvalue()
    return data.replace(b"%%EOF", extra + b"\n%%EOF") if extra else data


def test_ordinary_pdf_passes_unchanged() -> None:
    data = (CORPUS / "01_nfse.pdf").read_bytes()
    assert triage(PDF, data) == data


@pytest.mark.parametrize(
    "extra",
    [
        b"4 0 obj << /S /JavaScript /JS (app.alert(1)) >> endobj",
        b"5 0 obj << /Type /Action /S /J#61vaScript >> endobj",  # hex-escaped name
        b"6 0 obj << /S /Launch /F (cmd.exe) >> endobj",
    ],
)
def test_pdf_with_active_content_is_refused(extra: bytes) -> None:
    with pytest.raises(Rejected, match="conteúdo ativo"):
        triage(PDF, _pdf(extra))


def test_pdf_with_an_embedded_file_is_refused() -> None:
    doc = pdfium.PdfDocument(_pdf())
    attachment = doc.new_attachment("planilha.xlsm")
    attachment.set_data(b"conteudo")
    out = io.BytesIO()
    doc.save(out)
    with pytest.raises(Rejected, match="conteúdo ativo"):
        triage(PDF, out.getvalue())


def test_pdf_password_to_open_is_refused_restrictions_only_pass() -> None:
    with pytest.raises(Rejected, match="pede senha"):
        triage(PDF, _pdf(encrypt=StandardEncryption("abrir", ownerPassword="dono")))
    restricted = _pdf(encrypt=StandardEncryption("", ownerPassword="dono", canPrint=0))
    assert triage(PDF, restricted) == restricted  # common in city-hall invoices


def test_corrupted_pdf_is_kept_for_the_reading_to_report() -> None:
    data = b"%PDF-1.4\n% truncated\n"
    assert triage(PDF, data) == data


def test_images_are_saved_again_without_payloads() -> None:
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), (120, 130, 140)).save(buf, format="PNG")
    with_payload = buf.getvalue() + b"<script>alert(1)</script>"
    cleaned = triage(PNG, with_payload)
    assert b"<script>" not in cleaned
    assert Image.open(io.BytesIO(cleaned)).size == (40, 30)

    exif = Image.Exif()
    exif[0x010E] = "descricao com dados pessoais"  # ImageDescription
    jpg = io.BytesIO()
    Image.new("RGB", (20, 20), "white").save(jpg, format="JPEG", exif=exif)
    assert b"dados pessoais" in jpg.getvalue()
    assert b"dados pessoais" not in triage(JPEG, jpg.getvalue())


def _png_header_only(width: int, height: int) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(b"\x00"))
        + chunk(b"IEND", b"")
    )


def test_decompression_bomb_and_broken_images_are_refused() -> None:
    with pytest.raises(Rejected, match="grande demais"):
        triage(PNG, _png_header_only(20_000, 20_000))
    with pytest.raises(Rejected, match="Não consegui abrir"):
        triage(JPEG, b"\xff\xd8\xff\xe0 not really a jpeg")
