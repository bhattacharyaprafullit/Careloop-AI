"""Cases router: priority-queue, details, assign, advance, and SSE stream (M5)."""
import json
import logging
from collections.abc import Iterator
from typing import Annotated, Any

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import (
    Case,
    Closure,
    Consult,
    Evidence,
    LLMOutput,
    Message,
    Patient,
    PendingApproval,
    Referral,
    RiskScore,
)
from app.db.repo import clock_for_sandbox, get_sandbox_by_token
from app.deps import DbSession, SandboxCtx
from app.domain.priority import compute_case_priority, evaluate_escalation
from app.domain.sla import (
    hours_in_state,
    hours_remaining,
    is_overdue,
    sla_due_at,
    sla_pressure,
)
from app.domain.states import CaseState, EvidenceType
from app.domain.transitions import owner_role_for_state, validate_transition
from app.schemas.cases import (
    AdvanceCaseRequest,
    AssignCaseRequest,
    CaseDetailsResponse,
    CurvePoint,
    PriorityQueueItem,
    PriorityQueueResponse,
    ShapDriverItem,
    ShapPayload,
    SummaryPayload,
)
from app.services.events import get_case_timeline, record_event
from app.services.inference import get_loaded_models, score_case

logger = logging.getLogger(__name__)

router = APIRouter(tags=["cases"])


def _latest_risk(db: Session, case_id: str) -> RiskScore | None:
    return db.scalar(
        select(RiskScore)
        .where(RiskScore.case_id == case_id)
        .order_by(RiskScore.at.desc())
    )


