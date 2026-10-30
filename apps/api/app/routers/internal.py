"""Internal cron endpoint: POST /api/v1/internal/tick protected by X-Cron-Token (M9)."""
import logging
import secrets
from datetime import UTC
from typing import Annotated

from fastapi import APIRouter, Header
from sqlalchemy import select

from app.core.clock import utc_now
from app.core.config import get_settings
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
    db: DbSession,
    x_cron_token: Annotated[str | None, Header(alias="X-Cron-Token")] = None,
) -> InternalTickResponse:
    """Keepalive ping and maintenance: delete expired sandboxes, scan SLA breaches.

    If X-Cron-Token is provided and valid, runs maintenance for active sandboxes.
    If called without token (or via GET keepalive ping), returns 200 OK immediately.
    """
    settings = get_settings()
    expected = (
        settings.cron_token.get_secret_value()
        if settings.cron_token is not None
        else "demo-cron-secret-token-12345"
    )

    if not x_cron_token or not secrets.compare_digest(x_cron_token, expected):
        return InternalTickResponse(
            expired_sandboxes_deleted=0,
            sla_breaches_recorded=0,
            cases_escalated=0,
        )

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
