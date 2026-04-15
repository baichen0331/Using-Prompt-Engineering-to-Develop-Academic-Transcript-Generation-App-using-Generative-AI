from __future__ import annotations

import io
import re
import time
from dataclasses import dataclass
from typing import Optional

import pdfplumber

from app.core.config import settings


@dataclass(frozen=True)
class OCRSettings:
    enabled: bool
    language: str
    dpi: int
    max_pages: int
    page_timeout: float
    total_timeout: float


@dataclass(frozen=True)
class DocumentLoadResult:
    text_content: str
    page_count: Optional[int]
    extraction_method: str
    ocr_used: bool
    warnings: list[str]


def normalize_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def sanitize_transcript_text(text: str) -> tuple[str, list[str]]:
    warnings = []
    if not text:
        return "", warnings

    working = text.replace("\ufeff", "")
    note_markers = ("说明:", "备注:", "Remarks:", "Notes:", "璇存槑:")
    for marker in note_markers:
        if marker in working:
            working = working.split(marker, 1)[0].strip()
            warnings.append("Removed the explanatory notes section before sending content to the model.")
            break

    repeated_header_patterns = (
        r"^page\s*\d+\s*/\s*\d+$",
        r"^第\s*\d+\s*页\s*/\s*共\s*\d+\s*页$",
        r"^课程.*学分.*成绩.*学期.*$",
        r"^course.*credit.*grade.*semester.*$",
    )

    lines = []
    removed_headers = 0
    for raw_line in working.splitlines():
        line = normalize_text(raw_line)
        if not line:
            continue
        if line.casefold() in {"photo", "照片", "鐓х墖"}:
            continue
        if any(re.match(pattern, line, re.IGNORECASE) for pattern in repeated_header_patterns):
            removed_headers += 1
            continue
        lines.append(line)

    if removed_headers:
        warnings.append(f"Removed {removed_headers} repeated course header row(s) before model extraction.")

    return normalize_text("\n".join(lines)), warnings


def decode_text_content(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="ignore")


def load_ocr_backends():
    try:
        import pytesseract
        import pypdfium2 as pdfium
    except ImportError as exc:
        return None, None, [f"OCR dependencies are unavailable: {exc}"]

    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
    return pytesseract, pdfium, []


def resolve_ocr_settings(
    *,
    enabled_override: Optional[bool] = None,
    language_override: Optional[str] = None,
    dpi_override: Optional[int] = None,
    max_pages_override: Optional[int] = None,
    page_timeout_override: Optional[float] = None,
    total_timeout_override: Optional[float] = None,
) -> OCRSettings:
    return OCRSettings(
        enabled=settings.ocr_enabled if enabled_override is None else enabled_override,
        language=(language_override or settings.ocr_language).strip(),
        dpi=max(72, min(dpi_override or settings.ocr_dpi, 400)),
        max_pages=max(1, min(max_pages_override or settings.ocr_max_pages, 50)),
        page_timeout=max(1.0, min(page_timeout_override or settings.ocr_page_timeout_seconds, 60.0)),
        total_timeout=max(5.0, min(total_timeout_override or settings.ocr_total_timeout_seconds, 300.0)),
    )


def extract_pdf_content(content: bytes, ocr_settings: OCRSettings) -> tuple[str, int, str, bool, list[str]]:
    warnings = []
    extracted_pages: list[str] = []

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        raw_pages = [normalize_text(page.extract_text() or "") for page in pdf.pages]

    page_count = len(raw_pages)
    pages_with_text_layer = sum(1 for page_text in raw_pages if page_text)

    pytesseract = None
    pdfium = None
    pdfium_doc = None
    ocr_attempted = 0
    ocr_succeeded = 0
    empty_ocr_pages = 0
    total_start = time.monotonic()
    ocr_available = ocr_settings.enabled

    if ocr_available:
        pytesseract, pdfium, ocr_import_warnings = load_ocr_backends()
        warnings.extend(ocr_import_warnings)
        ocr_available = pytesseract is not None and pdfium is not None
        if ocr_available:
            try:
                pdfium_doc = pdfium.PdfDocument(content)
            except Exception as exc:
                warnings.append(f"Failed to initialize OCR document renderer: {exc}")
                ocr_available = False

    try:
        for page_index, page_text in enumerate(raw_pages, start=1):
            if page_text:
                extracted_pages.append(page_text)
                continue

            if not ocr_available:
                continue

            if ocr_attempted >= ocr_settings.max_pages:
                warnings.append(f"OCR page limit reached after {ocr_settings.max_pages} pages; remaining image-only pages were skipped.")
                break

            elapsed = time.monotonic() - total_start
            remaining_total = ocr_settings.total_timeout - elapsed
            if remaining_total <= 0:
                warnings.append(f"OCR total timeout reached after {round(elapsed, 1)} seconds; remaining image-only pages were skipped.")
                break

            ocr_attempted += 1
            per_page_timeout = max(1.0, min(ocr_settings.page_timeout, remaining_total))

            try:
                page = pdfium_doc[page_index - 1]
                bitmap = page.render(scale=ocr_settings.dpi / 72)
                page_image = bitmap.to_pil()
                ocr_text = pytesseract.image_to_string(
                    page_image,
                    lang=ocr_settings.language,
                    timeout=per_page_timeout,
                ) or ""
                ocr_text = normalize_text(ocr_text)
            except RuntimeError:
                warnings.append(f"OCR timed out on page {page_index} after {round(per_page_timeout, 1)} seconds.")
                continue
            except Exception as exc:
                warnings.append(f"OCR failed on page {page_index}: {exc}")
                continue

            if ocr_text:
                extracted_pages.append(ocr_text)
                ocr_succeeded += 1
            else:
                empty_ocr_pages += 1
                if empty_ocr_pages <= settings.ocr_empty_page_warning_limit:
                    warnings.append(f"OCR found no readable text on page {page_index}.")
    finally:
        if pdfium_doc is not None:
            pdfium_doc.close()

    if pages_with_text_layer > 0 and ocr_succeeded > 0:
        extraction_method = "mixed"
    elif ocr_succeeded > 0:
        extraction_method = "ocr"
    else:
        extraction_method = "text"

    if ocr_attempted > 0:
        warnings.append(
            f"OCR attempted on {ocr_attempted} page(s), succeeded on {ocr_succeeded}, language pack `{ocr_settings.language}`."
        )

    combined = "\n\n".join(extracted_pages).strip()
    sanitized, sanitize_warnings = sanitize_transcript_text(combined)
    warnings.extend(sanitize_warnings)
    return sanitized, page_count, extraction_method, ocr_succeeded > 0, warnings


def prepare_document_text(content: bytes, extension: str, ocr_settings: OCRSettings) -> DocumentLoadResult:
    if extension == ".pdf":
        text_content, page_count, extraction_method, ocr_used, warnings = extract_pdf_content(content, ocr_settings)
        return DocumentLoadResult(text_content, page_count, extraction_method, ocr_used, warnings)

    text_content = decode_text_content(content)
    sanitized, warnings = sanitize_transcript_text(text_content)
    return DocumentLoadResult(sanitized, None, "text", False, warnings)
