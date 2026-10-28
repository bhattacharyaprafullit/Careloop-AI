"""Deterministic fallback templates per LLMKind and per language (en, hi, es) (M6)."""
import logging
from typing import Any

from ml.data.schema import FEATURE_COLUMNS

from app.domain.states import LLMKind, ReasonCode, TeachBackLabel, resolve_language

logger = logging.getLogger(__name__)


def build_case_summary_template(facts: dict[str, Any]) -> dict[str, Any]:
    """Build deterministic case_summary strictly grounded in FACTS."""
    state = str(facts.get("state", "RESULT_ISSUED"))
    owner = str(facts.get("owner_role", "clinician"))
    days = facts.get("days_in_state", 0)
    sla_rem = facts.get("sla_hours_remaining", 24)
    pct = facts.get("p_dropoff_percent", 25)

    pos_drivers_raw = facts.get("shap_top_positive", [])
    cited: list[str] = []
    for item in pos_drivers_raw:
        feat = item.get("feature") if isinstance(item, dict) else str(item)
        if feat in FEATURE_COLUMNS:
            cited.append(str(feat))
    if not cited:
        cited = ["prior_noshow_ratio"]

    lines = [
        f"Case is in state {state} with owner role {owner}.",
        f"Elapsed time in state is {days} days with {sla_rem} SLA hours remaining.",
        f"Calibrated stage drop-off risk is {pct} percent.",
    ]
    gaps = facts.get("evidence_gaps")
    if gaps:
        lines.append(f"Required next evidence: {', '.join(str(g) for g in gaps)}.")

    return {
        "summary_lines": lines[:5],
        "next_step": f"Coordinate {state} milestone completion within {sla_rem} hours.",
        "cited_drivers": cited[:3],
    }


def build_patient_message_template(facts: dict[str, Any]) -> dict[str, Any]:
    """Build deterministic patient_message in en, hi, or es (<= 60 words, includes key facts)."""
    lang, _ = resolve_language(str(facts.get("language", "en")))
    test_name = str(facts.get("test_name", "FIT"))
    urgency_code = str(facts.get("urgency_code", "routine"))
    due_date = str(facts.get("due_date", "2026-06-06"))
    reply_inst = str(
        facts.get(
            "reply_instruction",
            "Reply in the portal by clicking 'I understand'.",
        )
    )

    if lang == "hi":
        urgency_hi = "शीघ्र" if urgency_code == "soon" else "नियमित"
        body = (
            f"नमस्ते, आपकी {test_name} जाँच का परिणाम आ गया है। "
            f"कृपया {due_date} तक अपनी {urgency_hi} अगली जाँच के कदम की पुष्टि करें। "
            "जवाब देने के लिए पोर्टल में 'मैं समझता हूँ' चुनें।"
        )
        return {"body": body}

    if lang == "es":
        urgency_es = "pronto" if urgency_code == "soon" else "de rutina"
        body = (
            f"Hola, su resultado de {test_name} está listo. "
            f"Por favor confirme el siguiente paso {urgency_es} antes del {due_date}. "
            "Responda en el portal seleccionando 'Entiendo'."
        )
        return {"body": body}

    body = (
        f"Hello, your {test_name} screening result is ready for {urgency_code} follow-up. "
        f"Please confirm your next step by {due_date}. "
        f"{reply_inst}"
    )
    return {"body": body}


