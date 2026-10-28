"""FastAPI dependencies for database session, sandbox context, and cron auth."""
import logging
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.security import RequestContext, verify_cron_token, verify_sandbox_and_role
from app.db.session import get_session

logger = logging.getLogger(__name__)

DbSession = Annotated[Session, Depends(get_session)]


def get_request_context(
    db: DbSession,
    x_sandbox_token: Annotated[str | None, Header(alias="X-Sandbox-Token")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> RequestContext:
    """Extract and validate X-Sandbox-Token and X-Role headers."""
    return verify_sandbox_and_role(db, x_sandbox_token, x_role)


SandboxCtx = Annotated[RequestContext, Depends(get_request_context)]


def require_cron_auth(
    x_cron_token: Annotated[str | None, Header(alias="X-Cron-Token")] = None,
) -> None:
    """Validate X-Cron-Token on /internal/tick."""
    verify_cron_token(x_cron_token)
