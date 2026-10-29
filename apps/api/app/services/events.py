"""Event formatting, append helpers, and case details assembly for CareLoop AI (M5)."""
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Case,
    CaseEvent,
    Closure,
    Consult,
    Evidence,
    LLMOutput,
    Message,
    Patient,
    PendingApproval,
    Referral,
    RiskScore,
    Sandbox,
)
from app.db.repo import append_case_event, clock_for_sandbox
from app.domain.priority import compute_case_priority
from app.domain.sla import hours_in_state, hours_remaining, is_overdue, sla_due_at, sla_pressure
from app.domain.states import CaseState
from app.schemas.cases import (
    CaseDetailsResponse,
    CurvePoint,
    ShapDriverItem,
    ShapPayload,
    SummaryPayload,
    TimelineEntry,
)
from app.services.inference import build_case_feature_dict, get_loaded_models, score_case

logger = logging.getLogger(__name__)
_RISK_KEYS = (
    "stage",
    "p_dropoff",
    "median_days",
    "p_open_30",
    "p_open_60",
    "p_open_90",
    "model_version",
)


def summarize_event(ev: CaseEvent) -> str:
    """Build a human-readable single-line summary for a CaseEvent."""
    et, p = ev.event_type, ev.payload
    if et == "CASE_ISSUED":
        return f"Screening result issued in state {ev.to_state} ({ev.actor_role})."
    if et == "STATE_CHANGED":
        return f"Transitioned from {ev.from_state} to {ev.to_state} by {ev.actor_role}."
    if et == "OWNER_ASSIGNED":
        owner = p.get("owner_id") or ev.actor_id or "unassigned"
        return f"Assigned to {p.get('owner_role', ev.actor_role)} ({owner})."
    if et == "SLA_BREACH":
        return f"SLA deadline breached in state {ev.from_state or ev.to_state}; case escalated."
    if et == "VISIT_MISSED_REBOOK_NEEDED":
        return "Patient missed scheduled appointment; priority rebooking required."
    if et == "MESSAGE_QUEUED":
        return f"Outreach message queued via {p.get('channel', 'portal')}."
    if et == "PATIENT_ACKNOWLEDGED":
        return "Patient acknowledged receipt of screening result."
    if et == "TEACHBACK_RECORDED":
        return f"Patient teach-back check recorded as '{p.get('label', 'unknown')}'."
    if et == "REFERRAL_CREATED":
        return f"Referral sent to {p.get('to_org', 'specialty clinic')}."
    if et == "REFERRAL_DECIDED":
        return f"Referral {p.get('decision', 'decided')} by clinician."
    if et == "CONSULT_CREATED":
        return f"Consultation thread opened ({p.get('kind', 'consult')})."
    if et == "CONSULT_REPLIED":
        return f"Consultation reply added by {ev.actor_role}."
    if et == "APPROVAL_DECIDED":
        return f"Human approval gate decision: {p.get('decision', 'decided')}."
    if et == "CASE_CLOSED":
        return f"Case closed ({p.get('kind', 'evidence')})."
    return f"{et} recorded by {ev.actor_role}."


def get_case_timeline(db: Session, case_id: str) -> list[TimelineEntry]:
    """Return chronologically ordered timeline entries for `case_id`."""
    stmt = select(CaseEvent).where(CaseEvent.case_id == case_id).order_by(CaseEvent.at.asc())
    return [
        TimelineEntry(
            at=r.at if r.at.tzinfo else r.at.replace(tzinfo=UTC),
            event_type=r.event_type,
            from_state=r.from_state,
            to_state=r.to_state,
            actor_role=r.actor_role,
            summary=summarize_event(r),
        )
        for r in db.scalars(stmt)
    ]


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


