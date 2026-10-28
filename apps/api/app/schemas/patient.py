"""Pydantic v2 schemas for patient portal, referrals, consults, and closure (M8)."""
import logging
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class PatientStepItem(BaseModel):
    label: str
    done: bool


class PatientPortalResponse(BaseModel):
    case_id: str
    status_text: str
    next_step_text: str
    due_date: str
    language: str
    language_fallback: bool = False
    acknowledged: bool
    steps: list[PatientStepItem]


class TeachBackRequest(BaseModel):
    reply_text: str


class TeachBackResponse(BaseModel):
    label: str
    followup_text: str
    escalated: bool


class CreateReferralRequest(BaseModel):
    case_id: str
    to_org: str


class CreateReferralResponse(BaseModel):
    referral_id: str
    sbar: dict[str, str]


class ReferralDecisionRequest(BaseModel):
    decision: str
    reason_code: str | None = None


class CreateConsultRequest(BaseModel):
    case_id: str
    kind: str
    message: str


class ReplyConsultRequest(BaseModel):
    message: str


class OverrideInput(BaseModel):
    reason: str


class CloseCaseRequest(BaseModel):
    evidence_type: str | None = None
    override: OverrideInput | None = None
    extra: dict[str, Any] | None = None
