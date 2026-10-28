"""Liveness and database readiness endpoints (/healthz and /healthz/db)."""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import get_session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str | bool]:
    """Cheap liveness probe used by Hugging Face, the keepalive cron and the frontend."""
    settings = get_settings()
    return {
        "status": "ok",
        "version": settings.app_version,
        "demo_mode": settings.demo_mode,
        "llm": "groq" if settings.llm_enabled else "template",
    }


@router.get("/healthz/db")
def healthz_db(db: Annotated[Session, Depends(get_session)]) -> dict[str, str]:
    """Database connectivity probe (returns 503 with friendly envelope when DB is down)."""
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error("database healthcheck failed", extra={"err": str(exc)})
        raise AppError(
            503,
            "db_unavailable",
            "Database is temporarily unreachable. Please retry in a moment.",
        ) from exc
    return {"status": "ok", "db": "connected"}
