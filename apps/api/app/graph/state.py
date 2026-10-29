"""LangGraph TypedDict state and shared DB execution helpers (M7)."""
import logging
from datetime import datetime
from typing import Any, TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import ClockFn
from app.db.models import (
    Case,
    CaseEvent,
    Closure,
    Evidence,
    Patient,
    PendingApproval,
    Sandbox,
)
from app.db.repo import clock_for_sandbox
from app.db.session import get_engine
from app.domain.closure import can_close
from app.domain.states import CaseState
from app.services.events import record_event

logger = logging.getLogger(__name__)


class CareLoopGraphState(TypedDict, total=False):
    case_id: str
    sandbox_id: str
    features: dict[str, Any]
    risk: dict[str, Any]
    shap: dict[str, Any]
    summary: dict[str, Any]
    message: dict[str, Any]
    suggested_action: dict[str, Any]
    reasons: list[str]
    requires_human: bool
    decision: dict[str, Any]
    action_result: dict[str, Any]
    closure_result: dict[str, Any]


def open_graph_db() -> Session:
    """Open a SQLAlchemy Session against the active graph engine."""
    return Session(get_engine())


def load_graph_ctx(
    db: Session, state: CareLoopGraphState
) -> tuple[Case, Sandbox, Patient, ClockFn]:
    """Load Case, Sandbox, Patient, and sandbox ClockFn for a graph node."""
    c = db.scalar(select(Case).where(Case.id == state["case_id"]))
    if c is None:
        raise ValueError(f"Case {state['case_id']} not found")
    pat = db.scalar(select(Patient).where(Patient.id == c.patient_id))
    sb = db.scalar(select(Sandbox).where(Sandbox.id == c.sandbox_id))
    if pat is None or sb is None:
        raise ValueError("Missing patient or sandbox for case")
    return c, sb, pat, clock_for_sandbox(sb)


def upsert_pending_approval(
    db: Session,
    *,
    sandbox_id: str,
    case_id: str,
    action_type: str,
    payload: dict[str, Any],
    reasons: list[str],
    at: datetime,
) -> PendingApproval:
    """Idempotently create or update an open PendingApproval row for `case_id`."""
    stmt = select(PendingApproval).where(
        PendingApproval.case_id == case_id, PendingApproval.status == "pending"
    )
    pa = db.scalar(stmt)
    if pa is None:
        pa = PendingApproval(
            sandbox_id=sandbox_id,
            case_id=case_id,
            action_type=action_type,
            payload=payload,
            reasons=reasons,
            status="pending",
            at=at,
        )
        db.add(pa)
    else:
        pa.action_type, pa.payload, pa.reasons = action_type, payload, reasons
    return pa


def execute_graph_action(db: Session, state: CareLoopGraphState) -> dict[str, Any]:
    """Execute the approved, modified, or routine action idempotently inside `db`."""
    c, sb, _, clock = load_graph_ctx(db, state)
    now = clock()
    dec = state.get("decision") or {}
    kind = str(dec.get("decision", "approve"))
    actor = str(dec.get("decided_by", "coordinator"))
    suggested = dict(state.get("suggested_action") or {})
    if kind == "modify" and isinstance(dec.get("modified_action"), dict):
        suggested.update(dec["modified_action"])

    act_type = str(suggested.get("action_type", "act"))
    act_key = str(suggested.get("action_key") or f"{c.id}:{c.state}:{act_type}")
    pa = db.scalar(
        select(PendingApproval).where(
            PendingApproval.case_id == c.id, PendingApproval.status == "pending"
        )
    )
    if pa is not None:
        pa.status, pa.decision, pa.decided_by, pa.note = "decided", kind, actor, dec.get("note")

    if kind == "reject":
        record_event(
            db,
            sandbox_id=sb.id,
            case_id=c.id,
            event_type="MANUAL_PLAN_RECORDED",
            actor_role=actor,
            from_state=c.state,
            to_state=c.state,
            payload={"decision": "reject", "note": dec.get("note"), "action_key": act_key},
            at=now,
        )
        db.commit()
        return {"executed": False, "status": "rejected_manual_plan"}

    stmt = select(CaseEvent).where(
        CaseEvent.case_id == c.id, CaseEvent.event_type == "ACTION_EXECUTED"
    )
    if not any(ev.payload.get("action_key") == act_key for ev in db.scalars(stmt)):
        if suggested.get("owner_id"):
            c.owner_id = str(suggested["owner_id"])
        c.contact_attempts = int(c.contact_attempts) + 1
        record_event(
            db,
            sandbox_id=sb.id,
            case_id=c.id,
            event_type="ACTION_EXECUTED",
            actor_role=actor,
            from_state=c.state,
            to_state=c.state,
            payload={
                "action_key": act_key,
                "action_type": act_type,
                "channel": suggested.get("channel"),
                "owner_id": c.owner_id,
                "decision": kind,
            },
            at=now,
        )
    db.commit()
    return {"executed": True, "action_key": act_key, "action_type": act_type}


def evaluate_graph_closure(db: Session, state: CareLoopGraphState) -> dict[str, Any]:
    """Evaluate domain `can_close` and persist Closure if valid."""
    req = state.get("closure_result") or {}
    c, _, _, _ = load_graph_ctx(db, state)
    ev_types = set(db.scalars(select(Evidence.type).where(Evidence.case_id == c.id)))
    override = req.get("override")
    ok, kind_or_msg = can_close(ev_types, override)
    if ok and c.state != CaseState.CLOSED.value:
        c.state, c.owner_role, c.owner_id = CaseState.CLOSED.value, None, None
        db.add(
            Closure(
                sandbox_id=c.sandbox_id,
                case_id=c.id,
                kind="override" if kind_or_msg == "authorized_override" else "evidence",
                evidence_type=req.get("evidence_type"),
                override_by=override.get("by") if isinstance(override, dict) else None,
                override_reason=override.get("reason") if isinstance(override, dict) else None,
            )
        )
        db.commit()
    return {"checked": True, "can_close": ok, "reason": kind_or_msg}
