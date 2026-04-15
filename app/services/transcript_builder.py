from __future__ import annotations

from typing import Iterable, Optional

from app.models.schemas import TranscriptExtractionSchema, TranscriptSchema, ValidationSummary
from app.services.gpa import calculate_gpa, course_has_data


def dedupe_warnings(warnings: Iterable[str]) -> list[str]:
    seen = set()
    result = []
    for warning in warnings:
        cleaned = warning.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


def build_transcript(
    extraction: TranscriptExtractionSchema,
    *,
    source_file_name: Optional[str],
    source_file_type: Optional[str],
    page_count: Optional[int],
    extraction_method: str,
    ocr_used: bool,
    additional_warnings: Optional[list[str]] = None,
) -> TranscriptSchema:
    normalized_courses = [course for course in extraction.courses if course_has_data(course)]
    gpa_summary, gpa_warnings = calculate_gpa(normalized_courses)

    warnings = list(additional_warnings or [])
    if not extraction.student_info.name:
        warnings.append("Student name is missing and should be reviewed manually.")
    if not extraction.student_info.student_id:
        warnings.append("Student ID is missing and should be reviewed manually.")
    if not extraction.student_info.major:
        warnings.append("Major is missing and should be reviewed manually.")
    if not normalized_courses:
        warnings.append("No courses were extracted. The source file may require manual cleanup or OCR.")
    if len(normalized_courses) < 2:
        warnings.append("Fewer than two modules were extracted. Please verify that the transcript meets the project requirement.")

    warnings.extend(gpa_warnings[:5])

    return TranscriptSchema(
        student_info=extraction.student_info,
        courses=normalized_courses,
        gpa_summary=gpa_summary,
        validation_summary=ValidationSummary(
            source_file_name=source_file_name,
            source_file_type=source_file_type,
            page_count=page_count,
            extraction_method=extraction_method,
            ocr_used=ocr_used,
            warnings=dedupe_warnings(warnings),
        ),
    )
