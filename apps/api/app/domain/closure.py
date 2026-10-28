"""Closure gate rule (exact code required by CareLoop AI spec)."""
import logging
from typing import Any

from app.domain.states import ALLOWED_CLOSURE_EVIDENCE

logger = logging.getLogger(__name__)


def can_close(evidence_types: set[str], override: dict[str, Any] | None) -> tuple[bool, str]:
    if evidence_types & ALLOWED_CLOSURE_EVIDENCE:
        return True, "evidence"
    if override and override.get("authorized") and override.get("reason"):
        return True, "authorized_override"
    return False, "closure requires evidence or an authorized override"
