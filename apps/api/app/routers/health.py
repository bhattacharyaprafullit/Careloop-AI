"""Liveness endpoint. /healthz/db is added in M4 with the database layer."""
import logging

from fastapi import APIRouter

from app.core.config import get_settings

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
