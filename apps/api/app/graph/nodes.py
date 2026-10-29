"""LangGraph node implementations for CareLoop AI (M7).

Rule: hitl_gate has zero side effects before interrupt() as it re-runs on resume.
"""
import logging
from datetime import timedelta
from typing import Any

from langgraph.types import interrupt
from sqlalchemy import select

from app.db.models import Evidence, Message, Referral
from app.domain.priority import evaluate_escalation
from app.domain.sla import hours_in_state, hours_remaining, is_overdue, sla_due_at
from app.domain.states import ActionType, CaseState, LLMKind
from app.domain.transitions import STATE_SPECS, owner_role_for_state
from app.graph.state import (
    CareLoopGraphState,
    evaluate_graph_closure,
    execute_graph_action,
    load_graph_ctx,
    open_graph_db,
    upsert_pending_approval,
)
from app.llm.client import generate_validated_llm_output
from app.services.events import record_event
from app.services.inference import build_case_feature_dict, persist_risk_score, score_case

logger = logging.getLogger(__name__)
_RISK_KEYS = (
    "stage",
    "p_dropoff",
    "median_days",
    "p_open_30",
    "p_open_60",
    "p_open_90",
    "model_version",
)


def ingestion_node(state: CareLoopGraphState) -> CareLoopGraphState:
    """Load case and patient context and assemble the 17-feature vector."""
    with open_graph_db() as db:
        c, sb, pat, clock = load_graph_ctx(db, state)
        days_st = hours_in_state(c.state_entered_at, clock=clock) / 24.0
        return {"features": build_case_feature_dict(c, pat, days_st), "sandbox_id": sb.id}


def ml_inference_node(state: CareLoopGraphState) -> CareLoopGraphState:
    """Score case with calibrated XGBoost + survival + SHAP and insert risk_scores row."""
    scored = score_case(state["features"])
    with open_graph_db() as db:
        c, sb, _, clock = load_graph_ctx(db, state)
        persist_risk_score(
            db,
            sandbox_id=sb.id,
            case_id=c.id,
            stage=str(scored["stage"]),
            scored=scored,
            at=clock(),
        )
        db.commit()
    return {"risk": {k: scored[k] for k in _RISK_KEYS}, "shap": scored["shap"]}


def summarizer_node(state: CareLoopGraphState) -> CareLoopGraphState:
    """Generate validated case_summary, compute ADS, and log to llm_outputs."""
    with open_graph_db() as db:
        c, sb, _, clock = load_graph_ctx(db, state)
        rem_h = hours_remaining(c.state, c.state_entered_at, c.urgency_tier, clock=clock)
        spec = STATE_SPECS[CaseState(c.state)]
        existing_ev = set(db.scalars(select(Evidence.type).where(Evidence.case_id == c.id)))
        facts = {
            "state": c.state,
            "owner_role": c.owner_role or owner_role_for_state(c.state) or "clinician",
            "days_in_state": round(state["features"]["days_in_stage"], 1),
            "sla_hours_remaining": round(rem_h if rem_h is not None else 0.0, 1),
            "p_dropoff_percent": int(round(float(state["risk"]["p_dropoff"]) * 100)),
            "shap_top_positive": state["shap"]["top_positive"],
            "shap_top_negative": state["shap"]["top_negative"],
            "evidence_gaps": sorted(spec.required_entry_evidence - existing_ev),
        }
        res = generate_validated_llm_output(
            LLMKind.CASE_SUMMARY.value, facts, db=db, sandbox_id=sb.id, case_id=c.id
        )
        db.commit()
        return {"summary": {**res["output"], "ads": res["ads"], "source": res["source"]}}


def ownership_node(state: CareLoopGraphState) -> CareLoopGraphState:
    """Ensure owner_role is set for the current state and record OWNER_ASSIGNED."""
    with open_graph_db() as db:
        c, sb, _, clock = load_graph_ctx(db, state)
        target = owner_role_for_state(c.state)
        c.owner_role = target
        due = sla_due_at(c.state, c.state_entered_at, c.urgency_tier)
        record_event(
            db,
            sandbox_id=sb.id,
            case_id=c.id,
            event_type="OWNER_ASSIGNED",
            actor_role=target or "clinician",
            actor_id=c.owner_id,
            from_state=c.state,
            to_state=c.state,
            payload={
                "owner_role": target,
                "owner_id": c.owner_id,
                "sla_due_at": due.isoformat() if due else None,
            },
            at=clock(),
        )
        db.commit()
    return {}


