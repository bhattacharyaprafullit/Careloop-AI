"""LangGraph node implementations for CareLoop AI (M7).

Rule: hitl_gate has zero side effects before interrupt() as it re-runs on resume.
"""
import logging
from datetime import timedelta
from typing import Any

from langgraph.types import interrupt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Case,
    CaseEvent,
    Closure,
    Evidence,
    Message,
    Patient,
    PendingApproval,
    Referral,
    RiskScore,
    Sandbox,
)
from app.db.repo import clock_for_sandbox
from app.db.session import get_engine
from app.domain.closure import can_close
from app.domain.priority import evaluate_escalation
from app.domain.sla import (
    hours_in_state,
    hours_remaining,
    is_overdue,
    sla_due_at,
)
from app.domain.states import ActionType, CaseState, LLMKind
from app.domain.transitions import STATE_SPECS, owner_role_for_state
from app.graph.state import CareLoopGraphState
from app.llm.client import generate_validated_llm_output
from app.services.events import record_event
from app.services.inference import score_case

logger = logging.getLogger(__name__)


def _db() -> Session:
    return Session(get_engine())


def ingestion_node(state: CareLoopGraphState) -> CareLoopGraphState:
    """Load case and patient context and assemble the 17-feature vector."""
    with _db() as db:
        c = db.scalar(select(Case).where(Case.id == state["case_id"]))
        if c is None:
            raise ValueError(f"Case {state['case_id']} not found")
        pat = db.scalar(select(Patient).where(Patient.id == c.patient_id))
        sb = db.scalar(select(Sandbox).where(Sandbox.id == c.sandbox_id))
        if pat is None or sb is None:
            raise ValueError("Missing patient or sandbox for case")
        clock = clock_for_sandbox(sb)
        days_st = round(hours_in_state(c.state_entered_at, clock=clock) / 24.0, 2)
        features = {
            "screening_type": c.screening_type,
            "severity_grade": c.severity_grade,
            "urgent_flag": 1 if c.urgency_tier == 1 else 0,
            "finding_to_order_days": c.finding_to_order_days,
            "prior_noshow_count": pat.prior_noshow_count,
            "prior_noshow_ratio": pat.prior_noshow_ratio,
            "days_since_last_encounter": pat.days_since_last_encounter,
            "scheduling_lead_time": c.scheduling_lead_time,
            "distance_miles": pat.distance_miles,
            "insurance_category": pat.insurance,
            "patient_age": pat.age,
            "preferred_language": pat.language,
            "digital_portal_active": 1 if pat.portal_active else 0,
            "stage": c.state if c.state != "CLOSED" else "TREATMENT_OR_SURVEILLANCE",
            "days_in_stage": days_st,
            "contact_attempts": c.contact_attempts,
            "acknowledged_flag": 1 if c.acknowledged else 0,
        }
        return {"features": features, "sandbox_id": sb.id}


def ml_inference_node(state: CareLoopGraphState) -> CareLoopGraphState:
    """Score case with calibrated XGBoost + survival + SHAP and insert risk_scores row."""
    scored = score_case(state["features"])
    with _db() as db:
        c = db.scalar(select(Case).where(Case.id == state["case_id"]))
        sb = db.scalar(select(Sandbox).where(Sandbox.id == state["sandbox_id"]))
        assert c is not None and sb is not None
        now = clock_for_sandbox(sb)()
        db.add(
            RiskScore(
                sandbox_id=sb.id,
                case_id=c.id,
                stage=str(scored["stage"]),
                p_dropoff=float(scored["p_dropoff"]),
                median_days=float(scored["median_days"]),
                p_open_30=float(scored["p_open_30"]),
                p_open_60=float(scored["p_open_60"]),
                p_open_90=float(scored["p_open_90"]),
                shap=scored["shap"],
                survival_curve=scored["survival_curve"],
                model_version=str(scored["model_version"]),
                at=now,
            )
        )
        db.commit()
    return {
        "risk": {
            "stage": scored["stage"],
            "p_dropoff": scored["p_dropoff"],
            "median_days": scored["median_days"],
            "p_open_30": scored["p_open_30"],
            "p_open_60": scored["p_open_60"],
            "p_open_90": scored["p_open_90"],
            "model_version": scored["model_version"],
        },
        "shap": scored["shap"],
    }


