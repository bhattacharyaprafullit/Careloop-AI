"""Data schema definitions, column contracts, and seed archetype specs for CareLoop AI."""
import logging
from typing import Any, Final

logger = logging.getLogger(__name__)

INSURANCE_CATEGORIES: Final[tuple[str, ...]] = (
    "COMMERCIAL",
    "MEDICARE",
    "MEDICAID",
    "UNINSURED",
)

LANGUAGES: Final[tuple[str, ...]] = ("en", "hi", "es", "other")
LANGUAGE_PROBS: Final[tuple[float, ...]] = (0.70, 0.15, 0.10, 0.05)

SCREENING_TYPES: Final[tuple[str, ...]] = ("FIT", "MAMMOGRAPHY", "PAP_HPV")

STAGE_SEQUENCE: Final[tuple[str, ...]] = (
    "RESULT_ISSUED",
    "PATIENT_NOTIFIED",
    "ACKNOWLEDGED",
    "CONFIRMATORY_PENDING",
    "REFERRAL_SENT",
    "REJECTED",
    "REFERRAL_ACCEPTED",
    "APPOINTMENT_BOOKED",
    "SEEN",
    "TREATMENT_OR_SURVEILLANCE",
)

STAGE_BASE_SLA_HOURS: Final[dict[str, float]] = {
    "RESULT_ISSUED": 24.0,
    "PATIENT_NOTIFIED": 48.0,
    "ACKNOWLEDGED": 120.0,
    "CONFIRMATORY_PENDING": 336.0,
    "REFERRAL_SENT": 72.0,
    "REJECTED": 24.0,
    "REFERRAL_ACCEPTED": 120.0,
    "APPOINTMENT_BOOKED": 168.0,
    "SEEN": 72.0,
    "TREATMENT_OR_SURVEILLANCE": 720.0,
}

FEATURE_COLUMNS: Final[tuple[str, ...]] = (
    "screening_type",
    "severity_grade",
    "urgent_flag",
    "finding_to_order_days",
    "prior_noshow_count",
    "prior_noshow_ratio",
    "days_since_last_encounter",
    "scheduling_lead_time",
    "distance_miles",
    "insurance_category",
    "patient_age",
    "preferred_language",
    "digital_portal_active",
    "stage",
    "days_in_stage",
    "contact_attempts",
    "acknowledged_flag",
)

FORBIDDEN_DEMOGRAPHIC_COLUMNS: Final[frozenset[str]] = frozenset(
    {"race", "ethnicity", "religion", "name", "zip"}
)

CASE_COLUMNS: Final[tuple[str, ...]] = (
    "case_id",
    "patient_id",
    "patient_age",
    "preferred_language",
    "insurance_category",
    "distance_miles",
    "digital_portal_active",
    "prior_noshow_count",
    "prior_noshow_ratio",
    "days_since_last_encounter",
    "screening_type",
    "severity_grade",
    "urgent_flag",
    "urgency_tier",
    "finding_to_order_days",
    "scheduling_lead_time",
    "final_state",
    "closed_flag",
    "days_to_close_or_censor",
)

STAGE_ROW_COLUMNS: Final[tuple[str, ...]] = (
    "case_id",
    "patient_id",
    *FEATURE_COLUMNS,
    "dropoff",
    "stage_hours",
)

OWNER_ROLE_BY_STATE: Final[dict[str, str | None]] = {
    "RESULT_ISSUED": "clinician",
    "PATIENT_NOTIFIED": "coordinator",
    "ACKNOWLEDGED": "coordinator",
    "CONFIRMATORY_PENDING": "clinician",
    "REFERRAL_SENT": "clinician",
    "REJECTED": "coordinator",
    "REFERRAL_ACCEPTED": "clinician",
    "APPOINTMENT_BOOKED": "coordinator",
    "SEEN": "clinician",
    "TREATMENT_OR_SURVEILLANCE": "clinician",
    "CLOSED": None,
}

_BASE_REF_PATH: list[tuple[str, str | None]] = [
    ("RESULT_ISSUED", None),
    ("PATIENT_NOTIFIED", "message_sent"),
    ("ACKNOWLEDGED", "acknowledgement"),
    ("REFERRAL_SENT", "referral_created"),
]
_ACC_PATH = [*_BASE_REF_PATH, ("REFERRAL_ACCEPTED", "referral_accepted")]
_BOOK_PATH = [*_ACC_PATH, ("APPOINTMENT_BOOKED", "appointment_booked")]
_SEEN_PATH = [*_BOOK_PATH, ("SEEN", "attendance_recorded")]
_TREAT_PATH = [*_SEEN_PATH, ("TREATMENT_OR_SURVEILLANCE", "plan_recorded")]

