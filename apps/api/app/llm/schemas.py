"""Pydantic v2 output schemas for all 5 LLM tasks (M6)."""
import logging

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CaseSummaryOutput(BaseModel):
    summary_lines: list[str] = Field(min_length=1, max_length=5)
    next_step: str
    cited_drivers: list[str]


class PatientMessageOutput(BaseModel):
    body: str


class TeachBackOutput(BaseModel):
    label: str
    missing_facts: list[str]
    followup_text: str


class SbarNoteOutput(BaseModel):
    situation: str
    background: str
    assessment: str
    recommendation: str


class DelayReasonOutput(BaseModel):
    code: str
    rationale: str
