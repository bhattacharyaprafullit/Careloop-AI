"""LangGraph TypedDict state with exact spec keys (M7)."""
import logging
from typing import Any, TypedDict

logger = logging.getLogger(__name__)


class CareLoopGraphState(TypedDict, total=False):
    case_id: str
    sandbox_id: str
    features: dict[str, Any]
    risk: dict[str, Any]
    shap: dict[str, Any]
    summary: dict[str, Any]
    message: dict[str, Any]
    suggested_action: dict[str, Any]
    reasons: list[str]
    requires_human: bool
    decision: dict[str, Any]
    action_result: dict[str, Any]
    closure_result: dict[str, Any]
