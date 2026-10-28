"""Exact domain enums and constants as specified in CareLoop AI spec."""
import logging
from enum import StrEnum

logger = logging.getLogger(__name__)


class CaseState(StrEnum):
    RESULT_ISSUED = "RESULT_ISSUED"
    PATIENT_NOTIFIED = "PATIENT_NOTIFIED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    CONFIRMATORY_PENDING = "CONFIRMATORY_PENDING"
    REFERRAL_SENT = "REFERRAL_SENT"
    REJECTED = "REJECTED"
    REFERRAL_ACCEPTED = "REFERRAL_ACCEPTED"
    APPOINTMENT_BOOKED = "APPOINTMENT_BOOKED"
    SEEN = "SEEN"
    TREATMENT_OR_SURVEILLANCE = "TREATMENT_OR_SURVEILLANCE"
    CLOSED = "CLOSED"


ALL_STATES: tuple[CaseState, ...] = tuple(CaseState)
NON_CLOSED_STATES: tuple[CaseState, ...] = tuple(s for s in CaseState if s != CaseState.CLOSED)


class Role(StrEnum):
    COORDINATOR = "coordinator"
    CLINICIAN = "clinician"
    PATIENT = "patient"


class ScreeningType(StrEnum):
    FIT = "FIT"
    MAMMOGRAPHY = "MAMMOGRAPHY"
    PAP_HPV = "PAP_HPV"


class UrgencyTier( int ):
    """1 = urgent, 2 = priority, 3 = routine."""
    URGENT = 1
    PRIORITY = 2
    ROUTINE = 3


URGENCY_TIERS: tuple[int, ...] = (1, 2, 3)


class Language(StrEnum):
    EN = "en"
    HI = "hi"
    ES = "es"


SUPPORTED_LANGUAGES: frozenset[str] = frozenset({Language.EN, Language.HI, Language.ES})


def resolve_language(lang: str | None) -> tuple[str, bool]:
    """Return (resolved_lang, language_fallback). Unsupported languages fall back to 'en'."""
    if lang and lang.lower() in SUPPORTED_LANGUAGES:
        return lang.lower(), False
    return Language.EN.value, True


class EvidenceType(StrEnum):
    MESSAGE_SENT = "message_sent"
    ACKNOWLEDGEMENT = "acknowledgement"
    CALL_LOG = "call_log"
    CONFIRMATORY_ORDERED = "confirmatory_ordered"
    CONFIRMATORY_RESULT = "confirmatory_result"
    REFERRAL_CREATED = "referral_created"
    REFERRAL_ACCEPTED = "referral_accepted"
    REFERRAL_REJECTED = "referral_rejected"
    APPOINTMENT_BOOKED = "appointment_booked"
    ATTENDANCE_RECORDED = "attendance_recorded"
    PLAN_RECORDED = "plan_recorded"
    TREATMENT_STARTED = "treatment_started"
    SURVEILLANCE_PLAN = "surveillance_plan"
    BENIGN_CONFIRMED = "benign_confirmed"
    PATIENT_DECLINED_COUNSELED = "patient_declined_counseled"


ALLOWED_CLOSURE_EVIDENCE: set[str] = {
    EvidenceType.TREATMENT_STARTED.value,
    EvidenceType.SURVEILLANCE_PLAN.value,
    EvidenceType.BENIGN_CONFIRMED.value,
    EvidenceType.PATIENT_DECLINED_COUNSELED.value,
}


class ReasonCode(StrEnum):
    PATIENT_UNREACHABLE = "patient_unreachable"
    TRANSPORT_BARRIER = "transport_barrier"
    COST_CONCERN = "cost_concern"
    LANGUAGE_BARRIER = "language_barrier"
    SCHEDULING_CONFLICT = "scheduling_conflict"
    REFERRAL_REJECTED_CAPACITY = "referral_rejected_capacity"
    REFERRAL_INCOMPLETE = "referral_incomplete"
    NO_APPOINTMENT_AVAILABLE = "no_appointment_available"
    PATIENT_DECLINED = "patient_declined"
    CLINICIAN_DELAY = "clinician_delay"
    LOST_RESULT = "lost_result"
    UNKNOWN = "unknown"


class ActionType(StrEnum):
    SEND_PORTAL_MESSAGE = "send_portal_message"
    SEND_SMS = "send_sms"
    CREATE_NAVIGATOR_TASK = "create_navigator_task"
    REQUEST_CONSULT = "request_consult"
    REASSIGN_OWNER = "reassign_owner"
    PRIORITY_REBOOK = "priority_rebook"


class Decision(StrEnum):
    APPROVE = "approve"
    MODIFY = "modify"
    REJECT = "reject"


class TeachBackLabel(StrEnum):
    UNDERSTOOD = "understood"
    PARTIAL = "partial"
    CONFUSED = "confused"


class LLMKind(StrEnum):
    CASE_SUMMARY = "case_summary"
    PATIENT_MESSAGE = "patient_message"
    TEACHBACK = "teachback"
    SBAR_NOTE = "sbar_note"
    DELAY_REASON = "delay_reason"
