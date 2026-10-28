"""Case closure service enforcing the domain closure gate and authorized overrides (M8)."""
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import Case, Closure, Evidence, Sandbox
from app.db.repo import clock_for_sandbox
from app.domain.closure import can_close
from app.domain.states import ALLOWED_CLOSURE_EVIDENCE, CaseState, Role
from app.domain.transitions import is_legal_transition
from app.schemas.patient import CloseCaseRequest
from app.services.events import record_event

logger = logging.getLogger(__name__)


def close_case_with_gate(
    db: Session,
    *,
    sb: Sandbox,
    actor_role: str,
    case_id: str,
    body: CloseCaseRequest,
) -> dict[str, Any]:
    """Attempt to close `case_id` via domain `can_close` (409 closure_blocked if rejected)."""
    now = clock_for_sandbox(sb)()
    c = db.scalar(select(Case).where(Case.id == case_id, Case.sandbox_id == sb.id))
    if c is None:
        raise AppError(404, "case_not_found", f"Case '{case_id}' not found.")

    if c.state == CaseState.CLOSED.value:
        return {"case_id": c.id, "state": "CLOSED", "kind": "already_closed"}

    ev_types = set(db.scalars(select(Evidence.type).where(Evidence.case_id == c.id)))
    if body.evidence_type:
        if body.evidence_type not in ALLOWED_CLOSURE_EVIDENCE:
            raise AppError(
                409,
                "closure_blocked",
                f"Evidence '{body.evidence_type}' is not an allowed closure evidence type.",
            )
        # Normal evidence closure is only legal from states that can transition to CLOSED
        if not is_legal_transition(c.state, CaseState.CLOSED.value):
            raise AppError(
                409,
                "closure_blocked",
                f"Cannot close with evidence directly from state {c.state}.",
            )
        db.add(
            Evidence(
                sandbox_id=sb.id,
                case_id=c.id,
                type=body.evidence_type,
                ref=f"close-ev-{c.id}",
                created_by=actor_role,
                at=now,
            )
        )
        ev_types.add(body.evidence_type)

    override_dict: dict[str, Any] | None = None
    if body.override is not None:
        # Only a clinician can authorize a closure override
        is_authorized = actor_role == Role.CLINICIAN.value
        override_dict = {
            "authorized": is_authorized,
            "reason": body.override.reason.strip(),
        }
    else:
        # Without an override, the state itself must legally reach CLOSED
        if not is_legal_transition(c.state, CaseState.CLOSED.value):
            raise AppError(
                409,
                "closure_blocked",
                f"State {c.state} requires an authorized clinician override to close.",
            )

    ok, kind_or_msg = can_close(ev_types, override_dict)
    if not ok:
        raise AppError(409, "closure_blocked", kind_or_msg)

    prev_state = c.state
    c.state = CaseState.CLOSED.value
    c.state_entered_at = now
    c.closed_at = now
    c.owner_role = None
    c.owner_id = None
    c.escalated = False

    closure_kind = "override" if kind_or_msg == "authorized_override" else "evidence"
    chosen_ev = body.evidence_type or next(iter(ev_types & ALLOWED_CLOSURE_EVIDENCE), None)

    db.add(
        Closure(
            sandbox_id=sb.id,
            case_id=c.id,
            kind=closure_kind,
            evidence_type=chosen_ev if closure_kind == "evidence" else None,
            override_by=actor_role if closure_kind == "override" else None,
            override_reason=body.override.reason.strip() if body.override else None,
            at=now,
        )
    )

    record_event(
        db,
        sandbox_id=sb.id,
        case_id=c.id,
        event_type="STATE_CHANGED",
        actor_role=actor_role,
        from_state=prev_state,
        to_state=CaseState.CLOSED.value,
        payload={"kind": closure_kind, "evidence_type": chosen_ev},
        at=now,
    )
    record_event(
        db,
        sandbox_id=sb.id,
        case_id=c.id,
        event_type="CASE_CLOSED",
        actor_role=actor_role,
        from_state=prev_state,
        to_state=CaseState.CLOSED.value,
        payload={
            "kind": closure_kind,
            "evidence_type": chosen_ev,
            "override_reason": body.override.reason.strip() if body.override else None,
        },
        at=now,
    )
    db.commit()
    return {
        "case_id": c.id,
        "state": c.state,
        "kind": closure_kind,
        "evidence_type": chosen_ev,
    }
