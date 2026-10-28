"""Deterministic builder for the 60 seed cases (5 per archetype 1..12) in ml/artifacts/seed.json."""
import hashlib
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from ml.data.schema import INSURANCE_CATEGORIES, SCREENING_TYPES

logger = logging.getLogger(__name__)

BASE_TIME = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)

ARCHETYPES: tuple[dict[str, Any], ...] = (
    {
        "id": 1,
        "name": "urgent_just_issued_unassigned",
        "state": "RESULT_ISSUED",
        "urgency_tier": 1,
        "owner_id": None,
        "hours_in_state": 4.0,
        "escalated": False,
        "acknowledged": False,
    },
    {
        "id": 2,
        "name": "notified_not_acknowledged_overdue",
        "state": "PATIENT_NOTIFIED",
        "urgency_tier": 2,
        "owner_id": "coord-1",
        "hours_in_state": 60.0,
        "escalated": True,
        "acknowledged": False,
    },
    {
        "id": 3,
        "name": "acknowledged_teachback_confused_escalated",
        "state": "ACKNOWLEDGED",
        "urgency_tier": 2,
        "owner_id": "coord-2",
        "hours_in_state": 18.0,
        "escalated": True,
        "acknowledged": True,
        "teachback_label": "confused",
    },
    {
        "id": 4,
        "name": "confirmatory_pending_near_sla",
        "state": "CONFIRMATORY_PENDING",
        "urgency_tier": 2,
        "owner_id": "clin-1",
        "hours_in_state": 310.0,
        "escalated": False,
        "acknowledged": True,
    },
    {
        "id": 5,
        "name": "referral_sent_awaiting_acceptance",
        "state": "REFERRAL_SENT",
        "urgency_tier": 2,
        "owner_id": "clin-2",
        "hours_in_state": 30.0,
        "escalated": False,
        "acknowledged": True,
        "referral_status": "sent",
    },
    {
        "id": 6,
        "name": "referral_rejected_needing_reassignment",
        "state": "REJECTED",
        "urgency_tier": 1,
        "owner_id": "coord-1",
        "hours_in_state": 8.0,
        "escalated": True,
        "acknowledged": True,
        "referral_status": "rejected",
        "reason_code": "referral_rejected_capacity",
    },
    {
        "id": 7,
        "name": "accepted_no_appointment",
        "state": "REFERRAL_ACCEPTED",
        "urgency_tier": 2,
        "owner_id": "clin-1",
        "hours_in_state": 48.0,
        "escalated": False,
        "acknowledged": True,
        "referral_status": "accepted",
    },
    {
        "id": 8,
        "name": "appointment_missed_rebook_needed",
        "state": "APPOINTMENT_BOOKED",
        "urgency_tier": 1,
        "owner_id": "coord-2",
        "hours_in_state": 96.0,
        "escalated": True,
        "acknowledged": True,
        "referral_status": "accepted",
        "missed_visit": True,
    },
    {
        "id": 9,
        "name": "seen_no_treatment_plan_recorded",
        "state": "SEEN",
        "urgency_tier": 2,
        "owner_id": "clin-2",
        "hours_in_state": 50.0,
        "escalated": False,
        "acknowledged": True,
        "referral_status": "accepted",
    },
    {
        "id": 10,
        "name": "in_surveillance_ready_to_close_with_evidence",
        "state": "TREATMENT_OR_SURVEILLANCE",
        "urgency_tier": 3,
        "owner_id": "clin-1",
        "hours_in_state": 120.0,
        "escalated": False,
        "acknowledged": True,
        "referral_status": "accepted",
        "ready_closure_evidence": "surveillance_plan",
    },
    {
        "id": 11,
        "name": "closed_with_evidence",
        "state": "CLOSED",
        "urgency_tier": 2,
        "owner_id": None,
        "hours_in_state": 24.0,
        "escalated": False,
        "acknowledged": True,
        "referral_status": "accepted",
        "closure_kind": "evidence",
        "closure_evidence": "treatment_started",
    },
    {
        "id": 12,
        "name": "closed_by_authorized_override_with_reason",
        "state": "CLOSED",
        "urgency_tier": 3,
        "owner_id": None,
        "hours_in_state": 12.0,
        "escalated": False,
        "acknowledged": True,
        "referral_status": "accepted",
        "closure_kind": "override",
        "override_reason": "Patient relocated and confirmed care at out-of-state oncology center",
    },
)

