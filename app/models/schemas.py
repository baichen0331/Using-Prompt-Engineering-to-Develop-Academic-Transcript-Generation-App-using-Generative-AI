from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class AppBaseModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class StudentInfo(AppBaseModel):
    name: Optional[str] = Field(default=None, description="Student's full name")
    student_id: Optional[str] = Field(default=None, description="Student ID number")
    major: Optional[str] = Field(default=None, description="Major or program of study")
    institution: Optional[str] = Field(default=None, description="University or institution name")


class Course(AppBaseModel):
    code: Optional[str] = Field(default=None, description="Course code, e.g., CS101")
    title: Optional[str] = Field(default=None, description="Course title")
    credits: Optional[float] = Field(default=None, description="Number of credits awarded")
    grade: Optional[str] = Field(default=None, description="Letter grade or numeric score")
    semester: Optional[str] = Field(default=None, description="Semester and year, e.g., Fall 2023")


class TranscriptExtractionSchema(AppBaseModel):
    student_info: StudentInfo = Field(default_factory=StudentInfo)
    courses: List[Course] = Field(default_factory=list)


class GPASummary(AppBaseModel):
    calculated_gpa: Optional[float] = Field(default=None, description="Calculated GPA based on a standard 4.0 scale")
    total_credits: float = Field(default=0.0, description="Total credits included in GPA calculation")
    counted_courses: int = Field(default=0, description="Number of courses included in GPA calculation")
    skipped_courses: int = Field(default=0, description="Number of courses skipped during GPA calculation")


class ValidationSummary(AppBaseModel):
    source_file_name: Optional[str] = Field(default=None, description="Uploaded source filename")
    source_file_type: Optional[str] = Field(default=None, description="Uploaded source file type")
    page_count: Optional[int] = Field(default=None, description="Number of pages processed for PDF uploads")
    extraction_method: Optional[str] = Field(default=None, description="text, ocr, or mixed")
    ocr_used: bool = Field(default=False, description="Whether OCR fallback was used for this transcript")
    warnings: List[str] = Field(default_factory=list, description="Validation or review warnings")


class TranscriptSchema(TranscriptExtractionSchema):
    gpa_summary: GPASummary = Field(default_factory=GPASummary)
    validation_summary: ValidationSummary = Field(default_factory=ValidationSummary)


class LoginRequest(AppBaseModel):
    username: str = Field(description="Username used for login")
    password: str = Field(description="Password used for login")


class TokenResponse(AppBaseModel):
    access_token: str = Field(description="Bearer token for API access")
    token_type: str = Field(default="bearer", description="Token type")
    username: str = Field(description="Authenticated username")
    role: str = Field(description="Authenticated role")


class CreateUserRequest(AppBaseModel):
    username: str = Field(description="Username to create")
    password: str = Field(description="Plaintext password that will be hashed before storage")
    role: str = Field(default="reviewer", description="Role for the new user")
    is_active: bool = Field(default=True, description="Whether the user can log in")


class UserSummary(AppBaseModel):
    username: str = Field(description="Username")
    role: str = Field(description="Role")
    is_active: bool = Field(description="Whether the user is active")
    created_at: Optional[str] = Field(default=None, description="Creation timestamp")


class ResetPasswordRequest(AppBaseModel):
    username: str = Field(description="Username whose password will be changed")
    new_password: str = Field(description="New plaintext password")
    current_password: Optional[str] = Field(default=None, description="Current password for self-service changes")


class OCRPreviewResponse(AppBaseModel):
    source_file_name: Optional[str] = Field(default=None, description="Uploaded source filename")
    page_count: Optional[int] = Field(default=None, description="Total PDF pages")
    extraction_method: Optional[str] = Field(default=None, description="text, ocr, or mixed")
    ocr_used: bool = Field(default=False, description="Whether OCR was used")
    extracted_characters: int = Field(default=0, description="Character count after extraction")
    preview_text: str = Field(default="", description="Preview text returned to the UI")
    warnings: List[str] = Field(default_factory=list, description="Preview warnings")
    effective_ocr_language: Optional[str] = Field(default=None, description="OCR language setting used")
    effective_ocr_dpi: Optional[int] = Field(default=None, description="OCR DPI used")
    effective_ocr_max_pages: Optional[int] = Field(default=None, description="Maximum OCR pages used")


class ExtractionJobCreated(AppBaseModel):
    task_id: str = Field(description="Background extraction task id")
    status: str = Field(description="Current task state")
    model: str = Field(description="Fixed model used for extraction")


class ExtractionJobStatus(AppBaseModel):
    task_id: str = Field(description="Background extraction task id")
    status: str = Field(description="queued, running, completed, or failed")
    message: Optional[str] = Field(default=None, description="Human-readable task progress")
    result: Optional[TranscriptSchema] = Field(default=None, description="Structured transcript when the task completes")
    error: Optional[str] = Field(default=None, description="Failure reason when the task fails")
