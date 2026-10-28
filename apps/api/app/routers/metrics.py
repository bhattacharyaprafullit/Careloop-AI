"""GET /api/v1/metrics/summary and GET /api/v1/metrics/model-card endpoints (M9/M10)."""
import logging
from typing import Any

from fastapi import APIRouter
from ml.eval.simulate_queue import run_queue_simulation
from sqlalchemy import select

from app.db.models import Case, CaseEvent, Closure, DelayReason, Message, Referral
from app.db.repo import clock_for_sandbox
from app.deps import DbSession, SandboxCtx
from app.domain.metrics import compute_metrics_summary
from app.schemas.metrics import MetricsSummaryResponse
from app.services.inference import get_loaded_models

logger = logging.getLogger(__name__)

router = APIRouter(tags=["metrics"])

_SIMULATION_CACHE: dict[str, Any] = {}


def _get_simulation_summary() -> dict[str, Any]:
    if _SIMULATION_CACHE:
        return _SIMULATION_CACHE
    bundle = get_loaded_models()
    sim = bundle.get("metrics", {}).get("simulation")
    if not isinstance(sim, dict) or "fifo" not in sim:
        sim = run_queue_simulation(runs=100)
    _SIMULATION_CACHE.update(sim)
    return _SIMULATION_CACHE


@router.get("/metrics/summary", response_model=MetricsSummaryResponse)
def get_metrics_summary(
    db: DbSession,
    ctx: SandboxCtx,
) -> MetricsSummaryResponse:
    """Compute R6 closure and impact metrics from events plus the FIFO vs CareLoop simulation."""
    sb = ctx.sandbox
    clock = clock_for_sandbox(sb)

    cases = [
        {
            "id": c.id,
            "state": c.state,
            "created_at": c.created_at,
            "acknowledged": c.acknowledged,
        }
        for c in db.scalars(select(Case).where(Case.sandbox_id == sb.id))
    ]
    events = [
        {
            "case_id": ev.case_id,
            "from_state": ev.from_state,
            "to_state": ev.to_state,
            "event_type": ev.event_type,
            "at": ev.at,
        }
        for ev in db.scalars(select(CaseEvent).where(CaseEvent.sandbox_id == sb.id))
    ]
    referrals = [
        {"id": r.id, "status": r.status}
        for r in db.scalars(select(Referral).where(Referral.sandbox_id == sb.id))
    ]
    closures = [
        {"id": cl.id, "kind": cl.kind}
        for cl in db.scalars(select(Closure).where(Closure.sandbox_id == sb.id))
    ]
    delay_reasons = [
        {"code": dr.code, "confirmed": dr.confirmed}
        for dr in db.scalars(select(DelayReason).where(DelayReason.sandbox_id == sb.id))
    ]
    messages = [
        {"teachback_label": m.teachback_label}
        for m in db.scalars(select(Message).where(Message.sandbox_id == sb.id))
    ]

    summary = compute_metrics_summary(
        cases=cases,
        events=events,
        referrals=referrals,
        closures=closures,
        delay_reasons=delay_reasons,
        messages=messages,
        simulation=_get_simulation_summary(),
        clock=clock,
    )
    return MetricsSummaryResponse(**summary)


@router.get("/metrics/model-card")
def get_model_card_metrics() -> dict[str, Any]:
    """Return the full ml/artifacts/metrics.json payload for the /app/model-card frontend page."""
    bundle = get_loaded_models()
    metrics = dict(bundle.get("metrics") or {})
    if "simulation" not in metrics:
        metrics["simulation"] = _get_simulation_summary()
    return metrics
