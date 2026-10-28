"""Pydantic v2 schemas for cases, priority queue, details, ingest, assign, and advance (M5)."""
import logging
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import EvidenceInput

logger = logging.getLogger(__name__)


class PriorityQueueItem(BaseModel):
    case_id: str
    patient_alias: str
    screening_type: str
    state: str
    owner_role: str | None
    owner_id: str | None
    urgency_tier: int
    p_dropoff: float
    priority: float
    sla_due_at: datetime | None
    hours_remaining: float | None
    overdue: bool
    escalated: bool
    needs_approval: bool


class PriorityQueueResponse(BaseModel):
    items: list[PriorityQueueItem]
    page: int
    page_size: int
    total: int


class TimelineEntry(BaseModel):
    at: datetime
    event_type: str
    from_state: str | None
    to_state: str | None
    actor_role: str
    summary: str


class ShapDriverItem(BaseModel):
    feature: str
    label: str
    value: float


class ShapPayload(BaseModel):
    top_positive: list[ShapDriverItem]
    top_negative: list[ShapDriverItem]


class CurvePoint(BaseModel):
    day: int
    s: float


class SummaryPayload(BaseModel):
    lines: list[str]
    next_step: str
    cited_drivers: list[str]
    ads: float
    source: str


class CaseDetailsResponse(BaseModel):
    case: dict[str, Any]
    patient: dict[str, Any]
    timeline: list[TimelineEntry]
    risk: dict[str, Any]
    shap: ShapPayload
    survival_curve: list[CurvePoint]
    km_curve: list[CurvePoint]
    summary: SummaryPayload
    messages: list[dict[str, Any]]
    referral: dict[str, Any] | None
    consults: list[dict[str, Any]]
    pending_approval: dict[str, Any] | None
    closure: dict[str, Any] | None


class IngestPatientInput(BaseModel):
    id: str | None = None
    alias: str = "PT-NEW"
    age: int = Field(default=54, ge=18, le=100)
    language: str = "en"
    insurance: str = "COMMERCIAL"
    distance_miles: float = Field(default=10.0, ge=0.0, le=500.0)
    portal_active: bool = True
    prior_noshow_count: int = Field(default=0, ge=0, le=20)
    prior_noshow_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    days_since_last_encounter: int = Field(default=45, ge=0, le=5000)


class ScreeningIngestRequest(BaseModel):
    patient_id: str | None = None
    patient: IngestPatientInput | None = None
    screening_type: str
    severity_grade: int = Field(ge=0, le=5)
    urgent_flag: bool = False
    finding_to_order_days: float = Field(default=5.0, ge=0.0, le=365.0)
    scheduling_lead_time: float = Field(default=14.0, ge=0.0, le=365.0)


class ScreeningIngestResponse(BaseModel):
    case_id: str
    state: str
    p_dropoff: float
    priority: float
    escalated: bool


class AssignCaseRequest(BaseModel):
    owner_role: str
    owner_id: str


class AdvanceCaseRequest(BaseModel):
    to_state: str
    evidence: EvidenceInput
