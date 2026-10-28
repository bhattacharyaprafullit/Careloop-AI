"""Header authentication and role checks for sandbox, staff roles, and cron (M5)."""
import logging
import secrets
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.models import Sandbox
from app.db.repo import get_sandbox_by_token
from app.domain.states import Role

logger = logging.getLogger(__name__)

STAFF_ROLES: frozenset[str] = frozenset({Role.COORDINATOR.value, Role.CLINICIAN.value})


@dataclass(frozen=True)
class RequestContext:
    sandbox: Sandbox
    role: str
    token: str


def verify_sandbox_and_role(
    db: Session,
    sandbox_token: str | None,
    role_header: str | None,
) -> RequestContext:
    """Validate X-Sandbox-Token and X-Role (coordinator or clinician)."""
    if not sandbox_token or not sandbox_token.strip():
        raise AppError(401, "missing_sandbox_token", "Header X-Sandbox-Token is required.")

    sb = get_sandbox_by_token(db, sandbox_token.strip())
    if sb is None:
        raise AppError(
            401, "invalid_sandbox_token", "Sandbox token is invalid or has expired."
        )

    if not role_header or role_header.strip() not in STAFF_ROLES:
        raise AppError(
            403,
            "invalid_role",
            "Header X-Role must be 'coordinator' or 'clinician'.",
        )

    return RequestContext(sandbox=sb, role=role_header.strip(), token=sandbox_token.strip())


def verify_cron_token(cron_token: str | None) -> None:
    """Validate X-Cron-Token header against settings.cron_token."""
    settings = get_settings()
    expected = (
        settings.cron_token.get_secret_value()
        if settings.cron_token is not None
        else "change-me-to-a-long-random-string"
    )
    if not cron_token or not secrets.compare_digest(cron_token, expected):
        raise AppError(401, "invalid_cron_token", "Invalid or missing X-Cron-Token header.")
