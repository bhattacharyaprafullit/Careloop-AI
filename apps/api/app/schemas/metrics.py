"""Pydantic v2 schemas for metrics summary, demo advance-time/reset, and internal tick (M9)."""
import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AdvanceTimeRequest(BaseModel):
    hours: float = Field(gt=0.0, le=720.0)


class AdvanceTimeResponse(BaseModel):
    clock_offset_hours: float
    overdue_cases: int
    newly_breached: int


class DemoResetResponse(BaseModel):
    sandbox_id: str
    clock_offset_hours: float
    case_count: int


class InternalTickResponse(BaseModel):
    expired_sandboxes_deleted: int
    sla_breaches_recorded: int
    cases_escalated: int


class MetricsSummaryResponse(BaseModel):
    state_counts: dict[str, int]
    intervals: dict[str, dict[str, float | int | None]]
    referral_completion_rate: float
    appointment_completion_rate: float
    unresolved: dict[str, Any]
    delay_reasons: list[dict[str, Any]]
    documented_closure_rate: float
    acknowledgement_rate: float
    teachback: dict[str, int]
    simulation: dict[str, Any]