def summarizer_node(state: CareLoopGraphState) -> CareLoopGraphState:
    """Generate validated case_summary, compute ADS, and log to llm_outputs."""
    with _db() as db:
        c = db.scalar(select(Case).where(Case.id == state["case_id"]))
        sb = db.scalar(select(Sandbox).where(Sandbox.id == state["sandbox_id"]))
        assert c is not None and sb is not None
        clock = clock_for_sandbox(sb)
        rem_h = hours_remaining(c.state, c.state_entered_at, c.urgency_tier, clock=clock)
        spec = STATE_SPECS[CaseState(c.state)]
        existing_ev = set(
            db.scalars(select(Evidence.type).where(Evidence.case_id == c.id))
        )
        gaps = sorted(spec.required_entry_evidence - existing_ev)

        facts = {
            "state": c.state,
            "owner_role": c.owner_role or owner_role_for_state(c.state) or "clinician",
            "days_in_state": round(state["features"]["days_in_stage"], 1),
            "sla_hours_remaining": round(rem_h if rem_h is not None else 0.0, 1),
            "p_dropoff_percent": int(round(float(state["risk"]["p_dropoff"]) * 100)),
            "shap_top_positive": state["shap"]["top_positive"],
            "shap_top_negative": state["shap"]["top_negative"],
            "evidence_gaps": gaps,
        }
        llm_res = generate_validated_llm_output(
            LLMKind.CASE_SUMMARY.value,
            facts,
            db=db,
            sandbox_id=sb.id,
            case_id=c.id,
        )
        db.commit()
        return {
            "summary": {
                **llm_res["output"],
                "ads": llm_res["ads"],
                "source": llm_res["source"],
            }
        }


def ownership_node(state: CareLoopGraphState) -> CareLoopGraphState:
    """Ensure owner_role is set for the current state and record OWNER_ASSIGNED."""
    with _db() as db:
        c = db.scalar(select(Case).where(Case.id == state["case_id"]))
        sb = db.scalar(select(Sandbox).where(Sandbox.id == state["sandbox_id"]))
        assert c is not None and sb is not None
        now = clock_for_sandbox(sb)()
        target_role = owner_role_for_state(c.state)
        c.owner_role = target_role
        due = sla_due_at(c.state, c.state_entered_at, c.urgency_tier)
        record_event(
            db,
            sandbox_id=sb.id,
            case_id=c.id,
            event_type="OWNER_ASSIGNED",
            actor_role=target_role or "clinician",
            actor_id=c.owner_id,
            from_state=c.state,
            to_state=c.state,
            payload={
                "owner_role": target_role,
                "owner_id": c.owner_id,
                "sla_due_at": due.isoformat() if due else None,
            },
            at=now,
        )
        db.commit()
    return {}


def patient_comms_node(state: CareLoopGraphState) -> CareLoopGraphState:
    """Queue a multilingual outbox message and write MESSAGE_QUEUED when notification is needed."""
    with _db() as db:
        c = db.scalar(select(Case).where(Case.id == state["case_id"]))
        sb = db.scalar(select(Sandbox).where(Sandbox.id == state["sandbox_id"]))
        pat = db.scalar(select(Patient).where(Patient.id == c.patient_id)) if c else None
        assert c is not None and sb is not None and pat is not None
        now = clock_for_sandbox(sb)()

        existing_msg = db.scalar(
            select(Message).where(Message.case_id == c.id, Message.direction == "out")
        )
        if existing_msg is not None and c.state not in {
            CaseState.RESULT_ISSUED.value,
            CaseState.PATIENT_NOTIFIED.value,
        }:
            return {"message": {"id": existing_msg.id, "body": existing_msg.body}}

        due_str = (now + timedelta(days=5)).strftime("%Y-%m-%d")
        msg_facts = {
            "language": pat.language,
            "test_name": c.screening_type,
            "urgency_code": "soon" if c.urgency_tier == 1 else "routine",
            "due_date": due_str,
            "reply_instruction": "Reply in the portal by clicking 'I understand'.",
        }
        llm_msg = generate_validated_llm_output(
            LLMKind.PATIENT_MESSAGE.value,
            msg_facts,
            db=db,
            sandbox_id=sb.id,
            case_id=c.id,
        )
        channel = "portal" if pat.portal_active else "sms"
        msg_row = Message(
            sandbox_id=sb.id,
            case_id=c.id,
            channel=channel,
            language=pat.language,
            body=str(llm_msg["output"]["body"]),
            direction="out",
            status="queued",
            at=now,
        )
        db.add(msg_row)
        db.flush()
        record_event(
            db,
            sandbox_id=sb.id,
            case_id=c.id,
            event_type="MESSAGE_QUEUED",
            actor_role="coordinator",
            from_state=c.state,
            to_state=c.state,
            payload={"channel": channel, "message_id": msg_row.id},
            at=now,
        )
        db.commit()
        return {"message": {"id": msg_row.id, "body": msg_row.body, "channel": channel}}


