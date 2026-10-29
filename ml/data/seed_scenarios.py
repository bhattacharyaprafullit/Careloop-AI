"""Deterministic builder for the 60 seed cases (5 per archetype 1..12) in ml/artifacts/seed.json."""
import hashlib
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from ml.data.schema import (
    ARCHETYPES,
    INSURANCE_CATEGORIES,
    OWNER_ROLE_BY_STATE,
    PATH_TO_STATE,
    SCREENING_TYPES,
)

logger = logging.getLogger(__name__)
BASE_TIME = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
_SHAP_POS = [
    {"feature": "prior_noshow_ratio", "label": "Prior no-show ratio", "value": 0.42},
    {"feature": "scheduling_lead_time", "label": "Scheduling lead time (days)", "value": 0.28},
    {"feature": "distance_miles", "label": "Distance to clinic (miles)", "value": 0.19},
]
_SHAP_NEG = [
    {"feature": "digital_portal_active", "label": "Active patient portal", "value": -0.31},
    {"feature": "acknowledged_flag", "label": "Result acknowledged", "value": -0.18},
    {"feature": "patient_age", "label": "Patient age", "value": -0.09},
]


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


def _llm_row(kind: str, raw_key: str, output: dict[str, Any]) -> dict[str, Any]:
    h = hashlib.sha256(raw_key.encode()).hexdigest()
    return {
        "kind": kind, "input_hash": h, "output": output,
        "source": "template", "faithful_ok": True, "ads": 0.0,
    }


