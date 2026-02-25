import os
from io import BytesIO

import fitz
import pytesseract
from PIL import Image


def ocr_image_bytes(payload: bytes) -> str:
    image = Image.open(BytesIO(payload))
    configured_cmd = os.getenv("TESSERACT_CMD", "").strip()
    if configured_cmd:
        pytesseract.pytesseract.tesseract_cmd = configured_cmd

    return pytesseract.image_to_string(image)


def ocr_pdf_bytes(payload: bytes) -> str:
    document = fitz.open(stream=payload, filetype="pdf")
    page_texts: list[str] = []

    for page in document:
        pixmap = page.get_pixmap(dpi=200)
        png_bytes = pixmap.tobytes("png")
        text = ocr_image_bytes(png_bytes)
        if text.strip():
            page_texts.append(text)

    return "\n".join(page_texts)
