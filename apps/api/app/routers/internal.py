"""Internal cron endpoint: POST /api/v1/internal/tick protected by X-Cron-Token (M9)."""
import logging
from datetime import UTC

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.core.clock import utc_now
from app.db.models import Sandbox
from app.db.repo import purge_sandbox_data
from app.deps import DbSession, require_cron_auth
from app.routers.demo import scan_and_record_sla_breaches
from app.schemas.metrics import InternalTickResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["internal"])


@router.post(
    "/internal/tick",
    response_model=InternalTickResponse,
    dependencies=[Depends(require_cron_auth)],
)
def post_internal_tick(db: DbSession) -> InternalTickResponse:
    """Delete expired sandboxes, record idempotent SLA_BREACH events, and trigger escalation."""
    now = utc_now()
    all_sandboxes = list(db.scalars(select(Sandbox)))

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
