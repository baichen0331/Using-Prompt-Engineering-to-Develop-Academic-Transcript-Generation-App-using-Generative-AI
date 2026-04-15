from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.core.config import settings
from app.core.security import require_roles
from app.models.schemas import ExtractionJobCreated, ExtractionJobStatus, OCRPreviewResponse, TranscriptSchema
from app.services.document_pipeline import normalize_text, prepare_document_text, resolve_ocr_settings
from app.services.extraction_tasks import get_task, start_extraction_task
from app.services.llm_extractor import extract_structured_transcript
from app.services.transcript_builder import build_transcript, dedupe_warnings

ALLOWED_EXTENSIONS = {".pdf", ".txt"}
ALLOWED_CONTENT_TYPES = {"application/pdf", "text/plain", "application/octet-stream"}

router = APIRouter(tags=["extract"])


def _resolve_suffix(file: UploadFile) -> str:
    extension = file.filename and file.filename.lower().rsplit(".", 1)
    return f".{extension[-1]}" if extension and len(extension) > 1 else ""


def _validate_upload(file: UploadFile, suffix: str) -> None:
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Only .txt and .pdf files are supported.")
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported content type: {file.content_type}")


@router.post("/preview/ocr", response_model=OCRPreviewResponse)
async def preview_ocr(
    file: UploadFile = File(...),
    ocr_enabled: Optional[bool] = Form(None),
    ocr_language: Optional[str] = Form(None),
    ocr_dpi: Optional[int] = Form(None),
    ocr_max_pages: Optional[int] = Form(None),
    ocr_page_timeout_seconds: Optional[float] = Form(None),
    ocr_total_timeout_seconds: Optional[float] = Form(None),
    preview_chars: int = Form(4000),
    user: dict = Depends(require_roles("admin", "reviewer")),
):
    _ = user
    suffix = _resolve_suffix(file)
    _validate_upload(file, suffix)

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > settings.max_upload_size:
        raise HTTPException(status_code=413, detail=f"File exceeds the {settings.max_upload_mb}MB upload limit.")

    ocr_settings = resolve_ocr_settings(
        enabled_override=ocr_enabled,
        language_override=ocr_language,
        dpi_override=ocr_dpi,
        max_pages_override=ocr_max_pages,
        page_timeout_override=ocr_page_timeout_seconds,
        total_timeout_override=ocr_total_timeout_seconds,
    )
    result = prepare_document_text(content, suffix, ocr_settings)
    text_content = normalize_text(result.text_content)

    return OCRPreviewResponse(
        source_file_name=file.filename,
        page_count=result.page_count,
        extraction_method=result.extraction_method,
        ocr_used=result.ocr_used,
        extracted_characters=len(text_content),
        preview_text=text_content[: max(500, min(preview_chars, 10000))],
        warnings=dedupe_warnings(result.warnings),
        effective_ocr_language=ocr_settings.language,
        effective_ocr_dpi=ocr_settings.dpi,
        effective_ocr_max_pages=ocr_settings.max_pages,
    )


@router.post("/extract/transcript", response_model=TranscriptSchema)
async def extract_transcript(
    file: UploadFile = File(...),
    ocr_enabled: Optional[bool] = Form(None),
    ocr_language: Optional[str] = Form(None),
    ocr_dpi: Optional[int] = Form(None),
    ocr_max_pages: Optional[int] = Form(None),
    ocr_page_timeout_seconds: Optional[float] = Form(None),
    ocr_total_timeout_seconds: Optional[float] = Form(None),
    user: dict = Depends(require_roles("admin", "reviewer")),
):
    suffix = _resolve_suffix(file)
    _validate_upload(file, suffix)

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > settings.max_upload_size:
        raise HTTPException(status_code=413, detail=f"File exceeds the {settings.max_upload_mb}MB upload limit.")

    ocr_settings = resolve_ocr_settings(
        enabled_override=ocr_enabled,
        language_override=ocr_language,
        dpi_override=ocr_dpi,
        max_pages_override=ocr_max_pages,
        page_timeout_override=ocr_page_timeout_seconds,
        total_timeout_override=ocr_total_timeout_seconds,
    )

    warnings = [f"Processed by {user['sub']} ({user['role']})."]
    prepared = prepare_document_text(content, suffix, ocr_settings)
    warnings.extend(prepared.warnings)

    text_content = normalize_text(prepared.text_content)
    if not text_content:
        raise HTTPException(
            status_code=400,
            detail="No usable text could be extracted from the file. For scanned PDFs, enable OCR and install Tesseract.",
        )
    if len(text_content) > settings.max_text_chars:
        raise HTTPException(
            status_code=413,
            detail=f"Extracted text is too long for the current model limit ({settings.max_text_chars} characters).",
        )

    try:
        extraction = extract_structured_transcript(text_content, settings.llm_model)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return build_transcript(
        extraction,
        source_file_name=file.filename,
        source_file_type=suffix.lstrip(".") or file.content_type,
        page_count=prepared.page_count,
        extraction_method=prepared.extraction_method,
        ocr_used=prepared.ocr_used,
        additional_warnings=warnings,
    )


@router.post("/extract/transcript/jobs", response_model=ExtractionJobCreated, status_code=202)
async def create_extract_job(
    file: UploadFile = File(...),
    ocr_enabled: Optional[bool] = Form(None),
    ocr_language: Optional[str] = Form(None),
    ocr_dpi: Optional[int] = Form(None),
    ocr_max_pages: Optional[int] = Form(None),
    ocr_page_timeout_seconds: Optional[float] = Form(None),
    ocr_total_timeout_seconds: Optional[float] = Form(None),
    user: dict = Depends(require_roles("admin", "reviewer")),
):
    suffix = _resolve_suffix(file)
    _validate_upload(file, suffix)

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > settings.max_upload_size:
        raise HTTPException(status_code=413, detail=f"File exceeds the {settings.max_upload_mb}MB upload limit.")

    ocr_settings = resolve_ocr_settings(
        enabled_override=ocr_enabled,
        language_override=ocr_language,
        dpi_override=ocr_dpi,
        max_pages_override=ocr_max_pages,
        page_timeout_override=ocr_page_timeout_seconds,
        total_timeout_override=ocr_total_timeout_seconds,
    )
    task = start_extraction_task(
        owner=f"{user['sub']} ({user['role']})",
        filename=file.filename or "uploaded_file",
        content_type=file.content_type or "application/octet-stream",
        suffix=suffix,
        content=content,
        ocr_settings=ocr_settings,
    )
    return ExtractionJobCreated(task_id=task.task_id, status=task.status, model=settings.llm_model)


@router.get("/extract/transcript/jobs/{task_id}", response_model=ExtractionJobStatus)
async def get_extract_job(task_id: str, user: dict = Depends(require_roles("admin", "reviewer"))):
    task = get_task(task_id, f"{user['sub']} ({user['role']})")
    return ExtractionJobStatus(
        task_id=task.task_id,
        status=task.status,
        message=task.message,
        result=task.result,
        error=task.error,
    )
