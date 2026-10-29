"""Repository and seed loader for CareLoop AI (M4).

Every state change, message, decision, and LLM call writes an append-only row.
"""
import hashlib
import json
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.clock import ClockFn, make_clock, utc_now
from app.core.config import get_settings
from app.db.models import (
    Case,
    CaseEvent,
    Closure,
    Consult,
    DelayReason,
    Evidence,
    LLMOutput,
    Message,
    Patient,
    PendingApproval,
    Referral,
    RiskScore,
    Sandbox,
)

logger = logging.getLogger(__name__)
MAX_CASES_PER_SANDBOX = 250


def _uid(prefix: str = "") -> str:
    h = uuid.uuid4().hex[:16]
    return f"{prefix}-{h}" if prefix else h


def _parse_dt(val: str | datetime | None) -> datetime | None:
    if val is None:
        return None
    dt = val if isinstance(val, datetime) else datetime.fromisoformat(val)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _shift_dt(val: str | datetime | None, base: datetime, shift: timedelta) -> datetime:
    return (_parse_dt(val) or base) + shift


def hash_token(token: str) -> str:
    """Return SHA-256 hex digest of a sandbox or patient token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def load_seed_data(model_dir: Path | None = None) -> dict[str, Any]:
    """Load the 60-case seed payload from ml/artifacts/seed.json."""
    mdir = model_dir or get_settings().model_dir
    return dict(json.loads((Path(mdir) / "seed.json").read_text(encoding="utf-8")))


def clone_seed_into_sandbox(
    db: Session,
    *,
    sandbox_id: str,
    token_hash: str,
    now: datetime | None = None,
    model_dir: Path | None = None,
) -> Sandbox:
    """Clone all 60 seed cases and pre-generated LLM outputs under `sandbox_id`."""
    seed = load_seed_data(model_dir)
    base_time = _parse_dt(seed["base_time"]) or utc_now()
    current_now = now or utc_now()
    shift = current_now - base_time

    sb = Sandbox(
        id=sandbox_id,
        token_hash=token_hash,
        clock_offset_hours=0.0,
        created_at=current_now,
        expires_at=current_now + timedelta(hours=24),
    )
    db.add(sb)
    db.flush()

    c_keys = (
        "screening_type", "severity_grade", "urgency_tier", "state", "owner_role",
        "owner_id", "escalated", "finding_to_order_days", "scheduling_lead_time",
        "contact_attempts", "acknowledged",
    )
    ev_keys = ("event_type", "from_state", "to_state", "actor_role", "actor_id")
    m_keys = ("channel", "language", "direction", "status", "teachback_label")
    r_keys = ("from_org", "to_org", "status", "reason_code", "sbar")
    cl_keys = ("kind", "evidence_type", "override_by", "override_reason")

    for item in seed["cases"]:
        idx_suffix = str(item["case_id"]).split("-")[-1]
        cid, pid = f"{sandbox_id[:8]}-case-{idx_suffix}", f"{sandbox_id[:8]}-pat-{idx_suffix}"
        pt_plain = f"pt-{sandbox_id[:8]}-{idx_suffix}"
        db.add(
            Patient(
                id=pid,
                sandbox_id=sandbox_id,
                **{k: v for k, v in item["patient"].items() if k != "id"},
            )
        )

        c_raw = item["case"]
        st_entered = _shift_dt(c_raw["state_entered_at"], base_time, shift)
        c_created = _shift_dt(c_raw["created_at"], base_time, shift)
        parsed_closed = _parse_dt(c_raw.get("closed_at"))
        db.add(
            Case(
                id=cid, sandbox_id=sandbox_id, patient_id=pid, state_entered_at=st_entered,
                patient_token_hash=hash_token(pt_plain), created_at=c_created,
                closed_at=(parsed_closed + shift) if parsed_closed else None,
                **{k: c_raw[k] for k in c_keys},
            )
        )
        db.add(
            RiskScore(
                id=_uid("rs"), sandbox_id=sandbox_id, case_id=cid, at=st_entered, **item["risk"]
            )
        )

        for ev in item["events"]:
            db.add(
                CaseEvent(
                    id=_uid("ev"), sandbox_id=sandbox_id, case_id=cid,
                    payload={**(ev.get("payload") or {}), "patient_token": pt_plain},
                    at=_shift_dt(ev["at"], base_time, shift),
                    **{k: ev.get(k) for k in ev_keys},
                )
            )

        for evd in item["evidence"]:
            db.add(
                Evidence(
                    id=_uid("evd"), sandbox_id=sandbox_id, case_id=cid,
                    at=_shift_dt(evd["at"], base_time, shift),
                    **{k: evd[k] for k in ("type", "ref", "created_by")},
                )
            )

        for msg in item["messages"]:
            db.add(
                Message(
                    id=_uid("msg"), sandbox_id=sandbox_id, case_id=cid,
                    body=str(msg["body"]).replace(item["case_id"], cid),
                    at=_shift_dt(msg["at"], base_time, shift),
                    **{k: msg.get(k) for k in m_keys},
                )
            )

        if item.get("referral"):
            ref = item["referral"]
            dec_dt = _parse_dt(ref.get("decided_at"))
            db.add(
                Referral(
                    id=_uid("ref"), sandbox_id=sandbox_id, case_id=cid,
                    created_at=_shift_dt(ref["created_at"], base_time, shift),
                    decided_at=(dec_dt + shift) if dec_dt else None,
                    **{k: ref.get(k) for k in r_keys},
                )
            )

        for con in item.get("consults", []):
            db.add(
                Consult(
                    id=_uid("con"), sandbox_id=sandbox_id, case_id=cid,
                    created_at=_shift_dt(con["created_at"], base_time, shift),
                    **{k: con[k] for k in ("kind", "status", "thread")},
                )
            )

        if item.get("pending_approval"):
            db.add(
                PendingApproval(
                    id=_uid("pa"), sandbox_id=sandbox_id, case_id=cid,
                    at=st_entered, **item["pending_approval"],
                )
            )

        if item.get("closure"):
            cl = item["closure"]
            db.add(
                Closure(
                    id=_uid("cl"), sandbox_id=sandbox_id, case_id=cid,
                    at=_shift_dt(cl["at"], base_time, shift),
                    **{k: cl.get(k) for k in cl_keys},
                )
            )

        for dr in item.get("delay_reasons", []):
            db.add(
                DelayReason(
                    id=_uid("dr"), sandbox_id=sandbox_id, case_id=cid, at=st_entered, **dr
                )
            )

        for lo in item.get("llm_outputs", []):
            out_dict = json.loads(json.dumps(lo["output"]).replace(item["case_id"], cid))
            db.add(
                LLMOutput(
                    id=_uid("llm"), sandbox_id=sandbox_id, case_id=cid, kind=str(lo["kind"]),
                    input_hash=hashlib.sha256(f"{lo['kind']}:{cid}".encode()).hexdigest(),
                    output=out_dict, source=str(lo["source"]), faithful_ok=bool(lo["faithful_ok"]),
                    ads=float(lo["ads"]) if lo.get("ads") is not None else 0.0, at=st_entered,
                )
            )

    db.commit()
    db.refresh(sb)
    return sb


def create_sandbox_with_seed(
    db: Session, model_dir: Path | None = None
) -> tuple[str, Sandbox, int]:
    """Generate a new sandbox token, clone the 60 seed cases, and return (token, sandbox, 60)."""
    raw_token = f"sbx_{secrets.token_urlsafe(24)}"
    sb = clone_seed_into_sandbox(
        db, sandbox_id=_uid("sbx"), token_hash=hash_token(raw_token), model_dir=model_dir
    )
    return raw_token, sb, 60


def purge_sandbox_data(db: Session, sandbox_id: str) -> None:
    """Delete a sandbox and all its child rows (deletes Sandbox first to satisfy triggers)."""
    db.execute(delete(Sandbox).where(Sandbox.id == sandbox_id))
    child_models = (
        CaseEvent, Closure, LLMOutput, Evidence, RiskScore, Referral,
        Consult, Message, PendingApproval, DelayReason, Case, Patient,
    )
    for model_cls in child_models:
        db.execute(delete(model_cls).where(model_cls.sandbox_id == sandbox_id))
    db.commit()


def get_sandbox_by_token(db: Session, token: str) -> Sandbox | None:
    """Look up an active (non-expired) sandbox by its plain token."""
    sb = db.scalar(select(Sandbox).where(Sandbox.token_hash == hash_token(token)))
    if sb is None:
        return None
    exp = sb.expires_at if sb.expires_at.tzinfo else sb.expires_at.replace(tzinfo=UTC)
    return sb if exp >= utc_now() else None


def clock_for_sandbox(sb: Sandbox) -> ClockFn:
    """Return an injectable clock shifted by `sb.clock_offset_hours`."""
    return make_clock(float(sb.clock_offset_hours))


def append_case_event(
    db: Session,
    *,
    sandbox_id: str,
    case_id: str,
    event_type: str,
    actor_role: str,
    actor_id: str | None = None,
    from_state: str | None = None,
    to_state: str | None = None,
    payload: dict[str, Any] | None = None,
    at: datetime | None = None,
) -> CaseEvent:
    """Insert an immutable row into case_events."""
    ev = CaseEvent(
        id=_uid("ev"), sandbox_id=sandbox_id, case_id=case_id, event_type=event_type,
        from_state=from_state, to_state=to_state, actor_role=actor_role,
        actor_id=actor_id, payload=payload or {}, at=at or utc_now(),
    )
    db.add(ev)
    return ev
