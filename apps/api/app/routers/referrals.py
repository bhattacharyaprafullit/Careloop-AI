"""Referrals router: create referral with SBAR, list referrals, accept/reject decision (M8)."""
import logging
from typing import Any

from fastapi import APIRouter, status
from sqlalchemy import select

from app.db.models import Case, Patient, Referral
from app.deps import DbSession, SandboxCtx
from app.schemas.patient import (
    CreateReferralRequest,
    CreateReferralResponse,
    ReferralDecisionRequest,
)
from app.services.referral_service import create_referral_with_sbar, decide_referral

logger = logging.getLogger(__name__)

router = APIRouter(tags=["referrals"])


@router.get("/referrals")
def list_referrals(
    db: DbSession,
    ctx: SandboxCtx,
    status_filter: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """List referrals in the current sandbox for the clinician workspace."""
    sb = ctx.sandbox
    stmt = select(Referral).where(Referral.sandbox_id == sb.id)
    if status_filter:
        stmt = stmt.where(Referral.status == status_filter)
    rows = list(db.scalars(stmt.order_by(Referral.created_at.desc())))

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
                "urgency_tier": c.urgency_tier if c else 2,
                "from_org": r.from_org,
                "to_org": r.to_org,
                "status": r.status,
                "reason_code": r.reason_code,
                "sbar": r.sbar,
                "created_at": r.created_at.isoformat(),
                "decided_at": r.decided_at.isoformat() if r.decided_at else None,
            }
        )
    return {"items": items}


@router.post(
    "/referrals",
    response_model=CreateReferralResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_referral(
    body: CreateReferralRequest,
    db: DbSession,
    ctx: SandboxCtx,
) -> CreateReferralResponse:
    """Create a referral with a validated SBAR note and advance case to REFERRAL_SENT."""
    return create_referral_with_sbar(
        db,
        sb=ctx.sandbox,
        actor_role=ctx.role,
        case_id=body.case_id,
        to_org=body.to_org,
    )


@router.post("/referrals/{referral_id}/decision")
def post_referral_decision(
    referral_id: str,
    body: ReferralDecisionRequest,
    db: DbSession,
    ctx: SandboxCtx,
) -> dict[str, Any]:
    """Accept or reject a referral (rejection requires reason_code and re-queues to coordinator)."""
    return decide_referral(
        db,
        sb=ctx.sandbox,
        actor_role=ctx.role,
        referral_id=referral_id,
        decision=body.decision,
        reason_code=body.reason_code,
    )
