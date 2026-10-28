"""Sandbox service: create, advance clock, reset, and enforce row caps (M5/M9)."""
import logging
from datetime import UTC

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import Case, Sandbox
from app.db.repo import (
    MAX_CASES_PER_SANDBOX,
    clone_seed_into_sandbox,
    create_sandbox_with_seed,
    purge_sandbox_data,
)
from app.schemas.common import SandboxResponse

logger = logging.getLogger(__name__)


def launch_sandbox(db: Session) -> SandboxResponse:
    """Create a fresh 24-hour sandbox cloned from the 60-case seed."""
    token, sb, count = create_sandbox_with_seed(db)
    exp = sb.expires_at if sb.expires_at.tzinfo else sb.expires_at.replace(tzinfo=UTC)
    logger.info("created sandbox", extra={"sandbox_id": sb.id, "cases": count})
    return SandboxResponse(token=token, expires_at=exp, case_count=count)


def enforce_sandbox_case_cap(db: Session, sandbox_id: str) -> None:
    """Ensure a single sandbox cannot exceed MAX_CASES_PER_SANDBOX rows."""
    current = db.scalar(
        select(func.count()).select_from(Case).where(Case.sandbox_id == sandbox_id)
    )
    if (current or 0) >= MAX_CASES_PER_SANDBOX:
        raise AppError(
            429,
            "sandbox_cap_reached",
            f"Sandbox case limit ({MAX_CASES_PER_SANDBOX}) reached. Please reset the demo.",
        )


def reset_sandbox(db: Session, sb: Sandbox) -> int:
    """Delete all data in `sb` and re-clone the 60 seed cases under the same token_hash."""
    sb_id = sb.id
    th = sb.token_hash
    purge_sandbox_data(db, sb_id)
    clone_seed_into_sandbox(db, sandbox_id=sb_id, token_hash=th)
    return 60
