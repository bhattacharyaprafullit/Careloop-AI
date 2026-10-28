"""Groq LLM client with 12s timeout, 1 retry on invalid JSON, validator, and template fallback."""
import json
import logging
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.states import LLMKind
from app.llm.ads import compute_ads
from app.llm.cache import compute_input_hash, lookup_cached_llm_output, record_llm_output
from app.llm.prompts import SYSTEM_PROMPT, build_user_prompt
from app.llm.templates import build_template_output
from app.llm.validators import validate_llm_output

logger = logging.getLogger(__name__)

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"


def _call_groq_once(api_key: str, model: str, user_prompt: str) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "temperature": 0.2,
        "max_tokens": 400,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    }
    with httpx.Client(timeout=12.0) as client:
        resp = client.post(GROQ_CHAT_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    content = data["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("LLM response is not a JSON object")
    return parsed


def _compute_ads_for_output(
    kind: str, output: dict[str, Any], facts: dict[str, Any]
) -> float:
    if kind != LLMKind.CASE_SUMMARY.value:
        return 0.0
    cited = output.get("cited_drivers", [])
    pos_raw = facts.get("shap_top_positive", [])
    pos_feats: list[str] = [
        str(item.get("feature") if isinstance(item, dict) else item)
        for item in pos_raw
    ]
    return compute_ads(cited, pos_feats)


def generate_validated_llm_output(
    kind: str,
    facts: dict[str, Any],
    *,
    db: Session | None = None,
    sandbox_id: str = "local",
    case_id: str = "local",
    raw_llm_Override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate, validate, cache, and log an LLM output (falls back to templates.py).

    Returns dict with keys: output, source, faithful_ok, ads, input_hash.
    """
    input_hash = compute_input_hash(kind, facts)

    if db is not None and raw_llm_Override is None:
        cached = lookup_cached_llm_output(db, sandbox_id=sandbox_id, input_hash=input_hash)
        if cached is not None:
            return {
                "output": cached.output,
                "source": cached.source,
                "faithful_ok": cached.faithful_ok,
                "ads": float(cached.ads or 0.0),
                "input_hash": input_hash,
            }

    settings = get_settings()
    candidate: dict[str, Any] | None = None
    source = "template"

    if raw_llm_Override is not None:
        candidate = raw_llm_Override
        source = "groq"
    elif settings.llm_enabled and settings.groq_api_key is not None:
        api_key = settings.groq_api_key.get_secret_value()
        user_prompt = build_user_prompt(kind, facts)
        # Try up to 2 attempts (initial + 1 retry on invalid JSON/error)
        for attempt in range(2):
            try:
                candidate = _call_groq_once(api_key, settings.llm_model, user_prompt)
                source = "groq"
                break
            except Exception as exc:
                logger.warning(
                    "Groq call attempt failed",
                    extra={"kind": kind, "attempt": attempt + 1, "err": str(exc)},
                )

    faithful_ok = True
    if candidate is not None:
        ok, reason = validate_llm_output(kind, candidate, facts)
        if not ok:
            logger.info(
                "LLM output rejected by validator; falling back to template",
                extra={"kind": kind, "reason": reason},
            )
            faithful_ok = False
            candidate = None

    if candidate is None:
        candidate = build_template_output(kind, facts)
        source = "template"
        ok_tpl, reason_tpl = validate_llm_output(kind, candidate, facts)
        assert ok_tpl, f"Template failed validator for {kind}: {reason_tpl}"

    ads = _compute_ads_for_output(kind, candidate, facts)

    if db is not None:
        record_llm_output(
            db,
            sandbox_id=sandbox_id,
            case_id=case_id,
            kind=kind,
            input_hash=input_hash,
            output=candidate,
            source=source,
            faithful_ok=faithful_ok,
            ads=ads,
        )

    return {
        "output": candidate,
        "source": source,
        "faithful_ok": faithful_ok,
        "ads": ads,
        "input_hash": input_hash,
    }
