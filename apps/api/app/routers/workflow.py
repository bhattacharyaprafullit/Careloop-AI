"""POST /api/v1/workflow/resume and GET /api/v1/workflow/approvals endpoints (M7)."""
import logging
from typing import Any

from fastapi import APIRouter
from sqlalchemy import select

from app.core.errors import AppError
from app.db.models import Case, Patient, PendingApproval
from app.db.repo import clock_for_sandbox
from app.deps import DbSession, SandboxCtx
from app.domain.states import Decision
from app.graph.runner import resume_case_graph
from app.schemas.workflow import WorkflowResumeRequest, WorkflowResumeResponse
from app.services.events import record_event

logger = logging.getLogger(__name__)

router = APIRouter(tags=["workflow"])


@router.get("/workflow/approvals")
def list_pending_approvals(
    db: DbSession,
    ctx: SandboxCtx,
) -> dict[str, list[dict[str, Any]]]:
    """List pending human approvals in the current sandbox."""
    sb = ctx.sandbox
    rows = list(
        db.scalars(
            select(PendingApproval)
            .where(
                PendingApproval.sandbox_id == sb.id,
                PendingApproval.status == "pending",
            )
            .order_by(PendingApproval.at.desc())
        )
    )
    cases_by_id = {
        c.id: c for c in db.scalars(select(Case).where(Case.sandbox_id == sb.id))
    }
    patients_by_id = {
        p.id: p for p in db.scalars(select(Patient).where(Patient.sandbox_id == sb.id))
    }
    items: list[dict[str, Any]] = []
    for r in rows:
        c = cases_by_id.get(r.case_id)
        pat = patients_by_id.get(c.patient_id) if c else None
        items.append(
            {
                "id": r.id,
                "case_id": r.case_id,
                "patient_alias": pat.alias if pat else r.case_id,
                "screening_type": c.screening_type if c else "FIT",
                "state": c.state if c else "RESULT_ISSUED",
                "urgency_tier": c.urgency_tier if c else 1,
                "action_type": r.action_type,
                "payload": r.payload,
                "reasons": r.reasons,
                "status": r.status,
                "at": r.at.isoformat(),
            }
        )
    return {"items": items}


@router.post("/workflow/resume", response_model=WorkflowResumeResponse)
def resume_workflow(
    body: WorkflowResumeRequest,
    db: DbSession,
    ctx: SandboxCtx,
) -> WorkflowResumeResponse:
    """Validate human decision (approve, modify, reject) and resume the paused LangGraph thread."""
    sb = ctx.sandbox
    clock = clock_for_sandbox(sb)
    now = clock()

    valid_decisions = {d.value for d in Decision}
    if body.decision not in valid_decisions:
        raise AppError(
            400, "invalid_decision", "decision must be approve, modify, or reject."
        )

    if body.decision in {Decision.MODIFY.value, Decision.REJECT.value} and (
        not body.note or not body.note.strip()
    ):
        raise AppError(
            400,
            "note_required",
            f"A rationale note is required when decision is '{body.decision}'.",
        )

    c = db.scalar(select(Case).where(Case.id == body.case_id, Case.sandbox_id == sb.id))
    if c is None:
        raise AppError(404, "case_not_found", f"Case '{body.case_id}' not found.")

    pa = db.scalar(
        select(PendingApproval).where(
            PendingApproval.case_id == c.id,
            PendingApproval.status == "pending",
        )
    )
    if pa is None:
        raise AppError(
            409,
            "no_pending_approval",
            f"Case '{c.id}' has no pending approval to resume.",
        )

    decision_payload = {
        "decision": body.decision,
        "modified_action": body.modified_action,
        "note": body.note,
        "decided_by": ctx.role,
    }
    record_event(
        db,
        sandbox_id=sb.id,
        case_id=c.id,
        event_type="APPROVAL_DECIDED",
        actor_role=ctx.role,
        from_state=c.state,
        to_state=c.state,
        payload=decision_payload,
        at=now,
    )
    db.commit()

    res = resume_case_graph(c.id, decision_payload)
    db.expire_all()
    c_updated = db.scalar(select(Case).where(Case.id == c.id))
    final_state = c_updated.state if c_updated else c.state

    return WorkflowResumeResponse(
        case_id=c.id,
        status=str(res["status"]),
        state=final_state,
    )