def clinical_router_node(state: CareLoopGraphState) -> CareLoopGraphState:
    """Evaluate escalation rule and perform idempotent upsert on pending_approvals if needed."""
    with _db() as db:
        c = db.scalar(select(Case).where(Case.id == state["case_id"]))
        sb = db.scalar(select(Sandbox).where(Sandbox.id == state["sandbox_id"]))
        assert c is not None and sb is not None
        clock = clock_for_sandbox(sb)
        now = clock()

        overdue = is_overdue(c.state, c.state_entered_at, c.urgency_tier, clock=clock)
        p_drop = float(state["risk"]["p_dropoff"])
        ads = float(state.get("summary", {}).get("ads", 0.0))

        latest_in_msg = db.scalar(
            select(Message)
            .where(Message.case_id == c.id, Message.direction == "in")
            .order_by(Message.at.desc())
        )
        tb_label = latest_in_msg.teachback_label if latest_in_msg else None

        latest_ref = db.scalar(
            select(Referral)
            .where(Referral.case_id == c.id)
            .order_by(Referral.created_at.desc())
        )
        ref_rejected = c.state == CaseState.REJECTED.value or (
            latest_ref is not None and latest_ref.status == "rejected"
        )

        esc, reasons = evaluate_escalation(
            urgency_tier=c.urgency_tier,
            overdue=overdue,
            p_dropoff=p_drop,
            teachback_label=tb_label,
            referral_rejected=ref_rejected,
            ads=ads,
            closure_override_requested=bool(
                state.get("closure_result", {}).get("override_requested")
            ),
        )

        if c.state == CaseState.REJECTED.value:
            act_type = ActionType.REASSIGN_OWNER.value
        elif c.state == CaseState.APPOINTMENT_BOOKED.value and esc:
            act_type = ActionType.PRIORITY_REBOOK.value
        elif esc:
            act_type = ActionType.CREATE_NAVIGATOR_TASK.value
        else:
            act_type = ActionType.SEND_PORTAL_MESSAGE.value

        action_key = f"{c.id}:{c.state}:{act_type}"
        suggested = {
            "action_type": act_type,
            "action_key": action_key,
            "channel": "sms" if esc else "portal",
            "owner_id": c.owner_id or "coord-1",
        }

        if esc:
            c.escalated = True
            # Idempotent upsert into pending_approvals keyed by case_id and action_type
            existing_pa = db.scalar(
                select(PendingApproval).where(
                    PendingApproval.case_id == c.id,
                    PendingApproval.status == "pending",
                )
            )
            if existing_pa is None:
                db.add(
                    PendingApproval(
                        sandbox_id=sb.id,
                        case_id=c.id,
                        action_type=act_type,
                        payload=suggested,
                        reasons=reasons,
                        status="pending",
                        at=now,
                    )
                )
            else:
                existing_pa.action_type = act_type
                existing_pa.payload = suggested
                existing_pa.reasons = reasons
        db.commit()

        return {
            "reasons": reasons,
            "requires_human": esc,
            "suggested_action": suggested,
        }


