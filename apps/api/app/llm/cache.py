"""SHA-256 input hashing and append-only llm_outputs cache (M6)."""
import hashlib
import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import utc_now
from app.db.models import LLMOutput

logger = logging.getLogger(__name__)


def compute_input_hash(kind: str, facts: dict[str, Any]) -> str:
    """Compute SHA-256 hash of `kind + canonical JSON of facts`."""
    canonical = json.dumps({"kind": kind, "facts": facts}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def lookup_cached_llm_output(
    db: Session,
    *,
    sandbox_id: str,
    input_hash: str,
) -> LLMOutput | None:
    """Return a previously validated LLMOutput row matching `input_hash` in the sandbox."""
    return db.scalar(
        select(LLMOutput)
        .where(
            LLMOutput.sandbox_id == sandbox_id,
            LLMOutput.input_hash == input_hash,
            LLMOutput.faithful_ok.is_(True),
        )
        .order_by(LLMOutput.at.desc())
    )


def record_llm_output(
    db: Session,
    *,
    sandbox_id: str,
    case_id: str,
    kind: str,
    input_hash: str,
    output: dict[str, Any],
    source: str,
    faithful_ok: bool,
    ads: float | None = None,
) -> LLMOutput:
    """Write an append-only row into llm_outputs."""
    row = LLMOutput(
        sandbox_id=sandbox_id,
        case_id=case_id,
        kind=kind,
        input_hash=input_hash,
        output=output,
        source=source,
        faithful_ok=faithful_ok,
        ads=ads,
        at=utc_now(),
    )
    db.add(row)
    db.flush()
    return row
