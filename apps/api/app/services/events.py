"""Event formatting and append helpers for CareLoop AI timelines (M5)."""
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CaseEvent
from app.db.repo import append_case_event
from app.schemas.cases import TimelineEntry

logger = logging.getLogger(__name__)


def summarize_event(ev: CaseEvent) -> str:
    """Build a human-readable single-line summary for a CaseEvent."""
    et = ev.event_type
    if et == "CASE_ISSUED":
        return f"Screening result issued in state {ev.to_state} ({ev.actor_role})."
    if et == "STATE_CHANGED":
        return f"Transitioned from {ev.from_state} to {ev.to_state} by {ev.actor_role}."
    if et == "OWNER_ASSIGNED":
        owner = ev.payload.get("owner_id") or ev.actor_id or "unassigned"
        return f"Assigned to {ev.payload.get('owner_role', ev.actor_role)} ({owner})."
    if et == "SLA_BREACH":
        return f"SLA deadline breached in state {ev.from_state or ev.to_state}; case escalated."
    if et == "VISIT_MISSED_REBOOK_NEEDED":
        return "Patient missed scheduled appointment; priority rebooking required."
    if et == "MESSAGE_QUEUED":
        return f"Outreach message queued via {ev.payload.get('channel', 'portal')}."
    if et == "PATIENT_ACKNOWLEDGED":
        return "Patient acknowledged receipt of screening result."
    if et == "TEACHBACK_RECORDED":
        lbl = ev.payload.get("label", "unknown")
        return f"Patient teach-back check recorded as '{lbl}'."
    if et == "REFERRAL_CREATED":
        return f"Referral sent to {ev.payload.get('to_org', 'specialty clinic')}."
    if et == "REFERRAL_DECIDED":
        dec = ev.payload.get("decision", "decided")
        return f"Referral {dec} by clinician."
    if et == "CONSULT_CREATED":
        return f"Consultation thread opened ({ev.payload.get('kind', 'consult')})."
    if et == "CONSULT_REPLIED":
        return f"Consultation reply added by {ev.actor_role}."
    if et == "APPROVAL_DECIDED":
        return f"Human approval gate decision: {ev.payload.get('decision', 'decided')}."
    if et == "CASE_CLOSED":
        return f"Case closed ({ev.payload.get('kind', 'evidence')})."
    return f"{et} recorded by {ev.actor_role}."


def get_case_timeline(db: Session, case_id: str) -> list[TimelineEntry]:
    """Return chronologically ordered timeline entries for `case_id`."""
    rows = list(
        db.scalars(
            select(CaseEvent)
            .where(CaseEvent.case_id == case_id)
            .order_by(CaseEvent.at.asc())
        )
    )
    out: list[TimelineEntry] = []
    for r in rows:
        at_utc = r.at if r.at.tzinfo else r.at.replace(tzinfo=UTC)
        out.append(
            TimelineEntry(
                at=at_utc,
                event_type=r.event_type,
                from_state=r.from_state,
                to_state=r.to_state,
                actor_role=r.actor_role,
                summary=summarize_event(r),
            )
        )
    return out


def record_event(
    db: Session,
    *,
    sandbox_id: str,
    case_id: str,
    event_type: str,
    actor_role: str,
    actor_id: str | None = None,
    from_state: str | None = None,
    to_state: str | None = None,
    payload: dict[str, Any] | None = None,
    at: datetime | None = None,
) -> CaseEvent:
    """Write an append-only row to case_events."""
    return append_case_event(
        db,
        sandbox_id=sandbox_id,
        case_id=case_id,
        event_type=event_type,
        actor_role=actor_role,
        actor_id=actor_id,
        from_state=from_state,
        to_state=to_state,
        payload=payload,
        at=at,
    )
