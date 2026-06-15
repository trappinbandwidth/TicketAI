import base64
import io
import logging

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

# 2x scale = ~144 DPI — good character detail while keeping pages well
# under Claude's 10 MB per-image limit (~3–4 MB for letter-size PDFs).
PDF_RENDER_SCALE = 2.0
MAX_IMAGE_BYTES = 9 * 1024 * 1024  # hard cap: re-render at lower quality if exceeded


def _try_tesseract_ocr(image_bytes: bytes) -> str:
    """Run Tesseract OCR on raw image bytes. Returns empty string if unavailable."""
    try:
        import pytesseract
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        return pytesseract.image_to_string(img, config="--psm 6")
    except Exception as exc:
        logger.debug("Tesseract OCR unavailable or failed: %s", exc)
        return ""


def _enhance_image(image_bytes: bytes) -> bytes:
    """
    Apply contrast normalization to improve Claude's extraction accuracy.
    Saves as JPEG (quality=88) to keep phone-camera photos well under 10 MB.
    Returns original bytes if PIL is unavailable.
    """
    try:
        from PIL import Image, ImageOps
        img = Image.open(io.BytesIO(image_bytes)).convert("L")  # grayscale
        img = ImageOps.autocontrast(img, cutoff=1)              # stretch contrast
        img = img.convert("RGB")

        # Cap longest dimension at 2048px — phone cameras shoot 4K+, which is
        # overkill for text extraction and bloats every API call by 3–5×.
        MAX_DIM = 2048
        w, h = img.size
        if max(w, h) > MAX_DIM:
            scale = MAX_DIM / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            logger.debug("Resized image from %dx%d to %dx%d", w, h, img.size[0], img.size[1])

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        result = buf.getvalue()
        logger.debug("Enhanced image: %d bytes → %d bytes (JPEG)", len(image_bytes), len(result))
        return result
    except Exception as exc:
        logger.debug("Image enhancement unavailable: %s", exc)
        return image_bytes


def pdf_to_images_and_text(file_bytes: bytes) -> tuple[list[str], str]:
    """
    Convert PDF bytes to:
      - list of base64-encoded PNG images (one per page)
      - extracted text (digital PDFs; Tesseract fallback for scanned pages)
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    images_b64 = []
    text_pages = []

    for page in doc:
        mat = fitz.Matrix(PDF_RENDER_SCALE, PDF_RENDER_SCALE)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")

        # If still over the limit, re-render at lower scale with JPEG compression
        if len(img_bytes) > MAX_IMAGE_BYTES:
            logger.warning("Page %d PNG is %d bytes — recompressing as JPEG", page.number, len(img_bytes))
            try:
                from PIL import Image
                img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=85, optimize=True)
                img_bytes = buf.getvalue()
                logger.warning("Page %d recompressed to %d bytes (JPEG)", page.number, len(img_bytes))
            except Exception as exc:
                logger.warning("JPEG recompression failed: %s", exc)

        images_b64.append(base64.standard_b64encode(img_bytes).decode())

        # Prefer embedded text; fall back to Tesseract for scanned pages
        embedded = page.get_text().strip()
        if embedded:
            text_pages.append(embedded)
        else:
            ocr_text = _try_tesseract_ocr(img_bytes)
            text_pages.append(ocr_text)

    doc.close()
    full_text = "\n\n--- PAGE BREAK ---\n\n".join(text_pages).strip()
    return images_b64, full_text


def image_file_to_base64(file_bytes: bytes, media_type: str) -> tuple[list[str], str]:
    """
    Handle direct image uploads (jpg, png).
    Enhances image quality and runs Tesseract OCR to provide Claude
    a text signal alongside the image — mirrors what PDFs already get.
    """
    enhanced = _enhance_image(file_bytes)
    ocr_text = _try_tesseract_ocr(file_bytes)  # OCR on original (pre-enhance) for accuracy
    return [base64.standard_b64encode(enhanced).decode()], ocr_text
