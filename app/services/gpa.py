from __future__ import annotations

import re
from typing import Iterable, Optional

from app.models.schemas import Course, GPASummary

GRADE_POINTS = {
    "A+": 4.0,
    "A": 4.0,
    "A-": 3.7,
    "B+": 3.3,
    "B": 3.0,
    "B-": 2.7,
    "C+": 2.3,
    "C": 2.0,
    "C-": 1.7,
    "D+": 1.3,
    "D": 1.0,
    "D-": 0.7,
    "F": 0.0,
}


def parse_numeric_grade(grade_value: float) -> Optional[float]:
    if grade_value < 0:
        return None
    if grade_value >= 90:
        return 4.0
    if grade_value >= 85:
        return 3.7
    if grade_value >= 82:
        return 3.3
    if grade_value >= 78:
        return 3.0
    if grade_value >= 75:
        return 2.7
    if grade_value >= 72:
        return 2.3
    if grade_value >= 68:
        return 2.0
    if grade_value >= 64:
        return 1.5
    if grade_value >= 60:
        return 1.0
    return 0.0


def grade_to_points(grade: Optional[str]) -> Optional[float]:
    if not grade:
        return None
    normalized = str(grade).strip().upper()
    if normalized in {"P", "PASS", "S", "SATISFACTORY"}:
        return None
    if normalized in GRADE_POINTS:
        return GRADE_POINTS[normalized]
    numeric_match = re.search(r"\d+(?:\.\d+)?", normalized)
    if numeric_match:
        return parse_numeric_grade(float(numeric_match.group(0)))
    return None


def course_has_data(course: Course) -> bool:
    return any(
        value not in (None, "")
        for value in (course.code, course.title, course.credits, course.grade, course.semester)
    )


def calculate_gpa(courses: Iterable[Course]) -> tuple[GPASummary, list[str]]:
    total_credits = 0.0
    total_quality_points = 0.0
    counted_courses = 0
    skipped_courses = 0
    warnings = []

    for course in courses:
        if not course_has_data(course):
            continue
        if course.credits is None or course.credits <= 0:
            skipped_courses += 1
            warnings.append(f"Skipped GPA for course '{course.title or course.code or 'Unknown'}' because credits are missing.")
            continue
        grade_points = grade_to_points(course.grade)
        if grade_points is None:
            skipped_courses += 1
            warnings.append(
                f"Skipped GPA for course '{course.title or course.code or 'Unknown'}' because grade '{course.grade or 'N/A'}' is not GPA-countable."
            )
            continue
        total_credits += float(course.credits)
        total_quality_points += grade_points * float(course.credits)
        counted_courses += 1

    calculated_gpa = round(total_quality_points / total_credits, 3) if total_credits > 0 else None
    return (
        GPASummary(
            calculated_gpa=calculated_gpa,
            total_credits=round(total_credits, 2),
            counted_courses=counted_courses,
            skipped_courses=skipped_courses,
        ),
        warnings,
    )
