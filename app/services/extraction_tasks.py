from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException

from app.core.config import settings
from app.models.schemas import TranscriptSchema
from app.services.document_pipeline import normalize_text, prepare_document_text
from app.services.llm_extractor import extract_structured_transcript
from app.services.transcript_builder import build_transcript


@dataclass
class ExtractionTask:
    task_id: str
    owner: str
    status: str = "queued"
    message: str = "Task queued."
    result: Optional[TranscriptSchema] = None
    error: Optional[str] = None


_TASKS: dict[str, ExtractionTask] = {}
_TASKS_LOCK = threading.Lock()


def create_task(owner: str) -> ExtractionTask:
    task = ExtractionTask(task_id=secrets.token_hex(16), owner=owner)
    with _TASKS_LOCK:
        _TASKS[task.task_id] = task
    return task


def get_task(task_id: str, owner: str) -> ExtractionTask:
    with _TASKS_LOCK:
        task = _TASKS.get(task_id)
    if task is None or task.owner != owner:
        raise HTTPException(status_code=404, detail="Extraction task not found.")
    return task


def _update_task(task_id: str, **changes) -> None:
    with _TASKS_LOCK:
        task = _TASKS[task_id]
        for key, value in changes.items():
            setattr(task, key, value)


def _run_task(
    *,
    task_id: str,
    owner: str,
    filename: str,
    content_type: str,
    suffix: str,
    content: bytes,
    ocr_settings,
) -> None:
    try:
        _update_task(task_id, status="running", message="Extracting document text and preparing OCR fallback...")
        prepared = prepare_document_text(content, suffix, ocr_settings)
        text_content = normalize_text(prepared.text_content)
        if not text_content:
            raise ValueError("No usable text could be extracted from the file. For scanned PDFs, enable OCR and install Tesseract.")
        if len(text_content) > settings.max_text_chars:
            raise ValueError(f"Extracted text is too long for the current model limit ({settings.max_text_chars} characters).")

        _update_task(task_id, message=f"Calling fixed model `{settings.llm_model}` for structured extraction...")
        extraction = extract_structured_transcript(text_content, settings.llm_model)
        transcript = build_transcript(
            extraction,
            source_file_name=filename,
            source_file_type=suffix.lstrip(".") or content_type,
            page_count=prepared.page_count,
            extraction_method=prepared.extraction_method,
            ocr_used=prepared.ocr_used,
            additional_warnings=[f"Processed by {owner}.", *prepared.warnings],
        )
        _update_task(task_id, status="completed", message="Extraction completed.", result=transcript)
    except Exception as exc:
        _update_task(task_id, status="failed", message="Extraction failed.", error=str(exc))


def start_extraction_task(
    *,
    owner: str,
    filename: str,
    content_type: str,
    suffix: str,
    content: bytes,
    ocr_settings,
) -> ExtractionTask:
    task = create_task(owner)
    threading.Thread(
        target=_run_task,
        kwargs={
            "task_id": task.task_id,
            "owner": owner,
            "filename": filename,
            "content_type": content_type,
            "suffix": suffix,
            "content": content,
            "ocr_settings": ocr_settings,
        },
        daemon=True,
    ).start()
    return task
