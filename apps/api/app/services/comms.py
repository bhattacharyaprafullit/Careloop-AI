"""Patient communication, acknowledgement, and teach-back service (M8)."""
import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import Case, Evidence, Message, Patient, PendingApproval, Sandbox
from app.db.repo import clock_for_sandbox, hash_token
from app.domain.sla import sla_due_at
from app.domain.states import (
    ActionType,
    CaseState,
    EvidenceType,
    LLMKind,
    TeachBackLabel,
    resolve_language,
)
from app.domain.transitions import owner_role_for_state
from app.llm.client import generate_validated_llm_output
from app.schemas.patient import (
    PatientPortalResponse,
    PatientStepItem,
    TeachBackResponse,
)
from app.services.events import record_event

logger = logging.getLogger(__name__)

PORTAL_TEXT_BY_LANG: dict[str, dict[str, str]] = {
    "en": {
        "status_open": "Your screening follow-up is active.",
        "status_closed": "Your screening follow-up is complete.",
        "step_1": "Result issued & notification sent",
        "step_2": "Result acknowledged & understood",
        "step_3": "Follow-up visit & care plan completed",
    },
    "hi": {
        "status_open": "आपकी जाँच का फॉलो-अप सक्रिय है।",
        "status_closed": "आपकी जाँच का फॉलो-अप पूरा हो गया है।",
        "step_1": "परिणाम जारी और सूचना भेजी गई",
        "step_2": "परिणाम प्राप्त और समझा गया",
        "step_3": "फॉलो-अप अपॉइंटमेंट और देखभाल योजना पूरी",
    },
    "es": {
        "status_open": "Su seguimiento de evaluación está activo.",
        "status_closed": "Su seguimiento de evaluación está completo.",
        "step_1": "Resultado emitido y notificación enviada",
        "step_2": "Resultado confirmado y comprendido",
        "step_3": "Cita de seguimiento y plan completados",
    },
}


def _find_case_by_patient_token(db: Session, token: str) -> tuple[Case, Patient, Sandbox]:
    th = hash_token(token.strip())
    c = db.scalar(select(Case).where(Case.patient_token_hash == th))
    if c is None:
        raise AppError(404, "patient_token_not_found", "Invalid patient link token.")
    pat = db.scalar(select(Patient).where(Patient.id == c.patient_id))
    sb = db.scalar(select(Sandbox).where(Sandbox.id == c.sandbox_id))
    if pat is None or sb is None:
        raise AppError(404, "patient_not_found", "Patient context not found.")
    return c, pat, sb


def get_patient_portal_view(
    db: Session, token: str, lang_override: str | None = None
) -> PatientPortalResponse:
    """Build localized 3-step patient portal view in en, hi, or es."""
    c, pat, sb = _find_case_by_patient_token(db, token)
    clock = clock_for_sandbox(sb)
    now = clock()

    raw_lang = lang_override or pat.language
    lang, is_fallback = resolve_language(raw_lang)
    t_map = PORTAL_TEXT_BY_LANG[lang]

    due = sla_due_at(c.state, c.state_entered_at, c.urgency_tier)
    due_str = (due or (now + timedelta(days=5))).strftime("%Y-%m-%d")

    msg_facts = {
        "language": lang,
        "test_name": c.screening_type,
        "urgency_code": "soon" if c.urgency_tier == 1 else "routine",
        "due_date": due_str,
        "reply_instruction": "Reply in the portal by clicking 'I understand'.",
    }
    llm_msg = generate_validated_llm_output(
        LLMKind.PATIENT_MESSAGE.value,
        msg_facts,
        db=db,
        sandbox_id=sb.id,
        case_id=c.id,
    )
    db.commit()

    step1_done = True
    step2_done = bool(c.acknowledged)
    step3_done = c.state in {
        CaseState.SEEN.value,
        CaseState.TREATMENT_OR_SURVEILLANCE.value,
        CaseState.CLOSED.value,
    }

    return PatientPortalResponse(
        case_id=c.id,
        status_text=(
            t_map["status_closed"]
            if c.state == CaseState.CLOSED.value
            else t_map["status_open"]
        ),
        next_step_text=str(llm_msg["output"]["body"]),
        due_date=due_str,
        language=lang,
        language_fallback=is_fallback,
        acknowledged=bool(c.acknowledged),
        steps=[
            PatientStepItem(label=t_map["step_1"], done=step1_done),
            PatientStepItem(label=t_map["step_2"], done=step2_done),
            PatientStepItem(label=t_map["step_3"], done=step3_done),
        ],
    )


