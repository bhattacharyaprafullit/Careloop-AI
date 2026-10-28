"""Graph runner: invoke and resume CareLoop LangGraph threads keyed by thread_id = case_id (M7)."""
import logging
from typing import Any

from langgraph.types import Command

from app.graph.build import build_careloop_graph

logger = logging.getLogger(__name__)


def run_case_graph(
    case_id: str,
    sandbox_id: str,
    *,
    closure_request: dict[str, Any] | None = None,
    checkpointer: Any = None,
) -> dict[str, Any]:
    """Run the CareLoop graph for `case_id` (`thread_id = case_id`).

    Returns {"status": "paused"|"completed", "state": dict}.
    """
    graph = build_careloop_graph(checkpointer=checkpointer)
    config: dict[str, Any] = {"configurable": {"thread_id": case_id}}
    initial_state: dict[str, Any] = {
        "case_id": case_id,
        "sandbox_id": sandbox_id,
    }
    if closure_request:
        initial_state["closure_result"] = closure_request

    result = graph.invoke(initial_state, config=config)
    snap = graph.get_state(config)
    is_paused = bool(snap.next)
    return {
        "status": "paused" if is_paused else "completed",
        "state": dict(result) if isinstance(result, dict) else {},
        "next": list(snap.next),
    }


def resume_case_graph(
    case_id: str,
    decision_payload: dict[str, Any],
    *,
    checkpointer: Any = None,
) -> dict[str, Any]:
    """Resume a paused graph at hitl_gate with Command(resume=decision_payload)."""
    graph = build_careloop_graph(checkpointer=checkpointer)
    config: dict[str, Any] = {"configurable": {"thread_id": case_id}}

    snap_before = graph.get_state(config)
    if not snap_before.next:
        # If the case was a pre-seeded pending approval without an active checkpoint yet,
        # run once to reach hitl_gate and then resume.
        from sqlalchemy import select
        from sqlalchemy.orm import Session

        from app.db.models import Case
        from app.db.session import get_engine

        with Session(get_engine()) as db:
            c = db.scalar(select(Case).where(Case.id == case_id))
            if c is not None:
                graph.invoke({"case_id": c.id, "sandbox_id": c.sandbox_id}, config=config)

    result = graph.invoke(Command(resume=decision_payload), config=config)
    snap_after = graph.get_state(config)
    return {
        "status": "paused" if snap_after.next else "completed",
        "state": dict(result) if isinstance(result, dict) else {},
    }