def hitl_gate_node(state: CareLoopGraphState) -> CareLoopGraphState:
    """Human-in-the-loop gate using LangGraph interrupt().

    No side effects before interrupt() because the node re-executes from the top on resume.
    """
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
    with _db() as db:
        c = db.scalar(select(Case).where(Case.id == state["case_id"]))
        sb = db.scalar(select(Sandbox).where(Sandbox.id == state["sandbox_id"]))
        assert c is not None and sb is not None
        now = clock_for_sandbox(sb)()

        dec = state.get("decision") or {}
        decision_kind = str(dec.get("decision", "approve"))
        suggested = dict(state.get("suggested_action") or {})
        if decision_kind == "modify" and isinstance(dec.get("modified_action"), dict):
            suggested.update(dec["modified_action"])

        action_key = str(
            suggested.get("action_key") or f"{c.id}:{c.state}:{suggested.get('action_type', 'act')}"
        )

        # Update pending approval if present
        pa = db.scalar(
            select(PendingApproval).where(
                PendingApproval.case_id == c.id,
                PendingApproval.status == "pending",
            )
        )
        if pa is not None:
            pa.status = "decided"
            pa.decision = decision_kind
            pa.decided_by = str(dec.get("decided_by", "coordinator"))
            pa.note = dec.get("note")

        if decision_kind == "reject":
            record_event(
                db,
                sandbox_id=sb.id,
                case_id=c.id,
                event_type="MANUAL_PLAN_RECORDED",
                actor_role=str(dec.get("decided_by", "coordinator")),
                from_state=c.state,
                to_state=c.state,
                payload={"decision": "reject", "note": dec.get("note"), "action_key": action_key},
                at=now,
            )
            db.commit()
            return {"action_result": {"executed": False, "status": "rejected_manual_plan"}}

        # Idempotency check: has ACTION_EXECUTED already been written for this action_key?
        existing_exec = [
            ev
            for ev in db.scalars(
                select(CaseEvent).where(
                    CaseEvent.case_id == c.id,
                    CaseEvent.event_type == "ACTION_EXECUTED",
                )
            )
            if ev.payload.get("action_key") == action_key
        ]
        if not existing_exec:
            if suggested.get("owner_id"):
                c.owner_id = str(suggested["owner_id"])
            c.contact_attempts = int(c.contact_attempts) + 1
            record_event(
                db,
                sandbox_id=sb.id,
                case_id=c.id,
                event_type="ACTION_EXECUTED",
                actor_role=str(dec.get("decided_by", "coordinator")),
                from_state=c.state,
                to_state=c.state,
                payload={
                    "action_key": action_key,
                    "action_type": suggested.get("action_type"),
                    "channel": suggested.get("channel"),
                    "owner_id": c.owner_id,
                    "decision": decision_kind,
                },
                at=now,
            )
        db.commit()
        return {
            "action_result": {
                "executed": True,
                "action_key": action_key,
                "action_type": suggested.get("action_type"),
            }
        }


def closure_check_node(state: CareLoopGraphState) -> CareLoopGraphState:
    """Call domain can_close only when closure is requested."""
    req = state.get("closure_result") or {}
    if not req.get("requested"):
        return {"closure_result": {"checked": False, "can_close": False}}

    with _db() as db:
        c = db.scalar(select(Case).where(Case.id == state["case_id"]))
        assert c is not None
        ev_types = set(db.scalars(select(Evidence.type).where(Evidence.case_id == c.id)))
        override = req.get("override")
        ok, kind_or_msg = can_close(ev_types, override)
        if ok and c.state != CaseState.CLOSED.value:
            c.state = CaseState.CLOSED.value
            c.owner_role = None
            c.owner_id = None
            db.add(
                Closure(
                    sandbox_id=c.sandbox_id,
                    case_id=c.id,
                    kind="override" if kind_or_msg == "authorized_override" else "evidence",
                    evidence_type=req.get("evidence_type"),
                    override_by=override.get("by") if isinstance(override, dict) else None,
                    override_reason=override.get("reason") if isinstance(override, dict) else None,
                )
            )
            db.commit()
        return {"closure_result": {"checked": True, "can_close": ok, "reason": kind_or_msg}}


def audit_log_node(state: CareLoopGraphState) -> CareLoopGraphState:
    """Write append-only GRAPH_COMPLETED event into case_events."""
    with _db() as db:
        c = db.scalar(select(Case).where(Case.id == state["case_id"]))
        sb = db.scalar(select(Sandbox).where(Sandbox.id == state["sandbox_id"]))
        if c is not None and sb is not None:
            now = clock_for_sandbox(sb)()
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
                at=now,
            )
            db.commit()
    return {}
