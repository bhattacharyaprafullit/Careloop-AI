"""Consults router: create and reply to cross-provider consult threads (M8)."""
import logging
from typing import Any

from fastapi import APIRouter, status
from sqlalchemy import select

from app.db.models import Case, Consult, Patient
from app.deps import DbSession, SandboxCtx
from app.schemas.patient import CreateConsultRequest, ReplyConsultRequest
from app.services.consult_service import create_consult_thread, reply_to_consult

logger = logging.getLogger(__name__)

router = APIRouter(tags=["consults"])


@router.get("/consults")
def list_consults(
    db: DbSession,
    ctx: SandboxCtx,
) -> dict[str, list[dict[str, Any]]]:
    """List consult threads in the current sandbox."""
    sb = ctx.sandbox
    rows = list(
        db.scalars(
            select(Consult)
            .where(Consult.sandbox_id == sb.id)
            .order_by(Consult.created_at.desc())
        )
    )
    cases_by_id = {
        c.id: c for c in db.scalars(select(Case).where(Case.sandbox_id == sb.id))
    }
    patients_by_id = {
        p.id: p for p in db.scalars(select(Patient).where(Patient.sandbox_id == sb.id))
    }
    items: list[dict[str, Any]] = []
    for con in rows:
        c = cases_by_id.get(con.case_id)
        pat = patients_by_id.get(c.patient_id) if c else None
        items.append(
            {
                "id": con.id,
                "case_id": con.case_id,
                "patient_alias": pat.alias if pat else con.case_id,
                "screening_type": c.screening_type if c else "FIT",
                "kind": con.kind,
                "status": con.status,
                "thread": con.thread,
                "created_at": con.created_at.isoformat(),
            }
        )
    return {"items": items}


@router.post("/consults", status_code=status.HTTP_201_CREATED)
def post_consult(
    body: CreateConsultRequest,
    db: DbSession,
    ctx: SandboxCtx,
) -> dict[str, Any]:
    """Create a patient_to_clinician or clinician_to_clinician consult thread."""
    return create_consult_thread(
        db,
        sb=ctx.sandbox,
        actor_role=ctx.role,
        case_id=body.case_id,
        kind=body.kind,
        message=body.message,
    )


@router.post("/consults/{consult_id}/reply")
def post_consult_reply(
    consult_id: str,
    body: ReplyConsultRequest,
    db: DbSession,
    ctx: SandboxCtx,
) -> dict[str, Any]:
    """Reply to a consult thread and mark it answered."""
    return reply_to_consult(
        db,
        sb=ctx.sandbox,
        actor_role=ctx.role,
        consult_id=consult_id,
        message=body.message,
    )
