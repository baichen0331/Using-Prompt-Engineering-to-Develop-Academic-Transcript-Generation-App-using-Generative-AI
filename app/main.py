from __future__ import annotations

from fastapi import FastAPI

from app.api.v1.routes_admin import router as admin_router
from app.api.v1.routes_auth import router as auth_router
from app.api.v1.routes_extract import router as extract_router
from app.api.v1.routes_pdf import router as pdf_router
from app.core.config import settings
from app.services.user_store import init_user_db

app = FastAPI(title=settings.app_name, version=settings.app_version)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(extract_router)
app.include_router(pdf_router)


@app.on_event("startup")
async def startup_event() -> None:
    init_user_db()