PATH_TO_STATE: Final[dict[str, list[tuple[str, str | None]]]] = {
    "RESULT_ISSUED": _BASE_REF_PATH[:1],
    "PATIENT_NOTIFIED": _BASE_REF_PATH[:2],
    "ACKNOWLEDGED": _BASE_REF_PATH[:3],
    "CONFIRMATORY_PENDING": [
        *_BASE_REF_PATH[:3],
        ("CONFIRMATORY_PENDING", "confirmatory_ordered"),
    ],
    "REFERRAL_SENT": _BASE_REF_PATH,
    "REJECTED": [*_BASE_REF_PATH, ("REJECTED", "referral_rejected")],
    "REFERRAL_ACCEPTED": _ACC_PATH,
    "APPOINTMENT_BOOKED": _BOOK_PATH,
    "SEEN": _SEEN_PATH,
    "TREATMENT_OR_SURVEILLANCE": _TREAT_PATH,
    "CLOSED": [*_TREAT_PATH, ("CLOSED", None)],
}

_ArchRow = tuple[int, str, str, int, str | None, float, bool, bool, dict[str, Any]]
_ARCH_SPECS: Final[tuple[_ArchRow, ...]] = (
    (1, "urgent_just_issued_unassigned", "RESULT_ISSUED", 1, None, 4.0, False, False, {}),
    (
        2,
        "notified_not_acknowledged_overdue",
        "PATIENT_NOTIFIED",
        2,
        "coord-1",
        60.0,
        True,
        False,
        {},
    ),
    (
        3,
        "acknowledged_teachback_confused_escalated",
        "ACKNOWLEDGED",
        2,
        "coord-2",
        18.0,
        True,
        True,
        {"teachback_label": "confused"},
    ),
    (
        4,
        "confirmatory_pending_near_sla",
        "CONFIRMATORY_PENDING",
        2,
        "clin-1",
        310.0,
        False,
        True,
        {},
    ),
    (
        5,
        "referral_sent_awaiting_acceptance",
        "REFERRAL_SENT",
        2,
        "clin-2",
        30.0,
        False,
        True,
        {"referral_status": "sent"},
    ),
    (
        6,
        "referral_rejected_needing_reassignment",
        "REJECTED",
        1,
        "coord-1",
        8.0,
        True,
        True,
        {"referral_status": "rejected", "reason_code": "referral_rejected_capacity"},
    ),
    (
        7,
        "accepted_no_appointment",
        "REFERRAL_ACCEPTED",
        2,
        "clin-1",
        48.0,
        False,
        True,
        {"referral_status": "accepted"},
    ),
    (
        8,
        "appointment_missed_rebook_needed",
        "APPOINTMENT_BOOKED",
        1,
        "coord-2",
        96.0,
        True,
        True,
        {"referral_status": "accepted", "missed_visit": True},
    ),
    (
        9,
        "seen_no_treatment_plan_recorded",
        "SEEN",
        2,
        "clin-2",
        50.0,
        False,
        True,
        {"referral_status": "accepted"},
    ),
    (
        10,
        "in_surveillance_ready_to_close_with_evidence",
        "TREATMENT_OR_SURVEILLANCE",
        3,
        "clin-1",
        120.0,
        False,
        True,
        {"referral_status": "accepted", "ready_closure_evidence": "surveillance_plan"},
    ),
    (
        11,
        "closed_with_evidence",
        "CLOSED",
        2,
        None,
        24.0,
        False,
        True,
        {
            "referral_status": "accepted",
            "closure_kind": "evidence",
            "closure_evidence": "treatment_started",
        },
    ),
    (
        12,
        "closed_by_authorized_override_with_reason",
        "CLOSED",
        3,
        None,
        12.0,
        False,
        True,
        {
            "referral_status": "accepted",
            "closure_kind": "override",
            "override_reason": (
                "Patient relocated and confirmed care at out-of-state oncology center"
            ),
        },
    ),
)

ARCHETYPES: Final[tuple[dict[str, Any], ...]] = tuple(
    {
        "id": i,
        "name": name,
        "state": st,
        "urgency_tier": tier,
        "owner_id": owner,
        "hours_in_state": hrs,
        "escalated": esc,
        "acknowledged": ack,
        **extra,
    }
    for i, name, st, tier, owner, hrs, esc, ack, extra in _ARCH_SPECS
)
