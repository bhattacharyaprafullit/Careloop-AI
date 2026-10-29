"""Cases router: priority-queue, details, assign, advance, close, and SSE stream (M5/M8)."""
import json
import logging
from collections.abc import Iterator
from typing import Annotated, Any

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.core.errors import AppError
from app.db.models import (
    Case,
    Evidence,
    LLMOutput,
    Patient,
    PendingApproval,
    RiskScore,
)
from app.db.repo import clock_for_sandbox, get_sandbox_by_token
from app.deps import DbSession, SandboxCtx
from app.domain.priority import compute_case_priority, evaluate_escalation
from app.domain.sla import hours_remaining, is_overdue, sla_due_at, sla_pressure
from app.domain.states import CaseState, EvidenceType
from app.domain.transitions import owner_role_for_state, validate_transition
from app.schemas.cases import (
    AdvanceCaseRequest,
    AssignCaseRequest,
    CaseDetailsResponse,
    PriorityQueueItem,
    PriorityQueueResponse,
)
from app.schemas.patient import CloseCaseRequest
from app.services.closure_service import close_case_with_gate
from app.services.events import build_case_details_response, record_event
from app.services.inference import build_case_feature_dict, persist_risk_score, score_case

logger = logging.getLogger(__name__)
router = APIRouter(tags=["cases"])


@router.get("/cases/priority-queue", response_model=PriorityQueueResponse)
def get_priority_queue(
    db: DbSession,
    ctx: SandboxCtx,
    state: str | None = None,
    overdue: bool | None = None,
    unassigned: bool | None = None,
    rejected: bool | None = None,
    needs_approval: bool | None = None,
    owner_role: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=250)] = 60,
    sort: str = "priority_desc",
) -> PriorityQueueResponse:
    """Return filtered, priority-sorted cases for the current sandbox."""
    sb = ctx.sandbox
    clock = clock_for_sandbox(sb)
    cases_with_patient = db.execute(
        select(Case, Patient.alias)
        .outerjoin(Patient, (Patient.id == Case.patient_id) & (Patient.sandbox_id == sb.id))
        .where(Case.sandbox_id == sb.id)
    ).all()
    pending_ids = set(
        db.scalars(
            select(PendingApproval.case_id).where(
                PendingApproval.sandbox_id == sb.id, PendingApproval.status == "pending"
            )
        )
    )
    # Select only case_id and p_dropoff instead of full ORM objects with JSON blobs
    risks = {
        row[0]: float(row[1])
        for row in db.execute(
            select(RiskScore.case_id, RiskScore.p_dropoff)
            .where(RiskScore.sandbox_id == sb.id)
            .order_by(RiskScore.at.asc())
        ).all()
    }

    items: list[PriorityQueueItem] = []
    for c, pat_alias in cases_with_patient:
        c_needs_app = c.id in pending_ids
        c_overdue = is_overdue(c.state, c.state_entered_at, c.urgency_tier, clock=clock)
        if (
            (state and c.state != state)
            or (owner_role and c.owner_role != owner_role)
            or (unassigned is not None and (c.owner_id is None) != unassigned)
            or (rejected is not None and (c.state == CaseState.REJECTED.value) != rejected)
            or (needs_approval is not None and c_needs_app != needs_approval)
            or (overdue is not None and c_overdue != overdue)
        ):
            continue

        p_drop = risks.get(c.id, 0.25)
        press = sla_pressure(c.state, c.state_entered_at, c.urgency_tier, clock=clock)
        prio = round(
            compute_case_priority(c.urgency_tier, p_drop, press)
            if c.state != CaseState.CLOSED.value
            else 0.0,
            4,
        )
        due = sla_due_at(c.state, c.state_entered_at, c.urgency_tier)
        rem = hours_remaining(c.state, c.state_entered_at, c.urgency_tier, clock=clock)
        items.append(
            PriorityQueueItem(
                case_id=c.id,
                patient_alias=pat_alias or c.patient_id,
                screening_type=c.screening_type,
                state=c.state,
                owner_role=c.owner_role,
                owner_id=c.owner_id,
                urgency_tier=c.urgency_tier,
                p_dropoff=round(p_drop, 4),
                priority=prio,
                sla_due_at=due,
                hours_remaining=round(rem, 2) if rem is not None else None,
                overdue=c_overdue,
                escalated=bool(c.escalated),
                needs_approval=c_needs_app,
            )
        )

    items.sort(
        key=lambda x: (x.priority, x.p_dropoff, x.case_id),
        reverse=(sort != "priority_asc"),
    )
    start = (page - 1) * page_size
    return PriorityQueueResponse(
        items=items[start : start + page_size], page=page, page_size=page_size, total=len(items)
    )


@router.get("/cases/{case_id}/details", response_model=CaseDetailsResponse)
def get_case_details(case_id: str, db: DbSession, ctx: SandboxCtx) -> CaseDetailsResponse:
    """Return full case details, timeline, risk, SHAP, survival vs KM curves, and threads."""
    sb = ctx.sandbox
    c = db.scalar(select(Case).where(Case.id == case_id, Case.sandbox_id == sb.id))
    if c is None:
        raise AppError(404, "case_not_found", f"Case '{case_id}' not found in sandbox.")
    pat = db.scalar(select(Patient).where(Patient.id == c.patient_id))
    if pat is None:
        raise AppError(404, "patient_not_found", "Patient record not found.")
    return build_case_details_response(db, sb, c, pat)


