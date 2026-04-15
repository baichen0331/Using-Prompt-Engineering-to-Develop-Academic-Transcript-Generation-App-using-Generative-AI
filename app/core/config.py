from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[2]
VALID_JWT_ALGORITHMS = {"HS256", "HS384", "HS512"}


@dataclass(frozen=True)
class Settings:
    app_name: str = "Academic Transcript Generation API"
    app_version: str = "6.0.0"
    dashscope_api_key: str = os.environ.get("DASHSCOPE_API_KEY", "")
    dashscope_base_url: str = os.environ.get(
        "DASHSCOPE_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    llm_model: str = os.environ.get("LLM_MODEL", "qwen3.6-plus")
    max_upload_mb: int = int(os.environ.get("MAX_UPLOAD_MB", "10"))
    max_text_chars: int = int(os.environ.get("MAX_TEXT_CHARS", "60000"))
    jwt_secret: str = os.environ.get("JWT_SECRET", "change-this-secret-in-production")
    jwt_algorithm: str = os.environ.get("JWT_ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))
    user_db_path_raw: str = os.environ.get("USER_DB_PATH", "users.db")
    password_hash_iterations: int = int(os.environ.get("PASSWORD_HASH_ITERATIONS", "390000"))
    admin_username: str = os.environ.get("ADMIN_USERNAME", "admin")
    admin_password: str = os.environ.get("ADMIN_PASSWORD", "admin123")
    reviewer_username: str = os.environ.get("REVIEWER_USERNAME", "reviewer")
    reviewer_password: str = os.environ.get("REVIEWER_PASSWORD", "review123")
    ocr_enabled: bool = os.environ.get("OCR_ENABLED", "false").lower() == "true"
    ocr_language: str = os.environ.get("OCR_LANGUAGE", "eng+chi_sim")
    ocr_dpi: int = int(os.environ.get("OCR_DPI", "200"))
    ocr_max_pages: int = int(os.environ.get("OCR_MAX_PAGES", "8"))
    ocr_page_timeout_seconds: float = float(os.environ.get("OCR_PAGE_TIMEOUT_SECONDS", "8"))
    ocr_total_timeout_seconds: float = float(os.environ.get("OCR_TOTAL_TIMEOUT_SECONDS", "30"))
    ocr_empty_page_warning_limit: int = int(os.environ.get("OCR_EMPTY_PAGE_WARNING_LIMIT", "3"))
    tesseract_cmd: str | None = os.environ.get("TESSERACT_CMD")

    @property
    def max_upload_size(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def user_db_path(self) -> Path:
        candidate = Path(self.user_db_path_raw)
        return candidate if candidate.is_absolute() else BASE_DIR / candidate

    @property
    def normalized_jwt_algorithm(self) -> str:
        if self.jwt_algorithm in VALID_JWT_ALGORITHMS:
            return self.jwt_algorithm
        return "HS256"


settings = Settings()
