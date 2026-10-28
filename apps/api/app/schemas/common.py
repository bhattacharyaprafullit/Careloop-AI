"""Common Pydantic v2 schemas shared across endpoints."""
import logging
from datetime import datetime

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class SandboxResponse(BaseModel):
    token: str
    expires_at: datetime
    case_count: int


class EvidenceInput(BaseModel):
    type: str
    ref: str
    reason_code: str | None = None
