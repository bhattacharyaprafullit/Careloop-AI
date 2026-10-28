"""Priority score and escalation rules (exact formulas from CareLoop AI spec)."""
import logging

from app.domain.states import TeachBackLabel, UrgencyTier

logger = logging.getLogger(__name__)

URGENCY_SCORE_MAP: dict[int, float] = {
    UrgencyTier.URGENT: 1.0,
    UrgencyTier.PRIORITY: 0.6,
    UrgencyTier.ROUTINE: 0.2,
}


def urgency_score_for(urgency_tier: int) -> float:
    """Map urgency tier (1, 2, 3) to its domain urgency score (1.0, 0.6, 0.2)."""
    return URGENCY_SCORE_MAP.get(urgency_tier, 0.2)


def priority(
    urgency_score: float, p_dropoff: float, sla_pressure: float, urgent: bool
) -> float:
    base = 0.45 * urgency_score + 0.35 * p_dropoff + 0.20 * min(sla_pressure, 1.5) / 1.5
    return base + (10.0 if urgent else 0.0)


def compute_case_priority(
    urgency_tier: int, p_dropoff: float, sla_pressure_val: float
) -> float:
    """Convenience wrapper that derives urgency_score and urgent flag from urgency_tier."""
    u_score = urgency_score_for(urgency_tier)
    is_urgent = urgency_tier == UrgencyTier.URGENT
    return priority(u_score, p_dropoff, sla_pressure_val, is_urgent)


def evaluate_escalation(
    *,
    urgency_tier: int,
    overdue: bool,
    p_dropoff: float,
    teachback_label: str | None = None,
    referral_rejected: bool = False,
    ads: float | None = None,
    closure_override_requested: bool = False,
) -> tuple[bool, list[str]]:
    """Evaluate the escalation rule and return (escalated, reasons).

    Rule: urgency_tier 1 and overdue; or p_dropoff > 0.65; or teach-back confused;
    or referral rejected; or ADS > 0.5; or closure override requested.
    """
    reasons: list[str] = []
    if urgency_tier == UrgencyTier.URGENT and overdue:
        reasons.append("urgent_and_overdue")
    if p_dropoff > 0.65:
        reasons.append("high_dropoff_risk")
    if teachback_label == TeachBackLabel.CONFUSED.value:
        reasons.append("teachback_confused")
    if referral_rejected:
        reasons.append("referral_rejected")
    if ads is not None and ads > 0.5:
        reasons.append("high_ads_divergence")
    if closure_override_requested:
        reasons.append("closure_override_requested")
    return (len(reasons) > 0), reasons
