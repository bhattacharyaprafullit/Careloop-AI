"""POST /api/v1/screenings/ingest endpoint (M5)."""
import logging
import uuid

from fastapi import APIRouter, status
from sqlalchemy import select

from app.core.errors import AppError
from app.db.models import Case, Patient, PendingApproval, RiskScore
from app.db.repo import clock_for_sandbox, hash_token
from app.deps import DbSession, SandboxCtx
from app.domain.priority import compute_case_priority, evaluate_escalation
from app.domain.sla import sla_pressure
from app.domain.states import CaseState, ScreeningType
from app.domain.transitions import owner_role_for_state
from app.schemas.cases import (
    IngestPatientInput,
    ScreeningIngestRequest,
    ScreeningIngestResponse,
)
from app.services.events import record_event
from app.services.inference import score_case
from app.services.sandbox import enforce_sandbox_case_cap

logger = logging.getLogger(__name__)

router = APIRouter(tags=["screenings"])


@router.post(
    "/screenings/ingest",
    response_model=ScreeningIngestResponse,
    status_code=status.HTTP_201_CREATED,
)
def ingest_screening(
    body: ScreeningIngestRequest,
    db: DbSession,
    ctx: SandboxCtx,
) -> ScreeningIngestResponse:
    """Ingest a new abnormal screening result, score drop-off & survival, and route."""
    sb = ctx.sandbox
    enforce_sandbox_case_cap(db, sb.id)
    clock = clock_for_sandbox(sb)
    now = clock()

    if body.screening_type not in {s.value for s in ScreeningType}:
        raise AppError(
            400,
            "invalid_screening_type",
            "screening_type must be FIT, MAMMOGRAPHY, or PAP_HPV.",
        )

    pat: Patient | None = None
    if body.patient_id:
        pat = db.scalar(
            select(Patient).where(
                Patient.id == body.patient_id, Patient.sandbox_id == sb.id
            )
        )
        if pat is None:
            raise AppError(404, "patient_not_found", f"Patient '{body.patient_id}' not found.")
    else:
        p_in = body.patient or IngestPatientInput()
        pid = p_in.id or f"{sb.id[:8]}-pat-{uuid.uuid4().hex[:6]}"
        pat = Patient(
            id=pid,
            sandbox_id=sb.id,
            alias=p_in.alias,
            age=p_in.age,
            language=p_in.language,
            insurance=p_in.insurance,
            distance_miles=p_in.distance_miles,
            portal_active=p_in.portal_active,
            prior_noshow_count=p_in.prior_noshow_count,
            prior_noshow_ratio=p_in.prior_noshow_ratio,
            days_since_last_encounter=p_in.days_since_last_encounter,
        )
        db.add(pat)
        db.flush()

    urgency_tier = 1 if body.urgent_flag or body.severity_grade >= 4 else (
        2 if body.severity_grade >= 2 else 3
    )
    suffix = uuid.uuid4().hex[:6]
    case_id = f"{sb.id[:8]}-case-{suffix}"
    pt_plain = f"pt-{sb.id[:8]}-{suffix}"
    pt_hash = hash_token(pt_plain)

    scored = score_case(
        {
            "screening_type": body.screening_type,
            "severity_grade": body.severity_grade,
            "urgent_flag": 1 if urgency_tier == 1 else 0,
            "finding_to_order_days": body.finding_to_order_days,
            "prior_noshow_count": pat.prior_noshow_count,
            "prior_noshow_ratio": pat.prior_noshow_ratio,
            "days_since_last_encounter": pat.days_since_last_encounter,
            "scheduling_lead_time": body.scheduling_lead_time,
            "distance_miles": pat.distance_miles,
            "insurance_category": pat.insurance,
            "patient_age": pat.age,
            "preferred_language": pat.language,
            "digital_portal_active": 1 if pat.portal_active else 0,
            "stage": CaseState.RESULT_ISSUED.value,
            "days_in_stage": 0.0,
            "contact_attempts": 0,
            "acknowledged_flag": 0,
        }
    )
    p_drop = float(scored["p_dropoff"])
    esc, reasons = evaluate_escalation(
        urgency_tier=urgency_tier,
        overdue=False,
        p_dropoff=p_drop,
    )

    new_case = Case(
        id=case_id,
        sandbox_id=sb.id,
        patient_id=pat.id,
        screening_type=body.screening_type,
        severity_grade=body.severity_grade,
        urgency_tier=urgency_tier,
        state=CaseState.RESULT_ISSUED.value,
        state_entered_at=now,
        owner_role=owner_role_for_state(CaseState.RESULT_ISSUED.value),
        owner_id=None,
        escalated=esc,
        finding_to_order_days=body.finding_to_order_days,
        scheduling_lead_time=body.scheduling_lead_time,
        contact_attempts=0,
        acknowledged=False,
        patient_token_hash=pt_hash,
        created_at=now,
        closed_at=None,
    )
    db.add(new_case)
    db.add(
        RiskScore(
            sandbox_id=sb.id,
            case_id=case_id,
            stage=CaseState.RESULT_ISSUED.value,
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
    record_event(
        db,
        sandbox_id=sb.id,
        case_id=case_id,
        event_type="CASE_ISSUED",
        actor_role=ctx.role,
        from_state=None,
        to_state=CaseState.RESULT_ISSUED.value,
        payload={"patient_token": pt_plain, "screening_type": body.screening_type},
        at=now,
    )

    if esc:
        db.add(
            PendingApproval(
                sandbox_id=sb.id,
                case_id=case_id,
                action_type="create_navigator_task",
                payload={"channel": "sms", "owner_id": "coord-1"},
                reasons=reasons,
                status="pending",
                at=now,
            )
        )

    press = sla_pressure(CaseState.RESULT_ISSUED.value, now, urgency_tier, clock=clock)
    prio = round(compute_case_priority(urgency_tier, p_drop, press), 4)
    db.commit()

    return ScreeningIngestResponse(
        case_id=case_id,
        state=new_case.state,
        p_dropoff=p_drop,
        priority=prio,
        escalated=esc,
    )