def build_case_details_response(
    db: Session, sb: Sandbox, c: Case, pat: Patient
) -> CaseDetailsResponse:
    """Assemble full CaseDetailsResponse for GET /cases/{id}/details."""
    clock = clock_for_sandbox(sb)
    r = db.scalar(select(RiskScore).where(RiskScore.case_id == c.id).order_by(RiskScore.at.desc()))
    km_raw = get_loaded_models().get("km_curve", [])
    if r is None:
        days_st = hours_in_state(c.state_entered_at, clock=clock) / 24.0
        scored = score_case(build_case_feature_dict(c, pat, days_st))
        risk_dict = {k: scored[k] for k in _RISK_KEYS}
        shap_raw, surv_raw = scored["shap"], scored["survival_curve"]
    else:
        risk_dict = {k: getattr(r, k) for k in _RISK_KEYS}
        shap_raw, surv_raw = r.shap, r.survival_curve

    lo = db.scalar(
        select(LLMOutput)
        .where(LLMOutput.case_id == c.id, LLMOutput.kind == "case_summary")
        .order_by(LLMOutput.at.desc())
    )
    summary_payload = (
        SummaryPayload(
            lines=list(lo.output.get("summary_lines", [])),
            next_step=str(lo.output.get("next_step", "")),
            cited_drivers=list(lo.output.get("cited_drivers", [])),
            ads=round(float(lo.ads or 0.0), 4),
            source=lo.source,
        )
        if lo is not None
        else SummaryPayload(
            lines=[
                f"Case {c.id} ({c.screening_type}) is in {c.state}.",
                f"Estimated drop-off probability is {int(round(risk_dict['p_dropoff'] * 100))}%.",
            ],
            next_step="Complete current stage action before SLA deadline.",
            cited_drivers=[d["feature"] for d in shap_raw.get("top_positive", [])[:3]],
            ads=0.0,
            source="template",
        )
    )

    ref = db.scalar(
        select(Referral).where(Referral.case_id == c.id).order_by(Referral.created_at.desc())
    )
    pa = db.scalar(
        select(PendingApproval).where(
            PendingApproval.case_id == c.id, PendingApproval.status == "pending"
        )
    )
    cl = db.scalar(select(Closure).where(Closure.case_id == c.id))
    due = sla_due_at(c.state, c.state_entered_at, c.urgency_tier)
    rem = hours_remaining(c.state, c.state_entered_at, c.urgency_tier, clock=clock)
    press = sla_pressure(c.state, c.state_entered_at, c.urgency_tier, clock=clock)
    prio = round(
        compute_case_priority(c.urgency_tier, float(risk_dict["p_dropoff"]), press)
        if c.state != CaseState.CLOSED.value
        else 0.0,
        4,
    )

    r_fields = ("id", "from_org", "to_org", "status", "reason_code", "sbar")
    pa_fields = ("id", "action_type", "payload", "reasons", "status")
    cl_fields = ("id", "kind", "evidence_type", "override_by", "override_reason")
    pat_fields = (
        "id",
        "alias",
        "age",
        "language",
        "insurance",
        "distance_miles",
        "portal_active",
        "prior_noshow_count",
        "prior_noshow_ratio",
        "days_since_last_encounter",
    )

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
            "overdue": is_overdue(c.state, c.state_entered_at, c.urgency_tier, clock=clock),
            "sla_due_at": due.isoformat() if due else None,
            "hours_remaining": round(rem, 2) if rem is not None else None,
            "priority": prio,
            "finding_to_order_days": c.finding_to_order_days,
            "scheduling_lead_time": c.scheduling_lead_time,
            "contact_attempts": c.contact_attempts,
            "acknowledged": c.acknowledged,
            "patient_token": f"pt-{sb.id[:8]}-{c.id.split('-')[-1]}",
            "evidence": [
                {
                    "id": e.id,
                    "type": e.type,
                    "ref": e.ref,
                    "created_by": e.created_by,
                    "at": e.at.isoformat(),
                }
                for e in db.scalars(select(Evidence).where(Evidence.case_id == c.id))
            ],
            "created_at": c.created_at.isoformat(),
            "closed_at": c.closed_at.isoformat() if c.closed_at else None,
        },
        patient={k: getattr(pat, k) for k in pat_fields},
        timeline=get_case_timeline(db, c.id),
        risk=risk_dict,
        shap=ShapPayload(
            top_positive=[ShapDriverItem(**d) for d in shap_raw.get("top_positive", [])],
            top_negative=[ShapDriverItem(**d) for d in shap_raw.get("top_negative", [])],
        ),
        survival_curve=[CurvePoint(**pt) for pt in surv_raw],
        km_curve=[CurvePoint(**pt) for pt in km_raw],
        summary=summary_payload,
        messages=[
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
        ],
        referral=(
            {
                **{k: getattr(ref, k) for k in r_fields},
                "created_at": ref.created_at.isoformat(),
                "decided_at": ref.decided_at.isoformat() if ref.decided_at else None,
            }
            if ref
            else None
        ),
        consults=[
            {
                **{k: getattr(con, k) for k in ("id", "kind", "status", "thread")},
                "created_at": con.created_at.isoformat(),
            }
            for con in db.scalars(
                select(Consult).where(Consult.case_id == c.id).order_by(Consult.created_at.asc())
            )
        ],
        pending_approval=(
            {**{k: getattr(pa, k) for k in pa_fields}, "at": pa.at.isoformat()} if pa else None
        ),
        closure=(
            {**{k: getattr(cl, k) for k in cl_fields}, "at": cl.at.isoformat()} if cl else None
        ),
    )
