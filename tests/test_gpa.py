from app.models.schemas import Course
from app.services.gpa import calculate_gpa, grade_to_points


def test_grade_to_points_handles_letter_and_numeric():
    assert grade_to_points("A") == 4.0
    assert grade_to_points("86") == 3.7
    assert grade_to_points("Pass") is None


def test_calculate_gpa_counts_only_countable_courses():
    summary, warnings = calculate_gpa(
        [
            Course(code="A1", title="Math", credits=3, grade="90"),
            Course(code="A2", title="PE", credits=1, grade="Pass"),
            Course(code="A3", title="Physics", credits=2, grade="B+"),
        ]
    )
    assert summary.counted_courses == 2
    assert summary.skipped_courses == 1
    assert summary.total_credits == 5.0
    assert summary.calculated_gpa == 3.72
    assert warnings