def patient_comms_node(state: CareLoopGraphState) -> CareLoopGraphState:
    """Queue a multilingual outbox message and write MESSAGE_QUEUED when notification is needed."""
    with open_graph_db() as db:
        c, sb, pat, clock = load_graph_ctx(db, state)
        now = clock()
        stmt = select(Message).where(Message.case_id == c.id, Message.direction == "out")
        existing = db.scalar(stmt)
        if existing is not None and c.state not in {
            CaseState.RESULT_ISSUED.value,
            CaseState.PATIENT_NOTIFIED.value,
        }:
            return {"message": {"id": existing.id, "body": existing.body}}

        msg_facts = {
            "language": pat.language,
            "test_name": c.screening_type,
            "urgency_code": "soon" if c.urgency_tier == 1 else "routine",
            "due_date": (now + timedelta(days=5)).strftime("%Y-%m-%d"),
            "reply_instruction": "Reply in the portal by clicking 'I understand'.",
        }
        llm_msg = generate_validated_llm_output(
            LLMKind.PATIENT_MESSAGE.value, msg_facts, db=db, sandbox_id=sb.id, case_id=c.id
        )
        ch = "portal" if pat.portal_active else "sms"
        row = Message(
            sandbox_id=sb.id,
            case_id=c.id,
            channel=ch,
            language=pat.language,
            body=str(llm_msg["output"]["body"]),
            direction="out",
            status="queued",
            at=now,
        )
        db.add(row)
        db.flush()
        record_event(
            db,
            sandbox_id=sb.id,
            case_id=c.id,
            event_type="MESSAGE_QUEUED",
            actor_role="coordinator",
            from_state=c.state,
            to_state=c.state,
            payload={"channel": ch, "message_id": row.id},
            at=now,
        )
        db.commit()
        return {"message": {"id": row.id, "body": row.body, "channel": ch}}


def clinical_router_node(state: CareLoopGraphState) -> CareLoopGraphState:
    """Evaluate escalation rule and perform idempotent upsert on pending_approvals if needed."""
    with open_graph_db() as db:
        c, sb, _, clock = load_graph_ctx(db, state)
        now = clock()
        in_msg = db.scalar(
            select(Message)
            .where(Message.case_id == c.id, Message.direction == "in")
            .order_by(Message.at.desc())
        )
        ref = db.scalar(
            select(Referral).where(Referral.case_id == c.id).order_by(Referral.created_at.desc())
        )
        ref_rejected = c.state == CaseState.REJECTED.value or (
            ref is not None and ref.status == "rejected"
        )
        esc, reasons = evaluate_escalation(
            urgency_tier=c.urgency_tier,
            overdue=is_overdue(c.state, c.state_entered_at, c.urgency_tier, clock=clock),
            p_dropoff=float(state["risk"]["p_dropoff"]),
            teachback_label=in_msg.teachback_label if in_msg else None,
            referral_rejected=ref_rejected,
            ads=float(state.get("summary", {}).get("ads", 0.0)),
            closure_override_requested=bool(
                state.get("closure_result", {}).get("override_requested")
            ),
        )
        act_type = (
            ActionType.REASSIGN_OWNER.value
            if c.state == CaseState.REJECTED.value
            else ActionType.PRIORITY_REBOOK.value
            if c.state == CaseState.APPOINTMENT_BOOKED.value and esc
            else ActionType.CREATE_NAVIGATOR_TASK.value
            if esc
            else ActionType.SEND_PORTAL_MESSAGE.value
        )
        suggested = {
            "action_type": act_type,
            "action_key": f"{c.id}:{c.state}:{act_type}",
            "channel": "sms" if esc else "portal",
            "owner_id": c.owner_id or "coord-1",
        }
        if esc:
            c.escalated = True
            upsert_pending_approval(
                db,
                sandbox_id=sb.id,
                case_id=c.id,
                action_type=act_type,
                payload=suggested,
                reasons=reasons,
                at=now,
            )
        db.commit()
        return {"reasons": reasons, "requires_human": esc, "suggested_action": suggested}


def hitl_gate_node(state: CareLoopGraphState) -> CareLoopGraphState:
    """Human-in-the-loop gate using LangGraph interrupt() (zero side effects before interrupt)."""
    resume_value: dict[str, Any] = interrupt(
        {
            "case_id": state["case_id"],
            "suggested_action": state.get("suggested_action"),
            "reasons": state.get("reasons", []),
        }
    )
    return {"decision": resume_value}


def action_exec_node(state: CareLoopGraphState) -> CareLoopGraphState:
    """Execute the approved, modified, or routine action idempotently."""
    with open_graph_db() as db:
        return {"action_result": execute_graph_action(db, state)}


def closure_check_node(state: CareLoopGraphState) -> CareLoopGraphState:
    """Call domain can_close only when closure is requested."""
    req = state.get("closure_result") or {}
    if not req.get("requested"):
        return {"closure_result": {"checked": False, "can_close": False}}
    with open_graph_db() as db:
        return {"closure_result": evaluate_graph_closure(db, state)}


def audit_log_node(state: CareLoopGraphState) -> CareLoopGraphState:
    """Write append-only GRAPH_COMPLETED event into case_events."""
    with open_graph_db() as db:
        c, sb, _, clock = load_graph_ctx(db, state)
        record_event(
            db,
            sandbox_id=sb.id,
            case_id=c.id,
            event_type="GRAPH_COMPLETED",
            actor_role="system",
            from_state=c.state,
            to_state=c.state,
            payload={
                "requires_human": bool(state.get("requires_human")),
                "action_result": state.get("action_result"),
            },
            at=clock(),
        )
        db.commit()
    return {}
