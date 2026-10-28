"""Pydantic v2 schemas for workflow resume and pending approvals (M7)."""
import logging
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class WorkflowResumeRequest(BaseModel):
    case_id: str
    decision: str
    modified_action: dict[str, Any] | None = None
    note: str | None = None


class WorkflowResumeResponse(BaseModel):
    case_id: str
    status: str
    state: str
