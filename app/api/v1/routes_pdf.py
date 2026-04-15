from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.security import require_roles
from app.models.schemas import TranscriptExtractionSchema, TranscriptSchema
from app.services.pdf_renderer import generate_transcript_pdf
from app.services.transcript_builder import build_transcript

router = APIRouter(tags=["pdf"])


@router.post("/validate/transcript", response_model=TranscriptSchema)
async def validate_transcript(
    transcript: TranscriptSchema,
    user: dict = Depends(require_roles("admin", "reviewer")),
):
    extraction = TranscriptExtractionSchema(
        student_info=transcript.student_info,
        courses=transcript.courses,
    )
    validation = transcript.validation_summary
    warnings = list(validation.warnings)
    warnings.append(f"Validated by {user['sub']} ({user['role']}).")
    return build_transcript(
        extraction,
        source_file_name=validation.source_file_name,
        source_file_type=validation.source_file_type,
        page_count=validation.page_count,
        extraction_method=validation.extraction_method or "manual",
        ocr_used=validation.ocr_used,
        additional_warnings=warnings,
    )


@router.post("/generate-pdf")
async def create_pdf(
    transcript: TranscriptSchema,
    user: dict = Depends(require_roles("admin", "reviewer")),
):
    canonical_transcript = await validate_transcript(transcript, user)
    pdf_buffer = generate_transcript_pdf(canonical_transcript)
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=transcript.pdf"},
    )
