"""Validators for LLM outputs: fact-grounding, banned phrases, word limits, and language (M6)."""
import json
import logging
import re
from typing import Any, Final

from ml.data.schema import FEATURE_COLUMNS

from app.domain.states import LLMKind, ReasonCode, TeachBackLabel

logger = logging.getLogger(__name__)

BANNED_PHRASES: Final[tuple[str, ...]] = (
    "you have cancer",
    "diagnosis is",
    "prescribe",
    "take this medicine",
    "prognosis",
    "malignant tumor",
    "terminal",
    "fatal",
)

STOPWORDS_BY_LANG: Final[dict[str, tuple[str, ...]]] = {
    "en": ("your", "the", "please", "by", "to", "result", "reply", "portal"),
    "hi": ("आपकी", "कृपया", "तक", "है", "के", "में", "परिणाम", "चुनें"),
    "es": ("su", "por", "favor", "el", "en", "resultado", "antes", "del", "responda"),
}

_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


def _extract_numbers_and_dates(text: str) -> tuple[set[str], set[str]]:
    dates = set(_DATE_RE.findall(text))
    # Strip dates first so YYYY, MM, DD aren't double-counted as standalone numbers
    scrubbed = _DATE_RE.sub(" ", text)
    nums = set(_NUMBER_RE.findall(scrubbed))
    return nums, dates


def _allowed_facts_tokens(facts: dict[str, Any]) -> tuple[set[str], set[str]]:
    serialized = json.dumps(facts, ensure_ascii=False)
    nums, dates = _extract_numbers_and_dates(serialized)
    # Also allow normalized integer forms of floats like 24.0 -> "24"
    normalized_nums = set(nums)
    for n in list(nums):
        try:
            fval = float(n)
            if fval.is_integer():
                normalized_nums.add(str(int(fval)))
        except ValueError:
            pass
    return normalized_nums, dates


def check_no_banned_phrases(text: str) -> tuple[bool, str]:
    """Ensure text contains none of the prohibited diagnostic/prescribing phrases."""
    lower = text.lower()
    for phrase in BANNED_PHRASES:
        if phrase in lower:
            return False, f"banned phrase detected: '{phrase}'"
    return True, "ok"


def check_numbers_and_dates_in_facts(text: str, facts: dict[str, Any]) -> tuple[bool, str]:
    """Every number and YYYY-MM-DD date in `text` must appear in `facts`."""
    out_nums, out_dates = _extract_numbers_and_dates(text)
    allowed_nums, allowed_dates = _allowed_facts_tokens(facts)

    invented_dates = out_dates - allowed_dates
    if invented_dates:
        return False, f"invented date(s) not in FACTS: {sorted(invented_dates)}"

    invented_nums = out_nums - allowed_nums
    if invented_nums:
        return False, f"invented number(s) not in FACTS: {sorted(invented_nums)}"

    return True, "ok"


def check_language_heuristic(text: str, lang: str) -> tuple[bool, str]:
    """Check message language using a stopword heuristic for en, hi, es."""
    target = lang if lang in STOPWORDS_BY_LANG else "en"
    stopwords = STOPWORDS_BY_LANG[target]
    lower = text.lower()
    matches = sum(1 for w in stopwords if w in lower)
    if matches < 2:
        return False, f"text failed {target} stopword heuristic (matches={matches})"
    return True, "ok"


def word_count(text: str) -> int:
    return len([w for w in text.strip().split() if w])


def validate_llm_output(
    kind: str, output: dict[str, Any], facts: dict[str, Any]
) -> tuple[bool, str]:
    """Validate structured output against all spec rules for `kind`."""
    serialized = json.dumps(output, ensure_ascii=False)
    ok_ban, msg_ban = check_no_banned_phrases(serialized)
    if not ok_ban:
        return False, msg_ban

    if kind == LLMKind.CASE_SUMMARY.value:
        lines = output.get("summary_lines")
        next_step = output.get("next_step")
        drivers = output.get("cited_drivers")
        if not isinstance(lines, list) or not (1 <= len(lines) <= 5):
            return False, "summary_lines must be a list of 1 to 5 strings"
        if not isinstance(next_step, str) or not next_step.strip():
            return False, "next_step is required"
        if not isinstance(drivers, list) or not all(d in FEATURE_COLUMNS for d in drivers):
            return False, "cited_drivers must be valid feature names from FEATURE_COLUMNS"
        combined_text = " ".join(str(x) for x in lines) + " " + next_step
        return check_numbers_and_dates_in_facts(combined_text, facts)

    if kind == LLMKind.PATIENT_MESSAGE.value:
        body = output.get("body")
        if not isinstance(body, str) or not body.strip():
            return False, "patient_message body is empty"
        if word_count(body) > 60:
            return False, f"patient_message exceeds 60 words ({word_count(body)})"
        ok_num, msg_num = check_numbers_and_dates_in_facts(body, facts)
        if not ok_num:
            return False, msg_num
        test_name = str(facts.get("test_name", ""))
        due_date = str(facts.get("due_date", ""))
        if test_name and test_name.lower() not in body.lower():
            return False, f"patient_message missing test_name '{test_name}'"
        if due_date and due_date not in body:
            return False, f"patient_message missing due_date '{due_date}'"
        lang = str(facts.get("language", "en"))
        return check_language_heuristic(body, lang)

    if kind == LLMKind.TEACHBACK.value:
        label = output.get("label")
        valid_labels = {t.value for t in TeachBackLabel}
        if label not in valid_labels:
            return False, f"invalid teachback label '{label}'"
        reply = str(facts.get("patient_reply", "")).strip()
        if not reply and label != TeachBackLabel.CONFUSED.value:
            return False, "empty patient reply must be labeled 'confused'"
        return True, "ok"

    if kind == LLMKind.SBAR_NOTE.value:
        for field in ("situation", "background", "assessment", "recommendation"):
            val = output.get(field)
            if not isinstance(val, str) or not val.strip():
                return False, f"sbar_note missing '{field}'"
            if word_count(val) > 40:
                return False, f"sbar_note '{field}' exceeds 40 words"
            ok_num, msg_num = check_numbers_and_dates_in_facts(val, facts)
            if not ok_num:
                return False, msg_num
        return True, "ok"

    if kind == LLMKind.DELAY_REASON.value:
        code = output.get("code")
        valid_codes = {r.value for r in ReasonCode}
        if code not in valid_codes:
            return False, f"delay_reason code '{code}' not in ReasonCode"
        return True, "ok"

    return False, f"unknown LLM kind '{kind}'"
