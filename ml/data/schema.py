"""Data schema definitions and column contracts for CareLoop AI synthetic data."""
import logging
from typing import Final

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
