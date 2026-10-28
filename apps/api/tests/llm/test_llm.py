"""M6 LLM tests: validators, invented numbers/dates, banned phrases, ADS, templates in en/hi/es."""
import logging

from app.domain.states import LLMKind
from app.llm.ads import ads_triggers_escalation, compute_ads
from app.llm.client import generate_validated_llm_output
from app.llm.validators import validate_llm_output, word_count

logger = logging.getLogger(__name__)


def test_r3_message_in_patient_language() -> None:
    """R3: Patient messages generated in en, hi, and es pass language stopword heuristic."""
    for lang in ("en", "hi", "es"):
        facts = {
            "language": lang,
            "test_name": "FIT",
            "urgency_code": "soon",
            "due_date": "2026-06-10",
            "reply_instruction": "Reply in the portal by clicking 'I understand'.",
        }
        res = generate_validated_llm_output(LLMKind.PATIENT_MESSAGE.value, facts)
        assert res["source"] == "template"
        assert res["faithful_ok"] is True
        ok, msg = validate_llm_output(LLMKind.PATIENT_MESSAGE.value, res["output"], facts)
        assert ok, msg


def test_r3_message_length_and_facts() -> None:
    """R3: Patient messages are <= 60 words, include key facts, and reject >60 words."""
    facts = {
        "language": "en",
        "test_name": "MAMMOGRAPHY",
        "urgency_code": "routine",
        "due_date": "2026-06-15",
        "reply_instruction": "Reply in the portal by clicking 'I understand'.",
    }
    res = generate_validated_llm_output(LLMKind.PATIENT_MESSAGE.value, facts)
    body = res["output"]["body"]
    assert word_count(body) <= 60
    assert "MAMMOGRAPHY" in body
    assert "2026-06-15" in body

    # Over-length message is rejected
    too_long = {"body": ("word " * 65) + "MAMMOGRAPHY 2026-06-15 your the please"}
    ok, reason = validate_llm_output(LLMKind.PATIENT_MESSAGE.value, too_long, facts)
    assert not ok
    assert "exceeds 60 words" in reason


def test_r4_sbar_facts_validated() -> None:
    """R4: SBAR notes must be <= 40 words per field and only contain numbers/dates in FACTS."""
    facts = {
        "screening_type": "PAP_HPV",
        "severity_grade": 4,
        "urgency_tier": 1,
        "finding_to_order_days": 6,
        "state": "REFERRAL_SENT",
        "p_dropoff_percent": 68,
    }
    res = generate_validated_llm_output(LLMKind.SBAR_NOTE.value, facts)
    sbar = res["output"]
    for key in ("situation", "background", "assessment", "recommendation"):
        assert word_count(sbar[key]) <= 40

    # Invented number (99) in SBAR is rejected and falls back to template
    bad_sbar = {
        "situation": "PAP_HPV referral in REFERRAL_SENT.",
        "background": "Severity grade 4, urgency tier 1, 99 days from finding.",
        "assessment": "Risk is 68 percent.",
        "recommendation": "Schedule visit.",
    }
    ok, reason = validate_llm_output(LLMKind.SBAR_NOTE.value, bad_sbar, facts)
    assert not ok
    assert "invented number" in reason


def test_invented_number_and_banned_phrase_rejected_and_falls_back() -> None:
    facts = {
        "state": "PATIENT_NOTIFIED",
        "owner_role": "coordinator",
        "days_in_state": 2,
        "sla_hours_remaining": 12,
        "p_dropoff_percent": 72,
        "shap_top_positive": [
            {"feature": "prior_noshow_ratio"},
            {"feature": "scheduling_lead_time"},
            {"feature": "distance_miles"},
        ],
    }

    # 1. Invented number 95 not in FACTS -> rejected, falls back to template
    unfaithful_num = {
        "summary_lines": ["Case has 95 percent drop-off probability."],
        "next_step": "Call patient within 12 hours.",
        "cited_drivers": ["prior_noshow_ratio"],
    }
    res1 = generate_validated_llm_output(
        LLMKind.CASE_SUMMARY.value, facts, raw_llm_Override=unfaithful_num
    )
    assert res1["source"] == "template"
    assert res1["faithful_ok"] is False
    assert "72" in " ".join(res1["output"]["summary_lines"])

    # 2. Banned phrase ("you have cancer" / "prescribe") -> rejected, falls back to template
    banned_out = {
        "summary_lines": ["Patient notified that you have cancer and need to prescribe therapy."],
        "next_step": "Call within 12 hours.",
        "cited_drivers": ["prior_noshow_ratio"],
    }
    res2 = generate_validated_llm_output(
        LLMKind.CASE_SUMMARY.value, facts, raw_llm_Override=banned_out
    )
    assert res2["source"] == "template"
    assert res2["faithful_ok"] is False


def test_ads_divergence_calculation() -> None:
    shap_top3 = ["prior_noshow_ratio", "scheduling_lead_time", "distance_miles"]
    assert compute_ads(shap_top3, shap_top3) == 0.0
    assert not ads_triggers_escalation(0.0)

    # 1 shared out of 5 union -> Jaccard = 0.2 -> ADS = 0.8 > 0.5 -> escalates
    divergent = ["prior_noshow_ratio", "patient_age", "contact_attempts"]
    ads = compute_ads(divergent, shap_top3)
    assert ads == 0.8
    assert ads_triggers_escalation(ads)
