"""Build and compile the CareLoop LangGraph StateGraph (M7)."""
import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.graph.checkpoint import get_checkpointer
from app.graph.nodes import (
    action_exec_node,
    audit_log_node,
    clinical_router_node,
    closure_check_node,
    hitl_gate_node,
    ingestion_node,
    ml_inference_node,
    ownership_node,
    patient_comms_node,
    summarizer_node,
)
from app.graph.state import CareLoopGraphState

logger = logging.getLogger(__name__)


def _route_after_clinical_router(state: CareLoopGraphState) -> str:
    if state.get("requires_human"):
        return "hitl_gate"
    return "action_exec"


def _route_after_hitl_gate(state: CareLoopGraphState) -> str:
    dec = state.get("decision") or {}
    if dec.get("decision") == "reject":
        # action_exec_node records the manual plan and skips action execution before audit_log
        return "action_exec"
    return "action_exec"


def build_careloop_graph(checkpointer: Any = None) -> Any:
    """Construct and compile the 10-node CareLoop LangGraph workflow."""
    builder = StateGraph(CareLoopGraphState)

    builder.add_node("ingestion", ingestion_node)
    builder.add_node("ml_inference", ml_inference_node)
    builder.add_node("summarizer", summarizer_node)
    builder.add_node("ownership", ownership_node)
    builder.add_node("patient_comms", patient_comms_node)
    builder.add_node("clinical_router", clinical_router_node)
    builder.add_node("hitl_gate", hitl_gate_node)
    builder.add_node("action_exec", action_exec_node)
    builder.add_node("closure_check", closure_check_node)
    builder.add_node("audit_log", audit_log_node)

    builder.add_edge(START, "ingestion")
    builder.add_edge("ingestion", "ml_inference")
    builder.add_edge("ml_inference", "summarizer")
    builder.add_edge("summarizer", "ownership")
    builder.add_edge("ownership", "patient_comms")
    builder.add_edge("patient_comms", "clinical_router")

    builder.add_conditional_edges(
        "clinical_router",
        _route_after_clinical_router,
        {"hitl_gate": "hitl_gate", "action_exec": "action_exec"},
    )
    builder.add_conditional_edges(
        "hitl_gate",
        _route_after_hitl_gate,
        {"action_exec": "action_exec", "audit_log": "audit_log"},
    )
    builder.add_edge("action_exec", "closure_check")
    builder.add_edge("closure_check", "audit_log")
    builder.add_edge("audit_log", END)

    ckpt = checkpointer if checkpointer is not None else get_checkpointer()
    return builder.compile(checkpointer=ckpt)