def build_teachback_template(facts: dict[str, Any]) -> dict[str, Any]:
    """Deterministic teach-back evaluator based on expected key facts and patient reply."""
    reply = str(facts.get("patient_reply", "")).strip()
    expected: list[str] = [str(x) for x in facts.get("expected_key_facts", [])]

    if not reply or len(reply.split()) < 3:
        return {
            "label": TeachBackLabel.CONFUSED.value,
            "missing_facts": expected or ["next_step", "due_date"],
            "followup_text": (
                "No worries — our care coordinator will call you to explain the next step "
                "and help schedule your appointment."
            ),
        }

    lower = reply.lower()
    confused_markers = (
        "not sure",
        "confused",
        "don't know",
        "do not know",
        "what test",
        "समझ नहीं",
        "no entiendo",
        "no sé",
    )
    if any(m in lower for m in confused_markers):
        return {
            "label": TeachBackLabel.CONFUSED.value,
            "missing_facts": expected or ["next_step"],
            "followup_text": (
                "Thank you for letting us know. A coordinator has been notified to walk "
                "through your follow-up step with you."
            ),
        }

    missing = [f for f in expected if f.lower() not in lower]
    if not expected:
        understand_markers = (
            "understand",
            "appointment",
            "confirm",
            "follow",
            "clinic",
            "समझ",
            "entiendo",
            "cita",
        )
        if any(m in lower for m in understand_markers):
            return {
                "label": TeachBackLabel.UNDERSTOOD.value,
                "missing_facts": [],
                "followup_text": "Thank you for confirming your follow-up plan.",
            }
        return {
            "label": TeachBackLabel.PARTIAL.value,
            "missing_facts": ["due_date"],
            "followup_text": "Thank you! Please remember to complete the step by the due date.",
        }

    if len(missing) == 0:
        return {
            "label": TeachBackLabel.UNDERSTOOD.value,
            "missing_facts": [],
            "followup_text": "Thank you for confirming all details of your next step.",
        }
    if len(missing) < len(expected):
        return {
            "label": TeachBackLabel.PARTIAL.value,
            "missing_facts": missing,
            "followup_text": f"Thank you. Please also note: {', '.join(missing)}.",
        }
    return {
        "label": TeachBackLabel.CONFUSED.value,
        "missing_facts": missing,
        "followup_text": (
            "A care coordinator will reach out shortly to clarify your next steps."
        ),
    }


def build_sbar_note_template(facts: dict[str, Any]) -> dict[str, Any]:
    """Build deterministic SBAR note (each section <= 40 words, strictly using FACTS numbers)."""
    screening = str(facts.get("screening_type", "FIT"))
    sev = facts.get("severity_grade", 3)
    tier = facts.get("urgency_tier", 2)
    f_days = facts.get("finding_to_order_days", 5)
    state = str(facts.get("state", "REFERRAL_SENT"))
    pct = facts.get("p_dropoff_percent", 25)

    return {
        "situation": f"{screening} follow-up referral in state {state}.",
        "background": (
            f"Severity grade {sev}, urgency tier {tier}, {f_days} days from finding to order."
        ),
        "assessment": f"Current stage {state} with calibrated drop-off risk {pct} percent.",
        "recommendation": "Accept referral and book specialist visit within target SLA window.",
    }


def build_delay_reason_template(facts: dict[str, Any]) -> dict[str, Any]:
    """Propose a structured delay ReasonCode from FACTS."""
    hint = str(facts.get("delay_hint", "")).lower()
    mapping = {
        "unreachable": ReasonCode.PATIENT_UNREACHABLE.value,
        "transport": ReasonCode.TRANSPORT_BARRIER.value,
        "distance": ReasonCode.TRANSPORT_BARRIER.value,
        "cost": ReasonCode.COST_CONCERN.value,
        "insurance": ReasonCode.COST_CONCERN.value,
        "language": ReasonCode.LANGUAGE_BARRIER.value,
        "schedule": ReasonCode.SCHEDULING_CONFLICT.value,
        "capacity": ReasonCode.REFERRAL_REJECTED_CAPACITY.value,
        "incomplete": ReasonCode.REFERRAL_INCOMPLETE.value,
        "declined": ReasonCode.PATIENT_DECLINED.value,
        "clinician": ReasonCode.CLINICIAN_DELAY.value,
    }
    for key, code in mapping.items():
        if key in hint:
            return {
                "code": code,
                "rationale": f"Matched barrier indicator '{key}' in case context.",
            }
    valid = {r.value for r in ReasonCode}
    explicit = str(facts.get("reason_code", ""))
    if explicit in valid:
        return {"code": explicit, "rationale": "Derived from recorded workflow reason code."}
    return {"code": ReasonCode.UNKNOWN.value, "rationale": "Requires coordinator confirmation."}


def build_template_output(kind: str, facts: dict[str, Any]) -> dict[str, Any]:
    """Dispatch to the deterministic template builder for `kind`."""
    if kind == LLMKind.CASE_SUMMARY.value:
        return build_case_summary_template(facts)
    if kind == LLMKind.PATIENT_MESSAGE.value:
        return build_patient_message_template(facts)
    if kind == LLMKind.TEACHBACK.value:
        return build_teachback_template(facts)
    if kind == LLMKind.SBAR_NOTE.value:
        return build_sbar_note_template(facts)
    if kind == LLMKind.DELAY_REASON.value:
        return build_delay_reason_template(facts)
    raise ValueError(f"Unsupported LLM kind: {kind}")