OWNER_ROLE_BY_STATE: dict[str, str | None] = {
    "RESULT_ISSUED": "clinician",
    "PATIENT_NOTIFIED": "coordinator",
    "ACKNOWLEDGED": "coordinator",
    "CONFIRMATORY_PENDING": "clinician",
    "REFERRAL_SENT": "clinician",
    "REJECTED": "coordinator",
    "REFERRAL_ACCEPTED": "clinician",
    "APPOINTMENT_BOOKED": "coordinator",
    "SEEN": "clinician",
    "TREATMENT_OR_SURVEILLANCE": "clinician",
    "CLOSED": None,
}

PATH_TO_STATE: dict[str, list[tuple[str, str | None]]] = {
    "RESULT_ISSUED": [("RESULT_ISSUED", None)],
    "PATIENT_NOTIFIED": [
        ("RESULT_ISSUED", None),
        ("PATIENT_NOTIFIED", "message_sent"),
    ],
    "ACKNOWLEDGED": [
        ("RESULT_ISSUED", None),
        ("PATIENT_NOTIFIED", "message_sent"),
        ("ACKNOWLEDGED", "acknowledgement"),
    ],
    "CONFIRMATORY_PENDING": [
        ("RESULT_ISSUED", None),
        ("PATIENT_NOTIFIED", "message_sent"),
        ("ACKNOWLEDGED", "acknowledgement"),
        ("CONFIRMATORY_PENDING", "confirmatory_ordered"),
    ],
    "REFERRAL_SENT": [
        ("RESULT_ISSUED", None),
        ("PATIENT_NOTIFIED", "message_sent"),
        ("ACKNOWLEDGED", "acknowledgement"),
        ("REFERRAL_SENT", "referral_created"),
    ],
    "REJECTED": [
        ("RESULT_ISSUED", None),
        ("PATIENT_NOTIFIED", "message_sent"),
        ("ACKNOWLEDGED", "acknowledgement"),
        ("REFERRAL_SENT", "referral_created"),
        ("REJECTED", "referral_rejected"),
    ],
    "REFERRAL_ACCEPTED": [
        ("RESULT_ISSUED", None),
        ("PATIENT_NOTIFIED", "message_sent"),
        ("ACKNOWLEDGED", "acknowledgement"),
        ("REFERRAL_SENT", "referral_created"),
        ("REFERRAL_ACCEPTED", "referral_accepted"),
    ],
    "APPOINTMENT_BOOKED": [
        ("RESULT_ISSUED", None),
        ("PATIENT_NOTIFIED", "message_sent"),
        ("ACKNOWLEDGED", "acknowledgement"),
        ("REFERRAL_SENT", "referral_created"),
        ("REFERRAL_ACCEPTED", "referral_accepted"),
        ("APPOINTMENT_BOOKED", "appointment_booked"),
    ],
    "SEEN": [
        ("RESULT_ISSUED", None),
        ("PATIENT_NOTIFIED", "message_sent"),
        ("ACKNOWLEDGED", "acknowledgement"),
        ("REFERRAL_SENT", "referral_created"),
        ("REFERRAL_ACCEPTED", "referral_accepted"),
        ("APPOINTMENT_BOOKED", "appointment_booked"),
        ("SEEN", "attendance_recorded"),
    ],
    "TREATMENT_OR_SURVEILLANCE": [
        ("RESULT_ISSUED", None),
        ("PATIENT_NOTIFIED", "message_sent"),
        ("ACKNOWLEDGED", "acknowledgement"),
        ("REFERRAL_SENT", "referral_created"),
        ("REFERRAL_ACCEPTED", "referral_accepted"),
        ("APPOINTMENT_BOOKED", "appointment_booked"),
        ("SEEN", "attendance_recorded"),
        ("TREATMENT_OR_SURVEILLANCE", "plan_recorded"),
    ],
    "CLOSED": [
        ("RESULT_ISSUED", None),
        ("PATIENT_NOTIFIED", "message_sent"),
        ("ACKNOWLEDGED", "acknowledgement"),
        ("REFERRAL_SENT", "referral_created"),
        ("REFERRAL_ACCEPTED", "referral_accepted"),
        ("APPOINTMENT_BOOKED", "appointment_booked"),
        ("SEEN", "attendance_recorded"),
        ("TREATMENT_OR_SURVEILLANCE", "plan_recorded"),
        ("CLOSED", None),
    ],
}


