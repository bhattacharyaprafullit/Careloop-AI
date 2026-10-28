"""SQLAlchemy 2.0 ORM models for CareLoop AI (M4)."""
import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.clock import utc_now

logger = logging.getLogger(__name__)

# JSONB on Postgres, JSON on SQLite
JsonType = JSON().with_variant(JSONB(), "postgresql")


def _uuid() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    """Base declarative class for all CareLoop tables."""


class Sandbox(Base):
    __tablename__ = "sandboxes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    clock_offset_hours: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    sandbox_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    alias: Mapped[str] = mapped_column(String(32), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    insurance: Mapped[str] = mapped_column(String(32), nullable=False)
    distance_miles: Mapped[float] = mapped_column(Float, nullable=False)
    portal_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    prior_noshow_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    prior_noshow_ratio: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    days_since_last_encounter: Mapped[int] = mapped_column(Integer, default=30, nullable=False)


class Case(Base):
    __tablename__ = "cases"
    __table_args__ = (
        Index("ix_cases_sandbox_state", "sandbox_id", "state"),
        Index("ix_cases_sandbox_escalated", "sandbox_id", "escalated"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    sandbox_id: Mapped[str] = mapped_column(String(64), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    screening_type: Mapped[str] = mapped_column(String(32), nullable=False)
    severity_grade: Mapped[int] = mapped_column(Integer, nullable=False)
    urgency_tier: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(40), nullable=False)
    state_entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    owner_role: Mapped[str | None] = mapped_column(String(24), nullable=True)
    owner_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    finding_to_order_days: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    scheduling_lead_time: Mapped[float] = mapped_column(Float, default=14.0, nullable=False)
    contact_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    patient_token_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CaseEvent(Base):
    """Append-only event log (UPDATE and DELETE blocked at DB level)."""

    __tablename__ = "case_events"
    __table_args__ = (Index("ix_case_events_case_at", "case_id", "at"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    sandbox_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    case_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    from_state: Mapped[str | None] = mapped_column(String(40), nullable=True)
    to_state: Mapped[str | None] = mapped_column(String(40), nullable=True)
    actor_role: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict, nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    sandbox_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    case_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(48), nullable=False)
    ref: Mapped[str] = mapped_column(String(128), nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class RiskScore(Base):
    __tablename__ = "risk_scores"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    sandbox_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    case_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    stage: Mapped[str] = mapped_column(String(40), nullable=False)
    p_dropoff: Mapped[float] = mapped_column(Float, nullable=False)
    median_days: Mapped[float] = mapped_column(Float, nullable=False)
    p_open_30: Mapped[float] = mapped_column(Float, nullable=False)
    p_open_60: Mapped[float] = mapped_column(Float, nullable=False)
    p_open_90: Mapped[float] = mapped_column(Float, nullable=False)
    shap: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False)
    survival_curve: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Referral(Base):
    __tablename__ = "referrals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    sandbox_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    case_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    from_org: Mapped[str] = mapped_column(String(128), nullable=False)
    to_org: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="sent", nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(48), nullable=True)
    sbar: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Consult(Base):
    __tablename__ = "consults"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    sandbox_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    case_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="open", nullable=False)
    thread: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    sandbox_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    case_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    channel: Mapped[str] = mapped_column(String(24), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="queued", nullable=False)
    teachback_label: Mapped[str | None] = mapped_column(String(24), nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class PendingApproval(Base):
    __tablename__ = "pending_approvals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    sandbox_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    case_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    action_type: Mapped[str] = mapped_column(String(48), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict, nullable=False)
    reasons: Mapped[list[str]] = mapped_column(JsonType, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False)
    decision: Mapped[str | None] = mapped_column(String(24), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Closure(Base):
    """Append-only closure record (UPDATE and DELETE blocked at DB level)."""

    __tablename__ = "closures"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    sandbox_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    case_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    evidence_type: Mapped[str | None] = mapped_column(String(48), nullable=True)
    override_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class DelayReason(Base):
    __tablename__ = "delay_reasons"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    sandbox_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    case_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    code: Mapped[str] = mapped_column(String(48), nullable=False)
    proposed_by: Mapped[str] = mapped_column(String(16), nullable=False)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class LLMOutput(Base):
    """Append-only LLM audit log (UPDATE and DELETE blocked at DB level)."""

    __tablename__ = "llm_outputs"
    __table_args__ = (Index("ix_llm_outputs_input_hash", "input_hash"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    sandbox_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    case_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    output: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    faithful_ok: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ads: Mapped[float | None] = mapped_column(Float, nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
