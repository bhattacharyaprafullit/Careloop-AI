"""System and user prompt builders for Groq llama-3.3-70b-versatile (M6)."""
import json
import logging
from typing import Any, Final

from ml.data.schema import FEATURE_COLUMNS

from app.domain.states import LLMKind, ReasonCode

logger = logging.getLogger(__name__)

# Exact system prompt mandated by spec
SYSTEM_PROMPT: Final[str] = (
    "You are a care-coordination assistant that helps staff. You never diagnose, prescribe, "
    "or predict prognosis. Use only the values in FACTS. Do not write any number or date that "
    "is not in FACTS. Reply with JSON that matches the schema and nothing else."
)

SCHEMA_HINTS: Final[dict[str, str]] = {
    LLMKind.CASE_SUMMARY.value: (
        '{"summary_lines": ["line1", ... up to 5], "next_step": "string", '
        f'"cited_drivers": [subset of {list(FEATURE_COLUMNS)}]}}'
    ),
    LLMKind.PATIENT_MESSAGE.value: (
        '{"body": "short message <= 60 words in requested language, including test_name, '
        'due_date, and ending with reply_instruction"}'
    ),
    LLMKind.TEACHBACK.value: (
        '{"label": "understood|partial|confused", "missing_facts": ["..."], '
        '"followup_text": "clarifying response"}'
    ),
    LLMKind.SBAR_NOTE.value: (
        '{"situation": "<=40 words", "background": "<=40 words", '
        '"assessment": "<=40 words", "recommendation": "<=40 words"}'
    ),
    LLMKind.DELAY_REASON.value: (
        f'{{"code": "one of {[r.value for r in ReasonCode]}", "rationale": "short explanation"}}'
    ),
}


def build_user_prompt(kind: str, facts: dict[str, Any]) -> str:
    """Build deterministic user prompt containing FACTS and the required JSON schema."""
    facts_json = json.dumps(facts, ensure_ascii=False, sort_keys=True)
    schema_hint = SCHEMA_HINTS.get(kind, "{}")
    return f"TASK: {kind}\nFACTS: {facts_json}\nSCHEMA: {schema_hint}"