def _patient_message_text(lang: str, screening: str, due_date: str) -> str:
    if lang == "hi":
        return (
            f"नमस्ते, आपकी {screening} जाँच का परिणाम आ गया है। "
            f"कृपया {due_date} तक अगले कदम की पुष्टि करें। "
            "जवाब देने के लिए पोर्टल में 'मैं समझता हूँ' चुनें।"
        )
    if lang == "es":
        return (
            f"Hola, su resultado de {screening} está listo. "
            f"Por favor confirme el siguiente paso antes del {due_date}. "
            "Responda en el portal seleccionando 'Entiendo'."
        )
    return (
        f"Hello, your {screening} screening result is ready for follow-up. "
        f"Please confirm your next step by {due_date}. "
        "Reply in the patient portal by clicking 'I understand'."
    )


def build_seed_cases() -> dict[str, Any]:
    """Generate all 60 seed cases (5 per archetype) with full history and pre-generated outputs."""
    cases: list[dict[str, Any]] = []
    langs = ("en", "hi", "es", "en", "es")
    idx = 0

    for arch in ARCHETYPES:
        for rep in range(5):
            idx += 1
            case_id = f"seed-case-{idx:03d}"
            patient_id = f"seed-pat-{idx:03d}"
            pt_token = f"pt-seed-{idx:03d}"
            pt_token_hash = hashlib.sha256(pt_token.encode()).hexdigest()
            lang = langs[rep % len(langs)]
            screening = SCREENING_TYPES[(idx - 1) % len(SCREENING_TYPES)]
            ins = INSURANCE_CATEGORIES[(idx - 1) % len(INSURANCE_CATEGORIES)]

            tier = int(arch["urgency_tier"])
            urgent_flag = 1 if tier == 1 else 0
            severity_grade = 4 if tier == 1 else (3 if tier == 2 else 2)
            age = 38 + (idx * 7) % 45
            distance = round(4.5 + ((idx * 11) % 55), 1)
            portal_active = (idx % 3) != 0
            noshow_count = (idx * 2) % 6 if arch["escalated"] else idx % 2
            extra_ns = 0.25 if arch["escalated"] else 0.05
            noshow_ratio = round(min(0.85, noshow_count / 7.0 + extra_ns), 2)
            lead_time = 28 if arch["escalated"] else 12
            finding_days = 5 + (idx % 14)

            p_dropoff = round(
                0.74 - 0.02 * rep if arch["escalated"] else 0.28 + 0.03 * rep, 3
            )
            hrs_in_state = float(arch["hours_in_state"]) + rep * 1.5
            state_entered_at = BASE_TIME - timedelta(hours=hrs_in_state)

            path = PATH_TO_STATE[arch["state"]]
            created_at = state_entered_at - timedelta(hours=18 * max(1, len(path) - 1))

            events: list[dict[str, Any]] = []
            evidences: list[dict[str, Any]] = []
            prev_st: str | None = None
            for step_i, (st, ev_type) in enumerate(path):
                ev_time = (
                    state_entered_at
                    if step_i == len(path) - 1
                    else created_at + timedelta(hours=18 * step_i)
                )
                actor_role = OWNER_ROLE_BY_STATE.get(st) or "clinician"
                events.append(
                    {
                        "event_type": "STATE_CHANGED" if prev_st else "CASE_ISSUED",
                        "from_state": prev_st,
                        "to_state": st,
                        "actor_role": actor_role,
                        "actor_id": arch["owner_id"] or "system",
                        "payload": {"archetype": arch["name"]},
                        "at": ev_time.isoformat(),
                    }
                )
                if ev_type:
                    evidences.append(
                        {
                            "type": ev_type,
                            "ref": f"ev-{case_id}-{step_i}",
                            "created_by": actor_role,
                            "at": ev_time.isoformat(),
                        }
                    )
                prev_st = st

            if arch.get("missed_visit"):
                events.append(
                    {
                        "event_type": "VISIT_MISSED_REBOOK_NEEDED",
                        "from_state": "APPOINTMENT_BOOKED",
                        "to_state": "APPOINTMENT_BOOKED",
                        "actor_role": "coordinator",
                        "actor_id": arch["owner_id"] or "coord-2",
                        "payload": {"reason": "patient_noshow"},
                        "at": (state_entered_at + timedelta(hours=12)).isoformat(),
                    }
                )

            if arch.get("ready_closure_evidence"):
                evidences.append(
                    {
                        "type": arch["ready_closure_evidence"],
                        "ref": f"ev-close-ready-{case_id}",
                        "created_by": "clinician",
                        "at": (state_entered_at + timedelta(hours=6)).isoformat(),
                    }
                )

            if arch.get("closure_evidence"):
                evidences.append(
                    {
                        "type": arch["closure_evidence"],
                        "ref": f"ev-close-{case_id}",
                        "created_by": "clinician",
                        "at": state_entered_at.isoformat(),
                    }
                )

            due_date_str = (BASE_TIME + timedelta(days=5)).strftime("%Y-%m-%d")
            msg_body = _patient_message_text(lang, screening, due_date_str)
            messages = [
                {
                    "channel": "portal" if portal_active else "sms",
                    "language": lang,
                    "body": msg_body,
                    "direction": "out",
                    "status": "delivered",
                    "teachback_label": None,
                    "at": (created_at + timedelta(hours=2)).isoformat(),
                }
            ]
            if arch.get("teachback_label"):
                messages.append(
                    {
                        "channel": "portal",
                        "language": lang,
                        "body": "I am not sure what test I need or when to come in.",
                        "direction": "in",
                        "status": "received",
                        "teachback_label": arch["teachback_label"],
                        "at": (state_entered_at + timedelta(hours=1)).isoformat(),
                    }
                )

            shap_pos = [
                {
                    "feature": "prior_noshow_ratio",
                    "label": "Prior no-show ratio",
                    "value": 0.42,
                },
                {
                    "feature": "scheduling_lead_time",
                    "label": "Scheduling lead time (days)",
                    "value": 0.28,
                },
                {
                    "feature": "distance_miles",
                    "label": "Distance to clinic (miles)",
                    "value": 0.19,
                },
            ]
            shap_neg = [
                {
                    "feature": "digital_portal_active",
                    "label": "Active patient portal",
                    "value": -0.31,
                },
                {
                    "feature": "acknowledged_flag",
                    "label": "Result acknowledged",
                    "value": -0.18,
                },
                {"feature": "patient_age", "label": "Patient age", "value": -0.09},
            ]
            survival_curve = [
                {
                    "day": d,
                    "s": round(max(0.04, 1.0 - (d / 130.0) * (1.15 - 0.5 * p_dropoff)), 3),
                }
                for d in (0, 15, 30, 45, 60, 75, 90, 105, 120)
            ]

            pct_drop = int(round(p_dropoff * 100))
            summary_out = {
                "summary_lines": [
                    f"Case {case_id} ({screening}) is currently in {arch['state']}.",
                    f"Estimated drop-off probability is {pct_drop}%.",
                    f"Assigned owner role: {OWNER_ROLE_BY_STATE.get(arch['state']) or 'none'}.",
                ],
                "next_step": (
                    "Review pending human approval and execute outreach."
                    if arch["escalated"]
                    else "Complete current stage milestone before SLA deadline."
                ),
                "cited_drivers": [
                    "prior_noshow_ratio",
                    "scheduling_lead_time",
                    "distance_miles",
                ],
            }

            sbar_out = {
                "situation": (
                    f"{screening} abnormality requiring specialist evaluation ({case_id})."
                ),
                "background": (
                    f"Severity grade {severity_grade}, urgency tier {tier}, "
                    f"{finding_days} days from finding to order."
                ),
                "assessment": (
                    f"Current state {arch['state']} with drop-off risk {pct_drop} percent."
                ),
                "recommendation": (
                    "Accept referral and schedule diagnostic appointment within SLA window."
                ),
            }

            referral_obj = None
            if arch.get("referral_status"):
                referral_obj = {
                    "from_org": "Community Primary Care Screening Clinic",
                    "to_org": "Regional Diagnostic Specialty Center",
                    "status": arch["referral_status"],
                    "reason_code": arch.get("reason_code"),
                    "sbar": sbar_out,
                    "created_at": (state_entered_at - timedelta(hours=4)).isoformat(),
                    "decided_at": (
                        state_entered_at.isoformat()
                        if arch["referral_status"] in {"accepted", "rejected"}
                        else None
                    ),
                }

            pending_approval = None
            if arch["escalated"] and arch["state"] != "CLOSED":
                pending_approval = {
                    "action_type": (
                        "reassign_owner"
                        if arch["state"] == "REJECTED"
                        else (
                            "priority_rebook"
                            if arch.get("missed_visit")
                            else "create_navigator_task"
                        )
                    ),
                    "payload": {"channel": "sms", "owner_id": arch["owner_id"] or "coord-1"},
                    "reasons": ["escalated_case", arch["name"]],
                    "status": "pending",
                }

            closure_obj = None
            if arch["state"] == "CLOSED":
                closure_obj = {
                    "kind": arch["closure_kind"],
                    "evidence_type": arch.get("closure_evidence"),
                    "override_by": "clin-lead" if arch["closure_kind"] == "override" else None,
                    "override_reason": arch.get("override_reason"),
                    "at": state_entered_at.isoformat(),
                }

            closed_at_iso = (
                state_entered_at.isoformat() if arch["state"] == "CLOSED" else None
            )
            risk_stage = (
                arch["state"]
                if arch["state"] != "CLOSED"
                else "TREATMENT_OR_SURVEILLANCE"
            )
            msg_hash = hashlib.sha256(f"msg:{case_id}:{lang}".encode()).hexdigest()

            cases.append(
                {
                    "case_id": case_id,
                    "archetype_id": arch["id"],
                    "archetype_name": arch["name"],
                    "patient": {
                        "id": patient_id,
                        "alias": f"PT-{idx:03d}",
                        "age": age,
                        "language": lang,
                        "insurance": ins,
                        "distance_miles": distance,
                        "portal_active": portal_active,
                        "prior_noshow_count": noshow_count,
                        "prior_noshow_ratio": noshow_ratio,
                        "days_since_last_encounter": 45 + (idx * 13) % 400,
                    },
                    "case": {
                        "id": case_id,
                        "patient_id": patient_id,
                        "screening_type": screening,
                        "severity_grade": severity_grade,
                        "urgency_tier": tier,
                        "urgent_flag": urgent_flag,
                        "state": arch["state"],
                        "state_entered_at": state_entered_at.isoformat(),
                        "owner_role": OWNER_ROLE_BY_STATE.get(arch["state"]),
                        "owner_id": arch["owner_id"],
                        "escalated": bool(arch["escalated"]),
                        "finding_to_order_days": finding_days,
                        "scheduling_lead_time": lead_time,
                        "contact_attempts": 2 if arch["escalated"] else 1,
                        "acknowledged": bool(arch["acknowledged"]),
                        "patient_token": pt_token,
                        "patient_token_hash": pt_token_hash,
                        "created_at": created_at.isoformat(),
                        "closed_at": closed_at_iso,
                    },
                    "risk": {
                        "stage": risk_stage,
                        "p_dropoff": p_dropoff,
                        "median_days": round(18.0 + 35.0 * p_dropoff, 1),
                        "p_open_30": round(float(survival_curve[2]["s"]), 3),
                        "p_open_60": round(float(survival_curve[4]["s"]), 3),
                        "p_open_90": round(float(survival_curve[6]["s"]), 3),
                        "shap": {"top_positive": shap_pos, "top_negative": shap_neg},
                        "survival_curve": survival_curve,
                        "model_version": "1.0.0-seed",
                    },
                    "events": events,
                    "evidence": evidences,
                    "messages": messages,
                    "referral": referral_obj,
                    "consults": [
                        {
                            "kind": "clinician_to_clinician",
                            "status": "open" if arch["escalated"] else "answered",
                            "thread": [
                                {
                                    "sender_role": "coordinator",
                                    "body": f"Please review follow-up pathway for {case_id}.",
                                    "at": state_entered_at.isoformat(),
                                }
                            ],
                            "created_at": state_entered_at.isoformat(),
                        }
                    ],
                    "pending_approval": pending_approval,
                    "closure": closure_obj,
                    "delay_reasons": (
                        [
                            {
                                "code": arch.get("reason_code") or "transport_barrier",
                                "proposed_by": "llm",
                                "confirmed": True,
                            }
                        ]
                        if arch["escalated"]
                        else []
                    ),
                    "llm_outputs": [
                        {
                            "kind": "case_summary",
                            "input_hash": hashlib.sha256(
                                f"summary:{case_id}".encode()
                            ).hexdigest(),
                            "output": summary_out,
                            "source": "template",
                            "faithful_ok": True,
                            "ads": 0.0,
                        },
                        {
                            "kind": "patient_message",
                            "input_hash": msg_hash,
                            "output": {"body": msg_body},
                            "source": "template",
                            "faithful_ok": True,
                            "ads": 0.0,
                        },
                        {
                            "kind": "sbar_note",
                            "input_hash": hashlib.sha256(
                                f"sbar:{case_id}".encode()
                            ).hexdigest(),
                            "output": sbar_out,
                            "source": "template",
                            "faithful_ok": True,
                            "ads": 0.0,
                        },
                    ],
                }
            )

    return {
        "base_time": BASE_TIME.isoformat(),
        "case_count": len(cases),
        "cases": cases,
    }
