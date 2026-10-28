"""Demo router: POST /api/v1/demo/advance-time and POST /api/v1/demo/reset (M9)."""
import logging

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Case, CaseEvent, PendingApproval, Sandbox
from app.db.repo import clock_for_sandbox
from app.deps import DbSession, SandboxCtx
from app.domain.sla import is_overdue
from app.domain.states import ActionType, CaseState, UrgencyTier
from app.schemas.metrics import (
    AdvanceTimeRequest,
    AdvanceTimeResponse,
    DemoResetResponse,
)
from app.services.events import record_event
from app.services.sandbox import reset_sandbox

logger = logging.getLogger(__name__)

router = APIRouter(tags=["demo"])


def scan_and_record_sla_breaches(db: Session, sb: Sandbox) -> tuple[int, int, int]:
    """Scan `sb` for overdue cases, record idempotent SLA_BREACH per (case, state), and escalate.

    Returns (total_overdue, newly_breached, newly_escalated).
    """
    clock = clock_for_sandbox(sb)
    now = clock()
    cases = list(db.scalars(select(Case).where(Case.sandbox_id == sb.id)))
    existing_breaches = {
        (ev.case_id, ev.from_state or ev.to_state)
        for ev in db.scalars(
            select(CaseEvent).where(
                CaseEvent.sandbox_id == sb.id,
                CaseEvent.event_type == "SLA_BREACH",
            )
        )
    }

    overdue_count = 0
    newly_breached = 0
    newly_escalated = 0

    for c in cases:
        if c.state == CaseState.CLOSED.value:
            continue
        if is_overdue(c.state, c.state_entered_at, c.urgency_tier, clock=clock):
            overdue_count += 1
            key = (c.id, c.state)
            if key not in existing_breaches:
                record_event(
                    db,
                    sandbox_id=sb.id,
                    case_id=c.id,
                    event_type="SLA_BREACH",
                    actor_role="system",
                    from_state=c.state,
                    to_state=c.state,
                    payload={"state": c.state, "urgency_tier": c.urgency_tier},
                    at=now,
                )
                existing_breaches.add(key)
                newly_breached += 1

            # Escalation rule: urgency_tier 1 and overdue (or any breached case needing attention)
            if c.urgency_tier == UrgencyTier.URGENT and not c.escalated:
                c.escalated = True
                newly_escalated += 1
                existing_pa = db.scalar(
                    select(PendingApproval).where(
                        PendingApproval.case_id == c.id,
                        PendingApproval.status == "pending",
                    )
                )
                if existing_pa is None:
                    db.add(
                        PendingApproval(
                            sandbox_id=sb.id,
                            case_id=c.id,
                            action_type=ActionType.CREATE_NAVIGATOR_TASK.value,
                            payload={"channel": "sms", "owner_id": c.owner_id or "coord-1"},
                            reasons=["urgent_and_overdue"],
                            status="pending",
                            at=now,
                        )
                    )

    return overdue_count, newly_breached, newly_escalated


@router.post("/demo/advance-time", response_model=AdvanceTimeResponse)
def post_advance_time(
    body: AdvanceTimeRequest,
    db: DbSession,
    ctx: SandboxCtx,
) -> AdvanceTimeResponse:
    """Advance the per-sandbox clock by `hours` (<= 720) and record idempotent SLA breaches."""
    sb = ctx.sandbox
    sb.clock_offset_hours = float(sb.clock_offset_hours) + float(body.hours)
    db.flush()

    overdue_n, breached_n, _ = scan_and_record_sla_breaches(db, sb)
    db.commit()
    return AdvanceTimeResponse(
        clock_offset_hours=round(float(sb.clock_offset_hours), 2),
        overdue_cases=overdue_n,
        newly_breached=breached_n,
    )


@router.post("/demo/reset", response_model=DemoResetResponse)
def post_demo_reset(
    db: DbSession,
    ctx: SandboxCtx,
) -> DemoResetResponse:
    """Reset the sandbox back to its initial 60 seed cases and zero clock offset."""
    sb = ctx.sandbox
    count = reset_sandbox(db, sb)
    return DemoResetResponse(
        sandbox_id=sb.id,
        clock_offset_hours=0.0,
        case_count=count,
    )
