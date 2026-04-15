from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["admin"])


@router.get("/healthz")
async def healthz():
    return {
        "status": "ok",
        "model": settings.llm_model,
        "llm_configured": bool(settings.dashscope_api_key),
        "ocr_enabled": settings.ocr_enabled,
        "ocr_language": settings.ocr_language,
        "user_db_path": str(settings.user_db_path),
    }
