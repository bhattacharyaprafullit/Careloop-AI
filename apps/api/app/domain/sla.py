"""SLA hours, due dates, pressure, and overdue calculations with injectable clock."""
import logging
from datetime import UTC, datetime, timedelta

from app.core.clock import ClockFn, utc_now
from app.domain.states import CaseState, UrgencyTier
from app.domain.transitions import STATE_SPECS

logger = logging.getLogger(__name__)


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def sla_hours_for(state: str | CaseState, urgency_tier: int) -> float | None:
    """Return SLA hours for `state` and `urgency_tier` (urgent tier 1 halves SLA hours)."""
    spec = STATE_SPECS[CaseState(state)]
    if spec.base_sla_hours is None:
        return None
    if urgency_tier == UrgencyTier.URGENT:
        return float(spec.base_sla_hours) / 2.0
    return float(spec.base_sla_hours)


def sla_due_at(
    state: str | CaseState, state_entered_at: datetime, urgency_tier: int
) -> datetime | None:
    """Compute the exact UTC timestamp when the current state's SLA expires."""
    hours = sla_hours_for(state, urgency_tier)
    if hours is None:
        return None
    entered = _ensure_utc(state_entered_at)
    return entered + timedelta(hours=hours)


def hours_in_state(
    state_entered_at: datetime, clock: ClockFn = utc_now
) -> float:
    """Return elapsed hours in the current state using the provided clock."""
    now = _ensure_utc(clock())
    entered = _ensure_utc(state_entered_at)
    elapsed = (now - entered).total_seconds() / 3600.0
    return max(0.0, elapsed)


def hours_remaining(
    state: str | CaseState,
    state_entered_at: datetime,
    urgency_tier: int,
    clock: ClockFn = utc_now,
) -> float | None:
    """Return hours remaining until SLA due (negative when overdue, None for CLOSED)."""
    due = sla_due_at(state, state_entered_at, urgency_tier)
    if due is None:
        return None
    now = _ensure_utc(clock())
    return (due - now).total_seconds() / 3600.0


def sla_pressure(
    state: str | CaseState,
    state_entered_at: datetime,
    urgency_tier: int,
    clock: ClockFn = utc_now,
) -> float:
    """Compute sla_pressure = hours in state / SLA hours (0.0 for CLOSED)."""
    total_sla = sla_hours_for(state, urgency_tier)
    if not total_sla or total_sla <= 0:
        return 0.0
    elapsed = hours_in_state(state_entered_at, clock=clock)
    return elapsed / total_sla


def is_overdue(
    state: str | CaseState,
    state_entered_at: datetime,
    urgency_tier: int,
    clock: ClockFn = utc_now,
) -> bool:
    """Return True if the case is past its state SLA deadline. Never true for CLOSED."""
    rem = hours_remaining(state, state_entered_at, urgency_tier, clock=clock)
    if rem is None:
        return False
    return rem < 0.0
