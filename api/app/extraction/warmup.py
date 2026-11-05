"""Download and load Docling models at image build time: python -m app.extraction.warmup

Converts a tiny generated PDF and image so every model used at runtime (layout, tables,
OCR) is in the local cache. The worker then runs with HF_HUB_OFFLINE=1.
"""

import io

from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

from app.extraction.convert import _with_docling


def main() -> None:
    buf = io.BytesIO()
    canvas = Canvas(buf, pagesize=A4)
    canvas.drawString(72, 760, "CondoOS - aquecimento do conversor")
    canvas.showPage()
    canvas.save()
    image = Image.new("RGB", (600, 200), "white")
    ImageDraw.Draw(image).text((20, 80), "CondoOS 123,45", fill="black")
    png = io.BytesIO()
    image.save(png, "PNG")
    for data, mime, name in (
        (buf.getvalue(), "application/pdf", "a.pdf"),
        (png.getvalue(), "image/png", "a.png"),
    ):
        result = _with_docling(data, mime, name)
        print(f"{name}: {len(result.text)} caracteres")


if __name__ == "__main__":
    main()
