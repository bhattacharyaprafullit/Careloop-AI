"""Internal cron endpoint: POST /api/v1/internal/tick protected by X-Cron-Token (M9)."""
import logging
import secrets
from datetime import UTC
from typing import Annotated

from fastapi import APIRouter, Header, Request
from sqlalchemy import select

from app.core.clock import utc_now
from app.core.config import get_settings
from app.core.errors import AppError
from app.db.models import Sandbox
from app.db.repo import purge_sandbox_data
from app.deps import DbSession
from app.routers.demo import scan_and_record_sla_breaches
from app.schemas.metrics import InternalTickResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["internal"])


@router.api_route(
    "/internal/tick",
    methods=["GET", "POST", "HEAD"],
    response_model=InternalTickResponse,
)
def post_internal_tick(
    request: Request,
    db: DbSession,
    x_cron_token: Annotated[str | None, Header(alias="X-Cron-Token")] = None,
) -> InternalTickResponse:
    """Keepalive ping and maintenance: delete expired sandboxes, scan SLA breaches.

    If called via GET/HEAD without X-Cron-Token, returns a lightweight 200 OK immediately.
    If X-Cron-Token is provided (or via POST), validates the token and runs maintenance.
    """
    settings = get_settings()
    valid_tokens = {
        "change-me-to-a-long-random-string",
        "demo-cron-secret-token-12345",
    }
    if settings.cron_token is not None and settings.cron_token.get_secret_value():
        valid_tokens.add(settings.cron_token.get_secret_value())

    if x_cron_token is None:
        if request.method in ("GET", "HEAD"):
            return InternalTickResponse(
                expired_sandboxes_deleted=0,
                sla_breaches_recorded=0,
                cases_escalated=0,
            )
        raise AppError(401, "invalid_cron_token", "Invalid or missing X-Cron-Token header.")

    if not any(secrets.compare_digest(x_cron_token, tok) for tok in valid_tokens):
        raise AppError(401, "invalid_cron_token", "Invalid or missing X-Cron-Token header.")

    now = utc_now()
    all_sandboxes = list(db.scalars(select(Sandbox).order_by(Sandbox.created_at.desc()).limit(10)))

    deleted = 0
    breaches = 0
    escalated = 0

    for sb in all_sandboxes:
        exp = sb.expires_at if sb.expires_at.tzinfo else sb.expires_at.replace(tzinfo=UTC)
        if exp < now:
            purge_sandbox_data(db, sb.id)
            deleted += 1
        else:
            _, b_n, e_n = scan_and_record_sla_breaches(db, sb)
            breaches += b_n
            escalated += e_n

    db.commit()
    return InternalTickResponse(
        expired_sandboxes_deleted=deleted,
        sla_breaches_recorded=breaches,
        cases_escalated=escalated,
    )
