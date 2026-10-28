"""Cross-provider consultation service: patient-to-clinician and clinician-to-clinician (M8)."""
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import Case, Consult, Sandbox
from app.db.repo import clock_for_sandbox
from app.services.events import record_event

logger = logging.getLogger(__name__)

VALID_CONSULT_KINDS = frozenset({"patient_to_clinician", "clinician_to_clinician"})


def create_consult_thread(
    db: Session,
    *,
    sb: Sandbox,
    actor_role: str,
    case_id: str,
    kind: str,
    message: str,
) -> dict[str, Any]:
    """Open a new consult thread on `case_id` and write a CONSULT_CREATED event."""
    if kind not in VALID_CONSULT_KINDS:
        raise AppError(
            400,
            "invalid_consult_kind",
            "kind must be 'patient_to_clinician' or 'clinician_to_clinician'.",
        )
    if not message.strip():
        raise AppError(400, "empty_message", "Consult message cannot be empty.")

    now = clock_for_sandbox(sb)()
    c = db.scalar(select(Case).where(Case.id == case_id, Case.sandbox_id == sb.id))
    if c is None:
        raise AppError(404, "case_not_found", f"Case '{case_id}' not found.")

    con = Consult(
        sandbox_id=sb.id,
        case_id=c.id,
        kind=kind,
        status="open",
        thread=[
            {
                "sender_role": actor_role,
                "body": message.strip(),
                "at": now.isoformat(),
            }
        ],
        created_at=now,
    )
    db.add(con)
    db.flush()

    record_event(
        db,
        sandbox_id=sb.id,
        case_id=c.id,
        event_type="CONSULT_CREATED",
        actor_role=actor_role,
        from_state=c.state,
        to_state=c.state,
        payload={"consult_id": con.id, "kind": kind},
        at=now,
    )
    db.commit()
    return {
        "consult_id": con.id,
        "case_id": c.id,
        "kind": con.kind,
        "status": con.status,
        "thread": con.thread,
    }


def reply_to_consult(
    db: Session,
    *,
    sb: Sandbox,
    actor_role: str,
    consult_id: str,
    message: str,
) -> dict[str, Any]:
    """Append a reply to an existing consult thread and write a CONSULT_REPLIED event."""
    if not message.strip():
        raise AppError(400, "empty_message", "Reply message cannot be empty.")

    now = clock_for_sandbox(sb)()
    con = db.scalar(
        select(Consult).where(Consult.id == consult_id, Consult.sandbox_id == sb.id)
    )
    if con is None:
        raise AppError(404, "consult_not_found", f"Consult '{consult_id}' not found.")

    c = db.scalar(select(Case).where(Case.id == con.case_id, Case.sandbox_id == sb.id))
    assert c is not None

    new_thread = [
        *con.thread,
        {
            "sender_role": actor_role,
            "body": message.strip(),
            "at": now.isoformat(),
        },
    ]
    con.thread = new_thread
    con.status = "answered"

    record_event(
        db,
        sandbox_id=sb.id,
        case_id=c.id,
        event_type="CONSULT_REPLIED",
        actor_role=actor_role,
        from_state=c.state,
        to_state=c.state,
        payload={"consult_id": con.id, "status": con.status},
        at=now,
    )
    db.commit()
    return {
        "consult_id": con.id,
        "case_id": c.id,
        "kind": con.kind,
        "status": con.status,
        "thread": con.thread,
    }