@router.post("/cases/{case_id}/assign")
def assign_case_owner(
    case_id: str, body: AssignCaseRequest, db: DbSession, ctx: SandboxCtx
) -> dict[str, Any]:
    """Assign or reassign owner_role and owner_id on a case and record OWNER_ASSIGNED event."""
    sb = ctx.sandbox
    c = db.scalar(select(Case).where(Case.id == case_id, Case.sandbox_id == sb.id))
    if c is None:
        raise AppError(404, "case_not_found", f"Case '{case_id}' not found.")
    if body.owner_role not in {"coordinator", "clinician"}:
        raise AppError(400, "invalid_owner_role", "owner_role must be coordinator or clinician.")

    c.owner_role, c.owner_id = body.owner_role, body.owner_id.strip() or None
    record_event(
        db,
        sandbox_id=sb.id,
        case_id=c.id,
        event_type="OWNER_ASSIGNED",
        actor_role=ctx.role,
        actor_id=body.owner_id,
        from_state=c.state,
        to_state=c.state,
        payload={"owner_role": c.owner_role, "owner_id": c.owner_id},
        at=clock_for_sandbox(sb)(),
    )
    db.commit()
    return {"case_id": c.id, "owner_role": c.owner_role, "owner_id": c.owner_id}


@router.post("/cases/{case_id}/advance")
def advance_case_state(
    case_id: str, body: AdvanceCaseRequest, db: DbSession, ctx: SandboxCtx
) -> dict[str, Any]:
    """Advance a case to `to_state` if transition and entry evidence are legal (409 otherwise)."""
    sb = ctx.sandbox
    now = clock_for_sandbox(sb)()
    c = db.scalar(select(Case).where(Case.id == case_id, Case.sandbox_id == sb.id))
    if c is None:
        raise AppError(404, "case_not_found", f"Case '{case_id}' not found.")
    if body.to_state == CaseState.CLOSED.value:
        raise AppError(
            409,
            "use_close_endpoint",
            "Transition to CLOSED must go through POST /cases/{id}/close closure gate.",
        )

    ok, reason = validate_transition(
        c.state,
        body.to_state,
        evidence_type=body.evidence.type,
        reason_code=body.evidence.reason_code,
    )
    if not ok:
        raise AppError(409, "illegal_transition", reason)

    prev_state = c.state
    db.add(
        Evidence(
            sandbox_id=sb.id,
            case_id=c.id,
            type=body.evidence.type,
            ref=body.evidence.ref,
            created_by=ctx.role,
            at=now,
        )
    )
    c.state = body.to_state
    c.state_entered_at = now
    c.owner_role = owner_role_for_state(body.to_state)
    if body.evidence.type == EvidenceType.ACKNOWLEDGEMENT.value:
        c.acknowledged = True

    is_rebook = prev_state == CaseState.APPOINTMENT_BOOKED.value == body.to_state
    record_event(
        db,
        sandbox_id=sb.id,
        case_id=c.id,
        event_type="VISIT_MISSED_REBOOK_NEEDED" if is_rebook else "STATE_CHANGED",
        actor_role=ctx.role,
        from_state=prev_state,
        to_state=body.to_state,
        payload={"evidence_type": body.evidence.type, "evidence_ref": body.evidence.ref},
        at=now,
    )

    pat = db.scalar(select(Patient).where(Patient.id == c.patient_id))
    p_drop = 0.25
    if pat is not None:
        scored = score_case(build_case_feature_dict(c, pat, 0.1))
        p_drop = float(scored["p_dropoff"])
        persist_risk_score(db, sandbox_id=sb.id, case_id=c.id, stage=c.state, scored=scored, at=now)

    esc, _ = evaluate_escalation(
        urgency_tier=c.urgency_tier,
        overdue=False,
        p_dropoff=p_drop,
        referral_rejected=(c.state == CaseState.REJECTED.value),
    )
    if esc:
        c.escalated = True
    db.commit()
    return {
        "case_id": c.id,
        "from_state": prev_state,
        "state": c.state,
        "owner_role": c.owner_role,
        "p_dropoff": p_drop,
        "escalated": c.escalated,
    }


@router.get("/cases/{case_id}/stream")
def stream_case_events(case_id: str, token: str, db: DbSession) -> StreamingResponse:
    """SSE stream (events: status, token, done). Authenticates via ?token= query param."""
    sb = get_sandbox_by_token(db, token)
    if sb is None:
        raise AppError(401, "invalid_sandbox_token", "Invalid or expired sandbox token.")
    c = db.scalar(select(Case).where(Case.id == case_id, Case.sandbox_id == sb.id))
    if c is None:
        raise AppError(404, "case_not_found", f"Case '{case_id}' not found.")

    lo = db.scalar(
        select(LLMOutput)
        .where(LLMOutput.case_id == c.id, LLMOutput.kind == "case_summary")
        .order_by(LLMOutput.at.desc())
    )
    lines = list(lo.output.get("summary_lines", [])) if lo else [f"Case {c.id} is in {c.state}."]
    status_json = json.dumps(
        {"case_id": case_id, "state": c.state, "escalated": bool(c.escalated)}
    )

    def _event_gen() -> Iterator[str]:
        yield f"event: status\ndata: {status_json}\n\n"
        for line in lines:
            yield f"event: token\ndata: {json.dumps({'text': line})}\n\n"
        yield f"event: done\ndata: {json.dumps({'case_id': case_id, 'done': True})}\n\n"

    return StreamingResponse(_event_gen(), media_type="text/event-stream")


@router.post("/cases/{case_id}/close")
def close_case(
    case_id: str, body: CloseCaseRequest, db: DbSession, ctx: SandboxCtx
) -> dict[str, Any]:
    """Close a case only if closure gate passes (evidence or authorized clinician override)."""
    return close_case_with_gate(
        db, sb=ctx.sandbox, actor_role=ctx.role, case_id=case_id, body=body
    )
