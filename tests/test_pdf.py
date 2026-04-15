from app.models.schemas import Course, GPASummary, StudentInfo, TranscriptSchema, ValidationSummary
from app.services.pdf_renderer import generate_transcript_pdf


def test_generate_pdf_returns_pdf_bytes():
    transcript = TranscriptSchema(
        student_info=StudentInfo(
            name="Zhang San",
            student_id="2023211234",
            major="Telecommunications Engineering with Management",
            institution="Beijing University of Posts and Telecommunications",
        ),
        courses=[
            Course(code="CS101", title="Signals and Systems", credits=3, grade="A", semester="2024 Fall"),
            Course(code="EE102", title="Probability Theory", credits=2, grade="88", semester="2025 Spring"),
        ],
        gpa_summary=GPASummary(calculated_gpa=3.88, total_credits=5.0, counted_courses=2, skipped_courses=0),
        validation_summary=ValidationSummary(extraction_method="text", ocr_used=False),
    )
    pdf_buffer = generate_transcript_pdf(transcript)
    payload = pdf_buffer.getvalue()
    assert payload.startswith(b"%PDF")
    assert len(payload) > 1000