def _build_history(
    case_id: str, arch: dict[str, Any], created_at: datetime, state_entered_at: datetime
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    path = PATH_TO_STATE[arch["state"]]
    events, evidences, prev_st = [], [], None
    for step_i, (st, ev_type) in enumerate(path):
        ev_t = (
            state_entered_at
            if step_i == len(path) - 1
            else created_at + timedelta(hours=18 * step_i)
        )
        role = OWNER_ROLE_BY_STATE.get(st) or "clinician"
        events.append({
            "event_type": "STATE_CHANGED" if prev_st else "CASE_ISSUED",
            "from_state": prev_st, "to_state": st, "actor_role": role,
            "actor_id": arch["owner_id"] or "system",
            "payload": {"archetype": arch["name"]}, "at": ev_t.isoformat(),
        })
        if ev_type:
            evidences.append({
                "type": ev_type, "ref": f"ev-{case_id}-{step_i}",
                "created_by": role, "at": ev_t.isoformat(),
            })
        prev_st = st

    if arch.get("missed_visit"):
        events.append({
            "event_type": "VISIT_MISSED_REBOOK_NEEDED",
            "from_state": "APPOINTMENT_BOOKED", "to_state": "APPOINTMENT_BOOKED",
            "actor_role": "coordinator", "actor_id": arch["owner_id"] or "coord-2",
            "payload": {"reason": "patient_noshow"},
            "at": (state_entered_at + timedelta(hours=12)).isoformat(),
        })
    closure_ev_specs = (
        ("ready_closure_evidence", "close-ready", 6),
        ("closure_evidence", "close", 0),
    )
    for key, suffix, offset_h in closure_ev_specs:
        if arch.get(key):
            evidences.append({
                "type": arch[key], "ref": f"ev-{suffix}-{case_id}",
                "created_by": "clinician",
                "at": (state_entered_at + timedelta(hours=offset_h)).isoformat(),
            })
    return events, evidences


def build_seed_cases() -> dict[str, Any]:
    """Generate all 60 seed cases (5 per archetype) with full history and pre-generated outputs."""
    cases: list[dict[str, Any]] = []
    langs = ("en", "hi", "es", "en", "es")
    idx = 0

    for arch in ARCHETYPES:
        for rep in range(5):
            idx += 1
            case_id, patient_id = f"seed-case-{idx:03d}", f"seed-pat-{idx:03d}"
            pt_token = f"pt-seed-{idx:03d}"
            pt_token_hash = hashlib.sha256(pt_token.encode()).hexdigest()
            lang = langs[rep % len(langs)]
            screening = SCREENING_TYPES[(idx - 1) % len(SCREENING_TYPES)]
            ins = INSURANCE_CATEGORIES[(idx - 1) % len(INSURANCE_CATEGORIES)]

            tier = int(arch["urgency_tier"])
            urgent_flag = 1 if tier == 1 else 0
            severity_grade = 4 if tier == 1 else (3 if tier == 2 else 2)
            age, distance = 38 + (idx * 7) % 45, round(4.5 + ((idx * 11) % 55), 1)
            portal_active = (idx % 3) != 0
            noshow_count = (idx * 2) % 6 if arch["escalated"] else idx % 2
            noshow_ratio = round(
                min(0.85, noshow_count / 7.0 + (0.25 if arch["escalated"] else 0.05)), 2
            )
            lead_time, finding_days = (28 if arch["escalated"] else 12), 5 + (idx % 14)

            p_dropoff = round(0.74 - 0.02 * rep if arch["escalated"] else 0.28 + 0.03 * rep, 3)
            hrs = float(arch["hours_in_state"]) + rep * 1.5
            state_entered_at = BASE_TIME - timedelta(hours=hrs)
            path = PATH_TO_STATE[arch["state"]]
            created_at = state_entered_at - timedelta(hours=18 * max(1, len(path) - 1))
            events, evidences = _build_history(case_id, arch, created_at, state_entered_at)

            due_date_str = (BASE_TIME + timedelta(days=5)).strftime("%Y-%m-%d")
            msg_body = _patient_message_text(lang, screening, due_date_str)
            messages: list[dict[str, Any]] = [
                dict(
                    channel="portal" if portal_active else "sms",
                    language=lang,
                    body=msg_body,
                    direction="out",
                    status="delivered",
                    teachback_label=None,
                    at=(created_at + timedelta(hours=2)).isoformat(),
                )
            ]
            if arch.get("teachback_label"):
                messages.append(
                    dict(
                        channel="portal",
                        language=lang,
                        body="I am not sure what test I need or when to come in.",
                        direction="in",
                        status="received",
                        teachback_label=arch["teachback_label"],
                        at=(state_entered_at + timedelta(hours=1)).isoformat(),
                    )
                )

            survival_curve = [
                {"day": d, "s": round(max(0.04, 1.0 - (d / 130.0) * (1.15 - 0.5 * p_dropoff)), 3)}
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
                "cited_drivers": ["prior_noshow_ratio", "scheduling_lead_time", "distance_miles"],
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
                "recommendation": "Accept referral and schedule diagnostic appointment within SLA.",
            }
            act_type = (
                "reassign_owner"
                if arch["state"] == "REJECTED"
                else ("priority_rebook" if arch.get("missed_visit") else "create_navigator_task")
            )
            st_iso = state_entered_at.isoformat()
            ref_st = arch.get("referral_status")
            r_stage = arch["state"] if arch["state"] != "CLOSED" else "TREATMENT_OR_SURVEILLANCE"
            cases.append(
                {
                    "case_id": case_id,
                    "archetype_id": arch["id"],
                    "archetype_name": arch["name"],
                    "patient": {
                        "id": patient_id, "alias": f"PT-{idx:03d}", "age": age, "language": lang,
                        "insurance": ins, "distance_miles": distance,
                        "portal_active": portal_active, "prior_noshow_count": noshow_count,
                        "prior_noshow_ratio": noshow_ratio,
                        "days_since_last_encounter": 45 + (idx * 13) % 400,
                    },
                    "case": {
                        "id": case_id, "patient_id": patient_id, "screening_type": screening,
                        "severity_grade": severity_grade, "urgency_tier": tier,
                        "urgent_flag": urgent_flag, "state": arch["state"],
                        "state_entered_at": st_iso,
                        "owner_role": OWNER_ROLE_BY_STATE.get(arch["state"]),
                        "owner_id": arch["owner_id"], "escalated": bool(arch["escalated"]),
                        "finding_to_order_days": finding_days, "scheduling_lead_time": lead_time,
                        "contact_attempts": 2 if arch["escalated"] else 1,
                        "acknowledged": bool(arch["acknowledged"]), "patient_token": pt_token,
                        "patient_token_hash": pt_token_hash, "created_at": created_at.isoformat(),
                        "closed_at": st_iso if arch["state"] == "CLOSED" else None,
                    },
                    "risk": {
                        "stage": r_stage, "p_dropoff": p_dropoff,
                        "median_days": round(18.0 + 35.0 * p_dropoff, 1),
                        "p_open_30": round(float(survival_curve[2]["s"]), 3),
                        "p_open_60": round(float(survival_curve[4]["s"]), 3),
                        "p_open_90": round(float(survival_curve[6]["s"]), 3),
                        "shap": {"top_positive": _SHAP_POS, "top_negative": _SHAP_NEG},
                        "survival_curve": survival_curve, "model_version": "1.0.0-seed",
                    },
                    "events": events, "evidence": evidences, "messages": messages,
                    "referral": (
                        {
                            "from_org": "Community Primary Care Screening Clinic",
                            "to_org": "Regional Diagnostic Specialty Center",
                            "status": ref_st, "reason_code": arch.get("reason_code"),
                            "sbar": sbar_out,
                            "created_at": (state_entered_at - timedelta(hours=4)).isoformat(),
                            "decided_at": st_iso if ref_st in {"accepted", "rejected"} else None,
                        }
                        if ref_st else None
                    ),
                    "consults": [
                        {
                            "kind": "clinician_to_clinician",
                            "status": "open" if arch["escalated"] else "answered",
                            "thread": [{
                                "sender_role": "coordinator",
                                "body": f"Please review follow-up pathway for {case_id}.",
                                "at": st_iso,
                            }],
                            "created_at": st_iso,
                        }
                    ],
                    "pending_approval": (
                        {
                            "action_type": act_type, "reasons": ["escalated_case", arch["name"]],
                            "payload": {
                                "channel": "sms", "owner_id": arch["owner_id"] or "coord-1",
                            },
                            "status": "pending",
                        }
                        if arch["escalated"] and arch["state"] != "CLOSED" else None
                    ),
                    "closure": (
                        {
                            "kind": arch["closure_kind"],
                            "evidence_type": arch.get("closure_evidence"),
                            "override_by": (
                                "clin-lead" if arch["closure_kind"] == "override" else None
                            ),
                            "override_reason": arch.get("override_reason"), "at": st_iso,
                        }
                        if arch["state"] == "CLOSED" else None
                    ),
                    "delay_reasons": (
                        [{
                            "code": arch.get("reason_code") or "transport_barrier",
                            "proposed_by": "llm", "confirmed": True,
                        }]
                        if arch["escalated"] else []
                    ),
                    "llm_outputs": [
                        _llm_row("case_summary", f"summary:{case_id}", summary_out),
                        _llm_row("patient_message", f"msg:{case_id}:{lang}", {"body": msg_body}),
                        _llm_row("sbar_note", f"sbar:{case_id}", sbar_out),
                    ],
                }
            )

    return {"base_time": BASE_TIME.isoformat(), "case_count": len(cases), "cases": cases}