def acknowledge_patient_result(db: Session, token: str) -> dict[str, Any]:
    """Record patient acknowledgement, advance PATIENT_NOTIFIED -> ACKNOWLEDGED, and log event."""
    c, _, sb = _find_case_by_patient_token(db, token)
    now = clock_for_sandbox(sb)()
    prev_state = c.state
    c.acknowledged = True

    db.add(
        Evidence(
            sandbox_id=sb.id,
            case_id=c.id,
            type=EvidenceType.ACKNOWLEDGEMENT.value,
            ref=f"pt-ack-{c.id}",
            created_by="patient",
            at=now,
        )
    )

    if c.state in {CaseState.RESULT_ISSUED.value, CaseState.PATIENT_NOTIFIED.value}:
        if c.state == CaseState.RESULT_ISSUED.value:
            db.add(
                Evidence(
                    sandbox_id=sb.id,
                    case_id=c.id,
                    type=EvidenceType.MESSAGE_SENT.value,
                    ref=f"pt-msg-{c.id}",
                    created_by="system",
                    at=now,
                )
            )
            record_event(
                db,
                sandbox_id=sb.id,
                case_id=c.id,
                event_type="STATE_CHANGED",
                actor_role="coordinator",
                from_state=CaseState.RESULT_ISSUED.value,
                to_state=CaseState.PATIENT_NOTIFIED.value,
                payload={"auto_notified": True},
                at=now,
            )
            prev_state = CaseState.PATIENT_NOTIFIED.value

        c.state = CaseState.ACKNOWLEDGED.value
        c.state_entered_at = now
        c.owner_role = owner_role_for_state(CaseState.ACKNOWLEDGED.value)

    record_event(
        db,
        sandbox_id=sb.id,
        case_id=c.id,
        event_type="PATIENT_ACKNOWLEDGED",
        actor_role="patient",
        from_state=prev_state,
        to_state=c.state,
        payload={"acknowledged": True},
        at=now,
    )
    db.commit()
    return {"case_id": c.id, "acknowledged": True, "state": c.state}


def submit_patient_teachback(
    db: Session, token: str, reply_text: str
) -> TeachBackResponse:
    """Evaluate patient teach-back reply, record Message & event, and escalate if confused."""
    c, pat, sb = _find_case_by_patient_token(db, token)
    now = clock_for_sandbox(sb)()

    facts = {
        "patient_reply": reply_text,
        "expected_key_facts": [c.screening_type],
    }
    res = generate_validated_llm_output(
        LLMKind.TEACHBACK.value,
        facts,
        db=db,
        sandbox_id=sb.id,
        case_id=c.id,
    )
    label = str(res["output"]["label"])
    followup = str(
        res["output"].get(
            "followup_text",
            "Thank you. Our care team has recorded your response.",
        )
    )

    db.add(
        Message(
            sandbox_id=sb.id,
            case_id=c.id,
            channel="portal",
            language=pat.language,
            body=reply_text,
            direction="in",
            status="received",
            teachback_label=label,
            at=now,
        )
    )
    record_event(
        db,
        sandbox_id=sb.id,
        case_id=c.id,
        event_type="TEACHBACK_RECORDED",
        actor_role="patient",
        from_state=c.state,
        to_state=c.state,
        payload={"label": label, "reply_text": reply_text},
        at=now,
    )

    if label == TeachBackLabel.CONFUSED.value:
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
                    action_type=ActionType.CREATE_NAVIGATOR_TASK.value,
                    payload={"channel": "sms", "owner_id": c.owner_id or "coord-1"},
                    reasons=["teachback_confused"],
                    status="pending",
                    at=now,
                )
            )
        elif "teachback_confused" not in existing_pa.reasons:
            existing_pa.reasons = [*existing_pa.reasons, "teachback_confused"]

    db.commit()
    return TeachBackResponse(
        label=label,
        followup_text=followup,
        escalated=bool(c.escalated),
    )