def _has_pending_approval(db: Session, case_id: str) -> PendingApproval | None:
    return db.scalar(
        select(PendingApproval).where(
            PendingApproval.case_id == case_id,
            PendingApproval.status == "pending",
        )
    )


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
    page_size: Annotated[int, Query(ge=1, le=50)] = 25,
    sort: str = "priority_desc",
) -> PriorityQueueResponse:
    """Return filtered, priority-sorted cases for the current sandbox."""
    sb = ctx.sandbox
    clock = clock_for_sandbox(sb)

    cases = list(db.scalars(select(Case).where(Case.sandbox_id == sb.id)))
    patients_by_id = {
        p.id: p for p in db.scalars(select(Patient).where(Patient.sandbox_id == sb.id))
    }
    pending_case_ids = set(
        db.scalars(
            select(PendingApproval.case_id).where(
                PendingApproval.sandbox_id == sb.id,
                PendingApproval.status == "pending",
            )
        )
    )
    risks_by_case: dict[str, float] = {}
    for r in db.scalars(
        select(RiskScore)
        .where(RiskScore.sandbox_id == sb.id)
        .order_by(RiskScore.at.asc())
    ):
        risks_by_case[r.case_id] = float(r.p_dropoff)

    items: list[PriorityQueueItem] = []
    for c in cases:
        if state and c.state != state:
            continue
        if owner_role and c.owner_role != owner_role:
            continue
        if unassigned is True and c.owner_id is not None:
            continue
        if unassigned is False and c.owner_id is None:
            continue
        if rejected is True and c.state != CaseState.REJECTED.value:
            continue
        if rejected is False and c.state == CaseState.REJECTED.value:
            continue

        c_needs_app = c.id in pending_case_ids
        if needs_approval is True and not c_needs_app:
            continue
        if needs_approval is False and c_needs_app:
            continue

        c_overdue = is_overdue(c.state, c.state_entered_at, c.urgency_tier, clock=clock)
        if overdue is True and not c_overdue:
            continue
        if overdue is False and c_overdue:
            continue

        p_drop = risks_by_case.get(c.id, 0.25)
        press = sla_pressure(c.state, c.state_entered_at, c.urgency_tier, clock=clock)
        prio = round(
            compute_case_priority(c.urgency_tier, p_drop, press)
            if c.state != CaseState.CLOSED.value
            else 0.0,
            4,
        )
        due = sla_due_at(c.state, c.state_entered_at, c.urgency_tier)
        rem = hours_remaining(c.state, c.state_entered_at, c.urgency_tier, clock=clock)
        pat = patients_by_id.get(c.patient_id)

        items.append(
            PriorityQueueItem(
                case_id=c.id,
                patient_alias=pat.alias if pat else c.patient_id,
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

    reverse = sort != "priority_asc"
    items.sort(key=lambda x: (x.priority, x.p_dropoff, x.case_id), reverse=reverse)
    total = len(items)
    start = (page - 1) * page_size
    paged = items[start : start + page_size]

    return PriorityQueueResponse(
        items=paged,
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/cases/{case_id}/details", response_model=CaseDetailsResponse)
def get_case_details(
    case_id: str,
    db: DbSession,
    ctx: SandboxCtx,
) -> CaseDetailsResponse:
    """Return full case details, timeline, risk, SHAP, survival vs KM curves, and threads."""
    sb = ctx.sandbox
    clock = clock_for_sandbox(sb)

    c = db.scalar(select(Case).where(Case.id == case_id, Case.sandbox_id == sb.id))
    if c is None:
        raise AppError(404, "case_not_found", f"Case '{case_id}' not found in sandbox.")

    pat = db.scalar(select(Patient).where(Patient.id == c.patient_id))
    if pat is None:
        raise AppError(404, "patient_not_found", "Patient record not found.")

    timeline = get_case_timeline(db, c.id)
    r = _latest_risk(db, c.id)
    bundle = get_loaded_models()
    km_raw = bundle.get("km_curve", [])

    if r is None:
        # Compute on the fly if missing
        scored = score_case(
            {
                "screening_type": c.screening_type,
                "severity_grade": c.severity_grade,
                "urgent_flag": 1 if c.urgency_tier == 1 else 0,
                "finding_to_order_days": c.finding_to_order_days,
                "prior_noshow_count": pat.prior_noshow_count,
                "prior_noshow_ratio": pat.prior_noshow_ratio,
                "days_since_last_encounter": pat.days_since_last_encounter,
                "scheduling_lead_time": c.scheduling_lead_time,
                "distance_miles": pat.distance_miles,
                "insurance_category": pat.insurance,
                "patient_age": pat.age,
                "preferred_language": pat.language,
                "digital_portal_active": 1 if pat.portal_active else 0,
                "stage": c.state if c.state != "CLOSED" else "TREATMENT_OR_SURVEILLANCE",
                "days_in_stage": hours_in_state(c.state_entered_at, clock=clock) / 24.0,
                "contact_attempts": c.contact_attempts,
                "acknowledged_flag": 1 if c.acknowledged else 0,
            }
        )
        risk_dict = {
            "stage": scored["stage"],
            "p_dropoff": scored["p_dropoff"],
            "median_days": scored["median_days"],
            "p_open_30": scored["p_open_30"],
            "p_open_60": scored["p_open_60"],
            "p_open_90": scored["p_open_90"],
            "model_version": scored["model_version"],
        }
        shap_raw = scored["shap"]
        surv_raw = scored["survival_curve"]
    else:
        risk_dict = {
            "stage": r.stage,
            "p_dropoff": r.p_dropoff,
            "median_days": r.median_days,
            "p_open_30": r.p_open_30,
            "p_open_60": r.p_open_60,
            "p_open_90": r.p_open_90,
            "model_version": r.model_version,
        }
        shap_raw = r.shap
        surv_raw = r.survival_curve

    lo_summary = db.scalar(
        select(LLMOutput)
        .where(LLMOutput.case_id == c.id, LLMOutput.kind == "case_summary")
        .order_by(LLMOutput.at.desc())
    )
    if lo_summary is not None:
        out_s = lo_summary.output
        summary_payload = SummaryPayload(
            lines=list(out_s.get("summary_lines", [])),
            next_step=str(out_s.get("next_step", "")),
            cited_drivers=list(out_s.get("cited_drivers", [])),
            ads=round(float(lo_summary.ads or 0.0), 4),
            source=lo_summary.source,
        )
    else:
        pos_feats = [d["feature"] for d in shap_raw.get("top_positive", [])[:3]]
        summary_payload = SummaryPayload(
            lines=[
                f"Case {c.id} ({c.screening_type}) is in {c.state}.",
                f"Estimated drop-off probability is {int(round(risk_dict['p_dropoff'] * 100))}%.",
            ],
            next_step="Complete current stage action before SLA deadline.",
            cited_drivers=pos_feats,
            ads=0.0,
            source="template",
        )

    msgs = [
        {
            "id": m.id,
            "channel": m.channel,
            "language": m.language,
            "body": m.body,
            "direction": m.direction,
            "status": m.status,
            "teachback_label": m.teachback_label,
            "at": m.at.isoformat(),
        }
        for m in db.scalars(
            select(Message).where(Message.case_id == c.id).order_by(Message.at.asc())
        )
    ]

    ref = db.scalar(
        select(Referral).where(Referral.case_id == c.id).order_by(Referral.created_at.desc())
    )
    referral_dict = (
        {
            "id": ref.id,
            "from_org": ref.from_org,
            "to_org": ref.to_org,
            "status": ref.status,
            "reason_code": ref.reason_code,
            "sbar": ref.sbar,
            "created_at": ref.created_at.isoformat(),
            "decided_at": ref.decided_at.isoformat() if ref.decided_at else None,
        }
        if ref
        else None
    )

    consults_list = [
        {
            "id": con.id,
            "kind": con.kind,
            "status": con.status,
            "thread": con.thread,
            "created_at": con.created_at.isoformat(),
        }
        for con in db.scalars(
            select(Consult).where(Consult.case_id == c.id).order_by(Consult.created_at.asc())
        )
    ]

    pa = _has_pending_approval(db, c.id)
    pa_dict = (
        {
            "id": pa.id,
            "action_type": pa.action_type,
            "payload": pa.payload,
            "reasons": pa.reasons,
            "status": pa.status,
            "at": pa.at.isoformat(),
        }
        if pa
        else None
    )

    cl = db.scalar(select(Closure).where(Closure.case_id == c.id))
    cl_dict = (
        {
            "id": cl.id,
            "kind": cl.kind,
            "evidence_type": cl.evidence_type,
            "override_by": cl.override_by,
            "override_reason": cl.override_reason,
            "at": cl.at.isoformat(),
        }
        if cl
        else None
    )

    due = sla_due_at(c.state, c.state_entered_at, c.urgency_tier)
    rem = hours_remaining(c.state, c.state_entered_at, c.urgency_tier, clock=clock)
    c_overdue = is_overdue(c.state, c.state_entered_at, c.urgency_tier, clock=clock)
    press = sla_pressure(c.state, c.state_entered_at, c.urgency_tier, clock=clock)
    prio = round(
        compute_case_priority(c.urgency_tier, float(risk_dict["p_dropoff"]), press)
        if c.state != CaseState.CLOSED.value
        else 0.0,
        4,
    )

    # Extract plain patient token from seed/ingest event payload if present
    pt_plain = f"pt-{sb.id[:8]}-{c.id.split('-')[-1]}"
    evidences_list = [
        {
            "id": e.id,
            "type": e.type,
            "ref": e.ref,
            "created_by": e.created_by,
            "at": e.at.isoformat(),
        }
        for e in db.scalars(select(Evidence).where(Evidence.case_id == c.id))
    ]

    return CaseDetailsResponse(
        case={
            "id": c.id,
            "patient_id": c.patient_id,
            "screening_type": c.screening_type,
            "severity_grade": c.severity_grade,
            "urgency_tier": c.urgency_tier,
            "state": c.state,
            "state_entered_at": c.state_entered_at.isoformat(),
            "owner_role": c.owner_role,
            "owner_id": c.owner_id,
            "escalated": c.escalated,
            "overdue": c_overdue,
            "sla_due_at": due.isoformat() if due else None,
            "hours_remaining": round(rem, 2) if rem is not None else None,
            "priority": prio,
            "finding_to_order_days": c.finding_to_order_days,
            "scheduling_lead_time": c.scheduling_lead_time,
            "contact_attempts": c.contact_attempts,
            "acknowledged": c.acknowledged,
            "patient_token": pt_plain,
            "evidence": evidences_list,
            "created_at": c.created_at.isoformat(),
            "closed_at": c.closed_at.isoformat() if c.closed_at else None,
        },
        patient={
            "id": pat.id,
            "alias": pat.alias,
            "age": pat.age,
            "language": pat.language,
            "insurance": pat.insurance,
            "distance_miles": pat.distance_miles,
            "portal_active": pat.portal_active,
            "prior_noshow_count": pat.prior_noshow_count,
            "prior_noshow_ratio": pat.prior_noshow_ratio,
            "days_since_last_encounter": pat.days_since_last_encounter,
        },
        timeline=timeline,
        risk=risk_dict,
        shap=ShapPayload(
            top_positive=[ShapDriverItem(**d) for d in shap_raw.get("top_positive", [])],
            top_negative=[ShapDriverItem(**d) for d in shap_raw.get("top_negative", [])],
        ),
        survival_curve=[CurvePoint(**pt) for pt in surv_raw],
        km_curve=[CurvePoint(**pt) for pt in km_raw],
        summary=summary_payload,
        messages=msgs,
        referral=referral_dict,
        consults=consults_list,
        pending_approval=pa_dict,
        closure=cl_dict,
    )


@router.post("/cases/{case_id}/assign")
def assign_case_owner(
    case_id: str,
    body: AssignCaseRequest,
    db: DbSession,
    ctx: SandboxCtx,
) -> dict[str, Any]:
    """Assign or reassign owner_role and owner_id on a case and record OWNER_ASSIGNED event."""
    sb = ctx.sandbox
    clock = clock_for_sandbox(sb)
    c = db.scalar(select(Case).where(Case.id == case_id, Case.sandbox_id == sb.id))
    if c is None:
        raise AppError(404, "case_not_found", f"Case '{case_id}' not found.")

    if body.owner_role not in {"coordinator", "clinician"}:
        raise AppError(400, "invalid_owner_role", "owner_role must be coordinator or clinician.")

    c.owner_role = body.owner_role
    c.owner_id = body.owner_id.strip() or None
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
        at=clock(),
    )
    db.commit()
    return {"case_id": c.id, "owner_role": c.owner_role, "owner_id": c.owner_id}


@router.post("/cases/{case_id}/advance")
def advance_case_state(
    case_id: str,
    body: AdvanceCaseRequest,
    db: DbSession,
    ctx: SandboxCtx,
) -> dict[str, Any]:
    """Advance a case to `to_state` if transition and entry evidence are legal (409 otherwise)."""
    sb = ctx.sandbox
    clock = clock_for_sandbox(sb)
    now = clock()

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

    is_rebook = prev_state == CaseState.APPOINTMENT_BOOKED.value and (
        body.to_state == CaseState.APPOINTMENT_BOOKED.value
    )
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
        scored = score_case(
            {
                "screening_type": c.screening_type,
                "severity_grade": c.severity_grade,
                "urgent_flag": 1 if c.urgency_tier == 1 else 0,
                "finding_to_order_days": c.finding_to_order_days,
                "prior_noshow_count": pat.prior_noshow_count,
                "prior_noshow_ratio": pat.prior_noshow_ratio,
                "days_since_last_encounter": pat.days_since_last_encounter,
                "scheduling_lead_time": c.scheduling_lead_time,
                "distance_miles": pat.distance_miles,
                "insurance_category": pat.insurance,
                "patient_age": pat.age,
                "preferred_language": pat.language,
                "digital_portal_active": 1 if pat.portal_active else 0,
                "stage": c.state,
                "days_in_stage": 0.1,
                "contact_attempts": c.contact_attempts,
                "acknowledged_flag": 1 if c.acknowledged else 0,
            }
        )
        p_drop = float(scored["p_dropoff"])
        db.add(
            RiskScore(
                sandbox_id=sb.id,
                case_id=c.id,
                stage=c.state,
                p_dropoff=p_drop,
                median_days=float(scored["median_days"]),
                p_open_30=float(scored["p_open_30"]),
                p_open_60=float(scored["p_open_60"]),
                p_open_90=float(scored["p_open_90"]),
                shap=scored["shap"],
                survival_curve=scored["survival_curve"],
                model_version=str(scored["model_version"]),
                at=now,
            )
        )

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
def stream_case_events(
    case_id: str,
    token: str,
    db: DbSession,
) -> StreamingResponse:
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
    lines = (
        list(lo.output.get("summary_lines", []))
        if lo is not None
        else [f"Case {c.id} is in {c.state}."]
    )
    state_str = c.state
    esc_bool = bool(c.escalated)

    def _event_gen() -> Iterator[str]:
        status_payload = json.dumps({"case_id": case_id, "state": state_str, "escalated": esc_bool})
        yield f"event: status\ndata: {status_payload}\n\n"
        for line in lines:
            tok_payload = json.dumps({"text": line})
            yield f"event: token\ndata: {tok_payload}\n\n"
        done_payload = json.dumps({"case_id": case_id, "done": True})
        yield f"event: done\ndata: {done_payload}\n\n"

    return StreamingResponse(_event_gen(), media_type="text/event-stream")
