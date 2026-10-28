"""Referral hand-off service: create referral with SBAR note and accept/reject decision (M8)."""
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import (
    Case,
    DelayReason,
    Evidence,
    PendingApproval,
    Referral,
    RiskScore,
    Sandbox,
)
from app.db.repo import clock_for_sandbox
from app.domain.states import ActionType, CaseState, EvidenceType, LLMKind, ReasonCode
from app.domain.transitions import owner_role_for_state
from app.llm.client import generate_validated_llm_output
from app.schemas.patient import CreateReferralResponse
from app.services.events import record_event

logger = logging.getLogger(__name__)


def create_referral_with_sbar(
    db: Session,
    *,
    sb: Sandbox,
    actor_role: str,
    case_id: str,
    to_org: str,
) -> CreateReferralResponse:
    """Create a Referral with a validated SBAR note and transition case to REFERRAL_SENT."""
    now = clock_for_sandbox(sb)()
    c = db.scalar(select(Case).where(Case.id == case_id, Case.sandbox_id == sb.id))
    if c is None:
        raise AppError(404, "case_not_found", f"Case '{case_id}' not found.")

    r_score = db.scalar(
        select(RiskScore)
        .where(RiskScore.case_id == c.id)
        .order_by(RiskScore.at.desc())
    )
    pct = int(round(float(r_score.p_dropoff if r_score else 0.25) * 100))

    sbar_facts = {
        "screening_type": c.screening_type,
        "severity_grade": c.severity_grade,
        "urgency_tier": c.urgency_tier,
        "finding_to_order_days": int(round(c.finding_to_order_days)),
        "state": CaseState.REFERRAL_SENT.value,
        "p_dropoff_percent": pct,
    }
    llm_sbar = generate_validated_llm_output(
        LLMKind.SBAR_NOTE.value,
        sbar_facts,
        db=db,
        sandbox_id=sb.id,
        case_id=c.id,
    )
    sbar_dict: dict[str, str] = {
        k: str(v) for k, v in llm_sbar["output"].items()
    }

    ref = Referral(
        sandbox_id=sb.id,
        case_id=c.id,
        from_org="Community Primary Care Screening Clinic",
        to_org=to_org.strip() or "Regional Diagnostic Specialty Center",
        status="sent",
        sbar=sbar_dict,
        created_at=now,
    )
    db.add(ref)
    db.flush()

    db.add(
        Evidence(
            sandbox_id=sb.id,
            case_id=c.id,
            type=EvidenceType.REFERRAL_CREATED.value,
            ref=ref.id,
            created_by=actor_role,
            at=now,
        )
    )

    prev_state = c.state
    if c.state in {
        CaseState.ACKNOWLEDGED.value,
        CaseState.CONFIRMATORY_PENDING.value,
        CaseState.REJECTED.value,
    }:
        c.state = CaseState.REFERRAL_SENT.value
        c.state_entered_at = now
        c.owner_role = owner_role_for_state(CaseState.REFERRAL_SENT.value)

    record_event(
        db,
        sandbox_id=sb.id,
        case_id=c.id,
        event_type="REFERRAL_CREATED",
        actor_role=actor_role,
        from_state=prev_state,
        to_state=c.state,
        payload={"referral_id": ref.id, "to_org": ref.to_org},
        at=now,
    )
    db.commit()
    return CreateReferralResponse(referral_id=ref.id, sbar=sbar_dict)


def decide_referral(
    db: Session,
    *,
    sb: Sandbox,
    actor_role: str,
    referral_id: str,
    decision: str,
    reason_code: str | None = None,
) -> dict[str, Any]:
    """Accept or reject a referral. Rejection re-queues to coordinator in REJECTED and escalates."""
    now = clock_for_sandbox(sb)()
    ref = db.scalar(
        select(Referral).where(Referral.id == referral_id, Referral.sandbox_id == sb.id)
    )
    if ref is None:
        raise AppError(404, "referral_not_found", f"Referral '{referral_id}' not found.")

    c = db.scalar(select(Case).where(Case.id == ref.case_id, Case.sandbox_id == sb.id))
    if c is None:
        raise AppError(404, "case_not_found", "Associated case not found.")

    if decision not in {"accept", "reject"}:
        raise AppError(400, "invalid_decision", "decision must be 'accept' or 'reject'.")

    prev_state = c.state
    if decision == "accept":
        ref.status = "accepted"
        ref.decided_at = now
        db.add(
            Evidence(
                sandbox_id=sb.id,
                case_id=c.id,
                type=EvidenceType.REFERRAL_ACCEPTED.value,
                ref=ref.id,
                created_by=actor_role,
                at=now,
            )
        )
        c.state = CaseState.REFERRAL_ACCEPTED.value
        c.state_entered_at = now
        c.owner_role = owner_role_for_state(CaseState.REFERRAL_ACCEPTED.value)
    else:
        if not reason_code or not reason_code.strip():
            raise AppError(
                400,
                "reason_code_required",
                "reason_code is required when rejecting a referral.",
            )
        valid_codes = {r.value for r in ReasonCode}
        clean_code = (
            reason_code.strip()
            if reason_code.strip() in valid_codes
            else ReasonCode.REFERRAL_REJECTED_CAPACITY.value
        )
        ref.status = "rejected"
        ref.reason_code = clean_code
        ref.decided_at = now
        db.add(
            Evidence(
                sandbox_id=sb.id,
                case_id=c.id,
                type=EvidenceType.REFERRAL_REJECTED.value,
                ref=ref.id,
                created_by=actor_role,
                at=now,
            )
        )
        db.add(
            DelayReason(
                sandbox_id=sb.id,
                case_id=c.id,
                code=clean_code,
                proposed_by="human",
                confirmed=True,
                at=now,
            )
        )
        c.state = CaseState.REJECTED.value
        c.state_entered_at = now
        c.owner_role = owner_role_for_state(CaseState.REJECTED.value)
        c.escalated = True

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
                    action_type=ActionType.REASSIGN_OWNER.value,
                    payload={"channel": "sms", "owner_id": "coord-1"},
                    reasons=["referral_rejected", clean_code],
                    status="pending",
                    at=now,
                )
            )

    record_event(
        db,
        sandbox_id=sb.id,
        case_id=c.id,
        event_type="REFERRAL_DECIDED",
        actor_role=actor_role,
        from_state=prev_state,
        to_state=c.state,
        payload={
            "referral_id": ref.id,
            "decision": decision,
            "reason_code": ref.reason_code,
        },
        at=now,
    )
    db.commit()
    return {
        "referral_id": ref.id,
        "case_id": c.id,
        "status": ref.status,
        "state": c.state,
        "owner_role": c.owner_role,
        "escalated": c.escalated,
    }
